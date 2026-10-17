# Retail MVP contract snapshot

Version: `0.1.0-draft.2`. Owner: DSC-24. Status: local draft for architecture and consumer review. DSC-3 and DSC-24 have mutually acknowledged the reserved ownership paths; exact schema snapshot agreement remains pending. This snapshot is not published and must not be described as an agreed consumer interface or production stable.

The machine-readable definitions are in [schema/retail-contract.schema.json](../../src/suiroai/contracts/schema/retail-contract.schema.json). This document defines their meaning and cross-artifact requirements. Passing schema validation establishes structural conformance only. It does not establish business approval, source correctness, model quality, a functioning analytical pipeline, or integration acceptance.

## Scope and authority

This is one retail restocking task, with representative component fixtures. The parent forms the proposed task from the original request and read-only inspection, obtains the user's approval, and owns all runtime transitions and checkpoint decisions. Component contracts report evidence and proposed outcomes; they cannot approve their own checkpoint. DSC-24 owns these definitions, not parent orchestration, data preparation, training, evaluation, report production, or a custom runtime.

Receiving a submission stores the request, supplied file references and access observations. It performs no joins, cleaning, deduplication, aggregation, feature materialization or modeling. Engineering fixture preparation is a separate activity after approval in a real run. The active local demo sources must never silently replace missing customer submissions. Examples under `examples/contracts/v0.1.0/` are unmistakably mock component messages, not proof that any workflow has run.

## Common version and evidence envelope

| Field | Meaning |
| --- | --- |
| `schema_version` | Exact contract snapshot used to interpret the artifact. A consumer must reject unsupported versions explicitly. |
| `artifact_id` | Stable logical identity of this artifact, unique within the artifact registry. |
| `artifact_version` | Immutable revision of that artifact. Changed bytes require a new version and hash. |
| `provenance` | Required origin enum: `supplied`, `synthetic`, `derived` or `mock`. It persists on every immutable reference, including external references. Synthetic facts must never be relabeled customer-supplied facts. Derived artifacts retain underlying source origins through lineage. |
| `kind`, `run_id` | Exact message discriminator and nonempty run/correlation identity. Assigning an intake correlation ID does not mean execution has begun; executed artifacts identify their run without changing the approved task binding. |
| `binding.task_id` | Identity of the single proposed business task, preserved through approval and execution. |
| `binding.task_version` | Exact business-task revision. A material correction creates a new proposal and approval cycle. |
| `binding.input_version` | Exact inventory/version of the submitted inputs and their access state. Missing inputs remain explicit. |
| `binding.input_digest` | SHA-256 binding of the canonical input inventory, including source identities, immutable file hashes where accessible, versions and missing/inaccessible states. It is not a hash of a prepared join. |
| `binding.proposal_version` | Exact proposed task revision shown for approval. Preproposal intake has no approved proposal; its absence must remain explicit under the schema's intake rules. |
| `binding.proposal_digest` | SHA-256 of the canonical proposed task content. Together with the input digest this prevents approval reuse after a silent semantic or input change. |
| Reference `artifact_id`, `version`, `sha256`, `provenance` | All four fields are required: exact immutable target artifact, integer revision, content SHA-256 and origin classification. A path or latest-version pointer alone is insufficient for evidence. |

Raw file hashes are SHA-256 over the exact retained bytes. Contract JSON hashes use the protocol implemented by `suiroai.contracts.validation.digest`: Python `json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`, encoded as UTF-8, then SHA-256. Consumers must reproduce these bytes, including compact separators, Unicode output and rejection of NaN/infinities. This is a specified application protocol, not a claim of generic canonical JSON equivalence across arbitrary serializers.

`input_digest` hashes exactly `{"original_request": submission.original_request, "files": submission.files}`; list order remains significant. `proposal_digest` hashes the proposal payload after excluding envelope keys `kind`, `schema_version`, `artifact_id`, `artifact_version`, `provenance`, `binding`, `input_binding` and `run_id`. Artifact references hash the entire referenced contract JSON with the same protocol; referenced raw files retain byte hashes. Raw hashes remain independent of prepared artifacts. Mock external artifacts identify explicit fixture markers and never attest that real analytical outputs exist.

