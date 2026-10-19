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
    return [UploadedInput(name=f"{role}.csv", data=
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


@pytest.mark.parametrize("change", ["question", "bytes", "name", "remove"])
def test_input_edits_revoke_displayed_proposal(tmp_path, uploads, change):
    """Bind consent to every question, file byte, name, and removal edit.

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


def test_renamed_shuffled_uploads_are_identified_from_headers(tmp_path, uploads):
    """Infer source meaning from measured columns regardless of names or order.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    renamed = [replace(file, name=f"document-{index}.csv")
               for index, file in enumerate(reversed(uploads))]
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", renamed)
    assert view["status"] == "awaiting_approval"
    assert set(view["proposal_summary"]["inputs"]) == {file.name for file in renamed}
    assert session.download() is None


def test_role_hints_cannot_override_measured_headers(tmp_path, uploads):
    """Ignore legacy role hints when determining what uploaded data contains.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    misleading = [replace(file, role="sales") for file in uploads]
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", misleading)
    assert view["status"] == "awaiting_approval"
    assert session.download() is None


def test_reordering_unchanged_uploads_keeps_review_identity(tmp_path, uploads):
    """Keep identical measured input sets approved for review across reordering.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", uploads)
    session.invalidate("What should we replenish?", list(reversed(uploads)))
    assert session.view == view


@pytest.mark.parametrize("kind", ["unknown", "ambiguous", "duplicate"])
def test_unidentifiable_or_duplicate_uploads_require_guidance(tmp_path, uploads, kind):
    """Reject uncertain file identity rather than guessing a source to execute.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    files = list(uploads)
    if kind == "unknown":
        files.append(UploadedInput(name="unrelated.csv", data=b"Unrelated,Other\n1,2\n"))
        filename = "unrelated.csv"
    elif kind == "ambiguous":
        fields = sorted(ROLES["sales"][1] | ROLES["inventory"][1])
        files.append(UploadedInput(name="mixed.csv", data=(",".join(fields) + "\n").encode()))
        filename = "mixed.csv"
    else:
        files.append(replace(uploads[0], name="another-sales.csv"))
        filename = "another-sales.csv"
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "needs_inputs"
    guidance = " ".join(view["errors"]).lower()
    assert filename in guidance
    assert "proposal_digest" not in view
    if kind == "ambiguous":
        assert "sales" in guidance and "inventory" in guidance
    elif kind == "duplicate":
        assert "sales" in guidance
    else:
        assert "column" in guidance or "recogniz" in guidance or "identif" in guidance
    assert session.download() is None


def test_missing_source_is_guidance_after_review(tmp_path, uploads):
    """Request missing source data only after the user's generic upload review.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = DemoSession(artifact_root=tmp_path)
    session.invalidate("", [])
    assert session.view["status"] == "draft"
    assert "inputs changed" not in session.view["message"].lower()
    assert session.view["errors"] == []
    view = session.review("What should we replenish?", uploads[:-1])
    assert view["status"] == "needs_inputs"
    assert "policy" in " ".join(view["errors"]).lower()
    assert "proposal_digest" not in view


def test_dictionary_is_optional_without_fabricated_source_or_semantics(tmp_path, uploads):
    """Review four operational sources while retaining evidence-based investigation.

    Column names identify source structure; they do not prove quantity semantics.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    files = [file for file in uploads if file.name != "dictionary.csv"]
    captured = []

    def backend(*args):
        """Capture the exact approved four-source submission and investigation plan.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        captured.append((args[1], args[2]))
        return SimpleNamespace(status="blocked", message="Unverified semantics", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "awaiting_approval"
    assert len(view["proposal_summary"]["inputs"]) == 4
    assert set(view["proposal_summary"]["inputs"]) == {file.name for file in files}
    session.approve_and_run(view["proposal_digest"])
    submission, proposal = captured[0]
    assert len(submission["files"]) == len(proposal["source_refs"]) == 4
    assert all(file["source_role"] != "dictionary" for file in submission["files"])
    assert proposal["target_policy"]["status"] == "pending"
    interpretations = [item["statement"].lower() for item in proposal["assumptions"]]
    assert any("quantity" in statement and "investigat" in statement
               for statement in interpretations)
    assert session.download() is None


def test_optional_dictionary_is_retained_when_supplied(tmp_path, uploads):
    """Keep an optional measured dictionary as a fifth source when provided.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", uploads)
    assert view["status"] == "awaiting_approval"
    assert len(view["proposal_summary"]["inputs"]) == 5
    assert "dictionary.csv" in view["proposal_summary"]["inputs"]


def test_missing_policy_remains_required_without_dictionary(tmp_path, uploads):
    """Request actual missing ordering policy without demanding a dictionary.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    files = [file for file in uploads if file.name not in {"dictionary.csv", "policy.csv"}]
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "needs_inputs"
    guidance = " ".join(view["errors"]).lower()
    assert "policy" in guidance
    assert "dictionary" not in guidance
    assert "proposal_digest" not in view
