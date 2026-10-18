"""Independent verifier/delivery component tests using explicit mock graphs.

The shared examples describe invented runs. Bytes are actually registered in the
immutable store; passing these tests never establishes a completed customer run.
No external customer transport is used.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path

import pytest

from suiroai.contracts import record_ref, validate_handoff, validate_record
from suiroai.contracts.validation import digest, input_digest, proposal_digest, walk
from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.verification import OutputVerifier, SourceReaders, VerificationError


EXAMPLES = Path(__file__).resolve().parents[2] / "examples/contracts/v0.1.0"
REF_FIELDS = {"artifact_id", "version", "sha256", "provenance"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def record(bundle, kind):
    return max((r for r in bundle["records"] if r["kind"] == kind),
               key=lambda r: r["artifact_version"])


def artifact_bytes(artifact):
    return artifact.get("raw_bytes", canonical(artifact["content_marker"]))


def rehash(bundle):
    """Bind edited mock records to their actual canonical bytes, to a fixed point."""
    for _ in range(40):
        old = deepcopy(bundle)
        if any("raw_bytes" in a for a in bundle["mock_artifacts"]):
            # A success fixture uses the actual CSV byte format, rather than its
            # original JSON marker, so all approved input/proposal bindings move.
            external = {a["ref"]["artifact_id"]: a for a in bundle["mock_artifacts"]}
            submission = record(bundle, "submission")
            for item in submission["files"]:
                raw = artifact_bytes(external[item["file_id"]])
                item.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
            input_hash = input_digest(submission)
            for node in walk(bundle):
                if {"task_id", "task_version", "input_version", "input_digest"} <= set(node):
                    node["input_digest"] = input_hash
            proposal_hash = proposal_digest(record(bundle, "task_proposal"))
            for node in walk(bundle):
                if {"task_id", "proposal_version", "proposal_digest"} <= set(node):
                    node["proposal_digest"] = proposal_hash
        hashes = {(r["artifact_id"], r["artifact_version"]): digest(r)
                  for r in bundle["records"]}
        hashes.update({(a["ref"]["artifact_id"], a["ref"]["version"]):
                       hashlib.sha256(artifact_bytes(a)).hexdigest()
                       for a in bundle["mock_artifacts"]})
        changed = False
        for node in walk(bundle):
            if set(node) == REF_FIELDS:
                sha = hashes.get((node["artifact_id"], node["version"]))
                if sha is not None and node["sha256"] != sha:
                    node["sha256"] = sha
                    changed = True
        if not changed and bundle == old:
            return bundle
    raise AssertionError("Mock graph did not converge")


def fixture(name="execution_failed"):
    bundle = json.loads((EXAMPLES / f"{name}.json").read_text())
    bundle["records"] = [r for r in bundle["records"]
                         if r["kind"] != "output_verification" and r["artifact_id"] != "mock-evidence-record"]
    return bundle


def passed(actual):
    return {"status": "pass", "expected": "Independently inspected mock evidence",
            "actual": actual}


def failed(actual):
    return {"status": "fail", "expected": "Truthful scoped terminal explanation",
            "actual": actual}


def claim_review(item, evidence):
    """Inspect actual source JSON, not a producer's report/check pass flag."""
    sources = [json.loads(raw) for raw in evidence]
    if item.get("classification") == "material_limitation":
        return passed("Mock fixture limitation is explicit")
    source = sources[0]
    if source["kind"] == "stage_result":
        expected = source["failure"]["reason"]
        if source["outcome"] != "execution_failed" or expected not in item["statement"]:
            return failed("Terminal claim does not match actual failed stage reason")
    elif source["kind"] == "final_validation_result":
        measured = source["scores"][0]["value"]
        if source["outcome"] != "fail" or str(measured) not in item["statement"]:
            return failed("Validation claim contradicts measured frozen holdout score")
    else:
        return failed("No supported terminal source")
    return passed("Terminal claim agrees with the actual stored failed-result bytes")


def narrative_review(draft, evidence):
    # This is an explicitly bounded mock reviewer, not a production NLP parser.
    text = draft["customer_draft"]
    if (draft["orders"] or draft["quantity_result_ref"] is not None
            or draft["failure"]["reason"] not in text
            or draft["failure"]["scope_limitation"] not in text
            or "MOCK" not in text or "No valid restocking list is available." not in text
            or "MAE 1 " in text or "runner-up" in text):
        return failed("Narrative invents a result, conceals a limitation or adds recommendations")
    assert evidence and all(type(raw) is bytes for raw in evidence.values())
    return passed("Entire mock explanation matches failure, provenance, scope and absent list")


def load(tmp_path, bundle=None, **kwargs):
    bundle = rehash(bundle or fixture())
    store = ArtifactStore(tmp_path)
    refs = [store.put_record(r) for r in bundle["records"]]
    external = []
    for artifact in bundle["mock_artifacts"]:
        ref = artifact["ref"]
        stored = store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"],
                                 artifact_bytes(artifact))
        assert stored == ref
        external.append(stored)
    options = dict(current_records=refs, current_artifacts=external,
                   authenticate=lambda records, artifacts: True, allow_mock=True,
                   review_claim=claim_review, review_narrative=narrative_review)
    options.update(kwargs)
    verifier = OutputVerifier(store, **options)
    return bundle, store, verifier


def check(verifier, bundle):
    return verifier.verify_draft(record_ref(record(bundle, "report_draft")),
                                 verification_id="mock-independent-verification")


def parent_decision(bundle, checked):
    value = deepcopy(record(bundle, "report_draft")["parent_decision"])
    value.update(checkpoint="output_verification", decision="proceed",
                 evidence_refs=[record_ref(record(bundle, "report_draft")), record_ref(checked)])
    return value


