"""Debug actual adapter control flow with MOCK contract packets, never Data.

Compare the published PR head to this working implementation, then use pdb
breakpoints to observe the fixed private-candidate boundary. No native/model
execution, customer analysis, shared-contract edit or nightly branch access.
"""
from copy import deepcopy
import hashlib
import inspect
import io
import json
from pathlib import Path
import pdb
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests/integration")]
from suiroai.contracts import record_ref
from suiroai.integration import adapter as fixed
from suiroai.integration.artifacts import ArtifactError, _json_bytes
from test_adapter_parent_review import ParentReviewTests

BASELINE = "e02055407d20ec69b7199aef5fb2aba0824ad426"


def baseline_retrieve(module, packet):
    receiver = module.StageAdapter(packet.store, work_root=packet.home / "baseline-attempts",
        parent_permits=lambda _: True, host=packet.host, allow_mock_handoffs=True)
    directory = packet.home / "baseline-output"
    directory.mkdir()
    packet.host.write(directory)
    return receiver._retrieve(packet.request, record_ref(packet.request), "mock", directory,
        packet.records, packet.external_refs, {"published_refs": []},
        lambda code, reason: {"outcome": "execution_failed", "failure": {"error_code": code}})


class BoundaryDebugger(pdb.Pdb):
    def __init__(self):
        super().__init__(stdout=io.StringIO(), readrc=False)
        self.observations = []
        source, start = inspect.getsourcelines(fixed.StageAdapter._review_candidate)
        for offset, line in enumerate(source):
            if "if not decisions and not prior:" in line or "if not isinstance(receipt, dict)" in line:
                self.set_break(str(Path(fixed.__file__).resolve()), start + offset)

    def user_line(self, frame):
        if frame.f_code.co_name == "_review_candidate":
            values = frame.f_locals
            item = {"stage": values["request"]["stage"],
                "checkpoint_paths": [c["json_pointer"] for c in values["decisions"]],
                "prior_authorization_paths": [c["json_pointer"] for c in values["prior"]]}
            if "receipt" in values:
                item["exact_receipt_matches"] = _json_bytes(values["receipt"]) == _json_bytes(values["expected"])
                item["candidate_sha256"] = values["candidate_sha"]
            self.observations.append(item)
        self.set_continue()


def main():
    source = subprocess.check_output(["git", "show", BASELINE + ":src/suiroai/integration/adapter.py"], cwd=ROOT)
    baseline = types.ModuleType("suiroai.integration._dsc26_debug_baseline")
    baseline.__package__ = "suiroai.integration"
    exec(compile(source, "<PR3-e020554-adapter>", "exec"), baseline.__dict__)
    case = ParentReviewTests()
    case.setUp()
    try:
        packet = case.packet()
        try:
            baseline_retrieve(baseline, packet)
        except ValueError as exc:
            preparation_error = str(exc)
        else:
            raise AssertionError("Baseline preparation defect did not reproduce")
        assert preparation_error == "worker cannot author a parent decision"

        packet = case.packet("final_validation_result", recheck=True, review=None)
        old = baseline_retrieve(baseline, packet)
        persisted = packet.store.read_record(record_ref(packet.target))
        forged_actor = persisted["defect_rechecks"][0]["parent_authorization"]["actor"]
        assert old["outcome"] == "completed" and forged_actor == "MOCK-FORGED-PARENT"

        debugger = BoundaryDebugger()
        packet = case.packet()
        new = debugger.runcall(case.execute, packet)
        assert new["outcome"] == "completed" and new["parent_decision"] is None
        assert packet.store.read_record(record_ref(packet.target)) == packet.target

        packet = case.packet("final_validation_result", recheck=True, review=None)
        rejected = debugger.runcall(case.execute, packet)
        assert rejected["failure"]["error_code"] == "integrity_error" and not rejected["output_refs"]
        try:
            packet.store.read_record(record_ref(packet.target))
        except ArtifactError:
            pass
        else:
            raise AssertionError("Fixed adapter published unauthenticated prior permission")
        assert any(row.get("exact_receipt_matches") for row in debugger.observations)
        assert any(row["prior_authorization_paths"] == ["/defect_rechecks/0/parent_authorization"]
            for row in debugger.observations)
        result = {"evidence_mode": "mock_adapter_control_flow_debug", "native_or_model_calls": 0,
            "customer_analysis": False, "shared_contract_changes": False,
            "baseline_commit": BASELINE, "baseline_source_sha256": hashlib.sha256(source).hexdigest(),
            "fixed_source_sha256": hashlib.sha256(Path(fixed.__file__).read_bytes()).hexdigest(),
            "baseline": {"schema_valid_preparation_rejected": preparation_error,
                "forged_nested_prior_authorization_published": True},
            "fixed": {"schema_valid_preparation_accepted_after_trusted_review": True,
                "forged_nested_prior_authorization_rejected_without_publication": True},
            "pdb_boundary_observations": debugger.observations,
            "limitations": "MOCK component packets only. Real Codex/Data invocation evidence remains separate; this does not implement DSC-10 parent policy."}
        path = Path(__file__).with_name("observation.json")
        path.write_bytes((json.dumps(result, indent=2) + "\n").encode())
        print(json.dumps({"baseline_defects_reproduced": 2, "fixed_cases_verified": 2,
            "pdb_boundary_stops": len(debugger.observations), "native_or_model_calls": 0,
            "observation": str(path)}))
    finally:
        case.doCleanups()


if __name__ == "__main__":
    main()
