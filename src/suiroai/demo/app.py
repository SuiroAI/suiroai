"""Present the local, consent-gated retail analysis demo in Streamlit.

Keep execution and output downloads behind the session service so browser
reruns cannot authorize work or reuse a result after an input edit.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

from collections.abc import Callable
import mimetypes
from pathlib import Path

import streamlit as st


def _html_report_url(data: bytes) -> str:
    """Serve approved report bytes for viewing in a separate browser tab.

    Streamlit owns the local media URL and removes it when the session stops
    referencing the result. Register HTML as viewable media, not an attachment.
    The service has already checked consent, artifact identity and passive HTML.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    from streamlit import runtime

    return runtime.get_instance().media_file_mgr.add(
        data, "text/html", "demo.html_report", is_for_static_download=False,
    )


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


def _show_outcome(session: object, view: dict) -> None:
    """Explain findings and offer separate restocking data and demo HTML files.

    Keep scientific assumptions and limitations in the analysis itself.
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
    elif status in {"failure", "failed", "execution_failed", "validation_failed", "context_failed"}:
        st.error(message or "The run failed. No restocking list is available.")
    elif status == "awaiting_current_process":
        st.info("Describe your current approach above, or choose Continue without a current approach.")
    elif status == "running":
        st.info(message or "Working on your approved task.")
    elif status == "investigation_completed":
        st.info(message or "The data investigation is complete.")
    elif status == "analysis_completed":
        st.info(message or "Data has produced an analysis output.")
    elif status in {"success", "completed"}:
        st.success(message or "Analysis complete.")
    if view.get("report_available") or status in {"success", "completed"}:
        result = session.download()
        if result is not None:
            name, data = result
            extension = Path(name).suffix.lower()
            mime = view.get("download_mime") or mimetypes.guess_type(name)[0] or "application/octet-stream"
            if extension not in {".html", ".htm"} and mime != "text/html":
                label = "Download restocking list (CSV)" if extension == ".csv" else "Download restocking list"
                st.download_button(label, data=data, file_name=name,
                                   mime=mime, key="download_restocking_list")
    if view.get("html_report_available"):
        html_result = session.download_html()
        if html_result is not None:
            _, data = html_result
            st.link_button("View restocking list", url=_html_report_url(data))
    investigation = view.get("investigation_text")
    if investigation:
        st.subheader("What we found")
        st.write(investigation)
    for error in view.get("errors", []):
        st.write(error)


def run_app(session_factory: Callable | None = None) -> None:
    """Run one page whose actions bind approval to the current exact inputs.

    The injected factory supports UI checks without executing the real backend.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    from suiroai.demo.service import DemoSession, UploadedInput, current_process_request

    st.set_page_config(page_title="SuiroAI local demo", page_icon="📊")
    st.title("SuiroAI local demo")
    st.caption("Review the proposed task before allowing analysis.")
    st.write("Upload your data.")
    st.caption("Changing the question, current approach or a file clears the previous approval and result.")
    if "demo_session" not in st.session_state:
        st.session_state.demo_session = (session_factory or DemoSession)()
    session = st.session_state.demo_session

    question = st.text_area("What are you trying to solve for?", key="business_question")
    uploaded_files = st.file_uploader("Upload your data", accept_multiple_files=True, key="upload_files")
    uploads = [UploadedInput(name=file.name, data=file.getvalue()) for file in uploaded_files]
    context = session.context_for(question, uploads)
    missing_context = context is not None and context["status"] == "missing"
    current_approach = ""
    if missing_context:
        clear_answer = st.session_state.pop("clear_current_approach", False)
        if clear_answer or st.session_state.get("current_approach_input_key") != context["input_key"]:
            st.session_state["current_approach"] = ""
        st.session_state["current_approach_input_key"] = context["input_key"]
        current_approach = st.text_area(
            "How do you do this now?", key="current_approach",
            help="Describe your usual steps, or continue below if you don't have a current approach.",
        )
    continue_without = bool(missing_context and not current_approach.strip()
                            and st.session_state.get("continue_without_current") == context["input_key"])
    session.invalidate(current_process_request(question, current_approach, continue_without), uploads)

    if st.button("Review task", key="review_task"):
        with st.spinner("Checking your question and files for your current approach…"):
            result = session.review(question, uploads, current_approach=current_approach,
                                    continue_without=continue_without)
        if result.get("status") == "awaiting_current_process" and not missing_context:
            st.rerun()
    if missing_context and st.button("Continue without a current approach", key="continue_without_current_approach"):
        st.session_state["continue_without_current"] = context["input_key"]
        st.session_state["clear_current_approach"] = True
        session.review(question, uploads, continue_without=True)
        st.rerun()

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