def approved(tmp_path, name="execution_failed", **kwargs):
    bundle, store, verifier = load(tmp_path, fixture(name), **kwargs)
    checked = check(verifier, bundle)
    proposal = verifier.propose_delivery(record_ref(checked),
                                        parent_decision=parent_decision(bundle, checked))
    ref = store.put_record(proposal)
    return bundle, store, verifier, checked, proposal, ref


@pytest.mark.parametrize("name", ["execution_failed", "validation_failed"])
def test_failure_check_is_independent_and_always_check_only(tmp_path, name):
    bundle, store, verifier = load(tmp_path, fixture(name))
    checked = check(verifier, bundle)
    assert checked["decision"] == "blocked"
    assert checked["parent_decision"] is None
    assert checked["permitted_response"] == {
        "kind": "no_customer_response", "text": "", "report_ref": None}
    assert checked["arithmetic_checks"] == []
    assert all(c["status"] == "pass" for c in checked["binding_checks"] + checked["claim_checks"])
    assert store.read_record(record_ref(checked)) == checked
    assert validate_handoff(bundle["records"] + [checked],
                            [a["ref"] for a in bundle["mock_artifacts"]]) == []


@pytest.mark.parametrize("name", ["execution_failed", "validation_failed"])
def test_verified_terminal_explanation_delivers_exact_artifact_without_quantities(tmp_path, name):
    bundle, store, verifier, checked, proposal, ref = approved(tmp_path, name)
    report = record(bundle, "report_draft")
    assert proposal["decision"] == "delivery_allowed"
    assert proposal["permitted_response"] == {
        "kind": "failure_explanation", "text": report["customer_draft"],
        "report_ref": record_ref(report)}
    assert not report["orders"] and report["quantity_result_ref"] is None
    authorized = []
    published = []
    def authorize(value):
        authorized.append(value)
        return True
    def publish(data):
        published.append(data)
        return {"reference": "mock-existing-response-surface/1", "content": data}
    receipt = verifier.deliver(ref, authorize=authorize, publish=publish)
    expected = report["customer_draft"].encode()
    assert authorized == [proposal] and published == [expected]
    assert store.read_bytes(receipt["delivered_artifact_ref"]) == expected
    assert receipt["sha256"] == hashlib.sha256(expected).hexdigest()
    assert receipt["report_ref"] == record_ref(report)
    assert receipt["verification_ref"] == ref
    assert receipt["destination_reference"] == "mock-existing-response-surface/1"
    assert receipt["mock"] is True and receipt["unresolved_blockers"] == []
    evidence = store.read_record(receipt["delivery_evidence_ref"])
    assert validate_record(evidence) == []
    assert evidence["kind"] == "evidence_record"
    assert evidence["checked_artifacts"] == [ref]
    assert evidence["binding"] == proposal["binding"] and evidence["run_id"] == proposal["run_id"]
    assert evidence["evidence_mode"] == "mock" and evidence["mock_limitation"]
    assert evidence["verifier_decision"] == "accepted"
    assert evidence["check"]["check_id"] == "delivered-content"
    assert evidence["check"]["status"] == "pass"
    assert evidence["check"]["actual"] == "sha256=" + hashlib.sha256(expected).hexdigest()
    assert evidence["check"]["evidence_refs"] == [ref, record_ref(report), receipt["delivered_artifact_ref"]]


def test_mocks_block_real_customer_run_by_default(tmp_path):
    bundle, _, verifier = load(tmp_path, allow_mock=False)
    with pytest.raises(VerificationError, match="mock evidence cannot establish"):
        check(verifier, bundle)


@pytest.mark.parametrize("answer", [False, None, 1, "approved", {"approved": True}])
def test_current_parent_authentication_requires_literal_true(tmp_path, answer):
    bundle, _, verifier = load(tmp_path, authenticate=lambda *args: answer)
    with pytest.raises(VerificationError, match="parent did not authenticate"):
        check(verifier, bundle)


def test_reviewers_receive_resolved_measured_json_and_complete_narrative(tmp_path):
    seen = []
    def review(item, evidence):
        assert all(type(raw) is bytes for raw in evidence)
        assert json.loads(evidence[0])["kind"] == "stage_result"
        seen.append(item)
        return claim_review(item, evidence)
    def review_all(draft, evidence):
        assert draft["failure"]["error_code"] == "plugin_unavailable"
        assert any(json.loads(raw).get("kind") == "stage_result"
                   for raw in evidence.values())
        return narrative_review(draft, evidence)
    bundle, _, verifier = load(tmp_path, review_claim=review, review_narrative=review_all)
    checked = check(verifier, bundle)
    assert len(seen) == 2  # Declared claim and customer-visible finding.
    assert all(c["status"] == "pass" for c in checked["claim_checks"])


def test_unavailable_independent_review_cannot_reuse_producer_pass_flags(tmp_path):
    bundle, _, verifier = load(tmp_path, review_claim=None, review_narrative=None)
    # Shared examples already contain upstream pass flags; they cannot replace review.
    checked = check(verifier, bundle)
    assert any(c["status"] == "unavailable" for c in checked["claim_checks"])
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))


@pytest.mark.parametrize("kind", ["claim", "narrative"])
def test_independently_failed_semantics_blocks_parent_proposal(tmp_path, kind):
    options = {"review_claim" if kind == "claim" else "review_narrative":
               lambda *args: failed("Mock independent source discrepancy")}
    bundle, _, verifier = load(tmp_path, **options)
    checked = check(verifier, bundle)
    assert any(c["status"] == "fail" for c in checked["claim_checks"])
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))


