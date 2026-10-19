"""Present the local, consent-gated retail analysis demo in Streamlit.

Keep execution and output downloads behind the session service so browser
reruns cannot authorize work or reuse a result after an input edit.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st


def _show_proposal(view: dict) -> None:
    """Show the exact service proposal that the approval digest identifies.

    Present labelled prose without rewriting any proposed scope or terms.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    st.subheader("Review the proposed task")
    proposal = view.get("proposal_summary")
    if isinstance(proposal, str):
        st.write(proposal)
    else:
        for field, label in (("question", "Your goal"), ("inputs", "Files to use"),
                             ("review_date", "Review date"), ("output", "What you'll receive"),
                             ("understanding", "How the data will be understood"),
                             ("assumptions", "Assumptions to review"),
                             ("execution", "When you approve")):
            value = proposal.get(field)
            if value is None:
                continue
            st.markdown(f"**{label}**")
            if isinstance(value, list):
                for item in value:
                    st.write(f"• {item}")
            else:
                st.write(value)
    with st.expander("Technical details"):
        st.caption(f"Proposal ID: {view['proposal_digest']}")


def _show_outcome(session: object, view: dict) -> None:
    """Render actual findings and distinguish generated files from verified reports.

    Download exact service bytes and state their independent verification status.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    status = view.get("status", "missing")
    message = view.get("message") or ""
    if status == "draft" and not message:
        return
    if status in {"draft", "missing", "missing_inputs", "needs_inputs"}:
        st.info(message or "Upload your data and describe what you are trying to solve for.")
    elif status in {"blocked", "unsupported_task"}:
        st.warning(message or "The task is blocked. Review the required changes below.")
    elif status in {"failure", "failed", "execution_failed", "validation_failed"}:
        st.error(message or "The run failed. No verified report is available.")
    elif status == "running":
        st.info(message or "Working on your approved task.")
    elif status == "investigation_completed":
        st.info(message or "The data investigation is complete. These findings are not a verified final report.")
    elif status == "analysis_completed":
        st.info(message or "Data has produced an analysis output.")
    elif status in {"success", "completed"}:
        result = session.download()
        if result is None or view.get("report_verified") is not True:
            st.error("The run has no verified report available for download.")
        else:
            name, data = result
            st.success(message or "Analysis completed and the report passed verification.")
            st.download_button("Download verified HTML report", data=data, file_name=name,
                               mime="text/html", key="download_verified_report")
    if view.get("report_available") and view.get("report_verified") is False:
        result = session.download()
        if result is not None:
            name, data = result
            st.caption("Data-generated development report; not independently verified.")
            st.download_button("Download Data output", data=data, file_name=name,
                               mime="text/html", key="download_data_output")
    investigation = view.get("investigation_text")
    if investigation:
        st.subheader("What we found")
        st.write(investigation)
    for error in view.get("errors", []):
        st.write(error)
    if view.get("technical_details"):
        with st.expander("Technical details"):
            st.text(view["technical_details"])


def run_app(session_factory: Callable | None = None) -> None:
    """Run one page whose actions bind approval to the current exact inputs.

    The injected factory supports UI checks without executing the real backend.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    from suiroai.demo.service import DemoSession, UploadedInput

    st.set_page_config(page_title="SuiroAI local demo", page_icon="📊")
    st.title("SuiroAI local demo")
    st.caption("Review the proposed task before allowing analysis. Downloaded outputs state whether they have been independently verified.")
    st.write("Upload your data.")
    st.caption("Changing the question or a file clears the previous approval and result.")
    if "demo_session" not in st.session_state:
        st.session_state.demo_session = (session_factory or DemoSession)()
    session = st.session_state.demo_session

    question = st.text_area("What are you trying to solve for?", key="business_question")
    uploaded_files = st.file_uploader("Upload your data", accept_multiple_files=True, key="upload_files")
    uploads = [UploadedInput(name=file.name, data=file.getvalue()) for file in uploaded_files]
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
            with st.spinner("Working on your approved task…"):
                session.approve_and_run(view["proposal_digest"])
            st.rerun()
    _show_outcome(session, view)


if __name__ == "__main__":
    run_app()
