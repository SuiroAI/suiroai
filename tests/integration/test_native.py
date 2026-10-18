"""Mock transport regressions only; these never establish native acceptance."""
from __future__ import annotations

from hashlib import sha256
import io
import importlib.util
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
import tomllib
from unittest.mock import patch

from suiroai.integration.native import DataPluginSpec, NativeHost, _Stop, _Transport
from suiroai.integration.native import _observed_invalid_code
from suiroai.integration import native_profile as policy


MARKDOWN = "# Data\nNative synthetic test skill.\n"
SPEC = DataPluginSpec(skill_sha256=sha256(MARKDOWN.encode()).hexdigest())


def inventory(version="1.0.11"):
    return {"pluginId": SPEC.plugin_id, "installed": True, "enabled": True,
            "version": version, "source": {"source": "remote", "id": SPEC.remote_plugin_id}}


class FakeTransport:
    instances = []
    terminal = {"id": "turn-real-shaped-mock", "status": "completed", "error": None}
    stop = None
    page_cursor = None
    markdown = MARKDOWN

    def __init__(self, executable, cwd, log, config_overrides=None):
        self.config = {"mcp_servers": {"mock-mcp": {"enabled": True}}, "plugins": {"mock-other": {"enabled": True}}}
        for value in config_overrides or []: self.config.update(tomllib.loads(value))
        self.cwd = Path(cwd)
        self.calls = []
        self.started = []
        self.events = []
        self.errors = []
        self.rejected_requests = []
        self.closed = False
        self.interrupted = False
        self.log = log
        self.__class__.instances.append(self)

    def send(self, message):
        self.calls.append(("send", message))

    def request(self, method, params, deadline, cancellation=None):
        self.calls.append((method, params))
        self.log.write(json.dumps({"mock": True, "method": method}) + "\n")
        if method == "initialize":
            return {"userAgent": "mock/0.163.0 (MOCK)", "platformFamily": "unix", "platformOs": "macos"}
        if method == "config/read":
            return {"config": self.config}
        if method == "permissionProfile/list":
            return {"data": [{"id": self.config["default_permissions"], "allowed": True}]}
        if method == "mcpServerStatus/list":
            return {"data": [], "nextCursor": None}
        if method == "plugin/skill/read":
            return {"contents": self.markdown}
        if method == "thread/start":
            result = {"thread": {"id": "thread-mock", "cliVersion": "0.163.0"}, "cwd": str(self.cwd),
                    "approvalPolicy": "never", "sandbox": {"type": "workspaceWrite", "networkAccess": False}}
            if "permissions" in params:
                result.update(activePermissionProfile={"id": params["permissions"]},
                    runtimeWorkspaceRoots=[str(self.cwd)], model=policy.MODEL, modelProvider="openai")
            return result
        if method == "turn/start":
            self.started.append(("thread-mock", "turn-real-shaped-mock"))
            return {"turn": {"id": "turn-real-shaped-mock", "status": "inProgress"}}
        if method == "turn/interrupt":
            self.interrupted = True
            return {}
        if method == "thread/read":
            return {"thread": {"id": "thread-mock"}}
        if method == "thread/items/list":
            item = {"id": "exec-mock", "type": "commandExecution", "command": "python3 mock_calculation.py",
                "cwd": str(self.cwd), "status": "completed", "exitCode": 0, "aggregatedOutput": "MOCK ONLY"}
            self.events = [{"threadId": "thread-mock", "turnId": "turn-real-shaped-mock", "item": item}]
            return {"data": [{"turnId": "turn-real-shaped-mock", "item": item}], "nextCursor": self.page_cursor}
        raise AssertionError("Unexpected method " + method)

    def wait_terminal(self, thread_id, turn_id, deadline, cancellation=None):
        if self.interrupted:
            return {"id": turn_id, "status": "interrupted", "error": None}
        if self.stop:
            raise self.stop
        return self.terminal

    def close(self):
        self.closed = True


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name) / "synthetic"
        self.cwd.mkdir()
        self.evidence = Path(self.temp.name) / "evidence"
        FakeTransport.instances = []
        FakeTransport.stop = None
        FakeTransport.page_cursor = None
        FakeTransport.markdown = MARKDOWN
        FakeTransport.terminal = {"id": "turn-real-shaped-mock", "status": "completed", "error": None}

    def run_mock(self, **kwargs):
        with patch("suiroai.integration.native.shutil.which", return_value="/mock/codex"), \
             patch.object(NativeHost, "_inventory", return_value=inventory()), \
             patch("suiroai.integration.native._Transport", FakeTransport):
            return NativeHost(plugin=SPEC).execute(cwd=self.cwd, prompt="Synthetic mock task",
                evidence_dir=self.evidence, timeout_seconds=90, mode="engineering", **kwargs)

    def test_customer_mode_blocks_before_process_and_retains_evidence(self):
        with patch("suiroai.integration.native.subprocess.Popen") as launch, \
             patch("suiroai.integration.native.subprocess.run") as command:
            result = NativeHost(plugin=SPEC).execute(cwd=self.cwd, prompt="approved task",
                evidence_dir=self.evidence, timeout_seconds=30)
        self.assertEqual(result.error_code, "unsupported_integration")
        launch.assert_not_called()
        command.assert_not_called()
        self.assertFalse((self.evidence / "native-run.json").exists())
        self.assertEqual(result.mode, "customer")

    def test_invalid_time_fails_before_native_process(self):
        with patch("suiroai.integration.native.subprocess.Popen") as launch:
            result = NativeHost().execute(cwd=self.cwd, prompt="mock", evidence_dir=self.evidence,
                timeout_seconds=float("inf"), mode="engineering")
        self.assertEqual(result.error_code, "budget_exhausted")
        launch.assert_not_called()

    def test_preset_cancellation_never_launches(self):
        event = Event()
        event.set()
        result = self.run_mock(cancellation=event)
        self.assertEqual(result.error_code, "cancelled")
        self.assertEqual(FakeTransport.instances, [])

    def test_supported_invocation_uses_stable_skill_and_native_mention(self):
        result = self.run_mock()
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.thread_id, "thread-mock")
        self.assertEqual(result.turn_id, "turn-real-shaped-mock")
        transport = FakeTransport.instances[0]
        methods = [name for name, _ in transport.calls]
        self.assertNotIn("plugin/read", methods)
        skill = next(params for name, params in transport.calls if name == "plugin/skill/read")
        self.assertEqual(skill["remotePluginId"], SPEC.remote_plugin_id)
        turn = next(params for name, params in transport.calls if name == "turn/start")
        self.assertEqual(turn["input"][1], {"type": "mention", "name": "Data",
            "path": "plugin://" + SPEC.plugin_id})
        self.assertNotIn("model", turn)
        self.assertNotIn(MARKDOWN, turn["input"][0]["text"])
        start = next(params for name, params in transport.calls if name == "thread/start")
        self.assertEqual(start["sandbox"], "workspace-write")
        self.assertEqual(result.evidence["skill_sha256"], SPEC.skill_sha256)
        self.assertTrue(transport.closed)
        self.assertFalse(result.evidence["automatic_acceptance"])

    def test_empty_skill_blocks_before_thread_start(self):
        FakeTransport.markdown = ""
        result = self.run_mock()
        self.assertEqual(result.error_code, "plugin_unavailable")
        self.assertFalse(any(name == "thread/start" for name, _ in FakeTransport.instances[0].calls))

    def test_changed_skill_digest_blocks_before_thread_start(self):
        FakeTransport.markdown = MARKDOWN + "changed"
        result = self.run_mock()
        self.assertEqual(result.error_code, "integrity_error")
        self.assertIsNone(result.thread_id)

    def test_enabled_command_network_blocks_before_turn(self):
        original = FakeTransport.request
        def reply(transport, method, params, deadline, cancellation=None):
            result = original(transport, method, params, deadline, cancellation)
            if method == "thread/start":
                result["sandbox"]["networkAccess"] = True
            return result
        with patch.object(FakeTransport, "request", reply):
            result = self.run_mock()
        self.assertEqual(result.error_code, "integrity_error")
        self.assertFalse(any(name == "turn/start" for name, _ in FakeTransport.instances[0].calls))

    def test_timeout_interrupts_and_preserves_timeout_outcome(self):
        FakeTransport.stop = _Stop("timeout", "mock timeout")
        result = self.run_mock()
        self.assertEqual(result.error_code, "timeout")
        self.assertEqual(result.outcome, "execution_failed")
        self.assertTrue(result.evidence["interruption_confirmed"])
        self.assertEqual(result.terminal_status, "interrupted")
        self.assertTrue(FakeTransport.instances[0].closed)

    def test_cancellation_interrupts_and_preserves_cancelled_outcome(self):
        FakeTransport.stop = _Stop("cancelled", "mock cancellation")
        result = self.run_mock()
        self.assertEqual(result.error_code, "cancelled")
        self.assertTrue(result.evidence["interruption_confirmed"])

    def test_evidence_limit_also_interrupts_active_turn_and_preserves_code(self):
        FakeTransport.stop = _Stop("budget_exhausted", "mock evidence cap")
        result = self.run_mock()
        self.assertEqual(result.error_code, "budget_exhausted")
        self.assertTrue(result.evidence["interruption_confirmed"])
        self.assertEqual(result.outcome, "execution_failed")

    def test_bulk_evidence_cap_keeps_control_plane_receipt_available(self):
        transport = _Transport.__new__(_Transport)
        transport.log, transport.log_bytes = io.StringIO(), policy.LOG_LIMIT - 5
        transport.recording_exhausted = False
        with self.assertRaises(_Stop):
            transport.record("received", {"bulk": "oversized"})
        transport.record("sent", {"method": "turn/interrupt", "id": 8}, control=True)
        self.assertIn("turn/interrupt", transport.log.getvalue())

    def test_exhausted_native_limit_is_not_analytical_validation_failure(self):
        FakeTransport.terminal = {"id": "turn-real-shaped-mock", "status": "failed",
            "error": {"codexErrorInfo": "UsageLimitExceeded", "message": "mock cap"}}
        result = self.run_mock()
        self.assertEqual(result.error_code, "budget_exhausted")
        self.assertEqual(result.outcome, "execution_failed")

    def test_prose_syntax_error_does_not_attest_invalid_code(self):
        FakeTransport.terminal = {"id": "turn-real-shaped-mock", "status": "failed",
            "error": {"message": "SyntaxError: mock generated code"}}
        self.assertEqual(self.run_mock().error_code, "runtime_error")

    def test_invalid_code_requires_matching_streamed_and_persisted_command(self):
        item = {"id": "exec-mock", "type": "commandExecution", "command": "python3 broken.py",
                "exitCode": 1, "status": "failed", "aggregatedOutput": "SyntaxError: intentional mock\n"}
        entries = [{"turnId": "turn-mock", "item": item}]
        events = [{"threadId": "thread-mock", "turnId": "turn-mock", "item": item}]
        self.assertEqual(_observed_invalid_code(entries, events, "thread-mock", "turn-mock"), "exec-mock")
        self.assertIsNone(_observed_invalid_code(entries, [], "thread-mock", "turn-mock"))
        self.assertIsNone(_observed_invalid_code(entries, events, "other-thread", "turn-mock"))

    def test_real_native_shell_wrapper_and_echo_false_positive(self):
        def observed(command):
            item = {"id": "exec-mock", "type": "commandExecution", "command": command,
                    "exitCode": 1, "status": "completed", "aggregatedOutput": "SyntaxError: invalid syntax\n"}
            return _observed_invalid_code([{"turnId": "turn-mock", "item": item}],
                [{"threadId": "thread-mock", "turnId": "turn-mock", "item": item}],
                "thread-mock", "turn-mock")
        self.assertEqual(observed("/bin/zsh -lc 'python3 intentional_failure.py'"), "exec-mock")
        self.assertIsNone(observed("/bin/zsh -lc 'echo python3 intentional_failure.py'"))
        self.assertIsNone(observed("echo python3 intentional_failure.py"))

    def test_actual_native_printf_then_python_and_shell_masks(self):
        def observed(command):
            item = {"id": "exec-c838dba9-c532-41b3-9018-c647228fd28f", "type": "commandExecution",
                "command": command, "exitCode": 1, "status": "failed",
                "aggregatedOutput": "  File \"intentional_failure.py\", line 1\n    def broken(:\nSyntaxError: invalid syntax\n"}
            return _observed_invalid_code([{"turnId": "turn-mock", "item": item}],
                [{"threadId": "thread-mock", "turnId": "turn-mock", "item": item}],
                "thread-mock", "turn-mock")
        inner = "printf '%s\\n' 'def broken(:' > intentional_failure.py\npython3 intentional_failure.py"
        self.assertEqual(observed(f'/bin/zsh -c "{inner}"'),
                         "exec-c838dba9-c532-41b3-9018-c647228fd28f")
        self.assertIsNone(observed('/bin/zsh -c "python3 intentional_failure.py || false"'))
        self.assertIsNone(observed('/bin/zsh -c "python3 intentional_failure.py; exit 1"'))
        self.assertIsNone(observed('/bin/zsh -c "echo \'not a command\npython3 intentional_failure.py\'"'))
        self.assertIsNone(observed('/bin/zsh -c "printf \'%s\\n\' \'prose\npython3 fake.py\'"'))

    def test_final_unclassified_command_error_cannot_be_native_completion(self):
        original = FakeTransport.request
        def reply(transport, method, params, deadline, cancellation=None):
            result = original(transport, method, params, deadline, cancellation)
            if method == "thread/items/list":
                item = {"id": "failed-exec", "type": "commandExecution", "command": "/bin/zsh -c false",
                        "status": "failed", "exitCode": 1, "aggregatedOutput": "mock command failed"}
                result["data"] = [{"turnId": "turn-real-shaped-mock", "item": item}]
                transport.events = [{"threadId": "thread-mock", "turnId": "turn-real-shaped-mock", "item": item}]
            return result
        with patch.object(FakeTransport, "request", reply):
            result = self.run_mock()
        self.assertEqual(result.error_code, "runtime_error")
        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(result.evidence["diagnostic_failed_command_ids"], ["failed-exec"])

    def test_later_successful_same_python_rerun_keeps_failure_diagnostic(self):
        original = FakeTransport.request
        def reply(transport, method, params, deadline, cancellation=None):
            result = original(transport, method, params, deadline, cancellation)
            if method == "thread/items/list":
                failed = {"id": "failed-exec", "type": "commandExecution", "command": "python3 calculation.py",
                          "status": "failed", "exitCode": 1, "aggregatedOutput": "SyntaxError: mock invalid syntax\n"}
                corrected = {**failed, "id": "corrected-exec", "status": "completed", "exitCode": 0,
                             "aggregatedOutput": "mock calculation executed"}
                result["data"] = [{"turnId": "turn-real-shaped-mock", "item": item} for item in (failed, corrected)]
                transport.events = [{"threadId": "thread-mock", "turnId": "turn-real-shaped-mock", "item": item}
                                    for item in (failed, corrected)]
            return result
        with patch.object(FakeTransport, "request", reply):
            result = self.run_mock()
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.evidence["diagnostic_failed_command_ids"], ["failed-exec"])

    def test_repeated_pagination_cursor_fails_partial_retrieval(self):
        FakeTransport.page_cursor = "repeated"
        result = self.run_mock()
        self.assertEqual(result.error_code, "integrity_error")
        self.assertEqual(result.outcome, "execution_failed")

    def test_server_auth_request_rejected_without_parameter_capture(self):
        transport = _Transport.__new__(_Transport)
        transport.log, transport.log_bytes = io.StringIO(), 0
        transport.rejected_requests = []
        sent = []
        transport.send = sent.append
        transport.consume("stdout", json.dumps({"id": "auth-1", "method": "account/chatgptAuthTokens/refresh",
            "params": {"accessToken": "private-auth-value", "opaque": "sensitive"}}).encode())
        self.assertNotIn("private-auth-value", transport.log.getvalue())
        self.assertNotIn("sensitive", transport.log.getvalue())
        self.assertEqual(sent[0]["error"]["code"], -32601)
        self.assertEqual(transport.rejected_requests, [{"method": "account/chatgptAuthTokens/refresh", "id": "auth-1"}])


