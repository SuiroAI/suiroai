# Retail contract field index

Snapshot `0.1.0-draft.3`. The [semantic guide](CONTRACT.md) explains behavior; the [schema](../../src/suiroai/contracts/schema/retail-contract.schema.json) defines exact fields. Objects reject unknown fields. Required fields may explicitly allow null.

## `artifact_ref`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `artifact_id` | yes | `{"type":"string"}` |
| `version` | yes | `{"type":"integer","minimum":1}` |
| `sha256` | yes | `{"type":"string","pattern":"^[0-9a-f]{64}$"}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |

## `input_binding`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `task_id` | yes | `{"type":"string"}` |
| `task_version` | yes | `{"type":"integer","minimum":1}` |
| `input_version` | yes | `{"type":"integer","minimum":1}` |
| `input_digest` | yes | `{"type":"string","pattern":"^[0-9a-f]{64}$"}` |
| `proposal_version` | no | `{"anyOf":[{"type":"integer","minimum":1},{"type":"null"}]}` |
| `proposal_digest` | no | `{"anyOf":[{"type":"string","pattern":"^[0-9a-f]{64}$"},{"type":"null"}]}` |

## `approved_binding`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `task_id` | yes | `{"type":"string"}` |
| `task_version` | yes | `{"type":"integer","minimum":1}` |
| `input_version` | yes | `{"type":"integer","minimum":1}` |
| `input_digest` | yes | `{"type":"string","pattern":"^[0-9a-f]{64}$"}` |
| `proposal_version` | yes | `{"type":"integer","minimum":1}` |
| `proposal_digest` | yes | `{"type":"string","pattern":"^[0-9a-f]{64}$"}` |

## `submission_file`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `file_id` | yes | `{"type":"string"}` |
| `original_name` | yes | `{"type":"string"}` |
| `supplied_location` | yes | `{"type":"string"}` |
| `source_role` | yes | `{"type":"string","enum":["transactions","dictionary","usable_stock","inbound_ledger","ordering_policy","other"]}` |
| `source_namespace` | yes | `{"type":"string"}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","mock"]}` |
| `access` | yes | `{"type":"string","enum":["accessible","missing","inaccessible"]}` |
| `sha256` | yes | `{"anyOf":[{"type":"string","pattern":"^[0-9a-f]{64}$"},{"type":"null"}]}` |
| `size_bytes` | yes | `{"anyOf":[{"type":"integer","minimum":0},{"type":"null"}]}` |
| `access_reason` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |

## `assumption`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `assumption_id` | yes | `{"type":"string"}` |
| `classification` | yes | `{"type":"string","enum":["supplied_fact","supported_interpretation","synthetic_assumption","unknown"]}` |
| `statement` | yes | `{"type":"string"}` |
| `status` | yes | `{"type":"string","enum":["confirmed","proposed","unresolved"]}` |
| `source_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |

## `gap`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `gap_id` | yes | `{"type":"string"}` |
| `description` | yes | `{"type":"string"}` |
| `material` | yes | `{"type":"boolean"}` |
| `blocks` | yes | `{"type":"array","minItems":0,"items":{"type":"string","enum":["approval","execution","quantities","report"]}}` |
| `request_to_user` | yes | `{"type":"string"}` |

## `check`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `check_id` | yes | `{"type":"string"}` |
| `requirement_id` | yes | `{"type":"string"}` |
| `status` | yes | `{"type":"string","enum":["pass","fail","unavailable","not_applicable"]}` |
| `expected` | yes | `{"type":"string"}` |
| `actual` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |
| `evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `verifier` | yes | `{"type":"string"}` |

