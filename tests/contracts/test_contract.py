"""Regressions for approval, leakage and honest terminal contract boundaries.

These tests validate in-memory mock interface graphs. They do not execute an
analytical pipeline, authenticate evidence or establish integration acceptance.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from suiroai.contracts.validation import digest, input_digest, proposal_digest, record_ref, validate_bundle, validate_record, walk

ROOT = Path(__file__).resolve().parent
REF_FIELDS = {"artifact_id", "version", "sha256", "provenance"}


def record(bundle, kind):
    return max((item for item in bundle["records"] if item["kind"] == kind), key=lambda item: item["artifact_version"])


def catalog(bundle, artifact_id):
    return next(item for item in bundle["mock_artifacts"] if item["ref"]["artifact_id"] == artifact_id)


def rehash(bundle):
    """Propagate changed artifact hashes without repairing semantic decisions.

    Intentional binding/proposal digests and provenance stay untouched, so tests
    can distinguish a content-valid prohibited transition from stale bytes.
    """
    for _ in range(40):
        refs = {(r["artifact_id"], r["artifact_version"]): digest(r) for r in bundle["records"]}
        refs.update({(a["ref"]["artifact_id"], a["ref"]["version"]): digest(a["content_marker"]) for a in bundle["mock_artifacts"]})
        changed = False
        for node in walk(bundle):
            if set(node) == REF_FIELDS:
                value = refs.get((node["artifact_id"], node["version"]))
                if value is not None and node["sha256"] != value:
                    node["sha256"] = value
                    changed = True
        if not changed:
            return bundle
    raise AssertionError("Fixture references did not converge; possible accidental cycle")


class ContractBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {path.stem: json.loads(path.read_text()) for path in (ROOT.parents[1] / "examples/contracts/v0.1.0").glob("*.json")}

    def fixture(self, name="successful_analysis"):
        return copy.deepcopy(self.fixtures[name])

    def accepts(self, bundle):
        self.assertEqual(validate_bundle(rehash(bundle)), [])

    def rejects(self, bundle, fragment):
        errors = validate_bundle(rehash(bundle))
        self.assertTrue(any(fragment in error for error in errors), "Expected " + repr(fragment) + "; actual: " + repr(errors))

    def bounded_recheck(self):
        bundle = self.fixture("validation_failed")
        final = record(bundle, "final_validation_result")
        evidence = final["checks"][0]["evidence_refs"]
        authorization = copy.deepcopy(final["parent_review"])
        authorization.update(decision="allow_defect_recheck", decided_at="2026-10-17T09:02:45Z", reason="MOCK bounded scoring alignment defect; frozen selection and forecast unchanged")
        final["parent_review"]["decided_at"] = "2026-10-17T09:03:00Z"
        final["defect_rechecks"] = [{"attempt": 1, "defect_description": "MOCK scoring alignment defect; no selection or holdout tuning",
                                     "defect_evidence_refs": evidence, "correction_refs": evidence,
                                     "parent_authorization": authorization, "model_selection_unchanged": True,
                                     "november_30_forecast_ref": copy.deepcopy(final["november_30_forecast_ref"]),
                                     "scores": copy.deepcopy(final["scores"]), "checks": copy.deepcopy(final["checks"]), "outcome": "fail"}]
        return bundle

    def test_five_baseline_component_fixtures_pass(self):
        self.assertEqual(set(self.fixtures), {"approved_execution", "missing_inputs", "successful_analysis", "validation_failed", "execution_failed"})
        for name, bundle in self.fixtures.items():
            with self.subTest(name=name):
                self.assertEqual(validate_bundle(bundle), [])

    def test_stale_approval_binding_cannot_execute(self):
        bundle = self.fixture()
        record(bundle, "task_approval")["binding"]["proposal_version"] = 2
        self.rejects(bundle, "binding mismatch")

    def test_rejected_proposal_cannot_execute(self):
        bundle = self.fixture()
        record(bundle, "task_approval")["decision"] = "rejected"
        self.rejects(bundle, "execution requires explicit approved decision")

    def test_silence_pending_approval_cannot_execute(self):
        bundle = self.fixture()
        approval = record(bundle, "task_approval")
        approval.update(decision="pending", actor=None, decided_at=None)
        self.rejects(bundle, "execution requires explicit approved decision")

    def test_new_file_snapshot_invalidates_old_input_digest(self):
        bundle = self.fixture()
        record(bundle, "submission")["files"][0]["sha256"] = digest("new mock sales bytes")
        self.rejects(bundle, "submission input digest differs")

    def test_new_input_version_cannot_reuse_old_approval(self):
        bundle = self.fixture()
        submission = record(bundle, "submission")
        submission["original_request"] += " MOCK material scope correction."
        submission["binding"].update(input_version=2, input_digest=input_digest(submission))
        self.rejects(bundle, "proposal/submission input_version mismatch")

    def test_mutated_task_is_not_the_approved_proposal(self):
        bundle = self.fixture()
        record(bundle, "task_proposal")["goal"] = "MOCK altered business goal"
        self.rejects(bundle, "proposal business payload digest mismatch")

    def test_new_proposal_digest_requires_new_approval_binding(self):
        bundle = self.fixture()
        proposal = record(bundle, "task_proposal")
        proposal["goal"] += " MOCK revised scope."
        proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
        self.rejects(bundle, "binding mismatch")

    def test_missing_source_stays_null_and_has_no_execution(self):
        bundle = self.fixture("missing_inputs")
        supplied = record(bundle, "submission")["files"][0]
        self.assertEqual((supplied["sha256"], supplied["size_bytes"]), (None, None))
        self.assertEqual(record(bundle, "task_proposal")["readiness"], "needs_inputs")
        self.assertFalse(any(r["kind"] in {"task_approval", "execution_contract"} for r in bundle["records"]))
        self.accepts(bundle)

    def test_inaccessible_source_cannot_claim_verified_hash(self):
        bundle = self.fixture("missing_inputs")
        record(bundle, "submission")["files"][0]["sha256"] = digest("substituted demo bytes")
        self.rejects(bundle, "is not of type 'null'")

    def test_no_demo_source_substitution_into_submission(self):
        bundle = self.fixture()
        record(bundle, "submission")["files"][0]["access"] = "inaccessible"
        file = record(bundle, "submission")["files"][0]
        file.update(sha256=None, size_bytes=None, access_reason="MOCK lost access")
        self.rejects(bundle, "proposal source not in actual accessible submission")

    def test_feature_generator_cannot_receive_holdout(self):
        bundle = self.fixture()
        feature = record(bundle, "feature_proposal")
        feature["generation"]["development_context_refs"] = [record(bundle, "preparation_result")["reserved_unseen_data_ref"]]
        self.rejects(bundle, "feature context: development input")

    def test_feature_definition_cannot_depend_on_future_rows(self):
        bundle = self.fixture()
        record(bundle, "feature_proposal")["definitions"][0]["source_refs"] = [record(bundle, "preparation_result")["reserved_unseen_data_ref"]]
        self.rejects(bundle, "feature source dependencies")

    def test_development_metadata_cannot_hide_future_availability(self):
        bundle = self.fixture()
        record(bundle, "preparation_result")["availability"][0]["latest_information_available_date"] = "2025-12-01"
        self.rejects(bundle, "development artifact contains future")

    def test_development_horizon_must_finish_by_cutoff(self):
        bundle = self.fixture()
        record(bundle, "initial_evaluation_result")["evaluation_plan"]["development_folds"][0]["target_end"] = "2025-12-01"
        self.rejects(bundle, "development target horizon")

    def test_baseline_and_candidate_must_share_population(self):
        bundle = self.fixture()
        record(bundle, "initial_evaluation_result")["initial_candidate"]["scores"][0]["population_id"] = "different-mock-population"
        self.rejects(bundle, "baseline/candidates must share")

    def test_initial_better_label_requires_actual_improvement(self):
        bundle = self.fixture()
        record(bundle, "initial_evaluation_result")["initial_candidate"]["scores"][0]["value"] = 15
        self.rejects(bundle, "initial comparison contradicts")

    def test_feature_generation_requires_initial_evaluation_ancestry(self):
        bundle = self.fixture()
        bundle["records"] = [r for r in bundle["records"] if r["kind"] != "initial_evaluation_result"]
        self.rejects(bundle, "LLM features require the initial baseline checkpoint")

    def test_saved_forecast_inputs_cannot_include_holdout(self):
        bundle = self.fixture()
        record(bundle, "evaluation_result")["frozen"]["forecast_input_refs"] = [record(bundle, "preparation_result")["reserved_unseen_data_ref"]]
        self.rejects(bundle, "saved forecast input contains unavailable/future")

    def test_final_result_cannot_replace_saved_forecast(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["november_30_forecast_ref"] = copy.deepcopy(record(bundle, "evaluation_result")["frozen"]["model_ref"])
        self.rejects(bundle, "saved November 30 forecast changed")

    def test_quantity_row_cannot_replace_saved_forecast(self):
        bundle = self.fixture()
        record(bundle, "quantity_result")["orders"][0]["forecast_ref"] = record(bundle, "evaluation_result")["frozen"]["model_ref"]
        self.rejects(bundle, "quantity row uses a different saved forecast")

    def test_final_false_pass_cannot_ignore_score_threshold(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["scores"][0]["value"] = 12
        self.rejects(bundle, "final outcome contradicts actual predeclared gates")

    def test_final_false_pass_cannot_ignore_observation_coverage(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["acceptance_rule"]["minimum_observation_count"] = 2
        self.rejects(bundle, "final outcome contradicts actual predeclared gates")

    def test_final_false_pass_cannot_ignore_required_check(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["checks"][0]["status"] = "fail"
        self.rejects(bundle, "final outcome contradicts actual predeclared gates")

    def test_holdout_cannot_be_accessed_before_freeze(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["holdout_accessed_at"] = "2026-10-17T09:00:00Z"
        self.rejects(bundle, "holdout accessed before freeze")

    def test_final_targets_cannot_extend_beyond_observed_holdout(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["scores"][0]["target_end_max"] = "2026-01-01"
        self.rejects(bundle, "outside reserved December period")

    def test_freeze_cannot_switch_to_unlisted_fallback_model(self):
        bundle = self.fixture()
        record(bundle, "evaluation_result")["frozen"]["selected_candidate_id"] = "mock-fallback"
        self.rejects(bundle, "frozen candidate was not an eligible shortlisted choice")

    def test_frozen_model_must_match_selected_candidate(self):
        bundle = self.fixture()
        evaluation = record(bundle, "evaluation_result")
        evaluation["frozen"]["model_ref"] = evaluation["candidates"][0]["model_ref"]
        self.rejects(bundle, "frozen model/features/preprocessing differ")

    def test_final_rule_cannot_be_relaxed_after_scores(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["acceptance_rule"]["metric_gates"][0]["threshold"] = 99
        self.rejects(bundle, "final acceptance rule differs")

    def test_freeze_cannot_bind_different_acceptance_rule(self):
        bundle = self.fixture()
        record(bundle, "evaluation_result")["frozen"]["acceptance_rule_ref"] = copy.deepcopy(record(bundle, "evaluation_result")["frozen"]["evaluation_plan_ref"])
        self.rejects(bundle, "frozen acceptance rule digest mismatch")

    def test_receipt_summary_cannot_be_subtracted_twice(self):
        bundle = self.fixture()
        row = record(bundle, "quantity_result")["orders"][0]
        row.update(raw_order_need=7, rounded_order_quantity=10, approved_order_quantity=10)
        self.rejects(bundle, "receipt summary must not be subtracted again")

    def test_moq_is_rounded_up_to_valid_multiple(self):
        bundle = self.fixture()
        for item in bundle["records"]:
            if item["kind"] in ("quantity_result", "report_draft"):
                row = item["orders"][0]
                row.update(minimum_positive_order_quantity=17, rounded_order_quantity=20)
                if row["approved_order_quantity"] is not None:
                    row["approved_order_quantity"] = 20
        self.accepts(bundle)
        record(bundle, "quantity_result")["orders"][0].update(rounded_order_quantity=17, approved_order_quantity=17)
        self.rejects(bundle, "quantity arithmetic inconsistent")

    def test_report_cannot_edit_approved_quantity_inputs(self):
        bundle = self.fixture()
        record(bundle, "report_draft")["orders"][0].update(forecast_quantity=25, raw_order_need=17, rounded_order_quantity=20, approved_order_quantity=20)
        self.rejects(bundle, "report altered approved quantities")

    def test_failure_paths_contain_no_valid_order_list(self):
        for name in ("validation_failed", "execution_failed"):
            with self.subTest(name=name):
                bundle = self.fixture(name)
                self.assertEqual(record(bundle, "report_draft")["orders"], [])
                self.accepts(bundle)
                record(bundle, "report_draft")["orders"] = copy.deepcopy(record(self.fixture(), "report_draft")["orders"])
                self.rejects(bundle, "expected to be empty")

    def test_runtime_error_codes_remain_distinct_and_typed(self):
        for code in ("plugin_unavailable", "unsupported_integration", "timeout", "invalid_code", "cancelled", "budget_exhausted"):
            with self.subTest(code=code):
                bundle = self.fixture("execution_failed")
                record(bundle, "stage_result")["failure"]["error_code"] = code
                record(bundle, "report_draft")["failure"]["error_code"] = code
                self.accepts(bundle)
        bundle = self.fixture("execution_failed")
        record(bundle, "stage_result")["failure"]["error_code"] = "made_up_failure"
        self.rejects(bundle, "not valid under any of the given schemas")

    def test_execution_failure_cannot_invent_measured_validation(self):
        bundle = self.fixture("execution_failed")
        report = record(bundle, "report_draft")
        report["outcome"] = "validation_failure"
        self.rejects(bundle, "measured validation failure needs actual failed-score evidence")

    def test_failed_independent_check_blocks_delivery(self):
        bundle = self.fixture()
        record(bundle, "output_verification")["claim_checks"][0]["status"] = "fail"
        self.rejects(bundle, "delivery blocked by failed/unavailable independent checks")

    def test_blocked_verifier_cannot_authorize_customer_response(self):
        bundle = self.fixture()
        verification = record(bundle, "output_verification")
        verification.update(decision="blocked", parent_decision=None, permitted_response={"kind": "no_customer_response", "text": "", "report_ref": None})
        self.accepts(bundle)
        verification["permitted_response"]["text"] = "Send the report anyway"
        self.rejects(bundle, "blocked verifier cannot authorize customer response")

    def test_mock_reference_cannot_be_reclassified_real(self):
        bundle = self.fixture()
        record(bundle, "execution_contract")["source_refs"][0]["provenance"] = "supplied"
        self.rejects(bundle, "reference provenance differs from bound artifact")

    def test_mock_evidence_cannot_be_promoted_to_real_acceptance(self):
        bundle = self.fixture()
        evidence = record(bundle, "evidence_record")
        evidence.update(evidence_mode="real", provenance="derived", mock_limitation=None)
        self.rejects(bundle, "all component fixture records must be mock")

    def test_one_bounded_defect_recheck_preserves_frozen_forecast(self):
        self.accepts(self.bounded_recheck())

    def test_defect_recheck_cannot_exceed_authorized_limit(self):
        bundle = self.bounded_recheck()
        final = record(bundle, "final_validation_result")
        second = copy.deepcopy(final["defect_rechecks"][0])
        second["attempt"] = 2
        final["defect_rechecks"].append(second)
        self.rejects(bundle, "defect recheck limit exhausted")

    def test_defect_recheck_cannot_change_saved_forecast(self):
        bundle = self.bounded_recheck()
        record(bundle, "final_validation_result")["defect_rechecks"][0]["november_30_forecast_ref"] = record(bundle, "evaluation_result")["frozen"]["model_ref"]
        self.rejects(bundle, "defect recheck changed the saved forecast")

    def test_defect_recheck_requires_parent_authorization(self):
        bundle = self.bounded_recheck()
        record(bundle, "final_validation_result")["defect_rechecks"][0]["parent_authorization"]["decision"] = "proceed"
        self.rejects(bundle, "defect recheck lacks sequential bounded parent authorization")

    def test_recheck_runtime_failure_does_not_require_invented_score(self):
        bundle = self.bounded_recheck()
        final = record(bundle, "final_validation_result")
        recheck = final["defect_rechecks"][0]
        recheck.update(outcome="execution_failure", scores=[])
        self.assertEqual(validate_record(final), [])
        recheck["outcome"] = "fail"
        self.assertTrue(validate_record(final), "Measured failure requires actual scores")

    def test_equal_or_worse_initial_result_requires_evidenced_review(self):
        for comparison, value in (("equal", 11), ("worse", 12)):
            with self.subTest(comparison=comparison):
                bundle = self.fixture()
                initial = record(bundle, "initial_evaluation_result")
                initial["comparison"] = comparison
                initial["initial_candidate"]["scores"][0]["value"] = value
                record(bundle, "evaluation_result")["candidates"][0]["scores"][0]["value"] = value
                initial["parent_decision"]["reason"] = "MOCK bounded review authorizes one finite feature attempt after " + comparison + " initial result"
                self.accepts(bundle)
                initial["parent_decision"]["evidence_refs"] = []
                self.rejects(bundle, "equal/worse initial result requires evidenced bounded parent review")

    def test_parent_review_cannot_be_indefinite(self):
        bundle = self.bounded_recheck()
        record(bundle, "execution_contract")["limits"]["max_parent_reviews"] = 1
        self.rejects(bundle, "parent review limit exhausted")

    def test_conflicting_duplicate_scores_cannot_hide_a_failure(self):
        bundle = self.fixture()
        final = record(bundle, "final_validation_result")
        failed_score = copy.deepcopy(final["scores"][0])
        failed_score["value"] = 999
        final["scores"].insert(0, failed_score)
        self.rejects(bundle, "duplicate scores identities")

    def test_forecast_origin_cannot_follow_scored_target(self):
        bundle = self.fixture()
        score = record(bundle, "final_validation_result")["scores"][0]
        score.update(forecast_origin_start="2026-01-01", forecast_origin_end="2026-01-01")
        self.rejects(bundle, "score origin/horizon chronology invalid")

    def test_shortlist_cannot_inflate_baseline_after_initial_gate(self):
        bundle = self.fixture()
        record(bundle, "evaluation_result")["baseline_scores"][0]["value"] = 999
        self.rejects(bundle, "shortlist changed the initial common baseline")

    def test_conflicting_availability_cannot_relabel_unseen_artifact(self):
        bundle = self.fixture()
        preparation = record(bundle, "preparation_result")
        conflict = copy.deepcopy(preparation["availability"][0])
        conflict["permitted_use"] = "reserved_unseen_evaluation"
        preparation["availability"].append(conflict)
        self.rejects(bundle, "conflicting availability declarations")

    def test_final_cannot_substitute_development_data_for_reserved_artifact(self):
        bundle = self.fixture()
        record(bundle, "final_validation_result")["reserved_unseen_data_ref"] = record(bundle, "preparation_result")["prepared_development_data_ref"]
        self.rejects(bundle, "final validation must use exact reserved unseen preparation artifact")

    def test_preparation_parent_stop_blocks_initial_evaluation(self):
        bundle = self.fixture()
        record(bundle, "preparation_result")["parent_decision"]["decision"] = "stop"
        self.rejects(bundle, "initial evaluation requires parent preparation authorization")

    def test_feature_parent_stop_blocks_comparison(self):
        bundle = self.fixture()
        record(bundle, "feature_result")["parent_decision"]["decision"] = "stop"
        self.rejects(bundle, "comparison requires parent feature authorization")

    def test_freeze_parent_stop_blocks_holdout_access(self):
        bundle = self.fixture()
        record(bundle, "evaluation_result")["parent_decision"]["decision"] = "stop"
        self.rejects(bundle, "holdout evaluation requires parent freeze authorization")

    def test_final_pass_does_not_bypass_parent_authorization(self):
        for decision in (None, "stop"):
            with self.subTest(decision=decision):
                bundle = self.fixture()
                final = record(bundle, "final_validation_result")
                if decision is None:
                    final["parent_review"] = None
                else:
                    final["parent_review"]["decision"] = decision
                self.rejects(bundle, "quantities require parent authorization of passed final validation")

    def test_forecast_reference_cannot_pose_as_independent_numerical_evidence(self):
        bundle = self.fixture()
        quantity = record(bundle, "quantity_result")
        wrong = quantity["november_30_forecast_ref"]
        quantity["independent_check_refs"] = [wrong]
        quantity["parent_decision"]["evidence_refs"] = [wrong]
        self.rejects(bundle, "independent quantity evidence must check exact candidate version")

    def test_numerical_evidence_must_check_exact_candidate_version(self):
        bundle = self.fixture()
        evidence = next(r for r in bundle["records"] if r["artifact_id"] == "mock-quantity-numerical-evidence")
        different_candidate = copy.deepcopy(next(r for r in bundle["records"] if r["kind"] == "quantity_result" and r["artifact_version"] == 1))
        different_candidate["artifact_id"] = "mock-other-quantity-candidate"
        bundle["records"].append(different_candidate)
        evidence["checked_artifacts"] = [record_ref(different_candidate)]
        self.rejects(bundle, "independent quantity evidence must check exact candidate version")

    def test_candidate_cannot_claim_approval_before_independent_check(self):
        bundle = self.fixture()
        candidate = next(r for r in bundle["records"] if r["kind"] == "quantity_result" and r["artifact_version"] == 1)
        candidate["orders"][0]["approved_order_quantity"] = 15
        self.rejects(bundle, "candidate quantities cannot already claim parent approval")

    def test_approval_cannot_change_candidate_body_even_when_arithmetic_matches(self):
        bundle = self.fixture()
        for kind in ("quantity_result", "report_draft"):
            record(bundle, kind)["orders"][0]["product_name"] = "MOCK changed display label"
        self.rejects(bundle, "quantity approval changed independently checked candidate content")

    def test_report_must_preserve_unresolved_exceptions(self):
        bundle = self.fixture()
        quantity = record(bundle, "quantity_result")
        exception = {"key": {"source_namespace": "mock-retail", "product_id": "MOCK-P002", "store_id": "MOCK-STORE"}, "reason": "MOCK missing operational stock for this extra key; no order claimed", "evidence_refs": [quantity["arithmetic_source_refs"][1]]}
        for item in bundle["records"]:
            if item["kind"] in {"quantity_result", "report_draft"}:
                item["exceptions"] = [copy.deepcopy(exception)]
        self.accepts(bundle)
        record(bundle, "report_draft")["exceptions"] = []
        self.rejects(bundle, "report must preserve unresolved quantity exceptions")

    @staticmethod
    def approve_changed_proposal_for_scenario(bundle):
        """Explicitly model a fresh consistent mock approval, not silent mutation."""
        proposal = record(bundle, "task_proposal")
        proposal["binding"]["proposal_version"] += 1
        proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
        for item in bundle["records"]:
            if item["kind"] != "submission":
                item["binding"] = copy.deepcopy(proposal["binding"])

    def test_pending_analytical_target_can_be_resolved_with_preparation_evidence(self):
        bundle = self.fixture()
        pending = {"status": "pending", "unresolved_gap_ids": ["mock-internal-target-investigation"]}
        record(bundle, "task_proposal")["target_policy"] = copy.deepcopy(pending)
        record(bundle, "execution_contract")["target_policy"] = copy.deepcopy(pending)
        preparation = record(bundle, "preparation_result")
        preparation["target_policy"]["policy_evidence_refs"] = preparation["quality_checks"][0]["evidence_refs"]
        self.approve_changed_proposal_for_scenario(bundle)
        self.accepts(bundle)
        preparation["target_policy"]["policy_evidence_refs"] = []
        self.rejects(bundle, "pending analytical target resolution requires versioned preparation evidence")

    def test_synthetic_zero_scenario_requires_explicit_approved_assumption(self):
        bundle = self.fixture()
        marker = "MOCK approved scenario assumption only: unobserved key-days represent zero solely in this hypothetical demonstration; no claim that the actual source is complete."
        assumption_ref = {"artifact_id": "mock-zero-assumption", "version": 1, "sha256": digest(marker), "provenance": "mock"}
        bundle["mock_artifacts"].append({"ref": assumption_ref, "role": "disclosed_synthetic_assumption", "content_marker": marker, "availability": None})
        assumption = {"assumption_id": "mock-explicit-zero-scenario", "classification": "synthetic_assumption", "statement": marker, "status": "confirmed", "source_refs": [assumption_ref]}
        proposal = record(bundle, "task_proposal")
        proposal["assumptions"].append(assumption)
        record(bundle, "execution_contract")["source_assumptions"] = copy.deepcopy(proposal["assumptions"])
        for kind in ("task_proposal", "execution_contract", "preparation_result"):
            record(bundle, kind)["target_policy"].update(missing_date_treatment="zero_under_disclosed_synthetic_assumption", zero_assumption_ref=assumption_ref)
        self.approve_changed_proposal_for_scenario(bundle)
        self.accepts(bundle)
        record(bundle, "execution_contract")["source_assumptions"].pop()
        proposal["assumptions"].pop()
        self.approve_changed_proposal_for_scenario(bundle)
        self.rejects(bundle, "synthetic missing-date zero treatment requires approved disclosed assumption")

    def test_synthetic_zero_scenario_without_assumption_ref_is_schema_invalid(self):
        bundle = self.fixture()
        record(bundle, "preparation_result")["target_policy"].update(missing_date_treatment="zero_under_disclosed_synthetic_assumption", zero_assumption_ref=None)
        self.rejects(bundle, "zero_assumption_ref")

    def test_stage_request_cannot_start_without_parent_permission(self):
        bundle = self.fixture("approved_execution")
        record(bundle, "stage_request")["parent_authorization"]["decision"] = "stop"
        self.rejects(bundle, "stage request requires parent permission for exact stage")

    def test_stage_request_cannot_exceed_attempt_limit(self):
        bundle = self.fixture("approved_execution")
        record(bundle, "stage_request")["attempt"] = 3
        record(bundle, "stage_result")["attempt"] = 3
        self.rejects(bundle, "stage request exceeds approved attempt limit")

    def test_stage_request_deadline_cannot_exceed_remaining_budget(self):
        bundle = self.fixture("approved_execution")
        record(bundle, "stage_request")["deadline"] = "2026-10-17T10:00:00Z"
        self.rejects(bundle, "stage request deadline exceeds remaining execution bound")

    def test_stage_request_cannot_expand_approved_remaining_limits(self):
        bundle = self.fixture("approved_execution")
        record(bundle, "stage_request")["remaining_limits"]["max_candidates"] = 999
        self.rejects(bundle, "stage request expands approved execution bounds")

    def test_stage_output_namespace_rejects_path_traversal(self):
        bundle = self.fixture("approved_execution")
        record(bundle, "stage_request")["output_namespace"] += "/../escape"
        self.rejects(bundle, "stage output namespace must stay within bound task/run")

    def test_stage_feature_context_cannot_release_holdout(self):
        bundle = self.fixture()
        request = copy.deepcopy(record(self.fixture("approved_execution"), "stage_request"))
        request["stage"] = "llm_features"
        request["parent_authorization"]["checkpoint"] = "llm_features"
        request["released_input_refs"] = [record(bundle, "preparation_result")["reserved_unseen_data_ref"]]
        bundle["records"].append(request)
        self.rejects(bundle, "stage released inputs: development input")

    def test_stage_measured_failure_requires_actual_final_scores(self):
        bundle = self.fixture("approved_execution")
        stage = record(bundle, "stage_result")
        stage.update(outcome="validation_failed", final_validation_result_ref=None)
        self.assertTrue(validate_record(stage), "A measured failure must reference actual final validation")
        stage["final_validation_result_ref"] = record_ref(record(bundle, "execution_contract"))
        self.assertEqual(validate_record(stage), [])
        self.rejects(bundle, "stage measured failure must bind failed final validation scores")

    def test_stage_missing_inputs_or_material_facts_requires_explicit_gaps(self):
        for outcome in ("needs_inputs", "needs_material_facts"):
            with self.subTest(outcome=outcome):
                bundle = self.fixture("approved_execution")
                stage = record(bundle, "stage_result")
                stage.update(outcome=outcome, output_refs=[], gaps=[])
                self.assertTrue(validate_record(stage), "Missing-input/fact state requires actionable gap")
                stage["gaps"] = [{"gap_id": "mock-material-gap", "description": "MOCK missing usable-stock snapshot", "material": True, "blocks": ["quantities"], "request_to_user": "Provide the actual usable-stock snapshot and its as-of date."}]
                self.assertEqual(validate_record(stage), [])
                self.accepts(bundle)

    def test_stage_can_dispatch_when_only_unrelated_budgets_are_exhausted(self):
        bundle = self.fixture("approved_execution")
        request = record(bundle, "stage_request")
        request["remaining_limits"].update(max_candidates=0, max_llm_feature_definitions=0,
                                           max_parent_reviews=0, max_defect_rechecks=0,
                                           max_stage_attempts=1, max_execution_seconds=15)
        self.accepts(bundle)

    def test_stage_cannot_dispatch_without_remaining_attempts_or_time(self):
        for field in ("max_stage_attempts", "max_execution_seconds"):
            with self.subTest(exhausted=field):
                bundle = self.fixture("approved_execution")
                record(bundle, "stage_request")["remaining_limits"][field] = 0
                self.rejects(bundle, "stage cannot dispatch with exhausted attempts or time")

    def test_feature_stage_cannot_dispatch_with_exhausted_feature_budget(self):
        bundle = self.fixture()
        request = copy.deepcopy(record(self.fixture("approved_execution"), "stage_request"))
        request["stage"] = "llm_features"
        request["parent_authorization"]["checkpoint"] = "llm_features"
        request["released_input_refs"] = [record(bundle, "preparation_result")["prepared_development_data_ref"]]
        bundle["records"].append(request)
        self.accepts(bundle)
        request["remaining_limits"]["max_llm_feature_definitions"] = 0
        self.rejects(bundle, "feature stage cannot dispatch with exhausted feature budget")

    def test_model_stages_cannot_dispatch_with_exhausted_candidate_budget(self):
        for stage in ("initial_baseline_evaluation", "comparison_and_freeze"):
            with self.subTest(stage=stage):
                bundle = self.fixture()
                request = copy.deepcopy(record(self.fixture("approved_execution"), "stage_request"))
                request["stage"] = stage
                request["parent_authorization"]["checkpoint"] = stage
                request["released_input_refs"] = [record(bundle, "preparation_result")["prepared_development_data_ref"]]
                bundle["records"].append(request)
                self.accepts(bundle)
                request["remaining_limits"]["max_candidates"] = 0
                self.rejects(bundle, "model stage cannot dispatch with exhausted candidate budget")

    def test_stage_deadline_requires_positive_remaining_duration(self):
        bundle = self.fixture("approved_execution")
        request = record(bundle, "stage_request")
        request["deadline"] = request["issued_at"]
        self.rejects(bundle, "stage request deadline exceeds remaining execution bound")


if __name__ == "__main__":
    unittest.main()
