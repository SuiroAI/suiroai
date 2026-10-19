"""MOCK final-release guards only; no native modeling or holdout evaluation.

Exercise release of the adopted immutable model bundle and exact detached
manifest while rejecting substitutions, ambiguous content, and early access.
"""
from copy import deepcopy
import json
import unittest

import test_workflow as fixtures
from suiroai.contracts import digest
from suiroai.parent import GuardRejected


class FrozenReleaseGuards(unittest.TestCase):
    setUp = fixtures.WorkflowTests.setUp
    release = fixtures.WorkflowTests.release
    review = fixtures.WorkflowTests.review
    r = fixtures.WorkflowTests.r
    rehash = fixtures.WorkflowTests.rehash
    begin = fixtures.WorkflowTests.begin
    refs_for_stage = fixtures.WorkflowTests.refs_for_stage
    stage = fixtures.WorkflowTests.stage
    to_final = fixtures.WorkflowTests.to_final

    def bundle(self, *, mutate=None, reviewed=True, encode=None):
        """Persist deliberately invented DSC-28 bytes, never native artifacts."""
        self.rehash()
        execution = self.r("execution_contract")
        packet = {
            "format": "dsc28-frozen-v1",
            "frozen": deepcopy(self.r("evaluation_result")["frozen"]),
            "frozen_result_ref": deepcopy(self.r("final_validation_result")["frozen_result_ref"]),
            "expected_observation_count": 1,
            "minimum_coverage_fraction": 1,
            "binding": deepcopy(execution["binding"]),
            "run_id": execution["run_id"],
            "execution_contract_sha256": digest(execution),
        }
        if mutate:
            mutate(packet)
        data = json.dumps(packet, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode()
        if encode:
            data = encode(packet, data)
        ref = self.store.put_bytes("mock-dsc28-frozen-bundle", 1, "mock", data)
        self.external.append(ref)
        if reviewed:
            self.r("evaluation_result")["comparison_checks"][0]["evidence_refs"].append(ref)
        return ref

    def final_refs(self, bundle_ref):
        frozen = self.r("evaluation_result")["frozen"]
        refs = [
            self.r("preparation_result")["reserved_unseen_data_ref"],
            self.r("final_validation_result")["frozen_result_ref"],
            frozen["evaluation_plan_ref"], frozen["acceptance_rule_ref"],
            frozen["model_ref"], frozen["feature_set_ref"], frozen["preprocessing_ref"],
            frozen["november_30_forecast_ref"],
            *frozen["development_input_refs"], *frozen["forecast_input_refs"], bundle_ref,
        ]
        # A forecast source can also be a development source; release once.
        return list({digest(ref): ref for ref in refs}.values())

    def assert_rejected_bundle(self, mutate, *, reviewed=True, encode=None):
        ref = self.bundle(mutate=mutate, reviewed=reviewed, encode=encode)
        self.to_final()
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([self.r("preparation_result")["reserved_unseen_data_ref"], ref])
        self.assertEqual(self.parent.state, "final_validation")
        self.assertIsNone(self.parent.checkpoint()["active_request_ref"])
        self.assertFalse(any(stage == "final_validation" for stage, _ in self.release_calls))

    def test_exact_reviewed_bundle_and_frozen_dependencies_are_released(self):
        bundle_ref = self.bundle()
        self.to_final()
        refs = self.final_refs(bundle_ref)
        request_ref = self.parent.issue_stage(refs)
        request = self.store.read_record(request_ref)
        self.assertEqual(request["released_input_refs"], refs)
        self.assertEqual(request["stage"], "final_validation")
        self.assertEqual(self.release_calls[-1], ("final_validation", refs))
        self.assertTrue(self.parent.parent_permits(request_ref))

    def test_final_release_includes_forecast_only_as_of_input(self):
        # This operational input is not a fitting source and is still needed
        # to reproduce the immutable November 30 forecast at final validation.
        source = next(artifact for artifact in self.fixture["mock_artifacts"]
                      if artifact["role"] == "source_usable_stock")
        source_ref = deepcopy(source["ref"])
        self.r("preparation_result")["availability"].append(deepcopy(source["availability"]))
        frozen = self.r("evaluation_result")["frozen"]
        self.assertNotIn(source_ref, frozen["development_input_refs"])
        frozen["forecast_input_refs"].append(source_ref)
        # The manifest is itself immutable measured JSON of the exact choice.
        manifest = self.store.put_bytes("mock-forecast-inputs-freeze", 1, "mock",
            json.dumps(frozen, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False).encode())
        old = self.r("final_validation_result")["frozen_result_ref"]
        self.records = fixtures.replace(self.records, old, manifest)
        self.external.append(manifest)
        bundle_ref = self.bundle()
        self.to_final()
        request_ref = self.parent.issue_stage(self.final_refs(bundle_ref))
        self.assertIn(source_ref, self.store.read_record(request_ref)["released_input_refs"])

    def test_reviewed_bundle_cannot_change_model_plan_or_rule(self):
        for field in ("model_ref", "evaluation_plan_ref", "acceptance_rule_ref"):
            with self.subTest(field=field):
                self.setUp()
                self.assert_rejected_bundle(lambda packet: packet["frozen"].update({field: self.external[0]}))

    def test_reviewed_bundle_cannot_change_binding_run_or_execution_digest(self):
        mutations = {
            "binding": lambda packet: packet["binding"].update(input_version=999),
            "run_id": lambda packet: packet.update(run_id="MOCK-another-run"),
            "execution_contract_sha256": lambda packet: packet.update(execution_contract_sha256="0" * 64),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                self.setUp()
                self.assert_rejected_bundle(mutate)

    def test_reviewed_bundle_cannot_replace_frozen_manifest(self):
        self.assert_rejected_bundle(lambda packet: packet.update(frozen_result_ref=self.external[0]))

    def test_measured_but_unreviewed_bundle_is_not_releasable(self):
        self.assert_rejected_bundle(None, reviewed=False)

    def test_bundle_mentioned_only_in_parent_decision_lacks_comparison_check(self):
        bundle_ref = self.bundle(reviewed=False)
        self.r("evaluation_result")["parent_decision"]["evidence_refs"].append(bundle_ref)
        self.to_final()
        with self.assertRaises(GuardRejected):
            self.parent.issue_stage([self.r("preparation_result")["reserved_unseen_data_ref"], bundle_ref])
        self.assertIsNone(self.parent.checkpoint()["active_request_ref"])

    def test_reviewed_bundle_with_extra_content_is_not_releasable(self):
        self.assert_rejected_bundle(lambda packet: packet.update(raw_future_rows=["MOCK prohibited extra payload"]))

    def test_reviewed_bundle_requires_canonical_measured_bytes(self):
        self.assert_rejected_bundle(None, encode=lambda packet, _: json.dumps(packet, indent=2).encode())

    def test_duplicate_frozen_key_cannot_hide_extra_future_payload(self):
        def duplicate_frozen_key(packet, canonical):
            data = b'{"frozen":{"raw_future_rows":["MOCK prohibited hidden payload"]},' + canonical[1:]
            # An ordinary JSON parse silently loses the first frozen value.
            # Byte identity must therefore be checked in addition to equality.
            self.assertEqual(json.loads(data), packet)
            return data
        self.assert_rejected_bundle(None, encode=duplicate_frozen_key)

    def test_bundle_and_holdout_are_denied_to_each_development_stage(self):
        bundle_ref = self.bundle()
        self.begin()
        self.stage()
        for expected in ("initial_baseline_evaluation", "llm_features", "comparison_and_freeze"):
            self.assertEqual(self.parent.state, expected)
            for protected in (bundle_ref, self.r("preparation_result")["reserved_unseen_data_ref"]):
                with self.subTest(stage=expected, artifact=protected["artifact_id"]):
                    with self.assertRaises(GuardRejected):
                        self.parent.issue_stage([*self.refs_for_stage(), protected])
                    self.assertIsNone(self.parent.checkpoint()["active_request_ref"])
            result, _ = self.stage()
            self.assertEqual(result["outcome"], "completed", result.get("failure"))
        self.assertEqual(self.parent.state, "final_validation")


if __name__ == "__main__":
    unittest.main()
