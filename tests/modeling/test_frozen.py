"""Explicit mock consumer evidence; no real December data is accessed.

Exercise immutable freeze bundles, reserved-target scoring, acceptance gates,
and bounded defect rechecks against explicitly mock evidence.

Requirement context for these component checks:
Support step9 scoring against the frozen model and predeclared acceptance
rule; defect rechecks preserve that choice and cannot become holdout tuning
or a retry with the second-best model.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from datetime import date
import json
import tempfile
import unittest

from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.modeling.core import Example, ModelingError, Window, canonical
from suiroai.modeling.frozen import (finalize_validation, freeze_bundle, record_defect_recheck,
                                    reserved_actuals_payload, score_frozen, verify_frozen, record_failed_defect_recheck, shared_defect_recheck)


class FrozenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.store = ArtifactStore(self.temp.name)
        self.execution = {"binding": {"task_id": "mock-task"}, "run_id": "mock-run"}
        self.ref = self.store.put_bytes("mock-source", 1, "mock", b"explicit mock fitted model, config, preprocessing")
        self.window = Window(("mock-task", "p1", "s1"), date(2025, 11, 30), 2)
        self.rule = {"rule_id": "mock-rule", "version": 1, "declared_at": "2026-01-01T00:00:00Z",
                     "metric_gates": [{"metric_id": "mae", "aggregation": "equal_series_mean", "population_id": "mock-final",
                                       "direction": "upper_bound", "threshold": 1, "unit": "product_unit"}],
                     "required_check_ids": ["frozen_coverage"], "all_gates_required": True,
                     "minimum_observation_count": 1}

    def freeze(self, forecast=None, **kwargs):
        return freeze_bundle(self.store, execution=self.execution, artifact_id="mock-freeze",
                             selected_candidate_id="mock-candidate", model_ref=self.ref, feature_set_ref=self.ref,
                             preprocessing_ref=self.ref, evaluation_plan_ref=self.ref, acceptance_rule=self.rule,
                             development_input_refs=[self.ref], forecast_input_refs=[self.ref],
                             forecast=forecast or [(self.window, 4)], frozen_at="2026-01-01T00:01:00Z",
                             provenance=kwargs.pop("provenance", "mock"), **kwargs)

    def evaluate(self, frozen, actuals, **kwargs):
        ref = self.store.put_bytes("mock-reserved", 1, "mock", canonical(reserved_actuals_payload(actuals)))
        return score_frozen(self.store, frozen["bundle_ref"], actuals,
                            holdout_accessed_at="2026-01-01T00:02:00Z", observed_through=date(2025, 12, 31),
                            population_id="mock-final", reserved_unseen_data_ref=ref, **kwargs)

    def decision(self, ref, decision):
        return {"checkpoint": "final_validation", "decision": decision, "actor": "mock-parent",
                "decided_at": "2026-01-01T00:03:00Z", "reason": "mock measured review",
                "evidence_refs": [ref]}

    def test_mock_lineage_cannot_be_promoted_by_default_or_requested_provenance(self):
        frozen = self.freeze(provenance="derived")
        self.assertEqual(frozen["bundle_ref"]["provenance"], "mock")
        self.assertEqual(frozen["frozen_result_ref"]["provenance"], "mock")
        self.assertEqual(frozen["frozen"]["november_30_forecast_ref"]["provenance"], "mock")
        result = self.evaluate(frozen, {self.window: Example(self.window, (), 4)})
        self.assertEqual(result["evidence_ref"]["provenance"], "mock")

    def test_unsupported_rules_fail_before_freeze_or_holdout_exposure(self):
        for changed in ({"metric_id": "wape"}, {"direction": "minimum_improvement_over_baseline"},
                        {"aggregation": "pooled"}, {"unit": "ratio"}):
            with self.subTest(changed=changed):
                before = set((self.store.root / "refs").iterdir())
                original = dict(self.rule["metric_gates"][0])
                self.rule["metric_gates"][0].update(changed)
                with self.assertRaises(ModelingError):
                    self.freeze()
                self.assertEqual(set((self.store.root / "refs").iterdir()), before)
                self.rule["metric_gates"][0] = original

    def test_saved_aggregate_scores_with_immutable_separate_forecast(self):
        frozen = self.freeze()
        self.assertNotEqual(frozen["bundle_ref"], frozen["frozen"]["november_30_forecast_ref"])
        result = self.evaluate(frozen, {self.window: Example(self.window, (), 4)})
        self.assertEqual(result["evidence"]["outcome"], "pass")
        self.assertEqual(result["evidence"]["scores"][0]["value"], 0)
        self.assertEqual(finalize_validation(self.store, result["evidence_ref"])["outcome"], "pass")
        # Caller mutation cannot change persisted winner or saved quantities.
        frozen["frozen"]["selected_candidate_id"] = "runner-up"
        _, _, forecast = verify_frozen(self.store, frozen["bundle_ref"])
        self.assertEqual(forecast["rows"][0]["predicted"], 4)
        self.assertFalse(forecast["recommendation_ready"])

    def test_missing_horizon_is_failed_coverage_not_zero_demand(self):
        frozen = self.freeze()
        result = self.evaluate(frozen, {})
        self.assertEqual(result["evidence"]["scores"], [])
        self.assertEqual(result["evidence"]["outcome"], "fail")
        self.assertEqual(result["evidence"]["coverage_fraction"], 0)
        self.assertEqual(finalize_validation(self.store, result["evidence_ref"])["outcome"], "parent_review_required")
        terminal = finalize_validation(self.store, result["evidence_ref"],
                                       parent_review=self.decision(result["evidence_ref"], "confirmed_failure"))
        self.assertEqual(terminal["outcome"], "execution_failed")

    def test_future_availability_is_not_scored(self):
        frozen = self.freeze()
        result = self.evaluate(frozen, {self.window: Example(self.window, (), 4, date(2026, 1, 1))})
        self.assertEqual(result["evidence"]["eligible_observation_count"], 0)

    def test_measured_underperformance_needs_parent_review(self):
        result = self.evaluate(self.freeze(), {self.window: Example(self.window, (), 20)})
        self.assertEqual(result["evidence"]["scores"][0]["value"], 16)
        self.assertEqual(result["evidence"]["outcome"], "fail")
        self.assertEqual(finalize_validation(self.store, result["evidence_ref"])["outcome"], "parent_review_required")

    def test_chronology_and_horizon_rejected(self):
        with self.assertRaises(ModelingError):
            self.freeze([(Window(self.window.key, date(2025, 12, 1), 2), 4)])
        self.rule["declared_at"] = "2026-01-01T00:02:00Z"
        with self.assertRaises(ModelingError):
            self.freeze()

    def test_late_holdout_access_and_source_binding_required(self):
        frozen = self.freeze()
        actuals = {self.window: Example(self.window, (), 4)}
        ref = self.store.put_bytes("mock-reserved", 1, "mock", canonical(reserved_actuals_payload(actuals)))
        with self.assertRaises(ModelingError):
            score_frozen(self.store, frozen["bundle_ref"], actuals, holdout_accessed_at="2026-01-01T00:00:00Z",
                         observed_through=date(2025, 12, 31), population_id="mock-final", reserved_unseen_data_ref=ref)
        with self.assertRaises(ModelingError):
            score_frozen(self.store, frozen["bundle_ref"], {}, holdout_accessed_at="2026-01-01T00:02:00Z",
                         observed_through=date(2025, 12, 31), population_id="mock-final", reserved_unseen_data_ref=ref)

    def test_exact_daily_trajectory_is_required_for_recommendation_readiness(self):
        rows = [{"key": {"source_namespace": "mock-task", "product_id": "p1", "store_id": "s1"},
                 "date": f"2025-12-0{day}", "quantity": 2, "quantity_unit": "product_unit",
                 "as_of_date": "2025-11-30", "latest_information_available_date": "2025-11-30"} for day in (1, 2)]
        frozen = self.freeze(daily_forecast=rows)
        self.assertTrue(verify_frozen(self.store, frozen["bundle_ref"])[2]["recommendation_ready"])

    def test_daily_trajectory_total_and_missing_date_rejected(self):
        row = {"key": {"source_namespace": "mock-task", "product_id": "p1", "store_id": "s1"},
               "date": "2025-12-01", "quantity": 4, "quantity_unit": "product_unit",
               "as_of_date": "2025-11-30", "latest_information_available_date": "2025-11-30"}
        with self.assertRaises(ModelingError):
            self.freeze(daily_forecast=[row])

    def test_artifact_tamper_detected(self):
        frozen = self.freeze()
        path = self.store.root / "objects" / frozen["frozen"]["model_ref"]["sha256"]
        path.chmod(0o600)
        path.write_bytes(b"changed model")
        with self.assertRaises(ArtifactError):
            verify_frozen(self.store, frozen["bundle_ref"])

    def test_recheck_cannot_change_winner_threshold_or_forecast(self):
        result = self.evaluate(self.freeze(), {self.window: Example(self.window, (), 20)})
        forged = dict(result["evidence"], acceptance_rule=dict(self.rule, minimum_observation_count=2))
        changed = self.store.put_bytes("mock-invalid-correction", 1, "mock", canonical(forged))
        with self.assertRaises(ModelingError):
            record_defect_recheck(self.store, result["evidence_ref"], changed, attempt=1, max_defect_rechecks=1,
                                  defect_description="mock calculation defect", defect_evidence_refs=[self.ref],
                                  correction_refs=[self.ref], parent_authorization=self.decision(result["evidence_ref"], "allow_defect_recheck"),
                                  artifact_id="mock-recheck", recheck_started_at="2026-01-01T00:04:00Z")

    def test_demonstrated_scoring_defect_can_pass_only_after_bound_parent_review(self):
        # Explicit mock defect: old scorer wrongly reported MAE=16 for equal values.
        corrected = self.evaluate(self.freeze(), {self.window: Example(self.window, (), 4)}, scored_at="2026-01-01T00:05:00Z")
        old = dict(corrected["evidence"], outcome="fail", requires_parent_review=True, scored_at="2026-01-01T00:02:00Z")
        old["scores"] = [dict(item, value=16) if item["metric_id"] == "mae" else item for item in old["scores"]]
        old_ref = self.store.put_bytes("mock-original-defective-scorer", 1, "mock", canonical(old))
        recheck = record_defect_recheck(self.store, old_ref, corrected["evidence_ref"], attempt=1, max_defect_rechecks=1,
                    defect_description="mock independently demonstrated subtraction defect", defect_evidence_refs=[self.ref],
                    correction_refs=[self.ref], parent_authorization=self.decision(old_ref, "allow_defect_recheck"),
                    artifact_id="mock-corrected-recheck", recheck_started_at="2026-01-01T00:04:00Z")
        review = self.decision(old_ref, "pass_after_recheck")
        review["decided_at"] = "2026-01-01T00:06:00Z"
        review["evidence_refs"].append(recheck)
        final = finalize_validation(self.store, old_ref, parent_review=review, defect_rechecks=[recheck], max_defect_rechecks=1)
        self.assertEqual(final["outcome"], "pass")
        with self.assertRaises(ModelingError):
            finalize_validation(self.store, old_ref, parent_review=review, defect_rechecks=[recheck, recheck], max_defect_rechecks=2)
        shared = shared_defect_recheck(self.store, recheck)
        self.assertEqual(shared["outcome"], "pass")
        self.assertNotIn("format", shared)
        self.assertEqual(shared["scores"], corrected["evidence"]["scores"])
        self.assertEqual(verify_frozen(self.store, corrected["evidence"]["bundle_ref"])[2]["rows"][0]["predicted"], 4)

    def test_failed_calculation_correction_is_execution_failure_not_model_failure(self):
        result = self.evaluate(self.freeze(), {self.window: Example(self.window, (), 20)})
        ref = record_failed_defect_recheck(self.store, result["evidence_ref"], attempt=1, max_defect_rechecks=1,
                defect_description="mock demonstrated scorer crash", defect_evidence_refs=[self.ref], correction_refs=[self.ref],
                failure_evidence_refs=[self.ref], error_code="runtime_error", artifact_id="mock-failed-recheck",
                parent_authorization=self.decision(result["evidence_ref"], "allow_defect_recheck"), recheck_started_at="2026-01-01T00:04:00Z")
        final = finalize_validation(self.store, result["evidence_ref"],
                parent_review=self.decision(result["evidence_ref"], "confirmed_failure"), defect_rechecks=[ref], max_defect_rechecks=1)
        self.assertEqual(final["outcome"], "execution_failed")
        self.assertEqual(json.loads(self.store.read_bytes(ref))["scores"], [])
        shared = shared_defect_recheck(self.store, ref)
        self.assertEqual(shared["outcome"], "execution_failure")
        self.assertEqual(shared["scores"], [])
        self.assertEqual(shared["checks"][0]["status"], "fail")


    def test_recheck_bound_is_finite(self):
        result = self.evaluate(self.freeze(), {self.window: Example(self.window, (), 20)})
        with self.assertRaises(ModelingError):
            record_defect_recheck(self.store, result["evidence_ref"], result["evidence_ref"], attempt=1, max_defect_rechecks=0,
                                  defect_description="mock", defect_evidence_refs=[self.ref], correction_refs=[self.ref],
                                  parent_authorization=self.decision(result["evidence_ref"], "allow_defect_recheck"), artifact_id="mock-recheck", recheck_started_at="2026-01-01T00:04:00Z")


if __name__ == "__main__":
    unittest.main()
