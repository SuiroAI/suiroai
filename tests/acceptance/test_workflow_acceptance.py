"""DSC-56 fixed-case seam checks against DSC-24 0.1.0-draft.3.

MOCK customer, model, host and analytical outcomes. Real intake, parent,
preparation permission guard and StageAdapter code execute locally. These
checks are development evidence only: neither native Data execution nor the
DSC-31 restocking demonstration is established by a passing test.

Component examples are loaded by explicit path under unique module names;
their TestCases are never imported into this module or collected as this suite.
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from suiroai.contracts import record_ref
from suiroai.intake import IntakeError
from suiroai.integration.artifacts import ArtifactStore
from suiroai.parent import GuardRejected, ParentWorkflow
from suiroai.preparation.worker import PreparationError, prepare_development


ROOT = Path(__file__).resolve().parents[2]


def _example_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_workflow = _example_module("dsc56_mock_parent_examples", "tests/parent/test_workflow.py")
_intake = _example_module("dsc56_mock_intake_examples", "tests/intake/test_conversation.py")
_preparation = _example_module("dsc56_mock_preparation_examples", "tests/preparation/mock_data.py")


class WorkflowAcceptanceTests(unittest.TestCase):
    """Fixed requirement checks across component ownership boundaries."""

    def setUp(self):
        self.flow = _workflow.WorkflowTests(methodName="runTest")
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)

    def _new_flow(self):
        flow = _workflow.WorkflowTests(methodName="runTest")
        flow.setUp()
        self.addCleanup(flow.doCleanups)
        return flow

    def _intake_example(self):
        intake = _intake.ConversationTests(methodName="runTest")
        intake.setUp()
        self.addCleanup(intake.doCleanups)
        return intake

    def _receive_intake(self, intake, flow):
        receipt, _, presentation, _, _ = intake.presentation()
        # The receipt uses its own measured CSV, not the similarly named
        # immutable source marker in the independent parent example chain.
        flow.store = ArtifactStore(flow.root / "intake-store")
        flow.parent = ParentWorkflow(flow.store, confirm_approval=lambda *_: True,
            review_release=flow.release, review_evidence=flow.review, allow_mocks=True)
        refs = [flow.store.put_bytes(source.file_id, source.version,
                source.provenance, source.data) for source in receipt.sources]
        flow.parent.receive_submission(receipt.submission, external_refs=refs)
        flow.parent.present_proposal(presentation.proposal)
        return receipt, presentation

    def test_intake_parent_silence_and_forged_preparation_do_not_join(self):
        """Steps 1-3: real receipt/pending approval cannot grant a join permit."""
        flow, intake = self.flow, self._intake_example()
        original = intake.path.read_bytes()
        with patch("suiroai.preparation.worker.align_operations") as join, \
             patch("suiroai.integration.adapter.StageAdapter.execute") as dispatch:
            receipt, presentation = self._receive_intake(intake, flow)
            pending = intake.capture(receipt, presentation, None)
            flow.parent.record_approval(pending.approval)
            self.assertEqual(flow.parent.state, "awaiting_approval")
            self.assertFalse(receipt.inspections[0]["analytical_preparation_performed"])
            args, _ = _preparation.packet()
            # Worker-authored authorization JSON is insufficient: the real
            # parent has never issued this request or received consent.
            args["parent_permits"] = lambda request, execution: flow.parent.parent_permits(record_ref(request))
            with self.assertRaisesRegex(PreparationError, "trusted parent"):
                prepare_development(**args)
            with self.assertRaises(GuardRejected):
                flow.parent.start(flow.r("execution_contract"))
            with self.assertRaises(GuardRejected):
                flow.parent.issue_stage([])
        join.assert_not_called()
        dispatch.assert_not_called()
        self.assertEqual(intake.path.read_bytes(), original)
        self.assertEqual(flow.parent.checkpoint()["attempts"], {})

    def test_intake_parent_revised_proposal_rejects_previous_exact_consent(self):
        """DSC-25 consent survives the seam only for its original proposal."""
        flow, intake = self.flow, self._intake_example()
        receipt, first = self._receive_intake(intake, flow)
        consent = intake.capture(receipt, first, intake.response(first)).approval
        flow.parent.record_approval(consent)
        self.assertEqual(flow.parent.state, "approved")
        _, _, revised, _, _ = intake.presentation(receipt, version=2)
        flow.parent.present_proposal(revised.proposal)
        with self.assertRaises(IntakeError):
            intake.capture(receipt, revised, intake.response(first))
        with self.assertRaises(GuardRejected):
            flow.parent.record_approval(consent)
        self.assertEqual(flow.parent.state, "awaiting_approval")
        current = intake.capture(receipt, revised, intake.response(revised), approval_version=2)
        flow.parent.record_approval(current.approval)
        self.assertEqual(flow.parent.state, "approved")
        self.assertEqual(current.approval["proposal_ref"], record_ref(revised.proposal))
        self.assertNotEqual(current.approval["proposal_ref"], consent["proposal_ref"])
        self.assertEqual(flow.parent.checkpoint()["attempts"], {})

    def test_parent_adapter_observe_exact_step6_step7_step8_order(self):
        """Inspect actual dispatched requests, rather than a stage-name enum."""
        flow = self.flow
        flow.begin()
        observed = []
        while flow.parent.state != "final_validation":
            result, host = flow.stage()
            self.assertEqual(result["outcome"], "completed", result.get("failure"))
            payload = json.loads(host.calls[0]["prompt"].split("\n", 1)[1])
            request = payload["stage_request"]
            observed.append(request["stage"])
            self.assertEqual(request["binding"], flow.r("execution_contract")["binding"])
            self.assertEqual(result["stage_request_ref"], payload["stage_request_ref"])
            self.assertEqual(request["execution_contract_ref"], record_ref(flow.r("execution_contract")))
        self.assertEqual(observed, ["preparation", "initial_baseline_evaluation", "llm_features", "comparison_and_freeze"])
        self.assertEqual(flow.parent.checkpoint()["frozen"], flow.r("evaluation_result")["frozen"])
        with self.assertRaises(GuardRejected):
            flow.parent.take_response()

    def test_adapter_cannot_advance_with_skipped_or_combined_modeling_stages(self):
        """A host cannot turn step6 directly into feature/freeze acceptance."""
        for kinds in (("feature_proposal", "feature_result"), ("initial_evaluation_result", "evaluation_result")):
            with self.subTest(injected=kinds):
                flow = self._new_flow()
                flow.begin()
                flow.stage()
                records = [flow.r(kind) for kind in kinds]
                result, host = flow.stage(records=records)
                self.assertEqual(len(host.calls), 1)
                self.assertEqual(result["outcome"], "execution_failed")
                self.assertEqual(flow.parent.state, "failure_reporting")
                self.assertIsNone(flow.parent.checkpoint()["frozen"])
                self.assertNotIn("llm_features", flow.parent.checkpoint()["attempts"])
                self.assertNotIn("comparison_and_freeze", flow.parent.checkpoint()["attempts"])

    def test_parent_adapter_development_stages_release_only_allowlisted_bytes(self):
        """Each actual staged manifest excludes raw and reserved artifacts."""
        flow = self.flow
        flow.begin()
        flow.stage()
        prohibited = [*flow.r("execution_contract")["source_refs"], flow.r("preparation_result")["reserved_unseen_data_ref"]]
        permitted = flow.r("preparation_result")["development_context_allowlist"]
        for expected in ("initial_baseline_evaluation", "llm_features", "comparison_and_freeze"):
            self.assertEqual(flow.parent.state, expected)
            for ref in prohibited:
                with self.subTest(stage=expected, artifact=ref["artifact_id"]):
                    with self.assertRaises(GuardRejected):
                        flow.parent.issue_stage([*permitted, ref])
            result, host = flow.stage()
            self.assertEqual(result["outcome"], "completed", result.get("failure"))
            payload = json.loads(host.calls[0]["prompt"].split("\n", 1)[1])
            entries = payload["released_files"]["artifacts"]
            self.assertEqual([entry["ref"] for entry in entries], permitted)
            for entry in entries:
                staged = host.calls[0]["released_root"] / entry["relative_path"]
                self.assertEqual(staged.read_bytes(), flow.store.read_bytes(entry["ref"]))
            self.assertFalse(any(entry["ref"] in prohibited for entry in entries))
        self.assertEqual(flow.parent.state, "final_validation")

    def _authorize_correction(self, flow):
        flow.failed_final()
        flow.to_final()
        result, _ = flow.stage(outcome="validation_failed")
        self.assertEqual(result["outcome"], "validation_failed")
        self.assertEqual(flow.parent.state, "final_review")
        authorization = flow.parent.review_validation(flow.domains(), verdict="demonstrated_defect", defect_kind="scoring")
        final = deepcopy(flow.r("final_validation_result"))
        final["artifact_version"] += 1
        final["outcome"] = "pass"
        final["scores"][0]["value"] = 8
        final["checks"][1].update(status="pass", actual="MOCK corrected scorer MAE 8")
        final["parent_review"]["decision"] = "pass_after_recheck"
        final["defect_rechecks"] = [{"attempt": 1,
            "defect_description": "MOCK demonstrated scorer defect; no model changes",
            "defect_evidence_refs": [flow.external[0]], "correction_refs": [flow.external[0]],
            "parent_authorization": authorization, "model_selection_unchanged": True,
            "november_30_forecast_ref": deepcopy(final["november_30_forecast_ref"]),
            "scores": deepcopy(final["scores"]), "checks": deepcopy(final["checks"]), "outcome": "pass"}]
        return final

    def test_bounded_correction_preserves_freeze_rule_chronology_and_only_rechecks_final(self):
        flow = self.flow
        final = self._authorize_correction(flow)
        frozen = deepcopy(flow.parent.checkpoint()["frozen"])
        forecast_bytes = flow.store.read_bytes(frozen["november_30_forecast_ref"])
        prior_attempts = deepcopy(flow.parent.checkpoint()["attempts"])
        rule = deepcopy(flow.r("execution_contract")["acceptance_rule"])
        result, host = flow.stage(records=[final])
        self.assertEqual(result["outcome"], "completed", result.get("failure"))
        self.assertEqual(flow.parent.state, "recommendations")
        self.assertEqual(flow.parent.checkpoint()["frozen"], frozen)
        self.assertEqual(final["acceptance_rule"], rule)
        self.assertEqual(flow.store.read_bytes(frozen["november_30_forecast_ref"]), forecast_bytes)
        expected_attempts = dict(prior_attempts, final_validation=2)
        self.assertEqual(flow.parent.checkpoint()["attempts"], expected_attempts)
        payload = json.loads(host.calls[0]["prompt"].split("\n", 1)[1])
        auth_entries = [entry for entry in payload["released_files"]["artifacts"] if entry["ref"]["artifact_id"].startswith("parent-recheck-")]
        self.assertEqual(len(auth_entries), 1)
        authorization = json.loads(flow.store.read_bytes(auth_entries[0]["ref"]))
        self.assertEqual(authorization["authorization"], final["defect_rechecks"][0]["parent_authorization"])
        self.assertEqual(authorization["review"]["frozen"], frozen)
        with self.assertRaises(GuardRejected):
            flow.parent.review_validation(flow.domains(), verdict="demonstrated_defect", defect_kind="scoring")

    def test_correction_cannot_redeclare_threshold_forecast_or_holdout_chronology(self):
        def replace_frozen_dependency(final, flow, field):
            frozen = deepcopy(flow.parent.checkpoint()["frozen"])
            frozen[field] = deepcopy(flow.r("evaluation_result")["candidates"][0][field])
            data = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
            ref = flow.store.put_bytes("mock-forbidden-alternate-" + field, 1, "mock", data)
            flow.external.append(ref)
            final["frozen_result_ref"] = ref

        mutations = {
            "threshold": lambda final, flow: final["acceptance_rule"]["metric_gates"][0].update(threshold=20),
            "forecast": lambda final, flow: final.update(november_30_forecast_ref=flow.external[0]),
            "chronology": lambda final, flow: final.update(holdout_accessed_at="2026-10-17T09:01:00Z"),
            "model": lambda final, flow: replace_frozen_dependency(final, flow, "model_ref"),
            "features": lambda final, flow: replace_frozen_dependency(final, flow, "feature_set_ref"),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                flow = self._new_flow()
                final = self._authorize_correction(flow)
                frozen = deepcopy(flow.parent.checkpoint()["frozen"])
                mutate(final, flow)
                result, _ = flow.stage(records=[final])
                self.assertEqual(result["outcome"], "execution_failed")
                self.assertEqual(flow.parent.state, "failure_reporting")
                self.assertEqual(flow.parent.checkpoint()["frozen"], frozen)
                self.assertNotIn("recommendations", flow.parent.checkpoint()["attempts"])

    def test_unsuccessful_bounded_correction_stops_without_retraining_or_second_best(self):
        flow = self.flow
        final = self._authorize_correction(flow)
        frozen = deepcopy(flow.parent.checkpoint()["frozen"])
        final["outcome"] = "fail"
        final["scores"][0]["value"] = 12
        final["checks"][1].update(status="fail", actual="MOCK corrected scorer still exceeds MAE cap")
        final["parent_review"]["decision"] = "stop"
        final["defect_rechecks"][0].update(outcome="fail", scores=deepcopy(final["scores"]), checks=deepcopy(final["checks"]))
        result, _ = flow.stage(records=[final], outcome="validation_failed")
        self.assertEqual(result["outcome"], "validation_failed", result.get("failure"))
        self.assertEqual(flow.parent.state, "final_review")
        auth = flow.parent.review_validation(flow.domains(), verdict="demonstrated_defect", defect_kind="scoring")
        self.assertIsNone(auth)
        self.assertEqual(flow.parent.state, "failure_reporting")
        self.assertEqual(flow.parent.checkpoint()["defect_rechecks"], 1)
        self.assertEqual(flow.parent.checkpoint()["frozen"], frozen)
        for stage in ("initial_baseline_evaluation", "llm_features", "comparison_and_freeze"):
            self.assertEqual(flow.parent.checkpoint()["attempts"][stage], 1)
        with self.assertRaises(GuardRejected):
            flow.parent.issue_stage([frozen["model_ref"]])
        report = self._failure_delivery(flow)
        self.assertEqual(report["outcome"], "validation_failure")
        self.assertEqual(report["final_validation_ref"], record_ref(final))

    def _failure_delivery(self, flow, *, execution_code=None):
        fixture = json.loads((ROOT / "examples/contracts/v0.1.0/validation_failed.json").read_text())
        report = deepcopy(next(r for r in fixture["records"] if r["kind"] == "report_draft"))
        if execution_code is None:
            final = flow.parent._one("final_validation_result")
            report = _workflow.replace(report, report["final_validation_ref"], record_ref(final))
        else:
            failed = flow.parent._one("stage_result")
            report.update(outcome="execution_failure", final_validation_ref=None, frozen_result_ref=None, november_30_forecast_ref=None)
            report["failure"] = deepcopy(failed["failure"])
            report["customer_draft"] = "MOCK execution stopped: " + execution_code + ". This MVP could not produce a reliable solution with the supplied data/scope in this run. No valid recommendation list was produced."
            report["claims"] = [{"claim_id": "mock-execution-stop", "statement": report["customer_draft"], "evidence_refs": [record_ref(failed)]}]
            report["findings"] = []
            report["parent_decision"].update(checkpoint="output_verification", decision="stop", evidence_refs=[record_ref(failed)])
        verification = deepcopy(next(r for r in fixture["records"] if r["kind"] == "output_verification"))
        verification["report_draft_ref"] = record_ref(report)
        verification["permitted_response"] = {"kind": "failure_explanation", "text": report["customer_draft"], "report_ref": record_ref(report)}
        with self.assertRaises(GuardRejected):
            flow.parent.take_response()
        flow.parent.prepare_failure_delivery()
        ref = flow.parent.issue_stage([record_ref(flow.r("execution_contract"))])
        result = flow.parent.execute(ref, work_root=flow.root / "attempts", host=_workflow.MockPacketHost([report, verification]))
        self.assertEqual(result["outcome"], "completed", result.get("failure"))
        response = flow.parent.take_response()
        self.assertEqual(response["kind"], "failure_explanation")
        self.assertEqual(response["report_ref"], record_ref(report))
        self.assertEqual(response["text"], report["customer_draft"])
        self.assertEqual(report["orders"], [])
        self.assertIsNone(report["quantity_result_ref"])
        self.assertNotIn("recommendations", flow.parent.checkpoint()["attempts"])
        with self.assertRaises(GuardRejected):
            flow.parent.take_response()
        return report

    def test_measured_underperformance_and_unresolved_review_end_without_fallback(self):
        for verdict in ("confirmed_underperformance", "unresolved"):
            with self.subTest(verdict=verdict):
                flow = self._new_flow()
                flow.failed_final()
                flow.to_final()
                result, _ = flow.stage(outcome="validation_failed")
                self.assertEqual(result["outcome"], "validation_failed")
                self.assertEqual(flow.parent.state, "final_review")
                self.assertEqual(flow.parent.checkpoint()["outcome"], "validation_failed")
                with self.assertRaises(GuardRejected):
                    flow.parent.review_validation({"metric": [flow.external[0]]}, verdict=verdict)
                frozen = deepcopy(flow.parent.checkpoint()["frozen"])
                flow.parent.review_validation(flow.domains(), verdict=verdict)
                self.assertEqual(flow.parent.checkpoint()["frozen"], frozen)
                self.assertEqual(flow.parent.state, "failure_reporting")
                with self.assertRaises(GuardRejected):
                    flow.parent.issue_stage([frozen["model_ref"]])
                report = self._failure_delivery(flow)
                self.assertEqual(report["outcome"], "validation_failure")
                self.assertIsNotNone(report["final_validation_ref"])

    def test_adapter_execution_failure_never_becomes_a_measured_validation_failure(self):
        flow = self.flow
        flow.to_final()
        result, _ = flow.stage(host=_workflow.MockPacketHost(code="runtime_error"))
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertIsNone(result["final_validation_result_ref"])
        self.assertEqual(flow.parent.checkpoint()["outcome"], "runtime_error")
        self.assertEqual(flow.parent.state, "failure_reporting")
        with self.assertRaises(GuardRejected):
            flow.parent.review_validation(flow.domains(), verdict="confirmed_underperformance")
        report = self._failure_delivery(flow, execution_code="runtime_error")
        self.assertEqual(report["outcome"], "execution_failure")
        self.assertIsNone(report["final_validation_ref"])
        self.assertIn("supplied data/scope in this run", report["customer_draft"])


if __name__ == "__main__":
    unittest.main()
