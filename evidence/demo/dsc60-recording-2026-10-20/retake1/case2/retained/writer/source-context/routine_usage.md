# Weekly restocking routine

Run with Python 3, NumPy and pandas. The measured environment used Python and dependency versions recorded in `routine_measurements.json`. No language model, API key, paid model service, GPU or internet connection is required by the routine.

Working invocation from this output directory:

```sh
python restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path restocking.csv
```

Use the Python executable in an environment with NumPy and pandas installed. The actual measured executable is retained in `routine_measurements.json`.

Supply current CSV files with the same schemas as the released inputs: transaction history through the planning date, usable stock dated on that date, complete open delivery ledger, and applicable ordering policy. Input and output paths and the planning date are configurable. Use an end-of-day planning date; arrival dates refer to stock available at the beginning of the due day. Policy rows must have unique product/store keys, with current applicable rules only. Future weekly use requires corresponding future supplied files; this analysis did not access December sales.

The routine rejects missing operating values, conflicting sales identifiers, duplicate operating keys, mismatched incoming totals, unsupported units, invalid quantities and dates, future sales or orders, stale stock, and output paths that overwrite any input. Exact duplicate sales rows are removed; status case is normalized. Product names come from nonconflicting sales names. At least one year of established product history is currently required.

The selected calculation averages each product's positive fulfilled recorded sales over 90 days, then blends that equally with product/store pooled rates. No return credits are assumed. Coverage is supplier lead time plus review days. Subtract stock and receipts due during coverage, add supplied safety stock, and round positive gaps to minimums and multiples. Zero orders remain in the CSV. Timing flags use evenly spread daily sales, not calibrated shortage probabilities. Full numerical rules and limitations are retained in internal supporting files.

For optional scheduling, a computer scheduler such as macOS launchd, Linux cron or Windows Task Scheduler can run the same command weekly, using absolute executable and file paths and an updated planning date. ChatGPT can help prepare that command and scheduler setup. No schedule, automatic file upload or integration has been installed; routine calculations need no further AI call. Local computer/electricity or hosting costs still apply.
