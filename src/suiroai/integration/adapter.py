"""DSC-26 stage boundary; DSC-10 retains all checkpoint decisions.

Dispatch retains the existing approval chain and uses the reviewed native
release/output boundary. Engineering evidence never authorizes a customer task.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid

from suiroai.contracts import VERSION, record_ref, validate_handoff, validate_record
from .artifacts import ArtifactStore, read_stage_file, _json_bytes
from .native import NativeHost


class AdapterRejected(ValueError):
    """Untrusted or invalid handoff: no worker was dispatched."""


class _BudgetExceeded(ValueError):
    pass


def _parent_claims(records):
    """Collect private authority claims at every depth, including rechecks."""
    decisions, prior = [], []

    def visit(value, path, ref):
        if isinstance(value, dict):
            for key, child in value.items():
                pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if key in {"parent_decision", "parent_review", "parent_authorization"} and child is not None:
                    if not isinstance(child, dict):
                        raise ValueError("parent authority claim is not an object")
                    claim = {"artifact_ref": deepcopy(ref), "json_pointer": pointer,
                             "decision_sha256": hashlib.sha256(_json_bytes(child)).hexdigest()}
                    (prior if key == "parent_authorization" else decisions).append(claim)
                visit(child, pointer, ref)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + "/" + str(index), ref)

    for record in records:
        visit(record, "", record_ref(record))
    return decisions, prior


def _compact(value, max_bytes=16384):
    """Large native details live in measured files, not the binding summary."""
    data = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return value if len(data) <= max_bytes else {
        "detail_omitted_due_limit": True, "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "see_native_evidence_refs": True}


def _refs(value):
    if isinstance(value, dict):
        if set(value) == {"artifact_id", "version", "sha256", "provenance"}:
            yield value
        else:
            for item in value.values():
                yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _key(ref):
    return json.dumps(ref, sort_keys=True)


def _check_snapshot():
    from suiroai.contracts import validation
    root = Path(validation.__file__).parent
    expected = {
        root / "schema/retail-contract.schema.json":
            "1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46",
        root / "validation.py":
            "7d407fdc73454c9942707609df4abea64aa30f036d436ed95cc87d6b305cddf3",
    }
    if VERSION != "0.1.0-draft.3" or any(
            hashlib.sha256(path.read_bytes()).hexdigest() != sha
            for path, sha in expected.items()):
        raise AdapterRejected("DSC-24 snapshot differs; owner agreement required")


class StageAdapter:
    """Accept existing immutable task records; never form or amend a task.

    ``parent_permits`` is supplied by the trusted DSC-10 process. It authenticates
    the exact stage-request reference independently of worker-authored JSON.
    Handoff refs include the current approval chain and upstream stage evidence;
    external refs must already exist in this measured store, not merely a list
    of caller-provided hashes. Mock handoffs are rejected by default.

    ``parent_review(candidate, artifact_bytes)`` is a trusted DSC-10 callback,
    required when component results contain parent authority claims. It adopts
    checkpoint decisions and authenticates prior authorizations against the
    parent's ledger using an exact candidate-bound receipt. It must bound its
    own I/O and return promptly; it cannot advance a checkpoint before the
    adapter commits the checked stage result.
    """

    def __init__(self, store: ArtifactStore, *, work_root: Path,
                 parent_permits, host=None, ceiling_seconds=300,
                 allow_mock_handoffs=False, parent_review=None):
        if not callable(parent_permits) or not 0 < ceiling_seconds <= 3600:
            raise ValueError("trusted parent verifier and finite ceiling required")
        self.store = store
        # The exercised native policy accepts physical roots. Resolve a trusted
        # deployment alias such as /tmp before creating fresh sibling stages.
        self.work_root = Path(work_root).resolve()
        self.parent_permits = parent_permits
        self.host = host or NativeHost()
        self.ceiling_seconds = ceiling_seconds
        self.allow_mock_handoffs = allow_mock_handoffs
        if parent_review is not None and not callable(parent_review):
            raise ValueError("parent_review must be a trusted callable")
        self.parent_review = parent_review

    def execute(self, request_ref, *, handoff_refs, external_refs=(),
                cancellation: threading.Event | None = None):
        started = time.monotonic()
        _check_snapshot()
        handoff_refs, external_refs = list(handoff_refs), list(external_refs)
        if len(handoff_refs) > 128 or len(external_refs) > 256:
            raise AdapterRejected("handoff reference count exceeds adapter bound")
        request = self.store.read_record(request_ref)
        if request.get("kind") != "stage_request" or validate_record(request):
            raise AdapterRejected("invalid stage request")
        if self.parent_permits(deepcopy(request_ref)) is not True:
            raise AdapterRejected("DSC-10 did not authorize this exact stage request")
        records = [self.store.read_record(ref) for ref in handoff_refs]
        records = [r for r in records if record_ref(r) != request_ref] + [request]
        mock_handoff = any(r["provenance"] == "mock" for r in records) or any(
            ref.get("provenance") == "mock" for ref in external_refs)
        if not self.allow_mock_handoffs and mock_handoff:
            raise AdapterRejected("mock handoff cannot authorize real execution")
        if mock_handoff and isinstance(self.host, NativeHost):
            raise AdapterRejected("mock handoff cannot dispatch a real NativeHost")
        if not isinstance(self.host, NativeHost) and not (self.allow_mock_handoffs and mock_handoff):
            raise AdapterRejected("an injected host is supported only for explicitly mocked development")
        # Measure referenced external bytes even though validate_handoff alone
        # only checks graph consistency. Reading occurs in the trusted adapter.
        total = 0
        for ref in external_refs:
            total += len(self.store.read_bytes(ref))
            if total > self.store.max_total_bytes:
                raise AdapterRejected("handoff external bytes exceed adapter bound")
        known = {_key(record_ref(r)) for r in records} | {_key(r) for r in external_refs}
        if any(_key(ref) not in known for r in records for ref in _refs(r)):
            raise AdapterRejected("handoff contains unresolved artifact references")
        executions = [r for r in records if r.get("kind") == "execution_contract"]
        if len(executions) != 1:
            raise AdapterRejected("one current execution contract required")
        execution = executions[0]
        # Exhaustion is an inspectable adapter outcome, not a dispatch. Shared
        # validator intentionally also rejects exhausted requests for dispatch.
        limit_errors = {
            "stage cannot dispatch with exhausted attempts or time",
            "model stage cannot dispatch with exhausted candidate budget",
            "feature stage cannot dispatch with exhausted feature budget",
            "stage request deadline exceeds remaining execution bound",
        }
        errors = validate_handoff(records, external_refs)
        exhausted = request["remaining_limits"]["max_execution_seconds"] == 0 or \
            request["remaining_limits"]["max_stage_attempts"] == 0
        exhausted |= request["stage"] in {"initial_baseline_evaluation", "comparison_and_freeze"} and \
            request["remaining_limits"]["max_candidates"] == 0
        exhausted |= request["stage"] == "llm_features" and \
            request["remaining_limits"]["max_llm_feature_definitions"] == 0
        remaining_errors = [e for e in errors if not (exhausted and e in limit_errors)]
        if remaining_errors:
            raise AdapterRejected("; ".join(remaining_errors))
        provenance = "mock" if mock_handoff else "derived"
        self.work_root.mkdir(parents=True, exist_ok=True)
        attempt_root = Path(tempfile.mkdtemp(prefix="stage-", dir=self.work_root))
        audit = {"request_ref": request_ref, "customer_model_turn_requested": False,
                 "mock_handoff": provenance == "mock", "events": [], "published_refs": [],
                 "published_output_bytes": 0,
                 "native_evidence_refs": [], "native_evidence_bytes": 0,
                 "controller_evidence_refs": [], "controller_evidence_bytes": 0,
                 "binding": deepcopy(request["binding"]), "run_id": request["run_id"],
                 "stage": request["stage"], "attempt": request["attempt"], "phase": "pre_dispatch"}

        def failure(code, reason):
            audit_bytes, evidence, result = self._failure_packet(request, request_ref, provenance, audit, code, reason)
            if validate_record(result):
                raise AdapterRejected("adapter generated invalid failure envelope")
            if self.store.put_bytes(evidence["artifact_id"], 1, provenance, audit_bytes) != evidence:
                raise AdapterRejected("failure evidence changed during publication")
            self.store.put_record(result)
            return result

        try:
            self._failure_packet(request, request_ref, provenance, audit, "integrity_error", "x" * 2048)
        except _BudgetExceeded as exc:
            raise AdapterRejected("artifact bounds cannot retain a minimal failure envelope") from exc
        if cancellation is not None and cancellation.is_set():
            return failure("cancelled", "Cancelled before native dispatch")
        if exhausted:
            return failure("budget_exhausted", "Parent supplied an exhausted stage limit; no turn started")
        deadline = datetime.fromisoformat(request["deadline"])
        seconds = min((deadline - datetime.now(timezone.utc)).total_seconds(),
                      request["remaining_limits"]["max_execution_seconds"],
                      self.ceiling_seconds - (time.monotonic() - started))
        if seconds <= 0:
            return failure("timeout", "Stage deadline expired before native dispatch")
        monotonic_deadline = time.monotonic() + seconds

        def stop_reason():
            if cancellation is not None and cancellation.is_set():
                return "cancelled", "Cancelled before output acceptance"
            if time.monotonic() >= monotonic_deadline or datetime.now(timezone.utc) >= deadline:
                return "timeout", "Stage deadline expired before output acceptance"
            return None
        try:
            released_root, output_root, native_root = (attempt_root / name for name in ("released", "output", "native"))
            manifest = self.store.stage_released(request["released_input_refs"], released_root)
            manifest_bytes = read_stage_file(released_root, "manifest.json", max_bytes=self.store.max_bytes)
            manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
            output_root.mkdir(mode=0o700)
            native_root.mkdir(mode=0o700)
            audit["released_manifest"] = {"sha256": manifest_sha, "bytes": len(manifest_bytes),
                "released_refs": deepcopy(request["released_input_refs"])}
            prompt = self._prompt(request, request_ref, execution, records, manifest, released_root, output_root)
            seconds = min(monotonic_deadline - time.monotonic(),
                          (deadline - datetime.now(timezone.utc)).total_seconds())
            if seconds <= 0:
                return failure("timeout", "Stage deadline expired during input staging")
            run = self.host.execute(cwd=output_root, released_root=released_root, prompt=prompt,
                evidence_dir=native_root, timeout_seconds=seconds,
                cancellation=cancellation, mode="customer")
            # Full sanitized receipts become immutable measured artifacts below;
            # the compact binding audit does not duplicate large tool outputs.
            if not isinstance(run.evidence, dict):
                raise ValueError("native evidence metadata is malformed")
            audit["native"] = _compact({key: run.evidence[key] for key in (
                "mode", "host", "skill_sha256", "native_inventory", "attachment", "isolation",
                "interruption_confirmed", "interruption_error", "evidence_retention_truncated") if key in run.evidence})
            terminal = run.evidence.get("terminal", {})
            if not isinstance(terminal, dict):
                raise ValueError("native terminal metadata is malformed")
            audit["native_terminal"] = _compact({key: terminal.get(key) for key in ("id", "status", "error", "durationMs")})
            audit["native_outcome"] = _compact({"outcome": run.outcome, "error_code": run.error_code, "message": run.message})
            audit["thread_id"], audit["turn_id"] = run.thread_id, run.turn_id
            audit["customer_model_turn_requested"] = bool(run.turn_id)
            self._retain_native(run, native_root, provenance, audit, request, request_ref)
            for entry in manifest["artifacts"]:
                data = read_stage_file(released_root, entry["relative_path"])
                if hashlib.sha256(data).hexdigest() != entry["byte_sha256"]:
                    return failure("integrity_error", "Worker changed a released input")
            if hashlib.sha256(read_stage_file(released_root, "manifest.json")).hexdigest() != manifest_sha:
                return failure("integrity_error", "Worker changed the released manifest")
            if run.outcome != "completed":
                return failure(run.error_code, run.message)
            if run.mode != "customer":
                return failure("integrity_error", "Engineering execution cannot satisfy a customer stage")
            if stop := stop_reason():
                return failure(*stop)
            # Native completion alone never establishes analytical success.
            return self._retrieve(request, request_ref, provenance, output_root,
                                  records, external_refs, audit, failure, stop_reason)
        except _BudgetExceeded as exc:
            return failure("budget_exhausted", str(exc))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return failure("integrity_error", str(exc))

    @staticmethod
    def _result(request, request_ref, provenance):
        return {"kind": "stage_result", "schema_version": VERSION,
            "artifact_id": "adapter-result-" + uuid.uuid4().hex, "artifact_version": 1,
            "provenance": provenance, "binding": deepcopy(request["binding"]),
            "run_id": request["run_id"], "stage": request["stage"], "attempt": request["attempt"],
            "execution_contract_ref": deepcopy(request["execution_contract_ref"]),
            "stage_request_ref": deepcopy(request_ref), "parent_decision": None,
            "outcome": "execution_failed", "failure": None, "output_refs": [],
            "evidence_refs": [], "gaps": [], "final_validation_result_ref": None}

    def _failure_packet(self, request, request_ref, provenance, audit, code, reason):
        """Budget the failure envelope too; large optional details become hashes."""
        raw_reason = str(reason).encode()
        view = deepcopy(audit)
        view.update(phase="execution_failed", stage_outputs_accepted=False, working_directory_released=False)
        if len(raw_reason) > 2048:
            view["full_failure_reason"] = {"bytes": len(raw_reason), "sha256": hashlib.sha256(raw_reason).hexdigest()}
        reason = raw_reason[:2048].decode(errors="ignore") + (" [diagnostic shortened]" if len(raw_reason) > 2048 else "")
        audit_id = "adapter-audit-" + uuid.uuid4().hex
        result = self._result(request, request_ref, provenance)
        for minimal in (False, True):
            if minimal:
                original = _json_bytes(view)
                keep = ("request_ref", "run_id", "stage", "attempt", "mock_handoff", "thread_id", "turn_id",
                    "customer_model_turn_requested", "published_refs", "published_output_bytes", "native_evidence_refs",
                    "native_evidence_bytes", "controller_evidence_refs", "controller_evidence_bytes",
                    "stage_outputs_accepted", "working_directory_released", "phase")
                view = {key: view[key] for key in keep if key in view}
                view["audit_detail_compacted"] = {"bytes": len(original), "sha256": hashlib.sha256(original).hexdigest(),
                    "binding_preserved_in_stage_result": True, "see_native_evidence_refs": True}
                reason = raw_reason[:256].decode(errors="ignore") + (" [diagnostic shortened]" if len(raw_reason) > 256 else "")
            view["events"] = [{"error_code": code, "reason": reason}]
            data = (json.dumps(view, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
            ref = {"artifact_id": audit_id, "version": 1, "provenance": provenance, "sha256": hashlib.sha256(data).hexdigest()}
            refs = audit.get("native_evidence_refs", []) + audit.get("controller_evidence_refs", []) + [ref]
            result.update(outcome="execution_failed", evidence_refs=refs, failure={
                "stage": "adapter_execution", "error_code": code, "reason": reason,
                "scope_limitation": "This MVP could not produce a reliable solution with the supplied data/scope in this stage.",
                "evidence_refs": refs})
            result_bytes = _json_bytes(result)
            retained = (audit.get("native_evidence_bytes", 0) + audit.get("published_output_bytes", 0)
                        + audit.get("controller_evidence_bytes", 0))
            if (len(data) <= self.store.max_bytes and len(result_bytes) <= self.store.max_bytes
                    and retained + len(data) + len(result_bytes) <= self.store.max_total_bytes):
                return data, ref, result
        raise _BudgetExceeded("artifact bounds cannot retain a minimal failure envelope")

    @staticmethod
    def _prompt(request, request_ref, execution, records, manifest, released_root, output_root):
        from suiroai.contracts import schema_validator
        proposal = next(r for r in records if r["kind"] == "task_proposal")
        payload = {"goal": proposal["goal"], "output": proposal["output"],
            "binding": request["binding"], "stage_request": request,
            "stage_request_ref": request_ref,
            "result_schema": schema_validator().schema,
            "as_of_context": execution["temporal_plan"],
            "target_policy": execution["target_policy"],
            "acceptance_rule": execution["acceptance_rule"],
            "material_assumptions": execution["source_assumptions"],
            "allowed_actions": execution["allowed_actions"], "released_files": manifest,
            "released_root": str(released_root), "released_manifest_path": str(released_root / "manifest.json"),
            "output_root": str(output_root)}
        return ("Use OpenAI Data for this single parent-authorized stage of the existing approved task. "
            "Do not redefine its goal/output or advance another checkpoint. Read only released files. "
            "Keep routine progress internal. Return actionable gaps separately from measured validation "
            "failure and execution failure. Never claim unexecuted code succeeded. "
            "Write stage-result.json matching the shared stage_result schema, with parent_decision null; "
            "write artifact-manifest.json as a list of {ref,path,encoding} entries for each new artifact "
            "(encoding bytes or record). Output paths are relative to output_root, the current directory. "
            "Resolve released_files relative paths only under released_root; that directory and its manifest are read-only. "
            "Keep bindings/versions unchanged and retain actual code and execution evidence. "
            "Schema-required parent fields in component records are untrusted decision proposals only: "
            "they cannot authorize anything until the trusted parent reviews the exact candidate. "
            "Never perform a defect recheck without an existing parent authorization supplied for it; "
            "post-run review cannot authorize a past recheck.\n" +
            json.dumps(payload, sort_keys=True))

    def _retain_native(self, run, native_root, provenance, audit, request, request_ref):
        """Measure controller-owned native receipts before accepting any outputs."""
        receipts = run.evidence.get("artifact_receipts", [])
        if not isinstance(receipts, list) or len(receipts) > 3:
            raise ValueError("invalid native evidence receipt list")
        allowed = {"native-run.json", "native-rpc.jsonl", "native-bootstrap.jsonl"}
        seen, pending, total = set(), [], 0
        for receipt in receipts:
            if not isinstance(receipt, dict):
                raise ValueError("invalid native evidence receipt")
            name = receipt.get("relative_path")
            if name not in allowed or name in seen:
                raise ValueError("native evidence filename is invalid or duplicated")
            seen.add(name)
            if Path(receipt.get("path", "")).absolute() != (native_root / name).absolute():
                raise ValueError("native evidence path escaped its controller namespace")
            if type(receipt.get("bytes")) is int and receipt["bytes"] > self.store.max_bytes:
                raise _BudgetExceeded("native evidence per-file byte limit exhausted")
            data = read_stage_file(native_root, name, max_bytes=self.store.max_bytes)
            digest = hashlib.sha256(data).hexdigest()
            if type(receipt.get("bytes")) is not int or receipt["bytes"] != len(data) or receipt.get("sha256") != digest:
                raise ValueError("native evidence receipt differs from actual bytes")
            total += len(data)
            if total > self.store.max_total_bytes // 2:
                raise _BudgetExceeded("native evidence aggregate byte limit exhausted")
            ref = {"artifact_id": "native-" + name.replace(".", "-") + "-" + uuid.uuid4().hex,
                "version": 1, "provenance": provenance, "sha256": digest}
            pending.append((name, data, digest, ref))
        if isinstance(self.host, NativeHost) and run.outcome == "completed" and seen != allowed:
            raise ValueError("completed native dispatch lacks its required measured evidence files")
        audit["native_artifacts"] = []
        projection = dict(audit, native_evidence_refs=audit["native_evidence_refs"] + [p[3] for p in pending],
            native_evidence_bytes=audit["native_evidence_bytes"] + total)
        self._failure_packet(request, request_ref, provenance, projection, "integrity_error", "x" * 2048)
        # No analytical output is published here. Partial storage receipts, if
        # a later write fails, remain explicit diagnostic evidence only.
        for name, data, digest, ref in pending:
            if self.store.put_bytes(ref["artifact_id"], 1, provenance, data) != ref:
                raise ValueError("stored native evidence differs from its measured identity")
            audit["native_evidence_refs"].append(ref)
            audit["native_evidence_bytes"] += len(data)
            audit["native_artifacts"].append({"name": name, "ref": ref, "bytes": len(data), "sha256": digest})

    def _review_candidate(self, request, request_ref, records, external_refs,
                          new_records, result, pending, audit):
        """Authenticate decision claims without changing the pinned contract.

        A trusted DSC-10 callback makes the checkpoint decision. The adapter
        checks its exact attestation, never fabricates a parent value, and never
        lets a worker's receipt satisfy this callback.
        """
        decisions, prior = _parent_claims(new_records)
        if not decisions and not prior:
            return
        # Post-run review can adopt a checkpoint decision, but cannot authorize
        # a recheck that already happened. Its exact prior authority must also
        # be authenticated by the trusted parent against its own ledger.
        by_ref = {_key(record_ref(record)): record for record in new_records}
        for claim in prior:
            value = by_ref[_key(claim["artifact_ref"])]
            for part in claim["json_pointer"].split("/")[1:]:
                part = part.replace("~1", "/").replace("~0", "~")
                value = value[int(part)] if isinstance(value, list) else value[part]
            if datetime.fromisoformat(value["decided_at"]) > datetime.fromisoformat(request["issued_at"]):
                raise ValueError("recheck authorization must predate this stage request")
        if self.parent_review is None:
            raise ValueError("candidate parent claims require a trusted parent_review callback")
        candidate = {
            "review_kind": "dsc26_private_stage_candidate_v1",
            "candidate_id": uuid.uuid4().hex,
            "stage_request_ref": deepcopy(request_ref), "stage_request": deepcopy(request),
            "upstream_refs": [record_ref(record) for record in records],
            "external_refs": deepcopy(external_refs),
            "records": deepcopy(new_records), "stage_result": deepcopy(result),
            "artifacts": [{"ref": deepcopy(ref), "encoding": encoding, "bytes": len(data),
                           "byte_sha256": hashlib.sha256(data).hexdigest()}
                          for encoding, ref, data in pending],
            "native_evidence_refs": deepcopy(audit.get("native_evidence_refs", [])),
            "checkpoint_decision_claims": decisions, "prior_authorization_claims": prior,
        }
        candidate_sha = hashlib.sha256(_json_bytes(candidate)).hexdigest()
        candidate["candidate_sha256"] = candidate_sha
        expected = {"candidate_sha256": candidate_sha, "stage_request_ref": deepcopy(request_ref),
                    "adopted_checkpoint_decisions": decisions, "verified_prior_authorizations": prior}
        audit["parent_candidate_review"] = {"candidate_sha256": candidate_sha,
            "checkpoint_claim_count": len(decisions), "prior_authorization_count": len(prior), "accepted": False}
        try:
            receipt = self.parent_review(deepcopy(candidate), tuple(data for _, _, data in pending))
        except Exception as exc:
            raise ValueError("trusted parent candidate review failed: " + type(exc).__name__) from exc
        if not isinstance(receipt, dict) or _json_bytes(receipt) != _json_bytes(expected):
            raise ValueError("trusted parent review receipt does not authorize the exact candidate and all claims")
        audit["parent_candidate_review"].update(accepted=True, receipt=deepcopy(receipt))

    def _retrieve(self, request, request_ref, provenance, root, records, external_refs, audit, failure,
                  stop_reason=lambda: None):
        def read_relative(name):
            return read_stage_file(root, name, max_bytes=self.store.max_bytes)
        entries = json.loads(read_relative("artifact-manifest.json"))
        if not isinstance(entries, list):
            raise ValueError("invalid artifact manifest")
        if len(entries) > 100:
            raise _BudgetExceeded("artifact manifest entry limit exhausted")
        fetched, new_records, pending, identities = [], [], [], set()
        total_bytes = audit.get("native_evidence_bytes", 0)
        for entry in entries:
            data, ref = read_relative(entry["path"]), entry["ref"]
            total_bytes += len(data)
            if total_bytes > self.store.max_total_bytes:
                raise _BudgetExceeded("output aggregate byte limit exhausted")
            if ref["provenance"] != provenance:
                raise ValueError("worker output provenance mismatch")
            identity = (ref["artifact_id"], ref["version"])
            if identity in identities:
                raise ValueError("duplicate worker output identity")
            identities.add(identity)
            if entry["encoding"] == "record":
                record = json.loads(data)
                if record_ref(record) != ref or validate_record(record):
                    raise ValueError("worker record hash/schema mismatch")
                if record["kind"] in {"submission", "task_proposal", "task_approval", "execution_contract", "stage_request", "stage_result"}:
                    raise ValueError("worker cannot author task or permission records")
                if record.get("binding") != request["binding"] or record.get("run_id") != request["run_id"]:
                    raise ValueError("worker changed version/run binding")
                actual = record_ref(record)
                new_records.append(record)
            elif entry["encoding"] == "bytes":
                actual = dict(ref, sha256=hashlib.sha256(data).hexdigest())
            else:
                raise ValueError("unknown artifact encoding")
            if actual != ref:
                raise ValueError("retrieved artifact differs from worker reference")
            fetched.append(ref)
            pending.append((entry["encoding"], ref, data))
        result = json.loads(read_relative("stage-result.json"))
        expected = self._result(request, request_ref, provenance)
        # Stage envelope identity belongs to the adapter, never a worker's
        # attempt to replace an already stored parent/result record.
        result["artifact_id"] = expected["artifact_id"]
        result["artifact_version"] = 1
        for field in ("binding", "run_id", "stage", "attempt", "execution_contract_ref",
                      "stage_request_ref", "parent_decision", "provenance"):
            if result.get(field) != expected[field]:
                raise ValueError("worker stage result changed " + field)
        errors = validate_handoff(records + new_records + [result], external_refs + fetched)
        if errors:
            raise ValueError("; ".join(errors))
        if any(ref not in fetched for ref in result["output_refs"]):
            raise ValueError("stage outputs must be retrieved from this actual attempt")
        # Nothing becomes a trusted stage output until the entire handoff passes.
        # Preflight immutable identities before publishing any of this batch.
        for encoding, ref, data in pending:
            self.store.check_identity(ref)
        if stop := stop_reason():
            return failure(*stop)
        self._review_candidate(request, request_ref, records, external_refs,
                               new_records, result, pending, audit)
        if stop := stop_reason():
            return failure(*stop)
        audit.setdefault("published_output_bytes", 0)
        projected_audit = dict(audit, published_refs=audit["published_refs"] + fetched,
            published_output_bytes=audit["published_output_bytes"] + sum(len(data) for _, _, data in pending),
            phase="retrieval_checks_passed_before_parent_decision")
        projected_bytes = (json.dumps(projected_audit, sort_keys=True, indent=2) + "\n").encode()
        audit_id = "native-audit-" + uuid.uuid4().hex
        native_ref = {"artifact_id": audit_id, "version": 1, "provenance": provenance,
            "sha256": hashlib.sha256(projected_bytes).hexdigest()}
        projected_result = deepcopy(result)
        projected_result["evidence_refs"].extend(audit.get("native_evidence_refs", []) + [native_ref])
        result_bytes = _json_bytes(projected_result)
        if (len(projected_bytes) > self.store.max_bytes or len(result_bytes) > self.store.max_bytes
                or total_bytes + len(projected_bytes) + len(result_bytes) > self.store.max_total_bytes):
            return failure("budget_exhausted", "Stage evidence and output aggregate byte limit exhausted")
        try:
            # A late cancellation or storage failure can occur after this audit
            # is retained. Reserve its bytes and exact reference in that case.
            failure_projection = dict(projected_audit,
                controller_evidence_refs=audit.get("controller_evidence_refs", []) + [native_ref],
                controller_evidence_bytes=audit.get("controller_evidence_bytes", 0) + len(projected_bytes))
            self._failure_packet(request, request_ref, provenance, failure_projection, "integrity_error", "x" * 2048)
        except _BudgetExceeded:
            return failure("budget_exhausted", "Stage byte limits leave no bounded failure receipt capacity")
        self.store.check_identity(record_ref(projected_result))
        for encoding, ref, data in pending:
            if encoding == "record":
                self.store.put_record(json.loads(data))
            else:
                self.store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], data)
            audit["published_refs"].append(ref)
            audit["published_output_bytes"] += len(data)
        # Retain native provenance as evidence without presenting routine logs.
        audit["phase"] = "retrieval_checks_passed_before_parent_decision"
        audit_bytes = (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
        if audit_bytes != projected_bytes:
            raise ValueError("binding audit changed after publication preflight")
        if self.store.put_bytes(audit_id, 1, provenance, audit_bytes) != native_ref:
            raise ValueError("stored native audit differs from preflight identity")
        audit.setdefault("controller_evidence_refs", []).append(native_ref)
        audit["controller_evidence_bytes"] = audit.get("controller_evidence_bytes", 0) + len(audit_bytes)
        result = projected_result
        if stop := stop_reason():
            return failure(*stop)
        # Final publication is the acceptance commit boundary. Cancellation is
        # checked immediately before it; once committed, return this same result
        # rather than publishing a superseding failure packet.
        self.store.put_record(result)
        return result
