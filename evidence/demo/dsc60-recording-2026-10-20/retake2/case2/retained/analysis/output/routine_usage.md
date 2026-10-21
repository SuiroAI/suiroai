# Weekly restocking command

Run from this output folder, using a new output filename:

```sh
python restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path next_week.csv
```

Paths may be relative or absolute. For future weekly use, provide the updated four files, change the planning date and choose a new output path. This demonstration was run only for November 30; later sales outcomes were not read or tested. Existing input and output files cannot be overwritten by the command.

Required: Python 3, NumPy and pandas. Tested with Python 3.13.9, NumPy 2.3.5 and pandas 2.3.3; exact measured versions are in routine_measurements.json. No account, connection, language model or network access is needed for weekly calculations. SciPy and scikit-learn were used only for the supporting candidate comparison, not the selected routine's execution.

Inputs must preserve the supplied CSV headers. Sales need transaction ID, order date, status, return flag, product/store IDs, product name and integer product quantity. The routine reads all original sales columns for exact-row deduplication. Stock needs the planning-date snapshot, usable stock, total on-order quantity, complete-ledger flag and product-unit designation. Deliveries need unique order-line IDs, order dates known by planning date, future due dates and incoming product-unit quantities. Policy needs effective date, supplier lead time, review period, order multiple, minimum and safety stock in product units. Units must agree; stock and policy need exactly matching unique keys, and dated receipts must match stock on-order totals. Overdue deliveries, conflicting transactions, missing values and unsupported units cause a clear input error rather than guessed quantities. Negative sales quantities are excluded as corrections of unknown meaning.

The frozen method pools each product's and store's last 84 calendar days of recorded outgoing units, blending that estimate with the product's own sales at that store. Orders cover lead time plus review period, use supplied safety stock, subtract usable stock and receipts due within coverage once, then round upward to the minimum and multiple. Receipts and new orders are assumed usable at the start of their arrival day. The projection flags shortages before replenishment; a zero order can still carry a timing warning when existing incoming stock arrives too late. Projected shortages are expected fractions of units, not guaranteed missed purchases. Forecasts use recent recorded-calendar throughput, not a verified store-opening calendar or stockout-adjusted demand estimate. Missing sales rows are never presented as proof of zero underlying demand.

Review shortage warnings for earlier deliveries and review quiet items before placing minimum-size orders. All 336 supported products at stores appear, including zero orders. CSV line endings are LF and quantities are product units, not cartons. The displayed forecast columns are rounded to three decimal places; rounding of orders uses full precision.

You can schedule the command on your computer using macOS launchd, Windows Task Scheduler or cron where available, with absolute paths, the appropriate weekly planning date and a fresh output filename. ChatGPT can help prepare that command and scheduler setup. Scheduling is optional and has not been installed; updated input files must be supplied locally, and no upload or store-system integration is included.

The measured November 30 command, source/code/output hashes, whole-process runtime and memory, and agreement checks are retained in routine_measurements.json. measure_routine.py contains that measurement and separate quantity/timing checks. Its retained measured rerun writes routine_verified.csv, byte-identical to restocking.csv.