## `finding`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `finding_id` | yes | `{"type":"string"}` |
| `statement` | yes | `{"type":"string"}` |
| `classification` | yes | `{"type":"string","enum":["verified_finding","material_limitation"]}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `audience` | yes | `{"type":"string","enum":["internal","final_report"]}` |

## `product_store_key`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `source_namespace` | yes | `{"type":"string"}` |
| `product_id` | yes | `{"type":"string"}` |
| `store_id` | yes | `{"type":"string"}` |

## `pending_policy`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `status` | yes | `{"const":"pending"}` |
| `unresolved_gap_ids` | yes | `{"type":"array","minItems":1,"items":{"type":"string","minLength":1}}` |

## `defined_target_policy`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `status` | yes | `{"const":"defined"}` |
| `policy_id` | yes | `{"type":"string"}` |
| `quantity_unit` | yes | `{"const":"product_unit"}` |
| `aggregation_grain` | yes | `{"const":"product_store_day"}` |
| `target_measure` | yes | `{"type":"string"}` |
| `included_order_statuses` | yes | `{"type":"array","minItems":1,"items":{"type":"string","minLength":1}}` |
| `returns_treatment` | yes | `{"type":"string"}` |
| `nonpositive_quantity_treatment` | yes | `{"type":"string"}` |
| `duplicate_treatment` | yes | `{"type":"string"}` |
| `missing_date_treatment` | yes | `{"type":"string","enum":["unknown_not_zero","zero_only_with_completeness_evidence","explicit_observation_mask","zero_under_disclosed_synthetic_assumption"]}` |
| `extract_completeness` | yes | `{"type":"string","enum":["unverified","verified_complete","verified_partial"]}` |
| `completeness_evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `policy_evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `zero_assumption_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref"},{"type":"null"}]}` |

## `temporal_plan`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `as_of_date` | yes | `{"const":"2025-11-30"}` |
| `date_interpretation` | yes | `{"const":"source_calendar_date"}` |
| `initial_development_start` | yes | `{"const":"2022-01-01"}` |
| `initial_development_end` | yes | `{"const":"2024-12-31"}` |
| `rolling_validation_start` | yes | `{"const":"2025-01-01"}` |
| `development_target_end_cutoff` | yes | `{"const":"2025-11-30"}` |
| `reserved_unseen_start` | yes | `{"const":"2025-12-01"}` |
| `reserved_unseen_end` | yes | `{"const":"2025-12-31"}` |
| `development_context_access` | yes | `{"const":"development_artifacts_only"}` |
| `every_development_horizon_finishes_by_cutoff` | yes | `{"const":true}` |
| `score_fully_observed_horizons_only` | yes | `{"const":true}` |
| `freeze_before_holdout_access` | yes | `{"const":true}` |
| `forecast_as_of_date` | yes | `{"const":"2025-11-30"}` |
| `december_must_not_change_saved_forecast` | yes | `{"const":true}` |

## `metric_gate`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `metric_id` | yes | `{"type":"string"}` |
| `aggregation` | yes | `{"type":"string"}` |
| `population_id` | yes | `{"type":"string"}` |
| `direction` | yes | `{"type":"string","enum":["upper_bound","lower_bound","minimum_improvement_over_baseline"]}` |
| `threshold` | yes | `{"type":"number"}` |
| `unit` | yes | `{"type":"string"}` |

## `acceptance_rule`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `rule_id` | yes | `{"type":"string"}` |
| `version` | yes | `{"type":"integer","minimum":1}` |
| `declared_at` | yes | `{"type":"string","format":"date-time"}` |
| `metric_gates` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_gate"}}` |
| `required_check_ids` | yes | `{"type":"array","minItems":1,"items":{"type":"string","minLength":1}}` |
| `all_gates_required` | yes | `{"const":true}` |
| `minimum_observation_count` | yes | `{"type":"integer","minimum":1}` |

## `execution_limits`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `max_candidates` | yes | `{"type":"integer","minimum":1}` |
| `max_llm_feature_definitions` | yes | `{"type":"integer","minimum":1}` |
| `max_defect_rechecks` | yes | `{"type":"integer","minimum":0}` |
| `max_parent_reviews` | yes | `{"type":"integer","minimum":1}` |
| `max_execution_seconds` | yes | `{"type":"integer","minimum":1}` |
| `max_stage_attempts` | yes | `{"type":"integer","minimum":1}` |