Artifacts in an execution chain must bind to the same approved task, input inventory and proposal. A changed material source, input access state, business assumption or proposed scope returns to proposal formation and signoff; execution does not redefine the task after signoff. Implementation-only repairs may create new derived artifact versions while retaining the approved binding when business/input semantics are unchanged. A verifier checks both the binding values and the referenced bytes.

## Interface meanings

The schema supplies concrete payload structure. The following is the minimum semantic responsibility of each interface; optional extensions do not authorize additional workflows.

The ten concepts are represented by seventeen discriminated message kinds: `submission`, `task_proposal`, `task_approval`, `execution_contract`, `preparation_result`, `initial_evaluation_result`, `feature_proposal`, `feature_result`, `evaluation_result`, `final_validation_result`, `quantity_result`, `report_draft`, `output_verification`, `evidence_record`, `capability_result`, `stage_request` and `stage_result`. In particular, the initial baseline checkpoint and the quantity producer are separate messages; a report is not their substitute.

| Interface | Required meaning and consumer responsibility |
| --- | --- |
| Submission | Preserve original business request, actual supplied source references, source/input versions and accessible, inaccessible or missing status with reasons. Distinguish the user's raw intake from the separately prepared engineering fixture. No preparation result is implied by acceptance of a file. |
| Task proposal and approval | State the business goal and promised output, source references, material assumptions, unresolved gaps and intended temporal/target scope. Record the user's decision against the exact proposal and input binding. Rejection, corrections and new material data return to proposal formation. Silence means waiting, never approval. |
| Execution contract | Carry the approved task reference, source versions, as-of policy, permitted bounded actions, numerical resource/recovery limits, required stages/checkpoints and temporal/evaluation plan. Require resolved business facts before dependent work; keep statistical decisions explicit and never silently invent material business facts. |
| Preparation result | Reference prepared tables and initial features with raw-to-derived lineage, join cardinality/coverage checks, quality findings, timing/availability metadata and concise verified observations. Report unresolved target/treatment decisions explicitly. Joins and cleaning occur only during approved execution. |
| Feature proposal and result | Record each LLM-generated feature definition, referenced inputs, availability timing, rationale and intended transform, then link the materialized feature artifact and its validation evidence. The generation context receives only permitted development artifacts. A textual definition alone is not a validated feature. |
| Evaluation and frozen result | Bind baseline and candidate scores to one common development evaluation plan, metric definitions and scored population. Record the selected model, features and preprocessing as immutable artifacts plus the separately retained November 30 forecast. Include the parent decision; an initial model equal to or worse than baseline triggers internal review, not an unreported success or automatic terminal failure. |
| Final validation result | Record the acceptance rule fixed before holdout access, actual December scores/checks, eligible and excluded horizons, parent review and any bounded defect correction/recheck evidence. Distinguish passed, measured failure and execution failure. Recheck repairs an identified defect under the permitted bound; it never selects a second-best model, tunes against holdout results or revises the acceptance rule. |
| Quantity and report draft | Bind arithmetic inputs, demand forecast, stock, policy and eligible receipts to proposed orders and explicit exceptions; retain the parent-approved quantities, evidence-linked analytical/feature findings, measured model results, limitations and customer draft. Failure variants contain no purportedly valid recommendation list. |
| Output verification | Independently recompute arithmetic and inspect customer claims against referenced evidence and exact versions. Report discrepancies and a parent decision controlling the permitted customer response. An unchecked draft or passing self-check cannot authorize delivery. |
| Evidence record | Bind a requirement to an exact artifact/version/hash, named check, expected result, actual result and verifier decision. Identify mock evidence unambiguously. A passed structural/fixture check is not a passed analytical or integration acceptance check. |

`capability_result` reports whether the actual host/interface is `supported`, `unsupported` or `unavailable`; `host` and `interface` name the environment examined. A supported result requires `demonstrated: true`, checks and evidence. A connector name alone is not demonstrated OpenAI Data execution. `stage_result` carries a focused stage outcome (`completed`, `needs_inputs`, `needs_material_facts`, `validation_failed`, `execution_failed`), output/evidence references, optional parent decision and failure detail. It reports evidence to the parent; it does not own transitions.

