"""Bounded native Codex/Data transport; no analytical or parent workflow logic.

Customer dispatch fails closed pending exercised native input isolation. Explicit
engineering mode can exercise the demonstrated host with synthetic inputs only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import subprocess
from threading import Event
import time
from typing import Literal


@dataclass(frozen=True)
class DataPluginSpec:
    plugin_id: str = "data-analytics@openai-curated-remote"
    remote_plugin_id: str = "Plugin_fc9843a6fb34819195d6c7802398a8a7"
    version: str = "1.0.11"
    skill_name: str = "index"
    skill_sha256: str | None = None


@dataclass
class NativeRun:
    outcome: str = "execution_failed"
    error_code: str | None = None
    message: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    terminal_status: str | None = None
    items: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    mode: str = "customer"


class _Stop(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _safe(value):
    if isinstance(value, dict):
        if value.get("type") == "reasoning":
            value = {**value, "content": "[RAW REASONING OMITTED]"}
        return {key: ("[REDACTED]" if re.search(
            r"token|secret|password|authorization|api.?key|cookie", key, re.I)
            else _safe(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", value)
        return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
    return value


def _check(deadline, cancellation=None):
    if cancellation is not None and cancellation.is_set():
        raise _Stop("cancelled", "Parent cancelled the native operation")
    if time.monotonic() >= deadline:
        raise _Stop("timeout", "Native operation exceeded its finite deadline")


def _host_error(error):
    text = json.dumps(error, ensure_ascii=False)
    if re.search(r"UsageLimitExceeded|ContextWindowExceeded", text, re.I):
        return "budget_exhausted"
    return "runtime_error"


def _python_invocation(command):
    """Recognize direct Python, or the observed exact printf/write then Python."""
    try:
        outer = shlex.split(command)
        if (len(outer) == 3 and Path(outer[0]).name in ("sh", "bash", "zsh")
                and outer[1] in ("-c", "-lc")):
            command = outer[2]
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>\n")
        lexer.whitespace, lexer.whitespace_split, lexer.commenters = " \t\r", True, ""
        tokens = list(lexer)
    except (TypeError, ValueError):
        return None
    if (len(tokens) == 8 and tokens[0] == "printf" and tokens[1] == "%s\\n"
            and "\n" not in tokens[2] and tokens[3] == ">" and tokens[5] == "\n"
            and tokens[4] == tokens[7]):
        tokens = tokens[6:]
    # No pipelines, conditional masks, quoted fake commands, or extra commands.
    if (len(tokens) < 2 or not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(tokens[0]).name)
            or any(token in (";", "&", "&&", "|", "||", ">", ">>", "<", "\n") for token in tokens)):
        return None
    return tuple(tokens)


def _matched_commands(items, events, thread_id, turn_id):
    observed = {(event.get("threadId"), event.get("turnId"),
                 (event.get("item") or {}).get("id")): event.get("item") or {}
                for event in events}
    commands = []
    for entry in items:
        item = entry.get("item") or {}
        event = observed.get((thread_id, turn_id, item.get("id")))
        if (entry.get("turnId") != turn_id or item.get("type") != "commandExecution" or not event
                or type(item.get("exitCode")) is not int
                or event.get("exitCode") != item["exitCode"]
                or event.get("command") != item.get("command")
                or item.get("status") not in ("completed", "failed")
                or event.get("status") != item.get("status")):
            continue
        output = item.get("aggregatedOutput")
        if not isinstance(output, str) or event.get("aggregatedOutput") != output:
            continue
        commands.append(item)
    return commands


def _observed_invalid_code(items, events, thread_id, turn_id):
    """Require actual paired Python failure, allowing a later successful rerun."""
    commands = _matched_commands(items, events, thread_id, turn_id)
    for index, item in enumerate(commands):
        invocation = _python_invocation(item.get("command", ""))
        if item["exitCode"] == 0 or invocation is None:
            continue
        if any(later["exitCode"] == 0 and _python_invocation(later.get("command", "")) == invocation
               for later in commands[index + 1:]):
            continue
        if re.search(r"(?:^|\n)(?:\s*)?(?:SyntaxError|IndentationError|TabError):", item["aggregatedOutput"]):
            return item["id"]
    return None


class _Transport:
    """One stdio connection with finite RPC, output and cleanup bounds."""

    def __init__(self, executable, cwd, log):
        self.log = log
        self.log_bytes = 0
        self.recording_exhausted = False
        self.process = subprocess.Popen(
            [executable, "app-server", "--listen", "stdio://"], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.buffers = {"stdout": b"", "stderr": b""}
        self.responses = {}
        self.terminals = {}
        self.started = []
        self.events = []
        self.rejected_requests = []
        self.errors = []
        self.counter = 0
        for stream, name in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
            self.selector.register(stream, selectors.EVENT_READ, name)

    def record(self, direction, message, control=False):
        if getattr(self, "recording_exhausted", False):
            if not control or self.log_bytes >= 64 * 1024 * 1024 + 65536:
                return
            # Reserve a small control receipt without retaining bulk payloads.
            message = {"method": message.get("method"), "id": message.get("id"),
                       "bulk_omitted_after_evidence_limit": True}
        encoded = json.dumps({"monotonic": time.monotonic(), "direction": direction,
                              "message": _safe(message)}, ensure_ascii=False) + "\n"
        encoded_size = len(encoded.encode())
        if not control and self.log_bytes + encoded_size > 64 * 1024 * 1024:
            self.recording_exhausted = True
            raise _Stop("budget_exhausted", "Native evidence exceeded the 64 MiB transport bound")
        self.log_bytes += encoded_size
        self.log.write(encoded)
        self.log.flush()

    def send(self, message):
        self.record("sent", message, control=message.get("method") == "turn/interrupt")
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def consume(self, name, line):
        if name == "stderr":
            self.record(name, line.decode(errors="replace"))
            return
        try:
            message = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _Stop("runtime_error", "Native stdout was not JSON RPC") from exc
        if not isinstance(message, dict):
            raise _Stop("runtime_error", "Native stdout was not an RPC object")
        if "method" in message and "id" in message:
            # Omit all server request parameters, including auth/attestation.
            identity = {key: message[key] for key in ("method", "id")}
            self.record("server_request_parameters_omitted", identity)
            self.rejected_requests.append(identity)
            self.send({"id": message["id"], "error": {"code": -32601,
                "message": "Native adapter rejects server requests; no permission granted"}})
            return
        method, params = message.get("method"), message.get("params") or {}
        if method == "item/reasoning/textDelta":
            self.record("received_reasoning_content_omitted", {"method": method})
            return
        self.record("received", message, control=("id" in message or method == "turn/completed")
                    and getattr(self, "recording_exhausted", False))
        if "id" in message:
            self.responses[message["id"]] = message
        if not isinstance(params, dict):
            return
        if method == "turn/started":
            self.started.append((params.get("threadId"), (params.get("turn") or {}).get("id")))
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            self.terminals[(params.get("threadId"), turn.get("id"))] = turn
        elif method == "item/completed":
            self.events.append(params)
        elif method == "error":
            self.errors.append(params)

    def pump(self, deadline, cancellation=None):
        _check(deadline, cancellation)
        for key, _ in self.selector.select(min(0.1, max(0, deadline - time.monotonic()))):
            name = key.data
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                self.selector.unregister(key.fileobj)
                if self.buffers[name]:
                    tail, self.buffers[name] = self.buffers[name], b""
                    self.consume(name, tail)
                continue
            self.buffers[name] += chunk
            if len(self.buffers[name]) > 16 * 1024 * 1024:
                raise _Stop("budget_exhausted", "Native RPC line exceeded 16 MiB")
            while b"\n" in self.buffers[name]:
                line, self.buffers[name] = self.buffers[name].split(b"\n", 1)
                if line:
                    self.consume(name, line)
        if not self.selector.get_map():
            raise _Stop("runtime_error", "Native app-server closed the transport")

    def request(self, method, params, deadline, cancellation=None):
        _check(deadline, cancellation)
        self.counter += 1
        request_id = self.counter
        self.send({"id": request_id, "method": method, "params": params})
        rpc_deadline = min(deadline, time.monotonic() + 20)
        while request_id not in self.responses:
            self.pump(rpc_deadline, cancellation)
        response = self.responses.pop(request_id)
        if "error" in response:
            raise _Stop(_host_error(response["error"]),
                        method + " failed: " + json.dumps(_safe(response["error"])))
        result = response.get("result")
        if not isinstance(result, dict):
            raise _Stop("runtime_error", method + " returned no object result")
        return result

    def wait_terminal(self, thread_id, turn_id, deadline, cancellation=None):
        while (thread_id, turn_id) not in self.terminals:
            self.pump(deadline, cancellation)
        return self.terminals[(thread_id, turn_id)]

    def close(self):
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=3)
        self.selector.close()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


class NativeHost:
    def __init__(self, executable="codex", plugin=None):
        self.executable = str(executable)
        self.plugin = plugin or DataPluginSpec()

    def _inventory(self, executable, cwd, deadline, cancellation):
        _check(deadline, cancellation)
        try:
            result = subprocess.run([executable, "plugin", "list", "--json"], cwd=cwd,
                capture_output=True, timeout=min(20, max(0.01, deadline - time.monotonic())))
        except subprocess.TimeoutExpired as exc:
            raise _Stop("timeout", "Native installed-plugin inventory timed out") from exc
        _check(deadline, cancellation)
        if result.returncode:
            raise _Stop("plugin_unavailable", "Native installed-plugin inventory failed: "
                        + result.stderr.decode(errors="replace"))
        try:
            inventory = json.loads(result.stdout)
        except ValueError as exc:
            raise _Stop("plugin_unavailable", "Native plugin inventory was not JSON") from exc
        entries = inventory.get("installed", []) if isinstance(inventory, dict) else []
        matches = [entry for entry in entries if isinstance(entry, dict)
                   and entry.get("pluginId") == self.plugin.plugin_id]
        if len(matches) != 1:
            raise _Stop("plugin_unavailable", "Exact Data identity absent/ambiguous in native installed inventory")
        entry = matches[0]
        if entry.get("installed") is not True or entry.get("enabled") is not True:
            raise _Stop("plugin_unavailable", "Native Data plugin is not installed and enabled")
        if (entry.get("version") != self.plugin.version
                or (entry.get("source") or {}).get("id") != self.plugin.remote_plugin_id):
            raise _Stop("integrity_error", "Native Data version or remote identity differs from pinned specification")
        return entry

    def execute(self, *, cwd: Path, prompt: str, evidence_dir: Path,
                timeout_seconds: float, cancellation: Event | None = None,
                mode: Literal["customer", "engineering"] = "customer") -> NativeRun:
        """Run one stage; engineering callers must supply synthetic data only.

        No boolean can attest customer isolation. This implementation blocks all
        customer dispatch until native release-only isolation has been exercised.
        """
        run = NativeRun(mode=mode)
        evidence_dir = Path(evidence_dir)
        transport = None
        deadline = time.monotonic()
        try:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            run.evidence = {"mode": mode, "customer_isolation_verified": False,
                "automatic_acceptance": False, "log": str(evidence_dir / "native-rpc.jsonl")}
            if mode not in ("customer", "engineering"):
                raise _Stop("integrity_error", "Unknown native dispatch mode")
            if mode == "customer":
                raise _Stop("unsupported_integration",
                            "Customer dispatch blocked: released-input-only native isolation is not yet exercised")
            if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (float, int))
                    or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
                raise _Stop("budget_exhausted", "Native execution requires positive finite remaining time")
            deadline = time.monotonic() + timeout_seconds
            _check(deadline, cancellation)
            cwd = Path(cwd).resolve(strict=True)
            if not cwd.is_dir() or not isinstance(prompt, str) or not prompt.strip():
                raise _Stop("integrity_error", "Native cwd and bounded stage prompt are required")
            executable = shutil.which(self.executable)
            if executable is None:
                raise _Stop("unsupported_integration", "Codex executable is unavailable")
            inventory = self._inventory(executable, cwd, deadline, cancellation)
            run.evidence["native_inventory"] = inventory
            run.evidence["executable"] = executable
            with (evidence_dir / "native-rpc.jsonl").open("w", encoding="utf-8") as log:
                transport = _Transport(executable, cwd, log)
                try:
                    run.evidence["host"] = transport.request("initialize", {"clientInfo": {
                        "name": "suiroai_dsc26_native", "version": "0.1.0"}}, deadline, cancellation)
                    transport.send({"method": "initialized", "params": {}})
                    marketplace = self.plugin.plugin_id.rsplit("@", 1)[-1]
                    skill = transport.request("plugin/skill/read", {
                        "remoteMarketplaceName": marketplace,
                        "remotePluginId": self.plugin.remote_plugin_id,
                        "skillName": self.plugin.skill_name}, deadline, cancellation)
                    markdown = skill.get("contents")
                    if not isinstance(markdown, str) or not markdown.strip():
                        raise _Stop("plugin_unavailable", "Native Data skill contents unavailable")
                    skill_hash = sha256(markdown.encode()).hexdigest()
                    run.evidence["skill_sha256"] = skill_hash
                    if self.plugin.skill_sha256 is not None and skill_hash != self.plugin.skill_sha256:
                        raise _Stop("integrity_error", "Native Data skill hash differs from pinned specification")
                    skill_path = evidence_dir / "native-skill-evidence.txt"
                    skill_path.write_text(markdown, encoding="utf-8")
                    run.evidence["skill_evidence"] = str(skill_path)
                    thread = transport.request("thread/start", {"cwd": str(cwd),
                        "approvalPolicy": "never", "sandbox": "workspace-write"}, deadline, cancellation)
                    run.thread_id = (thread.get("thread") or {}).get("id")
                    if not run.thread_id:
                        raise _Stop("runtime_error", "Native thread identity missing")
                    run.evidence["thread_start"] = thread
                    if (Path(thread.get("cwd", "")).resolve() != cwd
                            or thread.get("approvalPolicy") != "never"
                            or (thread.get("sandbox") or {}).get("type") != "workspaceWrite"
                            or (thread.get("sandbox") or {}).get("networkAccess") is not False):
                        raise _Stop("integrity_error", "Native engineering cwd/approval/sandbox acknowledgement mismatch")
                    attachment = {"type": "mention", "name": "Data",
                                  "path": "plugin://" + self.plugin.plugin_id}
                    run.evidence["attachment"] = attachment
                    started = transport.request("turn/start", {"threadId": run.thread_id,
                        "input": [{"type": "text", "text": prompt}, attachment]},
                        deadline, cancellation)
                    run.turn_id = (started.get("turn") or {}).get("id")
                    if not run.turn_id:
                        raise _Stop("runtime_error", "Native turn identity missing")
                    terminal = transport.wait_terminal(run.thread_id, run.turn_id, deadline, cancellation)
                    run.terminal_status = terminal.get("status")
                    run.evidence["terminal"] = terminal
                    if run.terminal_status != "completed" or terminal.get("error"):
                        error = terminal.get("error") or terminal
                        raise _Stop("cancelled" if run.terminal_status == "interrupted" else _host_error(error),
                                    "Native turn did not complete: " + json.dumps(_safe(error)))
                    if transport.rejected_requests:
                        raise _Stop("runtime_error", "Unexpected native server requests were rejected")
                    read = transport.request("thread/read", {"threadId": run.thread_id,
                        "includeTurns": False}, deadline, cancellation)
                    if (read.get("thread") or {}).get("id") != run.thread_id:
                        raise _Stop("integrity_error", "Retrieved native thread identity differs")
                    run.evidence["retrieved_thread"] = read
                    cursor, cursors = None, set()
                    for _ in range(50):
                        params = {"threadId": run.thread_id, "turnId": run.turn_id,
                                  "limit": 100, "sortDirection": "asc"}
                        if cursor is not None:
                            params["cursor"] = cursor
                        page = transport.request("thread/items/list", params, deadline, cancellation)
                        entries = page.get("data")
                        if not isinstance(entries, list) or any(
                                not isinstance(entry, dict) or entry.get("turnId") != run.turn_id for entry in entries):
                            raise _Stop("integrity_error", "Native item page shape or turn binding differs")
                        run.items.extend(entries)
                        cursor = page.get("nextCursor")
                        if cursor is None:
                            break
                        if not isinstance(cursor, str) or not cursor or cursor in cursors:
                            raise _Stop("integrity_error", "Native item cursor is invalid/repeated")
                        cursors.add(cursor)
                    else:
                        raise _Stop("budget_exhausted", "Native item pagination limit exhausted; retrieval incomplete")
                    if not run.items:
                        raise _Stop("integrity_error", "Native turn history retrieval is empty")
                    failed_code = _observed_invalid_code(run.items, transport.events, run.thread_id, run.turn_id)
                    if failed_code:
                        run.evidence["invalid_code_command_id"] = failed_code
                        raise _Stop("invalid_code", "Matching native command/history contains an actual Python syntax failure")
                    commands = _matched_commands(run.items, transport.events, run.thread_id, run.turn_id)
                    run.evidence["diagnostic_failed_command_ids"] = [
                        item["id"] for item in commands if item["exitCode"] != 0]
                    if commands and commands[-1]["exitCode"] != 0:
                        raise _Stop("runtime_error", "Native turn completed with a final failed command and no subsequent correction")
                    # A completed native turn is not analytical acceptance.
                    # Historical failures remain diagnostic; adapter/parent
                    # checks must establish that retrieved outputs are valid.
                    run.outcome = "completed"
                except _Stop as exc:
                    if run.terminal_status not in ("completed", "failed", "interrupted"):
                        self._interrupt(transport, run)
                    raise
                except BaseException:
                    if run.terminal_status not in ("completed", "failed", "interrupted"):
                        self._interrupt(transport, run)
                    raise
                finally:
                    run.evidence["item_completed_events"] = transport.events
                    run.evidence["native_error_events"] = transport.errors
                    run.evidence["rejected_server_requests"] = transport.rejected_requests
                    run.evidence["evidence_retention_truncated"] = getattr(transport, "recording_exhausted", False)
                    transport.close()
                    transport = None
        except _Stop as exc:
            run.outcome, run.error_code, run.message = "execution_failed", exc.code, str(exc)
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            run.outcome, run.error_code, run.message = "execution_failed", "runtime_error", str(exc)
        finally:
            if transport is not None:
                try:
                    transport.close()
                except (OSError, subprocess.SubprocessError) as exc:
                    run.outcome, run.error_code, run.message = "execution_failed", "runtime_error", str(exc)
            try:
                report = evidence_dir / "native-run.json"
                run.evidence["report"] = str(report)
                report.write_text(json.dumps(_safe(asdict(run)), indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                run.outcome, run.error_code, run.message = "execution_failed", "runtime_error", str(exc)
        return run

    @staticmethod
    def _interrupt(transport, run):
        if not run.thread_id:
            return
        if not run.turn_id:
            candidates = [turn for thread, turn in transport.started if thread == run.thread_id and turn]
            run.turn_id = candidates[-1] if candidates else None
        if not run.turn_id:
            run.evidence["interruption_confirmed"] = False
            run.evidence["interruption_error"] = "Native turn ID unavailable after interrupted start"
            return
        deadline = time.monotonic() + 10
        try:
            transport.request("turn/interrupt", {"threadId": run.thread_id, "turnId": run.turn_id}, deadline)
            terminal = transport.wait_terminal(run.thread_id, run.turn_id, deadline)
            run.terminal_status = terminal.get("status")
            run.evidence["terminal"] = terminal
            run.evidence["interruption_confirmed"] = run.terminal_status == "interrupted"
        except (_Stop, OSError) as exc:
            run.evidence["interruption_confirmed"] = False
            run.evidence["interruption_error"] = str(exc)
