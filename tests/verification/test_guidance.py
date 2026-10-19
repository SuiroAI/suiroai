"""Preexecution checks use mock records only; no customer run is established.

Check current submission and proposal bindings, accessible source bytes,
and independent semantic review before missing-input guidance can proceed.

Requirement context for these component checks:
Check specific supported capability and minimum missing facts for the current
request, preserving the distinction between a blocked task and completed
restocking without fabricating quantities or silently replacing the objective.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from suiroai.contracts import input_digest, proposal_digest, record_ref
from suiroai.verification.guidance import check_capability_guidance


def snapshot():
    fixture = Path(__file__).resolve().parents[2] / "examples/contracts/v0.1.0/missing_inputs.json"
    submission, proposal = json.loads(fixture.read_text())["records"]
    return submission, proposal


def rebind(submission, proposal):
    submission["binding"]["input_digest"] = input_digest(submission)
    proposal["binding"].update(submission["binding"])
    proposal["submission_ref"] = record_ref(submission)
    proposal["binding"]["proposal_digest"] = proposal_digest(proposal)


def passed(*args):
    return {"status": "pass", "expected": "Mock exact gap guidance",
            "actual": "Mock missing file and next step agree with supplied snapshot"}


def run(submission, proposal, text="MOCK: Provide accessible sales and dictionary.", **kwargs):
    return check_capability_guidance(submission, proposal, text,
        resolve_bytes=kwargs.pop("resolve_bytes", lambda ref: b"mock,sales\n"),
        review=kwargs.pop("review", passed), verifier="mock-independent-reviewer", **kwargs)


def accessible_source(submission, proposal):
    file = submission["files"][0]
    data = b"mock,sales\n"
    file.update(access="accessible", sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data), access_reason=None)
    proposal["source_refs"] = [{"artifact_id": file["file_id"], "version": 1,
                                "sha256": file["sha256"], "provenance": "mock"}]
    rebind(submission, proposal)


def test_missing_input_snapshot_has_no_fabricated_run_and_can_be_reviewed():
    submission, proposal = snapshot()
    seen = []
    def inspect(text, supplied, proposed, evidence):
        seen.append((text, supplied, proposed, evidence))
        assert supplied["files"][0]["access"] == "inaccessible"
        assert evidence == {}
        return passed()
    checks = run(submission, proposal, review=inspect)
    assert all(check["status"] == "pass" for check in checks)
    assert seen
    assert all(check["evidence_refs"] == [record_ref(submission), record_ref(proposal)] for check in checks)
    assert "run_id" not in submission and "run_id" not in proposal


def test_accessible_source_is_hashed_and_given_to_reviewer():
    submission, proposal = snapshot()
    accessible_source(submission, proposal)
    def inspect(text, supplied, proposed, evidence):
        assert list(evidence.values()) == [b"mock,sales\n"]
        return passed()
    assert all(c["status"] == "pass" for c in run(submission, proposal, review=inspect))


def test_stale_input_and_proposal_digests_block():
    submission, proposal = snapshot()
    submission["original_request"] += " changed input"
    proposal["goal"] += " changed goal"
    checks = run(submission, proposal)
    assert next(c for c in checks if c["check_id"] == "guidance-binding")["status"] == "fail"
    assert checks[-1]["status"] == "unavailable"


@pytest.mark.parametrize("data", [b"changed", None])
def test_changed_or_nonbyte_source_blocks(data):
    submission, proposal = snapshot()
    accessible_source(submission, proposal)
    assert any(c["status"] == "unavailable" for c in
               run(submission, proposal, resolve_bytes=lambda ref: data))


def test_unavailable_source_is_not_read_or_pretended_accessible():
    submission, proposal = snapshot()
    proposal["source_refs"] = [{"artifact_id": submission["files"][0]["file_id"],
                                "version": 1, "sha256": "0" * 64, "provenance": "mock"}]
    rebind(submission, proposal)
    def forbidden(ref):
        raise AssertionError("Inaccessible source must not be read")
    checks = run(submission, proposal, resolve_bytes=forbidden)
    assert next(c for c in checks if c["check_id"] == "guidance-access")["status"] == "fail"


@pytest.mark.parametrize("review", [None, lambda *args: True,
    lambda *args: {"status": "pass", "expected": "x", "actual": ""}])
def test_missing_or_invalid_review_never_passes(review):
    assert run(*snapshot(), review=review)[-1]["status"] == "unavailable"


def test_semantic_reviewer_rejects_false_capability_and_silent_goal_change():
    def inspect(text, submission, proposal, evidence):
        assert "Choose a neural model" in text
        return {"status": "fail", "expected": "Minimum business facts and offered narrower option",
                "actual": "Statistical choice and unsupported universal impossibility replace approved goal"}
    assert run(*snapshot(), text="Choose a neural model; no solution exists.",
               review=inspect)[-1]["status"] == "fail"


def test_ready_proposal_and_fabricated_run_are_rejected():
    submission, proposal = snapshot()
    proposal.update(readiness="ready", run_id="invented-run")
    rebind(submission, proposal)
    checks = run(submission, proposal)
    assert next(c for c in checks if c["check_id"] == "guidance-preexecution")["status"] == "fail"
    assert next(c for c in checks if c["check_id"] == "guidance-gaps")["status"] == "fail"


def test_invalid_records_return_blocked_checks():
    checks = run({}, {})
    assert checks[0]["status"] == "fail"


def test_reviewer_cannot_mutate_snapshot():
    submission, proposal = snapshot()
    before = deepcopy((submission, proposal))
    def mutate(text, supplied, proposed, evidence):
        proposed["goal"] = "Changed"
        supplied["files"].clear()
        return passed()
    run(submission, proposal, review=mutate)
    assert (submission, proposal) == before
