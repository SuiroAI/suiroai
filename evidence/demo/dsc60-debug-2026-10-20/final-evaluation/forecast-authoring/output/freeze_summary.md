# Pre-evaluation freeze

Ready within the checked generation scope. This package freezes the already selected shrink26 and the original recent13 analytical baseline at **2025-11-30**, for the same 336 sorted current product/store policy keys. There was no model discovery, customer rewriting, shrink26 refit, reselection, or execution of the supplied development programs.

The selected model's source and copied SHA256 remain `93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e`. All 13 supplied files are retained byte-for-byte in `assets/`, with their roles and exact hashes bound in `protocol.json`. The protocol was written and verified before forecast generation; reruns require the identical protocol. Original code and plan statements are retained as historical evidence; the current freeze rules are explicit in the protocol.

## Frozen definitions

The target is positive noncancelled recorded product units across store-attributed channels, including processing and returned orders. Exact full-row duplicates are removed; Transaction_ID conflicts cause a stop, while repeated Order_ID lines remain. Status is stripped and lowercased. No returned-stock credit is inferred. The development input contains 17,406 raw rows, 17,364 after 42 exact duplicates, and no conflicting transaction IDs. The target includes 16,505 rows, excluding 8 nonpositive-quantity and 851 cancelled rows (859 distinct exclusions).

Any deduplicated store transaction establishes an observed recording day, before target filtering. Missing product contributions on observed days contribute zero recorded units; absent store-days remain unknown. Observations and date presence do not establish complete demand. Supplied final statuses lack knowledge timestamps; exact historical status availability cannot be certified. The population is conditional on current assortment, with no historical active-assortment claim.

recent13 uses the 13 complete Monday–Sunday calendar weeks **September 1–November 30**, not the last 13 observed weeks. The mean omits unknown store-weeks; it retains a zero when a known store-week has no eligible product contribution. Week starts must be strictly later than each key's first transaction. There are 4,340 known and 28 excluded key-weeks out of 4,368 possible; each key has 12 or 13 known weeks. `baseline_exclusions.csv` lists each excluded key/week and reason, and `baseline_coverage.csv` reports every key's denominator. An alternate scalar reconstruction matched the original panel calculation exactly for every key. No replacement baseline or selected-model reconstruction was fitted.

Both methods use a constant saved weekly rate divided by seven each day, without seasonal adjustment. Full-precision float64 rates are retained in `frozen_rates.csv`; forecast CSVs use 17 significant digits, not display rounding.

## Deliverables and checks

| File | Scope | Rows |
|---|---|---:|
| `fixed_forecasts.csv` | Two methods × 336 keys × four weeks | 2,688 |
| `daily_forecasts.csv` | Two methods × 336 keys × all 31 December days | 20,832 |
| `coverage_forecasts.csv` | Two methods × 336 supplied lead-plus-review horizons | 672 |

All rows have as_of_date and origin November 30. Primary weeks are December 1–7, 8–14, 15–21, and 22–28. Coverage diagnostics sum the same trajectory from December 1 through origin plus the supplied 8–14 day lead-plus-review period. Known future receipt due dates are operational inputs, not future sales. No purchase quantities or customer decision process were rewritten.

`generate_freeze.py` is inference-only and was actually executed. `execution.log` and `execution_evidence.json` retain its command, ordering events, runtime, dependency versions and program/protocol/check hashes. `freeze_checks.json` records source/model identities before and after, IDs, cutoff, exact schemas, row uniqueness, populations, dates, finite nonnegative values, and full-precision selected weekly values. Weekly/daily sums differ by at most 4.440892098500626e-16 units; coverage sums agree exactly, within the required 1e-9 tolerance. Python 3.13.9, pandas 2.3.3 and numpy 2.3.5 match the supplied dependency record. These are author-generated checks, **not independent validation**.

## What remains unmeasured

Forecast coverage is 336/336 keys for each method, with no forecast exclusions. Reserved evaluation eligibility, observed recording-day coverage, targets, errors and accuracy remain unmeasured; no outcome or accuracy scores were produced. No post-cutoff sales were accessed. Internal evaluation provenance is retained separately in `internal_provenance.json`.

At evaluation, both methods must use the same store/window observation eligibility. Entirely unobserved windows are excluded for both and listed individually; partially observed weeks retain their recorded subtotal without rescaling. Report eligible/population coverage, all exclusions and observed-day counts, with a complete-seven-observed-day subset. Pooled MAE gives each eligible key/week equal weight; report per-week MAE, bias, relative and absolute paired differences, and the descriptive paired week-cluster uncertainty procedure specified in `protocol.json`. Four test weeks limit uncertainty interpretation.

The frozen MVP question is whether shrink26 has lower pooled weekly recorded-unit absolute error than recent13. There is no invented 5% threshold. A loss is a failure of this candidate on that question; retain the useful baseline option and do not tune or promote another model. December 29–31, month totals and coverage horizons are secondary. No purchasing savings, service-level success, lost sales, authentic parent-contract acceptance or final approval is established. The broader typed DSC28 contract remains separate.
