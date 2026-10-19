"""Verify preexecution guidance without inventing an approved run.

The caller supplies the *current* submission/proposal snapshot and a trusted,
independent semantic reviewer. Passing checks permit DSC-25/DSC-10 to consider
publishing guidance through their existing conversation; this is neither final
report authorization nor permission to execute. Currentness and parent authority
remain the caller's responsibility.

``review(text, submission, proposal, evidence_map)`` must check the exact blocked
decision, minimum missing business facts, consequences and actionable next step;
an offered narrower task must be explicit, never silently replace the goal.
It must also reject statistical-method questions, invented quantities, false
access/capability claims and hidden synthetic provenance. Evidence-map keys are
(artifact_id, version, sha256, provenance). There is no keyword-based truth pass.

Check specific supported capability and minimum missing facts for the current
request, preserving the distinction between a blocked task and completed
restocking without fabricating quantities or silently replacing the objective.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

from suiroai.contracts import record_ref, validate_handoff, validate_record

from .claims import _review


def check_capability_guidance(submission, proposal, customer_text, *, resolve_bytes,
                              review=None, verifier):
    """Return shared checks bound to unapproved submission/proposal references.

    Source bytes are hashed and compared with the submitted size. Missing and
    inaccessible files are declarations inspected by the semantic reviewer, not
    files this module pretends to have read. No source joining/preparation occurs.
    A missing reviewer or unreadable evidence blocks guidance verification.
    """
    if type(verifier) is not str or not verifier.strip():
        raise ValueError("An independent verifier identity is required")
    submission, proposal = deepcopy((submission, proposal))
    checks = []
    bound_refs = []
    for record in (submission, proposal):
        try:
            if not validate_record(record):
                bound_refs.append(record_ref(record))
        except Exception:
            pass

    def add(check_id, status, expected, actual):
        checks.append({"check_id": check_id, "requirement_id": "DSC-30-capability-guidance",
                       "status": status, "expected": expected, "actual": actual,
                       "evidence_refs": deepcopy(bound_refs), "verifier": verifier})

    errors = []
    for record, kind in ((submission, "submission"), (proposal, "task_proposal")):
        try:
            errors += validate_record(record)
            if record.get("kind") != kind:
                errors.append(f"Expected {kind} record")
        except Exception as exc:
            errors.append(f"Record validation failed: {type(exc).__name__}")
    if errors:
        add("guidance-records", "fail", "Valid submission and task proposal",
            f"Invalid snapshot: {len(errors)} record validation errors")
        return checks

    files = submission["files"]
    source_refs = proposal["source_refs"]
    file_ids = [file["file_id"] for file in files]
    source_ids = [(ref["artifact_id"], ref["version"]) for ref in source_refs]
    access_errors = []
    if len(file_ids) != len(set(file_ids)) or len(source_ids) != len(set(source_ids)):
        access_errors.append("Duplicate supplied-file or source identities")
    resolved = {}
    resolved_refs = []
    resolution_errors = []
    for ref in source_refs:
        matching = [file for file in files if file["file_id"] == ref["artifact_id"]
                    and file["sha256"] == ref["sha256"]
                    and file["provenance"] == ref["provenance"]
                    and file["access"] == "accessible"]
        if len(matching) != 1:
            access_errors.append("Source does not identify one actual accessible supplied file")
            continue
        try:
            data = resolve_bytes(deepcopy(ref))
            if (type(data) is not bytes or hashlib.sha256(data).hexdigest() != ref["sha256"]
                    or len(data) != matching[0]["size_bytes"]):
                resolution_errors.append("Source bytes do not match submitted hash/size")
                continue
            key = tuple(ref[name] for name in ("artifact_id", "version", "sha256", "provenance"))
            resolved[key] = data
            resolved_refs.append(ref)
        except Exception:
            resolution_errors.append("Source bytes are unavailable")
    add("guidance-access", "fail" if access_errors else "pass",
        "Source references preserve actual accessible file identity and provenance",
        f"Checked {len(source_refs)} sources; {len(access_errors)} access/identity discrepancies")
    add("guidance-source-bytes", "unavailable" if resolution_errors else "pass",
        "Every referenced source resolves to its submitted bytes/hash/size",
        f"Resolved {len(resolved_refs)} sources; {len(resolution_errors)} byte verification failures")
    try:
        handoff_errors = validate_handoff([submission, proposal], resolved_refs)
    except Exception as exc:
        handoff_errors = [f"Handoff validation raised {type(exc).__name__}"]
    add("guidance-binding", "fail" if handoff_errors else "pass",
        "Exact submission reference and task/input/proposal digests match",
        f"Shared handoff validation returned {len(handoff_errors)} errors")

    preexecution = not any("run_id" in record or "execution_contract_ref" in record
                           for record in (submission, proposal))
    gaps = proposal["gaps"]
    gap_ids = [gap["gap_id"] for gap in gaps]
    readiness = (proposal["readiness"] in {"needs_inputs", "needs_material_facts"}
                 and any(gap["material"] and "execution" in gap["blocks"] for gap in gaps)
                 and len(gap_ids) == len(set(gap_ids)))
    for field in ("target_policy", "acceptance_rule"):
        policy = proposal[field]
        if policy.get("status") == "pending":
            readiness &= bool(policy["unresolved_gap_ids"]) and set(policy["unresolved_gap_ids"]) <= set(gap_ids)
    add("guidance-preexecution", "pass" if preexecution else "fail",
        "Unapproved guidance has no fabricated run or execution identity",
        "Submission/proposal only" if preexecution else "Run/execution identity is present")
    add("guidance-gaps", "pass" if readiness else "fail",
        "Needs-inputs/material-facts readiness names explicit material execution blockers",
        f"Readiness={proposal['readiness']}; material blocking gaps="
        f"{sum(gap['material'] and 'execution' in gap['blocks'] for gap in gaps)}")
    if type(customer_text) is not str or not customer_text.strip():
        add("guidance-semantic-review", "fail", "Nonempty customer guidance",
            "Customer guidance is empty or invalid")
    elif any(check["status"] != "pass" for check in checks):
        add("guidance-semantic-review", "unavailable", "Review against a valid resolved snapshot",
            "Independent semantic review blocked by snapshot/evidence discrepancies")
    else:
        result = _review(review, customer_text, submission, proposal, resolved)
        add("guidance-semantic-review", **result)
    return checks
