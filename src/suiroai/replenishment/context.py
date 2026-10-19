"""Consumer checks around the DSC-24 handoff, never parent decisions.

Callbacks are supplied by the trusted parent/application, not model output.
The reference graph validator checks consistency, not checker authenticity.

Bind the candidate and report to the approved inputs and measured evidence
so quantities and claims remain traceable before humanization.

Linear: https://linear.app/gr3enarr0w/issue/DSC-29
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

from suiroai.contracts import VERSION, record_ref, validate_handoff


class InputError(ValueError):
    """Missing, stale, unauthorized or incompatible component input."""


class Handoff:
    """Closed current record graph plus explicitly bound artifact access.

    ``read_bytes(ref)`` returns the original external artifact bytes, and
    ``parent_confirms(record_ref, decision)`` authenticates the exact decision
    against the parent's own ledger. Neither callback is supplied by an LLM.
    Mock handoffs require an explicit development-only opt-in.
    """

    def __init__(self, records, external_refs, read_bytes, parent_confirms,
                 *, allow_mock=False):
        if not callable(read_bytes) or not callable(parent_confirms):
            raise InputError("trusted artifact reader and parent verifier required")
        self.records = deepcopy(list(records))
        self.external_refs = deepcopy(list(external_refs))
        self._read_bytes = read_bytes
        self._parent_confirms = parent_confirms
        self.allow_mock = allow_mock is True
        self.validate()

    def validate(self, extra=()):
        records = self.records + list(extra)
        if not self.allow_mock and any(
                r.get("provenance") == "mock"
                for r in records + self.external_refs):
            raise InputError("mock handoffs require allow_mock=True; no real acceptance")
        errors = validate_handoff(records, self.external_refs)
        if errors:
            raise InputError("invalid handoff: " + "; ".join(errors[:8]))

    def one(self, kind):
        matches = [r for r in self.records if r["kind"] == kind]
        if kind == "quantity_result" and matches:
            return deepcopy(max(matches, key=lambda r: r["artifact_version"]))
        if len(matches) != 1:
            raise InputError(f"exactly one current {kind} required")
        return deepcopy(matches[0])

    def record(self, ref):
        matches = [r for r in self.records if record_ref(r) == ref]
        if len(matches) != 1:
            raise InputError("exact record reference is absent or changed")
        return deepcopy(matches[0])

    def read(self, ref):
        if ref not in self.external_refs:
            raise InputError("artifact is outside the declared external allowlist")
        data = self._read_bytes(deepcopy(ref))
        if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise InputError("artifact bytes do not match immutable reference")
        return data

    def authorize(self, record, decision_field, permitted_decisions):
        self.record(record_ref(record))
        decision = record.get(decision_field)
        if not decision or decision["decision"] not in permitted_decisions:
            raise InputError("parent checkpoint does not authorize this operation")
        if self._parent_confirms(deepcopy(record_ref(record)), deepcopy(decision)) is not True:
            raise InputError("exact parent decision is unauthenticated")
        return deepcopy(decision)

    def envelope(self, kind, artifact_id, version=1):
        execution = self.one("execution_contract")
        return {
            "kind": kind, "schema_version": VERSION,
            "artifact_id": artifact_id, "artifact_version": version,
            "provenance": "mock" if execution["provenance"] == "mock" else "derived",
            "binding": deepcopy(execution["binding"]), "run_id": execution["run_id"],
            "execution_contract_ref": record_ref(execution),
        }

    def finish(self, record):
        self.validate([record])
        return deepcopy(record)