def test_changed_review_between_check_and_permission_blocks_delivery(tmp_path):
    state = {"fail": False}
    def review(*args):
        return failed("New independently observed contradiction") if state["fail"] else claim_review(*args)
    bundle, _, verifier = load(tmp_path, review_claim=review)
    checked = check(verifier, bundle)
    state["fail"] = True
    with pytest.raises(VerificationError, match="changed, failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))


def test_execution_failure_requires_exact_failed_stage_not_just_same_error_code(tmp_path):
    bundle = fixture()
    draft = record(bundle, "report_draft")
    draft["failure"]["reason"] = "MOCK invented execution failure under a real error code."
    draft["customer_draft"] = (draft["failure"]["reason"] + " " +
                               draft["failure"]["scope_limitation"] +
                               " No valid restocking list is available.")
    bundle, _, verifier = load(tmp_path, bundle)
    checked = check(verifier, bundle)
    terminal = next(c for c in checked["binding_checks"]
                    if c["check_id"] == "terminal-execution-evidence")
    assert terminal["status"] == "fail"
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))


def test_execution_unavailability_cannot_fabricate_measured_underperformance(tmp_path):
    bundle = fixture()
    draft = record(bundle, "report_draft")
    draft["claims"][0]["statement"] = "MOCK measured MAE 1 proves accurate forecasts."
    draft["customer_draft"] += " MAE 1 proves accurate forecasts."
    bundle, _, verifier = load(tmp_path, bundle)
    checked = check(verifier, bundle)
    assert next(c for c in checked["claim_checks"]
                if c["check_id"] == "claims-claim-0")["status"] == "fail"
    assert next(c for c in checked["claim_checks"]
                if c["check_id"] == "claims-full-narrative")["status"] == "fail"


def test_failed_validation_cannot_be_disguised_as_success(tmp_path):
    bundle = fixture("validation_failed")
    draft = record(bundle, "report_draft")
    draft.update(outcome="success", customer_draft="MOCK a runner-up produced valid orders.")
    bundle, _, verifier = load(tmp_path, bundle)
    with pytest.raises(VerificationError):
        check(verifier, bundle)


def test_unconcluded_final_parent_review_cannot_deliver_terminal_validation(tmp_path):
    bundle = fixture("validation_failed")
    record(bundle, "final_validation_result")["parent_review"]["decision"] = "review"
    bundle, _, verifier = load(tmp_path, bundle)
    with pytest.raises(VerificationError, match="concluded parent review"):
        check(verifier, bundle)


@pytest.mark.parametrize("change", ["checkpoint", "decision", "missing-report", "missing-check", "stale-report", "stale-check"])
def test_parent_permission_binds_exact_report_and_independent_checks(tmp_path, change):
    bundle, _, verifier = load(tmp_path)
    checked = check(verifier, bundle)
    decision = parent_decision(bundle, checked)
    if change == "checkpoint":
        decision["checkpoint"] = "final_validation"
    elif change == "decision":
        decision["decision"] = "stop"
    elif change == "missing-report":
        decision["evidence_refs"].pop(0)
    elif change == "missing-check":
        decision["evidence_refs"].pop(1)
    else:
        decision["evidence_refs"][0 if change == "stale-report" else 1]["sha256"] = "0" * 64
    with pytest.raises(VerificationError, match="bind exact report and check-only evidence"):
        verifier.propose_delivery(record_ref(checked), parent_decision=decision)


def test_check_only_artifact_never_publishes(tmp_path):
    bundle, _, verifier = load(tmp_path)
    checked = check(verifier, bundle)
    published = []
    with pytest.raises(VerificationError, match="parent-authorized verification"):
        verifier.deliver(record_ref(checked), authorize=lambda *args: True,
                         publish=lambda data: published.append(data))
    assert not published


@pytest.mark.parametrize("veto", [False, 1, {"approved": True}])
def test_current_parent_veto_prevents_publish(tmp_path, veto):
    _, _, verifier, _, _, ref = approved(tmp_path)
    published = []
    with pytest.raises(VerificationError, match="not currently authorized"):
        verifier.deliver(ref, authorize=lambda *args: veto,
                         publish=lambda data: published.append(data))
    assert not published


def test_revoked_current_handoff_authentication_prevents_publish(tmp_path):
    state = {"allowed": True}
    _, _, verifier, _, _, ref = approved(tmp_path, authenticate=lambda *args: state["allowed"])
    state["allowed"] = False
    published = []
    with pytest.raises(VerificationError, match="parent did not authenticate"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=lambda data: published.append(data))
    assert not published


def test_modified_approved_response_is_recomputed_and_rejected_before_publish(tmp_path):
    bundle, store, verifier = load(tmp_path)
    checked = check(verifier, bundle)
    proposal = verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))
    proposal["permitted_response"]["text"] += " MOCK unsupported promise."
    ref = store.put_record(proposal)
    published = []
    with pytest.raises(VerificationError, match="stale, altered"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=lambda data: published.append(data))
    assert not published


def test_new_current_draft_invalidates_prior_delivery(tmp_path):
    bundle, store, old, _, _, ref = approved(tmp_path)
    report = record(bundle, "report_draft")
    report["artifact_version"] += 1
    report["customer_draft"] += " MOCK clarified limitation."
    new_report_ref = store.put_record(report)
    refs = [new_report_ref if r["artifact_id"] == report["artifact_id"] else r for r in old.record_refs]
    verifier = OutputVerifier(store, current_records=refs, current_artifacts=old.artifact_refs,
                              authenticate=lambda *args: True, allow_mock=True,
                              review_claim=claim_review, review_narrative=narrative_review)
    published = []
    with pytest.raises(VerificationError, match="current parent-selected report"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=lambda data: published.append(data))
    assert not published


