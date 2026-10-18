# DSC-24 source and fixture reconciliation

This is real local source-audit evidence. It is neither mock analytical evidence nor proof of an implemented cleaning, forecasting, evaluation or restocking pipeline. The script reads the supplied files without changing them and writes only the explicitly requested audit output.

Run from the application/worktree root:

```sh
python3 docs/contracts/audit/reconcile_sources.py \
  --data-root /Users/ceverson/Development/SuiroAI/data/retail_mvp/sales_2022_2025 \
  --output docs/contracts/audit/reconciliation.json
```

Omit `--output` to print JSON. `--downloads-root` optionally points to original sales/dictionary files; its default is the current user's Downloads directory. Original files being unavailable is explicitly recorded, not a portability failure. JSON includes raw-byte SHA256 and byte size for the five CSV files, generation manifest and shared-locations document. It compares manifest hashes/bytes and recorded Drive file sizes. Recorded sizes do not verify remote Drive content.

## Observed fixture profile

These counts describe the current supplied fixture. They are not fixed acceptance thresholds for another customer's input.

- Sales has 36 columns, 18,045 raw rows, 18,000 distinct records and transaction IDs, and 45 exact duplicate excess rows.
- Before/on the manifest review date, November 30, 2025: 17,406 raw rows and 42 duplicate excess rows. December contains 639 raw rows and 636 distinct records. The audit records only source-profile facts; it does not derive a target or expose holdout outcome measures for model selection.
- There are 28 products, 12 stores and 336 product/store keys. Inventory and policy each have one row per same key. All keys occur before/on the review cutoff.
- Transaction, product, store, date, quantity, status and return-flag fields are populated. Product names are blank on 144 distinct rows. Nonblank product and store names have no ID mapping conflicts. Category, region and city text contains casing or naming differences. Product/store IDs remain canonical; display names do not define joins.
- All 1,461 dates occur somewhere, but per-key observed dates range from 15 to 117, median 50. Calendar coverage across the whole extract does not establish complete histories for each key.
- Eight nonpositive quantity records are retained in the audit: five zeros and three negatives (-1, -2, -3). All have Return_Flag=No. They cannot silently be interpreted as documented returns or silently removed. The JSON identifies each source transaction for later investigation.
- Completed, Shipped, Returned, Processing and Cancelled statuses occur, with casing differences. Return_Flag is a separate observation. No target treatment is chosen by this audit.

## Source/hash reconciliation

All five CSV SHA256/size pairs match `documentation/synthetic_generation_manifest.json`. The preserved raw sales/dictionary copies also match their declared `source_hashes`. Available originals in `/Users/ceverson/Downloads/` byte-for-byte match the preserved raw copies. This supports local source preservation; it does not establish origin, license, authenticity or extract completeness.

`documentation/shared_locations.json` supplies Drive IDs and recorded sizes. Those recorded sizes match the audited local files. Drive contents were not fetched or independently hashed in this audit. Linked external issue/document content is outside this script's evidence scope.

## Operational facts and receipt-summary reconciliation

Every operational row is labeled synthetic and uses `product_unit`. Inventory snapshots and policies are dated November 30, 2025. The dictionary's Quantity means units in a transaction: one unit of the same SKU. No pack-to-weight or currency conversion is inferred from product names.

The 126 inbound lines have unique PO line IDs across 126 keys. Incoming quantities total 927 units and exactly reconcile by product/store key to inventory On_Order_Qty, also 927 units. The remaining 210 keys have no receipt line, On_Order_Qty=0 and Open_Order_Ledger_Complete=true. All 336 inventory keys declare complete synthetic ledgers.

This explicit completeness assertion permits absent receipt rows to mean zero **only for this dataset, key scope and as-of snapshot**. It does not license zero-filling an incomplete customer ledger or missing sales dates. Consumers should use receipt lines for dated availability, use On_Order_Qty as reconciliation evidence and never add the summary to the same receipt quantities.

Receipts arrive December 1–7, with order dates no later than the cutoff and arrival-minus-order equal to the explicit synthetic supplier lead time. Receipt quantities obey explicit purchase multiples. Policies use 1–7 calendar-day supplier lead times, seven-day review, multiples of 1/5/10 units and minimum positive order equal to one multiple. Safety stock and usable on-hand stock are synthetic scenario assumptions, not recovered business facts.

The generator uses deduplicated, positive past transaction quantities across statuses only to vary arbitrary synthetic quantities. This is neither target selection nor an estimate of daily demand. The generator was inspected, not executed. No December records determine fixture generation according to the inspected generator; this audit confirms source/profile and row-level operational consistency without rerunning generation.

## Unresolved material semantics and downstream obligations

1. Source origin, license, authenticity and extract completeness remain unverified. Observed transactions do not establish unconstrained demand, store opening periods or sales lost during stockouts.
2. Per-key absent dates are unknown until supported completeness evidence or an explicit approved synthetic scenario assumption authorizes zeros. A global full calendar is insufficient.
3. The analytical owner must justify the target, statuses, returns/cancellations and treatment of the eight nonpositive rows, preserving raw lineage and treatment decisions. Customers should clarify irreducible business facts, not choose algorithms or imputation methods.
4. Status and return fields have no historical availability/revision timestamps. Financials, realized fulfillment duration, approximate stock and customer fields are not automatically available or safe at prediction time.
5. Store-local date/timezone semantics and revision timing are unspecified across countries. Calendar-day policy timing must remain explicit.
6. Inventory_Level is approximate stock at transaction and cannot replace usable stock at the review date. Delivery_Days is customer fulfillment duration and cannot replace supplier procurement lead time.
7. Real usable stock, reservations/unusable-stock treatment, open orders, supplier lead times, buffers, multiples and purchasing constraints are not established by this synthetic fixture. A final list using it must remain illustrative.
8. Development/selection uses only permitted artifacts through November 30, with every development target horizon ending by that cutoff. December remains reserved unseen evaluation; only fully observed horizons may be scored. The original raw CSV must be preserved while access to future rows is restricted for feature/model selection contexts.
9. Metrics, aggregation, baseline, acceptance thresholds and bounded defect/recheck limits must be declared before unseen evaluation. Hash reconciliation cannot settle those choices or constitute model validation.

There are no forecasts, fitted models, measured analytical scores, restocking lists or customer business facts synthesized by this audit. Contract examples that refer to analytical success/failure remain separate and explicitly mocked.
