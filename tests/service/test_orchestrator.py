"""A-PR2 (DSC-71): the read-only orchestration façade over committed analysis evidence.

Each shipped contract fixture represents a terminal (or pre-terminal) state of the governed run.
These tests assert the façade classifies each outcome correctly, exposes the right key records,
and enforces the delivery gate (R9): only a verified success is delivery-allowed, and failures
carry no order lines. Fixtures are mock interface examples; no analytical acceptance is implied.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from suiroai.service.orchestrator import (
    OUTCOME_EXECUTION_FAILURE,
    OUTCOME_MISSING_INPUTS,
    OUTCOME_RUNNING,
    OUTCOME_SUCCESS,
    OUTCOME_VALIDATION_FAILURE,
    OrchestratorError,
    load_analysis,
)

FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "contracts" / "v0.1.0"


def _load(name):
    return load_analysis(FIXTURES / f"{name}.json")


class OrchestratorOutcomeTests(unittest.TestCase):
    def test_successful_analysis_is_success_with_report_and_orders(self):
        view = _load("successful_analysis")
        self.assertEqual(view.outcome, OUTCOME_SUCCESS)
        self.assertTrue(view.is_mock)
        self.assertTrue(view.notice)
        self.assertIsNotNone(view.report_draft())
        self.assertEqual(view.report_draft()["outcome"], "success")
        self.assertIsNotNone(view.quantity_result())
        self.assertIsNotNone(view.evaluation_result())

    def test_successful_analysis_is_delivery_allowed(self):
        self.assertTrue(_load("successful_analysis").delivery_allowed)

    def test_missing_inputs_stops_pre_execution(self):
        view = _load("missing_inputs")
        self.assertEqual(view.outcome, OUTCOME_MISSING_INPUTS)
        self.assertIsNone(view.report_draft())
        self.assertIsNone(view.quantity_result())
        self.assertIsNone(view.evaluation_result())
        self.assertFalse(view.delivery_allowed)
        # The proposal/submission are still readable even without a handoff.
        self.assertIsNotNone(view.submission())
        self.assertIsNotNone(view.proposal())

    def test_validation_failure_has_no_orders_and_is_not_delivery_allowed(self):
        view = _load("validation_failed")
        self.assertEqual(view.outcome, OUTCOME_VALIDATION_FAILURE)
        self.assertEqual(view.report_draft()["outcome"], "validation_failure")
        self.assertIsNone(view.quantity_result())
        self.assertFalse(view.delivery_allowed)

    def test_execution_failure_has_no_orders_and_is_not_delivery_allowed(self):
        view = _load("execution_failed")
        self.assertEqual(view.outcome, OUTCOME_EXECUTION_FAILURE)
        self.assertEqual(view.report_draft()["outcome"], "execution_failure")
        self.assertIsNone(view.quantity_result())
        self.assertFalse(view.delivery_allowed)

    def test_approved_execution_is_running_without_report(self):
        view = _load("approved_execution")
        self.assertEqual(view.outcome, OUTCOME_RUNNING)
        self.assertIsNone(view.report_draft())
        self.assertFalse(view.delivery_allowed)

    def test_mock_cannot_back_real_analysis(self):
        with self.assertRaises(OrchestratorError):
            load_analysis(FIXTURES / "successful_analysis.json", allow_mock=False)

    def test_explicit_store_root_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            view = load_analysis(FIXTURES / "successful_analysis.json", store_root=root)
            self.assertEqual(view.outcome, OUTCOME_SUCCESS)
            self.assertTrue(root.exists())

    def test_handoff_present_for_executed_runs_only(self):
        self.assertIsNotNone(_load("successful_analysis").handoff)
        self.assertIsNone(_load("missing_inputs").handoff)


if __name__ == "__main__":
    unittest.main()
