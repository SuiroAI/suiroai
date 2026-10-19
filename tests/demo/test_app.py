"""Check Streamlit consent controls independently of backend execution.

Exercise real widget reruns so approval cannot be inferred from page refreshes.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest


class FakeSession:
    """Expose a deterministic session for UI-only consent regression checks.

    Successful report bytes are explicitly test data, never a runtime fallback.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """

    def __init__(self):
        """Initialize isolated consent state and a count of execution requests.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        self.question = None
        self.runs = 0
        self.context = {"status": "found", "input_key": "test-context", "summary": "Test process supplied"}
        self.view = {"status": "missing", "errors": []}

    def invalidate(self, question, uploads):
        """Revoke the test proposal and result when the question changes.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        if question != self.question:
            self.question = question
            self.view = {"status": "missing", "errors": []}

    def context_for(self, question, uploads):
        """Return explicit test context without calling a real model."""
        return self.context

    def review(self, question, uploads, *, current_approach=None, continue_without=False):
        """Publish the exact test proposal without requesting execution.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        from suiroai.demo.service import current_process_request
        if self.context["status"] == "missing" and not current_approach and not continue_without:
            self.view = {"status": "awaiting_current_process", "errors": []}
            return self.view
        question = current_process_request(question, current_approach, continue_without)
        self.question = question
        self.view = {"status": "awaiting_approval", "proposal_digest": "exact-digest",
                     "proposal_summary": {
                         "question": question,
                         "inputs": ["sales.csv", "inventory.csv"],
                         "review_date": "2025-11-30",
                         "output": "Exact reviewed deliverable",
                         "understanding": "Exact reviewed interpretation",
                         "assumptions": ["A disclosed assumption", "An unresolved limitation"],
                         "execution": "Approval permits one bounded attempt, with no guaranteed result.",
                     }}

        return self.view

    def revise(self):
        """Revoke the unchanged test proposal upon an explicit revision.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        self.view = {"status": "missing", "errors": []}

    def approve_and_run(self, digest):
        """Require the rendered proposal identity before counting execution.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        assert digest == self.view["proposal_digest"] == "exact-digest"
        self.runs += 1
        self.view = {"status": "completed", "message": "Analysis complete.", "report_available": True}

    def download(self):
        """Return known test bytes only after the simulated completed result.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        assert self.view["status"] == "completed"
        return "restocking.csv", b"Product_ID,Store_ID,Order_Qty\nP1,S1,12\n"


@pytest.fixture
def app(monkeypatch):
    """Create an actual Streamlit page backed by a deterministic test service.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    import suiroai.demo.service as service

    monkeypatch.setattr(service, "DemoSession", FakeSession)
    app = AppTest.from_string("from suiroai.demo.app import run_app\nrun_app()").run()
    return app


def test_review_and_approval_require_explicit_actions(app):
    """Verify review, approval, refresh, and input-edit consent boundaries.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    assert not app.exception
    uploaders = app.get("file_uploader")
    assert len(uploaders) == 1
    assert uploaders[0].proto.multiple_files
    assert uploaders[0].label == "Upload your data"
    assert app.text_area(key="business_question").label == "What are you trying to solve for?"
    assert "Upload your data." in [element.value for element in app.markdown]
    assert len(app.get("download_button")) == 0
    session = app.session_state["demo_session"]
    app.text_area(key="business_question").input("What should we replenish?").run()
    app.button(key="review_task").click().run()
    assert session.runs == 0
    assert len(app.json) == 0
    rendered = [element.value for element in app.markdown]
    proposal = session.view["proposal_summary"]
    for value in proposal.values():
        for item in value if isinstance(value, list) else [value]:
            assert item in rendered or f"• {item}" in rendered
    for label in ("Your goal", "Files to use", "Review date", "What you'll receive",
                  "How the data will be understood", "Assumptions to review", "When you approve"):
        assert f"**{label}**" in rendered
    assert len(app.expander) == 0
    assert not any("exact-digest" in item.value or "Proposal ID" in item.value
                   for item in list(app.caption) + list(app.markdown))
    app.run()
    assert session.runs == 0
    app.button(key="approve_and_run").click().run()
    assert not app.exception
    assert session.runs == 1
    assert len(app.get("download_button")) == 1
    app.run()
    assert session.runs == 1
    app.text_area(key="business_question").input("A different question").run()
    assert session.view["status"] == "missing"
    assert len(app.get("download_button")) == 0
    assert not any(button.key == "approve_and_run" for button in app.button)


def test_revise_revokes_proposal_without_running(app):
    """Check that revising an unchanged proposal still revokes approval access.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    app.text_area(key="business_question").input("What should we replenish?").run()
    app.button(key="review_task").click().run()
    session = app.session_state["demo_session"]
    app.button(key="revise_task").click().run()
    assert not app.exception
    assert session.runs == 0
    assert session.view["status"] == "missing"
    assert not any(button.key == "approve_and_run" for button in app.button)


