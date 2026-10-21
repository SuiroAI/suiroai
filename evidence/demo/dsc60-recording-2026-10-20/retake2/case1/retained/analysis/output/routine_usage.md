Run the weekly calculation with Python, NumPy and pandas installed. The measured versions were Python 3.13.9, NumPy 2.3.5 and pandas 2.3.3. The weekly command does not use ChatGPT or any model service.

From this output folder, this invocation uses the released files:

```sh
python restock_routine.py \
  --sales-path ../released/input-4.csv \
  --stock-path ../released/input-3.csv \
  --deliveries-path ../released/input-2.csv \
  --policy-path ../released/input-1.csv \
  --planning-date 2025-11-30 \
  --output-path restocking.csv
```

For later weeks, change the four paths to the updated files, set the planning date and choose the output filename. Stock must be dated on the planning date; sales must retain the history from January 1, 2024 through that date, with no later transactions, plus earlier records establishing the products were already in the assortment. Ordering rules must already apply. Keep the supplied column headings and product units. The delivery file must list all open deliveries, including none for products without open orders. Output cannot overwrite any input. A previous output at the specified destination will be replaced.

The command writes all supported products at stores, including zero orders, incoming delivery timing and items to review. It checks dates, units, duplicate identifiers, matching product lists and agreement between deliveries and stock. It stops on gaps in daily sales reporting, unknown products or incomplete incoming delivery records. New assortments without pre-2024 history require separate handling; a missing transaction is treated as no recorded sale only for established assortments with continuous reporting. The fixed historical start is January 1, 2024; this is configurable in code only, not a CLI option.

The selected calculation estimates sale size and time between sales, then subtracts stock and timely deliveries from expected coverage needs plus the supplied buffer, and rounds up to the supplied minimum and batch size. Returned items are not automatically added back to usable stock. Arrival-day receipts are assumed usable before that day's sales; shortage flags use expected sales and are not guarantees.

The command can be scheduled weekly with the computer's built-in scheduler, such as Task Scheduler on Windows or launchd on macOS. Use absolute paths, the intended Python environment, updated inputs and a planning date matching the stock file. ChatGPT can help prepare the command and scheduler setup. No schedule, file upload or store-system integration has been installed.
