"""Bind the local demo's measured uploads to explicit, single-use consent.

Use the existing intake records and immutable artifact store for the fixed
retail task. Browser reruns only display state; edited inputs revoke consent
and downloads. Approved development files reach the actual Data runtime;
unverified findings remain distinct from an independently verified report.

Structured task context preserves the original question and attributes the
current-process interpretation independently of the readable review text.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import csv
import codecs
import io
import json
from pathlib import Path
import re
import threading
import uuid

from suiroai.contracts import VERSION, digest, proposal_digest, record_ref, schema_validator, validate_handoff, validate_record
from suiroai.integration.artifacts import ArtifactStore
from suiroai.intake import SuppliedFile, receive_submission
from .backend import run_approved
from .task import CONTEXT_ID, comparison_contract_record, task_context


ROLES = {
    "sales": ("transactions", {"Product_ID", "Store_ID", "Order_Date", "Quantity", "Order_Status", "Return_Flag"}),
    "dictionary": ("dictionary", {"Column_Name", "Description", "Business_Meaning"}),
    "inventory": ("usable_stock", {"Product_ID", "Store_ID", "Snapshot_Date", "Usable_On_Hand_Qty", "On_Order_Qty"}),
    "receipts": ("inbound_ledger", {"Product_ID", "Store_ID", "Expected_Arrival_Date", "Incoming_Qty"}),
    "policy": ("ordering_policy", {"Product_ID", "Store_ID", "Supplier_Lead_Time_Days", "Review_Period_Days", "Safety_Stock_Qty", "Minimum_Order_Qty", "Order_Multiple_Qty"}),
}
REQUIRED_ROLES = {"sales"}


@dataclass(frozen=True)
class UploadedInput:
    """Carry generic uploaded bytes; the backend identifies their content role."""
    name: str
    role: str | None = None
    data: bytes = b""


def _identify_uploads(uploads):
    """Identify this backend's input roles from bounded headers, never names.

    The browser stays generic. Unknown and duplicate inputs remain available to Data. The controller uses
    a transaction date column only to isolate later outcomes.
    """
    identified, errors, seen = [], [], set()
    for file in uploads:
        if len(file.data) > 16 * 1024 * 1024:
            errors.append(f"{file.name}: exceeds the 16 MiB file limit.")
            continue
        try:
            # Only inspect a bounded header here; source rows remain untouched.
            text = codecs.getincrementaldecoder("utf-8-sig")().decode(
                file.data[:65536], final=len(file.data) <= 65536)
            columns = next(csv.reader(io.StringIO(text)), [])
        except (UnicodeError, csv.Error):
            columns = []
        if not columns or len(columns) > 256 or any(len(column) > 256 for column in columns):
            errors.append(f"{file.name}: unrecognized format; this demo's backend currently reads CSV data.")
            continue
        candidates = [role for role, (_, fields) in ROLES.items() if fields <= set(columns)]
        if "Order_Date" in columns and not candidates:
            candidates = ["sales"]
        # Structural routing is solely for the confidential date partition.
        # Duplicate sources and uncertain meanings are retained for Data to
        # reconcile from their contents rather than decided by this app.
        role = candidates[0] if len(candidates) == 1 else "other"
        seen.add(role)
        identified.append(UploadedInput(name=file.name,
            role=role + ":" + str(len(identified)), data=file.data))
    if "sales" not in seen:
        errors.append("Supply the dated transaction CSV for this historical retail task so later outcomes can be kept separate.")
    return tuple(identified), errors


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(question, uploads):
    return digest({"question": question, "files": sorted([
        {"name": file.name, "role": file.role, "sha256": sha256(file.data).hexdigest()}
        for file in uploads], key=lambda row: (row["role"] or "", row["name"], row["sha256"]))})


def current_process_request(question, current_approach=None, continue_without=False):
    """Bind explicit process context or absence to the exact user-approved request.

    Never substitute a detector summary for the user's original question.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    if continue_without:
        return question + "\n\nThe user chose to continue without a current approach. Do not invent an incumbent."
    if current_approach and current_approach.strip():
        return question + "\n\nHow do you do this now?\n" + current_approach.strip()
    return question