## `parent_decision`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `checkpoint` | yes | `{"type":"string","enum":["approved_execution","preparation","initial_baseline_evaluation","llm_features","comparison_and_freeze","final_validation","recommendations","output_verification"]}` |
| `decision` | yes | `{"type":"string","enum":["proceed","stop","request_material_facts","allow_defect_recheck","confirmed_failure","pass_after_recheck","review"]}` |
| `actor` | yes | `{"type":"string"}` |
| `decided_at` | yes | `{"type":"string","format":"date-time"}` |
| `reason` | yes | `{"type":"string"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |

## `lineage_entry`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `output_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `input_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"1. output ref."}}` |
| `transformation_id` | yes | `{"type":"string"}` |
| `description` | yes | `{"type":"string"}` |
| `row_lineage_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref","description":"1. output ref."},{"type":"null"}]}` |
| `preserved_raw_hashes` | yes | `{"type":"array","minItems":1,"items":{"type":"string","pattern":"^[0-9a-f]{64}$"}}` |

## `artifact_availability`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `artifact_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `permitted_use` | yes | `{"type":"string","enum":["development","reserved_unseen_evaluation","as_of_operations"]}` |
| `earliest_event_date` | yes | `{"type":"string","format":"date"}` |
| `latest_event_date` | yes | `{"type":"string","format":"date"}` |
| `latest_information_available_date` | yes | `{"type":"string","format":"date"}` |
| `event_time_column` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |
| `availability_time_column` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |
| `contains_post_cutoff_rows` | yes | `{"type":"boolean"}` |

## `join_check`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `left_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `right_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `join_keys` | yes | `{"type":"array","minItems":1,"items":{"type":"string","enum":["Product_ID","Store_ID","Order_Date"]}}` |
| `expected_cardinality` | yes | `{"type":"string","enum":["one_to_one","many_to_one","one_to_many"]}` |
| `left_rows` | yes | `{"type":"integer","minimum":0}` |
| `right_rows` | yes | `{"type":"integer","minimum":0}` |
| `result_rows` | yes | `{"type":"integer","minimum":0}` |
| `unmatched_left_keys` | yes | `{"type":"integer","minimum":0}` |
| `unmatched_right_keys` | yes | `{"type":"integer","minimum":0}` |
| `check_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |

## `feature_definition`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `feature_id` | yes | `{"type":"string"}` |
| `name` | yes | `{"type":"string"}` |
| `expression` | yes | `{"type":"string"}` |
| `source_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `event_time_basis` | yes | `{"type":"string"}` |
| `availability_time_basis` | yes | `{"type":"string"}` |
| `minimum_lag_calendar_days` | yes | `{"type":"integer","minimum":0}` |
| `timing_rule` | yes | `{"type":"string"}` |
| `uses_only_information_available_at_origin` | yes | `{"const":true}` |
| `rationale` | yes | `{"type":"string"}` |
| `fit_scope` | yes | `{"const":"training_fold_only"}` |

## `llm_generation_provenance`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `generation_kind` | yes | `{"const":"llm_generated"}` |
| `model_id` | yes | `{"type":"string"}` |
| `prompt_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `response_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `generated_at` | yes | `{"type":"string","format":"date-time"}` |
| `development_context_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"3. prompt ref."}}` |
| `unrestricted_raw_future_access` | yes | `{"const":false}` |

## `metric_score`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `metric_id` | yes | `{"type":"string"}` |
| `value` | yes | `{"type":"number"}` |
| `unit` | yes | `{"type":"string"}` |
| `population_id` | yes | `{"type":"string"}` |
| `observation_count` | yes | `{"type":"integer","minimum":1}` |
| `forecast_origin_start` | yes | `{"type":"string","format":"date"}` |
| `forecast_origin_end` | yes | `{"type":"string","format":"date"}` |
| `target_end_max` | yes | `{"type":"string","format":"date"}` |

