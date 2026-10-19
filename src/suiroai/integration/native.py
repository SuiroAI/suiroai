"""Bounded native Codex/Data transport; no analytical or parent workflow logic.

Customer stages use the exercised named permission profile. Engineering mode
without released_root retains legacy synthetic-only probe compatibility.

Support invocation and evidence retrieval through the demonstrated native
Codex/Data interface, with inspectable timeout and invalid-code outcomes.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
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
import tomllib
import uuid
from typing import Literal

from . import native_profile as policy
from .artifacts import read_stage_file


@dataclass(frozen=True)
class DataPluginSpec:
    plugin_id: str = "data-analytics@openai-curated-remote"
    remote_plugin_id: str = "Plugin_fc9843a6fb34819195d6c7802398a8a7"
    version: str = "1.0.11"
    skill_name: str = "index"
    skill_sha256: str | None = policy.SKILL_SHA256


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


_Stop = policy.NativePolicyError
_safe = policy.sanitize
_check = policy.check


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
                or event.get("cwd") != item.get("cwd")
                or item.get("status") not in ("completed", "failed")
                or event.get("status") != item.get("status")):
            continue
        output = item.get("aggregatedOutput")
        if output is not None and not isinstance(output, str):
            continue
        if event.get("aggregatedOutput") != output:
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
        if isinstance(item.get("aggregatedOutput"), str) and re.search(
                r"(?:^|\n)(?:\s*)?(?:SyntaxError|IndentationError|TabError):", item["aggregatedOutput"]):
            return item["id"]
    return None


def _matched_file_changes(items, events, thread_id, turn_id, cwd):
    """Canonical paired writes plus actual bounded output bytes, never prose."""
    observed = {(event.get("threadId"), event.get("turnId"), (event.get("item") or {}).get("id")):
        event.get("item") or {} for event in events}
    receipts, total = [], 0
    for entry in items:
        item = entry.get("item") or {}
        event = observed.get((thread_id, turn_id, item.get("id")))
        changes = item.get("changes")
        if (entry.get("turnId") != turn_id or item.get("type") != "fileChange" or not event
                or item.get("status") != "completed" or event.get("status") != "completed"
                or not isinstance(changes, list) or not 0 < len(changes) <= 100 or event.get("changes") != changes):
            continue
        measured = []
        for change in changes:
            if (not isinstance(change, dict) or not isinstance(change.get("path"), str)
                    or not isinstance(change.get("kind"), dict)
                    or change["kind"].get("type") not in {"add", "update"}):
                continue
            path = Path(change["path"])
            if not path.is_absolute() or not path.is_relative_to(cwd):
                continue
            try:
                relative = str(path.relative_to(cwd))
                data = read_stage_file(cwd, relative, max_bytes=16 * 1024 * 1024)
            except (ValueError, OSError):
                continue
            total += len(data)
            if total > 64 * 1024 * 1024:
                raise _Stop("budget_exhausted", "Native file-change receipt bytes exceed 64 MiB")
            measured.append({"relative_path": relative, "bytes": len(data), "sha256": sha256(data).hexdigest()})
        if measured:
            receipts.append({"item_id": item["id"], "files": measured})
    return receipts


class _Transport:
    """One stdio connection with finite RPC, output and cleanup bounds."""

    def __init__(self, executable, cwd, log, *, config_overrides=None):
        self.log = log
        self.log_bytes = 0
        self.recording_exhausted = False
        overrides = [] if config_overrides is None else config_overrides
        if not isinstance(overrides, list) or any(not isinstance(value, str) for value in overrides):
            raise ValueError("Native config overrides must be a list of literal key=value strings")
        command = [executable]
        for value in overrides:
            command.extend(["-c", value])
        command.extend(["app-server", "--listen", "stdio://"])
        self.process = subprocess.Popen(
            command, cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.buffers = {"stdout": b"", "stderr": b""}
        self.responses = {}
        self.received_bytes = 0
        self.receiving_exhausted = False
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
            if not control or self.log_bytes >= policy.LOG_LIMIT + 65536:
                return
            # Reserve a small control receipt without retaining bulk payloads.
            message = {"method": message.get("method"), "id": message.get("id"),
                       "bulk_omitted_after_evidence_limit": True}
        encoded = json.dumps({"monotonic": time.monotonic(), "direction": direction,
                              "message": policy.project_message(message)}, ensure_ascii=False) + "\n"
        encoded_size = len(encoded.encode())
        if not control and self.log_bytes + encoded_size > policy.LOG_LIMIT:
            self.recording_exhausted = True
            raise _Stop("budget_exhausted", "Native evidence exceeded the 8 MiB transport bound")
        self.log_bytes += encoded_size
        self.log.write(encoded)
        self.log.flush()

    def send(self, message):
        self.record("sent", message, control=message.get("method") == "turn/interrupt")
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def consume(self, name, line):
        if name == "stderr":
            self.record(name, {"content_omitted": True, "bytes": len(line), "sha256": sha256(line).hexdigest()})
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
            self.received_bytes += len(chunk)
            wire_limit = 64 * 1024 * 1024
            if self.received_bytes > wire_limit + (65536 if self.receiving_exhausted else 0):
                self.receiving_exhausted = True
                raise _Stop("budget_exhausted", "Native incoming transport exceeded 64 MiB")
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
        receipt = {}
        _, selected = policy.bounded_plugin_inventory(executable, cwd,
            min(deadline, time.monotonic() + 20), receipt, self.plugin, cancellation)
        return selected

    def execute(self, *, cwd: Path, prompt: str, evidence_dir: Path,
                timeout_seconds: float, cancellation: Event | None = None,
                mode: Literal["customer", "engineering"] = "customer",
                released_root: Path | None = None) -> NativeRun:
        """One native turn; approval and task validation belong to StageAdapter.

        Customer calls must use disjoint physical released/output/evidence roots.
        No caller attestation substitutes for native config/profile checks.
        All discovery, execution and retrieval consume the same stage deadline.
        """
        run = NativeRun(mode=mode)
        evidence_dir = Path(evidence_dir)
        transport = None
        evidence_allowed = False
        deadline = time.monotonic()
        strict = released_root is not None
        try:
            if mode not in ("customer", "engineering"):
                raise _Stop("integrity_error", "Unknown native dispatch mode")
            if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (float, int))
                    or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
                raise _Stop("budget_exhausted", "Native execution requires positive finite remaining time")
            deadline = time.monotonic() + timeout_seconds
            _check(deadline, cancellation)
            if mode == "customer" and not strict:
                raise _Stop("unsupported_integration", "Customer dispatch requires a released-input root")
            if strict:
                released_root, cwd, evidence_dir = policy.validate_roots(released_root, cwd, evidence_dir)
                policy.validate_supported_plugin(self.plugin)
            else:
                cwd = Path(cwd).resolve(strict=True)
            if not cwd.is_dir() or not isinstance(prompt, str) or not prompt.strip():
                raise _Stop("integrity_error", "Native cwd and bounded stage prompt are required")
            if len(prompt.encode()) > 2 * 1024 * 1024:
                raise _Stop("budget_exhausted", "Native stage prompt exceeds 2 MiB")
            evidence_dir.mkdir(parents=not strict, exist_ok=True)
            evidence_allowed = True
            run.evidence = {"mode": mode, "automatic_acceptance": False,
                "isolation_policy": "native_named_profile" if strict else "engineering_legacy_workspace",
                "experimental_profile_api": strict,
                "log": str(evidence_dir / "native-rpc.jsonl"),
                "total_stage_limit_seconds": timeout_seconds}
            executable = shutil.which(self.executable)
            if executable is None:
                raise _Stop("unsupported_integration", "Codex executable is unavailable")
            run.evidence["executable"] = executable
            overrides, profile = None, None
            if strict:
                _check(deadline, cancellation)
                with (evidence_dir / "native-bootstrap.jsonl").open("w", encoding="utf-8") as log:
                    bootstrap = _Transport(executable, cwd, log)
                    try:
                        policy.verify_host(self._initialize(bootstrap, deadline, cancellation, experimental=True))
                        config = policy.config_maps(bootstrap.request("config/read", {
                            "cwd": str(cwd), "includeLayers": False}, deadline, cancellation))
                        servers = set(config.get("mcp_servers", {}))
                        configured_plugins = set(config.get("plugins", {}))
                    finally:
                        bootstrap.close()
                inventory_receipt = {}
                try:
                    plugin_ids, selected = policy.bounded_plugin_inventory(executable, cwd,
                        min(deadline, time.monotonic() + 60), inventory_receipt, self.plugin, cancellation)
                finally:
                    run.evidence["inventory_command"] = inventory_receipt
                plugin_ids |= configured_plugins
                run.evidence["native_inventory"] = selected
                profile = "dsc26-stage-" + uuid.uuid4().hex
                overrides = policy.profile_overrides(profile, released_root, cwd, servers, plugin_ids, self.plugin)
                filesystem = tomllib.loads(overrides[1])["permissions"][profile]["filesystem"]
                run.evidence["profile"] = {"id": profile, "filesystem": filesystem, "network_enabled": False,
                    "disabled_mcp_servers": sorted(servers), "disabled_plugin_ids": sorted(plugin_ids - {self.plugin.plugin_id})}
            else:
                run.evidence["native_inventory"] = self._inventory(executable, cwd, deadline, cancellation)
            _check(deadline, cancellation)
            with (evidence_dir / "native-rpc.jsonl").open("w", encoding="utf-8") as log:
                transport = (_Transport(executable, cwd, log, config_overrides=overrides) if strict
                    else _Transport(executable, cwd, log))
                try:
                    host = self._initialize(transport, deadline, cancellation, experimental=strict)
                    run.evidence["host"] = host
                    if strict:
                        policy.verify_host(host)
                        config = policy.config_maps(transport.request("config/read", {
                            "cwd": str(cwd), "includeLayers": False}, deadline, cancellation))
                        policy.verify_restrictions(config, profile, filesystem, servers, plugin_ids, self.plugin)
                        run.evidence["effective_profile_verified"] = True
                        profiles = transport.request("permissionProfile/list", {"cwd": str(cwd), "limit": 100}, deadline, cancellation)
                        matches = [row for row in profiles.get("data", []) if isinstance(row, dict) and row.get("id") == profile]
                        policy.require(len(matches) == 1 and matches[0].get("allowed") is True,
                            "Selected native profile was not returned as allowed")
                    marketplace = self.plugin.plugin_id.rsplit("@", 1)[-1]
                    skill = transport.request("plugin/skill/read", {"remoteMarketplaceName": marketplace,
                        "remotePluginId": self.plugin.remote_plugin_id, "skillName": self.plugin.skill_name}, deadline, cancellation)
                    markdown = skill.get("contents")
                    if not isinstance(markdown, str) or not markdown.strip():
                        raise _Stop("plugin_unavailable", "Native Data skill contents unavailable")
                    skill_hash = sha256(markdown.encode()).hexdigest()
                    run.evidence["skill_sha256"] = skill_hash
                    if self.plugin.skill_sha256 is not None and skill_hash != self.plugin.skill_sha256:
                        raise _Stop("integrity_error", "Native Data skill hash differs from pinned specification")
                    thread_params = {"cwd": str(cwd), "approvalPolicy": "never"}
                    if strict:
                        thread_params.update(permissions=profile, runtimeWorkspaceRoots=[str(cwd)], model=policy.MODEL)
                    else:
                        thread_params["sandbox"] = "workspace-write"
                    thread = transport.request("thread/start", thread_params, deadline, cancellation)
                    run.thread_id = (thread.get("thread") or {}).get("id")
                    if not isinstance(run.thread_id, str) or not run.thread_id:
                        raise _Stop("runtime_error", "Native thread identity missing")
                    run.evidence["thread_start"] = thread
                    if (thread.get("cwd") != str(cwd) or thread.get("approvalPolicy") != "never"
                            or (thread.get("sandbox") or {}).get("networkAccess") is not False):
                        raise _Stop("integrity_error", "Native cwd/approval/network acknowledgement mismatch")
                    if strict:
                        policy.require((thread.get("activePermissionProfile") or {}).get("id") == profile
                            and thread.get("runtimeWorkspaceRoots") == [str(cwd)]
                            and thread.get("model") == policy.MODEL
                            and thread.get("modelProvider") == "openai"
                            and (thread.get("thread") or {}).get("cliVersion") == policy.CLI_VERSION,
                            "Native profile/workspace/model/CLI acknowledgement differs")
                        before = {}
                        run.evidence["mcp_inventory_before"] = before
                        policy.disabled_inventory(transport, run.thread_id, deadline, cancellation, before)
                    elif (thread.get("sandbox") or {}).get("type") != "workspaceWrite":
                        raise _Stop("integrity_error", "Native engineering sandbox acknowledgement mismatch")
                    attachment = {"type": "mention", "name": "Data", "path": "plugin://" + self.plugin.plugin_id}
                    run.evidence["attachment"] = attachment
                    started = transport.request("turn/start", {"threadId": run.thread_id,
                        "input": [{"type": "text", "text": prompt}, attachment]}, deadline, cancellation)
                    run.turn_id = (started.get("turn") or {}).get("id")
                    if not isinstance(run.turn_id, str) or not run.turn_id:
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
                        params = {"threadId": run.thread_id, "turnId": run.turn_id, "limit": 100, "sortDirection": "asc"}
                        if cursor is not None:
                            params["cursor"] = cursor
                        page = transport.request("thread/items/list", params, deadline, cancellation)
                        entries = page.get("data")
                        if not isinstance(entries, list) or len(entries) > 100 or any(
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
                    if strict:
                        after = {}
                        run.evidence["mcp_inventory_after"] = after
                        policy.disabled_inventory(transport, run.thread_id, deadline, cancellation, after)
                        allowed = {"userMessage", "agentMessage", "reasoning", "commandExecution", "fileChange", "plan"}
                        item_types = {(entry.get("item") or {}).get("type") for entry in run.items}
                        item_types.update((event.get("item") or {}).get("type") for event in transport.events
                            if event.get("threadId") == run.thread_id and event.get("turnId") == run.turn_id)
                        run.evidence["native_turn_item_types"] = sorted(item_types, key=str)
                        policy.require(item_types <= allowed, "Native tool/item outside declared tabular profile")
                    failed_code = _observed_invalid_code(run.items, transport.events, run.thread_id, run.turn_id)
                    if failed_code:
                        run.evidence["invalid_code_command_id"] = failed_code
                        raise _Stop("invalid_code", "Matching native command/history contains an actual Python syntax failure")
                    commands = _matched_commands(run.items, transport.events, run.thread_id, run.turn_id)
                    file_changes = _matched_file_changes(run.items, transport.events, run.thread_id, run.turn_id, cwd)
                    run.evidence["matched_command_ids"] = [item["id"] for item in commands]
                    run.evidence["matched_file_changes"] = file_changes
                    run.evidence["diagnostic_failed_command_ids"] = [item["id"] for item in commands if item["exitCode"] != 0]
                    if not commands and not file_changes:
                        raise _Stop("runtime_error", "Native completion has no actual paired command or output-file-change evidence")
                    if commands and commands[-1]["exitCode"] != 0:
                        raise _Stop("runtime_error", "Native turn completed with a final failed command and no subsequent correction")
                    _check(deadline, cancellation)
                    run.outcome = "completed"
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
            run.items, run.evidence = _safe(run.items), _safe(run.evidence)
            run.message = _safe(run.message)
            if evidence_allowed:
                try:
                    self._write_evidence(run, evidence_dir)
                except (OSError, ValueError) as exc:
                    run.outcome, run.error_code, run.message = "execution_failed", "runtime_error", str(exc)
        return run

    @staticmethod
    def _initialize(transport, deadline, cancellation, *, experimental):
        params = {"clientInfo": {"name": "suiroai_dsc26_native", "version": "0.1.0"}}
        if experimental:
            params["capabilities"] = {"experimentalApi": True}
        host = transport.request("initialize", params, deadline, cancellation)
        transport.send({"method": "initialized", "params": {}})
        return host

    @staticmethod
    def _write_evidence(run, directory):
        receipts = []
        for name in ("native-bootstrap.jsonl", "native-rpc.jsonl"):
            path = directory / name
            if not path.exists():
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError("Native evidence path was replaced")
            with path.open("rb") as stream:
                data = stream.read(policy.LOG_LIMIT + 65537)
            if len(data) > policy.LOG_LIMIT + 65536:
                raise ValueError("Native evidence file exceeds limit")
            receipts.append({"path": str(path), "relative_path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()})
        run.evidence["artifact_receipts"] = receipts
        report = directory / "native-run.json"
        run.evidence["report"] = str(report)
        data = (json.dumps(_safe(asdict(run)), indent=2) + "\n").encode()
        if len(data) > policy.REPORT_LIMIT:
            run.outcome, run.error_code, run.message = "execution_failed", "budget_exhausted", "Native report exceeded 16 MiB"
            run.items = []
            run.evidence = {"mode": run.mode, "automatic_acceptance": False, "report": str(report),
                "artifact_receipts": receipts, "oversized_report_sha256": sha256(data).hexdigest(),
                "oversized_report_bytes": len(data), "sanitized_items_retained_in_logs": True}
            data = (json.dumps(asdict(run), indent=2) + "\n").encode()
        if report.is_symlink():
            raise ValueError("Native evidence report path was replaced")
        report.write_bytes(data)
        receipts.append({"path": str(report), "relative_path": "native-run.json", "bytes": len(data),
            "sha256": sha256(data).hexdigest()})

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
