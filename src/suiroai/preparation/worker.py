"""Deterministic preparation kernels for the existing approved Data task.

The controller runs partition_sales in the preparation stage before releasing
development bytes to a model. prepare_development never receives December rows.
Neither function starts a host or grants execution authority. Both require the
trusted caller's exact-request permit, including in explicitly mocked tests.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
import re
import statistics
import unicodedata

from suiroai.contracts import record_ref, validate_record

CUTOFF = "2025-11-30"
START = "2022-01-01"
END = "2025-12-31"
KEYS = ("Product_ID", "Store_ID")
SALES = (*KEYS, "Transaction_ID", "Order_ID", "Order_Date", "Quantity",
         "Order_Status", "Return_Flag", "Product_Name", "Store_Name")
SOURCE_ROLES = {"sales", "dictionary", "inventory", "receipts", "policy"}


class PreparationError(ValueError):
    """Rejected preparation, with measured diagnostics (never a success result)."""

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cosmetic(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def integer(value, *, minimum=None):
    if not re.fullmatch(r"-?\d+", value):
        raise PreparationError("quantity/policy must be an integer", details={"value": value})
    n = int(value)
    if minimum is not None and n < minimum:
        raise PreparationError("quantity/policy outside permitted range", details={"value": value})
    return n


def calendar(value):
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except (ValueError, TypeError):
        raise PreparationError("invalid source calendar date", details={"value": value}) from None
    return value


def table(data, required):
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
        columns = reader.fieldnames
        if not columns or len(set(columns)) != len(columns) or not set(required) <= set(columns):
            raise PreparationError("missing/duplicate CSV columns")
        rows = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise PreparationError("malformed CSV row width")
        return columns, rows
    except (UnicodeError, csv.Error) as exc:
        raise PreparationError("invalid CSV") from exc


def csv_bytes(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def guard(execution, request, parent_permits):
    """A DSC-10 injected permit is authority; record contents alone are not."""
    for value, kind in ((execution, "execution_contract"), (request, "stage_request")):
        errors = validate_record(value)
        if errors or value.get("kind") != kind:
            raise PreparationError("invalid " + kind, details={"errors": errors})
    if (request["stage"] != "preparation" or request["execution_contract_ref"] != record_ref(execution)
            or request["binding"] != execution["binding"] or request["run_id"] != execution["run_id"]
            or request["provenance"] != execution["provenance"]):
        raise PreparationError("preparation request binding mismatch")
    if not {"clean", "join", "aggregate", "eda", "materialize_features"} <= set(execution["allowed_actions"]):
        raise PreparationError("preparation actions not allowed")
    if (request["parent_authorization"]["checkpoint"] != "preparation"
            or request["parent_authorization"]["decision"] != "proceed"):
        raise PreparationError("preparation not authorized")
    if not callable(parent_permits) or parent_permits(request, execution) is not True:
        raise PreparationError("trusted parent did not permit exact preparation request")


def measured(data, ref):
    if sha(data) != ref["sha256"]:
        raise PreparationError("source hash mismatch", details={"source": ref})


def partition_sales(data, source_ref, *, execution, request, parent_permits):
    """Trusted non-model prelude; preserve every raw record and exact identity.

    Returns separate bytes and controller-only reconciliation. Never release
    this whole return value to a development/LLM context. Raw inputs are read
    only; no filesystem writes occur here. Row numbers are CSV records, not
    physical line numbers (quoted newlines can span physical lines).
    """
    guard(execution, request, parent_permits)
    if source_ref not in execution["source_refs"] or source_ref not in request["released_input_refs"]:
        raise PreparationError("raw sales reference is not approved/released")
    measured(data, source_ref)
    columns, rows = table(data, SALES)
    if "_source_record" in columns or "_duplicate_of" in columns:
        raise PreparationError("source uses reserved lineage columns")
    first, development, reserved, lineage = {}, [], [], []
    counts = Counter({name: 0 for name in ("development_raw", "development_distinct", "development_duplicate_excess",
                                           "reserved_raw", "reserved_distinct", "reserved_duplicate_excess")})
    counts["raw_records"] = len(rows)
    for index, row in enumerate(rows, 1):
        when = calendar(row["Order_Date"])
        if not START <= when <= END:
            raise PreparationError("transaction outside approved temporal scope")
        identity = tuple(row[c] for c in columns)  # BEFORE cosmetic normalization
        duplicate_of = first.get(identity)
        if duplicate_of is None:
            first[identity] = index
        destination = "development" if when <= CUTOFF else "reserved"
        counts[destination + "_raw"] += 1
        counts[destination + ("_distinct" if duplicate_of is None else "_duplicate_excess")] += 1
        row_hash = sha(encoded([row[c] for c in columns]))
        lineage.append({"source_record": index, "record_sha256": row_hash,
                        "duplicate_of": duplicate_of, "partition": destination})
        # Keep duplicates in the partitions: each side independently reconciles
        # its own exact duplicate counts before analytical aggregation.
        item = dict(row, _source_record=str(index), _duplicate_of=str(duplicate_of or ""))
        (development if destination == "development" else reserved).append(item)
    counts["distinct_records"] = len(first)
    counts["exact_duplicate_excess"] = len(rows) - len(first)
    dev = csv_bytes(columns + ["_source_record", "_duplicate_of"], development)
    unseen = csv_bytes(columns + ["_source_record", "_duplicate_of"], reserved)
    audit = {"raw_sha256": sha(data), "counts": dict(counts),
             "development_sha256": sha(dev), "reserved_sha256": sha(unseen), "row_lineage": lineage}
    return {"development_csv": dev, "reserved_csv": unseen, "controller_audit": audit,
            "reserved_receipt": {"raw_ref": source_ref, "reserved_sha256": sha(unseen),
                "controller_audit_sha256": sha(encoded(audit)),
                "permitted_start": "2025-12-01", "permitted_end": END},
            # This receipt contains no holdout values, distributions or counts.
            "development_receipt": {"raw_ref": source_ref, "development_sha256": sha(dev),
                "development_raw_records": len(development)}}


def key(row):
    result = tuple(row[c].strip() for c in KEYS)
    if any(not v for v in result):
        raise PreparationError("empty product/store key")
    return result


def keyed(rows, name):
    result = {}
    for index, row in enumerate(rows, 1):
        k = key(row)
        if k in result:
            raise PreparationError(name + " duplicates product/store key; join would multiply rows",
                                   details={"key": k, "source_records": [result[k][0], index]})
        result[k] = (index, row)
    return result


def align_operations(inventory, receipts, policy, sales_keys, ledger_policy):
    """Align stock/policy once per key; aggregate receipt ledger before joining.

    Keep due-dated lines for later replenishment timing. No operational fields
    are copied to historical features, and On_Order_Qty is reconciliation only.
    """
    stock = keyed(inventory, "inventory")
    rules = keyed(policy, "policy")
    if set(stock) != sales_keys or set(rules) != sales_keys:
        raise PreparationError("operational key coverage differs from development population", details={
            "sales_keys": len(sales_keys), "inventory_missing": sorted(sales_keys - set(stock)),
            "inventory_extra": sorted(set(stock) - sales_keys),
            "policy_missing": sorted(sales_keys - set(rules)), "policy_extra": sorted(set(rules) - sales_keys)})
    lines, po_ids = defaultdict(list), set()
    for index, r in enumerate(receipts, 1):
        k = key(r)
        if k not in sales_keys or not r["PO_Line_ID"] or r["PO_Line_ID"] in po_ids:
            raise PreparationError("receipt key/line identity invalid")
        po_ids.add(r["PO_Line_ID"])
        if not calendar(r["Order_Date"]) <= CUTOFF < calendar(r["Expected_Arrival_Date"]):
            raise PreparationError("receipt is not an open order known as of review")
        lines[k].append(dict(r, Incoming_Qty=integer(r["Incoming_Qty"], minimum=1), source_record=index))
    receipt_key_count = len(lines)
    aligned, row_lineage = [], []
    for k in sorted(sales_keys):
        si, s = stock[k]
        pi, p = rules[k]
        if calendar(s["Snapshot_Date"]) != CUTOFF or calendar(p["Effective_Date"]) != CUTOFF:
            raise PreparationError("operational snapshot/policy as-of mismatch")
        if any(r["Quantity_Unit"] != "product_unit" or r["Provenance"] != "synthetic"
               for r in [s, p] + lines[k]):
            raise PreparationError("unsupported operational units/provenance")
        values = {n: integer(p[n], minimum=0 if n == "Safety_Stock_Qty" else 1) for n in (
            "Supplier_Lead_Time_Days", "Review_Period_Days", "Order_Multiple_Qty", "Minimum_Order_Qty", "Safety_Stock_Qty")}
        if values["Minimum_Order_Qty"] % values["Order_Multiple_Qty"]:
            raise PreparationError("minimum order is not a multiple")
        total = sum(r["Incoming_Qty"] for r in lines[k])
        summary = integer(s["On_Order_Qty"], minimum=0)
        on_hand = integer(s["Usable_On_Hand_Qty"], minimum=0)
        complete = (ledger_policy == "complete_synthetic_ledger_absence_is_zero"
                    and cosmetic(s["Open_Order_Ledger_Complete"]) == "true")
        if not complete:
            raise PreparationError("complete receipt ledger is not established; absence is unknown")
        if summary != total:
            raise PreparationError("On_Order_Qty differs from receipt sum", details={"key": k, "summary": summary, "ledger": total})
        for r in lines[k]:
            elapsed = (date.fromisoformat(r["Expected_Arrival_Date"]) - date.fromisoformat(r["Order_Date"])).days
            if elapsed != values["Supplier_Lead_Time_Days"]:
                raise PreparationError("receipt and supplier lead time disagree")
        aligned.append(dict(zip(KEYS, k), Usable_On_Hand_Qty=on_hand, **values,
                            inbound_lines=lines[k], reconciled_on_order_qty=total,
                            Quantity_Unit="product_unit", as_of_date=CUTOFF, provenance="synthetic"))
        row_lineage.append({"key": list(k), "inventory_record": si, "policy_record": pi,
                            "receipt_records": [r["source_record"] for r in lines[k]]})
    return aligned, row_lineage, {"keys": len(sales_keys), "inventory_rows": len(inventory),
        "policy_rows": len(policy), "receipt_lines": len(receipts), "receipt_keys": receipt_key_count,
        "keys_explicitly_without_open_orders": len(sales_keys) - receipt_key_count,
        "aligned_rows": len(aligned), "unmatched_keys": 0, "row_multiplier": 1}


def target_policy(evidence_refs):
    return {"status": "defined", "policy_id": "dsc27-recorded-completed-gross-v1",
        "quantity_unit": "product_unit", "aggregation_grain": "product_store_day",
        "target_measure": "Sum positive Quantity on completed transaction lines on observed record days; recorded gross fulfilled units, not latent demand or complete daily sales",
        "included_order_statuses": ["completed"],
        "returns_treatment": "Retain positive return-flagged completed lines as gross fulfilled units; exclude returned-status lines from the completed-only target. No return-time or returned-unit quantity is established. Report both sensitivities separately.",
        "nonpositive_quantity_treatment": "Quarantine nonpositive quantities; no revenue-based quantity inference",
        "duplicate_treatment": "Remove only exact full-source-record duplicate excess, before normalization; preserve shared Order_ID lines",
        "missing_date_treatment": "explicit_observation_mask", "extract_completeness": "unverified",
        "completeness_evidence_refs": [], "policy_evidence_refs": evidence_refs, "zero_assumption_ref": None}


def prepare_development(sources, *, execution, request, development_receipt,
                        parent_permits):
    """Prepare only explicitly released development bytes; no file discovery.

    sources maps role -> {data: bytes, ref: shared artifact reference}. Receipt
    is supplied by the trusted prelude, never generated by a model. The result
    is an internal value for build_result, not a parent checkpoint decision.
    """
    guard(execution, request, parent_permits)
    if set(sources) != SOURCE_ROLES:
        raise PreparationError("exactly sales/dictionary/inventory/receipts/policy are required")
    refs = {role: item["ref"] for role, item in sources.items()}
    for role, item in sources.items():
        if item["ref"] not in request["released_input_refs"]:
            raise PreparationError("source not released: " + role)
        if role != "sales" and item["ref"] not in execution["source_refs"]:
            raise PreparationError("source not approved: " + role)
        if role in {"inventory", "receipts", "policy"} and item["ref"] not in execution["synthetic_operational_source_refs"]:
            raise PreparationError("operational source is not bound to approved synthetic facts: " + role)
        measured(item["data"], item["ref"])
    if (development_receipt["raw_ref"] not in execution["source_refs"]
            or development_receipt["development_sha256"] != refs["sales"]["sha256"]):
        raise PreparationError("development partition receipt mismatch")
    if development_receipt["raw_ref"] in request["released_input_refs"]:
        raise PreparationError("unrestricted raw source must not be released to development worker")
    columns, raw_rows = table(sources["sales"]["data"], SALES + ("_source_record", "_duplicate_of"))
    _, dictionary = table(sources["dictionary"]["data"], ("Column_Name", "Business_Meaning", "Description"))
    definitions = {r["Column_Name"]: r for r in dictionary}
    if len(definitions) != len(dictionary) or not set(columns) - {"_source_record", "_duplicate_of"} <= set(definitions):
        raise PreparationError("dictionary coverage/uniqueness failed")
    quantity_definition = definitions["Quantity"]
    if "units" not in cosmetic(quantity_definition["Description"]):
        raise PreparationError("dictionary does not establish Quantity units")
    _, inventory = table(sources["inventory"]["data"], (*KEYS, "Snapshot_Date", "Usable_On_Hand_Qty", "On_Order_Qty", "Open_Order_Ledger_Complete", "Quantity_Unit", "Provenance"))
    _, receipts = table(sources["receipts"]["data"], (*KEYS, "PO_Line_ID", "Order_Date", "Expected_Arrival_Date", "Incoming_Qty", "Quantity_Unit", "Provenance"))
    _, policies = table(sources["policy"]["data"], (*KEYS, "Effective_Date", "Supplier_Lead_Time_Days", "Review_Period_Days", "Order_Multiple_Qty", "Minimum_Order_Qty", "Safety_Stock_Qty", "Quantity_Unit", "Provenance"))
    unique, seen, ids, lineage = [], {}, {}, []
    actual_columns = [c for c in columns if c not in ("_source_record", "_duplicate_of")]
    record_numbers = set()
    for row in raw_rows:
        when = calendar(row["Order_Date"])
        if not START <= when <= CUTOFF:
            raise PreparationError("future/out-of-scope row in development release")
        n = integer(row["_source_record"], minimum=1)
        if n in record_numbers:
            raise PreparationError("duplicate source-record identity")
        record_numbers.add(n)
        ident = tuple(row[c] for c in actual_columns)
        canonical = seen.get(ident)
        declared_duplicate = integer(row["_duplicate_of"], minimum=1) if row["_duplicate_of"] else None
        if declared_duplicate != canonical:
            raise PreparationError("duplicate lineage differs from actual full-record equality")
        record_hash = sha(encoded([row[c] for c in actual_columns]))
        lineage.append({"source_record": n, "record_sha256": record_hash, "duplicate_of": canonical})
        if canonical is not None:
            continue
        seen[ident] = n
        tid = row["Transaction_ID"].strip()
        if not tid or tid in ids:
            raise PreparationError("nonidentical shared Transaction_ID is wrong transaction grain")
        ids[tid] = n
        unique.append(row)
    if len(raw_rows) != development_receipt["development_raw_records"]:
        raise PreparationError("partition row count mismatch")
    if not unique:
        raise PreparationError("no development transactions")
    status_counts, return_counts = Counter(), Counter()
    days, quarantine = {}, []
    mapping_fields = [c for c in ("Product_Name", "Product_Category", "Product_Subcategory",
                                 "Store_Name", "Country", "Region", "City") if c in actual_columns]
    mappings = {c: defaultdict(set) for c in mapping_fields}
    missing_mapping_values = Counter()
    sensitivity = Counter()
    allowed_status = {"completed", "cancelled", "canceled", "processing", "shipped", "returned"}
    for row in unique:
        k = key(row)
        n = int(row["_source_record"])
        status = cosmetic(row["Order_Status"])
        if status == "canceled":
            status = "cancelled"
        if status not in allowed_status:
            raise PreparationError("unknown order status", details={"source_record": n, "status": status})
        returned = cosmetic(row["Return_Flag"])
        if returned not in {"yes", "no"}:
            raise PreparationError("unknown return flag", details={"source_record": n})
        quantity = integer(row["Quantity"])
        status_counts[status] += 1
        return_counts[returned] += 1
        for field in mapping_fields:
            identifier = k[0] if field.startswith("Product_") else k[1]
            values = mappings[field][identifier]
            value = cosmetic(row[field])
            if value:
                values.add(value)
            else:
                missing_mapping_values[field] += 1
        dk = (*k, row["Order_Date"])
        day = days.setdefault(dk, dict(zip((*KEYS, "Order_Date"), dk),
            target_quantity=0, observed_record_day=True, complete_daily_sales=False,
            source_records=[], target_source_records=[], excluded_source_records=[]))
        day["source_records"].append(n)
        if quantity <= 0:
            quarantine.append({"source_record": n, "quantity": quantity, "status": status,
                               "returned": returned, "reason": "nonpositive_quantity"})
        include = quantity > 0 and status == "completed"
        day["target_source_records" if include else "excluded_source_records"].append(n)
        if include:
            day["target_quantity"] += quantity
        if quantity > 0:
            sensitivity["positive_units_all_statuses"] += quantity
            if status != "cancelled":
                sensitivity["noncancelled_units"] += quantity
            if status in {"completed", "shipped"}:
                sensitivity["completed_plus_shipped_units"] += quantity
            if status in {"completed", "shipped", "returned"}:
                sensitivity["completed_shipped_returned_units"] += quantity
            if status == "completed":
                sensitivity["completed_gross_units"] += quantity
                if returned == "no":
                    sensitivity["completed_excluding_flagged_returns_units"] += quantity
    sales_keys = {key(r) for r in unique}
    aligned, op_lineage, join_audit = align_operations(inventory, receipts, policies, sales_keys, execution["inbound_ledger_policy"])
    prepared = [days[k] for k in sorted(days)]
    all_dates = {r["Order_Date"] for r in prepared}
    span = (date.fromisoformat(CUTOFF) - date.fromisoformat(START)).days + 1
    coverage = []
    for k in sorted(sales_keys):
        dates = sorted(r["Order_Date"] for r in prepared if key(r) == k)
        coverage.append(dict(zip(KEYS, k), observed_days=len(dates), possible_days=span,
            absent_days=span-len(dates), first_observed=dates[0], last_observed=dates[-1],
            zero_assumption_applied=False))
    mapping_output = {field: {identifier: (next(iter(names)) if len(names) == 1 else None)
                             for identifier, names in values.items()} for field, values in mappings.items()}
    ambiguous = {field: {identifier: sorted(names) for identifier, names in values.items() if len(names) != 1}
                 for field, values in mappings.items()}
    policy = target_policy([development_receipt["raw_ref"], refs["dictionary"]])
    approved_policy = execution["target_policy"]
    if approved_policy["status"] != "pending" and policy != approved_policy:
        raise PreparationError("approved target policy differs; cannot silently change approved task")
    positive_quantities = sorted(integer(r["Quantity"]) for r in unique if integer(r["Quantity"]) > 0)
    audit = {"raw_source_ref": development_receipt["raw_ref"],
        "raw_development_records": len(raw_rows), "distinct_development_records": len(unique),
        "exact_duplicate_excess": len(raw_rows)-len(unique), "daily_records": len(prepared),
        "shared_order_ids": sum(v > 1 for v in Counter(r["Order_ID"] for r in unique).values()),
        "product_count": len({k[0] for k in sales_keys}), "store_count": len({k[1] for k in sales_keys}),
        "product_store_count": len(sales_keys), "nonpositive_quantity_records": len(quarantine),
        "status_counts": dict(status_counts), "return_flag_counts": dict(return_counts),
        "target_retained_lines": sum(len(r["target_source_records"]) for r in prepared),
        "target_excluded_lines": sum(len(r["excluded_source_records"]) for r in prepared),
        "development_target_quantity": sum(r["target_quantity"] for r in prepared),
        "global_observed_dates": len(all_dates), "possible_calendar_dates": span,
        "median_series_observed_dates": statistics.median(r["observed_days"] for r in coverage),
        "sensitivity_units": dict(sensitivity), "ambiguous_mappings": ambiguous,
        "missing_mapping_values": dict(missing_mapping_values),
        "positive_quantity_summary": {"count": len(positive_quantities),
            "minimum": min(positive_quantities, default=None), "maximum": max(positive_quantities, default=None),
            "median": statistics.median(positive_quantities) if positive_quantities else None,
            "treatment": "Retain positive values without unsupported winsorization; boundedness/fitness belongs to measured modeling checks"},
        "joins": join_audit, "latest_event_date": max(all_dates), "earliest_event_date": min(all_dates),
        "quantity_source": "Quantity only", "source_refs": refs,
        "missing_date_sensitivity": {"primary": "unknown, no inserted zero rows",
            "observed_day_mean_units": sum(r["target_quantity"] for r in prepared)/len(prepared),
            "hypothetical_zero_fill_mean_units": sum(r["target_quantity"] for r in prepared)/(len(sales_keys)*span),
            "zero_fill_is_unsupported_sensitivity_only": True}}
    return {"daily": prepared, "operations": aligned, "row_lineage": lineage,
        "operational_lineage": op_lineage, "quarantine": quarantine, "mappings": mapping_output,
        "coverage": coverage, "audit": audit, "target_policy": policy,
        "limitations": [
            "Extract completeness and transaction/status/return availability times are unverified; observed-day recorded units are not latent demand or a complete daily demand series.",
            "No absent product/store dates are zero-filled; conditional pooled observed-day features are a bounded fallback, not evidence of restocking fitness. Score horizons only with established observation coverage.",
            "Completed gross units retain positive flagged returns; returned-status rows, processing/shipped and cancellations are excluded. Returns have no known event time or returned quantity; status alternatives are sensitivity only.",
            "Only calendar/identifier initial predictors are enabled. Realized status/returns, approximate Inventory_Level and customer Delivery_Days never enter predictors. Outcome lags require historical availability evidence.",
            "Stock and supplier policies are synthetic November 30 inputs, unavailable to earlier rolling folds. Cost/profit/stockout improvement is not measured."]}
