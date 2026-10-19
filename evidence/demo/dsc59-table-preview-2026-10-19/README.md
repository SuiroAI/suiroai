# DSC-59 table-only demo preview

The HTML is a deterministic visualization of the exact previously generated restocking CSV, not an analytical report. It has one generic heading and one table; no findings, metric cards, comparisons, extra summaries, methods, costs or limitations. All CSV headers, 336 rows, cell strings and row order match exactly. Verification uses an independent HTML parser against csv.reader; no Data-generated code was executed and no new analysis is claimed.

All customer explanation now belongs in the app response, in everyday words for a retail business owner. Detailed diagnostics remain internal. The app's new-tab link is labelled **View restocking list**; CSV remains a download.

Browser opening of this local file was rejected by the browser URL policy (only HTTP/HTTPS allowed). No workaround was attempted. The earlier HTTP new-tab route was visually exercised, while this final table-only content is covered by parser and integration tests.

Tracking: https://linear.app/gr3enarr0w/issue/DSC-59

Validation: 737 tests and 659 subtests passed. A GPT-6.1 medium subagent independently confirmed all 336 rows and 15 columns agree exactly and legacy narrative HTML remains internal.
