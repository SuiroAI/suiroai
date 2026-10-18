"""Forecast-to-candidate purchase arithmetic, separate from presentation.

Only immutable saved forecast bytes and as-of operational files are consumed.
Adapters normalize file formats; they must not train, refit or allocate an
aggregate forecast uniformly across days. DSC-30 independently recalculates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import csv
from datetime import date, timedelta
from decimal import Decimal, Inexact, InvalidOperation, localcontext
import io
import json
import unicodedata

from suiroai.contracts import record_ref
from .context import Handoff, InputError

KEY_FIELDS = ("source_namespace", "product_id", "store_id")
STOCK_FIELDS = {"Product_ID", "Store_ID", "Snapshot_Date", "Usable_On_Hand_Qty",
                "On_Order_Qty", "Open_Order_Ledger_Complete", "Quantity_Unit", "Provenance"}
RECEIPT_FIELDS = {"PO_Line_ID", "Product_ID", "Store_ID", "Order_Date",
                  "Expected_Arrival_Date", "Incoming_Qty", "Quantity_Unit", "Provenance"}
POLICY_FIELDS = {"Product_ID", "Store_ID", "Effective_Date", "Supplier_Lead_Time_Days",
                 "Review_Period_Days", "Order_Multiple_Qty", "Minimum_Order_Qty",
                 "Safety_Stock_Qty", "Quantity_Unit", "Provenance"}


class _KeyError(InputError):
    def __init__(self, reason, audit):
        super().__init__(reason)
        self.audit = audit


def _key(value):
    if (not isinstance(value, dict) or set(value) != set(KEY_FIELDS)
            or any(not isinstance(value[f], str) or not value[f].strip() for f in KEY_FIELDS)):
        raise InputError("invalid product/store/namespace key")
    return tuple(value[f] for f in KEY_FIELDS)


def _key_dict(key):
    return dict(zip(KEY_FIELDS, key))


def _day(value):
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise InputError("invalid calendar date") from None


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise InputError("quantity must be a finite nonnegative number")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise InputError("quantity must be a finite nonnegative number") from None
    if not result.is_finite() or result < 0:
        raise InputError("quantity must be a finite nonnegative number")
    return result


def _integer(value, minimum=0):
    number = _decimal(value)
    if number != number.to_integral_value() or number < minimum:
        raise InputError(f"integer quantity/day count must be at least {minimum}")
    return int(number)


def _sum(values):
    # Never let the ambient Decimal precision silently erase a small positive
    # need. Unsupported precision is a key exception, not a zero requirement.
    with localcontext() as context:
        context.prec = 28
        context.traps[Inexact] = True
        try:
            return sum(values, Decimal(0))
        except Inexact:
            raise InputError("forecast_precision_exceeds_exact_arithmetic_support") from None


def _number(value):
    """The shared JSON contract uses numbers; retain exact decimals in audit."""
    if value == value.to_integral_value():
        return int(value)
    result = float(value)
    if Decimal(str(result)) != value:
        raise InputError("forecast_precision_not_representable_in_shared_numeric_contract")
    return result


def _csv(data, fields):
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise InputError("missing/duplicate CSV headers")
        if not fields <= set(reader.fieldnames):
            raise InputError("missing required CSV headers: " + ", ".join(sorted(fields - set(reader.fieldnames))))
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise InputError("malformed CSV row")
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise InputError("unreadable CSV input") from exc


def _check(check_id, status, expected, actual, refs):
    return {"check_id": check_id, "requirement_id": "DSC-29/" + check_id,
            "status": status, "expected": expected,
            "actual": json.dumps(actual, sort_keys=True, allow_nan=False),
            "evidence_refs": deepcopy(refs), "verifier": "DSC-29-producer-self-check"}


def _source_ref(execution, submission, role, namespace):
    files = [f for f in submission["files"] if f["source_role"] == role
             and f["source_namespace"] == namespace and f["access"] == "accessible"]
    if len(files) != 1:
        raise InputError(f"one accessible approved {role} file in namespace required")
    source = files[0]
    refs = [r for r in execution["source_refs"] if r["artifact_id"] == source["file_id"]
            and r["sha256"] == source["sha256"] and r["provenance"] == source["provenance"]]
    if len(refs) != 1:
        raise InputError(f"{role} bytes are not an exact approved source reference")
    return refs[0]


def _product_name_mapping(rows, as_of):
    if not rows:
        raise InputError("missing_product_name_mapping")
    if len(rows) != 1:
        names = {row.get("product_name") for _, row in rows if isinstance(row.get("product_name"), str)}
        code = "conflicting_product_name_mapping" if len(names) > 1 else "duplicate_product_name_mapping"
        raise InputError(code)
    mapping = rows[0][1]
    if not {"key", "product_name", "latest_information_available_date"} <= set(mapping):
        raise InputError("product_name_adapter_missing_fields")
    available = _day(mapping["latest_information_available_date"])
    if available > as_of:
        raise InputError("product_name_mapping_uses_future_information")
    name = mapping["product_name"]
    if (not isinstance(name, str) or not name or name != name.strip() or len(name) > 256
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} or c in "<>[]`*_~" for c in name)):
        raise InputError("unsafe_or_empty_product_name_mapping")
    return name, available.isoformat()


def calculate_candidate(handoff: Handoff, *, artifact_id: str, scope_ref: dict,
                        scope_reader, forecast_reader, source_namespace: str,
                        artifact_version: int = 1, name_ref: dict | None = None,
                        name_reader=None) -> dict:
    """Return an unapproved DSC-24 quantity_result, including per-key exceptions.

    scope_reader(bytes) -> the explicitly bound requested key list.
    forecast_reader(bytes) -> daily dictionaries with key, date, quantity,
    quantity_unit, as_of_date, latest_information_available_date.
    Optional name_reader(bytes) -> dictionaries with key, product_name and
    latest_information_available_date; name_ref must bind an approved source
    or frozen development input. Supply both optional arguments or neither.

    Source formats are supplied by DSC-28/parent adapters, not a new wire
    contract. All adapters receive verified bytes only. All daily values and
    source row positions remain in arithmetic check evidence for DSC-30.

    Date-only arrivals receive conservative end-of-day treatment. A key needing
    stock before that day's arrival is withheld as timing_ambiguity/shortage;
    an order placed now cannot cure a shortage before supplier arrival.
    """
    handoff.validate()
    execution = handoff.one("execution_contract")
    final = handoff.one("final_validation_result")
    evaluation = handoff.one("evaluation_result")
    if "calculate_restocking" not in execution["allowed_actions"]:
        raise InputError("restocking arithmetic is outside approved actions")
    if final["outcome"] != "pass":
        raise InputError("passed final validation is a prerequisite for candidate orders")
    handoff.authorize(final, "parent_review", {"proceed", "pass_after_recheck"})
    if final["parent_review"]["checkpoint"] != "final_validation":
        raise InputError("wrong final-validation checkpoint")
    frozen = evaluation["frozen"]
    as_of = _day(execution["temporal_plan"]["as_of_date"])
    if frozen["forecast_as_of_date"] != as_of.isoformat():
        raise InputError("saved forecast as-of mismatch")
    forecast_ref = frozen["november_30_forecast_ref"]
    submission = handoff.one("submission")
    refs = [forecast_ref] + [_source_ref(execution, submission, role, source_namespace)
                            for role in ("usable_stock", "inbound_ledger", "ordering_policy")]
    stock_ref, receipt_ref, policy_ref = refs[1:]
    # Scope is an explicit reviewed artifact: do not silently take an inner join.
    if scope_ref not in execution["source_refs"] and not any(
            scope_ref == r for r in frozen["development_input_refs"]):
        raise InputError("scope must bind an approved source or frozen development artifact")
    if not callable(scope_reader) or not callable(forecast_reader):
        raise InputError("explicit scope and frozen-forecast readers required")
    if (name_ref is None) != (name_reader is None):
        raise InputError("product name reference and reader must be supplied together")
    if name_ref is not None:
        if not callable(name_reader):
            raise InputError("explicit product name reader required")
        if name_ref not in execution["source_refs"] and name_ref not in frozen["development_input_refs"]:
            raise InputError("product name mapping must bind an approved source or frozen development artifact")
    scope = [_key(k) for k in scope_reader(handoff.read(scope_ref))]
    if not scope or len(set(scope)) != len(scope):
        raise InputError("scope must contain unique explicit requested keys")
    if any(k[0] != source_namespace for k in scope):
        raise InputError("scope/source namespace mismatch")
    refs.append(scope_ref)
    if name_ref is not None:
        refs.append(name_ref)
    refs = list({json.dumps(r, sort_keys=True): r for r in refs}.values())
    input_data = {json.dumps(r, sort_keys=True): handoff.read(r) for r in refs}
    stocks = _csv(input_data[json.dumps(stock_ref, sort_keys=True)], STOCK_FIELDS)
    receipts = _csv(input_data[json.dumps(receipt_ref, sort_keys=True)], RECEIPT_FIELDS)
    policies = _csv(input_data[json.dumps(policy_ref, sort_keys=True)], POLICY_FIELDS)
    forecasts = list(forecast_reader(input_data[json.dumps(forecast_ref, sort_keys=True)]))
    names = (list(name_reader(input_data[json.dumps(name_ref, sort_keys=True)]))
             if name_ref is not None else [])
    name_index = defaultdict(list)
    indexed = [defaultdict(list) for _ in range(4)]
    problems = defaultdict(list)
    for rows, index in ((stocks, indexed[0]), (receipts, indexed[1]), (policies, indexed[2])):
        for line, row in enumerate(rows, 2):
            if not row["Product_ID"].strip() or not row["Store_ID"].strip():
                raise InputError("operational row lacks an attributable product/store key")
            key = (source_namespace, row["Product_ID"], row["Store_ID"])
            index[key].append((line, row))
    for line, row in enumerate(forecasts, 1):
        if not isinstance(row, dict):
            raise InputError("forecast reader must return daily dictionaries")
        key = _key(row.get("key"))
        indexed[3][key].append((line, row))
    for line, row in enumerate(names, 1):
        if not isinstance(row, dict):
            raise InputError("product name reader must return mapping dictionaries")
        key = _key(row.get("key"))
        name_index[key].append((line, row))
        if key[0] != source_namespace:
            problems[key].append("product_name_mapping_source_namespace_mismatch")
    product_names = defaultdict(set)
    product_stores = defaultdict(set)
    for key, rows in name_index.items():
        product_stores[key[:2]].add(key[2])
        for _, row in rows:
            if isinstance(row.get("product_name"), str):
                product_names[key[:2]].add(row["product_name"])
    for key in name_index:
        if len(product_names[key[:2]]) > 1 and len(product_stores[key[:2]]) > 1:
            problems[key].append("conflicting_product_names_across_stores")
    # A duplicate receipt identifier poisons every affected key, including the
    # first occurrence. Never silently deduplicate or double-count it.
    ids = Counter(row["PO_Line_ID"] for row in receipts)
    for row in receipts:
        if not row["PO_Line_ID"].strip() or ids[row["PO_Line_ID"]] > 1:
            problems[(source_namespace, row["Product_ID"], row["Store_ID"])].append("duplicate_or_empty_receipt_line_id")
    all_keys = set(scope).union(set(name_index), *(set(index) for index in indexed))
    result = handoff.envelope("quantity_result", artifact_id, artifact_version)
    result.update(final_validation_ref=record_ref(final),
                  frozen_result_ref=deepcopy(final["frozen_result_ref"]),
                  november_30_forecast_ref=deepcopy(forecast_ref),
                  arithmetic_source_refs=deepcopy(refs), orders=[], exceptions=[],
                  arithmetic_checks=[], independent_check_refs=[], parent_decision=None,
                  candidate_quantity_ref=None)
    for position, key in enumerate(sorted(all_keys), 1):
        audit = {"key": _key_dict(key), "as_of_date": as_of.isoformat(),
                 "quantity_unit": "product_unit", "receipt_convention": "end_of_day_conservative",
                 "source_rows": {label: [line for line, _ in index[key]] for label, index in
                                 zip(("stock", "receipts", "policy", "forecast"), indexed)}}
        if name_ref is not None:
            audit["source_rows"]["names"] = [line for line, _ in name_index[key]]
        reasons = list(dict.fromkeys(problems[key]))
        if key not in scope:
            reasons.append("unexpected_key_outside_requested_scope")
        try:
            if reasons:
                raise InputError(", ".join(reasons))
            if name_ref is not None:
                name, available = _product_name_mapping(name_index[key], as_of)
                audit.update(product_name=name, product_name_latest_information_available_date=available)
            row, key_audit = _calculate_key(key, indexed, execution, as_of, forecast_ref, refs)
            if name_ref is not None:
                row["product_name"] = name
            audit.update(key_audit)
            result["orders"].append(row)
        except InputError as exc:
            reason = str(exc)
            if isinstance(exc, _KeyError):
                audit.update(exc.audit)
            audit["exception"] = reason
            result["exceptions"].append({"key": _key_dict(key), "reason": reason,
                                         "evidence_refs": deepcopy(refs)})
        result["arithmetic_checks"].append(_check(
            f"key-{position}", "unavailable" if "exception" in audit else "pass",
            "complete as-of inputs; reconciled ledger; daily stock coverage; net need rounded by declared policy",
            audit, refs))
    result["arithmetic_checks"].append(_check(
        "coverage", "pass", "each requested key has one order or an explicit exception",
        {"requested_keys": len(scope), "orders": len(result["orders"]),
         "exceptions": len(result["exceptions"]), "self_check_only": True}, refs))
    return handoff.finish(result)


def _calculate_key(key, indexed, execution, as_of, forecast_ref, refs):
    stock_rows, receipt_rows, policy_rows, forecast_rows = (index[key] for index in indexed)
    if len(stock_rows) != 1 or len(policy_rows) != 1:
        raise InputError("missing_or_duplicate_stock_or_policy")
    stock, policy = stock_rows[0][1], policy_rows[0][1]
    if _day(stock["Snapshot_Date"]) != as_of or _day(policy["Effective_Date"]) != as_of:
        raise InputError("stale_or_future_stock_or_policy_requires_reviewed_movements_or_effectivity_evidence")
    for row in [stock, policy] + [r for _, r in receipt_rows]:
        if row["Quantity_Unit"] != "product_unit":
            raise InputError("incompatible_quantity_unit")
        if row["Provenance"] != "synthetic":
            raise InputError("active_demo_requires_declared_synthetic_operational_rows")
    if stock["Open_Order_Ledger_Complete"].lower() != "true" or execution[
            "inbound_ledger_policy"] != "complete_synthetic_ledger_absence_is_zero":
        raise InputError("receipt_ledger_completeness_unknown_no_absent_key_zero")
    # The complete-ledger assertion is confined to declared synthetic sources.
    if any(ref not in execution["synthetic_operational_source_refs"] for ref in refs[1:4]):
        raise InputError("operational_sources_not_declared_synthetic_in_approved_task")
    usable = _integer(stock["Usable_On_Hand_Qty"])
    summary = _integer(stock["On_Order_Qty"])
    lead = _integer(policy["Supplier_Lead_Time_Days"], 1)
    review = _integer(policy["Review_Period_Days"], 1)
    minimum = _integer(policy["Minimum_Order_Qty"], 1)
    multiple = _integer(policy["Order_Multiple_Qty"], 1)
    safety = _integer(policy["Safety_Stock_Qty"])
    try:
        end = as_of + timedelta(days=lead + review)
        arrival = as_of + timedelta(days=lead)
    except (OverflowError, ValueError):
        raise InputError("policy_horizon_outside_supported_calendar") from None
    demands = {}
    for _, row in forecast_rows:
        required = {"key", "date", "quantity", "quantity_unit", "as_of_date", "latest_information_available_date"}
        if not required <= set(row):
            raise InputError("daily_forecast_adapter_missing_fields")
        day = _day(row["date"])
        if day <= as_of or _day(row["as_of_date"]) != as_of or _day(
                row["latest_information_available_date"]) > as_of:
            raise InputError("forecast_not_frozen_at_review_or_uses_future_information")
        if row["quantity_unit"] != "product_unit":
            raise InputError("incompatible_forecast_unit")
        if day in demands:
            raise InputError("duplicate_daily_forecast")
        demands[day] = _decimal(row["quantity"])
    if len(demands) < lead + review:
        raise InputError("partial_daily_forecast_cannot_prove_receipt_timing")
    expected_days = [as_of + timedelta(days=d) for d in range(1, lead + review + 1)]
    if any(day not in demands for day in expected_days):
        raise InputError("partial_daily_forecast_cannot_prove_receipt_timing")
    due = defaultdict(int)
    receipt_trace = []
    for line, row in receipt_rows:
        ordered = _day(row["Order_Date"])
        day = _day(row["Expected_Arrival_Date"])
        quantity = _integer(row["Incoming_Qty"], 1)
        if ordered > as_of or day <= as_of or day < ordered:
            raise InputError("future_order_or_overdue_receipt_requires_reconciled_asof_evidence")
        due[day] += quantity
        receipt_trace.append({"csv_row": line, "line_id": row["PO_Line_ID"],
                              "order_date": ordered.isoformat(), "arrival_date": day.isoformat(),
                              "quantity": quantity, "within_horizon": day <= end})
    if sum(due.values()) != summary:
        raise InputError(f"receipt_summary_mismatch: summary={summary}; ledger={sum(due.values())}")
    forecast = _sum(demands[d] for d in expected_days)
    eligible = sum(q for d, q in due.items() if d <= end)
    signed_need = _sum((forecast, Decimal(safety), Decimal(-usable), Decimal(-eligible)))
    need = max(Decimal(0), signed_need)
    # Exact rational ceiling avoids division rounding just above a multiple.
    numerator, denominator = max(need, Decimal(minimum)).as_integer_ratio()
    pack_denominator = denominator * multiple
    order = 0 if need == 0 else (numerator + pack_denominator - 1) // pack_denominator * multiple
    audit = {"forecast_quantity_exact": str(forecast), "usable_on_hand_quantity": usable,
             "on_order_summary_quantity": summary, "ledger_total_quantity": sum(due.values()),
             "eligible_receipt_quantity": eligible, "outside_horizon_receipt_quantity": summary - eligible,
             "signed_need_exact": str(signed_need), "raw_order_need_exact": str(need),
             "minimum_positive_order_quantity": minimum, "order_multiple": multiple,
             "rounded_order_quantity": order, "candidate_arrival_date": arrival.isoformat(),
             "receipts": receipt_trace, "daily_balances": [],
             "summary_subtracted": False, "safety_stock_quantity": safety}
    # Test each day's demand before date-only arrivals. Also test terminal
    # safety stock, so a late receipt cannot erase a prior demand shortage.
    balance = Decimal(usable)
    trace = []
    for day in expected_days:
        before = _sum((balance, demands[day].copy_negate()))
        placed_order = order if day == arrival else 0
        after = _sum((before, Decimal(due[day]), Decimal(placed_order)))
        trace.append({"date": day.isoformat(), "opening": str(balance),
                      "forecast": str(demands[day]), "before_arrivals": str(before),
                      "receipt_quantity": due[day], "candidate_arrival_quantity": placed_order,
                      "closing": str(after)})
        audit["daily_balances"] = trace
        if before < 0:
            code = "timing_ambiguity" if after >= 0 else "shortage"
            raise _KeyError(f"{code}: {day.isoformat()} before-arrivals balance={before}; "
                            f"after-arrivals balance={after}; later receipts/orders cannot cure earlier demand", audit)
        balance = after
    if balance < safety:
        raise _KeyError("terminal_safety_stock_not_covered", audit)
    row = {"key": _key_dict(key), "quantity_unit": "product_unit",
           "arithmetic_input_refs": deepcopy(refs), "forecast_ref": deepcopy(forecast_ref),
           "forecast_horizon_start": expected_days[0].isoformat(), "forecast_horizon_end": end.isoformat(),
           "forecast_quantity": _number(forecast), "usable_on_hand_quantity": usable,
           "on_order_summary_quantity": summary, "eligible_receipt_quantity": eligible,
           "supplier_lead_calendar_days": lead, "review_period_calendar_days": review,
           "safety_stock_quantity": safety, "order_multiple": multiple,
           "minimum_positive_order_quantity": minimum, "raw_order_need": _number(need),
           "rounded_order_quantity": order, "approved_order_quantity": None,
           "evidence_refs": deepcopy(refs)}
    return row, audit
