# Weekly restocking command

Keep `restock_routine.py` and `forecasting.py` together. Requires Python 3.10+ with pandas and NumPy. Tested with Python 3.13.9, pandas 2.3.3 and NumPy 2.3.5. The selected calculation does not import or require scikit-learn, use a language model, or make network/API calls.

From this output folder, the following invocation uses the released inputs. Choose a fresh output filename because the command refuses to overwrite any existing file:

```sh
python restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path restocking_week_2025-12-01.csv
```

Use `python3` or the absolute path to your Python executable if appropriate. The measured invocation used `/opt/anaconda3/bin/python` and produced `restocking.csv`; `routine_measurements.json` retains its exact command, dependencies, hashes and workload measurements.

For a subsequent weekly run, supply newly dated sales and stock files, the open incoming-delivery ledger, applicable ordering rules, a planning date in `YYYY-MM-DD` form, and a new output path. The sales extract must end on that date, contain no later sales, and the stock snapshot must match it. Historical policy versions are supported: the most recent effective rule per product at store on or before the date applies. Sunday is convenient; other planning dates use the latest completed Monday–Sunday weeks for the average. This parameterization has not been tested against reserved December sales.

Required columns and accepted values are checked by the command. Sales need transaction identifiers, product/store identifiers, product names (names may be missing), order date, status, return flag and integer quantity. Recognized statuses are completed, shipped, returned, cancelled and processing, ignoring case/outer whitespace. Stock, ledger and rules use the supplied schemas and `product_unit`. The open-order ledger must be marked complete, and its totals must match stock's on-order totals. Invalid or inconsistent inputs stop the run without producing an order list. No source files are modified.

`OrderQty` is an integer number of individual product units, already rounded to the minimum and multiple. Coverage is lead time plus review days. Only future incoming units due within coverage reduce the order. Overdue units are withheld from available supply until confirmed. Receipt is assumed at the beginning of the due day; forecast sales are spread evenly across days. `PreArrivalShortageQty` and `NextWeekShortageQty` are rounded-up maximum projected deficits, not sums of daily shortages; the latter includes the proposed order on its expected arrival day. `REVIEW_EARLIER_SUPPLY` identifies shortages the normal order timing cannot prevent. `SPARSE_SALES_REVIEW` marks expected coverage sales below one unit, a descriptive review flag rather than a business-improvement threshold.

Optionally schedule this same command using Task Scheduler on Windows, launchd on macOS, or cron on Linux. Use absolute paths to the Python executable, scripts, input files and dated output; keep the two Python files together and ensure refreshed inputs are ready before execution. ChatGPT can help prepare the command and scheduler settings. No schedule, upload, integration or scheduler feature has been installed, and executing the command needs no further AI call.
