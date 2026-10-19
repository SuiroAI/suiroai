"""Independent review examples; all report/evidence data below are mocks.

Exercise trusted claim and whole-narrative review against resolved bytes,
rejecting false statements, missing evidence, and invalid reviewer responses.

Requirement context for these component checks:
Check the final list, EDA/feature statements, and limitations against resolved
evidence, including illustrative synthetic provenance and truthful failures.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""
from copy import deepcopy

import pytest

from suiroai.verification.claims import check_claims


REF = {"artifact_id": "mock-score", "version": 1,
       "sha256": "0" * 64, "provenance": "mock"}


def report():
    return {"kind": "report_draft", "artifact_id": "mock-report", "artifact_version": 1,
            "provenance": "mock", "outcome": "success", "orders": [],
            "quantity_result_ref": None, "customer_draft": "Mock MAE is 8.",
            "claims": [{"claim_id": "mock-mae", "statement": "Mock MAE is 8.",
                        "evidence_refs": [deepcopy(REF)]}], "findings": []}


def passed(*args):
    return {"status": "pass", "expected": "Mock independently checked evidence",
            "actual": "Mock statement agrees with the inspected evidence"}


def run(draft, **kwargs):
    return check_claims(draft, resolve_bytes=kwargs.pop("resolve_bytes", lambda ref: b"MAE=8"),
                        review_claim=kwargs.pop("review_claim", passed),
                        review_narrative=kwargs.pop("review_narrative", passed),
                        verifier="mock-independent-verifier", **kwargs)


def test_reviews_resolved_bytes_and_entire_narrative():
    seen = []
    def claim(item, evidence):
        seen.append((item, evidence))
        return passed()
    def narrative(draft, evidence):
        assert draft["customer_draft"] == "Mock MAE is 8."
        assert evidence[("mock-score", 1, "0" * 64, "mock")] == b"MAE=8"
        return passed()
    assert all(c["status"] == "pass" for c in
               run(report(), review_claim=claim, review_narrative=narrative))
    assert seen[0][1] == (b"MAE=8",)


def test_fabricated_metric_rejected_from_evidence():
    draft = report()
    draft["claims"][0]["statement"] = "Mock MAE is 1."
    def inspect(item, evidence):
        assert evidence == (b"MAE=8",)
        return {"status": "fail", "expected": "MAE 8", "actual": "Draft claims MAE 1"}
    assert any(c["status"] == "fail" for c in run(draft, review_claim=inspect))


def test_undeclared_adulterated_text_is_reviewed():
    draft = report()
    draft["customer_draft"] += " A runner-up model guarantees success."
    def inspect(draft, evidence):
        return {"status": "fail", "expected": "Evidence-supported complete narrative",
                "actual": "Undeclared guarantee and runner-up substitution lack support"}
    checks = run(draft, review_narrative=inspect)
    assert checks[-1]["check_id"] == "claims-full-narrative"
    assert checks[-1]["status"] == "fail"


@pytest.mark.parametrize("result", [True, {"status": True, "expected": "x", "actual": "y"},
    {"status": "PASS", "expected": "x", "actual": "y"},
    {"status": "pass", "expected": "x", "actual": " "}])
def test_invalid_review_result_never_passes(result):
    checks = run(report(), review_claim=lambda *args: result)
    assert next(c for c in checks if c["check_id"] == "claims-claim-0")["status"] == "unavailable"


def test_missing_callbacks_are_unavailable():
    checks = run(report(), review_claim=None, review_narrative=None)
    assert sum(c["status"] == "unavailable" for c in checks) == 2


def test_unresolved_finding_blocks_narrative_and_review():
    draft = report()
    draft["findings"] = [{"finding_id": "gap", "statement": "Mock limitation",
                           "audience": "final_report", "evidence_refs": [deepcopy(REF)]}]
    def missing(ref):
        raise FileNotFoundError("private source path")
    checks = run(draft, resolve_bytes=missing)
    assert next(c for c in checks if c["check_id"] == "claims-finding-1")["status"] == "unavailable"
    assert checks[-1]["status"] == "unavailable"
    assert "private source path" not in str(checks)


def test_empty_claims_and_unreferenced_final_finding_fail():
    draft = report()
    draft["claims"] = []
    draft["findings"] = [{"finding_id": "gap", "statement": "Mock limitation",
                           "audience": "final_report", "evidence_refs": []}]
    assert sum(c["status"] == "fail" for c in run(draft)) == 2


def test_terminal_list_and_missing_scope_are_rejected():
    draft = report()
    draft.update(outcome="execution_failure", orders=[{"quantity": 4}],
                 quantity_result_ref=deepcopy(REF), failure={"reason": "Mock timeout"})
    assert sum(c["status"] == "fail" for c in run(draft)) == 2


def test_callbacks_cannot_mutate_caller_report_or_other_review_input():
    draft = report()
    before = deepcopy(draft)
    def mutation(item, evidence):
        item["statement"] = "Mutated"
        return passed()
    run(draft, review_claim=mutation)
    assert draft == before


def test_guidance_truth_is_checked_by_trusted_narrative_reviewer():
    draft = report()
    draft.update(outcome="missing_inputs", customer_draft="No solution exists for any data.")
    def inspect(draft, evidence):
        return {"status": "fail", "expected": "Supported narrow capability/gap guidance",
                "actual": "Universal impossibility exceeds supplied-data evidence"}
    assert run(draft, review_narrative=inspect)[-1]["status"] == "fail"
