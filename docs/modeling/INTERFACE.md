# DSC-28 consumer interface

## Ownership and version

The published DSC-3 ownership map on source `nightly` reserves exactly
`src/suiroai/modeling/`, `tests/modeling/`, `docs/modeling/` for this role.
All component code stays there. Existing schema/validator snapshot hashes remain
unchanged. A fresh path/snapshot ACK was requested from the actual architecture
owner; no reply was observed at this documentation cutoff, so none is invented.
The published reservation and agreed draft.3 release remain the development base.

The user explicitly authorized a dedicated branch, PR and consolidation into
`nightly`, and then requested subagents. Independent coding ownership was:

| Owner | Exclusive files |
| --- | --- |
| Modeling lead | Common types/metrics/models, prepared-data/inference adapters, shared-record mapping, exports and documentation |
| Initial evaluation subagent | `evaluation.py`, `test_evaluation.py`; later `test_records.py` and read-only cross-module review |
| LLM feature subagent | `features.py`, `test_features.py`; later `test_feature_records.py` and read-only adapter review |
| Frozen validation subagent | `frozen.py`, `test_frozen.py` |

These were implementation assignments within one task, not runtime autonomous
agents. Core dataclasses, metrics and fit/predict signatures were agreed before
submodule writes. Shared schema and parent changes remain with DSC-24/10.

## Calculation types and preparation

`Window(key, origin, horizon_days)` has a namespace/product/store tuple,
first target day `origin + 1`, last day `origin + horizon_days`.
`Example(window, features, actual, available_on)` contains immutable ordered
numeric/null features and a complete gross-unit horizon label. For direct
synthetic examples only, omitted availability means target-end date; genuine
DSC-27 adapters require explicit availability evidence. Never treat omitted
transaction dates as observed zero-demand days.

`RollingFold(fold_id, training, validation, training_end=None)` uses one common
validation origin. Training target/information ends must precede its training
cutoff; validation targets lie in January–November2025. Series/horizon eligibility
must exist in training. Feature options share exact training/validation windows,
labels and label-availability dates. Each origin's features must already have
been calculated from permitted information before constructing an Example.
The typed vector cannot by itself prove that historical availability.

Agreed DSC-27 data payloads:

```text
dsc27-daily-v1:
  source_namespace
  rows: Product_ID, Store_ID, Order_Date, target_quantity,
        observed_record_day, complete_daily_sales, source/target/excluded lineage

dsc27-initial-v1:
  source_namespace
  rows: source_namespace, Product_ID, Store_ID, origin, target_date,
        target_weekday, target_month, target_day_of_year, target_weekend
  origin_rows: source_namespace, Product_ID, Store_ID, origin=2025-11-30
  predictor_columns, population_rule, no_fitted_transformations
```

Current DSC-27 rows declare incomplete daily sales and unknown historical
status/return availability. To create complete-demand labels, a supported future
preparation result must additionally supply actual completeness evidence and
`target_available_date` on each covered day. Consumers must not add those fields
merely to make evaluation run. `DailyView.horizon_target` reports unavailable
when evidence is absent; it never changes the upstream target policy.

`build_examples` aligns exact product/store/origin rows. Noncalendar fields need
explicit `latest_information_available_date <= origin`; calendar-only initial
fields are known by definition. Validated stateless additional features can be
assigned their origin availability by the caller based on retained definitions
and materialization evidence, not by an arbitrary metadata assertion.

## Feature generation and materialization

`generate_feature_proposal` requires the execution, preparation, exact shared
initial record/reference/parent decision, feature-stage request, context
availability, released DevelopmentArtifacts, original numeric fields, injected
LLM callable/model/time and provenance. The trusted parent authenticates the
stage request; the component checks its exact bindings, limits and release list.
Post-step6 error-summary references come from that new release. They are not
inserted into the immutable earlier preparation record.

Every DevelopmentArtifact hashes canonical JSON and has this private structured
format, which deliberately excludes raw rows, paths and arbitrary prose:

```text
format: dsc28-development-summary-v1
binding, run_id, source_namespace, development_end
summary_type: task_context | eda | development_errors | initial_features
feature_fields: explicitly prepared numeric feature IDs
statistics: [{name, value, period_start, period_end, optional feature/Product_ID/Store_ID}]
optional task_goal: retail_restocking_forecast
optional target_policy: positive_completed_gross_units
```

Task context, EDA and development-error summary types are all required. Statistics
are bounded to counts, minimum/maximum/mean/median, zero/null counts, feature
counts and development MAE/bias/RMSE. Their chronology ends by November30. Hashes
and structured dates establish byte consistency, not genuine historical origin;
DSC-10/26 must verify actual development lineage and isolation.

Each LLM definition uses the unchanged shared `feature_definition` shape:
meaning in name, source refs/fields, event/availability basis, origin timing,
rationale, training-only fit scope, and executable declarative expression JSON:

```json
{"op":"calendar","part":"weekday_sin"}
```

Calendar parts include year/month/quarter, weekday/day-of-year/week, weekend and
month/weekday sine/cosine. Arithmetic uses `add`, `multiply`, or `ratio` over two
released initial numeric fields. Ratio must declare `zero_division: "null"`.
Null inputs propagate null. No eval, arbitrary code, outcome lag, learned feature
transform or future-target input is admitted. Additional definitions remain
hypotheses until comparison. Learned imputation/scaling belongs to each training
fold, recorded by the fitted model; final inference reuses fixed parameters.

