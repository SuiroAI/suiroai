"""Connect explicit browser consent to the actual DSC-59 Data investigation.

Retain native execution evidence, a dedicated restocking CSV, optional demo HTML and the Data
explanation shown in the app. Exact stored output bytes remain bound to the
current approval and original runtime receipt.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from dataclasses import dataclass
import json
from pathlib import Path
import uuid

from suiroai.contracts import record_ref
from .investigation import run_investigation


@dataclass(frozen=True)
class BackendResult:
    """Return bounded native findings with verification provenance kept explicit."""

    status: str
    message: str
    download_bytes: bytes | None = None
    download_name: str | None = None
    evidence_path: str | None = None
    evidence_ref: dict | None = None
    investigation_text: str | None = None
    investigation_path: str | None = None
    native_outcome: str | None = None
    report_path: str | None = None
    report_ref: dict | None = None
    report_verified: bool = False
    download_mime: str = "text/csv"
    html_download_bytes: bytes | None = None
    html_download_name: str | None = None
    html_download_mime: str = "text/html"
    html_report_ref: dict | None = None
    html_report_path: str | None = None


def run_approved(store, submission, proposal, approval, execution, work_root,
                 consent_validator, progress=None):
    """Send one exact approved development snapshot to the actual Data runtime.

    Native completion is evidence of an attempted investigation, not independent
    verification. Browser consent is rechecked before publication by both helper
    and service; no inventory-only fallback substitutes for the analytical turn.
    """
    if not callable(consent_validator):
        raise ValueError("A trusted current-consent validator is required")
    if execution is not None:
        raise ValueError("This approval authorizes development investigation only")
    root = Path(work_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / ("attempt-" + uuid.uuid4().hex + ".json")
    result, error = None, None
    investigation_text = investigation_path = native_outcome = None
    download_bytes = download_name = report_path = report_ref = None
    html_download_bytes = html_download_name = html_report_path = html_report_ref = None
    try:
        result = run_investigation(store, submission, proposal, approval, root,
            consent_validator, progress=progress)
        native_outcome = result["native_outcome"]
        investigation_text = result.get("unverified_investigation_text")
        report_ref = result.get("unverified_report_ref")
        if result.get("output_error"):
            status = "execution_failed"
            message = "Data returned output that could not be safely published: " + result["output_error"]
        elif native_outcome == "completed" and report_ref:
            download_name = result.get("unverified_report_name", "restocking.csv")
            if (download_name != "restocking.csv"
                    or result.get("unverified_report_mime", "text/csv") != "text/csv"):
                raise ValueError("Data must return the restocking list as a CSV file")
            download_bytes = store.read_bytes(report_ref)
            report_file = root / ("restocking-" + uuid.uuid4().hex + ".csv")
            report_file.write_bytes(download_bytes)
            report_path = str(report_file)
            html_report_ref = result.get("html_report_ref")
            if html_report_ref:
                html_download_name = result.get("html_report_name", "report.html")
                if (html_download_name != "report.html"
                        or result.get("html_report_mime", "text/html") != "text/html"):
                    raise ValueError("The demo report must be an HTML file")
                html_download_bytes = store.read_bytes(html_report_ref)
                html_path = root / ("demo-report-" + uuid.uuid4().hex + ".html")
                html_path.write_bytes(html_download_bytes)
                html_report_path = str(html_path)
            status = "analysis_completed"
            message = "Analysis complete. Your restocking list is ready to download."
        elif native_outcome == "completed" and investigation_text:
            status = "investigation_completed"
            message = "Data completed the analysis. Findings are shown below."
        else:
            status = "blocked"
            message = "Data could not complete the investigation. " + result.get("message", "No investigation output was returned.")
        if investigation_text:
            investigation_path = root / ("investigation-" + uuid.uuid4().hex + ".md")
            investigation_path.write_text(investigation_text, encoding="utf-8")
            investigation_path = str(investigation_path)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        status, message = "execution_failed", "Data investigation could not proceed: " + str(exc)
    if consent_validator(approval, proposal) is not True:
        raise ValueError("Current customer consent was revoked before result publication")
    receipt = {"format": "dsc59-demo-attempt-v2", "status": status,
        "message": message, "analytical_success": False, "verified_report_available": False,
        "submission_ref": record_ref(submission), "proposal_ref": record_ref(proposal),
        "approval_ref": record_ref(approval), "stage_result": result, "error": error}
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    evidence_ref = store.put_bytes("demo-attempt-" + uuid.uuid4().hex, 1, "derived", receipt_bytes)
    receipt_path.write_bytes(receipt_bytes)
    return BackendResult(status, message, evidence_path=str(receipt_path), evidence_ref=evidence_ref,
        investigation_text=investigation_text, investigation_path=investigation_path,
        native_outcome=native_outcome, download_bytes=download_bytes, download_name=download_name,
        report_path=report_path, report_ref=report_ref,
        html_download_bytes=html_download_bytes, html_download_name=html_download_name,
        html_report_ref=html_report_ref, html_report_path=html_report_path)
