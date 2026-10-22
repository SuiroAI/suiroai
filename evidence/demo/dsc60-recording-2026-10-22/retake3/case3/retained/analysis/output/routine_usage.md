# Weekly restocking command

Keep `restock_routine.py` and `forecasting.py` together. Install Python 3.11+ with pandas and NumPy (`python3 -m pip install -r requirements.txt`). The measured environment used Python 3.13.9, pandas 2.3.3 and NumPy 2.3.5; see `routine_measurements.json` for the recorded versions. The selected routine needs neither scikit-learn nor a language model. The optional comparison script additionally uses scikit-learn 1.7.2.

From this output folder, the following invocation uses the supplied files. Choose a fresh output filename: the command refuses to overwrite existing files.

```sh
python3 restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path weekly_restocking_2025-11-30.csv
```

For each later weekly calculation, provide updated input paths, the new planning date, and a new output path. The sales extract must end on that date and must contain no later sales. Stock must have a matching snapshot date. Run after the day's sales and stock have been finalized; Sunday is preferred so the most recent full calendar week is used. On other days, the current incomplete week is excluded and flagged. Future configuration is supported; this investigation did not read or test December outcomes.

Required inputs:

- Sales: transaction identifier, date, product and store identifiers, product name, integer quantity, order status and return flag. Exact duplicate transactions are removed; conflicting identifiers fail. Positive completed, shipped and returned units measure goods going out. Returns are not assumed to be usable stock.
- Stock: one row per product at store, matching snapshot date, usable stock, on-order quantity, complete incoming-ledger indicator and product units.
- Deliveries: unique order-line identifier, product and store, order and arrival dates, quantity and product units. An empty ledger with the correct headers is supported. Totals must match the on-order stock records. Overdue arrivals are excluded from usable incoming stock and flagged for confirmation.
- Rules: one effective row per product at store, calendar-day supplier lead time, review days, pack multiple, minimum order, safety stock and product units. Provide the policy version in force as of the planning date.

The calculation assumes a complete sales extract after each product's first recorded transaction. It uses full weeks, including weeks without recorded sales. At least eight completed weeks are required. This does not prove stores were open or products were in stock on quiet days. Unsupported input coverage or inconsistent stock/receipts causes a clear error instead of invented quantities.

The command forecasts sales, subtracts usable stock and deliveries due within the coverage period, adds the supplied safety amount, and applies minimum orders and pack sizes. Coverage is supplier lead time plus review time. It also checks each day's expected balance and flags shortages before new stock arrives. Receipts are available at the start of their arrival day. Quantity forecasts and shortage flags are estimates, not guaranteed outcomes. Source files are never overwritten.

You can schedule this command on your computer using Task Scheduler, launchd or cron. Use full file paths, an output filename unique to each run, finalized weekly inputs, and save the command's output/error messages. ChatGPT can help prepare the command and scheduler setup. No schedule, upload or integration has been installed. The weekly calculation itself runs locally without ChatGPT, model calls or paid APIs.
