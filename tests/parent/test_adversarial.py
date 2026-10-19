"""Adversarial MOCK permissions/checkpoint evidence; no analytical acceptance.

Attempt forged authority, stale bindings, and stage-permission bypasses
to verify that untrusted or inconsistent evidence cannot advance the workflow.

Requirement context for these component checks:
Enforce the confirmed-task boundary and internal evidence checkpoints without
adding routine customer gates; missing facts, runtime failures, and measured
validation failures retain distinct bounded review and terminal paths.

Linear: https://linear.app/gr3enarr0w/issue/DSC-10
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

import test_workflow as fixtures
from suiroai.integration.adapter import AdapterRejected
from suiroai.parent import GuardRejected, ParentWorkflow


class AdversarialGuards(unittest.TestCase):
    # Reuse invented packets and their measured store, without inheriting tests.
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

    def use_clock(self):
        self.now = datetime.now(timezone.utc)
        self.parent = ParentWorkflow(self.store, confirm_approval=lambda *_: self.confirmed,
            review_release=self.release, review_evidence=self.review, allow_mocks=True,
            clock=lambda: self.now)

    def assert_no_delivery(self):
        with self.assertRaises(GuardRejected):
            self.parent.take_response()
        self.assertFalse(any(e["action"] == "customer_response_authorized"
                             for e in self.parent.checkpoint()["events"]))

    def test_expired_request_cannot_invoke_host_or_advance(self):
        self.use_clock()
        self.begin()
        ref = self.parent.issue_stage(self.refs_for_stage(), seconds=2)
        self.now += timedelta(seconds=2)
        host = fixtures.MockPacketHost([self.r("preparation_result")])
        self.assertFalse(self.parent.parent_permits(ref))
        with self.assertRaises(AdapterRejected):
            self.parent.execute(ref, work_root=self.root / "attempts", host=host)
        self.assertEqual(host.calls, [])
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assert_no_delivery()

    def test_parent_deadline_is_rechecked_after_worker_returns(self):
        self.use_clock()
        self.begin()
        ref = self.parent.issue_stage(self.refs_for_stage(), seconds=2)
        def expire():
            self.now += timedelta(seconds=3)
        host = fixtures.MockPacketHost([self.r("preparation_result")], before_return=expire)
        result = self.parent.execute(ref, work_root=self.root / "attempts", host=host)
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assert_no_delivery()

    def test_total_time_exhaustion_cannot_authorize_another_stage(self):
        self.use_clock()
        self.begin()
        self.stage()
        self.now += timedelta(seconds=self.r("execution_contract")["limits"]["max_execution_seconds"])
        with self.assertRaisesRegex(GuardRejected, "limits exhausted"):
            self.parent.issue_stage(self.refs_for_stage())
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertEqual(self.parent.checkpoint()["outcome"], "budget_exhausted")
        self.assert_no_delivery()

    def test_time_exhaustion_does_not_authorize_defect_recovery(self):
        self.use_clock()
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        self.now += timedelta(seconds=self.r("execution_contract")["limits"]["max_execution_seconds"])
        try:
            authorization = self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime")
        except GuardRejected:
            authorization = None
        self.assertIsNone(authorization)
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 0)
        self.assert_no_delivery()

    def test_review_budget_is_shared_by_initial_and_final_reviews(self):
        self.r("execution_contract")["limits"]["max_parent_reviews"] = 1
        initial = self.r("initial_evaluation_result")
        initial["comparison"] = "equal"
        initial["initial_candidate"]["scores"][0]["value"] = initial["baseline_scores"][0]["value"]
        comparison = self.r("evaluation_result")
        comparison["candidates"] = [deepcopy(initial["initial_candidate"])
            if candidate["candidate_id"] == initial["initial_candidate"]["candidate_id"] else candidate
            for candidate in comparison["candidates"]]
        self.failed_final()
        self.begin()
        self.stage()
        self.stage()
        self.parent.review_initial([self.external[0]], proceed=True)
        self.stage()
        self.stage()
        self.stage(outcome="validation_failed")
        with self.assertRaisesRegex(GuardRejected, "review limit exhausted"):
            self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime")
        self.assertEqual(self.parent.checkpoint()["reviews"], 1)
        self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 0)
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assert_no_delivery()

    def test_stage_attempt_budget_prevents_even_demonstrated_defect_recheck(self):
        self.r("execution_contract")["limits"]["max_stage_attempts"] = 1
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        frozen = self.parent.checkpoint()["frozen"]
        self.assertIsNone(self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime"))
        self.assertEqual(self.parent.checkpoint()["attempts"]["final_validation"], 1)
        self.assertEqual(self.parent.checkpoint()["defect_rechecks"], 0)
        self.assertEqual(self.parent.checkpoint()["frozen"], frozen)
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assert_no_delivery()

    def test_failed_authorized_recheck_is_terminal_without_second_model(self):
        self.failed_final()
        self.to_final()
        self.stage(outcome="validation_failed")
        frozen = self.parent.checkpoint()["frozen"]
        authorization = self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime")
        corrected = deepcopy(self.r("final_validation_result"))
        corrected["artifact_version"] += 1
        corrected["defect_rechecks"] = [{
            "attempt": 1, "defect_description": "MOCK runtime output corruption corrected; measured score still fails",
            "defect_evidence_refs": [self.external[0]], "correction_refs": [self.external[0]],
            "parent_authorization": authorization, "model_selection_unchanged": True,
            "november_30_forecast_ref": deepcopy(frozen["november_30_forecast_ref"]),
            "scores": deepcopy(corrected["scores"]), "checks": deepcopy(corrected["checks"]), "outcome": "fail",
        }]
        result, _ = self.stage(records=[corrected], outcome="validation_failed")
        self.assertEqual(result["outcome"], "validation_failed", result.get("failure"))
        self.assertEqual(self.parent.state, "final_review")
        self.assertIsNone(self.parent.review_validation(self.domains(), verdict="demonstrated_defect", defect_kind="runtime"))
        checkpoint = self.parent.checkpoint()
        self.assertEqual(checkpoint["defect_rechecks"], 1)
        self.assertEqual(checkpoint["attempts"]["final_validation"], 2)
        self.assertEqual(checkpoint["frozen"], frozen)
        self.assertEqual(self.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([frozen["model_ref"]])
        self.assert_no_delivery()

    def test_comparison_outputs_cannot_be_injected_at_frozen_validation(self):
        self.to_final()
        frozen = self.parent.checkpoint()["frozen"]
        fallback = deepcopy(self.r("evaluation_result"))
        fallback["artifact_version"] += 1
        fallback["frozen"]["selected_candidate_id"] = "MOCK-second-ranked-model"
        result, _ = self.stage(records=[fallback, self.r("final_validation_result")])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assertEqual(self.parent.checkpoint()["frozen"], frozen)
        self.assert_no_delivery()

    def test_final_validation_cannot_loosen_predeclared_threshold(self):
        self.to_final()
        final = deepcopy(self.r("final_validation_result"))
        final["acceptance_rule"]["metric_gates"][0]["threshold"] = 1000
        result, _ = self.stage(records=[final])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.state, "failure_reporting")
        self.assert_no_delivery()

    def test_final_validation_cannot_replace_saved_forecast(self):
        self.to_final()
        frozen = self.parent.checkpoint()["frozen"]
        final = deepcopy(self.r("final_validation_result"))
        final["november_30_forecast_ref"] = self.external[0]
        result, _ = self.stage(records=[final])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(self.parent.checkpoint()["frozen"], frozen)
        self.assert_no_delivery()

    def test_forged_envelope_request_binding_and_attempt_never_advance(self):
        for field, value in [("run_id", "MOCK-forged-run"), ("attempt", 2)]:
            with self.subTest(field=field):
                self.setUp()
                self.begin()
                host = fixtures.MockPacketHost([self.r("preparation_result")], mutate=lambda result: result.update({field: value}))
                result, _ = self.stage(host=host)
                self.assertEqual(result["outcome"], "execution_failed")
                self.assertEqual(self.parent.state, "failure_reporting")
                self.assert_no_delivery()

    def test_old_stage_permission_cannot_execute_after_new_checkpoint(self):
        self.begin()
        ref = self.parent.issue_stage(self.refs_for_stage())
        self.parent.execute(ref, work_root=self.root / "attempts", host=fixtures.MockPacketHost([self.r("preparation_result")]))
        self.assertEqual(self.parent.state, "initial_baseline_evaluation")
        host = fixtures.MockPacketHost([self.r("preparation_result")])
        with self.assertRaises(GuardRejected):
            self.parent.execute(ref, work_root=self.root / "attempts", host=host)
        self.assertFalse(self.parent.parent_permits(ref))
        self.assertEqual(host.calls, [])
        self.assertEqual(self.parent.state, "initial_baseline_evaluation")


if __name__ == "__main__":
    unittest.main()
