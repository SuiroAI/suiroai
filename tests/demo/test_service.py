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


def test_unknown_csv_reaches_data_without_an_application_semantics_gate(tmp_path, uploads):
    """Retain unfamiliar data for Data to interpret after approval.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    files = list(uploads) + [UploadedInput(name="extra.csv", data=b"Unrelated,Other\n1,2\n")]
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "awaiting_approval"
    assert "extra.csv" in view["proposal_summary"]["inputs"]


def test_only_dated_transactions_are_required_for_confidential_partition(tmp_path, uploads):
    """Let Data determine analytical input sufficiency after the release boundary.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    sales = [file for file in uploads if file.name == "sales.csv"]
    view = DemoSession(artifact_root=tmp_path).review("What should we replenish?", sales)
    assert view["status"] == "awaiting_approval"
    summary = str(view["proposal_summary"])
    assert "data dictionary" not in summary.lower()
    assert "stop before analysis" not in summary.lower()


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


def test_missing_policy_is_left_for_data_to_investigate(tmp_path, uploads):
    """Pass partial operational data rather than demanding policy before Data.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    files = [file for file in uploads if file.name not in {"dictionary.csv", "policy.csv"}]
    session = DemoSession(artifact_root=tmp_path)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "awaiting_approval"


def test_actual_investigation_result_is_visible_but_not_verified(tmp_path, uploads):
    """Expose native findings without promoting them into verified delivery.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    def backend(*args):
        assert args[6](args[3], args[2])
        assert any(a["assumption_id"] == "development_investigation" for a in args[2]["assumptions"])
        return SimpleNamespace(status="investigation_completed", message="Data finished; unverified.",
            evidence_path="/test/attempt.json", investigation_text="Findings and questions",
            investigation_path="/test/investigation.md", native_outcome="completed")
    session = DemoSession(artifact_root=tmp_path, backend=backend)
    proposal = session.review("What should we replenish?", uploads)
    view = session.approve_and_run(proposal["proposal_digest"])
    assert view["status"] == "investigation_completed"
    assert view["investigation_text"] == "Findings and questions"
    assert view["native_outcome"] == "completed"
    assert not view["verified_report_available"]
    assert session.download() is None


def test_development_report_download_retains_unverified_provenance_and_revokes(tmp_path, uploads):
    """Expose approved development output and remove it on any new input.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    def backend(*args):
        ref = args[0].put_bytes("TEST-development-report", 1, "derived", b"Product_ID,Store_ID,Order_Qty\nTEST-P,TEST-S,5\n")
        return SimpleNamespace(status="analysis_completed", message="Data output; unverified.",
            evidence_path=None, report_ref=ref, report_path="/test/restocking.csv",
            download_name="restocking.csv", download_bytes=args[0].read_bytes(ref))
    session = DemoSession(artifact_root=tmp_path, backend=backend)
    proposal = session.review("What should we replenish?", uploads)
    view = session.approve_and_run(proposal["proposal_digest"])
    assert view["report_available"]
    assert view["download_mime"] == "text/csv"
    assert not view["report_verified"]
    assert not view["verified_report_available"]
    assert session.download() == ("restocking.csv", b"Product_ID,Store_ID,Order_Qty\nTEST-P,TEST-S,5\n")
    session.invalidate("Replenish another store", uploads)
    assert session.download() is None


def test_split_and_overlapping_sources_are_left_for_data_to_reconcile(tmp_path, uploads):
    """Keep duplicate role files under unique measured file identities.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    captured = []
    def backend(*args):
        captured.append(args[1])
        return SimpleNamespace(status="blocked", message="TEST boundary", evidence_path=None)
    files = list(uploads) + [replace(uploads[0], name="sales-part-two.csv")]
    session = DemoSession(artifact_root=tmp_path, backend=backend)
    view = session.review("What should we replenish?", files)
    assert view["status"] == "awaiting_approval"
    session.approve_and_run(view["proposal_digest"])
    records = captured[0]["files"]
    assert len(records) == len(files)
    assert len({file["file_id"] for file in records}) == len(files)
    assert sum(file["source_role"] == "transactions" for file in records) == 2


def test_approval_authorizes_autonomous_treatment_and_report_without_followup(tmp_path, uploads):
    """Describe Data's supported result and limitations without a question gate.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    view = DemoSession(artifact_root=tmp_path).review("What should we replenish?", uploads)
    summary = view["proposal_summary"]
    assert "restocking csv" in summary["output"].lower()
    assert "shown in the app" in summary["output"].lower()
    assert "sensitivities" in summary["output"].lower()
    assert "No follow-up answers are required" in summary["understanding"]
    assert "ask only" not in str(summary).lower()
    assert "follow-up questions if" not in str(summary).lower()


def test_inbound_order_dates_do_not_route_receipts_as_sales(tmp_path, uploads):
    """Retain planned arrivals when an inbound ledger includes placement dates.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    fields = sorted(ROLES["receipts"][1] | {"Order_Date"})
    inbound = UploadedInput(name="incoming.csv", data=(",".join(fields) + "\n").encode())
    captured = []
    def backend(*args):
        captured.append(args[1])
        return SimpleNamespace(status="blocked", message="TEST boundary", evidence_path=None)
    files = [file for file in uploads if file.name != "receipts.csv"] + [inbound]
    session = DemoSession(artifact_root=tmp_path, backend=backend)
    view = session.review("What should we replenish?", files)
    session.approve_and_run(view["proposal_digest"])
    source = next(file for file in captured[0]["files"] if file["original_name"] == "incoming.csv")
    assert source["source_role"] == "inbound_ledger"


def test_proposal_uses_neutral_report_copy_and_keeps_scientific_assumptions(tmp_path, uploads):
    """Present Data's deliverable without blanket draft or verification labels.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    summary = DemoSession(artifact_root=tmp_path).review("What should we replenish?", uploads)["proposal_summary"]
    copy = str(summary).lower()
    for phrase in ("unverified", "independently verified", "final model selection", "development report", "draft"):
        assert phrase not in copy
    assert "sensitivities" in copy
    assert "november 30, 2025" in copy


@pytest.mark.parametrize("revoke", ["edit", "revise", "review"])
def test_csv_and_html_downloads_share_exact_bytes_and_revocation(tmp_path, uploads, revoke):
    """Bind both output artifacts to the same current browser approval.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    def backend(*args):
        csv_data, html_data = b"Product_ID,Store_ID,Order_Qty\nP,S,5\n", b"<html>TEST demo</html>"
        csv_ref = args[0].put_bytes("TEST-csv", 1, "derived", csv_data)
        html_ref = args[0].put_bytes("TEST-html", 1, "derived", html_data)
        return SimpleNamespace(status="analysis_completed", message="Analysis complete.", evidence_path=None,
            report_ref=csv_ref, download_name="restocking.csv", download_bytes=csv_data,
            html_report_ref=html_ref, html_download_name="report.html", html_download_bytes=html_data)
    session = DemoSession(artifact_root=tmp_path, backend=backend)
    proposal = session.review("What should we replenish?", uploads)
    view = session.approve_and_run(proposal["proposal_digest"])
    assert view["report_available"] and view["html_report_available"]
    assert session.download() == ("restocking.csv", b"Product_ID,Store_ID,Order_Qty\nP,S,5\n")
    assert session.download_html() == ("report.html", b"<html>TEST demo</html>")
    if revoke == "edit":
        session.invalidate("Replenish another store", uploads)
    elif revoke == "revise":
        session.revise()
    else:
        session.review("What should we replenish?", uploads)
    assert session.download() is None
    assert session.download_html() is None
