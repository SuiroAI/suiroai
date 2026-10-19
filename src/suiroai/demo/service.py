"""Bind the local demo's measured uploads to explicit, single-use consent.

Use the existing intake records and immutable artifact store for the fixed
retail task. Browser reruns only display state; edited inputs revoke consent
and downloads. The current backend can retain a real blocked preflight, but
cannot publish an unverified report as a successful analytical result.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import threading
import uuid

from suiroai.contracts import VERSION, digest, proposal_digest, record_ref, schema_validator, validate_handoff, validate_record
from suiroai.integration.artifacts import ArtifactStore
from suiroai.intake import SuppliedFile, receive_submission
from .backend import run_approved


ROLES = {
    "sales": ("transactions", {"Product_ID", "Store_ID", "Order_Date", "Quantity", "Order_Status", "Return_Flag"}),
    "dictionary": ("dictionary", {"Column_Name", "Description", "Business_Meaning"}),
    "inventory": ("usable_stock", {"Product_ID", "Store_ID", "Snapshot_Date", "Usable_On_Hand_Qty", "On_Order_Qty"}),
    "receipts": ("inbound_ledger", {"Product_ID", "Store_ID", "Expected_Arrival_Date", "Incoming_Qty"}),
    "policy": ("ordering_policy", {"Product_ID", "Store_ID", "Supplier_Lead_Time_Days", "Review_Period_Days", "Safety_Stock_Qty", "Minimum_Order_Qty", "Order_Multiple_Qty"}),
}


@dataclass(frozen=True)
class UploadedInput:
    """Carry a role-labelled upload without trusting its original path."""
    name: str
    role: str
    data: bytes


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(question, uploads):
    return digest({"question": question, "files": sorted([
        {"name": file.name, "role": file.role, "sha256": sha256(file.data).hexdigest()}
        for file in uploads], key=lambda row: (row["role"], row["name"], row["sha256"]))})


class DemoSession:
    """Keep one in-process task, proposal, consent event, and bounded attempt.

    Consent is checked against a private exact-record ledger, never inferred
    from a worker's JSON or restored from browser session data after restart.
    """
    def __init__(self, *, artifact_root=None, backend=None):
        self._root = Path(artifact_root or Path.cwd() / "artifacts" / "demo").resolve() / uuid.uuid4().hex
        self._task = "retail-" + uuid.uuid4().hex
        self._backend = backend or run_approved
        self._lock = threading.RLock()
        self._fingerprint = None
        self._revision = 0
        self._receipt = self._proposal = self._approval = None
        self._consent = None
        self._attempted = set()
        self._store = None
        self._view = {"status": "draft", "message": "Upload the five retail files and enter your question.", "errors": []}

    @property
    def view(self):
        with self._lock:
            return deepcopy(self._view)

    def invalidate(self, question, uploads):
        uploads = tuple(uploads)
        current = _fingerprint(question, uploads)
        with self._lock:
            if current == self._fingerprint:
                return
            self._fingerprint = current
            self._revision += 1
            self._receipt = self._proposal = self._approval = self._consent = None
            self._view = {"status": "draft", "message": "Inputs changed. Review the task before approving a new run.", "errors": []}

    def revise(self):
        with self._lock:
            self._proposal = self._approval = self._consent = None
            self._revision += 1
            self._view = {"status": "draft", "message": "Edit the question or files, then select Review task again.", "errors": []}

    def review(self, question, uploads):
        uploads = tuple(uploads)
        self.invalidate(question, uploads)
        with self._lock:
            if self._proposal is not None and self._view["status"] == "awaiting_approval":
                return self.view
            self._revision += 1
            self._consent = self._approval = None
            self._receipt = self._proposal = None
            errors = []
            if not question.strip():
                errors.append("Enter the retail restocking question you want answered.")
            roles = [file.role for file in uploads]
            if len(set(roles)) != len(roles) or any(role not in ROLES for role in roles):
                errors.append("Supply one file for each labelled input role.")
            errors.extend("Provide the " + role + " file." for role in ROLES if role not in roles)
            if errors:
                self._view = {"status": "needs_inputs", "message": "More information is needed before review.", "errors": errors}
                return self.view
            if not re.search(r"restock|replenish|reorder|order quantit", question, re.I):
                self._view = {"status": "unsupported_task", "message": "This demo supports the historical retail restocking task. Please state that request explicitly.", "errors": []}
                return self.view
            lookup = {}
            files = []
            for file in uploads:
                file_id = self._task + ":" + file.role
                lookup[file_id] = file.data
                files.append(SuppliedFile(file_id, "upload://" + file_id, ROLES[file.role][0], self._task,
                    provenance="supplied", version=self._revision, original_name=Path(file.name).name))
            receipt = receive_submission(original_request=question.strip(), files=files,
                task_id=self._task, task_version=1, input_version=self._revision, received_at=_now(),
                read_bytes=lambda file, limit: lookup[file.file_id][:limit + 1])
            measured = {source.file_id: source for source in receipt.sources}
            for file in uploads:
                source = measured.get(self._task + ":" + file.role)
                if source is None:
                    continue
                missing = ROLES[file.role][1] - set(source.inspection["columns"])
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
                 "statement": "This is an illustrative November 30, 2025 retail scenario in same-product units. Operational inputs must be validated as synthetic before any recommendation."},
                {"assumption_id": "demo-unknown-history", "classification": "unknown", "status": "unresolved", "source_refs": receipt.external_refs,
                 "statement": "Historical information availability and complete daily sales coverage are unverified. Missing dates remain unknown; this proposal does not authorize silent zero filling."},
            ]
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
                "review_date": "2025-11-30", "output": "One verified HTML restocking report, only if all gates pass.",
                "assumptions": [item["statement"] for item in assumptions],
                "execution": "Approval permits one bounded attempt. Current runtime discovery and safe-input-release blockers may prevent analysis. No successful report has been produced."}
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
                if status == "blocked":
                    message = ("The demo stopped before model execution. Development-only data release "
                        "and a supported policy for missing daily sales are not yet connected, "
                        "so no verified restocking report is available.")
                if status == "completed":
                    status = "blocked"
                    message = "The backend has not supplied an independently verified delivery receipt. No report can be downloaded."
                self._view.update(status=status, message=message, technical_details=details,
                    evidence_path=result.evidence_path, errors=[])
        except Exception:
            with self._lock:
                if self._fingerprint == fingerprint and consent(approval, proposal):
                    self._view.update(status="execution_failed", message="The backend attempt failed. No verified report is available.", errors=[])
        return self.view

    def download(self):
        """Return no bytes until the backend implements verified final delivery.

        An intermediate native receipt or unverified generated HTML is never a
        customer report. The current preflight-only backend cannot mint one.
        """
        return None
