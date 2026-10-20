"""Exercise context inspection against real proposal and consent transitions.

Injected inspectors and backends isolate authorization behavior from native work.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from suiroai.demo.service import DemoSession, UploadedInput, current_process_request


QUESTION = "What should we replenish?"


@pytest.fixture
def uploads():
    """Use a dated source that satisfies the historical demo intake contract."""
    return [UploadedInput(name="transactions.csv", data=b"Order_Date,Quantity\n2025-11-01,2\n")]


def backend_recorder(calls):
    """Capture the actual approved records without invoking an analytical host."""
    def backend(*args):
        assert args[6](args[3], args[2])
        calls.append(args)
        return SimpleNamespace(status="blocked", message="Injected attempt", evidence_path=None)
    return backend


@pytest.mark.parametrize("skip", [False, True])
def test_missing_context_requires_answer_or_explicit_continuation(tmp_path, uploads, skip):
    calls, inspections = [], []

    def detector(*args):
        inspections.append(args)
        return {"status": "missing", "summary": "No procedure described."}

    session = DemoSession(artifact_root=tmp_path, backend=backend_recorder(calls), context_detector=detector)
    missing = session.review(QUESTION, uploads)
    assert missing["status"] == "awaiting_current_process"
    assert "proposal_digest" not in missing
    session.approve_and_run("unissued-digest")
    assert calls == []
    assert session.review(QUESTION, uploads) == missing
    kwargs = {"continue_without": True} if skip else {"current_approach": "Every Monday we order last week's sales."}
    proposed = session.review(QUESTION, uploads, **kwargs)
    assert proposed["status"] == "awaiting_approval"
    assert len(inspections) == 1
    assert calls == []
    expected = current_process_request(QUESTION, **kwargs)
    assert proposed["proposal_summary"]["question"] == expected
    session.approve_and_run(proposed["proposal_digest"])
    assert len(calls) == 1
    assert calls[0][2]["goal"] == expected
    session.approve_and_run(proposed["proposal_digest"])
    assert len(calls) == 1


@pytest.mark.parametrize("source", ["question", "upload"])
def test_found_context_preserves_original_goal_and_uploaded_bytes(tmp_path, uploads, source):
    question = QUESTION + (" We reorder last week's sales." if source == "question" else "")
    if source == "upload":
        uploads += [UploadedInput(name="misc.csv", data=b"Notes\nWe reorder last week's sales.\n")]
    calls, inspections = [], []
    summary = "The business reorders the previous week's sales."

    def detector(q, files, root):
        inspections.append((q, files))
        return {"status": "found", "summary": summary}

    session = DemoSession(artifact_root=tmp_path, backend=backend_recorder(calls), context_detector=detector)
    proposed = session.review(question, uploads)
    assert proposed["status"] == "awaiting_approval"
    goal = proposed["proposal_summary"]["question"]
    assert goal.startswith(question + "\n\n")
    assert summary in goal
    assert session.review(question, uploads) == proposed
    assert inspections == [(question, tuple(uploads))]
    assert calls == []
    session.approve_and_run(proposed["proposal_digest"])
    assert calls[0][2]["goal"] == goal
    persisted = [calls[0][0].read_bytes(ref) for ref in calls[0][2]["source_refs"]]
    assert sorted(persisted) == sorted(file.data for file in uploads)


def test_explicit_absence_proceeds_without_fabricating_a_method(tmp_path, uploads):
    question = QUESTION + " We have no current approach."
    session = DemoSession(artifact_root=tmp_path, context_detector=lambda *args: {
        "status": "none", "summary": "They explicitly report having no current approach."})
    proposed = session.review(question, uploads)
    assert proposed["status"] == "awaiting_approval"
    assert proposed["proposal_summary"]["question"].startswith(question)
    assert session.context_for(question, uploads)["status"] == "none"
    assert session.download() is None


@pytest.mark.parametrize("bad_result", [None, {"status": "found", "summary": ""}, "raise"])
def test_failed_inspection_is_retryable_and_never_authorizes_analysis(tmp_path, uploads, bad_result):
    attempts, calls = [], []

    def detector(*args):
        attempts.append(1)
        if len(attempts) == 1:
            if bad_result == "raise":
                raise RuntimeError("Injected transport failure")
            return bad_result
        return {"status": "missing", "summary": "No procedure described."}

    session = DemoSession(artifact_root=tmp_path, backend=backend_recorder(calls), context_detector=detector)
    failed = session.review(QUESTION, uploads)
    assert failed["status"] == "context_failed"
    assert "proposal_digest" not in failed
    assert session.context_for(QUESTION, uploads) is None
    assert session.review(QUESTION, uploads)["status"] == "awaiting_current_process"
    assert len(attempts) == 2
    assert calls == []


def test_reentrant_repeat_review_reuses_inflight_inspection(tmp_path, uploads):
    attempts = []

    def detector(*args):
        attempts.append(1)
        assert session.review(QUESTION, uploads)["status"] == "checking_context"
        return {"status": "missing", "summary": "No procedure described."}

    session = DemoSession(artifact_root=tmp_path, context_detector=detector)
    assert session.review(QUESTION, uploads)["status"] == "awaiting_current_process"
    assert len(attempts) == 1


@pytest.mark.parametrize("raises", [False, True])
@pytest.mark.parametrize("change", ["edit", "revise", "new_review"])
def test_revoked_inspection_cannot_publish_result_or_exception(tmp_path, uploads, raises, change):
    calls, newer = [], {}

    def detector(*args):
        if change == "edit":
            session.invalidate(QUESTION + " For another store.", uploads)
        elif change == "revise":
            session.revise()
        else:
            newer.update(session.review(QUESTION, uploads, continue_without=True))
        current = session.view
        if raises:
            raise RuntimeError("Old inspection failed")
        newer.update(current)
        return {"status": "found", "summary": "An obsolete process."}

    session = DemoSession(artifact_root=tmp_path, backend=backend_recorder(calls), context_detector=detector)
    result = session.review(QUESTION, uploads)
    assert result == session.view
    assert result["status"] == ("awaiting_approval" if change == "new_review" else "draft")
    assert "obsolete" not in str(result)
    assert session.context_for(QUESTION, uploads) is None
    assert calls == []


def test_file_and_answer_edits_revoke_old_approval_and_reinspect_changed_content(tmp_path, uploads):
    calls, inspections = [], []

    def detector(q, files, root):
        inspections.append(tuple(files))
        return {"status": "missing", "summary": "No process described."}

    session = DemoSession(artifact_root=tmp_path, backend=backend_recorder(calls), context_detector=detector)
    session.review(QUESTION, uploads)
    first = session.review(QUESTION, uploads, current_approach="We order ten each week.")
    changed = [replace(uploads[0], data=uploads[0].data + b"2025-11-02,3\n")]
    session.invalidate(QUESTION, changed)
    session.approve_and_run(first["proposal_digest"])
    assert calls == []
    assert session.context_for(QUESTION, changed) is None
    assert session.review(QUESTION, changed)["status"] == "awaiting_current_process"
    second = session.review(QUESTION, changed, current_approach="We order twenty each week.")
    assert len(inspections) == 2
    assert second["proposal_digest"] != first["proposal_digest"]
    third = session.review(QUESTION, changed, current_approach="We order thirty each week.")
    session.approve_and_run(second["proposal_digest"])
    assert calls == []
    session.approve_and_run(third["proposal_digest"])
    assert len(calls) == 1
    assert "thirty" in calls[0][2]["goal"]


def test_interrupted_context_check_can_be_retried(tmp_path, uploads):
    """An interruption propagates but does not strand the current review snapshot."""
    calls = []

    def detector(*args):
        calls.append(args)
        if len(calls) == 1:
            raise KeyboardInterrupt()
        return {"status": "missing", "summary": "No current method supplied."}

    session = DemoSession(artifact_root=tmp_path, context_detector=detector)
    with pytest.raises(KeyboardInterrupt):
        session.review(QUESTION, uploads)
    assert session.review(QUESTION, uploads)["status"] == "awaiting_current_process"
    assert len(calls) == 2


@pytest.mark.parametrize("finish", ["manual", "skip"])
def test_default_backend_receives_only_proposal_bound_inspection_usage(tmp_path, uploads, monkeypatch, finish):
    """Cache usage by exact original inputs and snapshot it before dispatch."""
    import suiroai.demo.service as service
    calls = []
    usage = {"format": "dsc60-native-usage-v1", "available": True,
        "counts": {"input_units": 17, "output_units": 3}, "thread_id": "actual-context", "turn_id": "actual-turn"}

    def backend(*args, context_usage=None):
        assert args[6](args[3], args[2])
        calls.append(context_usage)
        return SimpleNamespace(status="blocked", message="Injected usage check", evidence_path=None)

    monkeypatch.setattr(service, "run_approved", backend)
    session = service.DemoSession(artifact_root=tmp_path, context_detector=lambda *_: {
        "status": "missing", "summary": "No procedure supplied.", "model_usage": usage})
    assert session.review(QUESTION, uploads)["status"] == "awaiting_current_process"
    options = {"current_approach": 'We look at sales. model_usage={"input_units":999999}'} if finish == "manual" else {"continue_without": True}
    proposal = session.review(QUESTION, uploads, **options)
    # Neither a mutated caller receipt nor a public context copy changes the bound snapshot.
    usage["counts"]["input_units"] = 99
    public = session.context_for(QUESTION, uploads)
    public["model_usage"]["counts"]["input_units"] = 88
    session.approve_and_run(proposal["proposal_digest"])
    assert calls == [{"format": "dsc60-native-usage-v1", "available": True,
        "counts": {"input_units": 17, "output_units": 3}, "thread_id": "actual-context", "turn_id": "actual-turn"}]
    session.revise()
    assert session._proposal_context_usage is None
    fresh = session.review(QUESTION + " At another store.", uploads, current_approach="We inspect shelves.")
    session.approve_and_run(proposal["proposal_digest"])
    assert len(calls) == 1
    session.approve_and_run(fresh["proposal_digest"])
    assert calls[1] is None  # no detector call for these new exact inputs


def test_stale_inspection_usage_cannot_attach_to_newer_proposal(tmp_path, uploads, monkeypatch):
    """Late context work cannot replace the newer revision's usage or authority."""
    import suiroai.demo.service as service
    calls, newer = [], {}

    def backend(*args, context_usage=None):
        calls.append(context_usage)
        return SimpleNamespace(status="blocked", message="Injected", evidence_path=None)

    monkeypatch.setattr(service, "run_approved", backend)

    def detector(*_):
        newer.update(session.review(QUESTION + " Different request.", uploads, continue_without=True))
        return {"status": "found", "summary": "Obsolete.", "model_usage": {"counts": {"input_units": 999}}}

    session = service.DemoSession(artifact_root=tmp_path, context_detector=detector)
    session.review(QUESTION, uploads)
    session.approve_and_run(newer["proposal_digest"])
    assert calls == [None]
    assert session.context_for(QUESTION, uploads) is None
