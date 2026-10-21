The reusable command reads the four CSV files, calculates orders and writes a CSV. It uses the selected 13-week averaging method, sharing a small amount of information for each product across stores. It runs locally without ChatGPT, language models, paid model calls or network access.

Use Python 3 with pandas and NumPy. The measured environment used Python 3.13.9, pandas 2.3.3 and NumPy 2.3.5; authoritative installed versions are recorded in routine_measurements.json. Reproducing the optional model comparison also needs scikit-learn 1.7.2 and SciPy 1.16.3. These two packages are not imported by the selected weekly calculation.

From this output folder, this invocation creates a new file:

```sh
python restock_routine.py --sales-path ../released/input-4.csv --stock-path ../released/input-3.csv --deliveries-path ../released/input-2.csv --policy-path ../released/input-1.csv --planning-date 2025-11-30 --output-path weekly_restocking.csv
```

Replace each file path, the planning date and the destination as needed. Absolute paths are accepted. Use an unused output filename: existing outputs and source files cannot be overwritten. The measured invocation used `--output-path restocking.csv`; that file is the delivered list.

Required inputs:

- Sales: transaction identifier, product/store identifiers, order date, integer quantity, status and return flag. A product name is optional and used only when unambiguous. Provide history through the planning date and at least 91 complete recent calendar days for every active product at store. The global calendar must contain records every day. Absence of a particular product's sale on represented days means zero recorded units, not proof that no customer wanted it.
- Stock: one row per product at store, dated on the planning date, with usable units, units on order, complete-ledger indicator and product-unit denomination.
- Deliveries: uniquely identified open purchase-order lines, ordered on/before the planning date, expected arrival dates and nonnegative incoming units. An empty ledger is allowed only when stock on order is zero everywhere.
- Rules: effective date, supplier lead days, review days, pack multiple, minimum order, safety stock and matching unit denomination. Latest eligible version applies per product at store. Lead/review/multiple must be positive integers; other quantities nonnegative integers. Products at stores must match stock and sales.

Orders cover supplier lead time plus review period; stock and deliveries due within that period reduce the order. Safety stock is retained and positive quantities are rounded up to the minimum and pack multiple. Existing on-order totals are checked against deliveries; they are never subtracted twice. All 336 current rows are retained, including supported zero orders.

Read the shortage quantities, first shortage dates and review flags before sending orders. Deliveries and new orders are assumed available at the start of their due day, and stock is assumed measured at the end of the planning date. Overdue incoming is flagged for confirmation; future files with incomplete ledgers or conflicting totals are rejected. Negative projected balances are expected-demand gaps, not measured lost sales. No unexpected extra safety buffer is added.

For future weekly use, supply updated sales, a matching stock snapshot, current delivery information and rules; change the planning date. This does not authorize evaluating the reserved December 2025 sales from this investigation. The command has no scheduler feature. You can schedule the command with your computer's scheduler; ChatGPT can help prepare the command and scheduler setup. No schedule, upload or integration has been installed.

Internal reproduction: `inspect_sources.py`, `compare_candidates.py`, `selection_and_checks.py`, `summarize_uncertainty.py` and `run_and_verify.py` preserve this investigation. The measurement script deliberately refuses to overwrite the delivered CSV. Preserve the frozen plan and results before any new investigation; weekly execution requires only restock_routine.py and its two installed dependencies.
