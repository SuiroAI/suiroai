"""Independently check the demonstrated CSV's chosen restocking arithmetic.

Read the four controller-released CSVs and the actual delivered CSV directly.
Use standard-library exact rational arithmetic, without importing or executing
Data's producer code. Retain hashes and aggregate checks, never personal rows.
This review does not grant frozen-holdout or authenticated workflow acceptance.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
import io
import json
import math
from pathlib import Path


def audit(run_root: Path, code_commit: str) -> dict:
    """Recompute all rows under the selected 90-day recorded-demand scenario."""
    measured = {}

    def load(relative: str) -> list[dict[str, str]]:
        data = (run_root / relative).read_bytes()
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        rows = list(reader)
        measured[relative] = {"sha256": sha256(data).hexdigest(), "bytes": len(data),
            "rows": len(rows), "columns": len(reader.fieldnames or [])}
        return rows

    transactions = load("released/input-1.csv")
    stock = load("released/input-2.csv")
    receipts = load("released/input-3.csv")
    policy = load("released/input-4.csv")
    result = load("output/restocking.csv")
    key = lambda row: (row["Product_ID"], row["Store_ID"])
    stock_by_key = {key(row): row for row in stock}
    policy_by_key = {key(row): row for row in policy}
    assert len(stock_by_key) == len(stock) == 336
    assert len(policy_by_key) == len(policy) == len(result) == 336
    assert set(map(key, result)) == set(stock_by_key) == set(policy_by_key)
    assert len({row["PO_Line_ID"] for row in receipts}) == len(receipts)

    as_of = date(2025, 11, 30)
    first_day = as_of - timedelta(days=89)
    seen = set()
    totals = defaultdict(int)
    duplicates = 0
    for row in transactions:
        identity = tuple(row.items())
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        when = date.fromisoformat(row["Order_Date"])
        assert when <= as_of
        if (first_day <= when <= as_of
                and row["Order_Status"].strip().lower() in {"completed", "shipped", "returned"}
                and int(row["Quantity"]) > 0):
            totals[key(row)] += int(row["Quantity"])

    assert all(date.fromisoformat(row["Order_Date"]) <= as_of
        < date.fromisoformat(row["Expected_Arrival_Date"]) for row in receipts)
    incoming_total = 0
    early_risks = 0
    for row in result:
        pair = key(row)
        inventory, rule = stock_by_key[pair], policy_by_key[pair]
        assert date.fromisoformat(inventory["Snapshot_Date"]) == as_of
        assert date.fromisoformat(rule["Effective_Date"]) == as_of
        assert inventory["Open_Order_Ledger_Complete"].strip().lower() == "true"
        lead = int(rule["Supplier_Lead_Time_Days"])
        horizon = lead + int(rule["Review_Period_Days"])
        through = as_of + timedelta(days=horizon)
        pair_receipts = [receipt for receipt in receipts if key(receipt) == pair]
        incoming = sum(int(receipt["Incoming_Qty"]) for receipt in pair_receipts
            if as_of < date.fromisoformat(receipt["Expected_Arrival_Date"]) <= through)
        assert sum(int(receipt["Incoming_Qty"]) for receipt in pair_receipts) == int(inventory["On_Order_Qty"])
        rate = Fraction(totals[pair], 90)
        shortage = (rate * horizon + int(rule["Safety_Stock_Qty"])
            - int(inventory["Usable_On_Hand_Qty"]) - incoming)
        multiple, minimum = int(rule["Order_Multiple_Qty"]), int(rule["Minimum_Order_Qty"])
        expected = 0 if shortage <= 0 else math.ceil(max(shortage, minimum) / multiple) * multiple
        assert int(row["OrderQty"]) == expected
        assert row["Quantity_Unit"] == inventory["Quantity_Unit"] == rule["Quantity_Unit"] == "product_unit"
        assert int(row["Recorded_90Day_Units"]) == totals[pair]
        assert int(row["Incoming_Within_Coverage"]) == incoming
        assert int(row["Usable_Stock"]) == int(inventory["Usable_On_Hand_Qty"])
        assert int(row["Stock_Buffer"]) == int(rule["Safety_Stock_Qty"])
        assert int(row["Pack_Size"]) == multiple and int(row["Minimum_Order"]) == minimum
        assert row["Coverage_Through"] == through.isoformat()
        assert row["As_Of_Date"] == as_of.isoformat()
        balance = Fraction(int(inventory["Usable_On_Hand_Qty"]))
        risk = False
        for offset in range(1, lead):
            day = as_of + timedelta(days=offset)
            balance += sum(int(receipt["Incoming_Qty"]) for receipt in pair_receipts
                if date.fromisoformat(receipt["Expected_Arrival_Date"]) == day)
            balance -= rate
            risk = risk or balance < 0
        assert row["Possible_Shortage_Before_New_Order_Arrives"].lower() == str(risk).lower()
        early_risks += risk
        incoming_total += incoming

    manifest_data = (run_root / "output/result.json").read_bytes()
    measured["output/result.json"] = {"sha256": sha256(manifest_data).hexdigest(), "bytes": len(manifest_data)}
    manifest = json.loads(manifest_data)
    assert manifest["output_file"] == "restocking.csv"
    assert manifest["output_sha256"] == measured["output/restocking.csv"]["sha256"]
    return {"format": "dsc59-independent-arithmetic-audit-v1",
        "reviewer": "Codex / plain-language-and-CSV-preview reviewer",
        "reviewed_at": datetime.now(timezone.utc).isoformat(), "code_commit": code_commit,
        "run_root": str(run_root), "auditor_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "decision": "pass_for_chosen_scenario_arithmetic_only", "measured_files": measured,
        "observed": {"rows_checked": len(result), "exact_duplicate_transactions_removed": duplicates,
            "order_units": sum(int(row["OrderQty"]) for row in result),
            "positive_order_rows": sum(int(row["OrderQty"]) > 0 for row in result),
            "zero_order_rows": sum(int(row["OrderQty"]) == 0 for row in result),
            "incoming_units_reconciled": incoming_total, "prearrival_risk_rows": early_risks},
        "checks_passed": ["source December outcomes absent", "source and output key coverage",
            "exact duplicate removal", "eligible 90-day recorded quantities", "stock and policy as-of dates",
            "receipt dates and ledger reconciliation", "lead plus review coverage",
            "stock/buffer/eligible receipt subtraction", "minimum and order-multiple rounding",
            "units and delivered calculation columns", "prearrival risk under stated timing convention",
            "manifest binds exact CSV bytes"],
        "limits": ["Validates the selected recorded-demand scenario, not complete underlying demand.",
            "Does not establish model superiority or frozen December holdout acceptance.",
            "Assumes expected receipts arrive before demand on their stated arrival date; new orders arrive after the checked prearrival interval.",
            "Separate reviewer calculation, not authenticated runtime verifier/parent approval or full milestone acceptance."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = audit(arguments.run_root, arguments.code_commit)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["observed"]))
