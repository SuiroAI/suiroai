# Prospective December evaluation freeze

This archive was prepared before this final workflow opened December outcomes. The selected shrink26 model and recent13 baseline issue all forecasts at November 30, 2025. The primary comparison is paired recorded-unit absolute error across December 1–7, 8–14, 15–21 and 22–28, with common eligibility. Strictly lower error passes the declared MVP comparison; a tie fails. No refit, reselection or threshold change is allowed after release.

Frozen manifest SHA-256: `2e31be4a68da6e1b69afdf32022107498b6fccb885af34613a10abb8975c91fb`.
Evaluation specification SHA-256: `ff2a824aa74d3c10e04ea2203247b3088a36ee0e3a8529eac94bf35754d6d02e`.
Selected fitted model SHA-256: `93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e`.

The Data-authored forecasts and model identity passed independent arithmetic and source reconstruction checks without executing producer code. See `../independent/final-freeze-review.md`. The independent scoring implementation passed seven synthetic tests and a separate code review before outcome release.

Earlier model-visible pooled full-history summaries included December records; no prior December-specific target vectors or forecast scores were established by the bounded provenance audit. This is therefore a frozen December-specific comparison with qualified prior exposure, not a globally pristine holdout claim. See `../independent/holdout-provenance-review.md`.

The complete immutable local bundle is `artifacts/dsc60-final-evaluation-2026-10-20/frozen`. Private development CSV assets are identified by hash in `frozen-artifact-index.json` rather than duplicated in Git. This archive is not self-contained without those authorized inputs. `controller-at-forecast-launch.py` preserves the exact controller used for the forecast call; the base commit and dirty-controller hash are recorded in `forecast-call.json`.

This prospective freeze does not grant authenticated delivery, original-video, complete-demand, purchasing-savings or parent milestone acceptance. Outcome results will be added separately after this freeze is committed and pushed.

## Completed outcome release and comparison

The prospective freeze was pushed as `286cdf7` and announced in Linear DSC-60 at 18:46:08 UTC before outcome release. The original full-source hash was checked and the December partition preserved original columns and field values; its SHA-256 is `523785126813d13b37f4746066825ce2780f4fe16d3a77a09660bc85943ddd7e`. Raw transaction rows remain in the authorized local release, not this Git archive.

The first native launch failed with `Operation not permitted` before any thread or turn. The identical prompt and released files were retried in fresh native evidence after obtaining OS execution permission. Both launch records and exact traces are retained; this was transport recovery, not repeated scoring. The genuine Data evaluator then ran once, without model/development-history access, refitting or reselection.

| Primary frozen comparison, December 1–28 | Selected shrink26 | Baseline recent13 |
| --- | ---: | ---: |
| Mean absolute weekly recorded-unit error | 1.03284108 | 1.07655105 |
| Total absolute error | 1388.138408311310248208 | 1446.884615384615386040 |
| Eligible product/store/week cells | 1344 | 1344 |

The selected model has **4.060186% lower absolute error**, and wins in each of the four primary weeks. It passes the prospectively declared strict-lower-error MVP comparison. There was no invented five-percent threshold. This is a modest forecast-accuracy result against the specified 13-week average, not an exact customer-process replica or a purchasing-cost/service-level result. Mean bias worsens to −0.264847 from −0.192250 recorded units per cell. Only 476/1344 windows have transactions on all seven days; partial windows remain under the frozen rule. Earlier pooled-profile exposure and broader milestone limits above still apply.

Data's exact output, evaluator source, command/time/checksum receipt, per-cell/week scores and descriptive four-week bootstrap are retained under `scoring/`. The independent verifier separately reconstructed target/exposure and scores without importing or executing Data's evaluator. See `../independent/final-reserved-review.md` and `../independent/final-reserved-verification.json`.

The separate genuine business-writing turn uses bounded final findings plus the original immutable CSV identity/counts and routine workload measurement. It cannot refit models or change orders. The original illustrative list remains 880 units, 112 positive rows, 224 zero rows and 52 early-stock flags. This engineering continuation completes reserved evaluation and presentation of the actual Streamlit-selected model; it is not a new recording or a claim that the earlier completed browser session was refreshed.

## Business explanation and source validation

`business-writing-v2/business_response.md` is the final intended customer explanation. A genuine separate writer turn produced it from immutable final findings, CSV counts/hash, routine measurements and the original Data-authored model rationale. The first writer was accurate but too technical; `business-writing-v1/` retains it and its independent review rather than silently replacing the history. V2 changed presentation only. Both prompts, source manifests, actual native outcome/thread/turn links and result checksums are retained. The backend now uses this separate writing stage automatically after a completed analysis, with approval validity checked before dispatch and publication and useful original findings preserved if writing fails.

The end-to-end path is actual Streamlit upload/context detection/review/approval/model discovery, followed by the same saved model's pre-release fixed forecasts, one reserved Data evaluation, independent source reconstruction and final writing. No new browser recording, CSV browser download or customer approval record is claimed for the engineering continuation. HTML/CSV bytes remain the previously validated exact table/list.

Independent final writing review passed: `../independent/final-business-writing-agreement.md`. The v2 explanation SHA-256 is `faf8e11f6c9affb3899f6077a517cfaae8d3a4c2f6c3a797811436656066103b`. The final full suite passed 845 tests and 659 subtests; focused writer/backend checks also passed. No broader issue was closed and no new recording began.
