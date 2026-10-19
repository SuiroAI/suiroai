"""Serialize measured preparation outputs using the DSC-24 snapshot unchanged.

Bind measured preparation payloads and source references into a validated
result record, preserving the exact stage request and parent review.
"""
from copy import deepcopy

from suiroai.contracts import VERSION, record_ref, validate_record

from .features import build_features, FEATURE_NAMES
from .worker import CUTOFF, START, END, KEYS, PreparationError, encoded, sha


def build_result(prepared, *, execution, request, reserved_ref, reserved_receipt,
                 partition_audit_ref, parent_decision, information_availability_evidence=None):
    """Build a private adapter candidate, not an authenticated checkpoint.

    Returned artifacts are bytes; the caller writes them inside the existing
    adapter output root and includes them in artifact-manifest.json. The actual
    reserved file is held by the controller and supplied as an external ref.
    parent_decision is a private proposal; DSC-26/10 must authenticate its exact
    bytes through candidate review before accepting anything. This function
    neither invents a parent decision nor returns a customer-facing response.
    """
    if (request["execution_contract_ref"] != record_ref(execution)
            or request["binding"] != execution["binding"] or request["run_id"] != execution["run_id"]
            or request["stage"] != "preparation"):
        raise PreparationError("result request binding mismatch")
    if (parent_decision["checkpoint"] != "preparation"
            or parent_decision["decision"] != "proceed"):
        raise PreparationError("candidate requires a preparation proceed proposal for parent review")
    if reserved_ref in request["released_input_refs"]:
        raise PreparationError("reserved rows were released to development worker")
    if (reserved_receipt["raw_ref"] != prepared["audit"]["raw_source_ref"]
            or reserved_receipt["reserved_sha256"] != reserved_ref["sha256"]
            or reserved_receipt["controller_audit_sha256"] != partition_audit_ref["sha256"]
            or reserved_receipt["permitted_start"] != "2025-12-01"
            or reserved_receipt["permitted_end"] != END
            or partition_audit_ref in request["released_input_refs"]):
        raise PreparationError("controller-held reserved partition identity/scope mismatch")
    if (execution["provenance"] == "mock") != (reserved_ref["provenance"] == "mock"):
        raise PreparationError("reserved artifact provenance mismatch")
    _verify(prepared)
    provenance = "mock" if execution["provenance"] == "mock" else "derived"
    information_date = CUTOFF  # hypothetical MOCK date, not a source fact
    information_ref = None
    if provenance != "mock":
        # No event-cutoff substitution for unknown information time. A genuine
        # upstream shared evidence_record may establish a bounded extract date;
        # the parent authenticates its verifier and exact bytes at review.
        e = information_availability_evidence
        if (not isinstance(e, dict) or validate_record(e) or e.get("kind") != "evidence_record"
                or e["provenance"] == "mock" or e["evidence_mode"] != "real"
                or e["verifier_decision"] != "accepted" or e["check"]["status"] != "pass"
                or e["requirement_id"] != "DSC-27-information-availability"
                or e["binding"] != execution["binding"] or e["run_id"] != execution["run_id"]
                or prepared["audit"]["source_refs"]["sales"] not in e["checked_artifacts"]
                or not e["check"]["evidence_refs"]):
            raise PreparationError("real preparation handoff blocked: retrospective information availability is unverified under the pinned contract")
        from .worker import calendar
        information_date = calendar(e["check"]["actual"])
        if not prepared["audit"]["latest_event_date"] <= information_date <= CUTOFF:
            raise PreparationError("real development information availability exceeds permitted boundary")
        information_ref = record_ref(e)
    prefix = request["artifact_id"] + "-"
    artifacts = []

    def artifact(name, value):
        data = encoded(value)
        ref = {"artifact_id": prefix+name, "version": 1, "provenance": provenance, "sha256": sha(data)}
        artifacts.append({"ref": ref, "path": name+".json", "encoding": "bytes", "data": data})
        return ref

    namespace = execution["binding"]["task_id"]
    daily_ref = artifact("prepared-development", {"format": "dsc27-daily-v1", "source_namespace": namespace,
        "rows": prepared["daily"], "target_policy": prepared["target_policy"],
        "quantity_unit": "product_unit", "coverage": prepared["coverage"], "mappings": prepared["mappings"],
        "label_availability": "Retrospective extract; status/return latency unverified. No origin-safe lag claim."})
    features = build_features(prepared["daily"], source_namespace=namespace,
                              operational_keys=[tuple(r[k] for k in KEYS) for r in prepared["operations"]])
    feature_ref = artifact("initial-features", features)
    operation_ref = artifact("as-of-operations", {"format": "dsc27-operations-v1",
        "source_namespace": namespace, "rows": prepared["operations"],
        "on_order_usage": "reconciliation only; downstream subtract due-dated incoming lines once",
        "as_of_date": CUTOFF, "historical_features_permitted": False})
    lineage_ref = artifact("development-row-lineage", {"raw_ref": prepared["audit"]["raw_source_ref"],
        "rows": prepared["row_lineage"], "quarantine": prepared["quarantine"],
        "daily_rows": [{k: r[k] for k in (*KEYS, "Order_Date", "source_records", "target_source_records", "excluded_source_records")}
                       for r in prepared["daily"]], "operational_rows": prepared["operational_lineage"]})
    audit_ref = artifact("development-checks", {"format": "dsc27-checks-v1", "actual": prepared["audit"],
        "limitations": prepared["limitations"], "evidence_mode": "mock" if provenance == "mock" else "real",
        "scope": "Development only; no reserved outcomes or production acceptance inferred"})
    checks = []

    def check(name, expected, actual, status="pass"):
        checks.append({"check_id": name, "requirement_id": "DSC-27", "status": status,
            "expected": expected, "actual": str(actual), "evidence_refs": [audit_ref],
            "verifier": "DSC-27 deterministic preparation checks; independent acceptance pending"})

    audit = prepared["audit"]
    check("development-duplicate-reconciliation", "raw = distinct + exact duplicate excess; no Order_ID dedup",
          f"{audit['raw_development_records']} = {audit['distinct_development_records']} + {audit['exact_duplicate_excess']}; shared Order_ID groups {audit['shared_order_ids']}")
    check("retained-target-lines", "distinct = retained + excluded",
          f"{audit['distinct_development_records']} = {audit['target_retained_lines']} + {audit['target_excluded_lines']}; quarantined {audit['nonpositive_quantity_records']}")
    check("development-boundary", "all event dates <= 2025-11-30; no reserved values in features/context",
          audit["latest_event_date"])
    check("daily-grain", "one row per observed product/store/day; no inserted missing dates", audit["daily_records"])
    check("operational-key-cardinality", "unique stock/policy keys; receipts aggregate before one-to-one alignment", audit["joins"])
    check("prediction-time-features", "calendar + fold-only identifier encoding; no outcome or operational predictors",
          features["predictor_columns"])
    check("extract-completeness", "evidence required for full daily demand horizons",
          "Unavailable: explicit per-series observation mask, no zero-fill; retrospective label timing unverified", "unavailable")
    feature_definitions = [{"feature_id": name, "name": name,
        "expression": (name + " from known target calendar date" if name in FEATURE_NAMES else
                       name + " known identity, encoded from frozen training-fold vocabulary; unknown=-1"),
        "source_refs": [daily_ref], "event_time_basis": "source calendar date",
        "availability_time_basis": "calendar known in advance; known product/store identities only",
        "minimum_lag_calendar_days": 0, "timing_rule": "No realized values; historical row origin precedes target_date",
        "uses_only_information_available_at_origin": True, "fit_scope": "training_fold_only",
        "rationale": "Initial bounded calendar/pooled identity features; no outcome lag without measured availability."}
        for name in (*KEYS, *FEATURE_NAMES)]
    earliest, latest = audit["earliest_event_date"], audit["latest_event_date"]

    def availability(ref, use, first, last, info, event=None, future=False):
        return {"artifact_ref": ref, "permitted_use": use, "earliest_event_date": first,
            "latest_event_date": last, "latest_information_available_date": info,
            "event_time_column": event, "availability_time_column": None, "contains_post_cutoff_rows": future}

    source_refs = [audit["raw_source_ref"], *audit["source_refs"].values()]
    input_refs = source_refs + [record_ref(execution)] + ([information_ref] if information_ref else [])
    lineage = [{"output_ref": ref, "input_refs": input_refs, "transformation_id": "dsc27-initial-preparation-v1",
        "description": "Development-only exact dedup, Quantity target, observation mask, deterministic initial features or as-of key alignment; source records in row-lineage artifact",
        "row_lineage_ref": lineage_ref, "preserved_raw_hashes": [r["sha256"] for r in source_refs]}
        for ref in (daily_ref, feature_ref, operation_ref)]
    lineage.append({"output_ref": reserved_ref, "input_refs": [audit["raw_source_ref"]],
        "transformation_id": "dsc27-approved-preparation-partition-v1",
        "description": "Controller-only deterministic temporal partition; exact raw row identities and duplicate reconciliation retained outside development context",
        "row_lineage_ref": partition_audit_ref, "preserved_raw_hashes": [audit["raw_source_ref"]["sha256"]]})
    findings = [{"finding_id": "preparation-reconciliation", "classification": "verified_finding",
        "statement": f"Development retained {audit['target_retained_lines']} completed positive lines; excluded {audit['target_excluded_lines']}, including {audit['nonpositive_quantity_records']} nonpositive rows. Status/return and unsupported zero-fill sensitivities retained internally.",
        "evidence_refs": [audit_ref], "audience": "final_report"}]
    findings.extend([
        {"finding_id": "preparation-sparse-coverage", "classification": "verified_finding",
         "statement": f"Across {audit['product_store_count']} product/store pairs, median observed record dates were {audit['median_series_observed_dates']} of {audit['possible_calendar_dates']} development dates. Missing dates remain unknown; pooled observed-day development is conditional on recorded activity.",
         "evidence_refs": [audit_ref], "audience": "final_report"},
        {"finding_id": "preparation-operational-alignment", "classification": "verified_finding",
         "statement": f"Synthetic November 30 operations align to {audit['joins']['keys']} keys with {audit['joins']['receipt_lines']} incoming lines and {audit['joins']['keys_explicitly_without_open_orders']} explicitly zero-open-order keys. Receipt summaries reconcile without row multiplication.",
         "evidence_refs": [audit_ref], "audience": "final_report"}])
    findings.extend({"finding_id": "preparation-limitation-"+str(i), "classification": "material_limitation",
        "statement": statement, "evidence_refs": [audit_ref], "audience": "final_report"}
        for i, statement in enumerate(prepared["limitations"], 1))
    # Cardinality declarations refer to actual aggregate alignment. The detailed
    # evidence retains raw receipt line counts, including keys with zero lines.
    joins = [{"left_ref": audit["source_refs"]["inventory"], "right_ref": audit["source_refs"]["policy"],
        "join_keys": list(KEYS), "expected_cardinality": "one_to_one",
        "left_rows": audit["joins"]["inventory_rows"], "right_rows": audit["joins"]["policy_rows"],
        "result_rows": len(prepared["operations"]), "unmatched_left_keys": 0, "unmatched_right_keys": 0,
        "check_ref": audit_ref}]
    result = {"kind": "preparation_result", "schema_version": VERSION,
        "artifact_id": prefix+"result", "artifact_version": 1, "provenance": provenance,
        "binding": deepcopy(execution["binding"]), "run_id": execution["run_id"],
        "execution_contract_ref": record_ref(execution), "prepared_development_data_ref": daily_ref,
        "reserved_unseen_data_ref": deepcopy(reserved_ref), "initial_feature_set_ref": feature_ref,
        "initial_feature_definitions": feature_definitions, "target_policy": prepared["target_policy"],
        "lineage": lineage, "join_checks": joins, "quality_checks": checks,
        "availability": [availability(r, "development", earliest, latest, information_date, "Order_Date" if r == daily_ref else None)
                         for r in (daily_ref, feature_ref, audit_ref, lineage_ref)] + [
            availability(operation_ref, "as_of_operations", CUTOFF, CUTOFF, CUTOFF, "as_of_date"),
            availability(reserved_ref, "reserved_unseen_evaluation", "2025-12-01", END, END, "Order_Date", True),
            availability(partition_audit_ref, "reserved_unseen_evaluation", START, END, END, None, True)],
        "development_context_allowlist": [daily_ref, feature_ref, audit_ref], "findings": findings,
        "parent_decision": deepcopy(parent_decision)}
    errors = validate_record(result)
    if errors:
        raise PreparationError("preparation result schema failed", details={"errors": errors})
    artifacts.append({"ref": record_ref(result), "path": "preparation-result.json", "encoding": "record", "data": encoded(result)})
    envelope = {"kind": "stage_result", "schema_version": VERSION,
        "artifact_id": prefix+"stage-result", "artifact_version": 1, "provenance": provenance,
        "binding": deepcopy(execution["binding"]), "run_id": execution["run_id"], "stage": "preparation",
        "outcome": "completed", "output_refs": [record_ref(result), daily_ref, feature_ref, operation_ref],
        "evidence_refs": [audit_ref, lineage_ref], "parent_decision": None, "failure": None,
        "execution_contract_ref": record_ref(execution), "stage_request_ref": record_ref(request),
        "attempt": request["attempt"], "gaps": [], "final_validation_result_ref": None}
    errors = validate_record(envelope)
    if errors:
        raise PreparationError("stage result schema failed", details={"errors": errors})
    return {"record": result, "stage_result": envelope, "artifacts": artifacts,
            "artifact_manifest": [{k: a[k] for k in ("ref", "path", "encoding")} for a in artifacts]}


