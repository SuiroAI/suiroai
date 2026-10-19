"""Present the local, consent-gated retail analysis demo in Streamlit.

Keep execution and verified downloads behind the session service so browser
reruns cannot authorize work or reuse a result after an input edit.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st


UPLOAD_ROLES = (
    ("sales", "Sales"),
    ("dictionary", "Data dictionary"),
    ("inventory", "Inventory"),
    ("receipts", "Receipts"),
    ("policy", "Replenishment policy"),
)


def _show_proposal(view: dict) -> None:
    """Show the exact service proposal that the approval digest identifies.

    Display structured content without rewriting any proposed scope or terms.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    st.subheader("Review the proposed task")
    proposal = view.get("proposal_summary")
    if isinstance(proposal, str):
        st.text(proposal)
    else:
        st.json(proposal)
    st.caption(f"Proposal ID: {view['proposal_digest']}")


def _show_outcome(session: object, view: dict) -> None:
    """Render distinct outcomes and offer only the service's verified HTML.

    Never build a report download from an intermediate artifact or UI text.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    status = view.get("status", "missing")
    message = view.get("message") or ""
    if status in {"draft", "missing", "missing_inputs", "needs_inputs"}:
        st.info(message or "Add your business question and required source files, then select Review task.")
    elif status in {"blocked", "unsupported_task", "needs_material_facts"}:
        st.warning(message or "The task is blocked. Review the required changes below.")
    elif status in {"failure", "failed", "execution_failed", "validation_failed"}:
        st.error(message or "The run failed. No verified report is available.")
    elif status == "running":
        st.info(message or "Analysis is running.")
    elif status in {"success", "completed"}:
        result = session.download()
        if result is None:
            st.error("The run has no verified report available for download.")
        else:
            name, data = result
            st.success(message or "Analysis completed and the report passed verification.")
            st.download_button("Download verified HTML report", data=data, file_name=name,
                               mime="text/html", key="download_verified_report")
    for error in view.get("errors", []):
        st.write(error)


def run_app(session_factory: Callable | None = None) -> None:
    """Run one page whose actions bind approval to the current exact inputs.

    The injected factory supports UI checks without executing the real backend.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    from suiroai.demo.service import DemoSession, UploadedInput

    st.set_page_config(page_title="SuiroAI local demo", page_icon="📊")
    st.title("SuiroAI local demo")
    st.caption("Development build: intake and runtime checks work; verified report generation is not yet connected.")
    st.write("Upload your retail data, review the proposed task, then approve the analysis.")
    st.caption("Changing the question or a file clears the previous approval and result.")
    if "demo_session" not in st.session_state:
        st.session_state.demo_session = (session_factory or DemoSession)()
    session = st.session_state.demo_session

    question = st.text_area("Business question", key="business_question",
                            placeholder="What should we replenish, and why?")
    uploads = []
    for role, label in UPLOAD_ROLES:
        uploaded = st.file_uploader(label, type=["csv"], key=f"upload_{role}")
        if uploaded is not None:
            uploads.append(UploadedInput(name=uploaded.name, role=role, data=uploaded.getvalue()))
    session.invalidate(question, uploads)

    if st.button("Review task", key="review_task"):
        session.review(question, uploads)

    view = session.view
    if view.get("proposal_digest") and view.get("status") in {"proposal", "awaiting_approval", "review"}:
        _show_proposal(view)
        revise, approve = st.columns(2)
        if revise.button("Revise", key="revise_task"):
            session.revise()
            st.rerun()
        if approve.button("Approve and run", key="approve_and_run"):
            with st.spinner("Analysis is running…"):
                session.approve_and_run(view["proposal_digest"])
            st.rerun()
    _show_outcome(session, view)


if __name__ == "__main__":
    run_app()
