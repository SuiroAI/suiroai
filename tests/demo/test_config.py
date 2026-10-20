"""Verify trusted Streamlit comparison configuration without native model calls.

Use real sessions and Streamlit reruns to test that operator configuration is
validated before creation and that changed or invalid files revoke approval
and results. Explicit customer download and preview actions stay unchanged.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import json
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from suiroai.demo.config import CONTRACT_ENV, DemoConfigurationError, configured_session, load_comparison_contract
from suiroai.demo.service import DemoSession, UploadedInput
from suiroai.demo.task import approved_task_context


DEFINITION = {field: "Explicit engineering definition for " + field for field in
    ("target", "baseline", "primary_metric", "population", "dates", "forecast_horizon", "selection_rule")}


def test_unset_config_preserves_autonomous_default(tmp_path):
    assert load_comparison_contract({}) is None
    session = configured_session(lambda **kwargs: DemoSession(artifact_root=tmp_path, **kwargs))
    assert session._comparison_contract is None


@pytest.mark.parametrize("variant", ["relative", "empty", "missing", "json", "schema", "null", "oversized", "symlink"])
def test_config_rejects_invalid_controller_files(tmp_path, variant):
    path = tmp_path.resolve() / "contract.json"
    if variant == "relative":
        value = "contract.json"
    elif variant == "empty":
        value = ""
    else:
        value = str(path)
        if variant == "symlink":
            other = path.with_name("other.json")
            other.write_text(json.dumps(DEFINITION))
            path.symlink_to(other)
        elif variant != "missing":
            path.write_text("{" if variant == "json" else "{}" if variant == "schema"
                else "null" if variant == "null" else "x" * 65537)
    with pytest.raises(DemoConfigurationError):
        load_comparison_contract({CONTRACT_ENV: value})


def test_app_loads_real_session_contract_and_changes_revoke_consent_and_result(tmp_path, monkeypatch):
    import streamlit as st
    import suiroai.demo.service as service

    path = tmp_path.resolve() / "contract.json"
    path.write_text(json.dumps(DEFINITION))
    monkeypatch.setenv(CONTRACT_ENV, str(path))
    calls = []

    def backend(*args):
        calls.append(args)
        csv = b"Product_ID,Store_ID,OrderQty\nP,S,2\n"
        ref = args[0].put_bytes("test-config-report", 1, "derived", csv)
        return SimpleNamespace(status="analysis_completed", message="Done", evidence_path=None,
            report_ref=ref, download_bytes=csv, download_name="restocking.csv")

    monkeypatch.setattr(service, "DemoSession", lambda **kwargs: DemoSession(artifact_root=tmp_path,
        backend=backend, context_detector=lambda *_: {"status": "found", "summary": "Weekly buying."}, **kwargs))
    data = b"Order_Date,Quantity\n2025-11-01,2\n"
    monkeypatch.setattr(st, "file_uploader", lambda *_, **__: [SimpleNamespace(name="sales.csv", getvalue=lambda: data)])
    app = AppTest.from_string("from suiroai.demo.app import run_app\nrun_app()").run()
    assert not app.exception
    question = "What should I restock?"
    app.text_area[0].set_value(question).run()
    session = app.session_state["demo_session"]
    view = session.review(question, [UploadedInput(name="sales.csv", data=data)])
    session.approve_and_run(view["proposal_digest"])
    assert approved_task_context(calls[0][2])["comparison_contract"]["definition"] == DEFINITION
    assert session.download() is not None
    app.run()
    assert session.download() is not None  # unchanged config preserves the result

    changed = dict(DEFINITION, baseline="A different explicit engineering baseline")
    path.write_text(json.dumps(changed))
    app.run()
    assert not app.exception
    assert session.download() is None
    assert session.view["status"] == "draft"
    session.approve_and_run(view["proposal_digest"])
    assert len(calls) == 1
    fresh = session.review(question, [UploadedInput(name="sales.csv", data=data)])
    assert fresh["proposal_digest"] != view["proposal_digest"]
    session.approve_and_run(fresh["proposal_digest"])
    assert approved_task_context(calls[1][2])["comparison_contract"]["definition"] == changed
    assert session.download() is not None

    path.write_text("{")
    app.run()
    assert not app.exception
    assert session.download() is None
    assert session.view["status"] == "draft"
    assert len(app.error) == 1
    assert not app.button
    assert session._comparison_contract["definition"] == changed
    assert len(calls) == 2
    monkeypatch.delenv(CONTRACT_ENV)
    app.run()
    assert not app.exception
    assert session._comparison_contract is None
    assert session.download() is None
    session.approve_and_run(fresh["proposal_digest"])
    assert len(calls) == 2


def test_bad_startup_config_does_not_create_a_session(tmp_path, monkeypatch):
    import suiroai.demo.service as service

    path = tmp_path.resolve() / "bad.json"
    path.write_text("{}")
    monkeypatch.setenv(CONTRACT_ENV, str(path))
    monkeypatch.setattr(service, "DemoSession", lambda **_: pytest.fail("Invalid config must stop before construction"))
    app = AppTest.from_string("from suiroai.demo.app import run_app\nrun_app()").run()
    assert not app.exception
    assert len(app.error) == 1
    assert not app.button
    assert "demo_session" not in app.session_state
