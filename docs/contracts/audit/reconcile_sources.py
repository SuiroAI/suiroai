#!/usr/bin/env python3
"""Read-only source/fixture audit; never prepares data or evaluates a model.

Compare supplied sales and synthetic operational files with their manifests,
then report hashes, observed source profiles, and reconciliation checks.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics

FILES = {
    "sales": "supplied_sales/Sales_transactions_2022_2025.csv",
    "dictionary": "supplied_sales/sales_data_dictionary.csv",
    "inventory": "synthetic_inventory/inventory_position.csv",
    "receipts": "synthetic_inventory/inbound_deliveries.csv",
    "policy": "synthetic_ordering_rules/ordering_policy.csv",
    "generation_manifest": "documentation/synthetic_generation_manifest.json",
    "shared_locations": "documentation/shared_locations.json",
}


def digest(path):
    content = path.read_bytes()
    return {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def key(row):
    return row["Product_ID"], row["Store_ID"]


def audit(root, downloads_root):
    root = root.resolve()
    manifest = json.loads((root / FILES["generation_manifest"]).read_text())
    shared = json.loads((root / FILES["shared_locations"]).read_text())
    files = {role: {"relative_path": rel, **digest(root / rel)} for role, rel in FILES.items()}
    checks = []

    def check(name, requirement, expected, actual, sources):
        checks.append({"check_id": name, "requirement": requirement,
                       "expected": expected, "actual": actual,
                       "decision": "pass" if expected == actual else "fail",
                       "sources": sources, "evidence_mode": "real_local_source_audit"})

    for role, item in files.items():
        rel = item["relative_path"]
        if rel in manifest.get("files", {}):
            check("manifest_file_" + role, "Local bytes match generation manifest",
                  manifest["files"][rel], {field: item[field] for field in ("bytes", "sha256")},
                  [rel, FILES["generation_manifest"]])
        name = Path(rel).name
        if name in manifest.get("source_hashes", {}):
            check("manifest_source_hash_" + role, "Preserved source hash matches declared source hash",
                  manifest["source_hashes"][name], item["sha256"], [rel, FILES["generation_manifest"]])
        if name in shared.get("files", {}):
            check("recorded_drive_size_" + role, "Local size matches recorded Drive size; remote content is not verified",
                  int(shared["files"][name]["size"]), item["bytes"], [rel, FILES["shared_locations"]])

    columns, raw = read_csv(root / FILES["sales"])
    unique = {tuple(row[column] for column in columns): row for row in raw}
    rows = list(unique.values())
    cutoff = manifest["review_date"]
    past = [row for row in raw if row["Order_Date"] <= cutoff]
    future = [row for row in raw if row["Order_Date"] > cutoff]
    past_keys = {key(row) for row in past}
    dates = collections.defaultdict(set)
    for row in rows:
        dates[key(row)].add(row["Order_Date"])
    nonpositive = [row for row in rows if float(row["Quantity"]) <= 0]
    profile = {
        "note": "Observed facts about this supplied fixture; counts are not validity thresholds for future inputs.",
        "columns": len(columns), "raw_rows": len(raw), "distinct_rows": len(rows),
        "exact_duplicate_excess": len(raw) - len(rows),
        "distinct_transaction_ids": len({row["Transaction_ID"] for row in rows}),
        "product_ids": sorted({row["Product_ID"] for row in rows}),
        "store_ids": sorted({row["Store_ID"] for row in rows}), "product_store_keys": len(dates),
        "date_min": min(row["Order_Date"] for row in rows), "date_max": max(row["Order_Date"] for row in rows),
        "all_observed_dates": len({row["Order_Date"] for row in rows}),
        "per_key_observed_dates_min_median_max": [min(map(len, dates.values())), statistics.median(map(len, dates.values())), max(map(len, dates.values()))],
        "nonpositive_raw_rows": sum(float(row["Quantity"]) <= 0 for row in raw),
        "nonpositive_distinct_rows": len(nonpositive),
        "nonpositive_records": [{column: row[column] for column in ("Transaction_ID", "Product_ID", "Store_ID", "Order_Date", "Quantity", "Order_Status", "Return_Flag")} for row in nonpositive],
        "status_counts_distinct": dict(sorted(collections.Counter(row["Order_Status"] for row in rows).items())),
        "return_counts_distinct": dict(sorted(collections.Counter(row["Return_Flag"] for row in rows).items())),
        "past_raw_rows": len(past),
        "past_exact_duplicate_excess": len(past) - len({tuple(row[column] for column in columns) for row in past}),
        "future_raw_rows": len(future),
        "future_distinct_rows": len({tuple(row[column] for column in columns) for row in future}),
        "past_product_store_keys": len(past_keys),
        "required_field_blank_counts": {column: sum(not row[column].strip() for row in rows) for column in ("Transaction_ID", "Product_ID", "Store_ID", "Order_Date", "Quantity", "Order_Status", "Return_Flag")},
        "product_name_blank_count": sum(not row["Product_Name"].strip() for row in rows),
        "identity_mappings": {},
    }
    for id_column, attributes in (("Product_ID", ("Product_Name", "Product_Category", "Product_Subcategory")), ("Store_ID", ("Store_Name", "Country", "Region", "City"))):
        for attribute in attributes:
            values = collections.defaultdict(set)
            for row in rows:
                if row[attribute].strip():
                    values[row[id_column]].add(row[attribute])
            profile["identity_mappings"][id_column + "_to_" + attribute] = {identifier: sorted(labels) for identifier, labels in sorted(values.items()) if len(labels) > 1}
    check("transaction_identity_after_exact_dedup", "Transaction_ID identifies a distinct supplied transaction",
          len(rows), len({row["Transaction_ID"] for row in rows}), [FILES["sales"]])

    inv = read_csv(root / FILES["inventory"])[1]
    receipts = read_csv(root / FILES["receipts"])[1]
    policies = read_csv(root / FILES["policy"])[1]
    policy_by_key = {key(row): row for row in policies}
    inventory_keys = {key(row) for row in inv}
    receipt_sums = collections.Counter()
    for row in receipts:
        receipt_sums[key(row)] += int(row["Incoming_Qty"])
    operational = {
        "inventory_rows": len(inv), "inventory_unique_keys": len(inventory_keys),
        "policy_rows": len(policies), "policy_unique_keys": len(policy_by_key),
        "receipt_rows": len(receipts), "receipt_unique_keys": len(receipt_sums),
        "receipt_unique_line_ids": len({row["PO_Line_ID"] for row in receipts}),
        "keys_without_receipts": len(inventory_keys - set(receipt_sums)),
        "receipt_qty_sum": sum(receipt_sums.values()),
        "summary_qty_sum": sum(int(row["On_Order_Qty"]) for row in inv),
        "arrival_date_min": min(row["Expected_Arrival_Date"] for row in receipts) if receipts else None,
        "arrival_date_max": max(row["Expected_Arrival_Date"] for row in receipts) if receipts else None,
        "supplier_lead_days": sorted({int(row["Supplier_Lead_Time_Days"]) for row in policies}),
        "review_days": sorted({int(row["Review_Period_Days"]) for row in policies}),
        "order_multiples": sorted({int(row["Order_Multiple_Qty"]) for row in policies}),
    }
    src = [FILES["inventory"], FILES["receipts"], FILES["policy"]]
    check("inventory_unique_keys", "No inventory join expansion", len(inv), len(inventory_keys), [FILES["inventory"]])
    check("policy_unique_keys", "No policy join expansion", len(policies), len(policy_by_key), [FILES["policy"]])
    check("receipt_line_unique", "Purchase-order lines are unique", len(receipts), len({row["PO_Line_ID"] for row in receipts}), [FILES["receipts"]])
    check("inventory_sales_key_coverage", "Fixture inventory covers past-sales keys exactly", sorted(past_keys), sorted(inventory_keys), [FILES["sales"], FILES["inventory"]])
    check("policy_inventory_key_coverage", "Fixture policy covers inventory keys exactly", sorted(inventory_keys), sorted(policy_by_key), src)
    check("receipt_orphan_keys", "Every receipt references a fixture policy key", [], sorted(set(receipt_sums) - set(policy_by_key)), src)
    check("summary_receipt_reconciliation", "On_Order_Qty summarizes receipt lines; never add both", [],
          [list(key(row)) for row in inv if int(row["On_Order_Qty"]) != receipt_sums[key(row)]], src)
    check("complete_ledger_zero_rule", "Only explicitly complete fixture ledgers authorize absent-line zero", [],
          [list(key(row)) for row in inv if key(row) not in receipt_sums and not (row["Open_Order_Ledger_Complete"] == "true" and int(row["On_Order_Qty"]) == 0)], src)
    check("fixture_complete_flags", "This synthetic fixture declares complete ledgers for all covered keys", ["true"], sorted({row["Open_Order_Ledger_Complete"] for row in inv}), src)
    check("operational_units", "No implicit pack/weight/currency conversion", ["product_unit"], sorted({row["Quantity_Unit"] for row in inv + receipts + policies}), src)
    check("operational_synthetic_provenance", "Operational facts remain explicitly synthetic", ["synthetic"], sorted({row["Provenance"] for row in inv + receipts + policies}), src)
    check("inventory_as_of", "Inventory belongs to declared review date", [cutoff], sorted({row["Snapshot_Date"] for row in inv}), src)
    check("policy_as_of", "Policy belongs to declared review date", [cutoff], sorted({row["Effective_Date"] for row in policies}), src)
    timing_failures, multiple_failures = [], []
    for row in receipts:
        policy = policy_by_key.get(key(row))
        if not policy:
            timing_failures.append(row["PO_Line_ID"])
            multiple_failures.append(row["PO_Line_ID"])
            continue
        elapsed = (dt.date.fromisoformat(row["Expected_Arrival_Date"]) - dt.date.fromisoformat(row["Order_Date"])).days
        if not row["Order_Date"] <= cutoff < row["Expected_Arrival_Date"] or elapsed != int(policy["Supplier_Lead_Time_Days"]):
            timing_failures.append(row["PO_Line_ID"])
        multiple = int(policy["Order_Multiple_Qty"])
        if multiple <= 0 or int(row["Incoming_Qty"]) % multiple:
            multiple_failures.append(row["PO_Line_ID"])
    check("receipt_timing", "Open receipt placement/arrival matches supplier lead time", [], timing_failures, src)
    check("receipt_multiples", "Incoming quantities follow explicit fixture multiples", [], multiple_failures, src)
    numeric_errors = []
    for role, records, fields in (("inventory", inv, ("Usable_On_Hand_Qty", "On_Order_Qty")), ("receipts", receipts, ("Incoming_Qty",)), ("policy", policies, ("Safety_Stock_Qty", "Minimum_Order_Qty", "Order_Multiple_Qty", "Supplier_Lead_Time_Days", "Review_Period_Days"))):
        for row in records:
            for field in fields:
                try:
                    value = int(row[field])
                    if value < 0 or field in ("Incoming_Qty", "Minimum_Order_Qty", "Order_Multiple_Qty", "Supplier_Lead_Time_Days", "Review_Period_Days") and value == 0:
                        raise ValueError("invalid sign")
                except ValueError:
                    numeric_errors.append({"role": role, "key": list(key(row)), "field": field})
    check("operational_integer_signs", "Quantities are nonnegative integer units; lead/review/multiple/minimum/receipt are positive", [], numeric_errors, src)

    declared_count_actuals = {"raw_sales_rows": len(raw), "past_raw_rows": len(past), "past_exact_duplicate_excess": profile["past_exact_duplicate_excess"], "future_raw_rows_excluded_from_generation": len(future), "eligible_product_store_keys": len(past_keys), "inventory_rows": len(inv), "inbound_rows": len(receipts), "policy_rows": len(policies), "keys_explicitly_without_open_orders": operational["keys_without_receipts"]}
    for name, actual in declared_count_actuals.items():
        if name in manifest.get("counts", {}):
            check("manifest_profile_" + name, "Observed fixture count reconciles with declared manifest; not a future-input validity rule", manifest["counts"][name], actual, [FILES["generation_manifest"]])

    originals = {}
    for role in ("sales", "dictionary"):
        original = downloads_root / Path(FILES[role]).name if downloads_root else None
        item = {"available": bool(original and original.is_file()), "portability_requirement": False}
        if item["available"]:
            item.update({"path": str(original), **digest(original)})
            check("original_copy_" + role, "Available original matches preserved raw bytes", files[role]["sha256"], item["sha256"], [str(original), FILES[role]])
        else:
            item["decision"] = "not_checked_original_unavailable"
        originals[role] = item
    return {"audit_kind": "real_local_source_and_fixture_reconciliation", "not_pipeline_or_model_acceptance": True,
            "data_root": str(root), "files": files, "observed_sales_profile": profile,
            "observed_operational_profile": operational, "original_download_comparison": originals,
            "checks": checks, "summary": {"passed": sum(c["decision"] == "pass" for c in checks), "failed": sum(c["decision"] == "fail" for c in checks)},
            "limitations": ["Remote Drive content and current issue state are not verified by this script.", "Hash and fixture checks do not settle target semantics, temporal field availability, sales-ledger completeness, or real operational facts.", "No cleaning, joins, feature materialization, forecasts, models, validation scores, or restocking recommendations are created."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--downloads-root", type=Path, default=Path.home() / "Downloads", help="Optional originals location; absent originals do not invalidate the portable audit")
    parser.add_argument("--output", type=Path, help="Write JSON here; otherwise print JSON")
    args = parser.parse_args()
    result = audit(args.data_root, args.downloads_root)
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(content)
    else:
        print(content, end="")
    return 1 if result["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
