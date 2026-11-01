"""MOCK transition/permission evidence only; no Data or retail analysis ran.

Uses the pinned DSC-24 draft.3 invented packets, the actual DSC-26 StageAdapter,
and a host writing mock packets. Genuine integration acceptance remains open.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from suiroai.contracts import digest, input_digest, proposal_digest, record_ref
from suiroai.integration.adapter import StageAdapter
from suiroai.integration.artifacts import ArtifactStore
from suiroai.parent import GuardRejected, ParentWorkflow

ROOT = Path(__file__).resolve().parents[2]


def replace(value, old, new):
    if value == old:
        return deepcopy(new)
    if isinstance(value, dict):
        return {k: replace(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace(v, old, new) for v in value]
    return value


class MockPacketHost:
    """No native invocation. Publish explicitly invented component outcomes."""
    def __init__(self, records=(), *, outcome="completed", code=None, mutate=None, before_return=None):
        self.records = deepcopy(list(records))
        self.outcome, self.code, self.mutate = outcome, code, mutate
        self.before_return = before_return
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.code:
            return SimpleNamespace(outcome="execution_failed", error_code=self.code,
                message="MOCK execution failure; no native invocation", evidence={}, thread_id=None, turn_id=None, mode="customer")
        payload = json.loads(kwargs["prompt"].split("\n", 1)[1])
        request, ref = payload["stage_request"], payload["stage_request_ref"]
        result = StageAdapter._result(request, ref, "mock")
        result.update(outcome=self.outcome, output_refs=[record_ref(r) for r in self.records], evidence_refs=[(self.records[0].get("execution_contract_ref", ref) if self.records else ref)])
        if self.outcome == "validation_failed":
            result["final_validation_result_ref"] = record_ref(next(r for r in self.records if r["kind"] == "final_validation_result"))
        if self.mutate:
            self.mutate(result)
        manifest = []
        for i, record in enumerate(self.records):
            name = f"mock-record-{i}.json"
            (kwargs["cwd"] / name).write_text(json.dumps(record))
            manifest.append({"ref": record_ref(record), "path": name, "encoding": "record"})
        (kwargs["cwd"] / "artifact-manifest.json").write_text(json.dumps(manifest))
        (kwargs["cwd"] / "stage-result.json").write_text(json.dumps(result))
        if self.before_return:
            self.before_return()
        return SimpleNamespace(outcome="completed", error_code=None, message="MOCK packets only",
            evidence={"evidence_mode": "mock"}, thread_id=None, turn_id=None, mode="customer")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="dsc10-mock-", dir="/private/tmp")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.fixture = json.loads((ROOT / "examples/contracts/v0.1.0/successful_analysis.json").read_text())
        self.assertEqual(self.fixture["fixture_provenance"], "mock")
        self.records = deepcopy(self.fixture["records"])
        self.original = [record_ref(r) for r in self.records]
        self.store = ArtifactStore(self.root / "store")
        self.external = []
        for artifact in self.fixture["mock_artifacts"]:
            data = json.dumps(artifact["content_marker"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
            self.external.append(self.store.put_bytes(artifact["ref"]["artifact_id"], artifact["ref"]["version"], "mock", data))
        self.reviews = []
        self.release_calls = []
        self.confirmed = True
        self.review_allowed = True
        self.parent = ParentWorkflow(self.store, confirm_approval=lambda *_: self.confirmed,
            review_release=self.release, review_evidence=self.review, allow_mocks=True)

    def release(self, stage, refs, records):
        self.release_calls.append((stage, refs))
        return True

    def review(self, packet, blobs):
        self.reviews.append(deepcopy(packet))
        return self.review_allowed

    def r(self, kind, version=None):
        found = [r for r in self.records if r["kind"] == kind and (version is None or r["artifact_version"] == version)]
        return found[-1]

    def rehash(self):
        for i, old in enumerate(self.original):
            new = record_ref(self.records[i])
            self.records = replace(self.records, old, new)
        self.original = [record_ref(r) for r in self.records]

    def begin(self):
        self.rehash()
        self.parent.receive_submission(self.r("submission"), external_refs=self.external)
        self.parent.present_proposal(self.r("task_proposal"))
        self.parent.record_approval(self.r("task_approval"))
        self.parent.start(self.r("execution_contract"))

    def refs_for_stage(self):
        stage = self.parent.state
        if stage == "preparation":
            return self.r("execution_contract")["source_refs"]
        if stage in {"initial_baseline_evaluation", "llm_features", "comparison_and_freeze"}:
            return self.r("preparation_result")["development_context_allowlist"]
        if stage == "final_validation":
            return [self.r("preparation_result")["reserved_unseen_data_ref"]]
        return [record_ref(self.r("evaluation_result"))]

    def stage(self, *, records=None, host=None, outcome="completed"):
        stage = self.parent.state
        kinds = {
            "preparation": ["preparation_result"], "initial_baseline_evaluation": ["initial_evaluation_result"],
            "llm_features": ["feature_proposal", "feature_result"], "comparison_and_freeze": ["evaluation_result"],
            "final_validation": ["final_validation_result"],
            "recommendations": ["quantity_result", "evidence_record", "report_draft"],
            "output_verification": ["output_verification"],
        }[stage]
        if records is None:
            records = [r for r in self.records if r["kind"] in kinds]
            if stage == "recommendations":
                records = [r for r in records if r["kind"] != "evidence_record" or "quantity" in r["requirement_id"]]
        host = host or MockPacketHost(records, outcome=outcome)
        ref = self.parent.issue_stage(self.refs_for_stage())
        result = self.parent.execute(ref, work_root=self.root / "attempts", host=host)
        return result, host

    def to_final(self):
        self.begin()
        for _ in range(4):
            result, _ = self.stage()
            self.assertEqual(result["outcome"], "completed", result.get("failure"))
        self.assertEqual(self.parent.state, "final_validation")

    def failed_final(self):
        final = self.r("final_validation_result")
        final["scores"][0]["value"] = 12
        final["outcome"] = "fail"
        final["parent_review"]["decision"] = "stop"
        # A failed threshold is measured failure, not a broken checkpoint protocol.
        final["checks"][1]["status"] = "fail"
        final["checks"][1]["actual"] = "MOCK MAE 12 exceeds 10"
        self.rehash()
        return final

    def domains(self):
        return {domain: [self.external[0]] for domain in ("source", "split", "model", "metric", "runtime")}

    def test_no_execution_before_explicit_current_approval_and_no_response_waits(self):
        with self.assertRaises(GuardRejected):
            self.parent.start(self.r("execution_contract"))
        self.parent.receive_submission(self.r("submission"), external_refs=self.external)
        self.parent.present_proposal(self.r("task_proposal"))
        pending = deepcopy(self.r("task_approval"))
        pending.update(decision="pending", actor=None, decided_at=None)
        self.parent.record_approval(pending)
        self.assertEqual(self.parent.state, "awaiting_approval")
        for _ in range(2):
            with self.assertRaises(GuardRejected):
                self.parent.start(self.r("execution_contract"))
            with self.assertRaises(GuardRejected):
                self.parent.issue_stage([])
        self.confirmed = False
        with self.assertRaisesRegex(GuardRejected, "authenticate"):
            self.parent.record_approval(self.r("task_approval"))

    def test_rejection_returns_step2_and_cannot_be_approved_without_reproposal(self):
        self.parent.receive_submission(self.r("submission"), external_refs=self.external)
        self.parent.present_proposal(self.r("task_proposal"))
        approval = deepcopy(self.r("task_approval"))
        approval["decision"] = "rejected"
        self.parent.record_approval(approval)
        self.assertEqual(self.parent.state, "intake")
        with self.assertRaises(GuardRejected):
            self.parent.record_approval(self.r("task_approval"))

    def test_correction_revokes_issued_permission_and_invalidates_approval(self):
        self.begin()
        request = self.parent.issue_stage(self.refs_for_stage())
        proposal = deepcopy(self.r("task_proposal"))
        proposal["artifact_version"] += 1
        proposal["goal"] += " MOCK corrected scope"
        proposal["binding"]["proposal_version"] += 1
        proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
        self.parent.present_proposal(proposal)
        self.assertFalse(self.parent.parent_permits(request))
        with self.assertRaises(GuardRejected):
            self.parent.record_approval(self.r("task_approval"))
        with self.assertRaises(GuardRejected):
            self.parent.start(self.r("execution_contract"))

    def test_new_material_input_invalidates_proposal_and_approval(self):
        self.begin()
        submission = deepcopy(self.r("submission"))
        submission["artifact_version"] += 1
        submission["binding"]["input_version"] += 1
        submission["original_request"] += " MOCK material new fact"
        submission["binding"]["input_digest"] = input_digest(submission)
        self.parent.receive_submission(submission, external_refs=self.external)
        self.assertEqual(self.parent.state, "intake")
        with self.assertRaises(GuardRejected):
            self.parent.start(self.r("execution_contract"))
        with self.assertRaises(GuardRejected):
            self.parent.present_proposal(self.r("task_proposal"))

    def test_missing_inputs_guidance_is_not_an_execution_error(self):
        missing = json.loads((ROOT / "examples/contracts/v0.1.0/missing_inputs.json").read_text())
        submission, proposal = [next(r for r in missing["records"] if r["kind"] == k) for k in ("submission", "task_proposal")]
        self.parent.receive_submission(submission, external_refs=[])
        self.parent.present_proposal(proposal)
        self.assertEqual(self.parent.state, "needs_inputs")
        self.assertTrue(proposal["gaps"][0]["request_to_user"])
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([])

    def test_exact_permission_is_single_use_and_not_a_json_flag(self):
        self.begin()
        ref = self.parent.issue_stage(self.refs_for_stage())
        altered = dict(ref, sha256="0" * 64)
        self.assertFalse(self.parent.parent_permits(altered))
        self.assertTrue(self.parent.parent_permits(ref))
        self.assertFalse(self.parent.parent_permits(ref))
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage(self.refs_for_stage())

    def test_failed_preparation_check_cannot_advance_or_publish(self):
        self.begin()
        target = deepcopy(self.r("preparation_result"))
        target["quality_checks"][0]["status"] = "fail"
        result, _ = self.stage(records=[target])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage(self.refs_for_stage())
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_worker_proceed_cannot_override_independent_parent_veto(self):
        self.begin()
        self.review_allowed = False
        result, _ = self.stage()
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertFalse(any(e["action"] == "customer_response_authorized" for e in self.parent.checkpoint()["events"]))

    def test_successful_sequential_flow_delivers_exact_verified_report_once(self):
        self.begin()
        while self.parent.state in {"preparation", "initial_baseline_evaluation", "llm_features", "comparison_and_freeze", "final_validation", "recommendations", "output_verification"}:
            result, _ = self.stage()
            self.assertEqual(result["outcome"], "completed", result.get("failure"))
            if self.parent.state != "delivery_ready":
                with self.assertRaises(GuardRejected):
                    self.parent.take_response()
        self.assertEqual(self.parent.state, "delivery_ready")
        response = self.parent.take_response()
        self.assertEqual(response, self.r("output_verification")["permitted_response"])
        self.assertEqual(response["kind"], "final_report")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_raw_future_and_holdout_inputs_are_denied_to_development(self):
        self.begin()
        self.stage()
        for ref in [self.r("execution_contract")["source_refs"][0], self.r("preparation_result")["reserved_unseen_data_ref"]]:
            with self.assertRaisesRegex(GuardRejected, "stage-permitted"):
                self.parent.issue_stage([ref])
        self.assertEqual(self.parent.state, "initial_baseline_evaluation")

    def test_initial_equal_and_worse_require_bounded_internal_review(self):
        for comparison, score in [("equal", 11), ("worse", 12)]:
            with self.subTest(comparison=comparison):
                self.setUp()
                initial = self.r("initial_evaluation_result")
                initial["comparison"] = comparison
                initial["initial_candidate"]["scores"][0]["value"] = score
                self.begin()
                self.stage()
                result, _ = self.stage()
                self.assertEqual(result["outcome"], "completed", result.get("failure"))
                self.assertEqual(self.parent.state, "initial_review")
                with self.assertRaises(GuardRejected):
                    self.parent.issue_stage(self.refs_for_stage() if self.parent.state in {"preparation"} else [])
                self.parent.review_initial([self.external[0]], proceed=True)
                self.assertEqual(self.parent.state, "llm_features")
                self.assertEqual(self.parent.checkpoint()["reviews"], 1)
                self.assertIsNone(self.parent.checkpoint()["frozen"])

    def test_measured_final_failure_requires_five_domain_review_and_no_fallback(self):
        self.failed_final()
        self.to_final()
        result, _ = self.stage(outcome="validation_failed")
        self.assertEqual(result["outcome"], "validation_failed", result.get("failure"))
        self.assertEqual(self.parent.state, "final_review")
        frozen = self.parent.checkpoint()["frozen"]
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([self.r("evaluation_result")["frozen"]["model_ref"]])
        with self.assertRaisesRegex(GuardRejected, "source/split/model/metric/runtime"):
            self.parent.review_validation({"metric": [self.external[0]]}, verdict="unresolved")
        self.parent.review_validation(self.domains(), verdict="confirmed_underperformance")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertEqual(self.parent.checkpoint()["frozen"], frozen)
        with self.assertRaises(GuardRejected):
            self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_no_recheck_for_unresolved_or_model_tuning(self):
        for verdict, kind in [("unresolved", None), ("demonstrated_defect", "model_tuning")]:
            with self.subTest(verdict=verdict):
                self.setUp()
                self.failed_final()
                self.to_final()
                self.stage(outcome="validation_failed")
                self.assertIsNone(self.parent.review_validation(self.domains(), verdict=verdict, defect_kind=kind))
                self.assertEqual(self.parent.state, "failure_reporting")
                self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 0)

    def test_expiry_exhaustion_and_cancellation_do_not_advance(self):
        self.begin()
        ref = self.parent.issue_stage(self.refs_for_stage())
        self.parent.cancel()
        self.assertFalse(self.parent.parent_permits(ref))
        self.assertEqual(self.parent.checkpoint()["outcome"], "cancelled")
        with self.assertRaises(GuardRejected):
            self.parent.execute(ref, work_root=self.root / "attempts", host=MockPacketHost())

    def test_late_cancellation_discards_mock_outputs(self):
        self.begin()
        host = MockPacketHost([self.r("preparation_result")], before_return=self.parent.cancel)
        result, _ = self.stage(host=host)
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(result["failure"]["error_code"], "cancelled")
        self.assertEqual(self.parent.state, "failure_reporting")

    def test_real_mode_rejects_mock_approval_chain(self):
        parent = ParentWorkflow(self.store, confirm_approval=lambda *_: True, review_release=lambda *_: True, review_evidence=lambda *_: True)
        with self.assertRaisesRegex(GuardRejected, "mock"):
            parent.receive_submission(self.r("submission"), external_refs=self.external)

    def test_checkpoint_is_a_copy_and_worker_cannot_resume_it(self):
        self.begin()
        snapshot = self.parent.checkpoint()
        snapshot["state"] = "delivery_ready"
        snapshot["record_refs"].clear()
        self.assertEqual(self.parent.state, "preparation")
        self.assertTrue(self.parent.checkpoint()["record_refs"])


if __name__ == "__main__":
    unittest.main()
