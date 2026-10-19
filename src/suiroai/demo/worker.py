"""Measure development-release prerequisites for the DSC-59 demo.

Keep the browser honest about gaps in the existing component contracts. These
checks grant no model execution or analytical checkpoint authority.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from collections import defaultdict
from datetime import date
import hashlib
import json
import uuid

from suiroai.preparation.worker import SALES, calendar, csv_bytes, table

PREPARATION_BLOCKER = (
    "Preparation cannot safely dispatch a model turn: the pinned parent contract "
    "permits original source references only, while development preparation "
    "requires a controller-created partition excluding December 2025. "
    "A reviewed derived-input release bridge is required. Historical information "
    "availability and daily-series completeness also remain unverified."
)


def analytical_blockers():
    """Return explicit remaining requirements, never fabricated retail results."""
    return [PREPARATION_BLOCKER,
        "Numerical checkpoint review and check-only output-verification transport "
        "must be connected before a verified recommendation can be delivered."]


def audit_development_partition(store, submission, proposal):
    """Inspect approved source bytes without issuing an analytical handoff.

    This controller-only audit preserves records, including duplicates, and
    stores December separately. Event dates establish partition membership;
    they never establish historical information availability or missing zeros.
    No output is a typed preparation_result or a released model input.
    """
    sales = [file for file in submission["files"] if file["source_role"] == "transactions"]
    if len(sales) != 1:
        raise ValueError("One measured transaction source is required for the release audit")
    file = sales[0]
    matching = [ref for ref in proposal["source_refs"] if ref["artifact_id"] == file["file_id"]
        and ref["sha256"] == file["sha256"]]
    if len(matching) != 1:
        raise ValueError("Transaction source does not match the approved proposal")
    source_ref = matching[0]
    raw = store.read_bytes(source_ref)
    columns, rows = table(raw, SALES)
    if "_source_record" in columns:
        raise ValueError("Transaction source uses a reserved audit lineage column")
    development, reserved = [], []
    dates = defaultdict(set)
    for index, row in enumerate(rows, 1):
        when = calendar(row["Order_Date"])
        if not "2022-01-01" <= when <= "2025-12-31":
            raise ValueError("Transaction date falls outside the approved historical scope")
        item = dict(row, _source_record=str(index))
        if when <= "2025-11-30":
            development.append(item)
            dates[(row["Product_ID"], row["Store_ID"])].add(when)
        else:
            reserved.append(item)
    if not development:
        raise ValueError("No development transaction records precede the holdout boundary")
    prefix = "demo-release-audit-" + uuid.uuid4().hex
    refs = []
    for suffix, partition in (("development", development), ("reserved", reserved)):
        data = csv_bytes(columns + ["_source_record"], partition)
        refs.append(store.put_bytes(prefix + "-" + suffix, 1, "derived", data))
    span = (date(2025, 11, 30) - date(2022, 1, 1)).days + 1
    observed = sum(len(values) for values in dates.values())
    audit = {"format": "dsc59-controller-release-audit-v1", "source_ref": source_ref,
        "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "development_ref": refs[0], "controller_only_reserved_ref": refs[1],
        "development_source_records": len(development), "development_product_store_pairs": len(dates),
        "development_observed_pair_dates": observed,
        "development_possible_pair_dates": span * len(dates),
        "development_unobserved_pair_dates": span * len(dates) - observed,
        "duplicates_preserved": True, "missing_dates_zero_filled": False,
        "latest_information_available_date": None, "historical_information_availability_verified": False,
        "daily_series_completeness_verified": False, "analytical_model_inputs_released": False,
        "meaning": "Unobserved pair dates have no transaction records in the supplied extract; their sales quantity is unknown.",
        "remaining_contract_requirement": "A new reviewed contract revision must bind partition lineage and permit derived development inputs before analytical dispatch."}
    encoded = (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
    audit_ref = store.put_bytes(prefix + "-audit", 1, "derived", encoded)
    return {"audit_ref": audit_ref, "development_source_records": len(development),
        "development_product_store_pairs": len(dates),
        "development_unobserved_pair_dates": audit["development_unobserved_pair_dates"],
        "analytical_model_inputs_released": False}