class DemoSession:
    """Keep one in-process task, proposal, consent event, and bounded attempt.

    Consent is checked against a private exact-record ledger, never inferred
    from a worker's JSON or restored from browser session data after restart.
    """
    def __init__(self, *, artifact_root=None, backend=None, context_detector=None,
                 comparison_contract=None):
        self._comparison_contract = comparison_contract_record(comparison_contract)
        self._root = Path(artifact_root or Path.cwd() / "artifacts" / "demo").resolve() / uuid.uuid4().hex
        self._task = "retail-" + uuid.uuid4().hex
        from .current_process import detect_current_process

        self._context_detector = context_detector or detect_current_process
        self._context_cache = {}
        self._context_inflight = {}
        self._backend = backend or run_approved
        self._lock = threading.RLock()
        self._fingerprint = None
        self._revision = 0
        self._receipt = self._proposal = self._approval = None
        self._consent = None
        self._attempted = set()
        self._store = None
        self._download = None
        self._html_download = None
        self._view = {"status": "draft", "message": "", "errors": []}

    def set_comparison_contract(self, definition):
        """Change controller comparison settings while revoking old consent/results.

        Ordinary customer analysis leaves this optional engineering contract
        unset. Validate before changing state; never infer it from detector text.
        Linear: https://linear.app/gr3enarr0w/issue/DSC-60
        """
        record = comparison_contract_record(definition)
        with self._lock:
            if record != self._comparison_contract:
                self._comparison_contract = record
                self.revise()
                self._fingerprint = None

    @property
    def view(self):
        with self._lock:
            return deepcopy(self._view)

    def invalidate(self, question, uploads):
        uploads = tuple(uploads)
        current = digest({"inputs": _fingerprint(question, uploads),
            "comparison_contract": self._comparison_contract})
        with self._lock:
            if current == self._fingerprint:
                return
            had_proposal = self._proposal is not None or self._approval is not None
            self._fingerprint = current
            self._revision += 1
            self._receipt = self._proposal = self._approval = self._consent = None
            self._download = self._html_download = None
            self._view = {"status": "draft", "message": "Inputs changed. Review the task before approving a new run." if had_proposal else "", "errors": []}

    def revise(self):
        with self._lock:
            self._proposal = self._approval = self._consent = None
            self._download = self._html_download = None
            self._revision += 1
            self._view = {"status": "draft", "message": "Edit the question or files, then select Review task again.", "errors": []}

    def context_for(self, question, uploads):
        """Return detected context only for the exact current question and file bytes.

        The UI uses a missing result to show one optional process question.
        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        key = _fingerprint(question, uploads)
        with self._lock:
            value = self._context_cache.get(key)
            return {**deepcopy(value), "input_key": key} if value else None

    def review(self, question, uploads, *, current_approach=None, continue_without=False):
        """Inspect existing context before asking, then propose the exact current task.

        Review authorizes only context inspection. Analysis still requires the
        resulting proposal's separate explicit approval. Late detection results
        cannot overwrite edits, revisions, or a newer review.
        Linear: https://linear.app/gr3enarr0w/issue/DSC-59
        """
        uploads = tuple(uploads)
        request = current_process_request(question, current_approach, continue_without)
        self.invalidate(request, uploads)
        with self._lock:
            if self._proposal is not None and self._view["status"] == "awaiting_approval":
                return self.view
            # Validate the existing input contract before any model inspection.
            _, errors = _identify_uploads(uploads)
            if not question.strip() or not re.search(r"restock|replenish|reorder|order quantit", question, re.I) or errors:
                return self._propose(request, uploads)
            revision = self._revision
            key = _fingerprint(question, uploads)
            context = self._context_cache.get(key)
            if not continue_without and not (current_approach and current_approach.strip()) and context is None:
                if self._context_inflight.get(key) == revision:
                    return self.view
                self._context_inflight[key] = revision
                self._view = {"status": "checking_context", "message": "Checking your question and files for your current approach…", "errors": []}
        if not continue_without and not (current_approach and current_approach.strip()) and context is None:
            try:
                context = self._context_detector(question, uploads, self._root / "context")
                if (not isinstance(context, dict) or context.get("status") not in {"found", "missing", "none"}
                        or not isinstance(context.get("summary"), str)
                        or (context["status"] == "found" and not context["summary"].strip())):
                    raise ValueError("Invalid current-process inspection result")
            except Exception:
                with self._lock:
                    if self._context_inflight.get(key) == revision:
                        self._context_inflight.pop(key, None)
                    if revision != self._revision:
                        return self.view
                    self._view = {"status": "context_failed", "message": "We couldn't check your files for your current approach. Select Review task to try again.", "errors": []}
                    return self.view
            except BaseException:
                # A user/runtime interruption must not leave the same snapshot
                # permanently marked as inspecting on the next Review action.
                with self._lock:
                    if self._context_inflight.get(key) == revision:
                        self._context_inflight.pop(key, None)
                raise
            with self._lock:
                if self._context_inflight.get(key) == revision:
                    self._context_inflight.pop(key, None)
                if revision != self._revision:
                    return self.view
                self._context_cache[key] = {field: deepcopy(context[field]) for field in
                    ("status", "summary", "evidence", "evidence_path", "result_sha256", "native_outcome", "released_files")
                    if field in context}
        with self._lock:
            if revision != self._revision:
                return self.view
            if not continue_without and not (current_approach and current_approach.strip()):
                if context["status"] == "missing":
                    self._view = {"status": "awaiting_current_process", "message": "How do you do this now?", "errors": []}
                    return self.view
                if context["status"] == "found":
                    request += "\n\nCurrent approach described in the supplied question or files:\n" + context["summary"]
                else:
                    request += "\n\nThe supplied context explicitly says there is no current approach. Do not invent an incumbent."
            return self._propose(request, uploads, context=task_context(question,
                current_approach=current_approach, continue_without=continue_without, detected=context,
                comparison_contract=(self._comparison_contract["definition"] if self._comparison_contract else None)))

    def _propose(self, question, uploads, *, context=None):
        uploads = tuple(uploads)
        with self._lock:
            if self._proposal is not None and self._view["status"] == "awaiting_approval":
                return self.view
            self._revision += 1
            self._consent = self._approval = None
            self._download = self._html_download = None
            self._receipt = self._proposal = None
            errors = []
            if not question.strip():
                errors.append("Describe what you are trying to solve for.")
            elif not re.search(r"restock|replenish|reorder|order quantit", question, re.I):
                self._view = {"status": "unsupported_task", "message": "This backend currently supports the historical retail restocking demo. Your requested task is not connected yet.", "errors": []}
                return self.view
            uploads, input_errors = _identify_uploads(uploads)
            errors.extend(input_errors)
            if errors:
                self._view = {"status": "needs_inputs", "message": "More information is needed before review.", "errors": errors}
                return self.view
            lookup = {}
            files = []
            for file in uploads:
                file_id = self._task + ":" + file.role
                lookup[file_id] = file.data
                files.append(SuppliedFile(file_id, "upload://" + file_id, ROLES.get(file.role.split(":", 1)[0], ("other", set()))[0], self._task,
                    provenance="supplied", version=self._revision, original_name=Path(file.name).name))
            receipt = receive_submission(original_request=(context["original_question"] if context else question.strip()), files=files,
                task_id=self._task, task_version=1, input_version=self._revision, received_at=_now(),
                read_bytes=lambda file, limit: lookup[file.file_id][:limit + 1])
            measured = {source.file_id: source for source in receipt.sources}
            for file in uploads:
                source = measured.get(self._task + ":" + file.role)
                if source is None:
                    continue
                missing = ({"Order_Date"} if file.role.split(":", 1)[0] == "sales" else set()) - set(source.inspection["columns"])
                if missing:
                    errors.append(f"{file.role}: required fields are absent: {', '.join(sorted(missing))}.")
            for file in receipt.submission["files"]:
                if file["access"] != "accessible":
                    errors.append(f"{file['original_name']}: {file['access_reason']}")
            if errors:
                self._view = {"status": "needs_inputs", "message": "The supplied files do not yet support this demo's input contract.", "errors": errors}
                return self.view
            temporal = {key: value["const"] for key, value in schema_validator().schema["$defs"]["temporal_plan"]["properties"].items()}
            assumptions = [
                {"assumption_id": "demo-scope", "classification": "synthetic_assumption", "status": "proposed", "source_refs": [],
                 "statement": "Use November 30, 2025 as the planning date and same-product units. Data will assess whether supplied operational inputs are synthetic and explain how their provenance affects the results."},
                {"assumption_id": "demo-unknown-history", "classification": "unknown", "status": "unresolved", "source_refs": receipt.external_refs,
                 "statement": "Data will assess historical availability and daily coverage from the files, choose supported treatment for missing observations, and explain assumptions and sensitivities."},
                {"assumption_id": "demo-inferred-measures", "classification": "supported_interpretation", "status": "proposed", "source_refs": receipt.external_refs,
                 "statement": "Quantity, status, and return fields are candidate transaction measures. Their meanings and treatment will be investigated from file contents and cross-file consistency. Use supported assumptions, methods and sensitivity analysis to resolve uncertainty; state any remaining limitations in the report."},
            ]
            if context is not None:
                assumptions.append({"assumption_id": CONTEXT_ID,
                    "classification": "supported_interpretation", "status": "proposed",
                    "source_refs": receipt.external_refs,
                    "statement": json.dumps(context, ensure_ascii=False, sort_keys=True)})
            assumptions.append({"assumption_id": "development_investigation",
                "classification": "synthetic_assumption", "status": "proposed",
                "source_refs": receipt.external_refs,
                "statement": "Send these approved files and question to Data for analysis through November 30, 2025, with later transaction outcomes withheld. Data will determine supported treatment and methods, compare sensitive assumptions, and produce the best useful report with limitations without asking follow-up questions."})
            pending = lambda name: {"status": "pending", "unresolved_gap_ids": [name]}
            proposal = {"kind": "task_proposal", "schema_version": VERSION, "artifact_id": self._task + ":proposal",
                "artifact_version": self._revision, "provenance": "derived",
                "binding": {**receipt.submission["binding"], "proposal_version": self._revision, "proposal_digest": "0" * 64},
                "submission_ref": receipt.ref, "goal": question.strip(),
                "output": "one_restocking_list_and_final_report_or_verified_failure_explanation",
                "source_refs": receipt.external_refs, "readiness": "ready", "assumptions": assumptions,
                "gaps": [{"gap_id": name, "description": text, "material": False, "blocks": [],
                          "request_to_user": "The backend must resolve this before analytical execution or report delivery."}
                    for name, text in [("target-investigation", "Investigate target treatment and historical coverage."),
                                       ("acceptance-rule", "Declare justified final-validation criteria before any holdout access.")]],
                "target_policy": pending("target-investigation"), "acceptance_rule": pending("acceptance-rule"), "temporal_plan": temporal}
            proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
            failures = validate_record(proposal) + validate_handoff([receipt.submission, proposal], receipt.external_refs)
            if failures:
                raise ValueError("Invalid proposal: " + "; ".join(failures))
            self._receipt, self._proposal = receipt, proposal
            self._store = ArtifactStore(self._root / "store")
            for source in receipt.sources:
                self._store.put_bytes(source.file_id, source.version, source.provenance, source.data)
            self._store.put_record(receipt.submission)
            self._store.put_record(proposal)
            summary = {"question": question.strip(), "inputs": [file["original_name"] for file in receipt.submission["files"]],
                "review_date": "2025-11-30", "output": "A restocking CSV to download, the same list in a separate browser tab, and a plain-language explanation shown in the app.",
                "understanding": "Data will inspect and compare your files, determine supported treatment and methods, and explain the results and limitations here. No follow-up answers are required.",
                "assumptions": [item["statement"] for item in assumptions if item["assumption_id"] != CONTEXT_ID],
                "execution": "Approve analysis of this question and these files. Data will prepare the restocking CSV and explanation using records through November 30, 2025; later transaction outcomes remain separate."}
            if self._comparison_contract:
                summary["assumptions"].append(
                    "This engineering run uses a fixed comparison setup: the same sales definition, "
                    "simple comparison method, products, weeks, forecast period, error measure and "
                    "selection rule throughout. It is not your supplied buying rule or proof of improvement.")
            self._view = {"status": "awaiting_approval", "proposal_digest": proposal["binding"]["proposal_digest"],
                "proposal_summary": summary, "message": "Review this exact task and its limitations before approving.", "errors": []}
            return self.view

    def approve_and_run(self, proposal_digest_value):
        with self._lock:
            if (self._proposal is None or self._receipt is None or self._view["status"] != "awaiting_approval"
                    or proposal_digest_value != self._proposal["binding"]["proposal_digest"]):
                return self.view
            key = (self._fingerprint, proposal_digest_value)
            if key in self._attempted:
                self._view.update(status="blocked", message="This proposal already used its run permission. Revise and review before a fresh attempt.")
                return self.view
            self._attempted.add(key)
            approval = {"kind": "task_approval", "schema_version": VERSION, "artifact_id": self._task + ":approval",
                "artifact_version": self._revision, "provenance": "derived", "binding": deepcopy(self._proposal["binding"]),
                "proposal_ref": record_ref(self._proposal), "decision": "approved", "actor": "local-demo-browser",
                "decided_at": _now(), "comment": "Explicit Approve and run click for the displayed proposal and exact input snapshot."}
            self._approval = approval
            self._consent = (deepcopy(approval), record_ref(self._proposal), self._fingerprint)
            self._store.put_record(approval)
            proposal, receipt, fingerprint = deepcopy(self._proposal), self._receipt, self._fingerprint
            self._view.update(status="running", message="Checking the approved task and native analytical runtime.")

        def consent(actual_approval, actual_proposal):
            with self._lock:
                return (self._consent is not None and self._fingerprint == fingerprint
                    and actual_approval == self._consent[0] and record_ref(actual_proposal) == self._consent[1])

        try:
            result = self._backend(self._store, receipt.submission, proposal, approval, None,
                self._root / "runs", consent)
            with self._lock:
                if self._fingerprint != fingerprint or not consent(approval, proposal):
                    return self.view
                status = result.status
                message = result.message
                details = message
                if status == "completed":
                    status = "blocked"
                    message = "The analysis did not return a report file for download."
                report_available = (status == "analysis_completed"
                    and getattr(result, "report_ref", None) is not None
                    and getattr(result, "download_bytes", None) is not None)
                if report_available:
                    persisted = self._store.read_bytes(result.report_ref)
                    if persisted != result.download_bytes:
                        raise ValueError("Data report differs from its immutable receipt")
                    self._download = (result.download_name, persisted)
                html_available = (report_available
                    and getattr(result, "html_report_ref", None) is not None
                    and getattr(result, "html_download_bytes", None) is not None)
                if html_available:
                    html_persisted = self._store.read_bytes(result.html_report_ref)
                    if html_persisted != result.html_download_bytes:
                        raise ValueError("Demo HTML differs from its immutable receipt")
                    self._html_download = (result.html_download_name, html_persisted)
                self._view.update(status=status, message=message, technical_details=details,
                    report_available=report_available, report_verified=False,
                    download_mime=getattr(result, "download_mime", "text/csv"),
                    html_report_available=html_available, html_download_mime="text/html",
                    html_report_path=getattr(result, "html_report_path", None),
                    report_path=getattr(result, "report_path", None),
                    evidence_path=result.evidence_path,
                    investigation_text=getattr(result, "investigation_text", None),
                    investigation_path=getattr(result, "investigation_path", None),
                    native_outcome=getattr(result, "native_outcome", None),
                    verified_report_available=False, errors=[])
        except Exception:
            with self._lock:
                if self._fingerprint == fingerprint and consent(approval, proposal):
                    self._view.update(status="execution_failed", message="The analysis attempt failed. No report is available.", errors=[])
        return self.view

    def download(self):
        """Return only the current approved Data output with explicit provenance.

        Unverified development output is available as such; it never sets the
        verified final report flag. Revise and changed inputs discard the bytes.
        """
        with self._lock:
            return self._download if self._view.get("report_available") else None

    def download_html(self):
        """Return the current consent-bound demo HTML alongside the primary CSV."""
        with self._lock:
            return self._html_download if self._view.get("html_report_available") else None
