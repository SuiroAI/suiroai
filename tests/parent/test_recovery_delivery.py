"""Complete MOCK recovery and verified failure responses; no real acceptance.

Exercise bounded defect recovery and verified terminal-failure explanations
while checking that exhausted or unavailable verification remains terminal.

Requirement context for these component checks:
Enforce the confirmed-task boundary and internal evidence checkpoints without
adding routine customer gates; missing facts, runtime failures, and measured
validation failures retain distinct bounded review and terminal paths.

Linear: https://linear.app/gr3enarr0w/issue/DSC-10
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest

import test_workflow as fixtures
from suiroai.contracts import record_ref
from suiroai.parent import GuardRejected, ParentWorkflow


class RecoveryDeliveryTests(unittest.TestCase):
    setUp = fixtures.WorkflowTests.setUp
    release = fixtures.WorkflowTests.release
    review = fixtures.WorkflowTests.review
    r = fixtures.WorkflowTests.r
    rehash = fixtures.WorkflowTests.rehash
    begin = fixtures.WorkflowTests.begin
    refs_for_stage = fixtures.WorkflowTests.refs_for_stage
    stage = fixtures.WorkflowTests.stage
    to_final = fixtures.WorkflowTests.to_final
    failed_final = fixtures.WorkflowTests.failed_final
    domains = fixtures.WorkflowTests.domains

    def failure_packet(self, *, code=None):
        fixture = json.loads((fixtures.ROOT / "examples/contracts/v0.1.0/validation_failed.json").read_text())
        report = deepcopy(next(r for r in fixture["records"] if r["kind"] == "report_draft"))
        old_final = report["final_validation_ref"]
        if code is None:
            final = self.parent._one("final_validation_result")
            report = fixtures.replace(report, old_final, record_ref(final))
        else:
            failed = self.parent._one("stage_result")
            failure_ref = record_ref(failed)
            report.update(outcome="execution_failure", final_validation_ref=None,
                frozen_result_ref=None, november_30_forecast_ref=None)
            report["failure"] = deepcopy(failed["failure"])
            report["customer_draft"] = "MOCK execution stopped: " + code + ". This MVP could not produce a reliable solution with the supplied data/scope in this run. No valid recommendation list was produced."
            report["claims"] = [{"claim_id": "mock-execution-stop", "statement": report["customer_draft"], "evidence_refs": [failure_ref]}]
            report["findings"] = []
            report["parent_decision"].update(checkpoint="output_verification", decision="stop", evidence_refs=[failure_ref])
        verification = deepcopy(next(r for r in fixture["records"] if r["kind"] == "output_verification"))
        verification["report_draft_ref"] = record_ref(report)
        verification["permitted_response"] = {"kind": "failure_explanation", "text": report["customer_draft"], "report_ref": record_ref(report)}
        return report, verification

    def assert_verified_failure(self, *, code=None):
        self.assertEqual(self.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()
        report, verification = self.failure_packet(code=code)
        self.parent.prepare_failure_delivery()
        ref = self.parent.issue_stage([record_ref(self.r("execution_contract"))])
        result = self.parent.execute(ref, work_root=self.root / "attempts", host=fixtures.MockPacketHost([report, verification]))
        self.assertEqual(result["outcome"], "completed", result.get("failure"))
        self.assertEqual(self.parent.state, "delivery_ready")
        response = self.parent.take_response()
        self.assertEqual(response["kind"], "failure_explanation")
        self.assertEqual(response["text"], report["customer_draft"])
        self.assertEqual(report["orders"], [])
        self.assertIsNone(report["quantity_result_ref"])
        self.assertNotIn("recommendations", self.parent.checkpoint()["attempts"])
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_confirmed_measured_failure_delivers_verified_explanation_only(self):
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        self.parent.review_validation(self.domains(), verdict="confirmed_underperformance")
        self.assert_verified_failure()

    def corrected(self, *, passed, runtime_failure=False):
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        frozen = self.parent.checkpoint()["frozen"]
        auth = self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="scoring")
        final = deepcopy(self.r("final_validation_result"))
        final["artifact_version"] += 1
        if passed:
            final["outcome"] = "pass"
            final["scores"][0]["value"] = 8
            final["checks"][1].update(status="pass", actual="MOCK corrected scorer MAE 8")
            final["parent_review"]["decision"] = "pass_after_recheck"
        final["defect_rechecks"] = [{"attempt": 1, "defect_description": "MOCK demonstrated scoring implementation defect only",
            "defect_evidence_refs": [self.external[0]], "correction_refs": [self.external[0]],
            "parent_authorization": auth, "model_selection_unchanged": True,
            "november_30_forecast_ref": deepcopy(frozen["november_30_forecast_ref"]),
            "scores": [] if runtime_failure else deepcopy(final["scores"]), "checks": deepcopy(final["checks"]),
            "outcome": "execution_failure" if runtime_failure else final["outcome"]}]
        result, host = self.stage(records=[final], outcome="completed" if passed else "validation_failed")
        self.assertEqual(result["outcome"], "completed" if passed else "validation_failed", result.get("failure"))
        self.assertEqual(self.parent.checkpoint()["frozen"], frozen)
        self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 1)
        # The genuine adapter staging boundary carried the parent-owned auth bytes.
        prompt = json.loads(host.calls[0]["prompt"].split("\n", 1)[1])
        released_ids = [entry["ref"]["artifact_id"] for entry in prompt["released_files"]["artifacts"]]
        self.assertTrue(any(name.startswith("parent-recheck-") for name in released_ids))
        return final

    def test_demonstrated_scoring_correction_can_pass_without_changing_freeze(self):
        self.corrected(passed=True)
        self.assertEqual(self.parent.state, "recommendations")
        with self.assertRaises(GuardRejected):
            self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="scoring")
        self.assertEqual(self.parent.checkpoint()["attempts"]["final_validation"], 2)

    def test_exhausted_recheck_delivers_verified_failure_without_recommendations(self):
        self.corrected(passed=False)
        self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="scoring")
        self.assert_verified_failure()

    def test_runtime_failure_during_recheck_uses_execution_explanation(self):
        self.corrected(passed=False, runtime_failure=True)
        self.assertEqual(self.parent.checkpoint()["outcome"], "runtime_error")
        self.assert_verified_failure(code="runtime_error")

    def test_predispatch_cancellation_has_typed_failure_and_verified_explanation(self):
        self.begin()
        self.parent.cancel()
        self.assertEqual(self.parent.checkpoint()["outcome"], "cancelled")
        self.assert_verified_failure(code="cancelled")

    def test_internal_initial_stop_has_typed_failure_and_verified_explanation(self):
        initial = self.r("initial_evaluation_result")
        initial["comparison"] = "worse"
        initial["initial_candidate"]["scores"][0]["value"] = 12
        self.begin()
        self.stage()
        self.stage()
        self.parent.review_initial([self.external[0]], proceed=False)
        self.assert_verified_failure(code="runtime_error")

    def test_analytical_exhaustion_preserves_only_reserved_verification_time(self):
        self.now = datetime.now(timezone.utc)
        self.parent = ParentWorkflow(self.store, confirm_approval=lambda *_: True,
            review_release=self.release, review_evidence=self.review, allow_mocks=True, clock=lambda: self.now)
        self.begin()
        self.now += timedelta(seconds=271)
        with self.assertRaisesRegex(GuardRejected, "limits exhausted"):
            self.parent.issue_stage(self.refs_for_stage())
        self.assert_verified_failure(code="budget_exhausted")
        self.assertEqual(self.parent.checkpoint()["attempts"].get("preparation", 0), 0)

    def test_cancel_revokes_report_pending_customer_delivery(self):
        self.begin()
        for _ in range(7):
            self.stage()
        self.assertEqual(self.parent.state, "delivery_ready")
        self.parent.cancel()
        self.assertEqual(self.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_exhausted_verification_budget_is_terminal_and_cannot_reopen(self):
        now = datetime.now(timezone.utc)
        self.parent = ParentWorkflow(self.store, confirm_approval=lambda *_: True,
            review_release=self.release, review_evidence=self.review, allow_mocks=True, clock=lambda: now)
        self.begin()
        self.parent.cancel()
        self.parent.prepare_failure_delivery()
        now += timedelta(seconds=301)
        with self.assertRaisesRegex(GuardRejected, "limits exhausted"):
            self.parent.issue_stage([record_ref(self.r("execution_contract"))])
        self.assertEqual(self.parent.state, "delivery_blocked")
        self.assertEqual(self.parent.checkpoint()["outcome"], "cancelled")
        self.assertEqual(self.parent.checkpoint()["delivery_blocker"], "budget_exhausted")
        events = len(self.parent.checkpoint()["events"])
        with self.assertRaises(GuardRejected):
            self.parent.prepare_failure_delivery()
        self.assertEqual(len(self.parent.checkpoint()["events"]), events)
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_review_cannot_authorize_recheck_after_reviewer_consumes_time(self):
        now = datetime.now(timezone.utc)
        self.parent = ParentWorkflow(self.store, confirm_approval=lambda *_: True,
            review_release=self.release, review_evidence=self.review, allow_mocks=True, clock=lambda: now)
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        def expires(packet, blobs):
            nonlocal now
            now += timedelta(seconds=301)
            return True
        self.parent._review = expires
        with self.assertRaisesRegex(GuardRejected, "review unresolved"):
            self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 0)

    def test_worker_cannot_force_hyperparameter_question_into_customer_intake(self):
        self.begin()
        self.review_allowed = False
        gap = {"gap_id": "mock-algorithm-question", "description": "MOCK pick a hyperparameter",
            "material": True, "blocks": ["execution"], "request_to_user": "MOCK choose model hyperparameters"}
        host = fixtures.MockPacketHost([], outcome="needs_material_facts", mutate=lambda r: r.update(gaps=[gap]))
        with self.assertRaisesRegex(GuardRejected, "irreducible consequential"):
            self.stage(host=host)
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertTrue(any(p.get("review_kind") == "material_gap" for p in self.reviews))
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_confirmed_material_fact_returns_to_intake_and_revokes_approval(self):
        self.begin()
        gap = {"gap_id": "mock-unit-meaning", "description": "MOCK irreducible product unit conversion affects quantities",
            "material": True, "blocks": ["execution"], "request_to_user": "MOCK confirm the physical pack conversion"}
        host = fixtures.MockPacketHost([], outcome="needs_material_facts", mutate=lambda r: r.update(gaps=[gap]))
        result, _ = self.stage(host=host)
        self.assertEqual(result["outcome"], "needs_material_facts", result.get("failure"))
        self.assertEqual(self.parent.state, "intake")
        self.assertTrue(any(p.get("review_kind") == "material_gap" for p in self.reviews))
        with self.assertRaises(GuardRejected):
            self.parent.start(self.r("execution_contract"))

    def test_check_only_verification_is_measured_external_evidence_not_delivery(self):
        self.begin()
        for _ in range(6):
            self.stage()
        prior = deepcopy(self.r("output_verification"))
        prior.update(artifact_id="mock-check-only-verification", decision="blocked", parent_decision=None,
            permitted_response={"kind": "no_customer_response", "text": "", "report_ref": None})
        prior_ref = self.store.put_record(prior)
        self.assertEqual(self.parent.register_verification_check(prior_ref), prior_ref)
        self.assertEqual(self.parent.state, "output_verification")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()
        final = deepcopy(self.r("output_verification"))
        final["parent_decision"]["evidence_refs"].extend([prior_ref, record_ref(self.r("report_draft"))])
        result, _ = self.stage(records=[final])
        self.assertEqual(result["outcome"], "completed", result.get("failure"))
        self.assertEqual(self.parent.take_response()["kind"], "final_report")

    def test_failed_additional_final_check_blocks_nominal_metric_pass(self):
        self.to_final()
        final = deepcopy(self.r("final_validation_result"))
        extra = deepcopy(final["checks"][0])
        extra.update(check_id="mock-safety-check", status="fail", actual="MOCK runtime safety check failed")
        final["checks"].append(extra)
        result, _ = self.stage(records=[final])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()

    def test_approved_actions_cannot_be_reduced_to_inspection(self):
        self.r("execution_contract")["allowed_actions"] = ["inspect"]
        with self.assertRaisesRegex(GuardRejected, "actions required"):
            self.begin()
        self.assertEqual(self.parent.state, "approved")
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([])

    def test_failed_verifier_cannot_release_success_report(self):
        self.begin()
        for _ in range(6):
            self.stage()
        verification = deepcopy(self.r("output_verification"))
        verification["binding_checks"][0]["status"] = "fail"
        verification.update(decision="blocked", parent_decision=None,
            permitted_response={"kind": "no_customer_response", "text": "", "report_ref": None})
        with self.assertRaisesRegex(GuardRejected, "checkpoint check"):
            self.stage(records=[verification])
        self.assertEqual(self.parent.state, "delivery_blocked")
        with self.assertRaises(GuardRejected):
            self.parent.take_response()
        with self.assertRaises(GuardRejected):
            self.parent.prepare_failure_delivery()


if __name__ == "__main__":
    unittest.main()
