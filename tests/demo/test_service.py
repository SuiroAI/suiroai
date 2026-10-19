"""Exercise exact-input consent and stale-run boundaries in the demo service.

Use an injected backend to test authorization without requesting model work.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from suiroai.demo.service import DemoSession, ROLES, UploadedInput


@pytest.fixture
def uploads():
    """Supply small measured CSVs with each required role's actual field names.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    return [UploadedInput(f"{role}.csv", role,
            (",".join(sorted(fields)) + "\n" + ",".join("1" for _ in fields) + "\n").encode())
            for role, (_, fields) in ROLES.items()]


def test_review_never_runs_and_approval_is_exact_and_single_use(tmp_path, uploads):
    """Require the shown proposal digest and consume approval only once.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    calls = []

    def backend(*args):
        """Record one call and check its private consent callback.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        calls.append(args)
        assert args[6](args[3], args[2])
        return SimpleNamespace(status="blocked", message="Test boundary", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend)
    view = session.review("What should we replenish?", uploads)
    assert view["status"] == "awaiting_approval"
    assert calls == []
    session.approve_and_run("wrong-digest")
    assert calls == []
    session.approve_and_run(view["proposal_digest"])
    session.approve_and_run(view["proposal_digest"])
    assert len(calls) == 1
    assert session.view["status"] == "blocked"
    assert session.download() is None


@pytest.mark.parametrize("change", ["question", "bytes", "name", "role", "remove"])
def test_input_edits_revoke_displayed_proposal(tmp_path, uploads, change):
    """Bind consent to every question, file byte, name, and role edit.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    calls = []
    session = DemoSession(artifact_root=tmp_path, backend=lambda *args: calls.append(args))
    question = "What should we replenish?"
    digest = session.review(question, uploads)["proposal_digest"]
    changed = list(uploads)
    if change == "question":
        question += " For another store."
    elif change == "bytes":
        changed[0] = replace(changed[0], data=changed[0].data + b"\n")
    elif change == "name":
        changed[0] = replace(changed[0], name="different.csv")
    elif change == "role":
        changed[0] = replace(changed[0], role="inventory")
    else:
        changed.pop()
    session.invalidate(question, changed)
    session.approve_and_run(digest)
    assert session.view["status"] == "draft"
    assert "proposal_digest" not in session.view
    assert calls == []
    assert session.download() is None


def test_repeat_review_is_safe_and_can_be_approved(tmp_path, uploads):
    """Allow a repeated review without conflicting immutable artifact records.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    calls = []

    def backend(*args):
        """Return an honest blocked result for a valid newly reviewed task.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        calls.append(args)
        return SimpleNamespace(status="blocked", message="Test boundary", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend)
    session.review("What should we replenish?", uploads)
    view = session.review("What should we replenish?", uploads)
    assert view["status"] == "awaiting_approval"
    session.approve_and_run(view["proposal_digest"])
    assert len(calls) == 1


@pytest.mark.parametrize("raises", [False, True])
def test_revise_during_execution_revokes_consent_and_keeps_new_state(tmp_path, uploads, raises):
    """Keep a revoked backend result or exception from replacing revised state.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    def backend(*args):
        """Revoke the running task before returning or raising an old outcome.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        assert args[6](args[3], args[2])
        session.revise()
        assert not args[6](args[3], args[2])
        if raises:
            raise RuntimeError("Stale attempt failed")
        return SimpleNamespace(status="blocked", message="Stale result", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend)
    view = session.review("What should we replenish?", uploads)
    session.approve_and_run(view["proposal_digest"])
    assert session.view["status"] == "draft"
    assert "Stale" not in session.view["message"]
    assert session.download() is None


def test_backend_completed_claim_cannot_publish_unverified_html(tmp_path, uploads):
    """Refuse a backend success label and raw HTML without independent delivery.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = DemoSession(artifact_root=tmp_path, backend=lambda *args: SimpleNamespace(
        status="completed", message="Unverified claim", evidence_path=None,
        download_name="unverified.html", download_bytes=b"<html>unverified</html>"))
    view = session.review("What should we replenish?", uploads)
    session.approve_and_run(view["proposal_digest"])
    assert session.view["status"] == "blocked"
    assert session.download() is None


@pytest.mark.parametrize("raises", [False, True])
def test_new_review_during_run_survives_stale_outcome(tmp_path, uploads, raises):
    """Keep fresh consent review intact despite an older same-input attempt.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    fresh = {}

    def backend(*args):
        """Open a fresh proposal before completing an already revoked attempt.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        fresh.update(session.review("What should we replenish?", uploads))
        assert not args[6](args[3], args[2])
        if raises:
            raise RuntimeError("Old run failed after fresh review")
        return SimpleNamespace(status="blocked", message="Old outcome", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend)
    original = session.review("What should we replenish?", uploads)
    session.approve_and_run(original["proposal_digest"])
    assert session.view == fresh
    assert fresh["status"] == "awaiting_approval"
    assert fresh["proposal_digest"] != original["proposal_digest"]
    assert session.download() is None
