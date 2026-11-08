"""Measured synthetic calculations through DSC-24 record serialization.

All source facts, parent decisions and approvals here are explicit mock fixtures.
Passing these checks is component evidence, never real retail/native acceptance.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from suiroai.contracts import digest, validate_record
from suiroai.integration.artifacts import ArtifactStore
from suiroai.modeling.core import CUTOFF, Example, ModelingError, Window, canonical, checked_definition
from suiroai.modeling.evaluation import CandidateSpec, RollingFold, compare_candidates, evaluate_initial
from suiroai.modeling.frozen import (finalize_validation, freeze_bundle, record_defect_recheck, record_failed_defect_recheck, reserved_actuals_payload,
                                     score_frozen, shared_defect_recheck)
from suiroai.modeling.records import (comparison_record, final_record, initial_record,
                                      persist_candidate)


class MeasuredRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.store = ArtifactStore(self.temp.name)
        fixture = json.loads((Path(__file__).resolve().parents[2] /
                              "examples/contracts/v0.1.0/successful_analysis.json").read_text())
        records = {r["kind"]: r for r in fixture["records"]}
        self.execution = deepcopy(records["execution_contract"])
        self.preparation = deepcopy(records["preparation_result"])
        self.feature_result = deepcopy(records["feature_result"])
        self.plan = deepcopy(records["evaluation_result"]["evaluation_plan"])
        self.execution["acceptance_rule"] = {
            "rule_id": "mock-measured-mae", "version": 1, "declared_at": "2026-10-17T09:00:15Z",
            "metric_gates": [{"metric_id": "mae", "aggregation": "equal_series_mean", "population_id": "mock-final",
                              "direction": "upper_bound", "threshold": 1.0, "unit": "product_unit"}],
            "required_check_ids": ["frozen_coverage"], "all_gates_required": True, "minimum_observation_count": 1}
        self.original_ref = self.put("mock-original-feature-set", {"meaning": "mock calendar index"})
        self.augmented_ref = self.put("mock-augmented-feature-set", {"meaning": "mock LLM-added square"})
        self.preparation["initial_feature_set_ref"] = self.original_ref
        self.feature_result["materialized_feature_set_ref"] = self.augmented_ref
        self.plan["primary_metric_id"] = "mae"
        self.plan["metric_definitions"] = [
            {"metric_id": "mae", "formula": "equal-series mean absolute horizon-total error", "unit": "product_unit",
             "aggregation": "equal_series_mean", "direction": "lower_is_better", "tie_tolerance": 0.0}]
        key = ("mock-task", "mock-product", "mock-store")
        training = tuple(Example(Window(key, date(2024, 1, 1)+timedelta(days=i), 1),
                                 (float(i),), float(2*i+2)) for i in range(5))
        validation = (Example(Window(key, date(2025, 10, 31), 1), (5.0,), 12.0),)
        self.folds = (RollingFold("mock-measured-fold", training, validation),)
        self.augmented = tuple(replace(f, training=tuple(replace(e, features=(*e.features, e.features[0]**2)) for e in f.training),
                                      validation=tuple(replace(e, features=(*e.features, e.features[0]**2)) for e in f.validation)) for f in self.folds)
        self.plan["development_folds"] = [{"fold_id": "mock-measured-fold", "training_end": "2025-10-31",
            "forecast_origin": "2025-10-31", "target_start": "2025-11-01", "target_end": "2025-11-01",
            "population_ref": self.original_ref}]
        self.initial_spec = CandidateSpec("mock-initial-ridge", "ridge", "original", {"alpha": 0.01}, "Mock bounded linear trend.")
        self.augmented_spec = CandidateSpec("mock-augmented-mean", "mean", "augmented", {}, "Mock simpler comparator for feature inclusion.")
        baseline = CandidateSpec("mock-demo-baseline", "past_mean", "original", {}, "Mock past-only historical comparator.")
        self.initial_measured = evaluate_initial(self.folds, baseline, self.initial_spec, population_id="mock-development")
        self.initial_candidate, self.initial_model = self.persist("mock-initial", self.initial_measured["initial"], self.original_ref, training)
        self.initial = initial_record(self.store, execution=self.execution, preparation=self.preparation,
            artifact_id="mock-measured-initial-record", plan=self.plan, measured=self.initial_measured,
            candidate=self.initial_candidate, parent_decision=self.decision("initial_baseline_evaluation"))
        self.measured = compare_candidates({"original": self.folds, "augmented": self.augmented},
            [self.initial_spec, self.augmented_spec], population_id="mock-development")
        self.augmented_candidate, _ = self.persist("mock-augmented", self.measured["candidates"][1],
                                                 self.augmented_ref, self.augmented[0].training)
        self.candidates = [self.initial_candidate, self.augmented_candidate]
        self.window = Window(key, CUTOFF, 1)
        self.predicted = self.initial_model.predict(Example(self.window, (6.0,), 0.0))
        self.frozen = freeze_bundle(self.store, execution=self.execution, artifact_id="mock-measured-freeze",
            selected_candidate_id=self.measured["selected_candidate_id"], model_ref=self.initial_candidate["model_ref"],
            feature_set_ref=self.original_ref, preprocessing_ref=self.initial_candidate["preprocessing_ref"],
            evaluation_plan_ref=self.put("mock-measured-plan", self.plan), acceptance_rule=self.execution["acceptance_rule"],
            development_input_refs=[self.original_ref], forecast_input_refs=[self.original_ref],
            forecast=[(self.window, self.predicted)], frozen_at="2026-10-17T09:02:00Z")
        self.checks = [{"check_id": "mock-measured-comparable", "requirement_id": "DSC-28", "status": "pass",
                        "expected": "equal populations, origins, horizons and metrics", "actual": "measured synthetic equality",
                        "evidence_refs": self.initial_candidate["evidence_refs"], "verifier": "mock-component-test"}]
        self.evaluation = self.comparison()

    def put(self, identity, payload):
        return self.store.put_bytes(identity, 1, "mock", canonical(payload))

    def decision(self, checkpoint, decision="proceed", refs=None, at="2026-10-17T09:03:00Z"):
        return {"checkpoint": checkpoint, "decision": decision, "actor": "mock-parent", "decided_at": at,
                "reason": "Explicit mock independent parent test decision.", "evidence_refs": refs or [self.original_ref]}

    def persist(self, identity, measurement, ref, training):
        return persist_candidate(self.store, execution=self.execution, artifact_id=identity, measurement=measurement,
                                 feature_set_ref=ref, final_training=training, feature_names=["x"] if len(training[0].features)==1 else ["x","square"], remaining_fits=1, max_seconds=10)

    def comparison(self, **changes):
        kwargs = {"execution": self.execution, "preparation": self.preparation, "initial": self.initial,
                  "feature_result": self.feature_result, "artifact_id": "mock-measured-comparison-record",
                  "measured": self.measured, "candidates": self.candidates, "frozen": self.frozen["frozen"],
                  "parent_decision": self.decision("comparison_and_freeze"), "checks": self.checks, "bundle_ref": self.frozen["bundle_ref"]}
        kwargs.update(changes)
        return comparison_record(self.store, **kwargs)

    def score(self, actual, *, identity="mock-final-targets", scored_at="2026-10-17T09:04:00Z"):
        actuals = {self.window: Example(self.window, (), actual)}
        targets = self.put(identity, reserved_actuals_payload(actuals))
        return score_frozen(self.store, self.frozen["bundle_ref"], actuals,
            holdout_accessed_at="2026-10-17T09:03:30Z", observed_through=date(2025, 12, 31),
            population_id="mock-final", reserved_unseen_data_ref=targets,
            evidence_id=identity+"/evidence", scored_at=scored_at)

    def final(self, evidence, *, identity="mock-measured-final-record", rechecks=(), review=None):
        return final_record(self.store, execution=self.execution, evaluation=self.evaluation, artifact_id=identity,
            evidence=evidence, parent_review=review or self.decision("final_validation",
                "proceed" if evidence["outcome"] == "pass" else "confirmed_failure", at="2026-10-17T09:05:00Z"),
            defect_rechecks=rechecks)

    def test_measured_initial_comparison_and_final_records_serialize(self):
        result = self.score(self.predicted+0.5)
        final = self.final(result["evidence"])
        for record in (self.initial, self.evaluation, final):
            self.assertEqual(validate_record(record), [])
            self.assertEqual(record["provenance"], "mock")
        self.assertEqual(self.initial["comparison"], "better")
        binding_check=next(c for c in self.evaluation["comparison_checks"] if c["check_id"]=="immutable_freeze_binding")
        self.assertIn(self.frozen["bundle_ref"],binding_check["evidence_refs"])
        self.assertEqual(self.evaluation["candidates"][0], self.initial["initial_candidate"])
        self.assertEqual(final["outcome"], "pass")
        self.assertAlmostEqual(final["scores"][0]["value"], 0.5)
        self.assertEqual(final["frozen_result_ref"]["sha256"], digest(self.evaluation["frozen"]))
        self.assertEqual(json.loads(self.store.read_bytes(final["frozen_result_ref"])), self.evaluation["frozen"])
        self.assertEqual(final["november_30_forecast_ref"], self.frozen["frozen"]["november_30_forecast_ref"])

    def test_mutated_shortlist_metric_and_winner_are_rejected(self):
        for field, value in (("primary_metric_id", "bias"), ("direction", "higher_is_better"),
                             ("tie_tolerance", 100.0), ("selected_candidate_id", "mock-augmented-mean")):
            with self.subTest(field=field):
                measured = deepcopy(self.measured)
                measured[field] = value
                with self.assertRaises(ModelingError):
                    self.comparison(measured=measured)

    def test_changed_acceptance_rule_or_frozen_choice_rejected(self):
        result = self.score(self.predicted)
        wrong_rule = deepcopy(result["evidence"])
        wrong_rule["acceptance_rule"]["metric_gates"][0]["threshold"] = 1000
        with self.assertRaisesRegex(ModelingError, "acceptance rule"):
            self.final(wrong_rule)
        wrong_freeze = deepcopy(result["evidence"])
        wrong_freeze["frozen_result_ref"] = self.original_ref
        with self.assertRaisesRegex(ModelingError, "frozen selection"):
            self.final(wrong_freeze)

    def test_measured_failure_stays_failure_after_parent_review(self):
        result = self.score(self.predicted+20)
        final = self.final(result["evidence"])
        self.assertEqual(final["outcome"], "fail")
        self.assertEqual(validate_record(final), [])
        with self.assertRaisesRegex(ModelingError, "contradicts"):
            self.final(result["evidence"], identity="mock-invalid-parent-final",
                       review=self.decision("final_validation", "proceed"))

    def test_failed_correction_projects_without_inventing_new_scores(self):
        original = self.score(self.predicted+20)
        authorization = self.decision("final_validation", "allow_defect_recheck",
                                      [original["evidence_ref"]], "2026-10-17T09:05:00Z")
        private = record_failed_defect_recheck(self.store, original["evidence_ref"], attempt=1,
            max_defect_rechecks=1, defect_description="Mock demonstrated correction runtime failure.",
            defect_evidence_refs=[self.original_ref], correction_refs=[self.original_ref],
            failure_evidence_refs=[self.original_ref], error_code="runtime_error",
            parent_authorization=authorization, artifact_id="mock-failed-correction",
            recheck_started_at="2026-10-17T09:06:00Z")
        shared = shared_defect_recheck(self.store, private)
        checked_definition("defect_recheck", shared)
        self.assertEqual(shared["scores"], [])
        self.assertEqual(shared["outcome"], "execution_failure")
        review = self.decision("final_validation", "confirmed_failure",
                               [original["evidence_ref"], private], "2026-10-17T09:09:00Z")
        terminal = finalize_validation(self.store, original["evidence_ref"], parent_review=review,
                                       defect_rechecks=[private], max_defect_rechecks=1)
        self.assertEqual(terminal["outcome"], "execution_failed")
        diagnostic = self.final(original["evidence"], rechecks=[shared], review=review)
        self.assertEqual(validate_record(diagnostic), [])
        self.assertEqual(diagnostic["scores"], original["evidence"]["scores"])
        self.assertEqual(diagnostic["outcome"], "fail")

    def test_shared_defect_projection_serializes_corrected_final(self):
        # Explicit simulated implementation defect; final data/model/rule stay fixed.
        corrected = self.score(self.predicted, scored_at="2026-10-17T09:08:00Z")
        old = deepcopy(corrected["evidence"])
        old.update(outcome="fail", requires_parent_review=True, scored_at="2026-10-17T09:04:00Z")
        old["scores"][0]["value"] = 20.0
        old_ref = self.put("mock-simulated-old-scorer-defect", old)
        authorization = self.decision("final_validation", "allow_defect_recheck", [old_ref], "2026-10-17T09:05:00Z")
        recheck_ref = record_defect_recheck(self.store, old_ref, corrected["evidence_ref"], attempt=1,
            max_defect_rechecks=1, defect_description="Explicit mock subtraction defect established independently.",
            defect_evidence_refs=[self.original_ref], correction_refs=[self.original_ref],
            parent_authorization=authorization, artifact_id="mock-measured-recheck", recheck_started_at="2026-10-17T09:06:00Z")
        shared = shared_defect_recheck(self.store, recheck_ref)
        checked_definition("defect_recheck", shared)
        self.assertNotIn("format", shared)
        final = self.final(corrected["evidence"], rechecks=[shared],
            review=self.decision("final_validation", "pass_after_recheck", [old_ref, recheck_ref], "2026-10-17T09:09:00Z"))
        self.assertEqual(validate_record(final), [])
        self.assertEqual(final["scores"], shared["scores"])
        self.assertEqual(final["outcome"], shared["outcome"])
        self.assertEqual(final["november_30_forecast_ref"], old["november_30_forecast_ref"])


if __name__ == "__main__":
    unittest.main()