@pytest.mark.parametrize("readback", [b"different bytes", "same text but not bytes", None])
def test_delivery_requires_exact_actual_readback(tmp_path, readback):
    _, store, verifier, _, proposal, ref = approved(tmp_path)
    sent = []
    def publish(data):
        sent.append(data)
        return {"reference": "mock-existing-surface", "content": readback}
    with pytest.raises(VerificationError, match="readback differs") as caught:
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    assert len(sent) == 1  # Delivery happened; mismatched readback cannot be called verified.
    evidence = store.read_record(caught.value.evidence_ref)
    assert validate_record(evidence) == []
    assert evidence["kind"] == "evidence_record"
    assert evidence["checked_artifacts"] == [ref]
    assert evidence["binding"] == proposal["binding"] and evidence["run_id"] == proposal["run_id"]
    assert evidence["evidence_mode"] == "mock" and evidence["mock_limitation"]
    assert evidence["verifier_decision"] == "rejected"
    assert evidence["check"]["check_id"] == "delivered-content"
    assert evidence["check"]["status"] == "fail"
    assert evidence["check"]["evidence_refs"] == [ref, proposal["report_draft_ref"]]
    assert evidence["check"]["expected"] == "readback_sha256=" + hashlib.sha256(sent[0]).hexdigest()
    expected_actual = ("readback_sha256=" + hashlib.sha256(readback).hexdigest()
                       if isinstance(readback, bytes) else "no valid byte readback")
    assert evidence["check"]["actual"] == expected_actual
    if readback:
        bad_text = readback.decode() if isinstance(readback, bytes) else readback
        assert bad_text not in canonical(evidence).decode()


def test_changed_source_bytes_are_remeasured_before_delivery(tmp_path):
    _, store, verifier, _, _, ref = approved(tmp_path)
    source = verifier.artifact_refs[0]
    path = store.root / "objects" / source["sha256"]
    path.chmod(0o600)
    path.write_bytes(b"MOCK altered source bytes")
    published = []
    with pytest.raises(ArtifactError, match="measured artifact bytes"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=lambda data: published.append(data))
    assert not published


def success_fixture():
    """Explicit daily trajectory and operational CSVs, still MOCK ONLY."""
    bundle = fixture("successful_analysis")
    artifacts = {a["ref"]["artifact_id"]: a for a in bundle["mock_artifacts"]}
    key = deepcopy(record(bundle, "report_draft")["orders"][0]["key"])
    for name in ("mock-stock", "mock-receipts", "mock-policy"):
        artifact = artifacts[name]
        rows = deepcopy(artifact["content_marker"]["rows"])
        for row in rows:
            for field, value in list(row.items()):
                if isinstance(value, bool):
                    row[field] = str(value).lower()
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        artifact["raw_bytes"] = text.getvalue().encode()
    forecast = artifacts["mock-november-30-forecast"]["content_marker"]
    forecast["daily_rows"] = [{"key": deepcopy(key),
                               "date": (date(2025, 12, 1) + timedelta(days=i)).isoformat(),
                               "quantity": 20 if i == 7 else 0,
                               "quantity_unit": "product_unit", "as_of_date": "2025-11-30",
                               "latest_information_available_date": "2025-11-30"}
                              for i in range(14)]
    artifacts["mock-dictionary"]["content_marker"] = {
        "notice": "MOCK ONLY source names/scope; never customer acceptance",
        "scope": [key], "names": [{"key": key, "product_name": "Mock widget",
                                      "latest_information_available_date": "2025-11-30"}]}
    for item in bundle["records"]:
        if item["kind"] in {"quantity_result", "report_draft"}:
            item["orders"][0]["product_name"] = "Mock widget"
    return rehash(bundle)


def success_readers(bundle):
    refs = {a["ref"]["artifact_id"]: a["ref"] for a in bundle["mock_artifacts"]}
    return SourceReaders(inventory_ref=refs["mock-stock"], receipt_ref=refs["mock-receipts"],
                         policy_ref=refs["mock-policy"], scope_ref=refs["mock-dictionary"],
                         names_ref=refs["mock-dictionary"], source_namespace="mock-retail",
                         forecast=lambda raw: json.loads(raw)["daily_rows"],
                         scope=lambda raw: json.loads(raw)["scope"],
                         names=lambda raw: json.loads(raw)["names"])


def success_claim_review(item, evidence):
    sources = [json.loads(raw) for raw in evidence]
    if item.get("classification") == "material_limitation":
        return passed("Mock component limitation explicit")
    final, quantity = sources
    if (final["outcome"] != "pass" or final["scores"][0]["value"] != 8
            or quantity["orders"][0]["approved_order_quantity"] != 15
            or "MAE 8" not in item["statement"] or "15 product units" not in item["statement"]):
        return failed("Mock report measured claims disagree with approved evidence bytes")
    return passed("Mock measured score 8 and approved quantity 15 match source records")


def success_narrative_review(draft, evidence):
    if (len(draft["orders"]) != 1 or draft["orders"][0]["product_name"] != "Mock widget"
            or draft["orders"][0]["approved_order_quantity"] != 15
            or "All stock, policies, metrics and quantities are invented." not in draft["customer_draft"]):
        return failed("Mock final list or synthetic limitation is inaccurate")
    assert evidence and all(type(raw) is bytes for raw in evidence.values())
    return passed("Mock full report list, measured results and synthetic limitations agree")


def test_success_independently_reconciles_actual_csv_daily_forecast_and_delivered_report(tmp_path):
    bundle, store, verifier = load(tmp_path, success_fixture(),
                                   review_claim=success_claim_review,
                                   review_narrative=success_narrative_review)
    readers = success_readers(bundle)
    checked = verifier.verify_draft(record_ref(record(bundle, "report_draft")),
                                    verification_id="mock-independent-success", readers=readers)
    assert checked["decision"] == "blocked"
    assert checked["arithmetic_checks"]
    assert all(c["status"] == "pass" for c in checked["arithmetic_checks"] +
               checked["claim_checks"] + checked["binding_checks"])
    raw_need = next(c for c in checked["arithmetic_checks"]
                    if c["check_id"].startswith("raw_order_need-"))
    assert raw_need["expected"] == "12"
    proposal = verifier.propose_delivery(record_ref(checked),
                                        parent_decision=parent_decision(bundle, checked), readers=readers)
    assert proposal["permitted_response"]["kind"] == "final_report"
    ref = store.put_record(proposal)
    receipt = verifier.deliver(ref, authorize=lambda value: value == proposal,
                              publish=lambda data: {"reference": "mock-existing-report-surface",
                                                    "content": data}, readers=readers)
    assert store.read_bytes(receipt["delivered_artifact_ref"]) == record(bundle, "report_draft")["customer_draft"].encode()
    assert receipt["mock"] is True
    evidence = store.read_record(receipt["delivery_evidence_ref"])
    assert validate_record(evidence) == []
    assert evidence["checked_artifacts"] == [ref]
    assert evidence["evidence_mode"] == "mock" and evidence["verifier_decision"] == "accepted"
    assert evidence["check"]["status"] == "pass"
    assert evidence["check"]["actual"] == "sha256=" + receipt["sha256"]
    assert evidence["check"]["evidence_refs"] == [ref, receipt["report_ref"], receipt["delivered_artifact_ref"]]


