# DSC-27 preparation component

This component implements preparation, alignment, internal EDA, initial features
and lineage for the one retail MVP. It owns only `src/suiroai/preparation/`,
`tests/preparation/` and `docs/preparation/`, as reserved by the architecture
[ownership map](../architecture/OWNERSHIP.md). It branches from `nightly`
`83f134fb7674de64d7f3a6b62f984bb6486ec81d`. Shared contracts remain the
unchanged DSC-24 `0.1.0-draft.3` snapshot. No DSCraft, dependency, parent,
model-selection, recommendation or report implementation is changed.

The current [DSC-27 issue](https://linear.app/gr3enarr0w/issue/DSC-27), DSC-24,
DSC-3, DSC-26 and the linked single-case implementation document were read via
the Linear connector on October 17, 2026. DSC-27 reported update time
`2026-10-17T04:47:39.707Z`. Its issue discussion was empty. The actual local
sales dictionary, generation manifest, shared-locations manifest and operational
headers were inspected read-only. Their supplied semantics guide implementation;
they are not runtime acceptance results. No Drive read or Miro modification was
needed or claimed.

## Execution boundary

Import performs no I/O. There is no standalone CLI, source autodiscovery,
independent runtime, Data API, Code Interpreter substitution, modeling or
customer-progress callback. The deterministic kernels are for the approved
analytical task executed through the existing [DSC-26 adapter](../integration/ADAPTER.md).
Submission and read-only understanding must never call them.

Both execution kernels validate the shared execution/request schemas, exact
task/run/reference bindings, preparation stage, allowed actions, parent proceed
authorization and a trusted caller's permit before parsing bytes. A record
claim alone is not authority. `parent_permits(request, execution)` is an
invocation-scoped bridge to the grant already obtained by the parent; it is
**not** an instruction to consume the adapter's single-use
`parent_permits(stage_request_ref)` callback again. The trusted parent owns
customer sign-off/version binding, expiry, remaining budgets, supported-host
approval, isolation and stage transitions. The adapter remeasures releases and
authenticates result decision claims before publishing.

1. In approved preparation only, the trusted non-model controller calls
   `partition_sales` with the approved raw source bytes. It checks actual hashes
   and calendar scope, computes full-record identity **before** normalization,
   and creates physically separate development/reserved CSV bytes. It does not
   delete or modify source files. Full raw counts, row ordinals, duplicate links
   and hashes are retained in a **controller-only** audit.
2. The parent stores the reserved CSV and full partition audit outside native
   development access and releases only the measured development CSV,
   dictionary, inventory, receipts and policy to the supported Data task. Its
   development request must omit the raw CSV, reserved CSV and full audit from
   `released_input_refs`. `prepare_development` rejects raw release and future
   rows even if a caller updates their byte hash. The small trusted partition
   receipt binds development bytes to the raw source without holdout outcomes.
3. `prepare_development` reconciles its own exact duplicate identities, checks
   transaction grain and operational alignment, and returns actual daily records,
   internal EDA/checks, quarantine, mappings, sensitivity totals and row lineage.
4. `build_result` serializes a private shared `preparation_result`, adapter byte
   manifest and stage envelope. The controller's hash-bound reserved receipt and
   partition-audit reference must accompany the opaque reserved reference; no
   reserved bytes/values enter the development worker. Its parent decision is a
   proposal supplied by the caller, authenticated through DSC-26's trusted
   candidate-review callback. The stage envelope leaves `parent_decision` null.
   Completed preparation is not a model-readiness or customer-delivery decision.

The genuine controller-prelude/release/adapter path has not been exercised with
an approved customer packet. The synthetic native mechanism on `nightly` does
not itself authorize a real preparation run. These integration dependencies
remain explicit acceptance waits; no issue status is changed by mock tests.
The pinned shared validator rejects derived development releases, and a real
retrospective source information-availability date is unverified. Consequently
real result serialization requires genuine timing evidence and fails closed for
the current unverified source pending owner-supported resolution; see
the exact [interface blockers](INTERFACE.md#current-shared-release-blocker).

## Analytical decisions encoded before step6

The target is positive **Quantity** summed on completed transaction lines at
Product_ID/Store_ID/calendar-day grain. It represents gross recorded completed
units on observed record days, not latent demand or established complete daily
sales. Positive completed lines with a return flag remain gross units; returned
status, cancellations, processing and shipped lines are excluded. There is no
known return date or returned-unit quantity for a net target. Nonpositive
quantities are quarantined with their original row identity. Positive revenue
never supplies missing/invalid quantity.

The EDA packet retains status counts, return flags, positive quantity range and
median, retained/excluded line counts and unit totals for completed-only,
completed excluding return flags, completed plus shipped, completed/shipped/
returned, noncancelled and all-positive alternatives. No measured winning
alternative is selected here. An explicit approved target cannot be silently
replaced: pending analytical policy permits this investigation; a different
defined approved policy is rejected.

Only verified exact duplicate record excess is removed, never shared Order_ID
lines. Conflicting shared Transaction_ID values fail grain checks. Cosmetic
whitespace, Unicode and status casing normalize after exact deduplication.
Product/store display mappings normalize cosmetic differences; noncosmetic
conflicts are retained as ambiguous and their display name is null rather than
invented. Blank names do not erase a unique observed nonblank mapping, and their
missing counts remain in the audit. Optional category/geography text receives
the same cosmetic normalization and conflict checks without guessing synonyms.
Identifier joins remain independent of display names.

Each observed record day is retained, including an excluded-only day whose
chosen recorded target is zero. `complete_daily_sales=false` remains explicit.
Absent dates are omitted, never silently inserted as zero. Coverage is measured
per series over the approved development calendar; global coverage cannot
establish per-series completeness. Observed-day pooling is a bounded fallback
for development. Unsupported zero-fill is calculated only as an internal
sensitivity denominator, labeled hypothetical; it produces no training rows.
Complete protection-period targets remain unavailable without actual per-day
observation/completeness evidence. Modeling owns whether a supported daily
forecast is achievable; this component never claims it is.

Only known calendar and product/store identity features are enabled initially.
There are no outcome lags because source status/return revision timing is
unverified. Identifiers use immutable training-fold vocabularies, with unseen
IDs encoded to -1; fitting on validation rows is rejected. Inventory_Level,
realized customer Delivery_Days, end-state status/returns, revenue, current
operational snapshots and future outcomes are absent from predictors.

Operational snapshots/policies align once per key after uniqueness, key
coverage, units, provenance and November 30 date checks. Receipt lines aggregate
before alignment; the original expected dates remain available for downstream
timing arithmetic. Explicit complete synthetic ledger evidence is required
before treating absent lines as zero. On_Order_Qty must equal the receipt sum;
it is a reconciliation field, never an additional receipt. No November snapshot
is broadcast into earlier rolling folds.

See [INTERFACE.md](INTERFACE.md) for artifact layout and availability limits,
and [VALIDATION.md](VALIDATION.md) for executed mock checks and acceptance waits.
