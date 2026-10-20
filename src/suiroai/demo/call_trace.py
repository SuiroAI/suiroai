"""Keep compact internal receipts for each demo native model dispatch.

Persist exact outbound UTF-8 prompt bytes before execution, alongside requested
model settings and the released-input manifest. Complete the same local receipt
with native thread/turn/outcome links or a transport exception. This trace aids
DSC-60 workflow debugging; it certifies neither analytical correctness nor model
compliance, and adds no customer-facing notices or approval authority.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import uuid

from suiroai.integration.native_profile import CLI_VERSION, MODEL, SKILL_SHA256


def begin_call_trace(evidence_dir, *, stage, prompt, manifest, trace_dir=None):
    """Write dispatch intent in a sibling, keeping native evidence fresh and empty.

    ``evidence_dir`` is the future NativeHost evidence root. Traces default to
    its sibling named ``<evidence-name>-trace``; replay callers may supply a
    separate ``trace_dir``. Neither file enters the worker output or release.
    """
    native_evidence_dir = Path(evidence_dir).resolve()
    root = Path(trace_dir).resolve() if trace_dir is not None else native_evidence_dir.with_name(native_evidence_dir.name + "-trace")
    if root == native_evidence_dir or root.is_relative_to(native_evidence_dir):
        raise ValueError("Call traces must remain outside fresh native evidence")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    prompt_path, receipt_path = root / "outbound-prompt.txt", root / "call-trace.json"
    data = prompt.encode("utf-8")
    with prompt_path.open("xb") as stream:
        stream.write(data)
    prompt_path.chmod(0o400)
    receipt = {"format": "dsc60-native-call-trace-v1", "stage": stage,
        "requested_model": MODEL, "requested_reasoning_effort": "medium",
        "requested_configuration": {"cli_version": CLI_VERSION,
            "data_plugin": "data-analytics@openai-curated-remote", "data_skill_sha256": SKILL_SHA256,
            "attachment": {"type": "mention", "name": "Data",
                "path": "plugin://data-analytics@openai-curated-remote"}},
        "visibility_limit": "Explicit outbound inputs and exposed native evidence only; hidden/system context is not known.",
        "prompt_path": str(prompt_path), "prompt_sha256": sha256(data).hexdigest(),
        "prompt_bytes": len(data), "released_files": deepcopy(manifest),
        "receipt_path": str(receipt_path), "native_evidence_dir": str(native_evidence_dir),
        "dispatch_status": "prepared",
        "native_execution": None, "native_evidence_files": [], "transport_exception": None}
    _write(receipt)
    return receipt


def finish_call_trace(receipt, *, native=None, error=None):
    """Retain failures as well as successful native links without changing inputs."""
    if sha256(Path(receipt["prompt_path"]).read_bytes()).hexdigest() != receipt["prompt_sha256"]:
        raise ValueError("Outbound prompt changed during native execution")
    result = deepcopy(receipt)
    result["dispatch_status"] = "transport_exception" if error is not None else "returned"
    if error is not None:
        result["transport_exception"] = {"type": type(error).__name__, "message": str(error)}
    if native is not None:
        result["native_execution"] = {"thread_id": native.thread_id, "turn_id": native.turn_id,
            "outcome": native.outcome, "error_code": native.error_code, "message": native.message}
        result["model_usage"] = deepcopy(native.evidence.get("model_usage"))
        thread = native.evidence.get("thread_start", {})
        result["observed_configuration"] = {
            "skill_sha256": native.evidence.get("skill_sha256"),
            "effective_profile_verified": native.evidence.get("effective_profile_verified"),
            "model": thread.get("model"), "model_provider": thread.get("modelProvider"),
            "reasoning_effort": thread.get("reasoningEffort"),
            "instruction_sources": deepcopy(thread.get("instructionSources")),
            "cwd": thread.get("cwd"),
            "runtime_workspace_roots": deepcopy(thread.get("runtimeWorkspaceRoots")),
            "data_attachment": deepcopy(native.evidence.get("attachment")),
            "cli_version": (thread.get("thread") or {}).get("cliVersion"),
            "permission_profile": (thread.get("activePermissionProfile") or {}).get("id")}
    root = Path(receipt["native_evidence_dir"])
    for path in sorted(root.glob("native-*")):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            result["native_evidence_files"].append({"path": str(path),
                "sha256": sha256(data).hexdigest(), "bytes": len(data)})
    _write(result)
    return result


def _write(receipt):
    target = Path(receipt["receipt_path"])
    temporary = target.with_name(".call-trace-" + uuid.uuid4().hex + ".json")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        temporary.chmod(0o600)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
