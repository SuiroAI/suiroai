"""One bounded synthetic Codex/Data engineering probe; never customer execution.

Run from a normal Terminal. This is discovery evidence, not a production adapter
or automatic DSC-26 acceptance. It never installs plugins or grants permissions.

Native plugin mention syntax is documented at:
https://learn.chatgpt.com/docs/reference/commands
The mention is a host plugin identity, not an external Data execution API.

Collect bounded real invocation and artifact-retrieval evidence for the
supported Codex/Data boundary using an isolated synthetic engineering task.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import uuid


MARKETPLACE = "openai-curated-remote"
PLUGIN = "data-analytics"
REMOTE_ID = "Plugin_fc9843a6fb34819195d6c7802398a8a7"
VERSION = "1.0.11"
RPC_SECONDS = 20
TURN_SECONDS = 90


class ProbeError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(value):
    """Keep evidence useful without recording common credential fields."""
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if re.search(
            r"token|secret|password|authorization|api.?key|cookie", key, re.I)
            else safe(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [safe(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", value)
        return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
    return value


class NativeRPC:
    def __init__(self, command, cwd, log_path):
        self.log = log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.buffers = {"stdout": b"", "stderr": b""}
        self.responses = {}
        self.terminals = {}
        self.started_turns = []
        self.command_events = {}
        self.errors = []
        self.rejected_requests = []
        self.next_id = 1
        for stream, name in ((self.process.stdout, "stdout"),
                             (self.process.stderr, "stderr")):
            self.selector.register(stream, selectors.EVENT_READ, name)

    def record(self, direction, message):
        self.log.write(json.dumps({"utc": datetime.datetime.now(
            datetime.timezone.utc).isoformat(), "direction": direction,
            "message": safe(message)}, ensure_ascii=False) + "\n")
        self.log.flush()

    def send(self, message):
        self.record("request" if "method" in message else "response", message)
        try:
            self.process.stdin.write((json.dumps(message) + "\n").encode())
            self.process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            raise ProbeError("native_transport_write_failed: " + str(exc)) from exc

    def consume(self, name, line):
        text = line.decode("utf-8", errors="replace")
        if name == "stderr":
            self.record(name, text)
            return
        try:
            message = json.loads(text)
        except ValueError as exc:
            self.record("invalid_stdout", text)
            raise ProbeError("native_stdout_was_not_json") from exc
        if not isinstance(message, dict):
            self.record(name, message)
            raise ProbeError("native_stdout_was_not_rpc_object")
        if "method" in message and "id" in message:
            # Never log parameters of server-initiated requests: auth and
            # attestation payloads may contain credentials. Never approve them.
            summary = {"id": message["id"], "method": message["method"]}
            self.record("server_request_parameters_omitted", summary)
            self.rejected_requests.append(summary)
            self.send({"id": message["id"], "error": {"code": -32601,
                       "message": "Engineering probe rejects server requests; no permissions granted"}})
            return
        self.record(name, message)
        if "id" in message:
            self.responses[message["id"]] = message
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return
        if method == "turn/started":
            self.started_turns.append((params.get("threadId"),
                                       (params.get("turn") or {}).get("id")))
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            self.terminals[(params.get("threadId"), turn.get("id"))] = turn
        elif method == "item/completed":
            item = params.get("item") or {}
            if item.get("type") == "commandExecution":
                self.command_events[(params.get("threadId"),
                    params.get("turnId"), item.get("id"))] = item
        elif method == "error":
            self.errors.append(params)

    def pump(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("native RPC deadline expired")
        for key, _ in self.selector.select(min(0.25, remaining)):
            chunk = os.read(key.fileobj.fileno(), 65536)
            name = key.data
            if not chunk:
                self.selector.unregister(key.fileobj)
                if self.buffers[name]:
                    tail, self.buffers[name] = self.buffers[name], b""
                    self.consume(name, tail)
                continue
            self.buffers[name] += chunk
            if len(self.buffers[name]) > 16 * 1024 * 1024:
                raise ProbeError("native_unterminated_line_exceeded_16MiB")
            while b"\n" in self.buffers[name]:
                line, self.buffers[name] = self.buffers[name].split(b"\n", 1)
                if line:
                    self.consume(name, line)
        if not self.selector.get_map():
            raise ProbeError("native_transport_closed")

    def request(self, method, params, timeout=RPC_SECONDS):
        request_id = self.next_id
        self.next_id += 1
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while request_id not in self.responses:
            self.pump(deadline)
        response = self.responses.pop(request_id)
        if "error" in response:
            raise ProbeError(method + " returned RPC error: " + json.dumps(safe(response["error"])))
        if not isinstance(response.get("result"), dict):
            raise ProbeError(method + " returned no object result")
        return response["result"]

    def wait_terminal(self, thread_id, turn_id, deadline):
        while (thread_id, turn_id) not in self.terminals:
            self.pump(deadline)
        return self.terminals[(thread_id, turn_id)]

    def close(self):
        # A dedicated session allows cleanup of native process descendants too.
        for signum, seconds in ((signal.SIGTERM, 3), (signal.SIGKILL, 3)):
            try:
                os.killpg(self.process.pid, signum)
            except ProcessLookupError:
                break
            try:
                self.process.wait(timeout=seconds)
                break
            except subprocess.TimeoutExpired:
                continue
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.selector.close()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()
        self.record("cleanup", {"exit_code": self.process.poll()})
        self.log.close()


def require(condition, message):
    if not condition:
        raise ProbeError(message)


def select_index(plugin):
    skills = plugin.get("skills") or []
    require(isinstance(skills, list), "plugin_skills_metadata_invalid")
    matches = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        name, path = skill.get("name"), skill.get("path")
        if (isinstance(name, str) and (name == "index" or name.endswith(":index"))) or (
                isinstance(path, str) and "/index/" in path):
            matches.append(skill)
    require(len(matches) == 1, "native_index_skill_not_unique_or_absent")
    skill = matches[0]
    require(skill.get("enabled") is True, "native_index_skill_disabled")
    require(isinstance(skill.get("name"), str) and skill["name"].strip(),
            "native_index_skill_name_absent")
    return skill


def fetch_artifact(stage, output, name):
    source = stage / name
    require(source.is_file() and not source.is_symlink(), "artifact_missing_or_symlink: " + name)
    require(source.resolve().parent == stage.resolve(), "artifact_outside_probe_directory: " + name)
    require(source.stat().st_size <= 2 * 1024 * 1024, "artifact_exceeds_2MiB: " + name)
    data = source.read_bytes()
    destination = output / "fetched" / name
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(data)
    return data, {"source": str(source), "fetched": str(destination),
                  "sha256": digest(data), "bytes": len(data)}


def invokes_calculation(command):
    try:
        tokens = shlex.split(command)
    except (ValueError, TypeError):
        return False
    # Native events may render a shell wrapper around the tool command. Accept
    # only one recognized wrapper containing an exact interpreter invocation;
    # token presence inside echo, a conditional, or a command chain is not proof.
    if (len(tokens) == 3 and Path(tokens[0]).name in ("sh", "bash", "zsh")
            and tokens[1] in ("-c", "-lc")):
        try:
            tokens = shlex.split(tokens[2])
        except ValueError:
            return False
    if not tokens or not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(tokens[0]).name):
        return False
    later = tokens[1:]
    while later and later[0] in ("-u", "-B", "-I", "-E", "-s"):
        later = later[1:]
    return len(later) == 1 and later[0] == "probe_calculation.py"


def run_probe(rpc, stage, output, report):
    report["host"] = rpc.request("initialize", {"clientInfo": {
        "name": "dsc26_bounded_data_engineering_probe", "version": "0.1.0"}})
    rpc.send({"method": "initialized", "params": {}})
    # Under-development metadata API: engineering discovery only, no mutations.
    # In CLI 0.163.0 the remote branch uses this field as an exact backend ID,
    # despite its name. A slug can resolve metadata yet miss installed state.
    # See core-plugins/src/remote.rs at the matching rust-v0.163.0 tag.
    detail = rpc.request("plugin/read", {"remoteMarketplaceName": MARKETPLACE,
                                         "pluginName": REMOTE_ID})
    plugin = detail.get("plugin") or {}
    summary = plugin.get("summary") or {}
    report["plugin_metadata"] = detail
    require(summary.get("remotePluginId") == REMOTE_ID, "unexpected_native_remote_plugin_id")
    require(summary.get("name") == PLUGIN, "unexpected_native_plugin_name")
    require(summary.get("id") == PLUGIN + "@" + MARKETPLACE,
            "unexpected_native_plugin_identity")
    require(summary.get("installed") is True and summary.get("enabled") is True,
            "native_Data_plugin_not_installed_and_enabled")
    require(summary.get("version") == VERSION, "unexpected_native_Data_remote_version")
    if summary.get("localVersion") is not None:
        require(summary["localVersion"] == VERSION, "native_Data_local_version_mismatch")
    require(plugin.get("marketplaceName") == MARKETPLACE, "unexpected_native_marketplace")
    skill = select_index(plugin)
    report["explicit_skill"] = skill
    read = rpc.request("plugin/skill/read", {"remoteMarketplaceName": MARKETPLACE,
        "remotePluginId": summary["remotePluginId"], "skillName": skill["name"]})
    markdown = read.get("contents")
    require(isinstance(markdown, str) and markdown.strip(), "native_Data_skill_Markdown_empty")
    # Evidence copy only: never registered or invoked as a standalone skill.
    (output / "native-index-skill-evidence.txt").write_text(markdown, encoding="utf-8")
    report["native_skill_markdown_sha256"] = digest(markdown.encode())
    path = skill.get("path")
    if isinstance(path, str) and path.strip():
        attachment = {"type": "skill", "name": skill["name"], "path": path}
        report["attachment_mode"] = "returned_skill"
    else:
        # The URI follows documented host mention syntax using verified native
        # plugin identity. Never invent a remote *skill* path or register a copy.
        attachment = {"type": "mention", "name": "Data",
                      "path": "plugin://" + summary["id"]}
        report["attachment_mode"] = "native_plugin_mention"
    report["native_attachment"] = attachment

    csv_bytes = b"product,units\nA,2\nA,3\nB,5\n"
    binding = {"probe_kind": "engineering_synthetic_only", "task_version": 1,
               "input_version": 1, "run_id": str(uuid.uuid4()),
               "input_sha256": digest(csv_bytes)}
    (stage / "probe_input.csv").write_bytes(csv_bytes)
    binding_bytes = (json.dumps(binding, indent=2) + "\n").encode()
    (stage / "binding.json").write_bytes(binding_bytes)
    report["binding"] = binding
    thread = rpc.request("thread/start", {"cwd": str(stage), "approvalPolicy": "never",
                                          "sandbox": "workspace-write"})
    report["thread_start"] = thread
    thread_id = (thread.get("thread") or {}).get("id")
    require(isinstance(thread_id, str) and thread_id, "native_thread_id_absent")
    report["thread_id"] = thread_id
    require(Path(thread.get("cwd", "")).resolve() == stage.resolve(), "native_cwd_mismatch")
    require(thread.get("approvalPolicy") == "never", "native_approval_policy_mismatch")
    require((thread.get("sandbox") or {}).get("type") == "workspaceWrite",
            "native_workspaceWrite_policy_not_effective")
    prompt = (
        f"${skill['name']} Use the attached OpenAI Data skill for one bounded engineering "
        "probe with synthetic data only. This is not customer analysis or a retail task; "
        "there is no customer proposal/approval. Write outputs only in this current directory. "
        "You may read installed Data skill resources to follow the plugin instructions. "
        "Read probe_input.csv and binding.json. Generate a nonempty probe_calculation.py "
        "using Python standard library, then execute it directly with python3 "
        "probe_calculation.py as a separate command in this directory, without shell "
        "chaining or cd. Compute row_count, group_totals (units summed by product), "
        "and total_units from the CSV. Write probe_result.json with exactly those fields "
        "plus binding copied unchanged from binding.json. Derive values from the file. "
        "Keep inputs unchanged. Do not access external connectors, networks, customer "
        "files, unrelated directories, other agents, or install anything. Do not produce a "
        "report/dashboard. Stop after the result and a concise artifact-path response. "
        "If the Data skill or execution is unavailable, state the precise blocker. "
        "Do not claim success for unexecuted code. The entire turn has a 90-second deadline.")
    deadline = time.monotonic() + TURN_SECONDS
    report["model_turn_requested"] = True
    try:
        started = rpc.request("turn/start", {"threadId": thread_id, "input": [
            {"type": "text", "text": prompt},
            attachment]},
            timeout=min(RPC_SECONDS, max(0.01, deadline - time.monotonic())))
        report["turn_start"] = started
        turn_id = (started.get("turn") or {}).get("id")
        require(isinstance(turn_id, str) and turn_id, "native_turn_id_absent")
        report["turn_id"] = turn_id
        terminal = rpc.wait_terminal(thread_id, turn_id, deadline)
    except TimeoutError:
        report["deadline_expired"] = True
        turn_id = report.get("turn_id")
        if not turn_id:
            candidates = [turn for thread, turn in rpc.started_turns if thread == thread_id and turn]
            turn_id = candidates[-1] if candidates else None
            report["turn_id"] = turn_id
        if turn_id:
            interrupt_deadline = time.monotonic() + 10
            try:
                rpc.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id},
                            timeout=max(0.01, interrupt_deadline - time.monotonic()))
                report["terminal"] = rpc.wait_terminal(thread_id, turn_id, interrupt_deadline)
                report["interruption_confirmed"] = report["terminal"].get("status") == "interrupted"
            except (TimeoutError, ProbeError) as exc:
                report["interruption_error"] = str(exc)
        raise ProbeError("turn_deadline_expired_never_success")
    report["terminal"] = terminal
    require(terminal.get("status") == "completed", "native_turn_terminal_not_completed")
    require(not terminal.get("error"), "native_completed_turn_contains_error")
    require(not rpc.rejected_requests, "unexpected_server_requests_were_rejected")

    report["retrieved_thread"] = rpc.request("thread/read", {"threadId": thread_id,
                                                               "includeTurns": False})
    require((report["retrieved_thread"].get("thread") or {}).get("id") == thread_id,
            "retrieved_thread_identity_mismatch")
    entries, cursor, seen_cursors = [], None, set()
    for _ in range(50):
        params = {"threadId": thread_id, "turnId": turn_id, "limit": 100,
                  "sortDirection": "asc"}
        if cursor is not None:
            params["cursor"] = cursor
        page = rpc.request("thread/items/list", params)
        require(isinstance(page.get("data"), list), "native_items_page_invalid")
        entries.extend(page["data"])
        cursor = page.get("nextCursor")
        if cursor is None:
            break
        require(isinstance(cursor, str) and cursor and cursor not in seen_cursors,
                "native_items_cursor_invalid_or_repeated")
        seen_cursors.add(cursor)
    else:
        raise ProbeError("native_items_pagination_limit_exhausted_partial_retrieval")
    require(entries, "native_turn_items_empty")
    require(all(entry.get("turnId") == turn_id for entry in entries), "retrieved_items_turn_mismatch")
    report["retrieved_items"] = entries
    verified_commands = []
    for entry in entries:
        item = entry.get("item") or {}
        event = rpc.command_events.get((thread_id, turn_id, item.get("id")))
        if (item.get("type") == "commandExecution" and item.get("status") == "completed"
                and type(item.get("exitCode")) is int and item["exitCode"] == 0
                and invokes_calculation(item.get("command"))
                and Path(item.get("cwd", "")).resolve() == stage.resolve()
                and event and event.get("status") == "completed" and event.get("exitCode") == 0
                and event.get("command") == item.get("command")):
            verified_commands.append(item["id"])
    report["verified_calculation_command_ids"] = verified_commands
    require(verified_commands, "no_real_successful_calculation_command_in_events_and_retrieved_items")
    artifacts = {}
    report["fetched_artifacts"] = artifacts
    for name in ("probe_input.csv", "binding.json", "probe_calculation.py", "probe_result.json"):
        data, artifacts[name] = fetch_artifact(stage, output, name)
        if name == "probe_input.csv":
            require(data == csv_bytes, "probe_input_changed")
        elif name == "binding.json":
            require(data == binding_bytes, "probe_binding_file_changed")
        elif name == "probe_calculation.py":
            require(data.strip(), "generated_calculation_code_empty")
        else:
            try:
                result = json.loads(data)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ProbeError("generated_result_invalid_JSON") from exc
    require(isinstance(result, dict) and set(result) == {
        "binding", "row_count", "group_totals", "total_units"}, "generated_result_fields_mismatch")
    require(json.dumps(result["binding"], sort_keys=True) == json.dumps(binding, sort_keys=True),
            "generated_result_binding_mismatch")
    require(type(result["row_count"]) is int and result["row_count"] == 3, "row_count_mismatch")
    require(result["group_totals"] == {"A": 5, "B": 5}, "group_totals_mismatch")
    require(type(result["total_units"]) in (int, float) and result["total_units"] == 10,
            "total_units_mismatch")
    require(all(type(value) in (int, float) for value in result["group_totals"].values()),
            "group_totals_not_numeric")
    report["independent_checks_passed"] = True
    report["status"] = "engineering_probe_checks_passed_pending_manual_review"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    del args
    output = Path(tempfile.mkdtemp(prefix="dsc26-data-stage-", dir="/private/tmp"))
    stage = output / "synthetic-stage"
    stage.mkdir()
    report = {"record_kind": "bounded_engineering_probe_not_customer_stage_result",
        "customer_analysis": False, "model_turn_requested": False,
        "manual_review_required": True, "automatic_DSC26_acceptance": False,
        "metadata_api_under_development": ["plugin/read"],
        "status": "integration_blocked", "deadline_expired": False,
        "independent_checks_passed": False,
        "not_fully_tested": ["invalid_code_outcome", "cancellation", "exhausted_limits",
                             "version_propagation_beyond_this_synthetic_binding"],
        "log_redactions": "Common credential fields/strings redacted; server request parameters omitted",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "evidence_directory": str(output), "synthetic_directory": str(stage)}
    rpc = None
    try:
        executable = shutil.which("codex")
        require(executable, "Codex_CLI_missing_from_Terminal_PATH")
        command = [executable, "app-server", "--listen", "stdio://"]
        report["command"] = command
        rpc = NativeRPC(command, stage, output / "native-rpc.jsonl")
        run_probe(rpc, stage, output, report)
    except (ProbeError, TimeoutError, OSError, ValueError, TypeError, KeyError) as exc:
        report["error"] = str(exc)
        if report["model_turn_requested"]:
            report["status"] = "engineering_probe_failed_or_incomplete"
    except KeyboardInterrupt:
        report["error"] = "operator_interrupted_probe"
        report["status"] = "engineering_probe_operator_interrupted"
    finally:
        if rpc:
            report["native_error_events"] = rpc.errors
            report["rejected_server_requests"] = rpc.rejected_requests
            try:
                rpc.close()
            except OSError as exc:
                report["cleanup_error"] = str(exc)
                report["independent_checks_passed"] = False
                report["status"] = "engineering_probe_cleanup_failed"
        report_path = output / "probe-evidence.json"
        report_path.write_text(json.dumps(safe(report), indent=2) + "\n", encoding="utf-8")
    summary = {key: report.get(key) for key in (
        "status", "thread_id", "turn_id", "error", "deadline_expired",
        "independent_checks_passed", "manual_review_required", "automatic_DSC26_acceptance")}
    summary.update({"evidence": str(report_path), "log": str(output / "native-rpc.jsonl"),
                    "terminal_status": (report.get("terminal") or {}).get("status")})
    print(json.dumps(safe(summary), indent=2))
    return 0 if report["independent_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