## `development_fold`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `fold_id` | yes | `{"type":"string"}` |
| `training_end` | yes | `{"type":"string","format":"date"}` |
| `forecast_origin` | yes | `{"type":"string","format":"date"}` |
| `target_start` | yes | `{"type":"string","format":"date"}` |
| `target_end` | yes | `{"type":"string","format":"date"}` |
| `population_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |

## `metric_definition`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `metric_id` | yes | `{"type":"string"}` |
| `formula` | yes | `{"type":"string"}` |
| `unit` | yes | `{"type":"string"}` |
| `aggregation` | yes | `{"type":"string"}` |
| `direction` | yes | `{"type":"string","enum":["lower_is_better","higher_is_better"]}` |
| `tie_tolerance` | yes | `{"type":"number","minimum":0}` |

## `evaluation_plan`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `plan_id` | yes | `{"type":"string"}` |
| `version` | yes | `{"type":"integer","minimum":1}` |
| `declared_at` | yes | `{"type":"string","format":"date-time"}` |
| `temporal_plan` | yes | `{"$ref":"#/$defs/temporal_plan"}` |
| `metric_definitions` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_definition"}}` |
| `development_folds` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/development_fold"}}` |
| `common_population_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `fully_observed_horizon_check_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `primary_metric_id` | yes | `{"type":"string"}` |

## `candidate_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `candidate_id` | yes | `{"type":"string"}` |
| `model_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `feature_set_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `preprocessing_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `scores` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_score"}}` |
| `eligible_for_selection` | yes | `{"type":"boolean"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"2. model ref."}}` |

## `frozen_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `freeze_id` | yes | `{"type":"string"}` |
| `frozen_at` | yes | `{"type":"string","format":"date-time"}` |
| `selected_candidate_id` | yes | `{"type":"string"}` |
| `model_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `feature_set_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `preprocessing_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `evaluation_plan_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `acceptance_rule_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `development_input_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. model ref."}}` |
| `november_30_forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `forecast_as_of_date` | yes | `{"const":"2025-11-30"}` |
| `forecast_input_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. model ref."}}` |
| `no_reserved_outcomes_in_fit_selection_or_forecast` | yes | `{"const":true}` |

## `defect_recheck`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `attempt` | yes | `{"type":"integer","minimum":1}` |
| `defect_description` | yes | `{"type":"string"}` |
| `defect_evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"7. november 30 forecast ref."}}` |
| `correction_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"7. november 30 forecast ref."}}` |
| `parent_authorization` | yes | `{"$ref":"#/$defs/parent_decision"}` |
| `model_selection_unchanged` | yes | `{"const":true}` |
| `november_30_forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `scores` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/metric_score"}}` |
| `checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `outcome` | yes | `{"type":"string","enum":["pass","fail","execution_failure"]}` |

## `quantity_row`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `key` | yes | `{"$ref":"#/$defs/product_store_key"}` |
| `quantity_unit` | yes | `{"const":"product_unit"}` |
| `arithmetic_input_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. forecast ref."}}` |
| `forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `forecast_horizon_start` | yes | `{"type":"string","format":"date"}` |
| `forecast_horizon_end` | yes | `{"type":"string","format":"date"}` |
| `forecast_quantity` | yes | `{"type":"number","minimum":0}` |
| `usable_on_hand_quantity` | yes | `{"type":"integer","minimum":0}` |
| `on_order_summary_quantity` | yes | `{"type":"integer","minimum":0}` |
| `eligible_receipt_quantity` | yes | `{"type":"integer","minimum":0}` |
| `supplier_lead_calendar_days` | yes | `{"type":"integer","minimum":1}` |
| `review_period_calendar_days` | yes | `{"type":"integer","minimum":1}` |
| `safety_stock_quantity` | yes | `{"type":"integer","minimum":0}` |
| `order_multiple` | yes | `{"type":"integer","minimum":1}` |
| `minimum_positive_order_quantity` | yes | `{"type":"integer","minimum":1}` |
| `raw_order_need` | yes | `{"type":"number"}` |
| `rounded_order_quantity` | yes | `{"type":"integer","minimum":0}` |
| `approved_order_quantity` | yes | `{"anyOf":[{"type":"integer","minimum":0},{"type":"null"}]}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. forecast ref."}}` |
| `product_name` | no | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |

## `quantity_exception`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `key` | yes | `{"$ref":"#/$defs/product_store_key"}` |
| `reason` | yes | `{"type":"string"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |

## `report_claim`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `claim_id` | yes | `{"type":"string"}` |
| `statement` | yes | `{"type":"string"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |

## `failure_detail`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `stage` | yes | `{"type":"string","enum":["input_review","preparation","initial_evaluation","feature_generation","comparison","final_validation","quantity_calculation","output_verification","adapter_execution"]}` |
| `reason` | yes | `{"type":"string"}` |
| `scope_limitation` | yes | `{"type":"string"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `error_code` | no | `{"type":"string","enum":["plugin_unavailable","unsupported_integration","inaccessible_input","invalid_code","timeout","cancelled","budget_exhausted","runtime_error","integrity_error"]}` |

## `permitted_customer_response`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"type":"string","enum":["final_report","failure_explanation","missing_input_guidance","no_customer_response"]}` |
| `text` | yes | `{"type":"string"}` |
| `report_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref"},{"type":"null"}]}` |

## `submission`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"submission"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/input_binding"}` |
| `run_id` | no | `{"type":"string"}` |
| `original_request` | yes | `{"type":"string"}` |
| `files` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/submission_file"}}` |
| `received_at` | yes | `{"type":"string","format":"date-time"}` |

## `task_proposal`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"task_proposal"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | no | `{"type":"string"}` |
| `submission_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `goal` | yes | `{"type":"string"}` |
| `output` | yes | `{"const":"one_restocking_list_and_final_report_or_verified_failure_explanation"}` |
| `source_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref","description":"8. submission ref."}}` |
| `readiness` | yes | `{"type":"string","enum":["ready","needs_inputs","needs_material_facts"]}` |
| `assumptions` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/assumption"}}` |
| `gaps` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/gap"}}` |
| `target_policy` | yes | `{"oneOf":[{"$ref":"#/$defs/pending_policy"},{"$ref":"#/$defs/defined_target_policy"}]}` |
| `temporal_plan` | yes | `{"$ref":"#/$defs/temporal_plan"}` |
| `acceptance_rule` | yes | `{"oneOf":[{"$ref":"#/$defs/pending_policy"},{"$ref":"#/$defs/acceptance_rule"}]}` |

## `task_approval`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"task_approval"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | no | `{"type":"string"}` |
| `proposal_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `decision` | yes | `{"type":"string","enum":["approved","rejected","pending"]}` |
| `actor` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |
| `decided_at` | yes | `{"anyOf":[{"type":"string","format":"date-time"},{"type":"null"}]}` |
| `comment` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |

## `execution_contract`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"execution_contract"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `approval_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `proposal_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `source_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"8. approval ref."}}` |
| `allowed_actions` | yes | `{"type":"array","minItems":1,"items":{"type":"string","enum":["inspect","clean","join","aggregate","eda","materialize_features","train","evaluate","freeze","calculate_restocking","draft_report","verify_outputs"]}}` |
| `limits` | yes | `{"$ref":"#/$defs/execution_limits"}` |
| `required_checkpoints` | yes | `{"type":"array","minItems":8,"uniqueItems":true,"items":{"type":"string","enum":["approved_execution","preparation","initial_baseline_evaluation","llm_features","comparison_and_freeze","final_validation","recommendations","output_verification"]}}` |
| `temporal_plan` | yes | `{"$ref":"#/$defs/temporal_plan"}` |
| `target_policy` | yes | `{"oneOf":[{"$ref":"#/$defs/pending_policy"},{"$ref":"#/$defs/defined_target_policy"}]}` |
| `acceptance_rule` | yes | `{"$ref":"#/$defs/acceptance_rule"}` |
| `source_assumptions` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/assumption"}}` |
| `quantity_unit` | yes | `{"const":"product_unit"}` |
| `inbound_ledger_policy` | yes | `{"type":"string","enum":["complete_synthetic_ledger_absence_is_zero","unknown_absence_not_zero"]}` |
| `inbound_summary_policy` | yes | `{"const":"reconcile_receipt_sum_never_double_count"}` |
| `synthetic_operational_source_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref","description":"8. approval ref."}}` |