@pytest.mark.parametrize("status,element", [("blocked", "warning"), ("execution_failed", "error"),
                                          ("validation_failed", "error"), ("needs_inputs", "info"),
                                          ("unsupported_task", "warning"), ("investigation_completed", "info")])
def test_states_without_report_never_offer_downloads(app, status, element):
    """Keep blocked, failed, and missing-input outcomes visibly distinct.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    app.session_state["demo_session"].view = {"status": status, "message": "Specific outcome"}
    app.run()
    assert getattr(app, element)[0].value == "Specific outcome"
    assert len(app.get("download_button")) == 0


@pytest.mark.parametrize("status", ["investigation_completed", "analysis_completed"])
def test_investigation_preserves_scientific_methods_and_limits(app, status):
    """Display actual data treatment and limitations without claiming verification.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    note = "Dates with no transactions were evaluated under two treatments; the report quantifies sensitivity and limits."
    app.session_state["demo_session"].view = {
        "status": status, "message": "Data investigation response",
        "investigation_text": note, "report_available": False,
        "technical_details": "Native execution receipt retained locally.",
    }
    app.run()
    assert not app.exception
    assert app.subheader[0].value == "What we found"
    assert note in [element.value for element in app.markdown]
    assert len(app.json) == len(app.success) == len(app.get("download_button")) == 0
    assert len(app.expander) == 0
    assert not any("Add your answer" in element.value for element in app.markdown)
    assert not any(button.key == "approve_and_run" for button in app.button)
    assert app.session_state["demo_session"].runs == 0