## Important nested field meanings

| Structure / fields | Meaning |
| --- | --- |
| `submission_file.file_id`, `original_name`, `supplied_location`, `source_role`, `source_namespace` | Identify the actual submitted file, its original label/location, intended table role and ID namespace. Role is a claim about meaning, not proof of usable content. |
| `submission_file.access`, `sha256`, `size_bytes`, `access_reason` | Accessible files require measured hash and size and a null access reason. Missing/inaccessible files have null hash/size and an explicit reason; no hash is fabricated. |
| `assumption.assumption_id`, `classification`, `statement`, `status`, `source_refs` | Track a fact/interpretation/assumption/unknown separately from its confirmation state and evidence. `unknown` stays `unresolved`. |
| `gap.gap_id`, `description`, `material`, `blocks`, `request_to_user` | Identify the unresolved business/input issue, whether material, dependent outputs/stages and the concrete information needed. Empty or nonmaterial gaps do not authorize silent business-fact selection. |
| `task_proposal.readiness`, `target_policy`, `acceptance_rule` | Separate a ready proposal from one needing files or material facts. A pending policy carries `unresolved_gap_ids`; pending material rules cannot be used as defined execution settings. |
| `task_approval.proposal_ref`, `decision`, `actor`, `decided_at`, `comment` | Identify the exact proposal, explicit approved/rejected/pending state, decision maker, time and any correction. A pending record is not permission to execute. |
| `defined_target_policy.target_measure`, `included_order_statuses`, `returns_treatment`, `nonpositive_quantity_treatment`, `duplicate_treatment` | Define exactly what transaction quantities become the target and how excluded/ambiguous source rows are treated. No default unconstrained-demand interpretation is provided. |
| `defined_target_policy.aggregation_grain`, `quantity_unit` | This narrow interface supports `product_store_day` and `product_unit`; that technical boundary does not establish the real target interpretation or missing-date completeness. |
| `missing_date_treatment`, `extract_completeness`, `completeness_evidence_refs`, `policy_evidence_refs` | Bind missing-date treatment and completeness claims to evidence; zero fill requires verified complete extraction and evidence. Policy evidence supports the substantive target/treatment choices. |
| `execution_contract.allowed_actions`, `limits`, `required_checkpoints` | Enumerate permitted preparation/analysis/report actions, finite limits and mandatory parent checkpoints. `max_candidates`, `max_llm_feature_definitions`, `max_defect_rechecks`, `max_parent_reviews`, `max_execution_seconds` are ceilings, not instructions to exhaust the budget. |
| `source_assumptions`, `synthetic_operational_source_refs`, `inbound_ledger_policy`, `inbound_summary_policy` | Keep synthetic origins and declared ledger completeness explicit; reconcile receipt sums without adding summary and ledger totals together. |
| `lineage_entry.output_ref`, `input_refs`, `transformation_id`, `description`, `row_lineage_ref`, `preserved_raw_hashes` | Identify derived output, source inputs, reproducible transformation and optional row mapping, while retaining original raw byte hashes. |
| `artifact_availability.permitted_use`, event-date range, `latest_information_available_date`, time-column names, `contains_post_cutoff_rows` | State which contexts can consume an artifact and its event/knowledge-time limits. Metadata must be checked against artifact content; an allowlist label alone cannot make future rows safe. |
| `join_check.left_ref`, `right_ref`, `join_keys`, `expected_cardinality`, row counts, unmatched-key counts, `check_ref` | Make join expectations and measured expansion/coverage inspectable; point to the supporting check. |
| `feature_definition.feature_id`, `name`, `expression`, `source_refs`, time bases, `minimum_lag_calendar_days`, `timing_rule`, `uses_only_information_available_at_origin`, `rationale`, `fit_scope` | Define an executable feature concept, inputs, information timing, reason and permitted fit population. A lag or boolean assertion must be supported by validation. |
| `llm_generation_provenance.model_id`, `prompt_ref`, `response_ref`, `generated_at`, `development_context_refs`, `unrestricted_raw_future_access` | Preserve actual generation inputs/output and context restrictions. The fixed generation kind identifies required LLM feature generation; unrestricted future raw access is prohibited. |
| `evaluation_plan.plan_id`, `version`, `declared_at`, `metric_definitions`, `development_folds`, `common_population_ref`, `fully_observed_horizon_check_ref` | Define one reproducible comparison plan, formulas, common scored population, fold boundaries and horizon-observation evidence. Each fold names `training_end`, `forecast_origin`, `target_start`, `target_end`, `population_ref`. |
| `metric_score.metric_id`, `value`, `unit`, `population_id`, `observation_count`, origin range, `target_end_max` | Bind a measured score to its formula/unit, population size and temporal extent. Scores over different populations are not silently comparable. |
| `acceptance_rule.rule_id`, `version`, `declared_at`, `metric_gates`, `required_check_ids`, `all_gates_required`, `minimum_observation_count` | Predeclare validation gates and required sample/check conditions. Each gate fixes metric, aggregation, population, direction, threshold and unit. Hypothetical fixture thresholds make no real customer decision. |
| `candidate_result.candidate_id`, `model_ref`, `feature_set_ref`, `preprocessing_ref`, `scores`, `eligible_for_selection`, `evidence_refs` | Identify each bounded candidate and measured common-plan result; preserve excluded candidates with reasons in their evidence. |
| `frozen_result.freeze_id`, `frozen_at`, `selected_candidate_id`, model/feature/preprocessing refs, plan/rule refs, development/forecast input refs, forecast ref | Freeze the whole fitted choice and the separate November 30 forecast before holdout access. `no_reserved_outcomes_in_fit_selection_or_forecast` is an invariant to verify. |
| `final_validation_result.holdout_accessed_at`, `scores`, `checks`, `outcome`, `parent_review`, `defect_rechecks` | Retain first holdout access and actual results. `outcome` is `pass` or `fail`; inability to execute is a separate execution failure, never an invented measured failure. |
| `defect_recheck.attempt`, `defect_description`, `defect_evidence_refs`, `correction_refs`, `parent_authorization`, `model_selection_unchanged`, forecast ref, scores/checks/outcome | Explain the concrete defect, authorized correction and bounded recheck. Preserve selected model and saved forecast. Recheck failure or operational failure remains explicit. |
| `quantity_row.key`, horizon dates, `forecast_ref`, `forecast_quantity`, `arithmetic_input_refs` | Bind the per-SKU/store arithmetic to a forecast for its exact protection horizon and immutable operational facts. |
| `usable_on_hand_quantity`, `on_order_summary_quantity`, `eligible_receipt_quantity`, lead/review days, safety/minimum/multiple fields | Expose measured or declared stock/policy inputs; distinguish all open orders from only timely eligible receipts. |
| `raw_order_need`, `rounded_order_quantity`, `approved_order_quantity` | Preserve shortage and rounding steps. Candidate `quantity_result` rows may have null approval while awaiting checking; successful report rows require an authorized nonnegative integer quantity. |
| `quantity_exception.key`, `reason`, `evidence_refs` | Explain each key for which a reliable quantity cannot be supported or an operational timing problem remains. An exception is not a zero order. |
| `check.check_id`, `requirement_id`, `status`, `expected`, `actual`, `evidence_refs`, `verifier` | Preserve assertion identity, expected/actual evidence and pass/fail/unavailable/not-applicable status with verifier identity. Unavailable evidence cannot become a passing check. |
| `finding.finding_id`, `statement`, `classification`, `evidence_refs`, `audience` | Separate verified findings from material limitations and internal notes from findings retained for the final report. |
| `parent_decision.checkpoint`, `decision`, `actor`, `decided_at`, `reason`, `evidence_refs` | Record parent authority and evidence for the specific checkpoint; components cannot infer authorization from a completed stage. |
| `report_claim.claim_id`, `statement`, `evidence_refs`; `report_draft.customer_draft` | Supply evidence-linked claims and customer prose for independent inspection; prose is not itself evidence. |
| `output_verification.independent_verifier`, `independence_basis`, arithmetic/claim/binding checks, `decision`, `parent_decision`, `permitted_response` | Explain independence from the producer, checks actually performed and allowed delivery. A permitted response names its kind, text and report reference; blocked/no-customer-response must not leak a purportedly valid list. |
| `evidence_record.requirement_id`, `requirement_source`, `checked_artifacts`, `check`, `evidence_mode`, `verifier_decision`, `verifier`, `verified_at`, `mock_limitation` | Tie acceptance evidence to its requirement and exact inputs. Mock evidence requires explicit mock provenance and limitation; `accepted` in a mock record remains fixture evidence only. |

