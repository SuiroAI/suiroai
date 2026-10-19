"""Mock component calculations only; no live LLM or analytical acceptance.

Exercise bounded feature proposals and materialization, rejecting malformed
definitions, forbidden information, and inconsistent initial feature sets.

Requirement context for these component checks:
Support step7 additional features after the initial evaluation by retaining
definitions, source fields, rationale, and prediction-time availability; keep
the original feature set available for measured step8 comparison.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import unittest

from suiroai.contracts import digest, record_ref
from suiroai.modeling.core import ModelingError
from suiroai.modeling.features import (DevelopmentArtifact, generate_feature_proposal,
                                      materialize_features)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((Path(__file__).resolve().parents[2] /
                              "examples/contracts/v0.1.0/successful_analysis.json").read_text())
        self.execution = next(r for r in fixture["records"] if r["kind"] == "execution_contract")
        self.preparation = next(r for r in fixture["records"] if r["kind"] == "preparation_result")
        self.fields = ["month", "day_of_year"]
        self.summary = {
            "format": "dsc28-development-summary-v1", "binding": self.execution["binding"],
            "run_id": self.execution["run_id"], "source_namespace": self.execution["binding"]["task_id"],
            "development_end": "2025-11-30", "summary_type": "development_errors",
            "feature_fields": self.fields,
            "statistics": [{"name": "mae", "value": 2.5,
                            "period_start": "2025-10-01", "period_end": "2025-11-30"}],
            "task_goal": "retail_restocking_forecast", "target_policy": "positive_completed_gross_units",
        }
        self.artifact = self.artifact_for(self.summary)
        self.artifacts = [self.artifact]
        for summary_type in ("task_context", "eda"):
            payload = dict(self.summary, summary_type=summary_type)
            self.artifacts.append(DevelopmentArtifact(self.ref(payload, "mock-" + summary_type), payload, date(2025, 11, 30)))
        self.preparation["initial_feature_definitions"] = [
            self.definition("month", {"op": "calendar", "part": "month"}),
            self.definition("day_of_year", {"op": "calendar", "part": "day_of_year"})]
        self.initial = next(r for r in fixture["records"] if r["kind"] == "initial_evaluation_result")
        self.initial["preparation_result_ref"] = record_ref(self.preparation)
        self.initial_ref = record_ref(self.initial)
        self.parent = self.initial["parent_decision"]
        stage_fixture = json.loads((Path(__file__).resolve().parents[2] /
                                    "examples/contracts/v0.1.0/approved_execution.json").read_text())
        self.stage = next(r for r in stage_fixture["records"] if r["kind"] == "stage_request")
        self.stage.update(stage="llm_features", issued_at="2026-10-17T12:00:00Z", deadline="2026-10-17T12:01:00Z",
                          released_input_refs=[*(a.ref for a in self.artifacts), self.initial_ref, record_ref(self.preparation)])
        self.stage["parent_authorization"] = dict(self.parent, checkpoint="llm_features")
        self.availability = [{"artifact_ref": self.artifact.ref, "permitted_use": "development",
                              "earliest_event_date": "2025-10-01", "latest_event_date": "2025-11-30",
                              "latest_information_available_date": "2025-11-30",
                              "event_time_column": None, "availability_time_column": None,
                              "contains_post_cutoff_rows": False}]
        self.availability.extend(dict(self.availability[0], artifact_ref=a.ref) for a in self.artifacts[1:])
        self.calendar = self.definition("weekend", {"op": "calendar", "part": "is_weekend"})

    @staticmethod
    def ref(payload, name="mock-summary"):
        return {"artifact_id": name, "version": 1, "sha256": digest(payload), "provenance": "mock"}

    def artifact_for(self, payload):
        return DevelopmentArtifact(self.ref(payload), payload, date(2025, 11, 30))

    def definition(self, name, spec):
        return {"feature_id": name, "name": "Mock feature meaning: " + name,
                "expression": json.dumps(spec), "source_refs": [self.artifact.ref],
                "event_time_basis": "Forecast origin calendar date",
                "availability_time_basis": "Calendar and initial fields known at origin",
                "minimum_lag_calendar_days": 0,
                "timing_rule": "Use only released calendar inputs at origin; unchanged at inference",
                "uses_only_information_available_at_origin": True,
                "rationale": "Mock hypothesis, eligibility requires measured comparison",
                "fit_scope": "training_fold_only"}

    def generate(self, **changes):
        kwargs = dict(execution=self.execution, preparation=self.preparation, stage_request=self.stage,
                      context_availability=self.availability, initial_evaluation=self.initial,
                      initial_evaluation_ref=self.initial_ref, parent_decision=self.parent,
                      artifacts=self.artifacts, initial_feature_fields=self.fields,
                      llm=lambda prompt: json.dumps({"definitions": [self.calendar]}),
                      model_id="mock-llm", generated_at="2026-10-17T12:00:01Z", provenance="mock")
        kwargs.update(changes)
        return generate_feature_proposal(**kwargs)

    def materialize(self, definitions=None, rows=None):
        return materialize_features(rows or [{"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-11-30",
                                             "month": 11, "day_of_year": 334}],
                                    definitions or [self.calendar], initial_feature_fields=self.fields,
                                    source_refs=[self.artifact.ref])

    def test_generation_calls_llm_once_with_released_summaries_and_retains_provenance(self):
        prompts = []
        def llm(prompt):
            prompts.append(prompt)
            return json.dumps({"definitions": [self.calendar]})
        result = self.generate(llm=llm)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(result["binding"], self.execution["binding"])
        self.assertEqual(result["run_id"], self.execution["run_id"])
        self.assertEqual(result["definitions"], [self.calendar])
        self.assertEqual(result["model_id"], "mock-llm")
        self.assertEqual(result["initial_evaluation_ref"], self.initial_ref)
        self.assertEqual(result["prompt_sha256"], hashlib.sha256(prompts[0].encode()).hexdigest())
        self.assertEqual(result["response_sha256"], hashlib.sha256(result["response"].encode()).hexdigest())
        self.assertEqual(result["selection_status"], "proposed_only_not_earned_inclusion")
        self.assertFalse(result["unrestricted_raw_future_access"])
        prompt = json.loads(prompts[0])
        self.assertEqual(prompt["released_development_summaries"][0]["summary"], self.summary)
        self.assertNotIn("raw", prompt)

    def test_step6_gate_is_required_and_ref_must_match_reviewed_bytes(self):
        called = []
        for mutation in ("stop", "wrong_ref", "changed_initial", "wrong_run"):
            with self.subTest(mutation=mutation):
                parent, initial = deepcopy(self.parent), deepcopy(self.initial)
                if mutation == "stop":
                    parent["decision"] = "stop"
                elif mutation == "wrong_ref":
                    parent["evidence_refs"] = [self.artifact.ref]
                elif mutation == "changed_initial":
                    initial["extra"] = 1
                else:
                    initial["run_id"] = "other-run"
                with self.assertRaises(ModelingError):
                    self.generate(parent_decision=parent, initial_evaluation=initial,
                                  llm=lambda p: called.append(p))
        self.assertEqual(called, [])

    def test_context_rejects_holdout_raw_paths_free_prose_and_mutated_bytes(self):
        for mutation in ("future", "raw_path", "free_prose", "future_stat", "unapproved_stat"):
            with self.subTest(mutation=mutation):
                payload = deepcopy(self.summary)
                if mutation == "future":
                    payload["development_end"] = "2025-12-01"
                elif mutation == "raw_path":
                    payload["raw_path"] = "/data/sales-including-december.csv"
                elif mutation == "free_prose":
                    payload["statistics"][0]["notes"] = "December outcomes are excellent"
                elif mutation == "future_stat":
                    payload["statistics"][0]["period_end"] = "2025-12-15"
                else:
                    payload["statistics"][0]["name"] = "final_holdout_mae"
                with self.assertRaises(ModelingError):
                    self.artifact_for(payload)
        self.summary["statistics"][0]["value"] = 999
        with self.assertRaisesRegex(ModelingError, "digest mismatch"):
            self.generate()

    def test_mock_context_cannot_be_laundered_to_real_generation(self):
        with self.assertRaisesRegex(ModelingError, "mock context"):
            self.generate(provenance="derived")

    def test_parent_stage_release_availability_and_remaining_budget_are_required(self):
        for mutation in ("unreleased", "holdout", "future_info", "wrong_stage", "exhausted", "early_call"):
            with self.subTest(mutation=mutation):
                stage, availability = deepcopy(self.stage), deepcopy(self.availability)
                timestamp = "2026-10-17T12:00:01Z"
                if mutation == "unreleased":
                    stage["released_input_refs"].remove(self.artifact.ref)
                elif mutation == "holdout":
                    availability[0]["permitted_use"] = "reserved_unseen_evaluation"
                elif mutation == "future_info":
                    availability[0]["latest_information_available_date"] = "2025-12-01"
                elif mutation == "wrong_stage":
                    stage["stage"] = "comparison_and_freeze"
                elif mutation == "exhausted":
                    stage["remaining_limits"]["max_llm_feature_definitions"] = 0
                else:
                    timestamp = "2026-10-17T11:00:00Z"
                with self.assertRaises(ModelingError):
                    self.generate(stage_request=stage, context_availability=availability, generated_at=timestamp)
        stage = deepcopy(self.stage)
        stage["remaining_limits"]["max_llm_feature_definitions"] = 1
        other = self.definition("other", {"op": "calendar", "part": "quarter"})
        with self.assertRaisesRegex(ModelingError, "count"):
            self.generate(stage_request=stage, llm=lambda prompt: json.dumps({"definitions": [self.calendar, other]}))

    def test_initial_score_branch_and_population_are_independently_checked(self):
        for mutation in ("comparison", "population", "future", "fold_future", "execution"):
            with self.subTest(mutation=mutation):
                initial = deepcopy(self.initial)
                if mutation == "comparison":
                    initial["comparison"] = "worse"
                elif mutation == "population":
                    initial["initial_candidate"]["scores"][0]["population_id"] = "other-population"
                elif mutation == "future":
                    initial["initial_candidate"]["scores"][0]["target_end_max"] = "2025-12-01"
                    initial["baseline_scores"][0]["target_end_max"] = "2025-12-01"
                elif mutation == "fold_future":
                    initial["evaluation_plan"]["development_folds"][0]["target_end"] = "2025-12-01"
                else:
                    initial["execution_contract_ref"]["sha256"] = "0" * 64
                reference = record_ref(initial)
                stage = deepcopy(self.stage)
                stage["released_input_refs"] = [reference if ref == self.initial_ref else ref
                                                for ref in stage["released_input_refs"]]
                with self.assertRaises(ModelingError):
                    self.generate(initial_evaluation=initial, initial_evaluation_ref=reference, stage_request=stage)

    def test_invalid_llm_definitions_are_rejected(self):
        transforms = [{"op": "exec", "code": "raise Exception()"},
                      {"op": "lag", "fields": ["target_quantity"], "days": 1},
                      {"op": "standardize", "fields": ["month"]},
                      {"op": "ratio", "fields": ["month", "day_of_year"]},
                      {"op": "add", "fields": ["month", "Quantity"]}]
        for transform in transforms:
            with self.subTest(transform=transform):
                definition = self.definition("unsafe", transform)
                with self.assertRaises(ModelingError):
                    self.generate(llm=lambda prompt: json.dumps({"definitions": [definition]}))
        with self.assertRaises(ModelingError):
            self.generate(llm=lambda prompt: "```json\n{}\n```")
        with self.assertRaises(ModelingError):
            self.generate(llm=lambda prompt: json.dumps({"definitions": [self.calendar, self.calendar]}))

    def test_arithmetic_null_policy_calendar_and_original_alignment(self):
        definitions = [self.calendar,
                       self.definition("sum_fields", {"op": "add", "fields": self.fields}),
                       self.definition("multiply_fields", {"op": "multiply", "fields": self.fields}),
                       self.definition("ratio_fields", {"op": "ratio", "fields": self.fields, "zero_division": "null"})]
        rows = [{"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-11-30", "month": 11, "day_of_year": 0},
                {"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-12-01", "month": None, "day_of_year": 335}]
        result = self.materialize(definitions, rows)
        self.assertEqual(result["rows"][0]["sum_fields"], 11)
        self.assertEqual(result["rows"][0]["multiply_fields"], 0)
        self.assertEqual(result["rows"][0]["weekend"], 1)
        self.assertIsNone(result["rows"][0]["ratio_fields"])
        self.assertIsNone(result["rows"][1]["sum_fields"])
        self.assertEqual(result["rows"][1]["weekend"], 0)
        for original, materialized in zip(rows, result["rows"]):
            self.assertEqual(original, {key: materialized[key] for key in original})
        self.assertEqual(result["checks"]["null_counts"]["ratio_fields"], 2)
        self.assertTrue(result["checks"]["calculation_rechecked"])
        self.assertEqual(result, self.materialize(definitions, rows))
        self.assertEqual(result["parent_approval"], "required_externally")

    def test_calendar_cyclic_definitions_have_deterministic_inference(self):
        result = self.materialize([self.definition("cycle", {"op": "calendar", "part": "month_cos"})],
                                  [{"Product_ID": "P1", "Store_ID": "S1", "origin": "2026-01-01", "month": 1, "day_of_year": 1}])
        self.assertAlmostEqual(result["rows"][0]["cycle"], 1)

    def test_invalid_rows_and_definition_sources_fail(self):
        row = {"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-11-30", "month": 11, "day_of_year": 334}
        for rows in ([row, row], [dict(row, target_quantity=100)], [dict(row, month=True)],
                     [dict(row, month=float("inf"))], [dict(row, origin="not-a-date")]):
            with self.subTest(rows=rows), self.assertRaises(ModelingError):
                self.materialize(rows=rows)
        definition = deepcopy(self.calendar)
        definition["source_refs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ModelingError, "unreleased"):
            self.materialize([definition])
        for field, value in (("feature_id", "month"), ("minimum_lag_calendar_days", 1)):
            definition = dict(self.calendar, **{field: value})
            with self.assertRaises(ModelingError):
                self.materialize([definition])


if __name__ == "__main__":
    unittest.main()