class StrictNativeTests(unittest.TestCase):
    """Customer-shaped MOCK calls; no Codex or model invocation/acceptance."""
    def setUp(self):
        NativeTests.setUp(self)
        root = Path(self.temp.name).resolve()
        self.cwd = self.cwd.resolve()
        self.evidence = root / "evidence"
        self.release = root / "released"
        self.release.mkdir()
        self.data_root = root / "mock-data-resource"
        self.python_root = root / "mock-python-resource"
        self.data_root.mkdir(); self.python_root.mkdir()

    def run_strict(self, *, plugin=SPEC, timeout_seconds=90, **kwargs):
        if self.evidence.exists():
            shutil.rmtree(self.evidence)
        with patch("suiroai.integration.native.shutil.which", return_value="/mock/codex"), \
             patch.object(policy, "SKILL_SHA256", SPEC.skill_sha256), \
             patch.object(policy, "DATA_ROOT", self.data_root), patch.object(policy, "PYTHON_ROOT", self.python_root), \
             patch.object(policy.sys, "platform", "darwin"), \
             patch.object(policy, "bounded_plugin_inventory", return_value=({SPEC.plugin_id, "mock-other"}, inventory())), \
             patch("suiroai.integration.native._Transport", FakeTransport):
            return NativeHost(plugin=plugin).execute(cwd=self.cwd, released_root=self.release,
                prompt="MOCK same approved task; no real authorization", evidence_dir=self.evidence,
                timeout_seconds=timeout_seconds, **kwargs)

    def test_strict_dispatch_uses_exact_profile_and_one_deadline_without_attestation_flags(self):
        deadlines = []
        original = FakeTransport.request
        def request(transport, method, params, deadline, cancellation=None):
            deadlines.append(deadline)
            return original(transport, method, params, deadline, cancellation)
        with patch.object(FakeTransport, "request", request): result = self.run_strict()
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(len(set(deadlines)), 1)
        self.assertEqual(len(FakeTransport.instances), 2)
        actual = FakeTransport.instances[-1]
        start = next(params for method, params in actual.calls if method == "thread/start")
        self.assertNotIn("sandbox", start)
        self.assertEqual(start["permissions"], actual.config["default_permissions"])
        self.assertEqual(start["model"], "gpt-6.1-sol")
        self.assertEqual(start["runtimeWorkspaceRoots"], [str(self.cwd)])
        self.assertTrue(result.evidence["mcp_inventory_before"]["validated_disabled_only"])
        self.assertTrue(result.evidence["mcp_inventory_after"]["validated_disabled_only"])
        self.assertEqual(result.evidence["matched_command_ids"], ["exec-mock"])
        receipts = result.evidence["artifact_receipts"]
        self.assertEqual({r["relative_path"] for r in receipts},
            {"native-bootstrap.jsonl", "native-rpc.jsonl", "native-run.json"})
        for receipt in receipts:
            data = Path(receipt["path"]).read_bytes()
            self.assertEqual(len(data), receipt["bytes"])
            self.assertEqual(sha256(data).hexdigest(), receipt["sha256"])
        self.assertNotIn("customer_isolation_verified", result.evidence)

    def test_unverified_plugin_version_or_hash_never_launches(self):
        for plugin in (DataPluginSpec(version="1.0.12"), DataPluginSpec(skill_sha256=None)):
            result = self.run_strict(plugin=plugin)
            self.assertEqual(result.error_code, "unsupported_integration")
            self.assertEqual(FakeTransport.instances, [])

    def test_zero_expired_or_cancelled_stage_never_launches(self):
        for seconds in (0, -1, 1e-30):
            with self.subTest(seconds=seconds):
                result = self.run_strict(timeout_seconds=seconds)
                self.assertIn(result.error_code, {"budget_exhausted", "timeout"})
                self.assertEqual(FakeTransport.instances, [])
        cancelled = Event(); cancelled.set()
        result = self.run_strict(cancellation=cancelled)
        self.assertEqual(result.error_code, "cancelled")
        self.assertEqual(FakeTransport.instances, [])

    def test_cancellation_after_discovery_cannot_launch_worker(self):
        cancelled = Event()
        original = FakeTransport.request
        def request(transport, method, params, deadline, cancellation=None):
            result = original(transport, method, params, deadline, cancellation)
            if method == "config/read": cancelled.set()
            return result
        with patch.object(FakeTransport, "request", request): result = self.run_strict(cancellation=cancelled)
        self.assertEqual(result.error_code, "cancelled")
        self.assertEqual(len(FakeTransport.instances), 1)
        self.assertTrue(FakeTransport.instances[0].closed)

    def test_profile_config_or_thread_binding_changes_block_before_turn(self):
        original = FakeTransport.request
        for defect in ("network", "profile", "workspace", "model", "cli", "features", "plugins", "mcp"):
            FakeTransport.instances = []
            def request(transport, method, params, deadline, cancellation=None):
                result = original(transport, method, params, deadline, cancellation)
                if method == "config/read" and "default_permissions" in transport.config:
                    if defect == "features": result["config"]["features"]["apps"] = True
                    if defect == "plugins": result["config"]["plugins"]["mock-other"]["enabled"] = True
                    if defect == "mcp": result["config"]["mcp_servers"]["mock-mcp"]["enabled"] = True
                if method == "thread/start":
                    if defect == "network": result["sandbox"]["networkAccess"] = True
                    if defect == "profile": result["activePermissionProfile"]["id"] = "wrong"
                    if defect == "workspace": result["runtimeWorkspaceRoots"] = ["/wrong"]
                    if defect == "model": result["model"] = "wrong"
                    if defect == "cli": result["thread"]["cliVersion"] = "0.164.0"
                return result
            with self.subTest(defect=defect), patch.object(FakeTransport, "request", request):
                result = self.run_strict()
                self.assertEqual(result.outcome, "execution_failed")
                self.assertIsNone(result.turn_id)
                self.assertFalse(any(method == "turn/start" for transport in FakeTransport.instances for method, _ in transport.calls))

    def test_live_mcp_after_turn_fails_instead_of_releasing_stage(self):
        original = FakeTransport.request
        seen = 0
        def request(transport, method, params, deadline, cancellation=None):
            nonlocal seen
            result = original(transport, method, params, deadline, cancellation)
            if method == "mcpServerStatus/list":
                seen += 1
                if seen == 2: result["data"] = [{"name": "MOCK newly active", "runtimeStatus": "connected"}]
            return result
        with patch.object(FakeTransport, "request", request): result = self.run_strict()
        self.assertEqual(result.outcome, "execution_failed")
        self.assertTrue(result.evidence["mcp_inventory_before"]["validated_disabled_only"])
        self.assertFalse(result.evidence["mcp_inventory_after"]["validated_disabled_only"])

    def test_prose_only_or_unpaired_history_does_not_count_as_execution(self):
        original = FakeTransport.request
        for prose in (True, False):
            def request(transport, method, params, deadline, cancellation=None):
                result = original(transport, method, params, deadline, cancellation)
                if method == "thread/items/list":
                    if prose: result["data"] = [{"turnId": "turn-real-shaped-mock", "item": {"id": "p", "type": "agentMessage", "text": "I ran code (MOCK)"}}]
                    transport.events = []
                return result
            with self.subTest(prose=prose), patch.object(FakeTransport, "request", request): result = self.run_strict()
            self.assertEqual(result.error_code, "runtime_error")
            self.assertEqual(result.evidence["matched_command_ids"], [])

    def test_paired_file_write_allows_transport_completion_without_claiming_analysis(self):
        original = FakeTransport.request
        packet = b'{"outcome":"needs_material_facts","mock":true}\n'
        for defect in (None, "unpaired", "missing"):
            path = self.cwd / "stage-result.json"
            if path.exists(): path.unlink()
            def request(transport, method, params, deadline, cancellation=None):
                result = original(transport, method, params, deadline, cancellation)
                if method == "thread/items/list":
                    if defect != "missing": path.write_bytes(packet)
                    item = {"type": "fileChange", "id": "write-mock", "status": "completed",
                        "changes": [{"path": str(path), "kind": {"type": "add"}, "diff": packet.decode()}]}
                    result["data"] = [{"turnId": "turn-real-shaped-mock", "item": item}]
                    transport.events = [] if defect == "unpaired" else [
                        {"threadId": "thread-mock", "turnId": "turn-real-shaped-mock", "item": item}]
                return result
            with self.subTest(defect=defect), patch.object(FakeTransport, "request", request): result = self.run_strict()
            self.assertEqual(result.outcome, "completed" if defect is None else "execution_failed")
            self.assertEqual(result.evidence["matched_command_ids"], [])
            if defect is None:
                files = result.evidence["matched_file_changes"][0]["files"]
                self.assertEqual(files, [{"relative_path": "stage-result.json", "bytes": len(packet),
                    "sha256": sha256(packet).hexdigest()}])
                self.assertFalse(result.evidence["automatic_acceptance"])

    def test_returned_items_and_report_omit_reasoning_and_full_skill_outputs(self):
        original = FakeTransport.request
        def request(transport, method, params, deadline, cancellation=None):
            result = original(transport, method, params, deadline, cancellation)
            if method == "thread/items/list":
                result["data"].append({"turnId": "turn-real-shaped-mock", "item": {"id": "r", "type": "reasoning",
                    "content": "PRIVATE_REASONING", "summary": "PRIVATE_SUMMARY", "encrypted_content": "PRIVATE_ENCRYPTED"}})
                skill = {"id": "s", "type": "commandExecution", "command": "cat /MOCK/SKILL.md", "cwd": str(self.cwd),
                    "status": "completed", "exitCode": 0, "aggregatedOutput": "PRIVATE_SKILL_BODY"}
                result["data"].append({"turnId": "turn-real-shaped-mock", "item": skill})
                transport.events.append({"threadId": "thread-mock", "turnId": "turn-real-shaped-mock", "item": skill})
            return result
        with patch.object(FakeTransport, "request", request): result = self.run_strict()
        self.assertEqual(result.outcome, "completed")
        returned = json.dumps({"items": result.items, "evidence": result.evidence})
        body = (self.evidence / "native-run.json").read_text()
        self.assertNotIn("PRIVATE_", returned)
        self.assertNotIn("PRIVATE_", body)
        self.assertIn("resource_output_sha256", body)

    def test_symlink_or_overlapping_roots_block_before_any_process(self):
        link = Path(self.temp.name) / "release-link"
        link.symlink_to(self.release, target_is_directory=True)
        self.release = link
        result = self.run_strict()
        self.assertEqual(result.error_code, "unsupported_integration")
        self.assertEqual(FakeTransport.instances, [])
        self.release = self.cwd
        result = self.run_strict()
        self.assertEqual(result.error_code, "unsupported_integration")
        self.assertEqual(FakeTransport.instances, [])