## Retail identity, units and source semantics

Product and store IDs are strings in a named source namespace. The analytical key is the namespace plus product/store IDs; source display names are labels, not join keys. Preserve identifiers without inferred numeric conversion, case folding or cross-source mapping. Cross-source identity mappings require explicit evidence and versioned lineage. Identity coverage must be checked before a stock/policy join is treated as complete.

The operational demo uses `product_unit`: one unit of the identified SKU. This does not imply a common physical size or interchangeable units across SKUs. Demand, usable stock, open receipts, safety stock, pack multiples, minimum order and approved quantities must declare compatible units. Currency is not required for this MVP's quantity-only recommendation; no implicit price or budget facts are introduced.

The sales dictionary defines `Quantity` as units in a transaction. It is not automatically unconstrained demand. `Inventory_Level` is approximate stock at transaction, not the usable-stock snapshot. `Delivery_Days` measures customer fulfillment duration, not supplier procurement lead time. Preserve the distinction between transaction observations and synthetic operational stock/policy facts, including at every customer-facing limitation.

Source audit and raw hashes are recorded in [audit/reconciliation.json](audit/reconciliation.json); semantic questions and preparation constraints are recorded in [audit/source-semantics.md](audit/source-semantics.md). Manifest claims and independently measured observations are separate evidence. A manifest value must not overwrite a measured source mismatch. The old 2016 workbook and supplements are superseded for this active demo.

