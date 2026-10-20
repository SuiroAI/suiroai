Run from the folder containing `restock_routine.py`, with Python 3, NumPy and pandas installed. The measured versions were Python 3.13.9, NumPy 2.3.5 and pandas 2.3.3. The selected calculation does not import scikit-learn or SciPy; those are needed only to repeat the candidate comparison.

Working invocation for the supplied folder layout:

```sh
python restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path restocking.csv
```

Use the full path to your Python executable if `python` is unavailable. The recorded absolute invocation and measurements are in `routine_measurements.json`.

For subsequent weeks, provide that week's files, change the planning date and choose a dated output filename. Stock must be dated exactly on the planning date; sales must cover every business-wide calendar date through it, contain no later dates and include at least 104 complete weeks. This delivered method uses the last 104 complete Monday–Sunday weeks. No December sales were accessed or tested in this analysis. Future use requires future supplied inputs; do not use reserved outcomes for this demonstration.

Required input columns are the supplied schemas: sales identifiers, order date, store, product, product name (may be missing), quantities, status and return flag; stock keys, snapshot, usable stock, on-order quantity, complete-ledger indicator and units; delivery keys, unique purchase-order line, order date, arrival date, incoming quantity and units; and policy keys, effective date, lead and review days, safety stock, minimum and multiple and units. Additional columns are ignored for calculation. Exact duplicate sales rows are removed. Conflicting transaction identifiers, unknown statuses, unsupported units, missing dates, inconsistent deliveries or incompatible keys stop the run with an error. Zero and negative sales quantities are excluded. Product names are filled only from a consistent observed name for that identifier. Policies use the latest supplied rule effective on or before planning.

The output contains all policy products at stores, including supported zero orders. Order quantities are integer product units. Forecast quantities are estimates, shown to three decimals; purchasing uses full precision. Shortage flags assume all arrivals become usable at the end of their due day. Overdue deliveries and deliveries after coverage are excluded from usable incoming quantities and flagged. Orders cannot repair a shortage that occurs before they arrive. Source paths cannot be used as the output path; existing output files can be replaced, so use dated names to retain history.

The command performs no network or language-model calls. On a computer with Python, Task Scheduler on Windows or launchd/cron on macOS/Linux can run it weekly after input files are updated. Use absolute paths in the scheduler and capture its output and errors. ChatGPT can help prepare the command and scheduler settings; no scheduler, upload or integration has been installed, and the weekly calculation does not require ChatGPT.
