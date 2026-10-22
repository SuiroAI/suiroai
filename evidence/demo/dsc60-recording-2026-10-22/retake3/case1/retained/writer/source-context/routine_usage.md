Run this command from the folder containing `restock_routine.py`:

```sh
python restock_routine.py --sales-path ../released/input-4.csv --stock-path ../released/input-3.csv --deliveries-path ../released/input-2.csv --policy-path ../released/input-1.csv --planning-date 2025-11-30 --output-path restocking.csv
```

Python 3 with pandas and NumPy is required. The measured run used Python 3.13.9, pandas 2.3.3 and NumPy 2.3.5. The selected weekly calculation needs no ChatGPT, language model, network connection or API. SciPy, scikit-learn and threadpoolctl are used only for the optional comparison script, not the selected routine.

For another week, change all four input paths to the current files, set the planning date and choose a new output filename. Sales must end on the planning date; the stock snapshot must be for that date. The policy must already be effective. Do not reuse the November stock snapshot for later weeks. Future input parameterization does not authorize accessing withheld December outcomes in this investigation.

Required input columns are validated in the script. Preserve the supplied identifiers and product units. Sales need transaction identifiers, dates, quantities, status, return flag and a product-name column; missing names are filled only when another row gives a unique name for that product. Stock needs usable stock, open-order total and confirmation that its delivery ledger is complete. The policy needs supplier lead time, review period, minimum, multiple and safety stock. Deliveries need unique line identifiers, placed dates, expected arrival dates and quantities.

The routine removes exact duplicate sales, standardizes status labels, and counts positive fulfilled quantities, including original sales subsequently returned. It excludes cancelled, processing and nonpositive sales quantities. It treats dates with no line after the first fulfilled sale as no recorded sales, assuming the file is complete. It smooths weekly purchase quantities and intervals between purchases, then applies current stock and rules. Products without usable sales history, conflicting records, missing quantities, unknown statuses, mismatched deliveries or overdue incoming orders stop the run with a clear error instead of producing unsupported zeros. One effective policy row per product at a store is required. Missing historical listing dates mean earlier coverage is not assumed.

Output contains every supported product at a store, including zero orders. Quantities are integer product units. Read the shortage dates and notes before ordering. Incoming deliveries and new orders are assumed available at the start of their arrival day. Coverage includes lead time plus review days; only deliveries arriving by that endpoint reduce the order. The shortage fields use expected sales, not a probability or a promise. Pack rounding can materially increase small orders.

You can schedule this command weekly on your computer using its scheduler, with the correct Python executable, working folder and refreshed input paths. ChatGPT can help prepare the command and scheduler setup. No schedule, upload or system integration has been installed.
