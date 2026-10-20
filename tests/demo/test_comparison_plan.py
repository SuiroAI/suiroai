"""Inspect DSC-60 declared plan adoption without granting scientific approval.

Use the real bounded, symlink-refusing file reader and immutable artifact store.
A matching declaration is evidence of recorded intent only, while missing or
mismatched declarations do not block useful CSV output.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from suiroai.demo.investigation import run_investigation
from suiroai.demo.service import DemoSession, UploadedInput
from suiroai.demo.task import comparison_contract_record, inspect_comparison_plan
from suiroai.integration.artifacts import ArtifactStore
from suiroai.integration.native import NativeRun


DEFINITION = {field: "Explicit engineering definition for " + field for field in
    ("target", "baseline", "primary_metric", "population", "dates", "forecast_horizon", "selection_rule")}


@pytest.mark.parametrize("variant,status", [("missing", "missing"), ("match", "recorded"),
    ("digest", "mismatch"), ("definition", "mismatch"), ("malformed", "invalid"),
    ("schema", "invalid"), ("oversized", "invalid"), ("symlink", "invalid")])
def test_safe_plan_inspection_and_exact_artifact_identity(tmp_path, variant, status):
    root = tmp_path.resolve()
    output = root / "output"
    output.mkdir()
    store = ArtifactStore(root / "store")
    contract = comparison_contract_record(DEFINITION)
    plan = {"comparison_contract": contract, "comparison_contract_sha256": contract["sha256"]}
    if variant == "digest":
        plan["comparison_contract_sha256"] = "0" * 64
    elif variant == "definition":
        plan["comparison_contract"] = dict(contract, provenance="customer_fact")
    raw = b'{' if variant == "malformed" else b'{}' if variant == "schema" else b'x' * (65536 + 1) if variant == "oversized" else json.dumps(plan).encode()
    path = output / "evaluation_plan.json"
    if variant == "symlink":
        outside = root / "elsewhere.json"
        outside.write_bytes(raw)
        path.symlink_to(outside)
    elif variant != "missing":
        path.write_bytes(raw)
    result = inspect_comparison_plan(store, output, contract)
    assert result["status"] == status
    assert result["expected_sha256"] == contract["sha256"]
    assert result["semantic_compliance_verified"] is False
    if variant in {"match", "digest", "definition", "malformed", "schema"}:
        assert store.read_bytes(result["plan_ref"]) == raw
    else:
        assert result["plan_ref"] is None


def test_ordinary_plan_inspection_is_not_requested(tmp_path):
    output = tmp_path.resolve()
    (output / "evaluation_plan.json").symlink_to(output / "unavailable")
    result = inspect_comparison_plan(ArtifactStore(output / "store"), output, None)
    assert result["status"] == "not_requested"
    assert result["plan_ref"] is None


@pytest.mark.parametrize("matching", [True, False])
def test_declared_adoption_never_promotes_verification_or_blocks_csv(tmp_path, matching):
    calls = []

    def backend(*args):
        calls.append(args)
        return SimpleNamespace(status="blocked", message="Captured", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path, backend=backend, comparison_contract=DEFINITION)
    view = session.review("What should I restock?", [UploadedInput(name="sales.csv",
        data=b"Order_Date,Quantity\n2025-11-01,2\n")], continue_without=True)
    session.approve_and_run(view["proposal_digest"])
    contract = comparison_contract_record(DEFINITION)

    class Host:
        def execute(self, **native):
            output = native["cwd"]
            plan = {"comparison_contract": contract,
                "comparison_contract_sha256": contract["sha256"] if matching else "0" * 64}
            (output / "evaluation_plan.json").write_text(json.dumps(plan))
            csv = b"Product_ID,Store_ID,OrderQty\nP,S,2\n"
            (output / "restocking.csv").write_bytes(csv)
            (output / "result.json").write_text(json.dumps({"disposition": "analysis",
                "output_file": "restocking.csv", "output_sha256": sha256(csv).hexdigest()}))
            return NativeRun(outcome="completed")

    stage = run_investigation(*calls[0][:4], tmp_path / "run", calls[0][6], host=Host())
    assert stage["comparison_plan"]["status"] == ("recorded" if matching else "mismatch")
    assert stage["comparison_plan"]["semantic_compliance_verified"] is False
    assert stage["unverified_report_ref"] is not None
    assert stage["output_error"] is None
    assert stage["verified_report_available"] is False
    assert stage["final_policy_frozen"] is False