class NativeGeneratedProtocolTests(unittest.TestCase):
    """Actual adapter payloads against schemas generated by installed CLI; no inference."""

    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name("test_native_probe_protocol.py")
        spec = importlib.util.spec_from_file_location("native_probe_schema_generator", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.NativeProbeProtocolTests.setUpClass.__func__(cls)

    def test_actual_native_dispatch_and_interrupt_payloads_validate(self):
        from jsonschema import Draft7Validator
        names = {"initialize": "v1/InitializeParams.json",
                 "plugin/skill/read": "v2/PluginSkillReadParams.json",
                 "thread/start": "v2/ThreadStartParams.json",
                 "turn/start": "v2/TurnStartParams.json",
                 "turn/interrupt": "v2/TurnInterruptParams.json",
                 "thread/read": "v2/ThreadReadParams.json",
                 "thread/items/list": "v2/ThreadItemsListParams.json"}
        methods = set()
        for failure in (None, "timeout", "cancelled"):
            case = NativeTests()
            case.setUp()
            try:
                FakeTransport.stop = _Stop(failure, "mock only") if failure else None
                case.run_mock()
                for method, params in FakeTransport.instances[-1].calls:
                    if method == "send":
                        Draft7Validator(self.schemas["ClientNotification.json"]).validate(params)
                    else:
                        Draft7Validator(self.schemas[names[method]]).validate(params)
                        methods.add(method)
            finally:
                case.doCleanups()
        self.assertEqual(methods, set(names))


if __name__ == "__main__":
    unittest.main()
