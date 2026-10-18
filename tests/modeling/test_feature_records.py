"""Synthetic feature integration; all calls, facts and parent decisions are mocks.

Some tests use nonmock-shaped provenance labels to verify that an explicitly
mock LLM call remains mock. Such labels do not establish real execution evidence.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from suiroai.contracts import digest, record_ref, validate_record
from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.modeling.core import ModelingError, canonical
from suiroai.modeling.features import (DevelopmentArtifact, generate_feature_proposal,
                                      materialize_features)
from suiroai.modeling.records import feature_records


class FeatureRecordTests(unittest.TestCase):
    def setUp(self):
        self.context = self.build_context()

    def build_context(self, provenance="mock"):
        temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        store = ArtifactStore(temporary.name)
        example_root = Path(__file__).resolve().parents[2] / "examples/contracts/v0.1.0"
        records = json.loads((example_root / "successful_analysis.json").read_text())["records"]
        stage_records = json.loads((example_root / "approved_execution.json").read_text())["records"]

        def relabel(value):
            if isinstance(value, dict):
                return {key: provenance if key == "provenance" else relabel(child)
                        for key, child in value.items()}
            if isinstance(value, list):
                return [relabel(child) for child in value]
            return value

        execution = relabel(next(r for r in records if r["kind"] == "execution_contract"))
        preparation = relabel(next(r for r in records if r["kind"] == "preparation_result"))
        initial = relabel(next(r for r in records if r["kind"] == "initial_evaluation_result"))
        fields = ["target_month", "target_day_of_year"]
        rows = [{"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-11-29",
                 "target_month": 11, "target_day_of_year": 333},
                {"Product_ID": "P1", "Store_ID": "S1", "origin": "2025-11-30",
                 "target_month": 11, "target_day_of_year": 334}]
        original_payload = {"format": "dsc27-initial-v1", "source_namespace": execution["binding"]["task_id"],
                            "rows": rows, "definitions": []}
        original_ref = store.put_bytes("fixture-original-features", 1, provenance, canonical(original_payload))

        def definition(feature_id, operation, refs):
            return {"feature_id": feature_id, "name": "Synthetic feature " + feature_id,
                    "expression": json.dumps(operation), "source_refs": refs,
                    "event_time_basis": "Calendar at forecast origin",
                    "availability_time_basis": "Known at forecast origin",
                    "minimum_lag_calendar_days": 0,
                    "timing_rule": "Use unchanged origin-safe calendar inputs at inference",
                    "uses_only_information_available_at_origin": True,
                    "rationale": "Synthetic component hypothesis only; comparison required",
                    "fit_scope": "training_fold_only"}

        preparation["execution_contract_ref"] = record_ref(execution)
        preparation["initial_feature_set_ref"] = original_ref
        preparation["initial_feature_definitions"] = [
            definition(fields[0], {"op": "calendar", "part": "month"}, [original_ref]),
            definition(fields[1], {"op": "calendar", "part": "day_of_year"}, [original_ref])]
        preparation["development_context_allowlist"] = [original_ref, preparation["prepared_development_data_ref"]]
        initial["execution_contract_ref"] = record_ref(execution)
        initial["preparation_result_ref"] = record_ref(preparation)
        initial["initial_candidate"]["feature_set_ref"] = original_ref
        initial_ref = record_ref(initial)
        artifacts, availability = [], []
        for summary_type in ("task_context", "eda", "development_errors"):
            summary = {"format": "dsc28-development-summary-v1", "binding": execution["binding"],
                       "run_id": execution["run_id"], "source_namespace": execution["binding"]["task_id"],
                       "development_end": "2025-11-30", "summary_type": summary_type,
                       "feature_fields": fields, "task_goal": "retail_restocking_forecast",
                       "target_policy": "positive_completed_gross_units",
                       "statistics": [] if summary_type == "task_context" else [
                           {"name": "row_count" if summary_type == "eda" else "mae", "value": 2,
                            "period_start": "2025-10-31", "period_end": "2025-11-30"}]}
            reference = store.put_bytes("fixture-post-step6-" + summary_type, 1, provenance, canonical(summary))
            artifacts.append(DevelopmentArtifact(reference, summary, date(2025, 11, 30)))
            availability.append({"artifact_ref": reference, "permitted_use": "development",
                                 "earliest_event_date": "2025-10-31", "latest_event_date": "2025-11-30",
                                 "latest_information_available_date": "2025-11-30",
                                 "event_time_column": None, "availability_time_column": None,
                                 "contains_post_cutoff_rows": False})
        stage = relabel(next(r for r in stage_records if r["kind"] == "stage_request"))
        stage.update(stage="llm_features", execution_contract_ref=record_ref(execution),
                     issued_at="2026-10-17T12:00:00Z", deadline="2026-10-17T12:01:00Z",
                     released_input_refs=[record_ref(preparation), initial_ref, *(a.ref for a in artifacts)])
        stage["parent_authorization"] = dict(initial["parent_decision"], checkpoint="llm_features",
                                              decided_at="2026-10-17T12:00:00Z", evidence_refs=[initial_ref])
        added = [definition("origin_weekend", {"op": "calendar", "part": "is_weekend"}, [artifacts[1].ref]),
                 definition("calendar_product", {"op": "multiply", "fields": fields}, [artifacts[1].ref])]
        before = deepcopy(preparation)
        generated = generate_feature_proposal(
            execution=execution, preparation=preparation, stage_request=stage,
            context_availability=availability, initial_evaluation=initial,
            initial_evaluation_ref=initial_ref, parent_decision=initial["parent_decision"],
            artifacts=artifacts, initial_feature_fields=fields,
            llm=lambda prompt: json.dumps({"definitions": added}), model_id="mock-feature-llm",
            generated_at="2026-10-17T12:00:01Z", provenance="mock")
        materialized = materialize_features(rows, generated["definitions"], initial_feature_fields=fields,
                                            source_refs=generated["development_context_refs"])
        parent = dict(stage["parent_authorization"], decided_at="2026-10-17T12:00:02Z",
                      evidence_refs=[initial_ref])
        return {"store": store, "execution": execution, "preparation": preparation, "initial": initial,
                "generated": generated, "materialized": materialized, "parent": parent,
                "before": before, "original_payload": original_payload, "artifacts": artifacts}

    def persist(self, context=None, **changes):
        context = context or self.context
        kwargs = {"execution": context["execution"], "preparation": context["preparation"],
                  "initial": context["initial"], "artifact_id": "fixture-added-features",
                  "generated": context["generated"], "materialized": context["materialized"],
                  "parent_decision": context["parent"]}
        kwargs.update(changes)
        return feature_records(context["store"], **kwargs)

    def test_generated_and_materialized_features_serialize_with_immutable_evidence(self):
        context = self.context
        proposal, result = self.persist()
        for record in (proposal, result):
            self.assertEqual(validate_record(record), [])
            self.assertEqual(record["provenance"], "mock")
            self.assertEqual(context["store"].read_record(record_ref(record)), record)
        self.assertEqual(proposal["generation"]["model_id"], "mock-feature-llm")
        for key in ("prompt", "response"):
            reference = proposal["generation"][key + "_ref"]
            self.assertEqual(context["store"].read_bytes(reference), context["generated"][key].encode())
        stored = json.loads(context["store"].read_bytes(result["materialized_feature_set_ref"]))
        self.assertEqual(stored["rows"], context["materialized"]["rows"])
        self.assertEqual(stored["rows"][0]["calendar_product"], 3663)
        self.assertEqual(stored["rows"][0]["origin_weekend"], 1)
        self.assertEqual(result["validation_checks"][0]["status"], "pass")
        self.assertIn(context["generated"]["stage_request_ref"], result["lineage"][0]["input_refs"])
        self.assertIn(context["preparation"]["initial_feature_set_ref"], result["lineage"][0]["input_refs"])
        self.assertEqual(context["before"], context["preparation"])
        self.assertEqual(digest(context["before"]), context["initial"]["preparation_result_ref"]["sha256"])
        for artifact in context["artifacts"]:
            self.assertNotIn(artifact.ref, context["preparation"]["development_context_allowlist"])
            self.assertIn(artifact.ref, proposal["generation"]["development_context_refs"])

    def test_explicit_mock_call_stays_mock_with_nonmock_shaped_input_metadata(self):
        context = self.build_context(provenance="derived")
        self.assertEqual(context["execution"]["provenance"], "derived")
        self.assertTrue(all(ref["provenance"] == "derived" for ref in context["generated"]["development_context_refs"]))
        proposal, result = self.persist(context)
        self.assertEqual(proposal["provenance"], "mock")
        self.assertEqual(result["provenance"], "mock")
        self.assertEqual(proposal["generation"]["prompt_ref"]["provenance"], "mock")
        self.assertEqual(proposal["generation"]["response_ref"]["provenance"], "mock")

    def test_changed_original_values_are_checked_against_prepared_artifact_bytes(self):
        context = self.context
        rows = deepcopy(context["original_payload"]["rows"])
        rows[0]["target_month"] = 99
        materialized = materialize_features(rows, context["generated"]["definitions"],
            initial_feature_fields=context["generated"]["initial_feature_fields"],
            source_refs=context["generated"]["development_context_refs"])
        with self.assertRaisesRegex(ModelingError, "original values differ"):
            self.persist(materialized=materialized)

    def test_original_artifact_bytes_are_retrieved_and_hash_verified(self):
        reference = self.context["preparation"]["initial_feature_set_ref"]
        object_path = self.context["store"].root / "objects" / reference["sha256"]
        object_path.chmod(0o600)
        object_path.write_bytes(b'{"format":"tampered-original"}')
        with self.assertRaisesRegex(ArtifactError, "measured artifact bytes"):
            self.persist()

    def test_materialized_output_and_checks_cannot_be_tampered_after_calculation(self):
        for mutation in ("output", "check", "digest"):
            with self.subTest(mutation=mutation):
                materialized = deepcopy(self.context["materialized"])
                if mutation == "output":
                    materialized["rows"][0]["calendar_product"] += 1
                elif mutation == "check":
                    materialized["checks"]["calculation_rechecked"] = False
                else:
                    materialized["checks"]["reproducibility_sha256"] = "0" * 64
                with self.assertRaisesRegex(ModelingError, "outputs/checks changed"):
                    self.persist(materialized=materialized)

    def test_changed_llm_call_bytes_fail_before_shared_result(self):
        generated = deepcopy(self.context["generated"])
        generated["response"] = "{}"
        with self.assertRaisesRegex(ModelingError, "call evidence changed"):
            self.persist(generated=generated)

    def test_stored_definitions_must_be_the_actual_llm_response(self):
        context = self.context
        generated = deepcopy(context["generated"])
        generated["definitions"][1]["expression"] = json.dumps(
            {"op": "add", "fields": generated["initial_feature_fields"]})
        materialized = materialize_features(context["original_payload"]["rows"], generated["definitions"],
            initial_feature_fields=generated["initial_feature_fields"], source_refs=generated["development_context_refs"])
        with self.assertRaises(ModelingError):
            self.persist(generated=generated, materialized=materialized)


if __name__ == "__main__":
    unittest.main()
