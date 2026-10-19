"""Connect explicit browser consent to the existing DSC-59 parent and adapter.

Retain actual native discovery and parent checkpoint evidence. An execution
receipt is distinct from a verified analytical report and cannot yield a
recommendation download while integration blockers remain.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import uuid

from suiroai.contracts import digest, record_ref
from suiroai.integration.artifacts import read_stage_file
from suiroai.parent import ParentWorkflow
from .runtime import DemoNativeHost
from .worker import analytical_blockers, audit_development_partition


@dataclass(frozen=True)
class BackendResult:
    """Return a bounded attempt status with no unverified analytical download."""

    status: str
    message: str
    download_bytes: bytes | None = None
    download_name: str | None = None
    evidence_path: str | None = None
    evidence_ref: dict | None = None


def _refs(value):
    if isinstance(value, dict):
        if set(value) == {"artifact_id", "version", "sha256", "provenance"}:
            yield value
        else:
            for child in value.values():
                yield from _refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _refs(child)


class MeasuredReview:
    """Review exact released bytes while refusing unsupported analytical claims."""

    def __init__(self, store, execution):
        self.store, self.execution = store, execution
        self.events = []

    def release(self, stage, refs, records):
        valid = (stage == "preparation" and bool(refs)
            and all(ref in self.execution["source_refs"] for ref in refs)
            and any(record_ref(r) == record_ref(self.execution) for r in records))
        for ref in refs:
            self.store.read_bytes(ref)
        self.events.append({"review": "release", "stage": stage,
            "accepted_for_inventory_only": valid, "refs": refs})
        return valid

    def evidence(self, packet, artifact_bytes):
        artifacts = packet.get("artifacts", [])
        exact = bool(artifacts) and len(artifacts) == len(artifact_bytes)
        exact = exact and all(len(data) == meta.get("bytes") and
            sha256(data).hexdigest() == meta.get("byte_sha256")
            for meta, data in zip(artifacts, artifact_bytes))
        self.events.append({"review": "candidate", "measured_bytes_match": exact,
            "accepted": False, "reason": "Independent numerical reviewer bridge is not implemented"})
        # Byte integrity alone does not prove numerical correctness.
        return False


def run_approved(store, submission, proposal, approval, execution, work_root,
                 consent_validator, progress=None):
    """Attempt one real approved run and persist an honest execution receipt.

    consent_validator(approval, proposal) must authenticate the current browser
    consent independently of worker records. Native preflight cannot bypass it.
    """
    if not callable(consent_validator):
        raise ValueError("A trusted current-consent validator is required")
    review = MeasuredReview(store, execution)
    parent = ParentWorkflow(store, confirm_approval=consent_validator,
        review_release=review.release, review_evidence=review.evidence)
    root = Path(work_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / ("attempt-" + uuid.uuid4().hex + ".json")
    result = None
    error = None
    try:
        records = [r for r in (submission, proposal, approval, execution) if r is not None]
        refs = {digest(ref): ref for record in records
            for ref in _refs(record)}
        identities = {digest(record_ref(r)) for r in records}
        external = [ref for key, ref in refs.items() if key not in identities]
        parent.receive_submission(submission, external_refs=external)
        parent.present_proposal(proposal)
        parent.record_approval(approval)
        if progress:
            progress("Approved task bound. Checking the actual native Data runtime.")
        if execution is None:
            attempt = root / ("preflight-" + uuid.uuid4().hex)
            attempt.mkdir(mode=0o700)
            released, output, evidence = [attempt / name for name in ("released", "output", "native")]
            for directory in (released, output, evidence):
                directory.mkdir(mode=0o700)
            native = DemoNativeHost().execute(cwd=output, prompt="Runtime discovery only; no customer data released.",
                evidence_dir=evidence, released_root=released, timeout_seconds=20)
            native_refs = []
            for meta in native.evidence.get("artifact_receipts", []):
                data = read_stage_file(evidence, meta["relative_path"])
                if len(data) != meta["bytes"] or sha256(data).hexdigest() != meta["sha256"]:
                    raise ValueError("Native discovery evidence changed before immutable publication")
                native_refs.append(store.put_bytes("demo-native-" + uuid.uuid4().hex, 1, "derived", data))
            result = {"preflight_only": True, "error_code": native.error_code,
                "message": native.message, "evidence": native.evidence,
                "immutable_native_evidence_refs": native_refs,
                "analytical_model_turn_requested": False}
            inventory = native.evidence.get("plugin_inventory_command", {})
            audit_summary = ""
            if inventory.get("status") == "verified":
                # Recheck the browser ledger immediately before accessing the
                # approved source for the controller-only release audit.
                if consent_validator(approval, proposal) is not True:
                    raise ValueError("Current customer consent was revoked before source audit")
                if progress:
                    progress("Native inventory verified. Measuring development partition boundaries without a model turn.")
                result["development_release_audit"] = audit_development_partition(store, submission, proposal)
                audit = result["development_release_audit"]
                audit_summary = (f" Controller audit preserved {audit['development_source_records']} development records "
                    f"across {audit['development_product_store_pairs']} product/store pairs; "
                    f"{audit['development_unobserved_pair_dates']} pair dates have no records and remain unknown.")
            message = native.message + audit_summary + " No execution contract was started: a justified acceptance rule and safe derived-input release are still required."
        else:
            parent.start(execution)
            # Discovery needs no sales bytes. Release one approved nonsales input
            # only; the host refuses all analytical turns independently.
            safe_hashes = {file["sha256"] for file in submission.get("files", [])
                if file.get("source_role") == "dictionary"}
            release = [ref for ref in execution["source_refs"] if ref["sha256"] in safe_hashes]
            if not release:
                raise ValueError("Native discovery requires a safe nonsales release reference")
            request = parent.issue_stage(release[:1], seconds=30)
            result = parent.execute(request, work_root=root / "stages", host=DemoNativeHost())
            message = result.get("failure", {}).get("reason") or "Native stage produced no verified analytical response."
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        message = "Approved execution could not proceed: " + str(exc)
    receipt = {"format": "dsc59-demo-attempt-v1", "status": "blocked",
        "message": message, "analytical_success": False, "verified_report_available": False,
        "execution_contract_ref": record_ref(execution) if execution else None,
        "submission_ref": record_ref(submission), "proposal_ref": record_ref(proposal),
        "approval_ref": record_ref(approval), "parent": parent.checkpoint(),
        "stage_result": result, "error": error, "reviews": review.events,
        "remaining_requirements": analytical_blockers()}
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    evidence_ref = store.put_bytes("demo-attempt-" + uuid.uuid4().hex, 1, "derived", receipt_bytes)
    receipt_path.write_bytes(receipt_bytes)
    return BackendResult("blocked", message, evidence_path=str(receipt_path), evidence_ref=evidence_ref)
