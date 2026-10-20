# Prospective December evaluation freeze

This archive was prepared before this final workflow opened December outcomes. The selected shrink26 model and recent13 baseline issue all forecasts at November 30, 2025. The primary comparison is paired recorded-unit absolute error across December 1–7, 8–14, 15–21 and 22–28, with common eligibility. Strictly lower error passes the declared MVP comparison; a tie fails. No refit, reselection or threshold change is allowed after release.

Frozen manifest SHA-256: `2e31be4a68da6e1b69afdf32022107498b6fccb885af34613a10abb8975c91fb`.
Evaluation specification SHA-256: `ff2a824aa74d3c10e04ea2203247b3088a36ee0e3a8529eac94bf35754d6d02e`.
Selected fitted model SHA-256: `93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e`.

The Data-authored forecasts and model identity passed independent arithmetic and source reconstruction checks without executing producer code. See `../independent/final-freeze-review.md`. The independent scoring implementation passed seven synthetic tests and a separate code review before outcome release.

Earlier model-visible pooled full-history summaries included December records; no prior December-specific target vectors or forecast scores were established by the bounded provenance audit. This is therefore a frozen December-specific comparison with qualified prior exposure, not a globally pristine holdout claim. See `../independent/holdout-provenance-review.md`.

The complete immutable local bundle is `artifacts/dsc60-final-evaluation-2026-10-20/frozen`. Private development CSV assets are identified by hash in `frozen-artifact-index.json` rather than duplicated in Git. This archive is not self-contained without those authorized inputs. `controller-at-forecast-launch.py` preserves the exact controller used for the forecast call; the base commit and dirty-controller hash are recorded in `forecast-call.json`.

This prospective freeze does not grant authenticated delivery, original-video, complete-demand, purchasing-savings or parent milestone acceptance. Outcome results will be added separately after this freeze is committed and pushed.
