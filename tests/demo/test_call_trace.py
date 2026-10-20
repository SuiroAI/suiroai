"""Keep DSC-60 pre-dispatch traces compatible with actual native root policy.

Use the real root validator so mocked hosts cannot hide a nonempty evidence
root regression. Trace identity and native log links remain internal evidence.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from hashlib import sha256
import json
from pathlib import Path

from suiroai.demo.call_trace import begin_call_trace, finish_call_trace
from suiroai.integration.native import NativeRun
from suiroai.integration.native_profile import validate_roots


def test_trace_preserves_real_native_root_contract_and_log_links(tmp_path):
    physical = tmp_path.resolve()
    released, output, evidence = [physical / name for name in ("released", "output", "native")]
    for root in (released, output, evidence):
        root.mkdir()
    prompt = 'Exact original question: "Restock?"\nUnicode: café\n'
    trace = begin_call_trace(evidence, stage="current_process", prompt=prompt, manifest=[])
    assert not list(evidence.iterdir())
    assert validate_roots(released, output, evidence) == (released, output, evidence)
    assert Path(trace["prompt_path"]).read_bytes() == prompt.encode()
    log = evidence / "native-rpc.jsonl"
    log.write_text('{"direction":"sent"}\n')
    attachment = {"type": "mention", "name": "Data", "path": "plugin://data-analytics@openai-curated-remote"}
    sources = [{"path": "/exposed/AGENTS.md", "type": "agents"}]
    native = NativeRun(outcome="completed", thread_id="T", turn_id="U", evidence={
        "attachment": attachment, "thread_start": {"model": "gpt-6.1-sol",
            "reasoningEffort": "medium", "instructionSources": sources,
            "cwd": str(output), "runtimeWorkspaceRoots": [str(output)]}})
    finished = finish_call_trace(trace, native=native)
    observed = finished["observed_configuration"]
    assert observed["reasoning_effort"] == "medium"
    assert observed["instruction_sources"] == sources
    assert observed["cwd"] == str(output)
    assert observed["runtime_workspace_roots"] == [str(output)]
    assert observed["data_attachment"] == attachment
    assert observed["model"] == "gpt-6.1-sol"
    assert finished["native_evidence_files"] == [{"path": str(log), "bytes": log.stat().st_size,
        "sha256": sha256(log.read_bytes()).hexdigest()}]
    assert finished["native_execution"]["thread_id"] == "T"
    assert json.loads(Path(trace["receipt_path"]).read_text()) == finished
