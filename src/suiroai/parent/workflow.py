"""Bounded, in-process parent controller; never an analytical runtime.

Callbacks belong to the trusted intake/verifier process, never worker JSON.
The shared DSC-24 records and DSC-26 adapter remain the only transport contracts.

Enforce the confirmed-task boundary and internal evidence checkpoints without
adding routine customer gates; missing facts, runtime failures, and measured
validation failures retain distinct bounded review and terminal paths.

Linear: https://linear.app/gr3enarr0w/issue/DSC-10
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
import threading
import uuid

from suiroai.contracts import VERSION, digest, record_ref, validate_handoff, validate_record
from suiroai.integration.adapter import StageAdapter


class GuardRejected(ValueError):
    """A permission/checkpoint was denied; this grants no customer response."""


STAGES = (
    "preparation", "initial_baseline_evaluation", "llm_features",
    "comparison_and_freeze", "final_validation", "recommendations", "output_verification",
)
KINDS = {
    "preparation": {"preparation_result"},
    "initial_baseline_evaluation": {"initial_evaluation_result"},
    "llm_features": {"feature_proposal", "feature_result"},
    "comparison_and_freeze": {"evaluation_result"},
    "final_validation": {"final_validation_result"},
    "recommendations": {"quantity_result", "report_draft", "evidence_record"},
    "output_verification": {"output_verification", "report_draft", "evidence_record"},
}
REQUIRED = {
    "preparation": {"preparation_result"},
    "initial_baseline_evaluation": {"initial_evaluation_result"},
    "llm_features": {"feature_proposal", "feature_result"},
    "comparison_and_freeze": {"evaluation_result"},
    "final_validation": {"final_validation_result"},
    "recommendations": {"quantity_result", "report_draft"},
    "output_verification": {"output_verification"},
}
DOMAINS = {"source", "split", "model", "metric", "runtime"}
REQUIRED_ACTIONS = {
    "preparation": {"inspect", "clean", "join", "aggregate", "eda", "materialize_features"},
    "initial_baseline_evaluation": {"train", "evaluate"},
    "llm_features": {"materialize_features"},
    "comparison_and_freeze": {"train", "evaluate", "freeze"},
    "final_validation": {"evaluate"},
    "recommendations": {"calculate_restocking", "draft_report"},
    "output_verification": {"verify_outputs"},
}


def _now():
    return datetime.now(timezone.utc)


def _checks(value):
    if isinstance(value, dict):
        if {"check_id", "status", "actual", "evidence_refs"} <= value.keys():
            yield value
        else:
            for item in value.values():
                yield from _checks(item)
    elif isinstance(value, list):
        for item in value:
            yield from _checks(item)


class ParentWorkflow:
    """One task/approval/run, with one outstanding stage at a time.

    ``confirm_approval(approval, proposal)`` authenticates genuine DSC-25 consent.
    ``review_release(stage, refs, records)`` attests measured content eligibility.
    ``review_evidence(packet, artifact_bytes)`` independently reviews actual
    checkpoint/recovery/delivery evidence. All return literal True to allow.
    These trusted callbacks must be bounded and must not call parent mutations.
    Mock use is explicit and is still barred from NativeHost by DSC-26.
    """

    def __init__(self, store, *, confirm_approval, review_release, review_evidence,
                 allow_mocks=False, clock=_now):
        if not all(callable(c) for c in (confirm_approval, review_release, review_evidence, clock)):
            raise ValueError("trusted intake, release and evidence reviewers required")
        self.store = store
        self._confirm = confirm_approval
        self._release = review_release
        self._review = review_evidence
        self._allow_mocks = allow_mocks
        self._clock = clock
        self._lock = threading.RLock()
        self._state = "intake"
        self._records = []
        self._external = []
        self._submission = self._proposal = self._approval = self._execution = None
        self._active = None
        self._dispatched = False
        self._executing = False
        self._cancel = threading.Event()
        self._attempts = {}
        self._reviews = self._rechecks = 0
        self._started = None
        self._frozen = None
        self._prior_authorizations = []
        self._recheck_authorization_ref = None
        self._candidate_receipts = {}
        self._outcome = None
        self._delivery_blocker = None
        self._response = None
        self._events = []
        self._used_runs = set()
        self._failure_reserve = 0
        self._verification_check_ref = None

    @property
    def state(self):
        with self._lock:
            return self._state

    def checkpoint(self):
        """Inspectable private checkpoint; never accept worker-authored resume state."""
        with self._lock:
            return deepcopy({"state": self._state, "outcome": self._outcome,
                "delivery_blocker": self._delivery_blocker,
                "record_refs": [record_ref(r) for r in self._records],
                "active_request_ref": record_ref(self._active) if self._active else None,
                "attempts": self._attempts, "reviews": self._reviews,
                "defect_rechecks": self._rechecks, "frozen": self._frozen,
                "events": self._events})

    def _event(self, action, **details):
        event = {"action": action, "at": self._clock().isoformat(), **deepcopy(details)}
        context = self._execution or self._proposal or self._submission
        if context:
            data = json.dumps({"event": event, "state": self._state,
                "context_ref": record_ref(context), "outcome": self._outcome,
                "attempts": self._attempts, "reviews": self._reviews,
                "defect_rechecks": self._rechecks}, sort_keys=True, separators=(",", ":")).encode()
            event["audit_ref"] = self.store.put_bytes("parent-event-" + uuid.uuid4().hex,
                1, context["provenance"], data)
        self._events.append(event)

    def _record(self, record, kind):
        record = deepcopy(record)
        errors = validate_record(record)
        if record.get("kind") != kind or errors:
            raise GuardRejected("invalid " + kind + ": " + "; ".join(errors))
        if record["provenance"] == "mock" and not self._allow_mocks:
            raise GuardRejected("mock evidence cannot authorize this run")
        return record

    def _validate(self, records, external=None):
        refs = self._external if external is None else external
        errors = validate_handoff(records, refs)
        if errors:
            raise GuardRejected("; ".join(errors))

    def _measure(self, refs):
        for ref in refs:
            if ref["provenance"] == "mock" and not self._allow_mocks:
                raise GuardRejected("mock reference cannot be promoted")
            self.store.read_bytes(ref)

    def _save(self, records):
        for record in records:
            self.store.put_record(record)

    def receive_submission(self, submission, *, external_refs):
        with self._lock:
            if self._executing:
                self._cancel.set()
                raise GuardRejected("cancel and finish the active dispatch before replacing material input")
            submission = self._record(submission, "submission")
            if self._submission:
                old, new = self._submission["binding"], submission["binding"]
                if new["task_id"] != old["task_id"] or new["input_version"] <= old["input_version"]:
                    raise GuardRejected("replacement material input needs the same task and a newer input version")
            refs = deepcopy(list(external_refs))
            self._measure(refs)
            self._validate([submission], refs)
            self._save([submission])
            self._cancel.set()
            self._submission = submission
            self._proposal = self._approval = self._execution = self._active = None
            self._frozen, self._prior_authorizations, self._recheck_authorization_ref = None, [], None
            self._verification_check_ref = None
            self._records, self._external = [submission], refs
            self._response = self._outcome = None
            self._delivery_blocker = None
            self._state = "intake"
            self._event("material_input_received_approval_invalidated", submission_ref=record_ref(submission))

    def present_proposal(self, proposal):
        with self._lock:
            if self._executing or self._submission is None or self._state == "delivered":
                raise GuardRejected("no current intake submission")
            proposal = self._record(proposal, "task_proposal")
            if self._proposal and proposal["binding"]["proposal_version"] <= self._proposal["binding"]["proposal_version"]:
                raise GuardRejected("correction requires a newer proposal version")
            records = [self._submission, proposal]
            self._validate(records)
            self._save([proposal])
            self._cancel.set()
            self._proposal, self._approval, self._execution, self._active = proposal, None, None, None
            self._frozen, self._prior_authorizations, self._recheck_authorization_ref = None, [], None
            self._verification_check_ref = None
            self._records = records
            self._response = self._outcome = None
            self._delivery_blocker = None
            self._state = "awaiting_approval" if proposal["readiness"] == "ready" else proposal["readiness"]
            self._event("proposal_presented_approval_invalidated", proposal_ref=record_ref(proposal))

    def record_approval(self, approval):
        with self._lock:
            if self._state != "awaiting_approval" or self._proposal is None:
                raise GuardRejected("a current ready proposal is required")
            approval = self._record(approval, "task_approval")
            records = [self._submission, self._proposal, approval]
            self._validate(records)
            if approval["decision"] == "approved" and self._confirm(deepcopy(approval), deepcopy(self._proposal)) is not True:
                raise GuardRejected("intake did not authenticate customer sign-off")
            self._save([approval])
            self._records = records
            self._approval = approval if approval["decision"] == "approved" else None
            self._state = {"approved": "approved", "pending": "awaiting_approval", "rejected": "intake"}[approval["decision"]]
            self._event("customer_approval", approval_ref=record_ref(approval), decision=approval["decision"])

    def start(self, execution):
        with self._lock:
            if self._state != "approved" or self._approval is None:
                raise GuardRejected("no execution before valid current customer approval")
            execution = self._record(execution, "execution_contract")
            if not set().union(*REQUIRED_ACTIONS.values()) <= set(execution["allowed_actions"]):
                raise GuardRejected("execution lacks actions required for the approved retail workflow")
            if execution["run_id"] in self._used_runs:
                raise GuardRejected("a run identity cannot be reset or replayed")
            self._validate(self._records + [execution])
            self._save([execution])
            self._execution = execution
            self._records.append(execution)
            self._used_runs.add(execution["run_id"])
            self._state, self._started = "preparation", self._clock()
            self._attempts, self._reviews, self._rechecks = {}, 0, 0
            self._frozen, self._prior_authorizations = None, []
            self._candidate_receipts = {}
            self._recheck_authorization_ref = None
            self._verification_check_ref = None
            self._failure_reserve = max(1, min(30, execution["limits"]["max_execution_seconds"] // 5))
            self._cancel = threading.Event()
            self._event("approved_run_started", execution_contract_ref=record_ref(execution))

    def _one(self, kind, records=None):
        found = [r for r in (self._records if records is None else records) if r["kind"] == kind]
        if not found:
            raise GuardRejected("missing " + kind + " checkpoint")
        return max(found, key=lambda r: r["artifact_version"])

    def _frozen_release_refs(self):
        """Resolve only immutable metadata of the already adopted frozen choice.

        DSC-28 owns its bundle encoding. The parent only binds that consumer
        envelope to the exact comparison checkpoint; it does not score it.
        """
        evaluation = self._one("evaluation_result")
        if evaluation["frozen"] != self._frozen:
            raise GuardRejected("frozen comparison changed before unseen release")
        refs = [self._frozen["evaluation_plan_ref"], self._frozen["acceptance_rule_ref"]]
        expected = [evaluation["evaluation_plan"], self._execution["acceptance_rule"]]
        for ref, payload in zip(refs, expected):
            if ref["sha256"] != digest(payload) or json.loads(self.store.read_bytes(ref)) != payload:
                raise GuardRejected("frozen plan or acceptance bytes differ from the adopted contract")
        reviewed = list(evaluation["parent_decision"]["evidence_refs"])
        bundle_scope = set()
        for check in evaluation["comparison_checks"]:
            reviewed.extend(check["evidence_refs"])
            bundle_scope.update(digest(ref) for ref in check["evidence_refs"])
        bundle_keys = {"format", "frozen", "frozen_result_ref", "expected_observation_count",
            "minimum_coverage_fraction", "binding", "run_id", "execution_contract_sha256"}
        bundles = []
        for ref in {digest(ref): ref for ref in reviewed}.values():
            try:
                payload = json.loads(self.store.read_bytes(ref))
            except (ValueError, UnicodeError):
                continue
            if payload == self._frozen and ref["sha256"] == digest(self._frozen):
                refs.append(ref)
            if not isinstance(payload, dict) or payload.get("format") != "dsc28-frozen-v1":
                continue
            if digest(ref) not in bundle_scope:
                continue
            if (ref["sha256"] != digest(payload) or set(payload) != bundle_keys or payload["frozen"] != self._frozen
                    or payload["binding"] != self._execution["binding"]
                    or payload["run_id"] != self._execution["run_id"]
                    or payload["execution_contract_sha256"] != digest(self._execution)
                    or type(payload["expected_observation_count"]) is not int
                    or payload["expected_observation_count"] < 1
                    or type(payload["minimum_coverage_fraction"]) not in {int, float}
                    or not 0 < payload["minimum_coverage_fraction"] <= 1):
                raise GuardRejected("reviewed frozen bundle does not bind the adopted choice and run")
            frozen_ref = payload["frozen_result_ref"]
            if frozen_ref["sha256"] != digest(self._frozen) or json.loads(self.store.read_bytes(frozen_ref)) != self._frozen:
                raise GuardRejected("bundle frozen-result bytes differ from the adopted choice")
            bundles.append(ref)
            refs.extend([ref, frozen_ref])
        if len(bundles) > 1:
            raise GuardRejected("one reviewed frozen bundle per selected choice")
        return refs

    def _eligible(self, stage, refs):
        if not refs or len({digest(r) for r in refs}) != len(refs):
            raise GuardRejected("stage release needs a nonempty unique measured allowlist")
        if stage == "preparation":
            allowed = self._execution["source_refs"]
        elif stage in {"initial_baseline_evaluation", "llm_features", "comparison_and_freeze"}:
            prep = self._one("preparation_result")
            allowed = prep["development_context_allowlist"][:]
            for record in self._records:
                for meta in record.get("availability", []):
                    if (meta["permitted_use"] == "development" and not meta["contains_post_cutoff_rows"]
                            and meta["latest_event_date"] <= "2025-11-30"
                            and meta["latest_information_available_date"] <= "2025-11-30"):
                        allowed.append(meta["artifact_ref"])
        elif stage == "final_validation":
            if self._frozen is None:
                raise GuardRejected("unseen data requires a passed frozen checkpoint")
            prep = self._one("preparation_result")
            allowed = [prep["reserved_unseen_data_ref"], *self._frozen["development_input_refs"],
                *self._frozen["forecast_input_refs"], *self._frozen_release_refs(),
                self._frozen["model_ref"], self._frozen["feature_set_ref"],
                self._frozen["preprocessing_ref"], self._frozen["november_30_forecast_ref"]]
            if self._recheck_authorization_ref:
                allowed.append(self._recheck_authorization_ref)
            if prep["reserved_unseen_data_ref"] not in refs:
                raise GuardRejected("final evaluation requires the exact reserved artifact")
        else:
            allowed = [record_ref(r) for r in self._records]
            allowed += self._execution["synthetic_operational_source_refs"]
            if self._frozen:
                allowed += [self._frozen["november_30_forecast_ref"]]
        if any(r not in allowed for r in refs):
            raise GuardRejected("release outside stage-permitted inputs")
        self._measure(refs)
        if self._release(stage, deepcopy(refs), deepcopy(self._records)) is not True:
            raise GuardRejected("content/chronology release verification did not pass")

    def issue_stage(self, released_input_refs, *, seconds=60):
        with self._lock:
            if self._state not in STAGES or self._active or self._executing or self._cancel.is_set():
                raise GuardRejected("stage is not permitted or already outstanding")
            stage = self._state
            limits = deepcopy(self._execution["limits"])
            now = self._clock()
            remaining = math.floor(limits["max_execution_seconds"] - (now - self._started).total_seconds())
            if stage != "output_verification":
                remaining -= self._failure_reserve
            attempt = self._attempts.get(stage, 0) + 1
            if remaining <= 0 or attempt > limits["max_stage_attempts"]:
                self._terminal_execution("budget_exhausted", "Approved analytical time or stage attempts exhausted; no dispatch")
                raise GuardRejected("approved run limits exhausted")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
                raise GuardRejected("finite positive stage duration required")
            refs = deepcopy(list(released_input_refs))
            if stage == "final_validation" and self._recheck_authorization_ref and self._recheck_authorization_ref not in refs:
                refs.append(self._recheck_authorization_ref)
            self._eligible(stage, refs)
            limits["max_execution_seconds"] = remaining
            limits["max_stage_attempts"] -= attempt - 1
            limits["max_parent_reviews"] -= self._reviews
            limits["max_defect_rechecks"] -= self._rechecks
            authorization = self._decision(stage, "proceed", "Exact stage release after passed preceding checkpoint", [record_ref(self._approval)])
            request = {"kind": "stage_request", "schema_version": VERSION,
                "artifact_id": "parent-stage-" + uuid.uuid4().hex, "artifact_version": 1,
                "provenance": self._execution["provenance"], "binding": deepcopy(self._execution["binding"]),
                "run_id": self._execution["run_id"], "execution_contract_ref": record_ref(self._execution),
                "stage": stage, "attempt": attempt, "parent_authorization": authorization,
                "released_input_refs": refs, "remaining_limits": limits,
                "issued_at": now.isoformat(), "deadline": (now + timedelta(seconds=min(seconds, remaining))).isoformat(),
                "output_namespace": f"artifacts/{self._execution['binding']['task_id']}/{self._execution['run_id']}/{stage}/attempt-{attempt}"}
            self._validate(self._records + [request])
            ref = self.store.put_record(request)
            self._active, self._dispatched = request, False
            self._attempts[stage] = attempt
            self._event("stage_authorized", stage_request_ref=ref)
            return deepcopy(ref)

    def _decision(self, stage, decision, reason, refs):
        return {"checkpoint": stage, "decision": decision, "actor": "DSC-10-parent",
            "decided_at": self._clock().isoformat(), "reason": reason, "evidence_refs": deepcopy(refs)}

    def parent_permits(self, ref):
        with self._lock:
            if (not self._active or ref != record_ref(self._active) or self._dispatched
                    or self._cancel.is_set() or self._state != self._active["stage"]
                    or self._clock() >= datetime.fromisoformat(self._active["deadline"])):
                return False
            self._dispatched = True
            return True

    def _merged(self, new_records):
        kinds = {r["kind"] for r in new_records}
        return [r for r in self._records if r["kind"] not in kinds] + list(new_records)

    def _inspect(self, records, result, external):
        stage = self._active["stage"]
        if any(r["kind"] not in KINDS[stage] for r in records):
            raise GuardRejected("worker crossed an owned stage boundary")
        if result["outcome"] not in {"completed", "validation_failed"}:
            if records:
                raise GuardRejected("unsuccessful stage cannot publish checkpoint records")
            return
        if not REQUIRED[stage] <= {r["kind"] for r in records}:
            raise GuardRejected("completed stage lacks required typed checkpoint evidence")
        merged = self._merged(records)
        self._validate(merged + [self._active, result], external)
        if stage != "final_validation":
            if any(c["status"] != "pass" for r in records for c in _checks(r)):
                raise GuardRejected("failed or unavailable checkpoint check cannot advance")
        for record in records:
            decision = record.get("parent_decision")
            if record["kind"] == "report_draft" and record["outcome"] != "success":
                if self._outcome is None or not decision or decision["decision"] != "stop":
                    raise GuardRejected("failure report requires the concluded parent stop decision")
                if decision["checkpoint"] not in {"final_validation", "output_verification", "initial_baseline_evaluation", "preparation"}:
                    raise GuardRejected("failure report checkpoint is outside the failed task")
                continue
            if decision is not None and (decision["checkpoint"] != stage or decision["decision"] != "proceed"):
                raise GuardRejected("checkpoint requires parent proceed for this stage")
        if stage == "comparison_and_freeze" and self._frozen is not None:
            raise GuardRejected("frozen selection cannot be replaced")
        if stage == "final_validation":
            final = self._one("final_validation_result", records)
            if final["outcome"] == "pass" and any(check["status"] != "pass" for check in final["checks"]):
                raise GuardRejected("passed final validation cannot advance with failed or unavailable checks")
            if self._one("evaluation_result")["frozen"] != self._frozen:
                raise GuardRejected("frozen model/features/preprocessing/chronology changed")
            expected = "completed" if final["outcome"] == "pass" else "validation_failed"
            if result["outcome"] != expected:
                raise GuardRejected("final outcome and stage envelope disagree")
            rechecks = final["defect_rechecks"]
            if len(rechecks) != self._rechecks:
                raise GuardRejected("worker attempted an unauthorized or omitted recheck")
            previous = [r for r in self._records if r["kind"] == "final_validation_result"]
            if previous and rechecks[:-1] != previous[-1]["defect_rechecks"]:
                raise GuardRejected("recheck history changed")
            if self._rechecks and rechecks[-1]["parent_authorization"] != self._prior_authorizations[-1]:
                raise GuardRejected("recheck does not bind exact prior parent authorization")
            if not final["parent_review"] or final["parent_review"]["checkpoint"] != stage:
                raise GuardRejected("final checkpoint needs scoped parent review")
            allowed = {"proceed", "pass_after_recheck"} if final["outcome"] == "pass" else {"stop"}
            if final["parent_review"]["decision"] not in allowed:
                raise GuardRejected("failed holdout must stop for internal five-domain review")
        if stage == "output_verification":
            report = self._one("report_draft", merged)
            verification = self._one("output_verification", records)
            success = self._outcome is None
            if report["outcome"] != ("success" if success else "validation_failure" if self._outcome == "validation_failed" else "execution_failure"):
                raise GuardRejected("report does not match parent terminal outcome")
            if not success and (report["orders"] or report["quantity_result_ref"] is not None):
                raise GuardRejected("failure cannot contain recommendations")
            if verification["decision"] != "delivery_allowed":
                raise GuardRejected("independent verifier blocked delivery")
            if self._verification_check_ref and any(ref not in verification["parent_decision"]["evidence_refs"] for ref in [self._verification_check_ref, record_ref(report)]):
                raise GuardRejected("delivery proposal omitted registered independent checks or the exact report")
            if not success and verification["permitted_response"]["kind"] != "failure_explanation":
                raise GuardRejected("failure permits only verified failure explanation")

    def parent_review(self, candidate, artifact_bytes):
        """DSC-26 private candidate receipt: pure review, no checkpoint advancement."""
        with self._lock:
            candidate = deepcopy(candidate)
            candidate_sha = candidate.pop("candidate_sha256", None)
            if candidate_sha != digest(candidate) or not self._active or self._cancel.is_set():
                raise GuardRejected("invalid or revoked candidate")
            if self._clock() >= datetime.fromisoformat(self._active["deadline"]):
                raise GuardRejected("candidate arrived after its original stage deadline")
            if (candidate["stage_request_ref"] != record_ref(self._active)
                    or candidate["stage_request"] != self._active or not self._dispatched):
                raise GuardRejected("candidate does not bind active dispatched request")
            if len(artifact_bytes) != len(candidate["artifacts"]):
                raise GuardRejected("candidate bytes missing")
            import hashlib
            for meta, data in zip(candidate["artifacts"], artifact_bytes):
                if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["byte_sha256"]:
                    raise GuardRejected("candidate measured bytes changed")
            for claim in candidate["prior_authorization_claims"]:
                record = next(r for r in candidate["records"] if record_ref(r) == claim["artifact_ref"])
                value = record
                for part in claim["json_pointer"].split("/")[1:]:
                    part = part.replace("~1", "/").replace("~0", "~")
                    value = value[int(part)] if isinstance(value, list) else value[part]
                if value not in self._prior_authorizations or digest(value) != claim["decision_sha256"]:
                    raise GuardRejected("prior recheck authorization is not in trusted ledger")
            external = list(candidate["external_refs"]) + [a["ref"] for a in candidate["artifacts"]]
            self._inspect(candidate["records"], candidate["stage_result"], external)
            if self._review(deepcopy(candidate), tuple(artifact_bytes)) is not True:
                raise GuardRejected("independent evidence review did not pass")
            receipt = {"candidate_sha256": candidate_sha,
                "stage_request_ref": deepcopy(candidate["stage_request_ref"]),
                "adopted_checkpoint_decisions": deepcopy(candidate["checkpoint_decision_claims"]),
                "verified_prior_authorizations": deepcopy(candidate["prior_authorization_claims"])}
            self._candidate_receipts[self._result_signature(candidate["stage_result"])] = candidate_sha
            return receipt

    def register_verification_check(self, ref):
        """Retain DSC-30's authenticated check-only record as external evidence.

        This is not a delivery decision or a second current verification record.
        The eventual proposal must still pass the exact candidate/commit gate.
        """
        with self._lock:
            if self._state != "output_verification" or self._active or self._executing:
                raise GuardRejected("verification evidence registration is not currently permitted")
            if self._verification_check_ref:
                if ref == self._verification_check_ref:
                    self.store.read_record(ref)
                    return deepcopy(ref)
                raise GuardRejected("one independent verification check registration per report")
            record = self._record(self.store.read_record(ref), "output_verification")
            report = self._one("report_draft")
            if (record_ref(record) != ref or record["binding"] != self._execution["binding"]
                    or record["run_id"] != self._execution["run_id"]
                    or record["report_draft_ref"] != record_ref(report)
                    or record["decision"] != "blocked" or record["parent_decision"] is not None
                    or record["permitted_response"]["kind"] != "no_customer_response"
                    or record["permitted_response"]["text"]
                    or not record["claim_checks"]
                    or (report["outcome"] == "success" and not record["arithmetic_checks"])
                    or any(c["status"] != "pass" for c in _checks(record))):
                raise GuardRejected("check-only verification does not match the current report or passing evidence")
            self._measure([ref for check in _checks(record) for ref in check["evidence_refs"]])
            self._validate(self._records + [record], self._external + [ref])
            packet = {"review_kind": "verification_check_registration", "record": record,
                "report_ref": record_ref(report), "current_refs": [record_ref(r) for r in self._records]}
            if self._review(deepcopy(packet), (self.store.read_bytes(ref), self.store.read_bytes(record_ref(report)))) is not True:
                raise GuardRejected("independent verification registration review denied")
            if ref not in self._external:
                self._external.append(deepcopy(ref))
            self._verification_check_ref = deepcopy(ref)
            self._event("verification_check_registered", verification_check_ref=ref)
            return deepcopy(ref)

    @staticmethod
    def _result_signature(result):
        return digest({k: v for k, v in result.items() if k != "evidence_refs"})

    def execute(self, request_ref, *, work_root, host=None):
        with self._lock:
            if self._executing or not self._active or request_ref != record_ref(self._active):
                raise GuardRejected("only the outstanding exact request may execute")
            self._executing = True
            adapter = StageAdapter(self.store, work_root=work_root,
                parent_permits=self.parent_permits, parent_review=self.parent_review,
                host=host, allow_mock_handoffs=self._allow_mocks)
            handoff_records = [r for r in self._records if not (self._active["stage"] == "final_validation" and r["kind"] == "final_validation_result")]
            refs = [record_ref(r) for r in handoff_records] + [request_ref]
            external = deepcopy(self._external)
            external += [record_ref(r) for r in self._records if r not in handoff_records]
        try:
            result = adapter.execute(request_ref, handoff_refs=refs, external_refs=external, cancellation=self._cancel)
            with self._lock:
                self._commit(result)
            return deepcopy(result)
        except Exception as exc:
            with self._lock:
                self._terminal_execution("runtime_error", "Parent/adapter rejected dispatch or retrieval: " + type(exc).__name__)
            raise
        finally:
            with self._lock:
                self._executing = False

    def _commit(self, result):
        if self.store.read_record(record_ref(result)) != result:
            raise GuardRejected("result is not adapter-committed")
        for field in ("binding", "run_id", "stage", "attempt", "execution_contract_ref"):
            if result[field] != self._active[field]:
                raise GuardRejected("stale stage result " + field)
        if result["stage_request_ref"] != record_ref(self._active) or result["parent_decision"] is not None:
            raise GuardRejected("result cannot self-authorize")
        if result["outcome"] != "execution_failed" and self._clock() >= datetime.fromisoformat(self._active["deadline"]):
            self._terminal_execution("timeout", "Committed packet arrived after the original parent deadline")
            return
        # All output refs must remain measured even after candidate review.
        self._measure(result["output_refs"] + result["evidence_refs"])
        records = []
        for ref in result["output_refs"]:
            try:
                record = json.loads(self.store.read_bytes(ref))
            except (ValueError, UnicodeError):
                continue
            if isinstance(record, dict) and "kind" in record:
                if record_ref(record) != ref:
                    raise GuardRejected("output record identity changed")
                records.append(record)
        external = self._external + result["output_refs"] + result["evidence_refs"]
        self._inspect(records, result, external)
        if result["outcome"] in {"needs_inputs", "needs_material_facts"}:
            if not result["gaps"] or not any(g["material"] for g in result["gaps"]):
                raise GuardRejected("intake return requires an irreducible material gap")
            packet = {"review_kind": "material_gap", "stage_result": deepcopy(result),
                "current_refs": [record_ref(r) for r in self._records]}
            if self._review(packet, tuple(self.store.read_bytes(r) for r in result["evidence_refs"])) is not True:
                raise GuardRejected("parent did not confirm an irreducible consequential fact or material contract change")
        claims = any(r.get("parent_decision") is not None or r.get("parent_review") is not None for r in records)
        # Adapter appends measured audit refs after review; compare without those.
        if claims and self._result_signature(result) not in self._candidate_receipts:
            raise GuardRejected("checkpoint lacks trusted candidate review")
        stage = self._active["stage"]
        self._records = self._merged(records)
        self._external = list({digest(r): r for r in external}.values())
        self._event("adapter_result_committed", stage_result_ref=record_ref(result), outcome=result["outcome"])
        outcome = result["outcome"]
        if outcome in {"needs_inputs", "needs_material_facts"}:
            if not result["gaps"] or not any(g["material"] for g in result["gaps"]):
                raise GuardRejected("intake return requires an irreducible material gap")
            self._state, self._outcome = "intake", outcome
            self._approval = None
            self._cancel.set()
        elif outcome == "execution_failed":
            if stage == "output_verification":
                self._state = "delivery_blocked"
                self._delivery_blocker = result["failure"]["error_code"]
                self._outcome = self._outcome or self._delivery_blocker
            else:
                self._state = "failure_reporting"
                self._outcome = result["failure"]["error_code"]
            self._records.extend([self._active, result])
        elif outcome == "validation_failed":
            final = self._one("final_validation_result")
            if final["defect_rechecks"] and final["defect_rechecks"][-1]["outcome"] == "execution_failure":
                self._terminal_execution("runtime_error", "Bounded frozen validation recheck failed to execute")
            else:
                self._state, self._outcome = "final_review", "validation_failed"
        elif stage == "initial_baseline_evaluation" and self._one("initial_evaluation_result")["comparison"] != "better":
            self._state = "initial_review"
        elif stage == "comparison_and_freeze":
            self._frozen = deepcopy(self._one("evaluation_result")["frozen"])
            self._state = "final_validation"
        elif stage == "output_verification":
            self._response = deepcopy(self._one("output_verification")["permitted_response"])
            self._state = "delivery_ready"
        else:
            self._state = STAGES[STAGES.index(stage) + 1]
            if stage == "final_validation":
                self._outcome = None
        self._active = None
        self._candidate_receipts = {}

    def review_initial(self, evidence_refs, *, proceed):
        with self._lock:
            if self._state != "initial_review":
                raise GuardRejected("no worse/equal initial result awaiting review")
            refs = deepcopy(list(evidence_refs))
            self._bounded_review({"review_kind": "initial_baseline", "comparison": self._one("initial_evaluation_result")["comparison"],
                "evidence_refs": refs, "proceed": proceed}, refs)
            self._state = "llm_features" if proceed is True else "failure_reporting"
            if proceed is not True:
                self._terminal_execution("runtime_error", "Parent stopped after measured equal/worse initial baseline review")
            self._event("initial_comparison_review", proceed=proceed is True, evidence_refs=refs)

    def _bounded_review(self, packet, refs):
        if (self._clock() - self._started).total_seconds() >= self._execution["limits"]["max_execution_seconds"] - self._failure_reserve:
            if self._state == "final_review":
                self._state = "failure_reporting"
                self._event("validation_review_time_exhausted")
            else:
                self._terminal_execution("budget_exhausted", "Analytical deadline exhausted before internal review")
            raise GuardRejected("approved review time exhausted")
        if self._reviews >= self._execution["limits"]["max_parent_reviews"]:
            if self._state == "final_review":
                self._state = "failure_reporting"
                self._event("validation_review_count_exhausted")
            else:
                self._terminal_execution("budget_exhausted", "Bounded internal parent review allowance exhausted")
            raise GuardRejected("parent review limit exhausted")
        if not refs:
            raise GuardRejected("internal review requires measured evidence")
        self._measure(refs)
        self._reviews += 1
        try:
            accepted = self._review(deepcopy(packet), tuple(self.store.read_bytes(r) for r in refs)) is True
        except Exception:
            accepted = False
        accepted &= (self._clock() - self._started).total_seconds() < self._execution["limits"]["max_execution_seconds"] - self._failure_reserve
        if not accepted:
            if self._state == "final_review":
                self._state = "failure_reporting"
                self._event("validation_review_unresolved")
            else:
                self._terminal_execution("integrity_error", "Internal evidence review could not establish a passed checkpoint")
            raise GuardRejected("internal evidence review unresolved; terminal failure")

    def review_validation(self, evidence_by_domain, *, verdict, defect_kind=None):
        with self._lock:
            if self._state != "final_review":
                raise GuardRejected("no failed final validation awaiting review")
            if set(evidence_by_domain) != DOMAINS or any(not refs for refs in evidence_by_domain.values()):
                raise GuardRejected("source/split/model/metric/runtime evidence is required")
            if verdict not in {"demonstrated_defect", "confirmed_underperformance", "unresolved"}:
                raise GuardRejected("unknown internal review verdict")
            refs = [r for values in evidence_by_domain.values() for r in values]
            packet = {"review_kind": "frozen_validation_failure", "verdict": verdict,
                "defect_kind": defect_kind, "evidence_by_domain": deepcopy(evidence_by_domain),
                "failed_validation_ref": record_ref(self._one("final_validation_result")), "frozen": deepcopy(self._frozen)}
            self._bounded_review(packet, refs)
            limit = self._execution["limits"]["max_defect_rechecks"]
            attempts_left = self._attempts.get("final_validation", 0) < self._execution["limits"]["max_stage_attempts"]
            if (verdict == "demonstrated_defect" and defect_kind in {"scoring", "runtime"}
                    and self._rechecks < limit and attempts_left):
                self._rechecks += 1
                auth = self._decision("final_validation", "allow_defect_recheck",
                    "Demonstrated " + defect_kind + " defect; frozen selection, forecast, threshold and chronology preserved", refs)
                self._prior_authorizations.append(auth)
                data = json.dumps({"authorization": auth, "review": packet}, sort_keys=True, separators=(",", ":")).encode()
                self._recheck_authorization_ref = self.store.put_bytes("parent-recheck-" + uuid.uuid4().hex, 1, self._execution["provenance"], data)
                self._external.append(self._recheck_authorization_ref)
                self._external += [r for r in refs if r not in self._external]
                self._state = "final_validation"
                self._event("bounded_defect_recheck_authorized", authorization=auth, attempt=self._rechecks)
                return deepcopy(auth)
            self._state = "failure_reporting"
            self._event("validation_failure_terminal", verdict=verdict, recovery_exhausted=self._rechecks >= limit)
            return None

    def prepare_failure_delivery(self):
        """Permit failure drafting/verification only; never recommendations."""
        with self._lock:
            if self._state != "failure_reporting":
                raise GuardRejected("no terminal failure to explain")
            self._state = "output_verification"
            self._cancel = threading.Event()
            self._event("failure_verification_requested", outcome=self._outcome)

    def _terminal_execution(self, code, reason):
        """Controller-owned failure evidence, including honest non-dispatch stops.

        This is a failure envelope, never a claim that a native turn executed.
        The exact stopped request is retained for the shared verifier contract.
        """
        execution = self._execution
        verification_stopped = self._state == "output_verification"
        request = deepcopy(self._active)
        if request is None:
            now = self._clock()
            limits = deepcopy(execution["limits"])
            limits["max_execution_seconds"] = max(0, math.floor(limits["max_execution_seconds"] - (now - self._started).total_seconds()))
            request = {"kind": "stage_request", "schema_version": VERSION,
                "artifact_id": "parent-stop-request-" + uuid.uuid4().hex, "artifact_version": 1,
                "provenance": execution["provenance"], "binding": deepcopy(execution["binding"]),
                "run_id": execution["run_id"], "execution_contract_ref": record_ref(execution),
                "stage": "approved_execution", "attempt": 1,
                "parent_authorization": self._decision("approved_execution", "proceed", "Controller stop receipt only; never placed in dispatch ledger", [record_ref(self._approval)]),
                "released_input_refs": [], "remaining_limits": limits, "issued_at": now.isoformat(),
                "deadline": (now + timedelta(seconds=limits["max_execution_seconds"])).isoformat(),
                "output_namespace": f"artifacts/{execution['binding']['task_id']}/{execution['run_id']}/controller-stop"}
        self._save([request])
        data = json.dumps({"producer": "DSC-10-parent", "error_code": code, "reason": reason,
            "stage_request_ref": record_ref(request), "native_execution_claimed": False,
            "meaning": "Parent stopped permission or checkpoint; consult adapter receipts for actual native activity"},
            sort_keys=True, separators=(",", ":")).encode()
        evidence = self.store.put_bytes("parent-failure-evidence-" + uuid.uuid4().hex, 1, execution["provenance"], data)
        result = {"kind": "stage_result", "schema_version": VERSION,
            "artifact_id": "parent-stop-result-" + uuid.uuid4().hex, "artifact_version": 1,
            "provenance": execution["provenance"], "binding": deepcopy(execution["binding"]),
            "run_id": execution["run_id"], "execution_contract_ref": record_ref(execution),
            "stage_request_ref": record_ref(request), "stage": request["stage"], "attempt": request["attempt"],
            "outcome": "execution_failed", "output_refs": [], "evidence_refs": [evidence],
            "parent_decision": None, "failure": {"stage": "adapter_execution", "error_code": code,
                "reason": reason, "scope_limitation": "This MVP could not produce a reliable solution with the supplied data/scope in this run.",
                "evidence_refs": [evidence]}, "gaps": [], "final_validation_result_ref": None}
        self._record(result, "stage_result")
        self._save([result])
        known = {digest(record_ref(r)) for r in self._records}
        self._records.extend(r for r in [request, result] if digest(record_ref(r)) not in known)
        self._external.append(evidence)
        self._state = "delivery_blocked" if verification_stopped else "failure_reporting"
        if verification_stopped:
            self._delivery_blocker = code
            self._outcome = self._outcome or code
        else:
            self._outcome = code
        self._active = None
        self._response = None
        self._cancel.set()
        self._event("controller_terminal_failure", stage_result_ref=record_ref(result), error_code=code)

    def cancel(self):
        with self._lock:
            self._cancel.set()
            if not self._executing and self._state != "delivered":
                self._response = None
                if self._execution:
                    self._terminal_execution("cancelled", "Cancelled before dispatch or customer delivery")
                else:
                    self._active = None
                    self._state, self._outcome = "intake", "cancelled"
            self._event("cancellation_requested")

    def take_response(self):
        with self._lock:
            if self._state != "delivery_ready" or self._response is None:
                raise GuardRejected("no independently verified parent-authorized customer response")
            response = deepcopy(self._response)
            self._state = "delivered"
            self._event("customer_response_authorized", response_kind=response["kind"])
            return response