`materialize_features` requires rows containing exactly Product_ID, Store_ID,
origin and those original numeric fields. It retains original values/order and
adds feature_id columns. `feature_records` rechecks the original prepared bytes,
recalculates outputs, compares definitions to actual saved LLM response, verifies
prompt/response hashes and writes shared proposal/result records with lineage,
availability, checks and original feature-set reference. A mock at any input
remains mock throughout outputs.

## Fitting, comparisons and handoffs

`CandidateSpec(candidate_id, model_kind, feature_set_id, parameters, rationale)`
accepts `past_mean`, `mean`, `ridge`. Ridge's positive alpha is predeclared.
`evaluate_initial` and `compare_candidates` return measured scores/predictions,
per-fold fitted payloads, counts, selection facts and `parent_verified=False`.
They do not manufacture parent decisions. Component fit/time limits must be
lower than or equal to the run's remaining limits.

`persist_candidate` takes explicit ordered `feature_names`, complete final
training examples and a remaining fit/time budget; it returns a contract-shaped
candidate plus immutable fitted model. Save/refit candidates before the final
freeze, never after holdout access. The original candidate remains byte-identical
in step8. `predict_november30` requires the saved candidate, exact feature names,
unique available Nov30 features and development-eligible policy horizons.

`initial_record`, `feature_records`, `comparison_record`, `final_record` serialize
shared DSC-24 records. Before publication use the full owner's handoff validator
and existing adapter's trusted parent review. Component `validate_record` checks
are schema checks, not source authenticity, actual approval or stage acceptance.

## Frozen forecast and recommendation adapter

`freeze_bundle` returns `bundle_ref`, exact shared `frozen_result_ref` and the
shared `frozen` object. The exact object bytes hash to `digest(frozen)`. Pass
`bundle_ref=freeze["bundle_ref"]` to `comparison_record`; its measured
`immutable_freeze_binding` comparison check retains the bundle and manifest refs
for the parent's exact final-stage release. Real publication requires this ref.
The bundle also fixes expected observation count and minimum coverage fraction.
The acceptance rule must equal the approved execution rule. Supported final
gates are absolute upper/lower bounds on equal-series MAE or bias, `product_unit`,
with one named final population. WAPE and baseline-improvement acceptance gates
are rejected before freeze; they cannot silently become measured model failures.
WAPE remains available as justified development diagnostics.

The saved forecast has task/run/execution bindings, `as_of_date=2025-11-30`,
`rows=[Window.payload() + predicted]`, optional `daily_forecast`, and
`recommendation_ready`. The producer must explicitly supply daily predictions;
an aggregate-only forecast remains valid for horizon scoring but blocks quantity
consumption. Daily rows must be unique, cover every protection day and sum to the
frozen evaluated horizon totals:

```text
key: {source_namespace, product_id, store_id}
date: ISO calendar day
quantity: nonnegative product units
quantity_unit: product_unit
as_of_date: 2025-11-30
latest_information_available_date: <=2025-11-30
```

DSC-29/30 agreed callbacks receiving verified raw bytes:
`forecast_daily_rows(bytes) -> daily rows` and `scope_keys(bytes) -> exact keys`.
No consumer interpolation is permitted. Separate scope bytes use
`dsc28-forecast-scope-v1`, bound task/run, and `keys` with the same identity shape;
persist with `put_payload` and include its ref in frozen development inputs.
The parent binds policy protection periods and approved scope; the verifier
checks source/forecast/arithmetic independently. Readiness is an arithmetic
property, not permission or proof of a statistically validated daily trajectory.

`materialize_reserved_targets` verifies the bundle and exact parent final-stage
request before reading December `dsc27-daily-v1`. It returns complete observed
Example labels plus original source and derived target refs. `score_frozen`
compares the registered derived bytes to actual values and retains the original
source ref for shared final validation. Missing horizons lower frozen coverage;
zero eligible horizons have no scores and cannot form a measured final-result
record. The stage failure variant carries that execution failure instead.

`record_defect_recheck`/`record_failed_defect_recheck` retain a demonstrable defect,
correction refs and prior parent authorization. `shared_defect_recheck` projects
only the existing shared defect fields. At most one correction is allowed even
if a looser parent ceiling exists. It cannot change model/features/rule/forecast,
original source or chronology; corrected measured evidence may pass or fail,
while operational failure has no fabricated new scores. `finalize_validation`
classifies internal review/terminal outcome only. The parent limits reviews and
authenticates authorization; DSC-29/30 draft and verify the final explanation.

## Native integration acceptance waits found against nightly

On `ee16115`, DSC-10's final release allowlist does not yet include the immutable
DSC-28 bundle, exact frozen-result object, plan or rule refs needed by
`verify_frozen`. Its feature-stage release also does not yet provide a trusted
registration path for newly derived development-error summaries and their
availability, or release the upstream typed record refs needed by the feature
consumer. Requests were sent to the actual parent owner; this branch neither
edits the parent nor bypasses those restrictions. A complete native handoff must
resolve these owner-level paths before real execution. Mock/direct component
calls are not native acceptance.

The current parent also rejects any failed/unavailable check on a purportedly
passing final record. Use full frozen coverage (the default 1.0); a looser
component coverage threshold does not authorize parent acceptance when the
fully-observed check fails. Parent decisions remain controlling and bounded.
