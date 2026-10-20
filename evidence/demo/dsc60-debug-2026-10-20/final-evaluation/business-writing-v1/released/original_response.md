Yes: the frozen selected model (shrink26) has lower pooled recorded-unit forecast error than the simple 13-week baseline (recent13). The relative magnitude is 4.0602%.

This is the reserved comparison of forecasts issued on 30 November 2025 against recorded product units in four seven-day windows, 1–28 December. Each eligible product/store/week has equal weight. The baseline is the frozen mean over the last 13 complete calendar-week positions, using known weeks; neither method was refitted, reselected or updated.

Pooled MAE is 1.032841 units for shrink26 versus 1.076551 for recent13. Selected minus baseline is -0.043710 units per eligible cell. Signed relative difference is -4.0602% (negative favors selected); gain is +4.0602% (positive means improvement, negative means loss).

Exact total absolute errors are 1388.138408311310248208 (selected) and 1446.884615384615386040 (baseline), on the same 1344 cells. The strict lower-sum rule gives **yes** to the predeclared MVP comparison; equality would not be improvement. There is no minimum percentage gate.

| Week | Eligible / 336 | Coverage | Selected MAE | Baseline MAE | Recorded units |
|---|---:|---:|---:|---:|---:|
| 2025-12-01–2025-12-07 | 336 | 100.00% | 1.167099 | 1.218712 | 336 |
| 2025-12-08–2025-12-14 | 336 | 100.00% | 0.989209 | 1.028388 | 268 |
| 2025-12-15–2025-12-21 | 336 | 100.00% | 1.036040 | 1.068491 | 295 |
| 2025-12-22–2025-12-28 | 336 | 100.00% | 0.939016 | 0.990614 | 254 |

Coverage is 1344/1344 possible cells (100.00%); 0 cells (0.00%) are excluded because their store-week has no recorded source rows. Partial observed weeks remain without rescaling. All cells, observed-day counts from 0 to 7, and exclusions are in per_key_week.csv. Recorded actual units total 1153. Mean prediction-minus-actual bias is -0.264847 units for selected and -0.192250 for baseline; positive means overprediction.

The secondary complete-seven-observed-day subset has 476 cells (35.42% of all possible cells), recorded units 557, and MAEs 1.250441 selected versus 1.311275 baseline.

The paired week-cluster bootstrap (seed 603; 2,000 resamples of four weeks with replacement) gives a descriptive 2.5th–97.5th percentile interval of [-0.051605, -0.035815] units for selected-minus-baseline pooled MAE. Four weeks and dependence limit inference; this is not a superiority guarantee and cannot override the exact Decimal comparison.

Data handling removed 3 exact duplicates using every original column before checking Transaction_ID; no conflicting nonidentical IDs remained. There are 0 out-of-population source rows (0 positive noncancelled units across December), disclosed in out_of_population.csv. The fixed 336-key population is unchanged; all deduplicated rows establish store-day presence before status or quantity filtering.

The target includes positive processing and returned quantities, uses final normalized statuses, and excludes cancelled or nonpositive contributions. A missing product on an observed store-day contributes zero recorded units; it does not prove zero demand. Missing store-days remain unknown, and even seven observed days do not prove complete capture. Status-update timestamps are unavailable. December 29–31 and monthwide results are secondary only in measured_results.json; lead-plus-review diagnostics were not generated because current policy fields were not among the released inputs.

This is the first post-freeze reserved-row scoring, not globally pristine untouched validation: earlier project AI sessions saw pooled full-history summaries. The freeze establishes input bytes and forecast shape/arithmetic, not independent verification of model internals or source provenance. The separate typed DSC28 complete-demand/parent-acceptance contract remains unresolved here; this evaluation asserts no complete_daily_sales=true, authenticated approval or final acceptance.

The result compares against recent13, not the customer’s unknown exact current process. It proves neither purchasing savings nor service improvement. It supports only the specified forecast-error comparison, with the coverage and inference limits above.

The existing illustrative list remains unchanged: 880 units across 112 positive product-at-store rows, 224 zero orders and 52 prearrival flags. It has not been regenerated and provides no new independent purchasing approval. Stock and policy are synthetic; check real stock, open orders, lead times and ordering policy before any purchasing use. No automatic deployment follows.

The existing routine local calculation measurement is 0.427337 seconds and 138428416 peak bytes (about 140 MB), measured on a 128 GB host; this was not a constrained 8 GB test. Routine runs require no paid model service, while ordinary computer/electricity costs remain and AI build charges are unknown. This historical runtime is separate from this evaluation’s measured execution time in execution_evidence.json.

Inspect measured_results.json for exact Decimal results and limits, paired_sums.json and scores_by_week.csv for independently recoverable numerators/denominators, and execution_evidence.json for the actual command, timestamps, runtime and input/output checksums. The script ran once; no model files, development histories or other outcome sources were read.
