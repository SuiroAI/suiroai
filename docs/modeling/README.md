# DSC-28 modeling and additional features

This implements the modeling component for the single retail restocking MVP.
It extends `nightly` at `83f134fb7674de64d7f3a6b62f984bb6486ec81d` and consumes
DSC-24 `0.1.0-draft.3` without shared schema, dependency, parent, raw-data or
DSCraft changes. Before publication it was refreshed against `nightly`
`ee16115`, including the actual DSC-27 preparation and DSC-10/25 components. The live [DSC-28 issue](https://linear.app/gr3enarr0w/issue/DSC-28)
was read through Linear on October 17, 2026. Its requirements remain the runtime
acceptance criteria; synthetic component checks do not close the issue.

## Component sequence

1. `read_development` reads only the exact, measured DSC-27 development artifact
   permitted by preparation metadata. `DailyView` retains missing/incomplete
   dates as unknown. `build_examples` requires every target day to have
   completeness evidence and explicit label availability. Protection horizons
   come from the approved supplier lead time plus review policy, never customer
   fulfillment `Delivery_Days`.
2. `evaluate_initial` compares a `past_mean` demo comparator and the initial
   model on identical windows and original features. The comparator is a
   historical per-key/protection-horizon mean, not a verified customer process.
   MAE/bias are reported per series and as an equal-series average. WAPE is
   available for positive-denominator, same-namespace/SKU pooled units only.
   Signed bias is prediction minus actual; MAPE is not used. Parent verification
   is required for all branches; equal/worse remain distinct internal reviews.
3. `generate_feature_proposal` calls an injected, supported LLM once after the
   reviewed step6 record. The parent releases structured task, EDA and
   development-error summaries with actual byte hashes and development-only
   availability metadata. The function never reads ambient files. It retains
   prompt/response/model/time provenance. `materialize_features` executes only
   the bounded declarative definitions, preserving original columns and rows.
   See [INTERFACE.md](INTERFACE.md) for exact inputs and limitations.
4. `compare_candidates` measures a declared shortlist on identical folds,
   populations, origins, labels, horizons and metrics. Each model/feature option
   counts against the candidate/fit budget. Put the original reference first:
   ties retain the earlier declared candidate. Candidate rationale is required.
   `records.comparison_record` verifies the declared ranking policy, measured
   winner and original/augmented options. Proposed features need not win.
5. `persist_candidate` fits the final candidate only on development examples
   whose complete labels and information dates end by November30, retaining
   fold-specific preprocessing, explicit ordered feature names, configuration
   and measured prediction evidence. It consumes a separately supplied remaining
   fit/runtime budget. Reuse the exact original initial candidate in step8;
   do not replace its references. `predict_november30` loads saved fitted JSON,
   checks exact feature order, population and availability, and never refits.
6. `freeze_bundle` persists selection, fitted model/preprocessing references,
   plan, acceptance rule, fixed expected population/coverage and a separate
   November30 forecast. Every reference is immutable through DSC-26's existing
   `ArtifactStore`. `materialize_reserved_targets` requires the post-freeze
   final-stage release before reading original December bytes. Derived targets
   preserve the exact original reserved source reference. `score_frozen` reads
   the saved predictions and scores only fully observed December horizons.
7. Failed measured validation returns internal parent review. A demonstrated
   scoring/runtime defect may receive one correction within the parent's lower
   limit. Model, feature, rule, forecast, source and chronology bindings stay
   fixed; successful or unsuccessful correction ends recovery. Genuine failed
   scores become `validation_failed`; absent reliable scores or operationally
   failed correction become `execution_failed`. There is no runner-up, tuning
   or customer list on failure. DSC-29/30 own customer wording and delivery.

`records.py` produces unchanged shared initial/feature/evaluation/final records.
Required parent fields are supplied decisions, not authenticated worker authority.
DSC-10/26 must independently adopt them through the existing trusted review
callback and authenticate prior recheck authorization before publication.
No function here advances parent state, dispatches a custom runtime, messages a
customer, calls a fictitious Data API, or authorizes recommendation delivery.

## Models and bounded execution

The small reference implementation uses standard-library deterministic `mean`
and ridge regression with training-only median imputation and standardization.
`past_mean` is the separately labeled baseline. There is no dependency change.
Classical DSCraft forecasting was inspected in the architecture review: its
observation-count backtest/refitting does not implement this calendar-window
frozen interface, so it is not silently substituted. Neural training is outside
this assignment. These candidates demonstrate the component, not a claim that
one algorithm is appropriate for currently incomplete real targets.

A small justified shortlist can be ridge on original features, ridge on the
eligible augmentation, and a simpler mean if justified. Predeclare configurations,
order, primary metric/direction/tie tolerance, fits and time limits before running.
Do not loop on suggestions. The parent accounts for earlier attempts, all rolling
fits, final refits, LLM calls and recovery; component budget checks cannot replace
that run ledger. Time checks are cooperative around bounded calls; the native
adapter must enforce deadline/cancellation on blocked external LLM/model calls.

## Current evidence and genuine waits

Tests use explicitly mock approvals, artifacts, LLM responses, complete targets
and parent decisions. [COMPONENT_EVIDENCE.json](COMPONENT_EVIDENCE.json) contains
actual numerical calculations over synthetic fixtures with an explicit mock
limitation. It is not evidence of genuine DSC-27/Data execution or customer demand
accuracy. Records tests check shared schema serialization and byte references;
they do not assert that a fabricated upstream graph is a genuine approved run.

The DSC-27 owner agreed `dsc27-daily-v1` and `dsc27-initial-v1` on October17.
Its current sparse daily artifact omits missing dates, declares daily completeness
false and cannot establish historical status/return availability. No full-demand
label, model comparison, actual November30 forecast or final customer validation
is claimed here. Unknown dates are never zero-filled. Lack of eligible complete
horizons yields unavailable evidence and eventually an execution failure through
the parent, not invented measured underperformance. This is a current source and
scope limitation, not a claim that reliable restocking is universally impossible.

Real acceptance still needs customer approval, genuine versioned preparation,
resolved target/completeness/availability policy, runtime-isolated development
summaries, parent stage reviews, measured comparison, frozen selection/rule and
reserved outcomes. DSC-27 additionally reported owner-level native release
validation/availability blockers; this branch does not bypass or modify them.
A hash/date declaration cannot prove isolation, historical availability or true
provenance. Only supported-host evidence and independent parent checks can.

No forecast metric alone establishes stockout, profit or inventory-cost benefit.
Overlapping horizons are dependent; these calculations make no significance
claim. Signed errors and absolute errors retain product-unit semantics; pooled
cross-SKU WAPE is disallowed.

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests/modeling -v
PYTHONPATH=src python3 -m unittest discover -s tests/contracts -q
PYTHONPATH=src python3 -m unittest discover -s tests/integration -q
```

No real source file is required or modified by these checks. Generated execution
artifacts belong under the parent's approved producer namespace, excluded from
source commits. Only source, tests and component documentation are committed.
