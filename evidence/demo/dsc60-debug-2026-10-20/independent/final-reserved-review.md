# Independent reserved-period evaluation

[DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60), with broader [DSC-9](https://linear.app/gr3enarr0w/issue/DSC-9) acceptance kept separate.

The frozen shrink26 model passes the predeclared MVP comparison against frozen recent13: pooled seven-day recorded-unit MAE is **1.03284108 versus 1.07655105**, a **4.060186% reduction**. This applies the strict lower-error rule without a five-percent threshold. The exact paired absolute-error sums are 1388.138408311310248208 and 1446.884615384615386040; all 1,344 fixed pair/week cells are eligible. No model, parameter, target, baseline, eligibility rule or primary metric was changed for this evaluation.

| Target week | shrink26 MAE | recent13 MAE | Relative reduction |
|---|---:|---:|---:|
| December 1–7, 2025 | 1.16709914 | 1.21871184 | 4.235021% |
| December 8–14, 2025 | 0.98920899 | 1.02838828 | 3.809776% |
| December 15–21, 2025 | 1.03603971 | 1.06849054 | 3.037072% |
| December 22–28, 2025 | 0.93901647 | 0.99061355 | 5.208598% |

The candidate has lower MAE in each of four weeks, but its mean signed error is more negative: −0.26484661 versus −0.19225046 recorded units per pair/week. MAE improvement therefore does not establish better aggregate stock sufficiency, service levels or purchasing savings. Four weeks provide limited evidence of generalization.

All store/weeks have at least one transaction, but only 476 of 1,344 pair/windows (35.4167%) have transactions on all seven days. The remaining 868 are partially observed and retained under the frozen rule. Seven observed days also do not prove complete demand capture. The secondary seven-observed-day subset also favors shrink26 (MAE 1.25044135 versus 1.31127451, 4.639239% reduction); it does not replace the primary test. The independent parser removed three exact original-row duplicates from 639 supplied rows and found no conflicting transaction identities.

## Procedure and provenance

The parent authorized the outcome release only after freeze commit/push `286cdf7` and Linear comment `90391b08-93ac-461a-a867-c7be792d51db` timestamped 2026-10-20 18:46:08 UTC. The reviewer then ran its own `scripts/dsc60_verify_reserved.py` once against the controller-released partition. It imported or executed no producer program and performed no refitting or selection. Its seven synthetic tests had passed before release.

Pinned inputs, rehashed successfully before outcome processing:

- Frozen bundle `artifacts/dsc60-final-evaluation-2026-10-20/frozen`; manifest SHA-256 `2e31be4a68da6e1b69afdf32022107498b6fccb885af34613a10abb8975c91fb`.
- Controller `final-evaluation/evaluation-spec.json` SHA-256 `ff2a824aa74d3c10e04ea2203247b3088a36ee0e3a8529eac94bf35754d6d02e`.
- Released `evaluation/released/december2025.csv` SHA-256 `523785126813d13b37f4746066825ce2780f4fe16d3a77a09660bc85943ddd7e`.
- Existing selected NPZ SHA-256 `93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e`.

The independent result is retained in `final-reserved-verification.json`. This is a first frozen December-specific scoring under this protocol, qualified by the earlier model-visible pooled full-history profiles documented in `holdout-provenance-review.md`. It is not certified globally pristine untouched data. The evaluated target is positive noncancelled recorded units under the fixed exposure/status assumptions, including processing and returned records. No true-demand, complete-capture, economic-value or broader authenticated parent acceptance assertion follows.

Data's separate scoring output was subsequently checked as described below. This document distinguishes the independent arithmetic from producer-authored internal checks.


## Agreement with Data's actual evaluation

Data's saved results agree exactly with the reviewer calculation for pooled, each-week and complete-seven-observed-day secondary counts, absolute-error sums, MAE, bias, differences, relative gain and strict comparison. All 1,344 emitted per-key/week rows were compared against the reviewer's own reconstruction from the hash-pinned raw partition: 16,128 date, exposure, actual-target, forecast and error fields had no discrepancy. The current partition has exactly the original source columns, so Data's full-row deduplication is consistent with the predeclared rule without added lineage fields.

The reviewer's own saved-output checker also verified all 2,000 bootstrap samples against seed 603 and the predeclared four-week draw scheme. Recomputing their statistics from independently obtained weekly error sums differs from the saved floating-point values by at most 2.02×10⁻¹⁶; the reported percentile bounds agree within 10⁻¹². The interval remains descriptive: only four week clusters exist, and it does not supersede the exact primary comparison. Producer source was read, never executed by the reviewer.

The actual execution receipt reports one successful scoring execution at 2026-10-20 18:51:31.861603–18:51:32.003937 UTC, with local scoring runtime 0.142357 seconds. Input hashes before/after agree, and every receipt-listed output hash matches the saved bytes. The initially denied native transport and pre-scoring source-inspection heredoc were not scoring executions. The native terminal trace subsequently reports `dispatch_status=returned`, `outcome=completed`, no exception, thread `01a15aa4-cac7-7c51-b405-cf6f5bb5acb7` and turn `01a15aa4-cd1c-7ff2-861e-ae69a906e546`. The later business writer is reviewed separately in `final-business-writing-agreement.md`. Retained machine evidence: `final-reserved-agreement.json` and reviewer-owned `check_reserved_agreement.py`.

The generated technical response accurately reports the frozen comparison, partial recording coverage, more negative candidate bias, prior pooled-profile exposure, unknown exact customer method and absent economic/service proof. Its historical routine timing is correctly separated from evaluation runtime and the AI workflow. No substantive numerical or methodological discrepancy was found. The completed v2 business summary subsequently passed the separate source/accuracy review retained in `final-business-writing-agreement.md` and `.json`; no analytical result or order-list change occurred during writing.
