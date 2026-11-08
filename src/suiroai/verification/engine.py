"""DSC-30 consumer of the owner-defined draft.3 contract.

Readers and review callbacks are trusted application code, never worker JSON.
There is intentionally no default interpretation of arbitrary forecast/prose
payloads and no autonomous workflow, customer consent, or external transport.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from typing import Callable

from suiroai.contracts import VERSION, digest, record_ref, validate_handoff, validate_record
from suiroai.integration.artifacts import ArtifactError

from .arithmetic import reconcile_orders
from .claims import check_claims


class VerificationError(ValueError):
    """No permitted response can be established from current evidence."""


def _key(ref):
    return ref["artifact_id"], ref["version"], ref["sha256"], ref["provenance"]


@dataclass(frozen=True)
class SourceReaders:
    """Explicit artifact adapters, agreed with producers, not a shared schema.

    Operational inputs use the supplied CSV headers. All other callbacks read
    measured bytes and return lists. Forecast rows: key/date/quantity/
    quantity_unit/as_of_date/latest_information_available_date. Scope: contract keys. Names: key/product_name/
    latest_information_available_date. No aggregate-to-daily interpolation.
    """

    inventory_ref: dict
    receipt_ref: dict
    policy_ref: dict
    scope_ref: dict
    names_ref: dict
    source_namespace: str
    forecast: Callable
    scope: Callable
    names: Callable
    # Use before_daily_demand only with a separately reviewed convention.
    receipt_timing: str = "unknown"
    manifest_ref: dict | None = None


class OutputVerifier:
    """Independent checks against a parent-supplied authoritative snapshot.

    current_records/current_artifacts must include the full current handoff,
    not a producer-selected subset. authenticate(records, raw_artifacts) must
    return literal True only after trusted parent review of currentness,
    permission, provenance, and verifier independence. A claimed actor name is
    never sufficient. Recreate this object when parent state changes.
    """

    def __init__(self, store, *, current_records, current_artifacts,
                 authenticate, verifier="DSC-30", allow_mock=False,
                 review_claim=None, review_narrative=None):
        if (not callable(authenticate) or not isinstance(verifier, str) or not verifier.strip()
                or type(allow_mock) is not bool):
            raise VerificationError("trusted parent authenticator and named verifier required")
        self.store = store
        self.record_refs = deepcopy(tuple(current_records))
        self.artifact_refs = deepcopy(tuple(current_artifacts))
        self.authenticate = authenticate
        self.verifier = verifier
        self.allow_mock = allow_mock
        self.review_claim = review_claim
        self.review_narrative = review_narrative

    def _snapshot(self):
        records = [self.store.read_record(ref) for ref in self.record_refs]
        artifacts = [(deepcopy(ref), self.store.read_bytes(ref)) for ref in self.artifact_refs]
        if self.authenticate(deepcopy(records), deepcopy(artifacts)) is not True:
            raise VerificationError("parent did not authenticate the current handoff")
        if not self.allow_mock and any(r["provenance"] == "mock"
                                       for r in (*self.record_refs, *self.artifact_refs)):
            raise VerificationError("mock evidence cannot establish a real customer run")
        errors = validate_handoff(records, list(self.artifact_refs))
        if errors:
            raise VerificationError("; ".join(errors))
        return records

    @staticmethod
    def _one(records, kind, *, optional=False):
        values = [r for r in records if r["kind"] == kind]
        if kind == "quantity_result" and values:
            return max(values, key=lambda r: r["artifact_version"])
        if len(values) != 1:
            if optional and not values:
                return None
            raise VerificationError(f"exactly one current {kind} required")
        return values[0]

    def _check(self, check_id, ok, expected, actual, refs):
        return {"check_id": check_id, "requirement_id": "DSC-30",
                "status": "pass" if ok else "fail", "expected": expected,
                "actual": actual, "evidence_refs": deepcopy(refs), "verifier": self.verifier}

    def _read_sources(self, readers, report, execution, records):
        if not isinstance(readers, SourceReaders) or not readers.source_namespace:
            raise VerificationError("explicit reviewed source readers required")
        if readers.receipt_timing != "unknown":
            raise VerificationError("this MVP requires conservative within-day timing; no approved alternative convention is supplied")
        known = {_key(r) for r in (*self.record_refs, *self.artifact_refs)}
        refs = [readers.inventory_ref, readers.receipt_ref, readers.policy_ref,
                readers.scope_ref, readers.names_ref, report["november_30_forecast_ref"]]
        if any(_key(r) not in known for r in refs):
            raise VerificationError("arithmetic source is outside the authenticated current snapshot")
        for ref in refs[:3]:
            if ref not in execution["source_refs"] or ref not in report["arithmetic_source_refs"]:
                raise VerificationError("operational source not bound to approved arithmetic inputs")
        # Source roles are verified against the actual submission, not inferred
        # from filenames chosen by the quantity producer.
        submission = self._one(records, "submission")
        for ref, role in zip(refs[:3], ("usable_stock", "inbound_ledger", "ordering_policy")):
            if not any(f["file_id"] == ref["artifact_id"] and f["sha256"] == ref["sha256"]
                       and f["source_role"] == role and f["access"] == "accessible"
                       and f["source_namespace"] == readers.source_namespace
                       for f in submission["files"]):
                raise VerificationError(f"source role/identity mismatch: {role}")

        def rows(ref):
            data = self.store.read_bytes(ref).decode("utf-8-sig")
            parsed = list(csv.DictReader(io.StringIO(data)))
            for row in parsed:
                row["source_namespace"] = readers.source_namespace
            return parsed

        forecast = deepcopy(readers.forecast(self.store.read_bytes(refs[-1])))
        stock, receipts, policies = [rows(r) for r in refs[:3]]
        scope = readers.scope(self.store.read_bytes(readers.scope_ref))
        if report["provenance"] != "mock":
            if any(row.get("Provenance") != "synthetic" for row in (*stock, *receipts, *policies)):
                raise VerificationError("operational row provenance differs from the synthetic scenario")
            if readers.manifest_ref is None or _key(readers.manifest_ref) not in known:
                raise VerificationError("current synthetic generation manifest is required for real scenario verification")
            manifest = json.loads(self.store.read_bytes(readers.manifest_ref))
            if manifest.get("review_date") != execution["temporal_plan"]["as_of_date"]:
                raise VerificationError("synthetic manifest review date mismatch")
            counts = manifest.get("counts", {})
            if any(counts.get(k) != count for k, count in (
                    ("inventory_rows", len(stock)), ("inbound_rows", len(receipts)),
                    ("policy_rows", len(policies)), ("eligible_product_store_keys", len(scope)))):
                raise VerificationError("synthetic manifest source/scope counts mismatch")
            for ref in refs[:3]:
                if ref not in execution["synthetic_operational_source_refs"] or ref["provenance"] != "synthetic":
                    raise VerificationError("synthetic operational source provenance mismatch")
                original = next(f["original_name"] for f in submission["files"] if f["file_id"] == ref["artifact_id"])
                entries = [v for k, v in manifest.get("files", {}).items() if k.rsplit("/", 1)[-1] == original]
                if len(entries) != 1 or entries[0].get("sha256") != ref["sha256"]:
                    raise VerificationError("synthetic manifest source hash mismatch")
            refs.append(readers.manifest_ref)
        return dict(scope_keys=scope,
                    forecast_rows=forecast, inventory_rows=stock,
                    receipt_rows=receipts, policy_rows=policies,
                    name_rows=readers.names(self.store.read_bytes(readers.names_ref)),
                    as_of=execution["temporal_plan"]["as_of_date"],
                    ledger_complete=execution["inbound_ledger_policy"] == "complete_synthetic_ledger_absence_is_zero",
                    receipt_timing=readers.receipt_timing), refs

    def _arithmetic(self, report, execution, records, readers, *, require_product_names=True):
        args, refs = self._read_sources(readers, report, execution, records)
        result = reconcile_orders(report["orders"], report["exceptions"], **args,
                                  require_product_names=require_product_names)
        checks = [self._check(f"{c['check_id']}-{index}", c["status"] == "pass", str(c["expected"]),
                              json.dumps({"actual": c["actual"], "key": c.get("key")}, sort_keys=True), refs)
                  for index, c in enumerate(result["checks"])]
        # Exceptions remain visible in the approved list; no hidden zero-fill.
        return checks, result

    def check_candidate(self, candidate_ref, *, readers, evidence_id, verified_at):
        """Emit independent numerical evidence before parent quantity approval."""
        records = self._snapshot()
        candidate = self.store.read_record(candidate_ref)
        if candidate_ref not in self.record_refs or candidate["kind"] != "quantity_result":
            raise VerificationError("candidate must be in the authenticated current handoff")
        if candidate["parent_decision"] is not None or any(
                r["approved_order_quantity"] is not None for r in candidate["orders"]):
            raise VerificationError("candidate cannot approve its own quantities")
        execution = self._one(records, "execution_contract")
        checks, reconciliation = self._arithmetic(candidate, execution, records, readers,
                                                  require_product_names=False)
        passed = bool(checks) and all(c["status"] == "pass" for c in checks)
        check = self._check("candidate-reconciliation", passed,
                            "independent source arithmetic and explicit per-key exceptions agree",
                            json.dumps({"checks": checks, "exceptions": reconciliation["exceptions"]},
                                       sort_keys=True), [candidate_ref, *candidate["arithmetic_source_refs"]])
        evidence = self._evidence(candidate, evidence_id, check, verified_at)
        self.store.put_record(evidence)
        return evidence

    def _evidence(self, record, artifact_id, check, verified_at):
        mock = record["provenance"] == "mock"
        evidence = {"kind": "evidence_record", "schema_version": VERSION,
                    "artifact_id": artifact_id, "artifact_version": 1,
                    "provenance": "mock" if mock else "derived",
                    "binding": deepcopy(record["binding"]), "run_id": record["run_id"],
                    "requirement_id": "DSC-30", "requirement_source": "https://linear.app/gr3enarr0w/issue/DSC-30",
                    "checked_artifacts": [record_ref(record)], "check": check,
                    "evidence_mode": "mock" if mock else "real",
                    "verifier_decision": "accepted" if check["status"] == "pass" else "rejected",
                    "verifier": self.verifier, "verified_at": verified_at,
                    "mock_limitation": "Component test only; no completed customer run." if mock else None}
        errors = validate_record(evidence)
        if errors:
            raise VerificationError("; ".join(errors))
        return evidence

    def verify_draft(self, report_ref, *, verification_id, readers=None):
        """Check-only proposal, always blocked until a later parent decision.

        Structural/currentness failures raise VerificationError and produce no
        response. Independent failed/unavailable checks return explicit blocked
        output_verification evidence, also with no response.
        """
        records = self._snapshot()
        report = self._one(records, "report_draft")
        if record_ref(report) != report_ref:
            raise VerificationError("draft is not the current parent-selected report")
        execution = self._one(records, "execution_contract")
        refs = [report_ref, record_ref(execution)]
        binding_checks = [self._check("current-handoff", True,
                                     "authenticated current task/run/input/proposal and immutable bytes",
                                     "full handoff resolved and contract graph checked", refs)]
        arithmetic = []
        if report["outcome"] == "success":
            final = self._one(records, "final_validation_result")
            quantity = self._one(records, "quantity_result")
            if (final["parent_review"]["checkpoint"] != "final_validation"
                    or quantity["parent_decision"]["checkpoint"] != "recommendations"
                    or report["parent_decision"]["checkpoint"] != "recommendations"):
                raise VerificationError("parent approvals belong to different checkpoints")
            arithmetic, _ = self._arithmetic(report, execution, records, readers)
        else:
            # Never gate an evidenced failure explanation on successful quantity
            # artifacts, and never mistake a pending review for a terminal run.
            stages = [r for r in records if r["kind"] == "stage_result"]
            if report["outcome"] == "execution_failure":
                def matches_terminal(stage):
                    if stage["outcome"] != "execution_failed" or stage["parent_decision"] is None:
                        return False
                    failure, draft_failure = stage["failure"], report["failure"]
                    stage_decision, draft_decision = stage["parent_decision"], report["parent_decision"]
                    stage_ref = record_ref(stage)
                    allowed_evidence = [stage_ref, *failure["evidence_refs"]]
                    # DSC-29 cites the failed stage instead of copying its
                    # internal log refs, and can reuse its authenticated parent
                    # decision. Neither needs a new terminal review or a
                    # circular decision reference to the stage containing it.
                    same_facts = all(draft_failure.get(field) == failure.get(field)
                                     for field in ("stage", "reason", "error_code"))
                    scoped_evidence = (bool(draft_failure["evidence_refs"])
                                       and all(ref in allowed_evidence for ref in draft_failure["evidence_refs"]))
                    exact_stage_edge = (stage_ref in draft_failure["evidence_refs"]
                                        or stage_ref in draft_decision["evidence_refs"])
                    reviewed = (stage_decision["checkpoint"] == stage["stage"]
                                and draft_decision["checkpoint"] == stage["stage"]
                                and stage_decision["decision"] in {"stop", "confirmed_failure"}
                                and draft_decision["decision"] in {"stop", "confirmed_failure"}
                                and (draft_decision == stage_decision
                                     or stage_ref in draft_decision["evidence_refs"]))
                    return same_facts and scoped_evidence and exact_stage_edge and reviewed

                matching = [stage for stage in stages if matches_terminal(stage)]
                binding_checks.append(self._check("terminal-execution-evidence", bool(matching),
                    "failure exactly matches a parent-reviewed failed stage",
                    f"matching failed stages: {len(matching)}", refs))
            elif report["outcome"] == "validation_failure":
                final = self._one(records, "final_validation_result")
                ok = (final["outcome"] == "fail" and final["parent_review"]["checkpoint"] == "final_validation"
                      and final["parent_review"]["decision"] in {"confirmed_failure", "stop"}
                      and report["final_validation_ref"] == record_ref(final))
                binding_checks.append(self._check("terminal-validation-evidence", ok,
                    "current failed frozen validation has concluded parent review",
                    final["outcome"] + ":" + final["parent_review"]["decision"], [*refs, record_ref(final)]))
            else:
                gaps = [g for r in stages if r["outcome"] in {"needs_inputs", "needs_material_facts"}
                        for g in r["gaps"] if g["material"]]
                binding_checks.append(self._check("material-gap-evidence", bool(gaps),
                    "actual material gaps support capability guidance", f"material gaps: {len(gaps)}", refs))
        claims = check_claims(report, resolve_bytes=self.store.read_bytes,
                              review_claim=self.review_claim, review_narrative=self.review_narrative,
                              verifier=self.verifier)
        result = {"kind": "output_verification", "schema_version": VERSION,
                  "artifact_id": verification_id, "artifact_version": 1,
                  "provenance": "mock" if report["provenance"] == "mock" else "derived",
                  "binding": deepcopy(report["binding"]), "run_id": report["run_id"],
                  "report_draft_ref": report_ref, "independent_verifier": self.verifier,
                  "independence_basis": "Separate source-byte Decimal reconciliation and trusted independent claim/full-text review; producer pass flags are unused.",
                  "arithmetic_checks": arithmetic, "claim_checks": claims,
                  "binding_checks": binding_checks, "decision": "blocked", "parent_decision": None,
                  "permitted_response": {"kind": "no_customer_response", "text": "", "report_ref": None}}
        errors = validate_record(result)
        if errors:
            raise VerificationError("; ".join(errors))
        self.store.put_record(result)
        return result

    def propose_delivery(self, verification_ref, *, parent_decision, readers=None):
        """Build a proposal for DSC-10 authentication; does not approve a run.

        Parent/adapter must authenticate the returned proposal before publishing.
        Its check evidence references the earlier immutable check-only version,
        avoiding self-reference. Runtime delivery reauthenticates current state.
        """
        previous = self.store.read_record(verification_ref)
        report_ref = previous["report_draft_ref"]
        fresh = self.verify_draft(report_ref, verification_id=previous["artifact_id"] + "/recheck", readers=readers)
        for field in ("arithmetic_checks", "claim_checks", "binding_checks"):
            if previous[field] != fresh[field] or not previous[field] or any(
                    c["status"] != "pass" for c in previous[field]):
                if field == "arithmetic_checks" and not previous[field] and not fresh[field]:
                    continue
                raise VerificationError("delivery blocked by changed, failed or unavailable independent checks")
        if (parent_decision.get("checkpoint") != "output_verification"
                or parent_decision.get("decision") != "proceed"
                or verification_ref not in parent_decision.get("evidence_refs", [])
                or report_ref not in parent_decision.get("evidence_refs", [])):
            raise VerificationError("parent delivery proposal must bind exact report and check-only evidence")
        report = self.store.read_record(report_ref)
        result = deepcopy(previous)
        result.update(artifact_version=previous["artifact_version"] + 1,
                      decision="delivery_allowed", parent_decision=deepcopy(parent_decision),
                      permitted_response={"kind": {"success": "final_report", "missing_inputs": "missing_input_guidance",
                                                   "validation_failure": "failure_explanation", "execution_failure": "failure_explanation"}[report["outcome"]],
                                          "text": report["customer_draft"], "report_ref": report_ref})
        errors = validate_record(result)
        if errors:
            raise VerificationError("; ".join(errors))
        return result

    def deliver(self, verification_ref, *, authorize, publish, readers=None):
        """Use the existing output surface and verify its actual readback.

        authorize(proposal) is a trusted current DSC-10 permission check, not a
        customer sign-off. publish(text_bytes) must deliver the bytes and return
        {reference: str, content: bytes} read back from that same surface. No
        transport, app, hosting, or messaging service is created here.
        """
        self._snapshot()
        approved = self.store.read_record(verification_ref)
        if approved["decision"] != "delivery_allowed" or not callable(authorize) or not callable(publish):
            raise VerificationError("parent-authorized verification and existing output surface required")
        decision = approved["parent_decision"]
        if not decision:
            raise VerificationError("current parent delivery authorization missing")
        check_refs = [r for r in decision["evidence_refs"] if r != approved["report_draft_ref"]]
        prior = [r for r in check_refs if r["artifact_id"] == approved["artifact_id"]
                 and r["version"] == approved["artifact_version"] - 1]
        if len(prior) != 1:
            raise VerificationError("delivery authorization lost exact independent check evidence")
        expected = self.propose_delivery(prior[0], parent_decision=decision, readers=readers)
        if expected != approved or authorize(deepcopy(approved)) is not True:
            raise VerificationError("delivery is stale, altered or not currently authorized by parent")
        content = approved["permitted_response"]["text"].encode("utf-8")
        # Reserve once before calling the output surface. The artifact store's
        # fresh directory operation is exclusive, including concurrent callers.
        # A failed/crashed attempt needs a newly reviewed verification version;
        # this consumer never retries an already-used customer delivery grant.
        try:
            self.store.stage_released([verification_ref, approved["report_draft_ref"]],
                                      self.store.root / "delivery-attempts" / digest(verification_ref))
        except ArtifactError as exc:
            raise VerificationError("delivery already attempted or its evidence namespace is unavailable") from exc
        receipt = publish(content)
        if (not isinstance(receipt, dict) or not isinstance(receipt.get("reference"), str)
                or not receipt["reference"] or receipt.get("content") != content
                or not isinstance(receipt.get("content"), bytes)):
            observed = receipt.get("content") if isinstance(receipt, dict) else None
            actual = ("readback_sha256=" + hashlib.sha256(observed).hexdigest()
                      if isinstance(observed, bytes) else "no valid byte readback")
            check = self._check("delivered-content", False,
                                "readback_sha256=" + hashlib.sha256(content).hexdigest(),
                                actual, [verification_ref, approved["report_draft_ref"]])
            evidence = self._evidence(approved, approved["artifact_id"] + "/delivery-mismatch",
                                      check, datetime.now(timezone.utc).isoformat())
            self.store.put_record(evidence)
            error = VerificationError("delivered content readback differs from the approved artifact")
            error.evidence_ref = record_ref(evidence)
            raise error
        measured = self.store.put_bytes(approved["artifact_id"] + "/delivered-text",
                                        approved["artifact_version"], approved["provenance"], content)
        if self.store.read_bytes(measured) != content:
            raise VerificationError("delivery evidence readback mismatch")
        now = datetime.now(timezone.utc).isoformat()
        check = self._check("delivered-content", True,
                            "delivered bytes equal exact parent-approved UTF-8 report",
                            "sha256=" + measured["sha256"],
                            [verification_ref, approved["report_draft_ref"], measured])
        evidence = self._evidence(approved, approved["artifact_id"] + "/delivery-check", check, now)
        self.store.put_record(evidence)
        return {"verification_ref": verification_ref,
                "report_ref": approved["report_draft_ref"], "delivered_artifact_ref": measured,
                "delivery_evidence_ref": record_ref(evidence),
                "destination_reference": receipt["reference"], "sha256": hashlib.sha256(content).hexdigest(),
                "verified_at": now,
                "mock": approved["provenance"] == "mock", "unresolved_blockers": [],
                "unresolved_exceptions": deepcopy(self.store.read_record(approved["report_draft_ref"])["exceptions"])}