@pytest.mark.parametrize("verification", [None, False, True])
def test_real_generated_output_is_downloadable_with_neutral_label(app, verification, monkeypatch):
    """Offer exact CSV bytes with the correct MIME and readable analysis in the app.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.view = {"status": "analysis_completed", "message": "Data produced an analysis output.",
                    "report_available": True, "report_verified": verification}
    data = b"Product_ID,Store_ID,Order_Qty\nP1,S1,12\n"
    session.download = lambda: ("restocking.csv", data)
    import streamlit as st
    original_download = st.download_button
    calls = []

    def capture_download(*args, **kwargs):
        """Observe exact bytes and MIME while retaining the actual Streamlit widget.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        calls.append(kwargs)
        return original_download(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app.run()
    assert not app.exception
    assert len(app.success) == 0
    downloads = app.get("download_button")
    assert len(downloads) == 1
    assert downloads[0].label == "Download restocking list (CSV)"
    assert downloads[0].key == "download_restocking_list"
    assert calls[0]["data"] == data
    assert calls[0]["file_name"] == "restocking.csv"
    assert calls[0]["mime"] == "text/csv"
    product_copy = " ".join(item.value for collection in (app.caption, app.markdown, app.info, app.warning)
                            for item in collection).lower()
    assert "verif" not in product_copy
    assert "Questions for you" not in [item.value for item in app.subheader]
    assert not any("Add your answer" in item.value for item in app.markdown)
    app.run()
    assert session.runs == 0


def test_report_availability_without_service_bytes_does_not_create_download(app):
    """Refuse to fabricate bytes when generated-output availability is inconsistent.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.view = {"status": "analysis_completed", "report_available": True, "report_verified": False}
    session.download = lambda: None
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == len(app.success) == 0


def test_html_report_is_not_offered_as_restocking_data(app):
    """Keep an old HTML report out of the dedicated restocking-file download.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.view = {"status": "analysis_completed", "report_available": True, "download_mime": "text/html"}
    session.download = lambda: ("old-report.html", b"<html>old report</html>")
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == 0


@pytest.mark.parametrize("html_available", [True, False])
def test_csv_download_and_html_open_with_plain_response(app, monkeypatch, html_available):
    """Keep the restocking CSV primary while optionally offering the actual demo HTML.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    import streamlit as st

    session = app.session_state["demo_session"]
    response = "Order 12 units for this store. The selected method accounts for missing dates and supplier lead time."
    csv_data = b"Product_ID,Store_ID,Order_Qty\nP1,S1,12\n"
    html_data = b"<!doctype html><html><body>Analysis and decisions</body></html>"
    session.view = {"status": "analysis_completed", "report_available": True,
                    "download_mime": "text/csv", "html_report_available": True,
                    "html_download_mime": "text/html", "investigation_text": response}
    session.download = lambda: ("restocking.csv", csv_data)
    session.download_html = lambda: ("demo-report.html", html_data) if html_available else None
    calls = []
    html_calls = []
    from suiroai.demo import app as demo_app
    monkeypatch.setattr(demo_app, "_html_report_url", lambda data: html_calls.append(data) or "/media/report.html")
    original_download = st.download_button

    def capture_download(*args, **kwargs):
        """Observe the exact CSV payload without replacing its real widget.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        calls.append(kwargs)
        return original_download(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app.run()
    assert not app.exception
    buttons = app.get("download_button")
    expected = ["Download restocking list (CSV)"]
    assert [button.label for button in buttons] == expected
    assert calls[0]["data"] == csv_data and calls[0]["mime"] == "text/csv"
    if html_available:
        assert html_calls == [html_data]
        assert app.get("link_button")[0].label == "View restocking list"
        assert app.get("link_button")[0].proto.url == "/media/report.html"
    else:
        assert len(app.get("link_button")) == 0
    assert response in [item.value for item in app.markdown]
    assert len(app.json) == 0
    app.run()
    assert session.runs == 0


def test_html_media_is_inline_and_removed_when_no_longer_referenced(monkeypatch):
    """Serve exact HTML without attachment headers and expire stale session media.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    from types import SimpleNamespace
    from streamlit import runtime
    from streamlit.runtime.media_file_manager import MediaFileManager
    from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
    from streamlit.runtime.media_file_storage import MediaFileKind, MediaFileStorageError
    from suiroai.demo.app import _html_report_url

    storage = MemoryMediaFileStorage("/media")
    manager = MediaFileManager(storage)
    monkeypatch.setattr(runtime, "get_instance", lambda: SimpleNamespace(media_file_mgr=manager))
    data = b"<!doctype html><html><body>Actual report</body></html>"
    url = _html_report_url(data)
    file = storage.get_file(url.rsplit("/", 1)[-1])
    assert file.content == data and file.mimetype == "text/html"
    assert file.kind == MediaFileKind.MEDIA
    manager.clear_session_refs()
    manager.remove_orphaned_files()
    with pytest.raises(MediaFileStorageError):
        storage.get_file(url.rsplit("/", 1)[-1])



def test_missing_current_approach_can_be_answered_and_edits_revoke_approval(app):
    """Ask only for missing context and bind typed current steps to consent.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.context = {"status": "missing", "input_key": "test-context"}
    app.text_area(key="business_question").input("What should we replenish?").run()
    assert app.text_area(key="current_approach").label == "How do you do this now?"
    app.button(key="review_task").click().run()
    assert not any(button.key == "approve_and_run" for button in app.button)
    app.text_area(key="current_approach").input("We order last week's sales every Monday.").run()
    app.button(key="review_task").click().run()
    assert "We order last week's sales every Monday." in session.view["proposal_summary"]["question"]
    app.text_area(key="current_approach").input("We top up to ten units.").run()
    assert not any(button.key == "approve_and_run" for button in app.button)
    assert session.runs == 0


def test_detected_current_approach_does_not_ask_user_to_identify_or_retype_it(app):
    """Review detected context automatically with no manual source selector.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    app.text_area(key="business_question").input("We order ten units weekly. What should we replenish?").run()
    assert not app.radio
    assert not any(area.key == "current_approach" for area in app.text_area)
    app.button(key="review_task").click().run()
    assert any(button.key == "approve_and_run" for button in app.button)


def test_user_can_continue_without_current_approach(app):
    """An explicit continue action skips the missing method without inventing one.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.context = {"status": "missing", "input_key": "test-context"}
    app.text_area(key="business_question").input("What should we replenish?").run()
    app.button(key="continue_without_current_approach").click().run()
    assert not app.exception
    assert "continue without a current approach" in session.view["proposal_summary"]["question"]
    assert any(button.key == "approve_and_run" for button in app.button)
    assert session.runs == 0


def test_answer_and_continuation_do_not_carry_to_changed_inputs(app):
    """A new question/file snapshot must not silently inherit an old process answer.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    session = app.session_state["demo_session"]
    session.context = {"status": "missing", "input_key": "old-inputs"}
    app.text_area(key="business_question").input("What should we replenish?").run()
    app.text_area(key="current_approach").input("We order ten each week.").run()
    app.button(key="review_task").click().run()
    session.context = {"status": "missing", "input_key": "changed-inputs"}
    app.run()
    assert app.text_area(key="current_approach").value == ""
    assert not any(button.key == "approve_and_run" for button in app.button)