## Temporal, target and availability policy

The demo review/as-of date is November 30, 2025. Development uses 2022–2024 and rolling validation in 2025 through that date. Every development target horizon must finish by November 30, including targets whose origin occurs earlier. A cutoff on feature rows alone is insufficient. As-of availability requires both event time and when a value could have been known; stock snapshots, policy and receipts must be bound to their applicable as-of context.

The feature-generation/model-selection context receives an explicit allowlist of development artifacts. The raw sales CSV contains December records and must not be supplied unrestricted to that context. Raw source hashes remain in provenance without granting raw-content access. All preprocessing fit, feature definition/materialization and candidate selection must honor development availability.

Freeze the selected model, features and fitted preprocessing before reserved December outcomes are exposed. December 2025 is final unseen evaluation; score only fully observed horizons and report the actual eligible population and exclusions. The November 30 forecast is a distinct immutable artifact. December outcomes cannot change its fit, selection, input values or restocking quantities. Evaluation forecasts and the saved November 30 business forecast must remain distinguishable.

Missing product/store dates are unknown unless a documented source completeness rule supports zero for that key/date. The presence of every calendar date somewhere in the dataset does not establish complete per-key observations. Do not apply the synthetic open-order zero rule to sales. The eight source nonpositive quantity rows require investigation and a justified treatment with preserved lineage; they do not prescribe rejection or cleaning for all future submissions.

This snapshot does not choose the real demand/transaction target, censoring interpretation, nonpositive-row treatment, missing-date treatment, baseline, metric aggregation or acceptance threshold. The schema's supported product/store/day grain is an implementation boundary, not evidence of source completeness. Substantive decisions require evidence and, where they change material business meaning, approval in the task proposal. A mock fixture may use hypothetical values solely to exercise an interface.

## Receipt reconciliation and order arithmetic

Reconcile the inventory receipt summary against the detailed incoming-delivery ledger at the same product/store key, unit, status definition and as-of date. Preserve checks for duplicate line identities, unknown keys, negative quantities, invalid dates, timing and sum differences. A summary-to-ledger discrepancy remains an explicit exception until explained; do not silently prefer whichever value permits a recommendation. Retain the detailed ledger as evidence for the receipt timing used in arithmetic.