@pytest.mark.parametrize("change", ["quantity", "name", "daily-timing", "forecast-unit", "forecast-stale", "missing-daily"])
def test_success_producer_flags_cannot_hide_independent_arithmetic_or_source_errors(tmp_path, change):
    bundle = success_fixture()
    if change in {"quantity", "name"}:
        for item in bundle["records"]:
            if item["kind"] in {"quantity_result", "report_draft"}:
                item["orders"][0]["product_name"] = "Wrong widget" if change == "name" else "Mock widget"
                if change == "quantity":
                    # Schema arithmetic stays coherent, but contradicts raw stock bytes.
                    row = item["orders"][0]
                    row.update(usable_on_hand_quantity=0, raw_order_need=17, rounded_order_quantity=20)
                    if row["approved_order_quantity"] is not None:
                        row["approved_order_quantity"] = 20
    else:
        forecast = next(a for a in bundle["mock_artifacts"]
                        if a["ref"]["artifact_id"] == "mock-november-30-forecast")["content_marker"]
        rows = forecast["daily_rows"]
        if change == "daily-timing":
            rows[0]["quantity"], rows[7]["quantity"] = 20, 0
        elif change == "forecast-unit":
            rows[0]["quantity_unit"] = "case"
        elif change == "forecast-stale":
            rows[0]["as_of_date"] = "2025-11-29"
        else:
            rows.pop(0)
    bundle, _, verifier = load(tmp_path, bundle, review_claim=success_claim_review,
                               review_narrative=success_narrative_review)
    checked = verifier.verify_draft(record_ref(record(bundle, "report_draft")),
                                    verification_id="mock-independent-error", readers=success_readers(bundle))
    assert all(c["status"] == "pass" for c in record(bundle, "report_draft")["arithmetic_checks"])
    assert any(c["status"] == "fail" for c in checked["arithmetic_checks"])
    assert checked["permitted_response"]["kind"] == "no_customer_response"
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked),
                                  readers=success_readers(bundle))


@pytest.mark.parametrize("change", ["stage-unreviewed", "stage-proceed", "stage-review", "wrong-stage", "report-review", "report-wrong-stage", "report-wrong-evidence"])
def test_execution_failure_waits_for_parent_concluded_exact_stage_review(tmp_path, change):
    bundle = fixture()
    stage = record(bundle, "stage_result")
    draft = record(bundle, "report_draft")
    if change == "stage-unreviewed":
        stage["parent_decision"] = None
    elif change in {"stage-proceed", "stage-review"}:
        stage["parent_decision"]["decision"] = change.split("-")[1]
    elif change == "wrong-stage":
        stage["parent_decision"]["checkpoint"] = "final_validation"
    elif change == "report-review":
        draft["parent_decision"]["decision"] = "review"
    elif change == "report-wrong-stage":
        draft["parent_decision"]["checkpoint"] = "final_validation"
    else:
        draft["parent_decision"]["evidence_refs"] = deepcopy(stage["evidence_refs"])
    bundle, _, verifier = load(tmp_path, bundle)
    checked = check(verifier, bundle)
    terminal = next(c for c in checked["binding_checks"]
                    if c["check_id"] == "terminal-execution-evidence")
    assert terminal["status"] == "fail"
    assert checked["permitted_response"]["kind"] == "no_customer_response"
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))


def test_candidate_check_emits_independent_measured_evidence_before_quantity_approval(tmp_path):
    bundle, store, verifier = load(tmp_path, success_fixture())
    candidate = next(r for r in bundle["records"]
                     if r["kind"] == "quantity_result" and r["artifact_version"] == 1)
    evidence = verifier.check_candidate(record_ref(candidate), readers=success_readers(bundle),
                                        evidence_id="mock-new-independent-quantity-evidence",
                                        verified_at="2026-10-17T09:04:00Z")
    assert evidence["verifier_decision"] == "accepted"
    assert evidence["check"]["status"] == "pass"
    assert evidence["checked_artifacts"] == [record_ref(candidate)]
    assert evidence["verifier"] == "DSC-30"
    assert evidence["evidence_mode"] == "mock" and evidence["mock_limitation"]
    assert store.read_record(record_ref(evidence)) == evidence
    trace = json.loads(evidence["check"]["actual"])
    assert trace["exceptions"] == []
    assert any(c["check_id"].startswith("raw_order_need-")
               and c["expected"] == "12" and c["status"] == "pass"
               for c in trace["checks"])
    assert candidate["parent_decision"] is None
    assert candidate["orders"][0]["approved_order_quantity"] is None


def test_parent_approved_quantity_cannot_pose_as_unapproved_candidate(tmp_path):
    bundle, _, verifier = load(tmp_path, success_fixture())
    approved_quantity = record(bundle, "quantity_result")
    with pytest.raises(VerificationError, match="candidate cannot approve its own quantities"):
        verifier.check_candidate(record_ref(approved_quantity), readers=success_readers(bundle),
                                  evidence_id="mock-self-approval-evidence",
                                  verified_at="2026-10-17T09:04:00Z")


