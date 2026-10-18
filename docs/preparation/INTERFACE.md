# DSC-27 to DSC-28 handoff

DSC-28 acknowledged these component-local JSON formats through the existing
owner coordination channel on October 17, 2026. They are byte artifacts referred
to by the shared draft.3 schema, not new shared schemas. Consumer agreement does
not establish real execution or native acceptance. Application ownership was
already reserved by DSC-3; the implementing session requested explicit owner
confirmation and records its response in VALIDATION.md.

`build_result` returns `{record, stage_result, artifacts, artifact_manifest}`.
Each artifact contains `{ref, path, encoding, data}`; data is actual immutable
UTF-8 JSON bytes. Write those paths only inside the adapter's output root, then
write `artifact-manifest.json` from `artifact_manifest` and `stage-result.json`
from `stage_result`. These transport names belong to DSC-26. The adapter
remeasures byte and canonical-record hashes, validates the complete handoff,
and asks the parent to review its private candidate. The reserved CSV and full
partition audit are measured external artifacts held by the controller.

| Artifact | Format and content | Release |
| --- | --- | --- |
| `prepared-development.json` | `format: dsc27-daily-v1`; source_namespace, rows, target_policy, quantity_unit, per-series coverage, mappings, label_availability | Development |
| `initial-features.json` | `format: dsc27-initial-v1`; source_namespace, rows, key-only origin_rows, predictor_columns, no_fitted_transformations, target_availability | Development |
| `development-checks.json` | `format: dsc27-checks-v1`; actual audit, limitations, evidence mode, scope | Development |
| `development-row-lineage.json` | Original raw source ref, all development record ordinals/record hashes/duplicate links, quarantine, daily aggregation source membership, operational source-row references | Internal development evidence; omitted from LLM context allowlist |
| `as-of-operations.json` | `format: dsc27-operations-v1`; one row per key, snapshot, policy, original due-dated receipt lines, reconciled summary, namespace/as-of metadata | As-of operations; never historical feature context |
| Reserved CSV | Original columns plus `_source_record`, `_duplicate_of`; duplicates retained for independent frozen-rule evaluation | Parent only until frozen final evaluation |
| Full partition audit | Raw byte hash, full raw/distinct/duplicate counts, partition counts and all raw row identity links | Controller only; excluded from development |

Daily rows contain Product_ID, Store_ID, Order_Date, integer target_quantity,
observed_record_day=true, complete_daily_sales=false, source_records,
target_source_records and excluded_source_records. Row ordinals start at one
after the CSV header and count parsed CSV records, not physical text lines.
`source_namespace` is the approved execution task ID. The artifact itself binds
to task/input/proposal/run versions through the shared result and measured ref.

Initial historical feature rows contain source_namespace, Product_ID, Store_ID,
origin (one day before target_date), target_date, target_weekday (Monday=0),
target_month, target_day_of_year and target_weekend (0/1). There is no target,
status, return, observed-day mask or operational value in the feature matrix.
`origin_rows` contains namespace, key and `origin=2025-11-30` for the separate
as-of forecast population; it contains no outcomes or fit data.

Historical feature rows omit each key's first observed day, so a future order
cannot introduce a known historical forecast population. The omission count
and population rule are explicit in the feature artifact; daily labels retain
all observed days.

The modeling owner constructs protection-period forecasts and stores the November 30
forecast separately. This role does not generate forecasts.

`fit_categories(training_rows, training_end, validation_start)` checks every
training label date against training_end and returns a frozen vocabulary.
`transform_categories` reuses it, without fit/update, and codes unknown IDs -1.
Use an independent fitted vocabulary per fold. Calendar values need no learned
transformation. `horizon_target` rejects repeated product/store/day grain and
returns unavailable (`None`) for any absent/incomplete day or target end beyond
November 30. Future completeness-supported records must supply explicit
completeness evidence references; the current prepared source does not.

MOCK availability uses the fixture's declared temporal bounds and establishes
no source revision-time facts. The required draft.3 information-availability
date cannot truthfully be inferred from the November 30 event cutoff for real
retrospective labels. `build_result` therefore requires genuine upstream timing
evidence for nonmock handoffs and fails closed when it is absent. It can consume
an existing shared `evidence_record` through `information_availability_evidence`:
requirement `DSC-27-information-availability`, real/accepted/pass, exact task/run
binding, checked development-source ref, supporting evidence refs, and a check
actual value that is an ISO date bounding extract information at/before cutoff.
The evidence's exact ref enters lineage; the parent authenticates verifier,
evidence bytes and date meaning. This component never authors that authority or
accepts a mocked timing record as real evidence. No such evidence was supplied
for the current source. The gap was raised explicitly to DSC-24 rather than
silently redefining its field.
The knowledge-time check remains unavailable in mocks, label availability
limitations are embedded in both artifacts, and outcome lags remain disabled.
Reserved dates are conservative contract bounds (December 1–31), bound to the
actual split hash; they are not a claim of complete per-series observation.
Operations use November 30 availability even when a known planned receipt's
arrival date is in December.

Only prepared daily data, initial features and development checks enter
`development_context_allowlist`. The parent must enforce exact measured refs
and inspect actual content before release. Do not pass the complete preparation
packet/raw CSV/controller audit/reserved bytes to feature generation. Initial
features precede step6; step7 LLM-generated additional features belong to DSC-28.

## Current shared release blocker

The complete mock raw-to-development handoff exposed a draft.3 validator rule:
preparation requests may release only approved `execution.source_refs` or
internal typed records. The controller-derived development CSV is a new measured
byte artifact, not a new customer input; its raw source remains approved. The
current validator nevertheless rejects that derived release before dispatch.
Releasing the unrestricted raw source instead would violate holdout isolation.
This gap was reported to DSC-24, DSC-26 and DSC-10 through owner coordination.
No consumer changes shared rules or adds an invented permission artifact.

A regression retains that real-interface rejection. A separate explicitly
artificial MOCK approval lists a sixth, already prepared CSV as a source solely
to exercise result serialization, adapter retrieval and exact parent-candidate
review. That artificial fixture is **not** the genuine supplied-raw workflow,
and does not resolve or count as acceptance of the production release path.
The separate missing information-availability evidence also blocks the current
source's real result serialization. Neither issue is bypassed by a mocked parent
callback. These are evidence-dependent gates, not hardcoded validity judgments
about every future input.