## `preparation_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"preparation_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `prepared_development_data_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `reserved_unseen_data_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `initial_feature_set_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `initial_feature_definitions` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/feature_definition"}}` |
| `target_policy` | yes | `{"$ref":"#/$defs/defined_target_policy"}` |
| `lineage` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/lineage_entry"}}` |
| `join_checks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/join_check"}}` |
| `quality_checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `availability` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_availability"}}` |
| `development_context_allowlist` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"8. execution contract ref."}}` |
| `findings` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/finding"}}` |
| `parent_decision` | yes | `{"$ref":"#/$defs/parent_decision"}` |

## `feature_proposal`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"feature_proposal"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `preparation_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `generation` | yes | `{"$ref":"#/$defs/llm_generation_provenance"}` |
| `definitions` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/feature_definition"}}` |
| `initial_evaluation_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |

## `feature_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"feature_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `feature_proposal_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `materialized_feature_set_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `definitions` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/feature_definition"}}` |
| `lineage` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/lineage_entry"}}` |
| `availability` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_availability"}}` |
| `validation_checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `findings` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/finding"}}` |
| `parent_decision` | yes | `{"$ref":"#/$defs/parent_decision"}` |

## `evaluation_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"evaluation_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `preparation_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `llm_feature_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `evaluation_plan` | yes | `{"$ref":"#/$defs/evaluation_plan"}` |
| `baseline_id` | yes | `{"type":"string"}` |
| `baseline_scores` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_score"}}` |
| `initial_candidate_id` | yes | `{"type":"string"}` |
| `candidates` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/candidate_result"}}` |
| `selection_rule` | yes | `{"type":"string"}` |
| `comparison_checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `frozen` | yes | `{"$ref":"#/$defs/frozen_result"}` |
| `findings` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/finding"}}` |
| `parent_decision` | yes | `{"$ref":"#/$defs/parent_decision"}` |

## `final_validation_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"final_validation_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `evaluation_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `frozen_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `november_30_forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `acceptance_rule` | yes | `{"$ref":"#/$defs/acceptance_rule"}` |
| `reserved_unseen_data_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `scores` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_score"}}` |
| `checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `outcome` | yes | `{"type":"string","enum":["pass","fail"]}` |
| `parent_review` | yes | `{"anyOf":[{"$ref":"#/$defs/parent_decision"},{"type":"null"}]}` |
| `defect_rechecks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/defect_recheck"}}` |
| `findings` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/finding"}}` |
| `holdout_accessed_at` | yes | `{"type":"string","format":"date-time"}` |

