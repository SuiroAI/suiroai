# Streamlit rerun: lightweight model discovery

Tracking: [DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60), [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59), [DSC-9](https://linear.app/gr3enarr0w/issue/DSC-9).

Actual source `3f774f4`, app http://127.0.0.1:8505/, session `8d99bf86d50541e19a6afa142746809c`. The same four authorized retail CSVs were selected through the normal native picker, and the exact original short question entered. Task review and approval were each clicked once. Genuine context detection and Data analysis completed once. Existing completed port 8504 session was preserved; no recording or security-policy change occurred.

## Result of this run

Data selected `shrink26`: a simple 26-week local sales estimate pooled toward broader product/store patterns. The comparator was a 13-complete-week average. Primary seven-day MAE measures absolute recorded-unit error per eligible product/store/week; lower is better.

| Candidate | Development weekly MAE | Versus baseline |
|---|---:|---|
| Pooled 26-week estimate | 0.942940 | 2.1481% lower |
| 13-week average baseline | 0.963640 | Reference |
| Simple exponential smoothing | 0.980696 | Worse |
| Poisson calendar regression | 1.036121 | Worse |

The selected model beat the baseline at all seven primary origins, target-start weeks October 6 through November 17, 2025. Independent arithmetic from emitted origin scores gives October 2.0657% and November 2.2434% reductions. These are development selection observations, not untouched final evaluation. Secondary 8–14 day coverage MAE improved 3.8265%; that is a distinct horizon and cannot replace the primary 2.1481% claim.

Missing-store-day handling, complete-week baseline implementation and origin set differ from prior runs. Thus this is a fair **within-run development comparison**, not an apples-to-apples gain over the earlier protocol or proof that prompt wording caused better forecasts. The model has more negative aggregate bias; its advantage on the small complete-store-week subset is below half a percent. Missing capture/lost sales, retrospective assortment/status knowledge and the exact customer buying rule remain unresolved. No purchasing savings or service-level improvement is established.

## What reached Data and what it did

Exact outbound prompts, approved input hashes, model/effort/plugin identity and native thread/turn/log identities are retained under [detector](detector/trace/call-trace.json) and [analysis](analysis/trace/call-trace.json). [Run index](run-index.json) and [receipt summary](receipt-summary.json) bind source, question, review/approval and final artifacts. Raw native logs, raw transactions and notebooks are not duplicated; indexes retain their local paths/hashes. Generated prediction files contain weekly aggregate targets/forecasts, not transaction rows.

The actual analytical payload had ordinary autonomous discovery, no six-formula engineering contract, and the user-authorized CPU/8 GB scope. Data preserved the exact question/context in [task_refinement.json](analysis/output/task_refinement.json), separately identified the decision and unknown priorities, treated the current procedure as context/comparison, and justified four lightweight candidates using file observations. It wrote [evaluation_plan.json](analysis/output/evaluation_plan.json) before scoring. Early planning bytes were additionally retained under `pre-score-plan-observation/`; this is not a final forecast/model freeze.

Data found a pooling-denominator implementation bug: wholly unobserved store-weeks were implicitly included as zeros in pooled rates. It documented a correction before corrected scores, retained original result files, and reran with observed-pair-week means. Baseline, candidates, hyperparameters, dates, primary metric and selection rule were unchanged. Initial gain 2.1855% is superseded by final 2.1481%; do not mix them. Original code/diff independently extracted from native file-change events is retained under [implementation history](../independent/streamlit-discovery-2026-10-20/implementation-history/). The producer's original-results directory did not initially contain original source code. [Plan v2](analysis/output/evaluation_plan_v2.json) honestly consolidates the correction **after** scoring; it does not retroactively claim predeclaration. A separately declared missing-day scenario freezes the selected forecast and does not reselect or overwrite delivered CSV.

## Practical runtime and output

[restock_model.py](analysis/output/restock_model.py) contains the selected non-LLM calculation using NumPy/Pandas. [Final routine receipt](analysis/output/routine_workload.json) measures 0.427337 seconds including imports/preparation/fitting/inference/orders and 138,428,416 bytes peak process RSS (about 140 MB). This was measured on a 128 GiB host, not an 8 GB-cap test; actual working-set evidence supports practical 8 GB capacity for this dataset, while speed/dependencies vary. Routine execution needs no paid model calls. Computer/electricity/hosting still have costs; AI analysis/build billing is separate and unknown. The multi-candidate development run's roughly 10 second local calculation is a different workload.

Final illustrative CSV: 336 unique rows, 112 positive/224 zero orders, 880 units and 52 prearrival review flags. The synthetic stock/delivery/policy inputs and November 30 order-placement assumption limit use; the prior run used a different order-date convention, so warning counts are not directly comparable. Fifteen order quantities differ from this run's baseline. [Final explanation](analysis/output/response.md) reports a small about2% gain without claiming improvement over an unspecified exact customer process or better availability. Minor copy issue: the opening omits2025, though approved context and CSV dates include it. The routine has five shared columns matching the full delivered 17-column CSV, not identical schema/bytes. Future-ingestion hardening for conflicting duplicate transaction IDs remains outside this exact-fixture check.

The app explanation including costs was traversed. View restocking list was explicitly clicked once; HTML opened in a new tab, was scrolled, and the completed app restored. The live DOM exactly matches all 17 headers, 336 rows, 5,712 body cells and row order. No embedded preview or automatic file action occurred. CSV download was not retried; the prior organization-policy block remains intact and no browser-download success is claimed. App and table remain open. Screenshots are separate observations, not a continuous recording.

## Independent checks and remaining acceptance

[Independent workflow/method review](../independent/streamlit-discovery-2026-10-20/REVIEW.md) inspected actual approval/dispatch, plan chronology, source compliance, correction history and resource claims. [Independent output consistency review](../independent/streamlit-discovery-2026-10-20/output-consistency-review.md) used its own parser/arithmetic to verify hashes, 336 row quantity/pack rules, aggregate/origin metrics, response claims, routine shared values and HTML/live-DOM identity. Neither reviewer executed generated producer code, built another model, analyzed raw sales or inspected withheld December 2025 outcomes. Producer-authored validation labelled “independent” is not substituted for these reviewers.

Ordinary analysis completed and the refined-task workflow was genuinely exercised. Final-policy freeze and verified-final-report flags remain false. The small selected-on-development gain does not satisfy untouched-data performance acceptance or prove a causal prompt benefit. December provenance certification, the parent-required freeze/forecast chain and independent one-shot evaluation remain open; no performance-success recording, broader gate closure, PR merge or original-video claim follows.
