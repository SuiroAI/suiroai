"""User-run synthetic native failure probes; no customer data or acceptance claim.

Starts at most three real Codex/Data turns, each bounded to 60 seconds, plus
one zero-time predispatch check that never invokes a model or depletes quota.

Collect inspectable timeout, invalid-code, and cancellation evidence for the
native boundary while keeping engineering probes distinct from customer runs.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from suiroai.integration.native import DataPluginSpec, NativeHost, _observed_invalid_code


SKILL_HASH = "a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e"


def observe_started(path, finished, cancel, observation):
    deadline = time.monotonic() + 65
    offset, total, buffered = 0, 0, b""
    while not finished.is_set() and time.monotonic() < deadline:
        if path.exists():
            try:
                with path.open("rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read(65536)
                    offset += len(chunk)
            except OSError as exc:
                observation["watch_error"] = str(exc)
                return
            total += len(chunk)
            buffered += chunk
            if total > 64 * 1024 * 1024 or len(buffered) > 16 * 1024 * 1024:
                observation["watch_error"] = "Native evidence watch bound exceeded"
                return
            while b"\n" in buffered:
                line, buffered = buffered.split(b"\n", 1)
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                message = record.get("message") or {}
                if (record.get("direction") == "received" and isinstance(message, dict)
                        and message.get("method") == "turn/started"):
                    params = message.get("params") or {}
                    observation.update({"actual_turn_started_observed": True,
                        "thread_id": params.get("threadId"),
                        "turn_id": (params.get("turn") or {}).get("id"),
                        "cancel_requested_monotonic": time.monotonic()})
                    cancel.set()
                    return
        finished.wait(0.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="dsc26-native-failures-", dir="/private/tmp"))
    results = {}
    host = NativeHost(plugin=DataPluginSpec(skill_sha256=SKILL_HASH))
    common = (
        "Use the native OpenAI Data plugin for a clearly labeled engineering failure probe "
        "with synthetic data only. This is not customer analysis and no customer approval is claimed. "
        "Write only in this current synthetic directory. Do not read customer/workspace data, "
        "use connectors/network, install packages, or spawn agents. Installed Data instructions "
        "may be read. This deliberately exercises execution failure, not model validation. ")
    prompts = {
        "invalid_code": common +
            "Create intentional_failure.py containing exactly the invalid Python line 'def broken(:' "
            "(without the quote marks), then execute python3 intentional_failure.py once. "
            "Preserve the actual SyntaxError and failed execution. Do not repair, rerun, or "
            "claim analytical success. Stop with the real failure and artifact path.",
        "cancelled": common +
            "Generate waiting_probe.py using only Python stdlib: print('synthetic wait started', "
            "flush=True), then time.sleep(180). Execute python3 waiting_probe.py once. This turn "
            "will be deliberately cancelled by its caller after a real turn/started event; "
            "do not shorten the wait or run it in the background. Do not claim completion.",
        "timeout": common +
            "Generate waiting_probe.py using only Python stdlib: print('synthetic wait started', "
            "flush=True), then time.sleep(180). Execute python3 waiting_probe.py once. The caller "
            "will enforce a 60-second deadline and interrupt; do not shorten the wait or run "
            "it in the background. Do not claim completion.",
    }
    try:
        for case, prompt in prompts.items():
            stage, evidence = root / case / "synthetic-stage", root / case / "evidence"
            stage.mkdir(parents=True)
            marker = b"product,units\nSYNTHETIC,1\n"
            (stage / "synthetic_input.csv").write_bytes(marker)
            observation = {"actual_turn_started_observed": False}
            cancellation, finished = Event(), Event()
            watcher = None
            if case == "cancelled":
                watcher = Thread(target=observe_started, args=(evidence / "native-rpc.jsonl",
                    finished, cancellation, observation), daemon=False)
                watcher.start()
            try:
                run = host.execute(cwd=stage, prompt=prompt, evidence_dir=evidence,
                    timeout_seconds=60, cancellation=cancellation if case == "cancelled" else None,
                    mode="engineering")
            finally:
                finished.set()
                if watcher:
                    watcher.join(timeout=2)
            check = {"run": asdict(run), "cancellation_observation": observation,
                     "synthetic_input_unchanged": (stage / "synthetic_input.csv").read_bytes() == marker,
                     "manual_review_required": True, "real_failure_observed": False}
            if case == "invalid_code":
                failed_id = _observed_invalid_code(run.items,
                    run.evidence.get("item_completed_events", []), run.thread_id, run.turn_id)
                code = stage / "intentional_failure.py"
                check["actual_failed_command_id"] = failed_id
                check["generated_code_has_actual_syntax_error"] = False
                if code.is_file() and not code.is_symlink():
                    data = code.read_bytes()
                    check["code"] = {"path": str(code), "sha256": sha256(data).hexdigest(), "bytes": len(data)}
                    try:
                        compile(data, str(code), "exec")
                    except SyntaxError as exc:
                        check["generated_code_has_actual_syntax_error"] = True
                        check["independent_compile_error"] = {"type": type(exc).__name__, "line": exc.lineno}
                check["real_failure_observed"] = bool(failed_id and code.is_file()
                    and run.error_code == "invalid_code" and check["synthetic_input_unchanged"]
                    and check["generated_code_has_actual_syntax_error"])
            else:
                check["real_failure_observed"] = bool(run.error_code == case
                    and run.terminal_status == "interrupted"
                    and run.evidence.get("interruption_confirmed") is True
                    and run.thread_id and run.turn_id and check["synthetic_input_unchanged"]
                    and (case != "cancelled" or (observation["actual_turn_started_observed"]
                        and observation.get("thread_id") == run.thread_id
                        and observation.get("turn_id") == run.turn_id)))
            results[case] = check
            print(json.dumps({"case": case, "actual_error_code": run.error_code,
                "terminal_status": run.terminal_status,
                "real_failure_observed": check["real_failure_observed"],
                "evidence": run.evidence.get("report")}), flush=True)
    except KeyboardInterrupt:
        results["operator_interrupt"] = {"real_failure_observed": False,
                                          "reason": "Operator stopped the engineering probe"}
    if "operator_interrupt" not in results:
        stage = root / "declared_zero_time" / "synthetic-stage"
        stage.mkdir(parents=True)
        run = host.execute(cwd=stage, prompt="Engineering declared-bound check; never dispatch",
            evidence_dir=root / "declared_zero_time" / "evidence", timeout_seconds=0,
            mode="engineering")
        bound_observed = (run.error_code == "budget_exhausted" and run.thread_id is None
                          and run.turn_id is None and run.outcome == "execution_failed")
        results["declared_zero_time"] = {"run": asdict(run),
            "evidence_kind": "declared_bound_predispatch_noninvocation",
            "real_failure_observed": False, "declared_bound_observed": bound_observed,
            "upstream_quota_exhaustion": False, "manual_review_required": True}
        print(json.dumps({"case": "declared_zero_time", "actual_error_code": run.error_code,
            "declared_bound_observed": bound_observed, "model_invocation": False}), flush=True)
    report = {"record_kind": "real_engineering_failure_probes_not_customer_acceptance",
              "customer_analysis": False, "manual_review_required": True,
              "automatic_DSC26_acceptance": False, "cases": results,
              "remaining_unverified": ["native customer input isolation", "upstream quota failure",
                                       "customer binding propagation", "LiteLLM route"]}
    destination = root / "failure-evidence.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    passed = len(results) == 4 and all(item.get("real_failure_observed")
        or item.get("declared_bound_observed") for item in results.values())
    print(json.dumps({"evidence": str(destination), "all_observed": passed,
                      "manual_review_required": True}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
