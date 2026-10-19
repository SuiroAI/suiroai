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
        self.view = {"status": "missing", "errors": []}

    def invalidate(self, question, uploads):
        """Revoke the test proposal and result when the question changes.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        if question != self.question:
            self.question = question
            self.view = {"status": "missing", "errors": []}

    def review(self, question, uploads):
        """Publish the exact test proposal without requesting execution.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
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
        self.view = {"status": "completed", "message": "Verified test completion"}

    def download(self):
        """Return known test bytes only after the simulated verified result.

        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        assert self.view["status"] == "completed"
        return "verified.html", b"<html>verified test bytes</html>"


@pytest.fixture
def app(monkeypatch):
    """Create an actual Streamlit page backed by a deterministic test service.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    import suiroai.demo.service as service

    monkeypatch.setattr(service, "DemoSession", FakeSession)
    return AppTest.from_string("from suiroai.demo.app import run_app\nrun_app()").run()


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
    assert app.expander[0].label == "Technical details"
    assert app.expander[0].proto.expanded is False
    assert "exact-digest" in app.expander[0].caption[0].value
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
    app.button(key="review_task").click().run()
    session = app.session_state["demo_session"]
    app.button(key="revise_task").click().run()
    assert not app.exception
    assert session.runs == 0
    assert session.view["status"] == "missing"
    assert not any(button.key == "approve_and_run" for button in app.button)


@pytest.mark.parametrize("status,element", [("blocked", "warning"), ("execution_failed", "error"),
                                          ("validation_failed", "error"), ("needs_inputs", "info"),
                                          ("needs_material_facts", "warning"), ("unsupported_task", "warning")])
def test_unverified_states_never_offer_downloads(app, status, element):
    """Keep blocked, failed, and missing-input outcomes visibly distinct.

    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    app.session_state["demo_session"].view = {"status": status, "message": "Specific outcome"}
    app.run()
    assert getattr(app, element)[0].value == "Specific outcome"
    assert len(app.get("download_button")) == 0