For the active synthetic demo only, the manifest declares a complete open-order ledger over all 336 product/store keys: 126 keys have incoming lines and the remaining 210 have zero open orders. Apply zero to absent keys only when the complete-ledger assertion, applicable scope, as-of date and key coverage are verified. An incomplete or unverified customer ledger has unknown missing keys, not zero. The complete-ledger assertion is a synthetic operational assumption, not an observed sales fact.

Quantity arithmetic uses the declared supplier lead time plus review interval as the protection horizon, the bound demand forecast, compatible safety stock, usable stock and timely eligible receipts. Preserve the unrounded shortage, applied minimum/multiple rules and final approved quantity so an independent verifier can reproduce every step. For a positive shortage, enforce minimum order and round upward to the permitted order multiple; a nonpositive shortage yields zero unless an explicitly approved policy states otherwise. Do not create a positive minimum order from zero demand/shortage automatically.

A receipt total alone cannot prove sufficient stock before a later receipt arrives. Check receipt timing within the horizon for intervening shortages, record timing gaps as exceptions, and withhold purportedly valid quantities when required facts are unknown. Do not infer supplier lead time from `Delivery_Days`. Do not invent lost-sales costs, service targets, budgets, stock usability rules or customer operating calendars.

## Parent checkpoints and terminal outcomes

The parent explicitly decides whether evidence permits continuation, requires bounded internal review/correction, requires material customer clarification, is awaiting proposal approval, or produces a terminal outcome. Checkpoint references preserve the requirement, consumed artifacts, checks and decision evidence. Routine EDA, feature and model decisions remain internal; only material business-fact questions and genuine blockers need customer interruption.

After initial baseline comparison, equal/worse candidate performance requires internal parent evidence review. The allowed response is bounded by the approved development limits; no stage claims validation success solely because training completed. After final holdout evaluation, any confirmed measured failure, unsuccessful bounded defect correction or exhausted recovery ends with a verified failure explanation. Parent review cannot erase a failing score.

| Outcome | Required customer meaning |
| --- | --- |
| Missing inputs / awaiting clarification | Explain which actual sources or material facts are missing/inaccessible and why needed. No analytical execution or valid order list is claimed. |
| Awaiting approval | Preserve the proposal and wait for an explicit user decision. No response is not a rejection or approval. |
| Success | Final validation passed the predeclared rule, quantities and report passed independent verification, and parent authorized the final response. Deliver one final report containing quantities, concise findings, measured results and material limitations. |
| Measured validation failure | Evaluation completed and did not support reliable output under the approved rule/scope. Preserve actual scores, checks and bounded review evidence. No valid recommendation list is delivered. |
| Execution failure | A required action or evidence production failed, so reliable results could not be established. Identify the failed stage and supported reason without fabricating a measured validation result. No valid recommendation list is delivered. |

Failure wording states that this MVP could not produce a reliable solution with the supplied data and scope. It must not claim that the customer's problem is universally impossible. A failure response still requires evidence/claim verification and parent authorization.

`failure_detail` records the failed `stage`, a supported `reason`, this MVP's `scope_limitation` and evidence. Execution failures require `error_code`; it classifies an operational failure and must not substitute for a measured model score:

| Error code | Meaning |
| --- | --- |
| `plugin_unavailable` | The required installed capability cannot be reached or used. |
| `unsupported_integration` | The actual host/interface cannot support the required approved execution. |
| `inaccessible_input` | A referenced required input cannot be read. |
| `invalid_code` | Generated or submitted analysis code is invalid for the attempted execution. |
| `timeout` | The permitted operation elapsed without completing. |
| `cancelled` | Execution was explicitly cancelled. |
| `budget_exhausted` | A declared resource/recovery limit was reached. |
| `runtime_error` | Execution failed for another supported operational reason. |
| `integrity_error` | A hash, version, binding or artifact-integrity requirement failed. |

## Representative examples and verification limits

- [Approved execution](examples/approved_execution.json): one explicitly hypothetical approved task/input/proposal binding.
- [Missing inputs](examples/missing_inputs.json): raw customer source remains missing; no demo substitution.
- [Successful analysis](examples/successful_analysis.json): mock measured results and hypothetical verified quantities.
- [Measured validation failure](examples/validation_failed.json): mock failing score and bounded parent review; no valid list.
- [Execution failure](examples/execution_failed.json): mock operational failure without invented scores or recommendations.