def test_candidate_is_checked_before_any_report_parent_quantity_approval_or_prior_numerical_evidence(tmp_path):
    bundle = success_fixture()
    bundle["records"] = [r for r in bundle["records"]
                         if r["kind"] not in {"report_draft", "evidence_record"}
                         and not (r["kind"] == "quantity_result" and r["artifact_version"] > 1)]
    assert not any(r["kind"] in {"report_draft", "evidence_record", "output_verification"}
                   for r in bundle["records"])
    bundle, store, verifier = load(tmp_path, bundle)
    candidate = record(bundle, "quantity_result")
    assert candidate["artifact_version"] == 1 and candidate["parent_decision"] is None
    assert all(row["approved_order_quantity"] is None for row in candidate["orders"])
    assert validate_handoff(bundle["records"], [a["ref"] for a in bundle["mock_artifacts"]]) == []
    evidence = verifier.check_candidate(record_ref(candidate), readers=success_readers(bundle),
                                        evidence_id="mock-first-independent-quantity-check",
                                        verified_at="2026-10-17T09:04:00Z")
    assert evidence["verifier_decision"] == "accepted"
    assert evidence["check"]["status"] == "pass"
    assert evidence["checked_artifacts"] == [record_ref(candidate)]
    assert store.read_record(record_ref(evidence)) == evidence
    trace = json.loads(evidence["check"]["actual"])
    assert trace["exceptions"] == []
    assert all(c["status"] == "pass" for c in trace["checks"])
    assert any(c["check_id"].startswith("raw_order_need-") and c["expected"] == "12"
               for c in trace["checks"])


def engineering_source_parser_sample(tmp_path, change=None):
    """Tiny synthetic engineering sample for parser guards, never a run handoff.

    This calls the source reader directly with a deliberately minimal context.
    It cannot pass _snapshot, approve quantities or establish customer acceptance.
    No shared mock graph is promoted to real evidence.
    """
    store = ArtifactStore(tmp_path)
    key = {"source_namespace": "engineering-sample", "product_id": "SAMPLE-P",
           "store_id": "SAMPLE-S"}
    common = {"Product_ID": "SAMPLE-P", "Store_ID": "SAMPLE-S",
              "Quantity_Unit": "product_unit", "Provenance": "synthetic"}
    stock = {**common, "Snapshot_Date": "2025-11-30", "Usable_On_Hand_Qty": 5,
             "On_Order_Qty": 5, "Open_Order_Ledger_Complete": "true"}
    receipt = {**common, "PO_Line_ID": "SAMPLE-PO", "Order_Date": "2025-11-30",
               "Expected_Arrival_Date": "2025-12-07", "Incoming_Qty": 5}
    policy = {**common, "Effective_Date": "2025-11-30", "Supplier_Lead_Time_Days": 7,
              "Review_Period_Days": 7, "Order_Multiple_Qty": 5,
              "Minimum_Order_Qty": 5, "Safety_Stock_Qty": 2}
    if change == "mock-row-labeled-synthetic-ref":
        stock["Provenance"] = "mock"
    refs = []
    files = []
    manifest_files = {}
    for label, name, role, row in (
            ("stock", "inventory_position.csv", "usable_stock", stock),
            ("receipts", "inbound_deliveries.csv", "inbound_ledger", receipt),
            ("policy", "ordering_policy.csv", "ordering_policy", policy)):
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        provenance = "derived" if label == "stock" and change == "wrong-reference-provenance" else "synthetic"
        ref = store.put_bytes("engineering-" + label, 1, provenance, text.getvalue().encode())
        refs.append(ref)
        files.append({"file_id": ref["artifact_id"], "sha256": ref["sha256"],
                      "original_name": name, "source_role": role, "access": "accessible",
                      "source_namespace": "engineering-sample"})
        manifest_files["synthetic_sources/" + name] = {"sha256": ref["sha256"]}
    dictionary = {"scope": [key], "names": [{"key": key, "product_name": "Engineering sample",
                                             "latest_information_available_date": "2025-11-30"}]}
    dictionary_ref = store.put_bytes("engineering-scope-names", 1, "derived", canonical(dictionary))
    daily = [{"key": key, "date": (date(2025, 12, 1) + timedelta(days=i)).isoformat(),
              "quantity": 20 if i == 7 else 0, "quantity_unit": "product_unit",
              "as_of_date": "2025-11-30", "latest_information_available_date": "2025-11-30"}
             for i in range(14)]
    forecast_ref = store.put_bytes("engineering-daily-forecast", 1, "derived", canonical(daily))
    manifest = {"review_date": "2025-11-30", "counts": {
        "inventory_rows": 1, "inbound_rows": 1, "policy_rows": 1,
        "eligible_product_store_keys": 1}, "files": manifest_files}
    if change == "manifest-date":
        manifest["review_date"] = "2025-11-29"
    elif change and change.startswith("count-"):
        manifest["counts"][change.removeprefix("count-")] = 2
    elif change == "manifest-hash":
        manifest["files"]["synthetic_sources/inventory_position.csv"]["sha256"] = "0" * 64
    elif change == "manifest-missing-file":
        manifest["files"].pop("synthetic_sources/inventory_position.csv")
    elif change == "manifest-duplicate-filename":
        manifest["files"]["another/inventory_position.csv"] = deepcopy(manifest["files"]["synthetic_sources/inventory_position.csv"])
    manifest_ref = store.put_bytes("engineering-synthetic-manifest", 1, "derived", canonical(manifest))
    snapshot_refs = [*refs, dictionary_ref, forecast_ref, manifest_ref]
    if change == "manifest-outside-snapshot":
        snapshot_refs.remove(manifest_ref)
    if change == "source-outside-snapshot":
        snapshot_refs.remove(refs[0])
    readers = SourceReaders(inventory_ref=refs[0], receipt_ref=refs[1], policy_ref=refs[2],
                            scope_ref=dictionary_ref, names_ref=dictionary_ref,
                            source_namespace="engineering-sample", forecast=json.loads,
                            scope=lambda raw: json.loads(raw)["scope"],
                            names=lambda raw: json.loads(raw)["names"],
                            manifest_ref=None if change == "manifest-absent" else manifest_ref)
    execution = {"source_refs": deepcopy(refs), "synthetic_operational_source_refs": deepcopy(refs),
                 "temporal_plan": {"as_of_date": "2025-11-30"},
                 "inbound_ledger_policy": "complete_synthetic_ledger_absence_is_zero"}
    draft = {"provenance": "derived", "november_30_forecast_ref": forecast_ref,
             "arithmetic_source_refs": deepcopy(refs)}
    records = [{"kind": "submission", "files": files}]
    if change == "source-role":
        files[0]["source_role"] = "transactions"
    elif change == "execution-source-unbound":
        execution["source_refs"].pop(0)
    elif change == "report-source-unbound":
        draft["arithmetic_source_refs"].pop(0)
    elif change == "synthetic-source-unbound":
        execution["synthetic_operational_source_refs"].pop(0)
    verifier = OutputVerifier(store, current_records=[], current_artifacts=snapshot_refs,
                              authenticate=lambda *args: True)
    return verifier, readers, draft, execution, records, manifest_ref


