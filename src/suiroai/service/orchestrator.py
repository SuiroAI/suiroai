"""Read-only orchestration façade over a governed analysis for the demo path.

A live customer run advances :class:`suiroai.parent.workflow.ParentWorkflow` through its seven
stages using a ``StageAdapter`` and a real execution host. That host is the macOS-gated native
Codex/Data integration and is not available on the universal (e.g. OpenShift) deployment, so the
demo and the frontend consume **already-produced, committed evidence** instead: the contract
fixtures in ``examples/contracts/v0.1.0`` (and, later, real run outputs stored identically).

This module therefore does **not** drive a live stage loop. It loads a fixture bundle into a
store (A-PR1's loader), builds the trusted consumer :class:`~suiroai.replenishment.context.Handoff`
over the record graph, determines the run's **terminal outcome** from which records exist, and
exposes the key records (report draft, quantity result, evaluation, proposal) for the
record→view translation layer (A-PR3). Swapping a live ``ParentWorkflow`` run in later is
additive: it produces the same record kinds this façade reads.

Nothing here authorises a parent transition, authenticates evidence or establishes analytical
acceptance. Fixture provenance is ``mock`` and is surfaced, never hidden.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from suiroai.contracts import record_ref
from suiroai.replenishment.context import Handoff, InputError
from .store import load_fixture_bundle, open_store


# Terminal outcomes a consumer/frontend distinguishes. These mirror report_draft.outcome plus the
# pre-execution and in-progress states that have no report yet.
OUTCOME_SUCCESS = "success"
OUTCOME_VALIDATION_FAILURE = "validation_failure"
OUTCOME_EXECUTION_FAILURE = "execution_failure"
OUTCOME_MISSING_INPUTS = "missing_inputs"
OUTCOME_RUNNING = "running"

_REPORT_OUTCOMES = {
    "success": OUTCOME_SUCCESS,
    "validation_failure": OUTCOME_VALIDATION_FAILURE,
    "execution_failure": OUTCOME_EXECUTION_FAILURE,
}


class OrchestratorError(ValueError):
    """The loaded evidence graph is not a recognisable terminal or in-progress analysis."""


class AnalysisView:
    """Read-only view of one analysis's committed evidence.

    Attributes:
        outcome: one of the ``OUTCOME_*`` constants.
        provenance: the bundle's declared provenance (e.g. ``"mock"``).
        notice: the bundle's mock/notice string, surfaced to callers.
        handoff: the trusted :class:`Handoff` over the record graph, or ``None`` for the
            pre-execution ``missing_inputs`` case (which has no execution contract to anchor one).
        records: ``{kind: [ref, ...]}`` index returned by the loader.
    """

    def __init__(self, *, outcome, provenance, notice, handoff, records, store):
        self.outcome = outcome
        self.provenance = provenance
        self.notice = notice
        self.handoff = handoff
        self.records = records
        self._store = store

    @property
    def is_mock(self) -> bool:
        return self.provenance == "mock"

    @property
    def delivery_allowed(self) -> bool:
        """True only when an output_verification record allows delivery (R9).

        A successful run carries an ``output_verification`` with ``decision == 'delivery_allowed'``.
        Failure/validation-failure/running/missing-inputs are never delivery-allowed.
        """
        if self.outcome != OUTCOME_SUCCESS or self.handoff is None:
            return False
        try:
            verification = self.handoff.one("output_verification")
        except InputError:
            return False
        return verification.get("decision") == "delivery_allowed"

    def report_draft(self):
        """The report_draft record, or ``None`` if the run produced none (missing inputs / running)."""
        return self._maybe_one("report_draft")

    def quantity_result(self):
        """The latest quantity_result (order lines), or ``None`` when there are no recommendations."""
        return self._maybe_one("quantity_result")

    def evaluation_result(self):
        """The model comparison record, or ``None`` if the run did not reach comparison."""
        return self._maybe_one("evaluation_result")

    def proposal(self):
        """The task_proposal record (present from readiness onward), or ``None``."""
        return self._maybe_one("task_proposal")

    def submission(self):
        """The submission record (uploaded question + files)."""
        return self._maybe_one("submission")

    def _maybe_one(self, kind):
        if self.handoff is not None:
            try:
                return self.handoff.one(kind)
            except InputError:
                return None
        # No handoff (missing_inputs): read directly from the stored records by kind.
        refs = self.records.get(kind) or []
        if not refs:
            return None
        return self._store.read_record(refs[0])


def _classify(records_index, store) -> str:
    """Determine the terminal outcome from which record kinds are present."""
    report_refs = records_index.get("report_draft") or []
    if report_refs:
        report = store.read_record(report_refs[0])
        mapped = _REPORT_OUTCOMES.get(report.get("outcome"))
        if mapped:
            return mapped
        raise OrchestratorError(f"unrecognised report_draft outcome: {report.get('outcome')!r}")
    if not records_index.get("execution_contract"):
        # No execution contract means the run never started: pre-signoff / missing inputs.
        return OUTCOME_MISSING_INPUTS
    # Execution started but produced no report yet.
    return OUTCOME_RUNNING


def load_analysis(path, *, store_root=None, allow_mock=True) -> AnalysisView:
    """Load a committed evidence bundle and return a read-only :class:`AnalysisView`.

    Args:
        path: a contract fixture bundle (or, later, a real run's record bundle).
        store_root: where to root the backing store; a fresh temp dir is used if omitted.
        allow_mock: permit ``mock`` provenance (fixtures). Real runs set this False so mock
            evidence can never be presented as a real analysis.
    """
    import tempfile

    if store_root is None:
        store_root = Path(tempfile.mkdtemp(prefix="suiroai-analysis-"))
    store = open_store(store_root)
    index = load_fixture_bundle(store, path)

    provenance = index.get("provenance")
    if provenance == "mock" and not allow_mock:
        raise OrchestratorError("mock evidence cannot back a real analysis (allow_mock=False)")

    outcome = _classify(index["records"], store)

    handoff = None
    if index["records"].get("execution_contract"):
        # The whole record graph is the current handoff; external artifact bytes come from the
        # store. parent_confirms accepts a decision that is actually present on the named record
        # (the fixtures are self-consistent committed evidence; this façade makes no new decision).
        records = [store.read_record(ref) for refs in index["records"].values() for ref in refs]
        external_refs = list(index["external_refs"])

        def _read_bytes(ref):
            return store.read_bytes(ref)

        def _parent_confirms(ref, decision):
            try:
                target = store.read_record(ref)
            except Exception:
                return False
            # Confirm the decision object is exactly the one carried on the referenced record.
            for field in ("parent_decision", "parent_review"):
                if target.get(field) == decision:
                    return True
            return False

        handoff = Handoff(records, external_refs, _read_bytes, _parent_confirms,
                          allow_mock=allow_mock)

    return AnalysisView(outcome=outcome, provenance=provenance, notice=index.get("notice"),
                        handoff=handoff, records=index["records"], store=store)
