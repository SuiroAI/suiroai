"""Independent, source-based restocking reconciliation; no producer arithmetic imports.

Raw operation rows retain CSV columns and must carry an explicit ``source_namespace``.
Forecast/name rows use contract ``key`` mappings. Returned decimal numbers are strings
so evidence survives JSON serialization without a binary floating point conversion.

Recompute candidate quantities against frozen forecasts, usable stock, timely
receipts, units, dates, and purchasing constraints; expose unsupported keys
rather than hiding exceptions or counting the receipt summary twice.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any


_KEY_FIELDS = ("source_namespace", "product_id", "store_id")
_PROVENANCE = {"supplied", "synthetic", "derived", "mock"}


def _key(row: dict) -> tuple[str, str, str]:
    value = row.get("key", row)
    if "Product_ID" in row or "Store_ID" in row:
        raw = {"source_namespace": row.get("source_namespace"),
               "product_id": row.get("Product_ID"), "store_id": row.get("Store_ID")}
        if "key" in row and value != raw:
            raise ValueError("raw and normalized identities differ")
        value = raw
    if not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not value[k] or value[k] != value[k].strip() for k in _KEY_FIELDS):
        raise ValueError("explicit, exact namespace/product/store strings required")
    return tuple(value[k] for k in _KEY_FIELDS)


def _mapping(key):
    return dict(zip(_KEY_FIELDS, key))


def _number(value, *, integer=False, positive=False):
    if isinstance(value, bool) or value is None:
        raise ValueError("quantity must be finite numeric data")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("quantity must be finite numeric data") from None
    if not result.is_finite() or result < 0 or (positive and result <= 0) or (integer and result != result.to_integral_value()):
        raise ValueError("quantity must be finite, nonnegative and use required whole product units")
    return result


def _date(value):
    if not isinstance(value, str):
        raise ValueError("ISO calendar date required")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("ISO calendar date required")
    return parsed


def _wire(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _has_evidence(row):
    refs = row.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False
    for ref in refs:
        if not isinstance(ref, dict):
            return False
        sha = ref.get("sha256")
        version = ref.get("version")
        if (not isinstance(ref.get("artifact_id"), str) or not ref["artifact_id"].strip()
                or not isinstance(version, int) or isinstance(version, bool) or version < 1
                or not isinstance(sha, str) or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
                or not isinstance(ref.get("provenance"), str)
                or ref.get("provenance") not in _PROVENANCE):
            return False
    return True


def reconcile_orders(orders, exceptions, *, scope_keys, forecast_rows, inventory_rows,
                     receipt_rows, policy_rows, name_rows, as_of="2025-11-30",
                     ledger_complete=False, receipt_timing="unknown",
                     require_product_names=True) -> dict[str, Any]:
    """Recompute source arithmetic and compare every candidate intermediate.

    A missing/stale/ambiguous source or unsatisfied receipt timing produces an explicit
    per-key exception, never a substitute quantity. An honestly evidenced and withheld
    exception may pass output verification while its source problem remains in the
    returned exception list. ``ledger_complete`` must be the
    authenticated execution-contract ledger assertion, not a producer pass flag.
    Candidate approved quantities may be null while awaiting parent approval.
    ``require_product_names=False`` supports numerical candidates with IDs only;
    any supplied candidate name still requires independent naming evidence.
    """
    checks, found_exceptions, expected_orders = [], [], []

    def check(check_id, okay, expected, actual, key=None):
        item = {"check_id": check_id, "status": "pass" if okay else "fail",
                "expected": _wire(expected), "actual": _wire(actual)}
        if key is not None:
            item["key"] = _mapping(key)
        checks.append(item)

    def problem(key, reason):
        item = {"key": _mapping(key), "reason": reason}
        if item not in found_exceptions:
            found_exceptions.append(item)

    try:
        review = _date(as_of)
    except (ValueError, TypeError):
        check("as_of_date", False, "ISO calendar date", as_of)
        return {"checks": checks, "exceptions": [], "expected_orders": []}
    if receipt_timing not in ("unknown", "before_daily_demand"):
        check("receipt_timing_convention", False, "unknown or approved before_daily_demand", receipt_timing)
        return {"checks": checks, "exceptions": [], "expected_orders": []}

    scope = set()
    for row in scope_keys:
        try:
            key = _key(row)
            check("scope_identity_unique", key not in scope, "one exact key", row, key)
            scope.add(key)
        except (ValueError, TypeError, AttributeError) as error:
            check("scope_identity", False, "exact namespaced key", str(error))
    check("scope_nonempty", bool(scope), "at least one scoped key", len(scope))

    def group(rows, label):
        result = defaultdict(list)
        for row in rows:
            try:
                key = _key(row)
            except (ValueError, TypeError, AttributeError) as error:
                check(label + "_identity", False, "exact namespaced identity", str(error))
                continue
            if key not in scope:
                check(label + "_scope", False, "scoped key", row, key)
            else:
                result[key].append(row)
        return result

    sources = {label: group(rows, label) for label, rows in (
        ("forecast", forecast_rows), ("inventory", inventory_rows),
        ("receipt", receipt_rows), ("policy", policy_rows), ("name", name_rows),
        ("order", orders), ("exception", exceptions))}

    # A SKU identity cannot acquire a different canonical name at another store.
    # Preserve every affected key rather than choose a first/last source spelling.
    product_names = defaultdict(set)
    for key, rows in sources["name"].items():
        for row in rows:
            name = row.get("product_name")
            if isinstance(name, str) and name.strip():
                product_names[key[:2]].add(name)
    for key in sorted(scope):
        if len(product_names[key[:2]]) > 1:
            problem(key, "conflicting_product_names_across_stores")

    # PO line identity is ledger-wide, not merely unique inside a product/store key.
    po_seen = {}
    for key, rows in sources["receipt"].items():
        for row in rows:
            po = row.get("PO_Line_ID")
            if not isinstance(po, str) or not po:
                problem(key, "missing_or_duplicate_po_line_id")
            elif po in po_seen:
                problem(key, "missing_or_duplicate_po_line_id")
                problem(po_seen[po], "missing_or_duplicate_po_line_id")
            else:
                po_seen[po] = key

    for key in sorted(scope):
        supplied_orders, supplied_exceptions = sources["order"][key], sources["exception"][key]
        if len(supplied_orders) > 1 or len(supplied_exceptions) > 1 or (supplied_orders and supplied_exceptions):
            check("key_output_identity", False, "one order or explicit exception", {"orders": len(supplied_orders), "exceptions": len(supplied_exceptions)}, key)
        try:
            inventory, policy, names = (sources[label][key] for label in ("inventory", "policy", "name"))
            name_required = require_product_names or any(row.get("product_name") is not None for row in supplied_orders)
            if (len(inventory) != 1 or len(policy) != 1 or len(names) > 1
                    or (name_required and not names)):
                raise ValueError("missing_or_duplicate_inventory_policy_or_name")
            stock, rule = inventory[0], policy[0]
            name = names[0] if names else None
            if _date(stock.get("Snapshot_Date")) != review:
                raise ValueError("stale_or_future_stock_snapshot")
            if _date(rule.get("Effective_Date")) > review:
                raise ValueError("policy_not_effective_as_of")
            for label, rows in (("inventory", inventory), ("policy", policy), ("receipt", sources["receipt"][key])):
                for row in rows:
                    if row.get("Quantity_Unit") != "product_unit":
                        raise ValueError(label + "_unit_mismatch")
                    if not isinstance(row.get("Provenance"), str) or not row["Provenance"].strip():
                        raise ValueError(label + "_missing_provenance")
                    if row["Provenance"] not in _PROVENANCE:
                        raise ValueError(label + "_invalid_provenance")
                    if row["Provenance"] not in {"synthetic", "mock"}:
                        raise ValueError(label + "_operational_source_not_labeled_synthetic")
            if name is not None:
                if not isinstance(name.get("product_name"), str) or not name["product_name"].strip():
                    raise ValueError("missing_product_name")
                if _date(name.get("latest_information_available_date")) > review:
                    raise ValueError("product_name_not_available_as_of")
            lead = int(_number(rule.get("Supplier_Lead_Time_Days"), integer=True, positive=True))
            period = int(_number(rule.get("Review_Period_Days"), integer=True, positive=True))
            # Bound dates to Python's calendar; a malicious duration is an exception.
            start, end = review + timedelta(days=1), review + timedelta(days=lead + period)
            on_hand = _number(stock.get("Usable_On_Hand_Qty"), integer=True)
            summary = _number(stock.get("On_Order_Qty"), integer=True)
            safety = _number(rule.get("Safety_Stock_Qty"), integer=True)
            minimum = _number(rule.get("Minimum_Order_Qty"), integer=True, positive=True)
            multiple = _number(rule.get("Order_Multiple_Qty"), integer=True, positive=True)
            if ledger_complete is not True or stock.get("Open_Order_Ledger_Complete") not in (True, "true"):
                raise ValueError("open_order_ledger_not_explicitly_complete")
            daily = {}
            for row in sources["forecast"][key]:
                day = _date(row.get("date"))
                if row.get("quantity_unit") != "product_unit":
                    raise ValueError("forecast_unit_mismatch")
                if _date(row.get("as_of_date")) != review or _date(row.get("latest_information_available_date")) > review:
                    raise ValueError("forecast_stale_or_future_information")
                if day in daily:
                    raise ValueError("duplicate_forecast_date")
                daily[day] = _number(row.get("quantity"))
            if len(daily) < lead + period:
                raise ValueError("incomplete_daily_forecast_coverage")
            horizon = [start + timedelta(days=i) for i in range(lead + period)]
            if not all(day in daily for day in horizon):
                raise ValueError("incomplete_daily_forecast_coverage")
            receipts, ledger_sum = defaultdict(Decimal), Decimal(0)
            for row in sources["receipt"][key]:
                ordered = _date(row.get("Order_Date"))
                arrival = _date(row.get("Expected_Arrival_Date"))
                quantity = _number(row.get("Incoming_Qty"), integer=True, positive=True)
                if ordered > review or arrival <= review or arrival < ordered:
                    raise ValueError("receipt_dates_not_open_as_of")
                ledger_sum += quantity
                if arrival <= end:
                    receipts[arrival] += quantity
            if ledger_sum != summary:
                raise ValueError("on_order_summary_does_not_reconcile_to_ledger")
            forecast = sum((daily[day] for day in horizon), Decimal(0))
            eligible = sum(receipts.values(), Decimal(0))
            raw = max(Decimal(0), forecast + safety - on_hand - eligible)
            rounded = ((max(raw, minimum) / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple) if raw else Decimal(0)
            balance = on_hand
            for day in horizon:
                arrivals = receipts[day]
                if day == review + timedelta(days=lead):
                    arrivals += rounded
                before = balance - daily[day]
                after = before + arrivals
                if after < 0:
                    raise ValueError("timing_shortage_on_" + day.isoformat())
                if receipt_timing == "unknown" and before < 0 and arrivals:
                    raise ValueError("timing_ambiguity_on_" + day.isoformat())
                balance = after
            expected = {"key": _mapping(key), "quantity_unit": "product_unit",
                        "forecast_horizon_start": start.isoformat(), "forecast_horizon_end": end.isoformat(),
                        "forecast_quantity": forecast, "usable_on_hand_quantity": on_hand,
                        "on_order_summary_quantity": summary, "eligible_receipt_quantity": eligible,
                        "supplier_lead_calendar_days": lead, "review_period_calendar_days": period,
                        "safety_stock_quantity": safety, "order_multiple": multiple,
                        "minimum_positive_order_quantity": minimum, "raw_order_need": raw,
                        "rounded_order_quantity": rounded}
            if name_required:
                expected["product_name"] = name["product_name"]
            if any(item["key"] == _mapping(key) for item in found_exceptions):
                continue
            expected_orders.append({field: _wire(value) for field, value in expected.items()})
            check("key_output_coverage", len(supplied_orders) == 1 and not supplied_exceptions, "one reconciled order", {"orders": len(supplied_orders), "exceptions": len(supplied_exceptions)}, key)
            if len(supplied_orders) == 1:
                actual = supplied_orders[0]
                for field, value in expected.items():
                    if field == "key":
                        continue
                    candidate = actual.get(field)
                    okay = candidate == value
                    if isinstance(value, (Decimal, int)):
                        try:
                            okay = _number(candidate) == value
                        except (ValueError, TypeError):
                            okay = False
                    check(field, okay, value, candidate, key)
                if actual.get("approved_order_quantity") is not None:
                    try:
                        approved_okay = _number(actual["approved_order_quantity"], integer=True) == rounded
                    except (ValueError, TypeError):
                        approved_okay = False
                    check("approved_order_quantity", approved_okay, rounded, actual["approved_order_quantity"], key)
        except (ValueError, TypeError, OverflowError, InvalidOperation) as error:
            problem(key, str(error))

    exception_reasons = defaultdict(list)
    for item in found_exceptions:
        exception_reasons[_key(item)].append(item["reason"])
    for key, reasons in exception_reasons.items():
        present = sources["exception"][key]
        explicit = (len(present) == 1 and isinstance(present[0].get("reason"), str)
                    and bool(present[0]["reason"].strip()) and _has_evidence(present[0]))
        withheld = explicit and not sources["order"][key]
        check("source_reconciliation", withheld, "valid sources or evidenced, explicitly withheld per-key exception", {"independently_discovered_reasons": reasons, "exception_evidenced_and_withheld": withheld}, key)
        check("unresolved_exception_reported", withheld, "evidenced explicit per-key exception and no recommendation", {"exceptions": present, "orders": len(sources["order"][key])}, key)
    return {"checks": checks, "exceptions": found_exceptions, "expected_orders": expected_orders}