def test_nonmock_parser_reads_current_counted_hashed_synthetic_engineering_sample(tmp_path):
    verifier, readers, draft, execution, records, manifest_ref = engineering_source_parser_sample(tmp_path)
    args, refs = verifier._read_sources(readers, draft, execution, records)
    assert refs[-1] == manifest_ref
    assert args["ledger_complete"] is True
    assert args["as_of"] == "2025-11-30"
    assert len(args["scope_keys"]) == 1 and len(args["forecast_rows"]) == 14
    for source in ("inventory_rows", "receipt_rows", "policy_rows"):
        assert len(args[source]) == 1
        assert args[source][0]["Provenance"] == "synthetic"
        assert args[source][0]["source_namespace"] == "engineering-sample"


@pytest.mark.parametrize("change, message", [
    ("manifest-absent", "current synthetic generation manifest"),
    ("manifest-outside-snapshot", "current synthetic generation manifest"),
    ("manifest-date", "manifest review date mismatch"),
    ("count-inventory_rows", "source/scope counts mismatch"),
    ("count-inbound_rows", "source/scope counts mismatch"),
    ("count-policy_rows", "source/scope counts mismatch"),
    ("count-eligible_product_store_keys", "source/scope counts mismatch"),
    ("manifest-hash", "manifest source hash mismatch"),
    ("manifest-missing-file", "manifest source hash mismatch"),
    ("manifest-duplicate-filename", "manifest source hash mismatch"),
    ("mock-row-labeled-synthetic-ref", "row provenance differs"),
    ("wrong-reference-provenance", "source provenance mismatch"),
    ("source-outside-snapshot", "outside the authenticated current snapshot"),
    ("source-role", "source role/identity mismatch"),
    ("execution-source-unbound", "not bound to approved arithmetic inputs"),
    ("report-source-unbound", "not bound to approved arithmetic inputs"),
    ("synthetic-source-unbound", "source provenance mismatch"),
])
def test_nonmock_parser_rejects_unbound_stale_inconsistent_or_mislabeled_sources(tmp_path, change, message):
    verifier, readers, draft, execution, records, _ = engineering_source_parser_sample(tmp_path, change)
    with pytest.raises(VerificationError, match=message):
        verifier._read_sources(readers, draft, execution, records)