def _verify(prepared):
    """Reconcile independent output views before emitting any pass declarations."""
    a = prepared["audit"]
    daily = prepared["daily"]
    lineage = prepared["row_lineage"]
    raw_numbers = [r["source_record"] for r in lineage]
    distinct = {r["source_record"] for r in lineage if r["duplicate_of"] is None}
    included = [n for r in daily for n in r["target_source_records"]]
    excluded = [n for r in daily for n in r["excluded_source_records"]]
    all_daily = [n for r in daily for n in r["source_records"]]
    from collections import Counter
    if (len(raw_numbers) != len(set(raw_numbers)) or len(lineage) != a["raw_development_records"]
            or len(distinct) != a["distinct_development_records"]
            or len(lineage)-len(distinct) != a["exact_duplicate_excess"]
            or set(all_daily) != distinct or len(all_daily) != len(distinct)
            or Counter(included+excluded) != Counter(all_daily)
            or len(included) != a["target_retained_lines"] or len(excluded) != a["target_excluded_lines"]
            or len(prepared["quarantine"]) != a["nonpositive_quantity_records"]
            or sum(r["target_quantity"] for r in daily) != a["development_target_quantity"]
            or len(daily) != a["daily_records"]
            or any(set(r["source_records"]) != set(r["target_source_records"]+r["excluded_source_records"]) for r in daily)
            or any(r["complete_daily_sales"] is not False for r in daily)):
        raise PreparationError("prepared output reconciliation failed")
    if (max(r["Order_Date"] for r in daily) != a["latest_event_date"]
            or min(r["Order_Date"] for r in daily) != a["earliest_event_date"]):
        raise PreparationError("prepared temporal audit mismatch")
    # Independently reconcile the aligned output, not only the producer's
    # summary. A dropped operation row must never emit a passing join check.
    from .worker import key, calendar
    operations = prepared["operations"]
    op_keys = [key(r) for r in operations]
    daily_keys = {key(r) for r in daily}
    join = a["joins"]
    op_lineage = prepared["operational_lineage"]
    receipt_lines = [r for op in operations for r in op["inbound_lines"]]
    nonempty_keys = sum(bool(op["inbound_lines"]) for op in operations)
    if (set(op_keys) != daily_keys or len(op_keys) != len(set(op_keys))
            or len(op_keys) != join["keys"] or len(op_keys) != join["aligned_rows"]
            or len(op_keys) != join["inventory_rows"] or len(op_keys) != join["policy_rows"]
            or len(op_keys) != len(op_lineage)
            or {tuple(r["key"]) for r in op_lineage} != daily_keys
            or len(receipt_lines) != join["receipt_lines"] or nonempty_keys != join["receipt_keys"]
            or len(op_keys)-nonempty_keys != join["keys_explicitly_without_open_orders"]
            or join["unmatched_keys"] != 0 or join["row_multiplier"] != 1):
        raise PreparationError("prepared operational reconciliation failed")
    by_key = {tuple(r["key"]): r for r in op_lineage}
    for op in operations:
        lines = op["inbound_lines"]
        if (op["as_of_date"] != CUTOFF or op["provenance"] != "synthetic"
                or op["Quantity_Unit"] != "product_unit"
                or any(type(op[n]) is not int or op[n] < 0 for n in ("Usable_On_Hand_Qty", "reconciled_on_order_qty", "Safety_Stock_Qty"))
                or any(type(op[n]) is not int or op[n] < 1 for n in ("Supplier_Lead_Time_Days", "Review_Period_Days", "Order_Multiple_Qty", "Minimum_Order_Qty"))
                or op["Minimum_Order_Qty"] % op["Order_Multiple_Qty"]
                or [r["source_record"] for r in lines] != by_key[key(op)]["receipt_records"]
                or any(type(r["Incoming_Qty"]) is not int or r["Incoming_Qty"] < 1 for r in lines)
                or sum(r["Incoming_Qty"] for r in lines) != op["reconciled_on_order_qty"]):
            raise PreparationError("prepared receipt/policy reconciliation failed")
        from datetime import date
        for r in lines:
            if (key(r) != key(op) or not calendar(r["Order_Date"]) <= CUTOFF < calendar(r["Expected_Arrival_Date"])
                    or r["Quantity_Unit"] != "product_unit" or r["Provenance"] != "synthetic"
                    or (date.fromisoformat(r["Expected_Arrival_Date"])-date.fromisoformat(r["Order_Date"])).days != op["Supplier_Lead_Time_Days"]):
                raise PreparationError("prepared receipt availability/timing failed")
