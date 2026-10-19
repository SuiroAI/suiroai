"""Generated MOCK CSVs and draft.3 authority examples; never customer data.

Build small sales and operational fixtures, measured artifacts, and exact
request permits for deterministic preparation component tests.
"""
from copy import deepcopy
import json
from pathlib import Path

from suiroai.contracts import record_ref, validate_record
from suiroai.preparation.worker import SALES, csv_bytes, sha, partition_sales

ROOT = Path(__file__).resolve().parents[2]


def sale(n=1, **changes):
    row = dict(Product_ID="MOCK-P1", Store_ID="MOCK-S1", Transaction_ID=f"MOCK-T{n}",
               Order_ID="MOCK-shared-order", Order_Date="2025-11-01", Quantity="3",
               Order_Status="Completed", Return_Flag="No", Product_Name="Mock product", Store_Name="Mock store")
    row.update(changes)
    return row


def artifact(name, data):
    return {"artifact_id": "mock-dsc27-" + name, "version": 1,
            "sha256": sha(data), "provenance": "mock"}


def authority(source_refs):
    fixture = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
    assert fixture["fixture_provenance"] == "mock"
    execution = deepcopy(next(r for r in fixture["records"] if r["kind"] == "execution_contract"))
    request = deepcopy(next(r for r in fixture["records"] if r["kind"] == "stage_request"))
    execution["source_refs"] = deepcopy(source_refs)
    execution["synthetic_operational_source_refs"] = deepcopy(source_refs[2:])
    execution["target_policy"] = {"status": "pending", "unresolved_gap_ids": ["mock-target-policy-investigation"]}
    request.update(stage="preparation", execution_contract_ref=record_ref(execution), released_input_refs=deepcopy(source_refs))
    request["parent_authorization"]["checkpoint"] = "preparation"
    for record in (execution, request):
        assert not validate_record(record), validate_record(record)
    return execution, request


def operations():
    common = dict(Product_ID="MOCK-P1", Store_ID="MOCK-S1", Quantity_Unit="product_unit", Provenance="synthetic")
    inventory = [dict(common, Snapshot_Date="2025-11-30", Usable_On_Hand_Qty="8", On_Order_Qty="7", Open_Order_Ledger_Complete="True")]
    receipts = [dict(common, PO_Line_ID="MOCK-PO1", Order_Date="2025-11-28", Expected_Arrival_Date="2025-12-05", Incoming_Qty="3"),
                dict(common, PO_Line_ID="MOCK-PO2", Order_Date="2025-11-29", Expected_Arrival_Date="2025-12-06", Incoming_Qty="4")]
    policy = [dict(common, Effective_Date="2025-11-30", Supplier_Lead_Time_Days="7", Review_Period_Days="7", Order_Multiple_Qty="2", Minimum_Order_Qty="4", Safety_Stock_Qty="0")]
    return inventory, receipts, policy


def packet(rows=None, mutate_operations=None):
    """Create actual local mock bytes, partition them, rebind all released refs."""
    rows = rows if rows is not None else [sale()]
    raw = csv_bytes(list(SALES), rows)
    dictionary = [dict(Column_Name=c, Business_Meaning="MOCK " + c,
                       Description="Units in a transaction" if c == "Quantity" else "MOCK dictionary definition") for c in SALES]
    inv, receipts, policy = operations()
    if mutate_operations:
        mutate_operations(inv, receipts, policy)
    payloads = {"sales": raw, "dictionary": csv_bytes(list(dictionary[0]), dictionary),
                "inventory": csv_bytes(list(inv[0]) if inv else list(operations()[0][0]), inv),
                "receipts": csv_bytes(list(receipts[0]) if receipts else list(operations()[1][0]), receipts),
                "policy": csv_bytes(list(policy[0]) if policy else list(operations()[2][0]), policy)}
    refs = {role: artifact(role, data) for role, data in payloads.items()}
    execution, request = authority(list(refs.values()))
    partition = partition_sales(raw, refs["sales"], execution=execution, request=request, parent_permits=lambda *_: True)
    dev = partition["development_csv"]
    sources = {role: {"data": data, "ref": refs[role]} for role, data in payloads.items()}
    sources["sales"] = {"data": dev, "ref": artifact("development-sales", dev)}
    request["released_input_refs"].remove(refs["sales"])
    request["released_input_refs"].append(sources["sales"]["ref"])
    return dict(sources=sources, execution=execution, request=request,
                development_receipt=partition["development_receipt"], parent_permits=lambda *_: True), partition