def test_delivery_grant_cannot_publish_again_after_successful_readback(tmp_path):
    _, store, verifier, _, _, ref = approved(tmp_path)
    sent = []
    def publish(data):
        sent.append(data)
        return {"reference": "mock-once-only-surface", "content": data}
    receipt = verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    original_evidence = store.read_record(receipt["delivery_evidence_ref"])
    with pytest.raises(VerificationError, match="delivery already attempted"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    assert len(sent) == 1
    assert store.read_record(receipt["delivery_evidence_ref"]) == original_evidence


def test_delivery_grant_cannot_publish_again_after_mismatched_readback(tmp_path):
    _, store, verifier, _, _, ref = approved(tmp_path)
    sent = []
    def publish(data):
        sent.append(data)
        return {"reference": "mock-once-only-surface", "content": b"wrong readback"}
    with pytest.raises(VerificationError, match="readback differs") as first:
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    mismatch = store.read_record(first.value.evidence_ref)
    assert mismatch["verifier_decision"] == "rejected"
    with pytest.raises(VerificationError, match="delivery already attempted"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    assert len(sent) == 1
    assert store.read_record(first.value.evidence_ref) == mismatch


def test_delivery_grant_cannot_retry_after_publisher_crash(tmp_path):
    _, _, verifier, _, _, ref = approved(tmp_path)
    sent = []
    def publish(data):
        sent.append(data)
        raise RuntimeError("Mock transport crashed after potentially publishing")
    with pytest.raises(RuntimeError, match="Mock transport crashed"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    with pytest.raises(VerificationError, match="delivery already attempted"):
        verifier.deliver(ref, authorize=lambda *args: True, publish=publish)
    assert len(sent) == 1


def test_concurrent_deliveries_reserve_same_approved_grant_only_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    _, store, verifier, _, _, ref = approved(tmp_path)
    before_reservation = Barrier(2)
    publisher_lock = Lock()
    sent = []
    def authorize(value):
        assert record_ref(value) == ref
        before_reservation.wait(timeout=10)
        return True
    def publish(data):
        with publisher_lock:
            sent.append(data)
        return {"reference": "mock-concurrent-output-surface", "content": data}
    def attempt():
        try:
            return verifier.deliver(ref, authorize=authorize, publish=publish)
        except VerificationError as exc:
            return exc
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt) for _ in range(2)]
        outcomes = [future.result(timeout=20) for future in futures]
    delivered = [value for value in outcomes if isinstance(value, dict)]
    rejected = [value for value in outcomes if isinstance(value, VerificationError)]
    assert len(sent) == len(delivered) == len(rejected) == 1
    assert "delivery already attempted" in str(rejected[0])
    assert store.read_bytes(delivered[0]["delivered_artifact_ref"]) == sent[0]
    assert store.read_record(delivered[0]["delivery_evidence_ref"])["verifier_decision"] == "accepted"


def stage_review_failure_draft_fixture():
    """MOCK DSC29 handoff shape: reuse reviewed stage decision without self refs.

    The report humanizes scope and cites the immutable stage; it does not change
    failure facts. This is an agreed interface example, not an actual DSC29 run.
    """
    bundle = fixture("execution_failed")
    stage = record(bundle, "stage_result")
    draft = record(bundle, "report_draft")
    draft["failure"] = {
        "stage": stage["failure"]["stage"],
        "reason": stage["failure"]["reason"],
        "error_code": stage["failure"]["error_code"],
        "scope_limitation": ("This MVP could not produce a reliable solution with the supplied data/scope. "
                             "This does not establish that the problem is universally impossible."),
        "evidence_refs": [record_ref(stage)],
    }
    draft["parent_decision"] = deepcopy(stage["parent_decision"])
    text = ("MOCK FAILURE EXPLANATION ONLY: " + draft["failure"]["reason"] + " " +
            draft["failure"]["scope_limitation"] + " No valid restocking list is available.")
    draft["customer_draft"] = text
    draft["claims"][0]["statement"] = text
    draft["claims"][0]["evidence_refs"] = [record_ref(stage)]
    return rehash(bundle)


def test_stage_reviewed_failure_draft_can_normalize_scope_and_reuse_parent_decision_without_self_reference(tmp_path):
    bundle, store, verifier = load(tmp_path, stage_review_failure_draft_fixture())
    stage = record(bundle, "stage_result")
    draft = record(bundle, "report_draft")
    assert draft["failure"] != stage["failure"]
    assert draft["failure"]["scope_limitation"] != stage["failure"]["scope_limitation"]
    assert draft["failure"]["evidence_refs"] == [record_ref(stage)]
    assert draft["parent_decision"] == stage["parent_decision"]
    assert record_ref(stage) not in stage["parent_decision"]["evidence_refs"]
    assert draft["orders"] == [] and draft["quantity_result_ref"] is None
    assert validate_handoff(bundle["records"], [a["ref"] for a in bundle["mock_artifacts"]]) == []
    checked = check(verifier, bundle)
    assert all(c["status"] == "pass" for c in checked["binding_checks"] + checked["claim_checks"])
    terminal = next(c for c in checked["binding_checks"]
                    if c["check_id"] == "terminal-execution-evidence")
    assert terminal["status"] == "pass"
    proposal = verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))
    assert proposal["permitted_response"]["kind"] == "failure_explanation"
    approved_ref = store.put_record(proposal)
    published = []
    def publish(data):
        published.append(data)
        return {"reference": "mock-existing-normalized-failure-surface", "content": data}
    receipt = verifier.deliver(approved_ref, authorize=lambda value: value == proposal, publish=publish)
    assert published == [draft["customer_draft"].encode()]
    assert store.read_bytes(receipt["delivered_artifact_ref"]) == published[0]
    assert store.read_record(receipt["delivery_evidence_ref"])["verifier_decision"] == "accepted"
    assert receipt["mock"] is True


@pytest.mark.parametrize("change", ["reason", "error-code", "failure-stage", "unrelated-failure-evidence",
                                     "altered-embedded-decision", "unreviewed-stage", "stage-review",
                                     "report-review", "wrong-report-checkpoint", "no-exact-stage-anchor"])
def test_stage_review_reuse_cannot_authorize_altered_failure_facts_or_unreviewed_reports(tmp_path, change):
    bundle = stage_review_failure_draft_fixture()
    stage = record(bundle, "stage_result")
    draft = record(bundle, "report_draft")
    if change == "reason":
        draft["failure"]["reason"] = "MOCK invented outage inconsistent with source stage."
    elif change == "error-code":
        draft["failure"]["error_code"] = "timeout"
    elif change == "failure-stage":
        draft["failure"]["stage"] = "final_validation"
    elif change == "unrelated-failure-evidence":
        draft["failure"]["evidence_refs"] = [record_ref(record(bundle, "execution_contract"))]
    elif change == "no-exact-stage-anchor":
        # Sharing low-level capability evidence alone cannot identify which
        # immutable failed stage the reused parent review approved.
        draft["failure"]["evidence_refs"] = deepcopy(stage["failure"]["evidence_refs"])
        assert draft["parent_decision"] == stage["parent_decision"]
        assert record_ref(stage) not in draft["parent_decision"]["evidence_refs"]
    elif change == "altered-embedded-decision":
        draft["parent_decision"]["reason"] += " MOCK material altered review reason."
    elif change == "unreviewed-stage":
        stage["parent_decision"] = None
    elif change == "stage-review":
        stage["parent_decision"]["decision"] = "review"
    elif change == "report-review":
        draft["parent_decision"]["decision"] = "review"
    else:
        draft["parent_decision"]["checkpoint"] = "final_validation"
    bundle, _, verifier = load(tmp_path, bundle)
    if change == "error-code":
        # The shared contract rejects contradictory typed error evidence first.
        with pytest.raises(VerificationError, match="contradicts observed stage error"):
            check(verifier, bundle)
        return
    checked = check(verifier, bundle)
    terminal = next(c for c in checked["binding_checks"]
                    if c["check_id"] == "terminal-execution-evidence")
    assert terminal["status"] == "fail"
    assert checked["permitted_response"]["kind"] == "no_customer_response"
    with pytest.raises(VerificationError, match="failed or unavailable"):
        verifier.propose_delivery(record_ref(checked), parent_decision=parent_decision(bundle, checked))