These are small component fixtures for the same business task, not a scenario dataset or implemented pipeline. Structural checks may establish that each example conforms to this draft and its cross-reference constraints. Only genuine upstream artifacts, independent verification and native acceptance can establish real integration success. See [COORDINATION.md](COORDINATION.md) for ownership and revision status.

## Pending analytical policies and verification limits

A proposal may leave nonmaterial analytical choices pending without asking the customer to select algorithms or treatments. The agent may finalize those choices during approved execution, with evidence, before dependent modeling/freeze. This configures execution of the same goal, not a second task-definition stage. Material gaps remain blocking and require renewed proposal/signoff. Concrete approved target/acceptance policies cannot silently change. Real thresholds, target/status/return treatments and completeness assumptions are not selected here.

A defect recheck with outcome execution_failure requires empty scores. Retain the last valid measured final result for diagnosis, record the failed recheck and a typed failed-stage artifact, and issue an execution-failure explanation. Do not turn an unresolved execution defect into confirmed model underperformance.

Contract checks compare declarations, numeric intermediates and immutable graph bindings. They cannot prove external data/model bytes exist, timing declarations are truthful, an LLM call occurred, or the named verifier is independent. DSC-26 and the producing/verification owners must check genuine artifacts in the supported environment. No parent state machine, transport, training or report-delivery implementation is supplied.

## Stage permission and discovery boundary

`stage_request` carries the same approved task binding plus `execution_contract_ref`, stage, attempt, a parent authorization, the released input references, remaining limits, issue time, deadline and task/run output namespace. `stage_result` binds that exact request/attempt/contract. Requests are bounded execution of the already approved task. They are not a second task-definition stage. A stage declaration cannot establish that the host actually enforces file isolation or cancellation; DSC-26 must supply that proof.

Missing-input/material-fact outcomes require actionable gaps and evidence. Measured validation failure requires an exact failed final-validation reference. Native execution failure requires typed error detail and evidence. Startup failure before initialization is an adapter/runtime failure; it does not establish that Data is missing or that a model failed. Partial outputs from an unsuccessful stage are diagnostic only and cannot satisfy the next checkpoint without separate verification.

Pre-customer engineering discovery is outside these customer execution messages. DSC-26 may retain standalone native logs and a discovery record naming probe purpose, host/version, exact command, timestamps, exit/error results and evidence hashes. Never invent customer approval to serialize a discovery probe. Customer-scoped capability results still bind to approved execution. A supported capability declaration requires genuine proof of the actual host/Data identity, accepted skill attachment, native thread/turn, code/output, retrieved artifact bytes and their task/input/run bindings; nonempty references alone do not prove support.

## Acyclic numerical approval and report fidelity

Persist candidate quantity artifact version 1 with null approved quantities and no parent approval. An independent `evidence_record.checked_artifacts` binds to the exact candidate version/hash; its check retains expected/actual quantities and verifier decision. Parent approval cites that evidence. Persist approved quantity version 2, referencing version 1 through `candidate_quantity_ref`, with identical candidate inputs/intermediates/exceptions and populated approved quantities. The report consumes version 2 and preserves its exceptions and rows. This avoids requiring a check to hash an artifact that already embeds that same check. A changed candidate requires a new independently checked version, not an edited old approval.

Optional `product_name` is display metadata only. Include it only when the versioned source/mapping evidence supports the exact ID; otherwise omit it or use null. The report copies approved names/IDs; humanizing cannot infer or invent names.

The target's missing-date policy has separate branches: unknown/masked observations, zeros supported by verified complete extracts, or an explicit disclosed synthetic-zero scenario assumption. The synthetic branch requires `zero_assumption_ref` linked to a synthetic assumption in the approved task. It leaves source completeness unverified and must remain visible in limitations; it never turns a synthetic scenario into observed demand. A pending analytical policy may be resolved in preparation with `policy_evidence_refs` under the unchanged approved task, while material business facts remain subject to renewed proposal/signoff.