## `report_draft`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"report_draft"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `outcome` | yes | `{"type":"string","enum":["success","missing_inputs","validation_failure","execution_failure"]}` |
| `final_validation_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref","description":"8. execution contract ref."},{"type":"null"}]}` |
| `frozen_result_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref","description":"8. execution contract ref."},{"type":"null"}]}` |
| `november_30_forecast_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref","description":"8. execution contract ref."},{"type":"null"}]}` |
| `arithmetic_source_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref","description":"8. execution contract ref."}}` |
| `orders` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/quantity_row"}}` |
| `exceptions` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/quantity_exception"}}` |
| `arithmetic_checks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/check"}}` |
| `claims` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/report_claim"}}` |
| `findings` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/finding"}}` |
| `customer_draft` | yes | `{"type":"string"}` |
| `failure` | yes | `{"anyOf":[{"$ref":"#/$defs/failure_detail"},{"type":"null"}]}` |
| `parent_decision` | yes | `{"$ref":"#/$defs/parent_decision"}` |
| `quantity_result_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref"},{"type":"null"}]}` |

## `output_verification`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"output_verification"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `report_draft_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `independent_verifier` | yes | `{"type":"string"}` |
| `independence_basis` | yes | `{"type":"string"}` |
| `arithmetic_checks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/check"}}` |
| `claim_checks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/check"}}` |
| `binding_checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `decision` | yes | `{"type":"string","enum":["delivery_allowed","blocked"]}` |
| `parent_decision` | yes | `{"anyOf":[{"$ref":"#/$defs/parent_decision"},{"type":"null"}]}` |
| `permitted_response` | yes | `{"$ref":"#/$defs/permitted_customer_response"}` |

## `evidence_record`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"evidence_record"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `requirement_id` | yes | `{"type":"string"}` |
| `requirement_source` | yes | `{"type":"string"}` |
| `checked_artifacts` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `check` | yes | `{"$ref":"#/$defs/check"}` |
| `evidence_mode` | yes | `{"type":"string","enum":["real","mock"]}` |
| `verifier_decision` | yes | `{"type":"string","enum":["accepted","rejected","needs_evidence"]}` |
| `verifier` | yes | `{"type":"string"}` |
| `verified_at` | yes | `{"type":"string","format":"date-time"}` |
| `mock_limitation` | yes | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |

## `initial_evaluation_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"initial_evaluation_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `preparation_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `evaluation_plan` | yes | `{"$ref":"#/$defs/evaluation_plan"}` |
| `baseline_id` | yes | `{"type":"string"}` |
| `baseline_scores` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/metric_score"}}` |
| `initial_candidate` | yes | `{"$ref":"#/$defs/candidate_result"}` |
| `comparison` | yes | `{"type":"string","enum":["better","equal","worse"]}` |
| `parent_decision` | yes | `{"$ref":"#/$defs/parent_decision"}` |

## `capability_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"capability_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `status` | yes | `{"type":"string","enum":["supported","unsupported","unavailable"]}` |
| `host` | yes | `{"type":"string"}` |
| `interface` | yes | `{"type":"string"}` |
| `demonstrated` | yes | `{"type":"boolean"}` |
| `evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `checks` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/check"}}` |

## `stage_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"stage_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `stage` | yes | `{"type":"string","enum":["approved_execution","preparation","initial_baseline_evaluation","llm_features","comparison_and_freeze","final_validation","recommendations","output_verification"]}` |
| `outcome` | yes | `{"type":"string","enum":["completed","needs_inputs","needs_material_facts","validation_failed","execution_failed"]}` |
| `output_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `evidence_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `parent_decision` | yes | `{"anyOf":[{"$ref":"#/$defs/parent_decision"},{"type":"null"}]}` |
| `failure` | yes | `{"anyOf":[{"$ref":"#/$defs/failure_detail"},{"type":"null"}]}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `stage_request_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `attempt` | yes | `{"type":"integer","minimum":1}` |
| `gaps` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/gap"}}` |
| `final_validation_result_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref"},{"type":"null"}]}` |

