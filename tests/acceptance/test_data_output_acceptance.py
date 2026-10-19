"""DSC-56 fixed-case MOCK seams against DSC-24 0.1.0-draft.3.

These engineering checks exercise real component functions with invented bytes.
They cannot establish DSC-31 demonstration or real-run acceptance. Expected
quantities below are hand calculations, not values returned by the producer.
Only fixture builders are imported from component tests; no TestCase is imported.

Requirement context for these component checks:
Check the selected-case preparation, forecast, quantity, and report seams
against fixed expected outcomes, including stale evidence and affected rechecks.

Linear: https://linear.app/gr3enarr0w/issue/DSC-56
"""
from copy import deepcopy
import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest

from suiroai.contracts import record_ref, validate_record
from suiroai.integration.artifacts import ArtifactError
from suiroai.preparation.features import build_features, horizon_target, validate_feature_rows
from suiroai.preparation.worker import PreparationError, prepare_development
from suiroai.replenishment.calculation import calculate_candidate
from suiroai.replenishment.context import Handoff
from suiroai.reporting import draft_success
from suiroai.verification import OutputVerifier, VerificationError


ROOT = Path(__file__).resolve().parents[2]


def _example_module(name, relative_path):
    """Load by exact path/unique name, avoiding generic test module collisions."""
    spec = importlib.util.spec_from_file_location("dsc56_mock_" + name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARATION = _example_module("preparation", "tests/preparation/mock_data.py")
OUTPUT = _example_module("output", "tests/verification/test_engine.py")


def _mock_candidate(tmp_path, mutate_source=None):
    """Actual DSC-29 producer followed by DSC-30 independent source reading."""
    bundle = OUTPUT.success_fixture()
    bundle["records"] = [r for r in bundle["records"]
                         if r["kind"] not in {"quantity_result", "report_draft", "evidence_record"}]
    # The operational scenario is synthetic even though all artifact/run
    # provenance remains explicitly MOCK. DSC-29 requires this source meaning.
    for artifact_id in ("mock-stock", "mock-receipts", "mock-policy"):
        _csv_change(bundle, artifact_id,
                    lambda rows: [row.update(Provenance="synthetic") for row in rows])
    if mutate_source:
        mutate_source(bundle)
    bundle, store, _ = OUTPUT.load(tmp_path, bundle)
    refs = [a["ref"] for a in bundle["mock_artifacts"]]
    handoff = Handoff(bundle["records"], refs, store.read_bytes,
                      lambda *_: True, allow_mock=True)
    readers = OUTPUT.success_readers(bundle)
    candidate = calculate_candidate(
        handoff, artifact_id="mock-dsc56-produced-candidate",
        scope_ref=readers.scope_ref, scope_reader=readers.scope,
        forecast_reader=readers.forecast, source_namespace=readers.source_namespace,
        name_ref=readers.names_ref, name_reader=readers.names)
    return bundle, store, readers, candidate


def _candidate_check(bundle, store, readers, candidate):
    candidate_ref = store.put_record(candidate)
    verifier = OutputVerifier(
        store, current_records=[record_ref(r) for r in bundle["records"]] + [candidate_ref],
        current_artifacts=[a["ref"] for a in bundle["mock_artifacts"]],
        authenticate=lambda *_: True, allow_mock=True, verifier="DSC-56 fixed MOCK reviewer")
    return verifier.check_candidate(candidate_ref, readers=readers,
                                    evidence_id=f"{candidate['artifact_id']}-independent-v{candidate['artifact_version']}",
                                    verified_at="2026-10-18T13:00:00Z")


def _csv_change(bundle, artifact_id, mutate):
    artifact = next(a for a in bundle["mock_artifacts"] if a["ref"]["artifact_id"] == artifact_id)
    rows = list(csv.DictReader(io.StringIO(artifact["raw_bytes"].decode())))
    mutate(rows)
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    artifact["raw_bytes"] = text.getvalue().encode()


def test_mock_preparation_duplicate_reconciliation_preserves_sparse_series_and_horizon_unknowns():
    """DSC-27: a globally present date gives no per-key zero-sale evidence."""
    rows = [PREPARATION.sale(1, Order_Date="2025-11-01", Quantity="2"),
            PREPARATION.sale(2, Order_Date="2025-11-03", Quantity="5"),
            PREPARATION.sale(3, Order_Date="2025-11-02", Product_ID="MOCK-P2", Quantity="7")]
    # A second key needs its own explicit operational rows, not a sales join fanout.
    def second_key(inventory, receipts, policy):
        for collection in (inventory, receipts, policy):
            extra = deepcopy(collection)
            for row in extra:
                row["Product_ID"] = "MOCK-P2"
                if "PO_Line_ID" in row:
                    row["PO_Line_ID"] += "-P2"
            collection.extend(extra)
    args, partition = PREPARATION.packet(rows + [deepcopy(rows[0])], second_key)
    prepared = prepare_development(**args)
    assert partition["controller_audit"]["counts"]["raw_records"] == 4
    assert prepared["audit"]["exact_duplicate_excess"] == 1
    assert prepared["audit"]["distinct_development_records"] == 3
    assert prepared["audit"]["development_target_quantity"] == 14
    assert len(prepared["daily"]) == 3
    assert len(prepared["operations"]) == 2
    assert all(not row["complete_daily_sales"] for row in prepared["daily"])
    first_key = [r for r in prepared["daily"] if r["Product_ID"] == "MOCK-P1"]
    assert [r["Order_Date"] for r in first_key] == ["2025-11-01", "2025-11-03"]
    assert horizon_target(prepared["daily"], product_id="MOCK-P1", store_id="MOCK-S1",
                          origin="2025-11-01", horizon_days=2) is None
    features = build_features(prepared["daily"], source_namespace="mock-retail")
    assert [(r["Product_ID"], r["target_date"]) for r in features["rows"]] == [("MOCK-P1", "2025-11-03")]


def test_mock_conflicting_transaction_grain_stops_before_feature_consumption():
    args, _ = PREPARATION.packet([PREPARATION.sale(1), PREPARATION.sale(1, Quantity="99")])
    with pytest.raises(PreparationError, match="wrong transaction grain"):
        prepare_development(**args)


def test_mock_december_poison_does_not_change_preparation_or_initial_features():
    outputs = []
    reserved = []
    for future_quantity in ("1", "999999999"):
        args, partition = PREPARATION.packet([
            PREPARATION.sale(1, Order_Date="2024-01-01", Quantity="2"),
            PREPARATION.sale(2, Order_Date="2025-11-30", Quantity="5"),
            PREPARATION.sale(3, Order_Date="2025-12-01", Quantity=future_quantity)])
        prepared = prepare_development(**args)
        outputs.append((partition["development_csv"], prepared["daily"],
                        build_features(prepared["daily"], source_namespace="mock-retail")))
        reserved.append(partition["reserved_csv"])
    assert reserved[0] != reserved[1]
    assert outputs[0] == outputs[1]
    assert all(r["target_date"] <= "2025-11-30" for r in outputs[0][2]["rows"])
    assert all("quantity" not in row for row in outputs[0][2]["origin_rows"])


@pytest.mark.parametrize("field", ["Delivery_Days", "Inventory_Level", "Quantity", "Revenue", "target_quantity"])
def test_mock_prepared_features_reject_customer_fields_and_realized_future_values(field):
    args, _ = PREPARATION.packet([PREPARATION.sale(1), PREPARATION.sale(2, Order_Date="2025-11-03")])
    features = build_features(prepare_development(**args)["daily"], source_namespace="mock-retail")
    features["rows"][0][field] = 999
    with pytest.raises(PreparationError, match="leakage"):
        validate_feature_rows(features["rows"])


def test_mock_produced_candidate_is_independently_recomputed_from_bound_sources(tmp_path):
    bundle, store, readers, candidate = _mock_candidate(tmp_path)
    # Demand 20 + safety 2 - usable 5 - receipt 5 = 12; pack 5 rounds to 15.
    # On_Order_Qty=5 reconciles the ledger; it is never subtracted a second time.
    assert candidate["orders"][0]["raw_order_need"] == 12
    assert candidate["orders"][0]["rounded_order_quantity"] == 15
    assert candidate["orders"][0]["approved_order_quantity"] is None
    checked = _candidate_check(bundle, store, readers, candidate)
    assert checked["evidence_mode"] == "mock"
    assert checked["checked_artifacts"] == [record_ref(candidate)]
    assert checked["verifier_decision"] == "accepted"
    actual = json.loads(checked["check"]["actual"])
    assert any(c["check_id"].startswith("raw_order_need-") and c["expected"] == "12"
               for c in actual["checks"])
    assert any(c["check_id"].startswith("rounded_order_quantity-") and c["expected"] == "15"
               for c in actual["checks"])


@pytest.mark.parametrize("mutation", ["double-count-ledger", "approximate-stock", "customer-lead-time"])
def test_mock_independent_verifier_rejects_plausible_false_producer_arithmetic(tmp_path, mutation):
    bundle, store, readers, candidate = _mock_candidate(tmp_path)
    row = candidate["orders"][0]
    # Keep producer flags/refs intact: the verifier must read operational bytes.
    if mutation == "double-count-ledger":
        # Conceal the second subtraction by understating displayed demand;
        # local arithmetic remains coherent but source reconciliation must fail.
        row.update(forecast_quantity=15, raw_order_need=7, rounded_order_quantity=10)
    elif mutation == "approximate-stock":
        row.update(usable_on_hand_quantity=10, raw_order_need=7, rounded_order_quantity=10)
    else:
        row.update(supplier_lead_calendar_days=2, review_period_calendar_days=12)
    checked = _candidate_check(bundle, store, readers, candidate)
    assert checked["verifier_decision"] == "rejected"
    assert checked["check"]["status"] == "fail"
    actual = json.loads(checked["check"]["actual"])
    assert any(check["status"] == "fail" for check in actual["checks"])


@pytest.mark.parametrize("arrival", ["2025-12-15", "2025-12-08"])
def test_mock_receipt_coverage_and_same_day_ambiguity_are_preserved_across_verifier(tmp_path, arrival):
    def late(bundle):
        _csv_change(bundle, "mock-stock", lambda rows: rows[0].update(Usable_On_Hand_Qty="5", On_Order_Qty="20"))
        _csv_change(bundle, "mock-receipts", lambda rows: rows[0].update(Expected_Arrival_Date=arrival, Incoming_Qty="20"))
    bundle, store, readers, candidate = _mock_candidate(tmp_path, late)
    if arrival == "2025-12-15":
        # Receipt outside Dec 1-14: 20+2-5=17, rounded to 20.
        assert candidate["orders"][0]["eligible_receipt_quantity"] == 0
        assert candidate["orders"][0]["rounded_order_quantity"] == 20
    else:
        # End-of-day arrival cannot support the 20 units demanded that same day.
        assert candidate["orders"] == []
        assert "timing_ambiguity" in candidate["exceptions"][0]["reason"]
    checked = _candidate_check(bundle, store, readers, candidate)
    assert checked["verifier_decision"] == "accepted"


def _produced_report(tmp_path, mutate=None, *, namespace_mock_findings=True):
    bundle = OUTPUT.success_fixture()
    bundle["records"] = [r for r in bundle["records"]
                         if r["kind"] != "report_draft"
                         and r.get("requirement_id") != "mock-terminal-evidence-binding"]
    if namespace_mock_findings:
        # The shared example repeats a source-local 'mock-finding' identifier.
        # Make independent examples explicit about run-wide finding identities.
        for source in bundle["records"]:
            for finding in source.get("findings", []):
                finding["finding_id"] = source["artifact_id"] + "-" + finding["finding_id"]
    bundle, store, _ = OUTPUT.load(tmp_path, bundle)
    refs = [a["ref"] for a in bundle["mock_artifacts"]]
    h = Handoff(bundle["records"], refs, store.read_bytes, lambda *_: True, allow_mock=True)
    report = draft_success(h, artifact_id="mock-dsc56-produced-report")
    if mutate:
        mutate(report)
    report_ref = store.put_record(report)
    return bundle, store, report, report_ref


def _review_report_claim(claim, evidence):
    """Explicit bounded MOCK reviewer: check key measured/order claims from bytes."""
    matches = True
    if claim.get("claim_id") == "unseen-score-0":
        sources = [json.loads(raw) for raw in evidence]
        final = next(r for r in sources if r.get("kind") == "final_validation_result")
        matches = f"= {final['scores'][0]['value']} " in claim["statement"]
    elif claim.get("claim_id") == "order-0":
        sources = [json.loads(raw) for raw in evidence]
        quantity = next(r for r in sources if r.get("kind") == "quantity_result")
        matches = f"approved order {quantity['orders'][0]['approved_order_quantity']} product_unit" in claim["statement"]
    return {"status": "pass" if matches else "fail", "expected": "Exact MOCK measured score and approved order",
            "actual": "matches immutable evidence" if matches else "contradicts immutable evidence"}


@pytest.mark.parametrize("claim_id,old,new", [(None, "", ""), ("unseen-score-0", "= 8 ", "= 1 "),
                                               ("order-0", "approved order 15 ", "approved order 999 ")])
def test_mock_generated_report_false_measured_claims_block_delivery(tmp_path, claim_id, old, new):
    def mutate(report):
        if claim_id is not None:
            claim = next(c for c in report["claims"] if c["claim_id"] == claim_id)
            assert old in claim["statement"]
            report["customer_draft"] = report["customer_draft"].replace(claim["statement"], claim["statement"].replace(old, new))
            claim["statement"] = claim["statement"].replace(old, new)
    bundle, store, report, report_ref = _produced_report(tmp_path, mutate)
    assert validate_record(report) == []
    verifier = OutputVerifier(store, current_records=[record_ref(r) for r in bundle["records"]] + [report_ref],
                              current_artifacts=[a["ref"] for a in bundle["mock_artifacts"]],
                              authenticate=lambda *_: True, allow_mock=True,
                              review_claim=_review_report_claim,
                              review_narrative=lambda *_: OUTPUT.passed("Bounded MOCK prose review only"))
    checked = verifier.verify_draft(report_ref, verification_id="mock-dsc56-produced-report-check",
                                    readers=OUTPUT.success_readers(bundle))
    if claim_id is None:
        assert all(c["status"] == "pass" for c in checked["claim_checks"] + checked["arithmetic_checks"] + checked["binding_checks"])
    else:
        assert any(c["status"] == "fail" for c in checked["claim_checks"])
        with pytest.raises(VerificationError, match="failed or unavailable"):
            verifier.propose_delivery(record_ref(checked), parent_decision={
                **report["parent_decision"], "checkpoint": "output_verification", "decision": "proceed",
                "evidence_refs": [report_ref, record_ref(checked)]}, readers=OUTPUT.success_readers(bundle))


def test_mock_previously_accepted_candidate_evidence_cannot_accept_changed_candidate_bytes(tmp_path):
    bundle, store, readers, candidate = _mock_candidate(tmp_path)
    checked = _candidate_check(bundle, store, readers, candidate)
    assert checked["verifier_decision"] == "accepted"
    changed = deepcopy(candidate)
    changed["orders"][0].update(usable_on_hand_quantity=10, raw_order_need=7, rounded_order_quantity=10)
    assert record_ref(changed) not in checked["checked_artifacts"]
    # Immutable id/version cannot be silently replaced under accepted evidence.
    with pytest.raises(ArtifactError, match="immutable"):
        store.put_record(changed)
    changed["artifact_id"] += "-corrected"
    rechecked = _candidate_check(bundle, store, readers, changed)
    assert rechecked["checked_artifacts"] == [record_ref(changed)]
    assert rechecked["verifier_decision"] == "rejected"


def test_mock_unmodified_shared_findings_compose_with_unique_report_identities(tmp_path):
    """Compose actual source-local IDs without rewriting the shared findings.

    The report owns its combined identities while preserving each upstream
    finding's statement, classification, audience, and exact evidence links.
    This MOCK seam verifies composition, not live analytical acceptance.
    """
    bundle, store, report, report_ref = _produced_report(tmp_path, namespace_mock_findings=False)
    assert validate_record(report) == []
    source_findings = [finding for source in bundle["records"]
                       if source["kind"] in {"preparation_result", "feature_result", "evaluation_result", "final_validation_result"}
                       for finding in source["findings"] if finding["audience"] == "final_report"]
    source_ids = [finding["finding_id"] for finding in source_findings]
    assert len(source_ids) > len(set(source_ids))
    report_ids = [finding["finding_id"] for finding in report["findings"]]
    assert len(report_ids) == len(set(report_ids))
    content = lambda finding: json.dumps({key: value for key, value in finding.items()
                                        if key != "finding_id"}, sort_keys=True)
    assert sorted(map(content, report["findings"])) == sorted(map(content, source_findings))
    verifier = OutputVerifier(store, current_records=[record_ref(r) for r in bundle["records"]] + [report_ref],
                              current_artifacts=[a["ref"] for a in bundle["mock_artifacts"]],
                              authenticate=lambda *_: True, allow_mock=True,
                              review_claim=_review_report_claim,
                              review_narrative=lambda *_: OUTPUT.passed("Bounded MOCK prose review only"))
    checked = verifier.verify_draft(report_ref, verification_id="mock-dsc56-composed-findings",
                                    readers=OUTPUT.success_readers(bundle))
    identity_check = next(c for c in checked["claim_checks"] if c["check_id"] == "claims-unique-identities")
    assert identity_check["status"] == "pass"
    assert all(c["status"] == "pass" for c in checked["claim_checks"] + checked["arithmetic_checks"] + checked["binding_checks"])


def test_mock_forged_duplicate_report_finding_identity_blocks_independent_delivery(tmp_path):
    """Keep duplicate rejection independent of the corrected report producer.

    A schema-valid forged report reuses one final finding's identity while
    retaining its other content. The verifier must detect the collision and
    refuse delivery despite otherwise valid source evidence.
    """
    def forge(report):
        assert len(report["findings"]) >= 2
        report["findings"][1]["finding_id"] = report["findings"][0]["finding_id"]

    bundle, store, report, report_ref = _produced_report(tmp_path, forge, namespace_mock_findings=False)
    assert validate_record(report) == []
    verifier = OutputVerifier(store, current_records=[record_ref(r) for r in bundle["records"]] + [report_ref],
                              current_artifacts=[a["ref"] for a in bundle["mock_artifacts"]],
                              authenticate=lambda *_: True, allow_mock=True,
                              review_claim=_review_report_claim,
                              review_narrative=lambda *_: OUTPUT.passed("Bounded MOCK prose review only"))
    readers = OUTPUT.success_readers(bundle)
    checked = verifier.verify_draft(report_ref, verification_id="mock-dsc56-forged-duplicate-finding", readers=readers)
    identity_check = next(c for c in checked["claim_checks"] if c["check_id"] == "claims-unique-identities")
    assert identity_check["status"] == "fail"
    assert checked["permitted_response"]["kind"] == "no_customer_response"
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision={
            **report["parent_decision"], "checkpoint": "output_verification", "decision": "proceed",
            "evidence_refs": [report_ref, record_ref(checked)]}, readers=readers)
