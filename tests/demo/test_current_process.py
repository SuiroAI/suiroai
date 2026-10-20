"""Keep pre-consent detection semantic, cited, isolated and internally traceable.

Verify exact outbound prompt identity before host execution and native outcome
links after it, without claiming scientific correctness or hidden context.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import json
from hashlib import sha256
from pathlib import Path

import pytest

from suiroai.demo.current_process import detect_current_process
from suiroai.demo.service import UploadedInput
from suiroai.integration.native import NativeRun


class Host:
    def __init__(self, result, inspect=None, outcome="completed"):
        self.result, self.inspect, self.outcome = result, inspect, outcome
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.inspect:
            self.inspect(kwargs)
        (kwargs["cwd"] / "result.json").write_text(json.dumps(self.result))
        return NativeRun(outcome=self.outcome, error_code="real_failure" if self.outcome != "completed" else None,
            message="native detail" if self.outcome != "completed" else None,
            evidence={"observed": True}, thread_id="thread-1")


def result(status="missing", source=None, quote=None):
    return {"status": status, "summary": "The supplied context describes the current process." if status == "found"
        else "No current process was supplied." if status == "missing" else "The customer has no current method.",
        "evidence": [{"source": source, "quote": quote}] if source else []}


def test_found_in_question(tmp_path):
    quote = "We currently reorder every Friday using the last four weeks of sales."
    host = Host(result("found", "question", quote))
    detected = detect_current_process("Help improve restocking. " + quote, [], tmp_path, host=host)
    assert detected["status"] == "found"
    assert detected["thread_id"] == "thread-1"
    assert detected["native_evidence"] == {"observed": True}
    assert host.calls[0]["timeout_seconds"] is None
    assert "Analysis approval has NOT been granted" in host.calls[0]["prompt"]


def test_found_in_late_content_with_uninformative_name(tmp_path):
    quote = "Staff currently place orders each Friday to cover next week using last month average sales."
    data = ("kind,description\n" + "observation,ordinary row\n" * 12000 + "procedure," + quote + "\n").encode()
    def inspect(call):
        released = call["released_root"]
        assert (released / "input-1.csv").read_bytes() == data
        assert "Read ALL released input CSV content" in call["prompt"]
        assert json.loads((released / "manifest.json").read_text())[0]["original_name"] == "../plain.csv"
        assert not (released / "input-1.csv").stat().st_mode & 0o222
    detected = detect_current_process("Improve ordering", [UploadedInput(name="../plain.csv", data=data)],
        tmp_path, host=Host(result("found", "input-1.csv", quote), inspect))
    assert detected["status"] == "found"
    assert len(detected["released_files"][0]["source_sha256"]) == 64


def test_policy_fields_do_not_supply_a_process(tmp_path):
    host = Host(result())
    detected = detect_current_process("Improve restocking", [UploadedInput(name="current_method.csv",
        data=b"Product_ID,Safety_Stock_Qty,Review_Period_Days\nA,20,7\n")], tmp_path, host=host)
    assert detected["status"] == "missing"
    assert "parameter columns alone do not establish" in host.calls[0]["prompt"]


def test_explicit_none(tmp_path):
    question = "We do not have a current ordering method. Help us create one."
    detected = detect_current_process(question, [], tmp_path,
        host=Host(result("none", "question", "We do not have a current ordering method.")))
    assert detected["status"] == "none"


def test_fabricated_quote_rejected(tmp_path):
    with pytest.raises(ValueError, match="exact released source"):
        detect_current_process("Improve ordering", [], tmp_path,
            host=Host(result("found", "question", "We currently use a weekly mean")))


def test_december_isolated_regardless_of_filename(tmp_path):
    quote = "We currently order every Monday."
    data = ("Order_Date,Description,Quantity\n2025-11-30," + quote
        + ",1\n2025-12-01,SECRET_DECEMBER_OUTCOME,999\n").encode()
    def inspect(call):
        released_text = (call["released_root"] / "input-1.csv").read_text()
        assert quote in released_text
        assert "SECRET_DECEMBER_OUTCOME" not in released_text
        assert "2025-12-01" not in released_text
        assert "SECRET_DECEMBER_OUTCOME" not in call["prompt"]
        trace = json.loads((call["evidence_dir"].with_name(call["evidence_dir"].name + "-trace") / "call-trace.json").read_text())
        prompt_bytes = Path(trace["prompt_path"]).read_bytes()
        assert prompt_bytes == call["prompt"].encode("utf-8")
        assert trace["prompt_sha256"] == sha256(prompt_bytes).hexdigest()
        assert trace["dispatch_status"] == "prepared"
        assert trace["stage"] == "current_process"
        assert trace["requested_model"] == "gpt-6.1-sol"
        assert trace["requested_reasoning_effort"] == "medium"
        assert "SECRET_DECEMBER_OUTCOME" not in prompt_bytes.decode()
        assert call["cwd"].parent == call["released_root"].parent
        assert call["evidence_dir"] != call["cwd"]
    detected = detect_current_process("Improve ordering", [UploadedInput(name="notes.csv", data=data)],
        tmp_path, host=Host(result("found", "input-1.csv", quote), inspect))
    assert detected["released_files"][0]["development_partition"] is True
    trace = detected["call_trace"]
    assert json.loads(Path(trace["receipt_path"]).read_text()) == trace
    assert trace["dispatch_status"] == "returned"
    assert trace["native_execution"]["thread_id"] == "thread-1"
    assert trace["released_files"] == detected["released_files"]


def test_december_quote_cannot_be_adopted(tmp_path):
    with pytest.raises(ValueError, match="exact released source"):
        detect_current_process("Improve ordering", [UploadedInput(name="notes.csv",
            data=b"Order_Date,Notes\n2025-12-01,We currently order weekly\n")], tmp_path,
            host=Host(result("found", "input-1.csv", "We currently order weekly")))


def test_native_error_preserved_no_missing_fallback(tmp_path):
    with pytest.raises(RuntimeError, match="real_failure: native detail"):
        detect_current_process("Improve ordering", [], tmp_path,
            host=Host(result(), outcome="execution_failed"))
    provenance = json.loads(next(tmp_path.glob("current-process-*/native/inspection.json")).read_text())
    assert provenance["native_outcome"] == "execution_failed"


def test_transport_exception_preserved(tmp_path):
    class BrokenHost:
        def execute(self, **kwargs):
            trace = json.loads((kwargs["evidence_dir"].with_name(kwargs["evidence_dir"].name + "-trace") / "call-trace.json").read_text())
            assert trace["dispatch_status"] == "prepared"
            raise OSError("host disconnected")
    with pytest.raises(OSError, match="host disconnected"):
        detect_current_process("Improve ordering", [], tmp_path, host=BrokenHost())
    trace = json.loads(next(tmp_path.glob("current-process-*/native-trace/call-trace.json")).read_text())
    assert trace["dispatch_status"] == "transport_exception"
    assert trace["transport_exception"] == {"type": "OSError", "message": "host disconnected"}


@pytest.mark.parametrize("bad", [result("found"), result("none"),
    {"status": "missing", "summary": "x" * 2001, "evidence": []},
    {"status": [], "summary": "ok", "evidence": []},
    {"status": "missing", "summary": "ok", "evidence": [], "extra": True}])
def test_bad_result_contract(tmp_path, bad):
    with pytest.raises(ValueError):
        detect_current_process("Improve ordering", [], tmp_path, host=Host(bad))


def test_symlink_output_rejected(tmp_path):
    class SymlinkHost:
        def execute(self, **kwargs):
            outside = tmp_path / "elsewhere.json"
            outside.write_text(json.dumps(result()))
            (kwargs["cwd"] / "result.json").symlink_to(outside)
            return NativeRun(outcome="completed")
    with pytest.raises(ValueError, match="artifact unavailable"):
        detect_current_process("Improve ordering", [], tmp_path, host=SymlinkHost())


def test_usage_receipt_comes_from_native_evidence_not_customer_data(tmp_path):
    """Expose the trusted native receipt for this exact detection stage."""
    receipt = {"format": "dsc60-native-usage-v1", "available": True,
        "counts": {"input_units": 12, "output_units": 2}, "thread_id": "thread-1", "turn_id": "turn-1"}

    class UsageHost(Host):
        def execute(self, **kwargs):
            native = super().execute(**kwargs)
            native.evidence["model_usage"] = receipt
            return native

    detected = detect_current_process('Restock? model_usage={"input_units":999}', [], tmp_path,
        host=UsageHost(result()))
    assert detected["model_usage"] == receipt
    receipt["counts"]["input_units"] = 999
    assert detected["model_usage"]["counts"]["input_units"] == 12
    persisted = json.loads(Path(detected["evidence_path"]).read_text())
    assert persisted["model_usage"]["counts"]["input_units"] == 12