## `approved_quantity_row`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `key` | yes | `{"$ref":"#/$defs/product_store_key"}` |
| `quantity_unit` | yes | `{"const":"product_unit"}` |
| `arithmetic_input_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. forecast ref."}}` |
| `forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `forecast_horizon_start` | yes | `{"type":"string","format":"date"}` |
| `forecast_horizon_end` | yes | `{"type":"string","format":"date"}` |
| `forecast_quantity` | yes | `{"type":"number","minimum":0}` |
| `usable_on_hand_quantity` | yes | `{"type":"integer","minimum":0}` |
| `on_order_summary_quantity` | yes | `{"type":"integer","minimum":0}` |
| `eligible_receipt_quantity` | yes | `{"type":"integer","minimum":0}` |
| `supplier_lead_calendar_days` | yes | `{"type":"integer","minimum":1}` |
| `review_period_calendar_days` | yes | `{"type":"integer","minimum":1}` |
| `safety_stock_quantity` | yes | `{"type":"integer","minimum":0}` |
| `order_multiple` | yes | `{"type":"integer","minimum":1}` |
| `minimum_positive_order_quantity` | yes | `{"type":"integer","minimum":1}` |
| `raw_order_need` | yes | `{"type":"number"}` |
| `rounded_order_quantity` | yes | `{"type":"integer","minimum":0}` |
| `approved_order_quantity` | yes | `{"type":"integer","minimum":0}` |
| `evidence_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref","description":"4. forecast ref."}}` |
| `product_name` | no | `{"anyOf":[{"type":"string","minLength":1},{"type":"null"}]}` |

## `quantity_result`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"quantity_result"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `final_validation_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `frozen_result_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `november_30_forecast_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `arithmetic_source_refs` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `orders` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/quantity_row"}}` |
| `exceptions` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/quantity_exception"}}` |
| `arithmetic_checks` | yes | `{"type":"array","minItems":1,"items":{"$ref":"#/$defs/check"}}` |
| `independent_check_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `parent_decision` | yes | `{"anyOf":[{"$ref":"#/$defs/parent_decision"},{"type":"null"}]}` |
| `candidate_quantity_ref` | yes | `{"anyOf":[{"$ref":"#/$defs/artifact_ref"},{"type":"null"}]}` |

## `stage_request`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `kind` | yes | `{"const":"stage_request"}` |
| `schema_version` | yes | `{"const":"0.1.0-draft.3"}` |
| `artifact_id` | yes | `{"type":"string"}` |
| `artifact_version` | yes | `{"type":"integer","minimum":1}` |
| `provenance` | yes | `{"type":"string","enum":["supplied","synthetic","derived","mock"]}` |
| `binding` | yes | `{"$ref":"#/$defs/approved_binding"}` |
| `run_id` | yes | `{"type":"string"}` |
| `execution_contract_ref` | yes | `{"$ref":"#/$defs/artifact_ref"}` |
| `stage` | yes | `{"type":"string","enum":["approved_execution","preparation","initial_baseline_evaluation","llm_features","comparison_and_freeze","final_validation","recommendations","output_verification"]}` |
| `attempt` | yes | `{"type":"integer","minimum":1}` |
| `parent_authorization` | yes | `{"$ref":"#/$defs/parent_decision"}` |
| `released_input_refs` | yes | `{"type":"array","minItems":0,"items":{"$ref":"#/$defs/artifact_ref"}}` |
| `remaining_limits` | yes | `{"$ref":"#/$defs/remaining_limits"}` |
| `issued_at` | yes | `{"type":"string","format":"date-time"}` |
| `deadline` | yes | `{"type":"string","format":"date-time"}` |
| `output_namespace` | yes | `{"type":"string"}` |

## `remaining_limits`

| Field | Required | Type / constraints |
| --- | --- | --- |
| `max_candidates` | yes | `{"type":"integer","minimum":0}` |
| `max_llm_feature_definitions` | yes | `{"type":"integer","minimum":0}` |
| `max_defect_rechecks` | yes | `{"type":"integer","minimum":0}` |
| `max_parent_reviews` | yes | `{"type":"integer","minimum":0}` |
| `max_execution_seconds` | yes | `{"type":"integer","minimum":0}` |
| `max_stage_attempts` | yes | `{"type":"integer","minimum":0}` |
