"""Generate five component-contract examples; no real analytics or dataset project."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from suiroai.contracts.validation import VERSION, digest, input_digest, proposal_digest, validate_bundle

ROOT = Path(__file__).resolve().parent
NOTICE = "MOCK COMPONENT FIXTURE ONLY: all files, identities, approvals, models, scores, checks and quantities are invented interface examples. No analytical pipeline ran; no customer facts or acceptance evidence are established."
KEY = {"source_namespace": "mock-retail", "product_id": "MOCK-P001", "store_id": "MOCK-STORE"}
STAGES = ["approved_execution", "preparation", "initial_baseline_evaluation", "llm_features", "comparison_and_freeze", "final_validation", "recommendations", "output_verification"]
TEMPORAL = {
    "as_of_date": "2025-11-30", "date_interpretation": "source_calendar_date",
    "initial_development_start": "2022-01-01", "initial_development_end": "2024-12-31",
    "rolling_validation_start": "2025-01-01", "development_target_end_cutoff": "2025-11-30",
    "reserved_unseen_start": "2025-12-01", "reserved_unseen_end": "2025-12-31",
    "development_context_access": "development_artifacts_only", "every_development_horizon_finishes_by_cutoff": True,
    "score_fully_observed_horizons_only": True, "freeze_before_holdout_access": True,
    "forecast_as_of_date": "2025-11-30", "december_must_not_change_saved_forecast": True,
}
RULE = {
    "rule_id": "mock-mae-cap", "version": 1, "declared_at": "2026-10-17T09:00:15Z",
    "metric_gates": [{"metric_id": "mock-mae", "aggregation": "macro_mean_over_mock_keys", "population_id": "mock-holdout-population", "direction": "upper_bound", "threshold": 10, "unit": "product_unit"}],
    "required_check_ids": ["fully_observed"], "all_gates_required": True, "minimum_observation_count": 1,
}


def timestamp(minute):
    # Fifteen-second mock ticks keep the entire example inside its 300s limit.
    seconds = minute * 15
    return f"2026-10-17T09:{seconds // 60:02d}:{seconds % 60:02d}Z"


def ref(record):
    return {"artifact_id": record["artifact_id"], "version": record["artifact_version"], "sha256": digest(record), "provenance": "mock"}


class Builder:
    def __init__(self, name):
        self.name = name
        self.binding = {"task_id": "mock-retail-restocking", "task_version": 1, "input_version": 1, "input_digest": "0" * 64}
        self.records = []
        self.artifacts = []

    def external(self, name, role, marker=None, use=None):
        marker = marker if marker is not None else f"MOCK ONLY {name}; no actual analytical artifact exists."
        artifact_ref = {"artifact_id": "mock-" + name, "version": 1, "sha256": digest(marker), "provenance": "mock"}
        availability = self.available(artifact_ref, use) if use else None
        self.artifacts.append({"ref": artifact_ref, "role": role, "content_marker": marker, "availability": availability})
        return artifact_ref

    @staticmethod
    def available(artifact_ref, use):
        unseen = use == "reserved_unseen_evaluation"
        operations = use == "as_of_operations"
        return {"artifact_ref": artifact_ref, "permitted_use": use,
                "earliest_event_date": "2025-12-01" if unseen else "2025-11-30" if operations else "2022-01-01",
                "latest_event_date": "2025-12-31" if unseen else "2025-11-30",
                "latest_information_available_date": "2025-12-31" if unseen else "2025-11-30",
                "event_time_column": "Order_Date", "availability_time_column": "mock_available_date",
                "contains_post_cutoff_rows": unseen}

    def record(self, kind, artifact_version=1, artifact_id=None, **payload):
        record = {"kind": kind, "schema_version": VERSION, "artifact_id": artifact_id or "mock-" + kind.replace("_", "-"),
                  "artifact_version": artifact_version, "provenance": "mock", "binding": copy.deepcopy(self.binding)}
        if kind not in ("submission", "task_proposal", "task_approval"):
            record["run_id"] = "mock-run-1"
        record.update(copy.deepcopy(payload))
        self.records.append(record)
        return record

    def check(self, name, status="pass", expected="Mock check expected to pass", actual="Mock check passes"):
        typed = {"check_id": name, "requirement_id": "mock-" + name, "status": status,
                 "expected": expected, "actual": actual, "evidence_refs": [], "verifier": "mock-independent-checker"}
        check_ref = self.external("check-" + name, "check", typed)
        return {**typed, "evidence_refs": [check_ref]}, check_ref

    @staticmethod
    def parent(checkpoint, refs, minute=20, decision="proceed"):
        return {"checkpoint": checkpoint, "decision": decision, "actor": "mock-parent", "decided_at": timestamp(minute),
                "reason": "MOCK checkpoint decision for component interface demonstration only.", "evidence_refs": refs}

    @staticmethod
    def finding(statement, refs, limitation=False):
        return {"finding_id": "mock-finding", "statement": statement,
                "classification": "material_limitation" if limitation else "verified_finding", "evidence_refs": refs, "audience": "final_report"}

    @staticmethod
    def score(value, holdout=False):
        return {"metric_id": "mock-mae", "value": value, "unit": "product_unit",
                "population_id": "mock-holdout-population" if holdout else "mock-development-population", "observation_count": 1,
                "forecast_origin_start": "2025-11-30" if holdout else "2025-10-31",
                "forecast_origin_end": "2025-11-30" if holdout else "2025-10-31",
                "target_end_max": "2025-12-14" if holdout else "2025-11-14"}

    def initial(self, missing=False):
        files, sources = [], []
        if missing:
            files = [{"file_id": "mock-unavailable-sales", "original_name": "mock-unavailable-sales.csv", "supplied_location": "mock://unavailable/sales.csv", "source_role": "transactions", "source_namespace": "mock-retail", "provenance": "mock", "access": "inaccessible", "sha256": None, "size_bytes": None, "access_reason": "MOCK file link is inaccessible; no replacement dataset is supplied."}]
        else:
            for name, source_role in [("sales", "transactions"), ("dictionary", "dictionary"), ("stock", "usable_stock"), ("receipts", "inbound_ledger"), ("policy", "ordering_policy")]:
                marker = f"MOCK supplied {name} file; {NOTICE}"
                operational_markers = {
                    "stock": {"notice": NOTICE, "rows": [{"Product_ID": "MOCK-P001", "Store_ID": "MOCK-STORE", "Snapshot_Date": "2025-11-30", "Usable_On_Hand_Qty": 5, "On_Order_Qty": 5, "Open_Order_Ledger_Complete": True, "Quantity_Unit": "product_unit", "Provenance": "mock"}]},
                    "receipts": {"notice": NOTICE, "rows": [{"PO_Line_ID": "MOCK-PO-1", "Product_ID": "MOCK-P001", "Store_ID": "MOCK-STORE", "Order_Date": "2025-11-30", "Expected_Arrival_Date": "2025-12-07", "Incoming_Qty": 5, "Quantity_Unit": "product_unit", "Provenance": "mock"}]},
                    "policy": {"notice": NOTICE, "rows": [{"Product_ID": "MOCK-P001", "Store_ID": "MOCK-STORE", "Effective_Date": "2025-11-30", "Supplier_Lead_Time_Days": 7, "Review_Period_Days": 7, "Order_Multiple_Qty": 5, "Minimum_Order_Qty": 5, "Safety_Stock_Qty": 2, "Quantity_Unit": "product_unit", "Provenance": "mock"}]},
                }
                marker = operational_markers.get(name, marker)
                source_ref = self.external(name, "source_" + source_role, marker, "as_of_operations" if name in ("stock", "receipts", "policy") else None)
                sources.append(source_ref)
                files.append({"file_id": source_ref["artifact_id"], "original_name": f"mock-{name}.csv", "supplied_location": f"mock://input/{name}.csv", "source_role": source_role, "source_namespace": "mock-retail", "provenance": "mock", "access": "accessible", "sha256": source_ref["sha256"], "size_bytes": len(json.dumps(marker, ensure_ascii=False, separators=(",", ":")).encode()), "access_reason": None})
        submission = self.record("submission", original_request="MOCK request: illustrate one restocking list for MOCK-P001 at MOCK-STORE.", files=files, received_at=timestamp(0))
        self.binding["input_digest"] = input_digest(submission)
        submission["binding"] = copy.deepcopy(self.binding)
        gap = {"gap_id": "missing-sales", "description": "MOCK sales file is inaccessible; quantities cannot be inspected.", "material": True, "blocks": ["approval", "execution", "quantities", "report"], "request_to_user": "Provide an accessible sales file and source dictionary; no demo substitution will occur."}
        target = {"status": "defined", "policy_id": "mock-observed-fulfilled-quantity", "quantity_unit": "product_unit", "aggregation_grain": "product_store_day", "target_measure": "MOCK hypothetical fulfilled transaction quantity on explicitly observed days; not unconstrained customer demand", "included_order_statuses": ["completed"], "returns_treatment": "MOCK exclude flagged returns; not a customer fact", "nonpositive_quantity_treatment": "MOCK quarantine pending source investigation", "duplicate_treatment": "MOCK exact duplicate excess removed with source-row lineage", "missing_date_treatment": "explicit_observation_mask", "extract_completeness": "unverified", "completeness_evidence_refs": [], "policy_evidence_refs": sources[:2], "zero_assumption_ref": None}
        assumption = {"assumption_id": "mock-policy-assumption", "classification": "synthetic_assumption", "statement": "MOCK target and operational numbers are hypothetical contract examples, not customer facts; no real-source daily completeness claim.", "status": "confirmed", "source_refs": sources}
        proposal = self.record("task_proposal", submission_ref=ref(submission), goal="MOCK single retail replenishment illustration only.", output="one_restocking_list_and_final_report_or_verified_failure_explanation", source_refs=sources, readiness="needs_inputs" if missing else "ready", assumptions=[] if missing else [assumption], gaps=[gap] if missing else [], target_policy={"status": "pending", "unresolved_gap_ids": [gap["gap_id"]]} if missing else target, temporal_plan=TEMPORAL, acceptance_rule={"status": "pending", "unresolved_gap_ids": [gap["gap_id"]]} if missing else RULE)
        self.binding.update({"proposal_version": 1, "proposal_digest": proposal_digest(proposal)})
        proposal["binding"] = copy.deepcopy(self.binding)
        if missing:
            return None, sources
        approval = self.record("task_approval", proposal_ref=ref(proposal), decision="approved", actor="mock-user", decided_at=timestamp(2), comment="MOCK approval, not a real customer authorization.")
        execution = self.record("execution_contract", approval_ref=ref(approval), proposal_ref=ref(proposal), source_refs=sources,
                                allowed_actions=["inspect", "clean", "join", "aggregate", "eda", "materialize_features", "train", "evaluate", "freeze", "calculate_restocking", "draft_report", "verify_outputs"],
                                limits={"max_candidates": 2, "max_llm_feature_definitions": 2, "max_defect_rechecks": 1, "max_parent_reviews": 2, "max_execution_seconds": 300, "max_stage_attempts": 2},
                                required_checkpoints=STAGES, temporal_plan=TEMPORAL, target_policy=target, acceptance_rule=RULE, source_assumptions=[assumption], quantity_unit="product_unit", inbound_ledger_policy="complete_synthetic_ledger_absence_is_zero", inbound_summary_policy="reconcile_receipt_sum_never_double_count", synthetic_operational_source_refs=sources[2:])
        return execution, sources

    def request_execution_stage(self, execution, sources):
        return self.record("stage_request", execution_contract_ref=ref(execution), stage="approved_execution", attempt=1,
                           parent_authorization=self.parent("approved_execution", [execution["approval_ref"]], 3),
                           released_input_refs=sources, remaining_limits=execution["limits"], issued_at=timestamp(3),
                           deadline=timestamp(4), output_namespace="artifacts/mock-retail-restocking/mock-run-1/approved-execution/attempt-1")

    def feature_definition(self, source, additional=False):
        return {"feature_id": "mock-lagged-mean" if additional else "mock-lag", "name": "MOCK lagged observed quantity mean" if additional else "MOCK previous observed quantity", "expression": "mean(quantity for observed rows strictly before origin)" if additional else "last(quantity where event_date < origin and available_date <= origin)", "source_refs": [source], "event_time_basis": "mock source calendar date", "availability_time_basis": "mock_available_date <= origin", "minimum_lag_calendar_days": 1, "timing_rule": "MOCK observed rows only; no automatic zero filling; every information date <= origin", "uses_only_information_available_at_origin": True, "fit_scope": "training_fold_only", "rationale": "MOCK LLM hypothesis about previous observed quantities; no measured real-world claim."}

    def analysis(self, execution, sources, failed=False):
        execution_ref = ref(execution)
        dev = self.external("prepared-development", "development_data", use="development")
        holdout = self.external("reserved-unseen", "reserved_unseen_data", use="reserved_unseen_evaluation")
        initial_features = self.external("initial-features", "feature_set", use="development")
        feature_definition = self.feature_definition(dev)
        quality, quality_ref = self.check("preparation-quality")
        lineage = {"output_ref": dev, "input_refs": [sources[0]], "transformation_id": "mock-dedup-mask", "description": "MOCK preparation lineage only; no rows actually transformed.", "row_lineage_ref": None, "preserved_raw_hashes": [sources[0]["sha256"]]}
        prep = self.record("preparation_result", execution_contract_ref=execution_ref, prepared_development_data_ref=dev, reserved_unseen_data_ref=holdout, initial_feature_set_ref=initial_features, initial_feature_definitions=[feature_definition], target_policy=execution["target_policy"], lineage=[lineage], join_checks=[], quality_checks=[quality], availability=[self.available(dev, "development"), self.available(initial_features, "development"), self.available(holdout, "reserved_unseen_evaluation")], development_context_allowlist=[dev, initial_features], findings=[self.finding("MOCK observation mask preserves unknown dates; this asserts no real-source completeness.", [quality_ref], True)], parent_decision=self.parent("preparation", [quality_ref], 4))
        population = self.external("development-population", "development_population", use="development")
        full_dev, full_dev_ref = self.check("development-fully-observed")
        plan = {"plan_id": "mock-common-plan", "version": 1, "declared_at": timestamp(3), "temporal_plan": TEMPORAL, "primary_metric_id": "mock-mae", "metric_definitions": [{"metric_id": "mock-mae", "formula": "mean(abs(actual - predicted)) on explicitly observed mock horizons", "unit": "product_unit", "aggregation": "macro_mean_over_mock_keys", "direction": "lower_is_better", "tie_tolerance": 0}], "development_folds": [{"fold_id": "mock-fold", "training_end": "2025-10-31", "forecast_origin": "2025-10-31", "target_start": "2025-11-01", "target_end": "2025-11-14", "population_ref": population}], "common_population_ref": population, "fully_observed_horizon_check_ref": full_dev_ref}
        plan_ref = self.external("evaluation-plan", "evaluation_plan", plan)
        rule_ref = self.external("acceptance-rule", "acceptance_rule", RULE)
        initial_model = self.external("initial-model", "model")
        preprocessing = self.external("preprocessing", "preprocessing", use="development")
        initial_candidate = {"candidate_id": "mock-initial", "model_ref": initial_model, "feature_set_ref": initial_features, "preprocessing_ref": preprocessing, "scores": [self.score(9)], "eligible_for_selection": True, "evidence_refs": [full_dev_ref]}
        initial = self.record("initial_evaluation_result", execution_contract_ref=execution_ref, preparation_result_ref=ref(prep), evaluation_plan=plan, baseline_id="mock-baseline", baseline_scores=[self.score(11)], initial_candidate=initial_candidate, comparison="better", parent_decision=self.parent("initial_baseline_evaluation", [full_dev_ref], 5))
        prompt = self.external("llm-prompt", "llm_prompt", use="development")
        response = self.external("llm-response", "llm_response", use="development")
        extra_definition = self.feature_definition(dev, True)
        feature_proposal = self.record("feature_proposal", execution_contract_ref=execution_ref, preparation_result_ref=ref(prep), initial_evaluation_ref=ref(initial), generation={"generation_kind": "llm_generated", "model_id": "MOCK-LLM-NO-CALL-MADE", "prompt_ref": prompt, "response_ref": response, "generated_at": timestamp(6), "development_context_refs": [dev, initial_features], "unrestricted_raw_future_access": False}, definitions=[extra_definition])
        extra_features = self.external("llm-features", "feature_set", use="development")
        feature_check, feature_check_ref = self.check("feature-timing")
        feature_result = self.record("feature_result", feature_proposal_ref=ref(feature_proposal), materialized_feature_set_ref=extra_features, definitions=[extra_definition], lineage=[{**lineage, "output_ref": extra_features, "input_refs": [dev], "transformation_id": "mock-lagged-mean"}], availability=[self.available(extra_features, "development")], validation_checks=[feature_check], findings=[self.finding("MOCK additional feature uses only available prior observations.", [feature_check_ref])], parent_decision=self.parent("llm_features", [feature_check_ref], 7))
        selected_model = self.external("selected-model", "model")
        selected = {"candidate_id": "mock-with-llm-feature", "model_ref": selected_model, "feature_set_ref": extra_features, "preprocessing_ref": preprocessing, "scores": [self.score(8)], "eligible_for_selection": True, "evidence_refs": [feature_check_ref, full_dev_ref]}
        forecast = self.external("november-30-forecast", "november_30_forecast", {"notice": NOTICE, "as_of_date": "2025-11-30", "key": KEY, "horizon_start": "2025-12-01", "horizon_end": "2025-12-14", "quantity_unit": "product_unit", "forecast_quantity": 20}, use="as_of_operations")
        frozen = {"freeze_id": "mock-freeze", "frozen_at": timestamp(8), "selected_candidate_id": selected["candidate_id"], "model_ref": selected_model, "feature_set_ref": extra_features, "preprocessing_ref": preprocessing, "evaluation_plan_ref": plan_ref, "acceptance_rule_ref": rule_ref, "development_input_refs": [dev, extra_features], "november_30_forecast_ref": forecast, "forecast_as_of_date": "2025-11-30", "forecast_input_refs": [dev, extra_features], "no_reserved_outcomes_in_fit_selection_or_forecast": True}
        frozen_ref = self.external("freeze-manifest", "frozen_result", frozen)
        evaluation = self.record("evaluation_result", execution_contract_ref=execution_ref, preparation_result_ref=ref(prep), llm_feature_result_ref=ref(feature_result), evaluation_plan=plan, baseline_id="mock-baseline", baseline_scores=[self.score(11)], initial_candidate_id=initial_candidate["candidate_id"], candidates=[initial_candidate, selected], selection_rule="MOCK minimum development MAE over identical population; maximum two candidates; choose before holdout access", comparison_checks=[full_dev, feature_check], frozen=frozen, findings=[self.finding("MOCK additional feature candidate has development MAE 8 versus baseline 11; not real measured results.", [full_dev_ref, feature_check_ref])], parent_decision=self.parent("comparison_and_freeze", [frozen_ref], 8))
        fully_observed, fully_observed_ref = self.check("fully_observed", expected="MOCK evaluated horizon is fully observed and ends by December 31", actual="MOCK November 30 origin, December 1 through December 14 target, observed count 1")
        acceptance_check, acceptance_check_ref = self.check("acceptance-score", "fail" if failed else "pass", expected="MOCK MAE <= 10", actual="MOCK MAE = 12" if failed else "MOCK MAE = 8")
        final = self.record("final_validation_result", execution_contract_ref=execution_ref, evaluation_result_ref=ref(evaluation), frozen_result_ref=frozen_ref, november_30_forecast_ref=forecast, acceptance_rule=RULE, reserved_unseen_data_ref=holdout, scores=[self.score(12 if failed else 8, True)], checks=[fully_observed, acceptance_check], outcome="fail" if failed else "pass", parent_review=self.parent("final_validation", [fully_observed_ref, acceptance_check_ref], 10, "confirmed_failure" if failed else "proceed"), defect_rechecks=[], findings=[self.finding("MOCK reserved evaluation fails its declared MAE cap; no fallback or tuning." if failed else "MOCK reserved evaluation passes its declared MAE cap.", [fully_observed_ref, acceptance_check_ref])], holdout_accessed_at=timestamp(9))
        return evaluation, frozen_ref, forecast, final

    def terminal(self, execution, sources, final=None, frozen_ref=None, forecast=None, capability=None):
        failed_validation = final is not None and final["outcome"] == "fail"
        runtime_failure = capability is not None
        successful = not failed_validation and not runtime_failure
        report_outcome = "execution_failure" if runtime_failure else "validation_failure" if failed_validation else "success"
        evidence_ref = ref(capability) if runtime_failure else ref(final)
        arithmetic_checks, orders, arithmetic_sources, quantity_ref = [], [], [], None
        failure = None
        if successful:
            arithmetic_sources = [forecast, *sources[2:]]
            arithmetic_check, arithmetic_ref = self.check("quantity-arithmetic", expected="MOCK raw need = 20+2-5-5 = 12; ceil(max(0,12)/5)*5 = 15; receipt summary counted once", actual="MOCK candidate=15 product_unit; independent arithmetic agrees")
            arithmetic_checks = [arithmetic_check]
            order = {"key": KEY, "quantity_unit": "product_unit", "arithmetic_input_refs": arithmetic_sources, "forecast_ref": forecast, "forecast_horizon_start": "2025-12-01", "forecast_horizon_end": "2025-12-14", "forecast_quantity": 20, "usable_on_hand_quantity": 5, "on_order_summary_quantity": 5, "eligible_receipt_quantity": 5, "supplier_lead_calendar_days": 7, "review_period_calendar_days": 7, "safety_stock_quantity": 2, "order_multiple": 5, "minimum_positive_order_quantity": 5, "raw_order_need": 12, "rounded_order_quantity": 15, "approved_order_quantity": None, "evidence_refs": [arithmetic_ref]}
            candidate = self.record("quantity_result", execution_contract_ref=ref(execution), final_validation_ref=ref(final), frozen_result_ref=frozen_ref, november_30_forecast_ref=forecast, candidate_quantity_ref=None, arithmetic_source_refs=arithmetic_sources, orders=[order], exceptions=[], arithmetic_checks=arithmetic_checks, independent_check_refs=[], parent_decision=None)
            numerical_check = {**arithmetic_check, "verifier": "mock-independent-numerical"}
            numerical_evidence = self.record("evidence_record", artifact_id="mock-quantity-numerical-evidence", requirement_id="mock-independent-quantity-arithmetic", requirement_source="DSC-24 candidate quantity verification interface", checked_artifacts=[ref(candidate)], check=numerical_check, evidence_mode="mock", verifier_decision="accepted", verifier="mock-independent-numerical", verified_at=timestamp(11), mock_limitation=NOTICE)
            # The later immutable version approves exactly the independently
            # checked candidate; no artifact points forward to its own evidence.
            order["approved_order_quantity"] = 15
            quantity = self.record("quantity_result", artifact_version=2, execution_contract_ref=ref(execution), final_validation_ref=ref(final), frozen_result_ref=frozen_ref, november_30_forecast_ref=forecast, candidate_quantity_ref=ref(candidate), arithmetic_source_refs=arithmetic_sources, orders=[order], exceptions=[], arithmetic_checks=arithmetic_checks, independent_check_refs=[ref(numerical_evidence)], parent_decision=self.parent("recommendations", [ref(numerical_evidence)], 12))
            quantity_ref = ref(quantity)
            orders = [{**order, "approved_order_quantity": 15}]
            text = "MOCK REPORT ONLY: illustrative order MOCK-P001 / MOCK-STORE: 15 product units. Mock holdout MAE 8 passes mock cap 10; mock LLM feature improves development MAE 9 to 8 (baseline 11). All stock, policies, metrics and quantities are invented. Missing source-date completeness is unresolved; this is not a verified purchasing instruction."
        else:
            failure = {"stage": "adapter_execution" if runtime_failure else "final_validation", "reason": "MOCK required OpenAI Data host integration is unavailable." if runtime_failure else "MOCK measured MAE 12 exceeds the predeclared cap 10; parent confirmed failure, no defect found and no fallback.", "scope_limitation": "This MVP could not produce a reliable solution with the supplied data/scope in this mock run; this does not establish universal impossibility.", "evidence_refs": [evidence_ref]}
            if runtime_failure:
                failure["error_code"] = "plugin_unavailable"
                stage = self.record("stage_result", execution_contract_ref=ref(execution), stage_request_ref=ref(self.execution_stage_request), stage="approved_execution", attempt=1, gaps=[], final_validation_result_ref=None, outcome="execution_failed", output_refs=[], evidence_refs=[evidence_ref], parent_decision=self.parent("approved_execution", [evidence_ref], 4, "stop"), failure=failure)
                evidence_ref = ref(stage)
            text = "MOCK FAILURE EXPLANATION ONLY: " + failure["reason"] + " " + failure["scope_limitation"] + " No valid restocking list is available."
        report = self.record("report_draft", execution_contract_ref=ref(execution), outcome=report_outcome, final_validation_ref=ref(final) if final else None, frozen_result_ref=frozen_ref, november_30_forecast_ref=forecast, quantity_result_ref=quantity_ref, arithmetic_source_refs=arithmetic_sources, orders=orders, exceptions=[], arithmetic_checks=arithmetic_checks, claims=[{"claim_id": "mock-terminal-claim", "statement": text, "evidence_refs": [evidence_ref] + ([quantity_ref] if quantity_ref else [])}], findings=[self.finding("MOCK component examples cannot establish analytical or integration acceptance.", [evidence_ref], True)], customer_draft=text, failure=failure, parent_decision=self.parent("recommendations" if successful else "final_validation" if failed_validation else "approved_execution", [evidence_ref], 12, "proceed" if successful else "stop"))
        claim_check, claim_check_ref = self.check("report-claims", expected="MOCK customer claims match bound evidence and honest terminal outcome", actual="MOCK claim audit agrees; no universally impossible assertion")
        binding_check, binding_check_ref = self.check("input-version-binding", expected="MOCK approval, inputs, artifacts and report have identical approved bindings", actual="MOCK binding comparison agrees")
        self.record("output_verification", report_draft_ref=ref(report), independent_verifier="mock-independent-output-verifier", independence_basis="MOCK separate verifier recomputes arithmetic and resolves claims from immutable refs; no actual verification pipeline ran", arithmetic_checks=arithmetic_checks, claim_checks=[claim_check], binding_checks=[binding_check], decision="delivery_allowed", parent_decision=self.parent("output_verification", [claim_check_ref, binding_check_ref], 13), permitted_response={"kind": "final_report" if successful else "failure_explanation", "text": text, "report_ref": ref(report)})
        self.record("evidence_record", requirement_id="mock-terminal-evidence-binding", requirement_source="DSC-24 interface fixture; not customer acceptance", checked_artifacts=[ref(report)], check=claim_check, evidence_mode="mock", verifier_decision="accepted", verifier="mock-independent-output-verifier", verified_at=timestamp(13), mock_limitation=NOTICE)

    def build(self):
        execution, sources = self.initial(self.name == "missing_inputs")
        if self.name == "execution_failed":
            self.execution_stage_request = self.request_execution_stage(execution, sources)
            capability_check, capability_ref = self.check("runtime-capability", "unavailable", "MOCK supported OpenAI Data host integration must be demonstrated", "MOCK host integration unavailable; no external Data API, Code Interpreter substitution or custom runtime is assumed")
            capability = self.record("capability_result", status="unavailable", host="MOCK unsupported host", interface="MOCK required supported OpenAI Data integration", demonstrated=False, evidence_refs=[capability_ref], checks=[capability_check])
            self.terminal(execution, sources, capability=capability)
        elif self.name in ("successful_analysis", "validation_failed"):
            _, frozen_ref, forecast, final = self.analysis(execution, sources, self.name == "validation_failed")
            self.terminal(execution, sources, final=final, frozen_ref=frozen_ref, forecast=forecast)
        elif self.name == "approved_execution":
            request = self.request_execution_stage(execution, sources)
            self.record("stage_result", execution_contract_ref=ref(execution), stage_request_ref=ref(request), stage="approved_execution", attempt=1, gaps=[], final_validation_result_ref=None, outcome="completed", output_refs=[ref(execution)], evidence_refs=[execution["approval_ref"]], parent_decision=self.parent("approved_execution", [ref(execution)], 4), failure=None)
        return {"schema_version": VERSION, "fixture_provenance": "mock", "mock_notice": NOTICE, "records": self.records, "mock_artifacts": self.artifacts}


def main():
    destination = ROOT.parents[1] / "examples/contracts/v0.1.0"
    destination.mkdir(parents=True, exist_ok=True)
    failed = False
    for name in ("approved_execution", "missing_inputs", "successful_analysis", "validation_failed", "execution_failed"):
        bundle = Builder(name).build()
        errors = validate_bundle(bundle)
        path = destination / (name + ".json")
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: {len(bundle['records'])} records, {len(bundle['mock_artifacts'])} mock artifacts; {'FAIL' if errors else 'schema + semantic PASS (mock only)'}")
        for error in errors:
            print(error)
        failed |= bool(errors)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
