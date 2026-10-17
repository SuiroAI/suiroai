"""Mock transport regressions only; these never establish native acceptance."""
from __future__ import annotations

from hashlib import sha256
import io
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from suiroai.integration.native import DataPluginSpec, NativeHost, _Stop, _Transport
from suiroai.integration.native import _observed_invalid_code


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

    def __init__(self, executable, cwd, log):
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
            return {"userAgent": "mock/0.163.0"}
        if method == "plugin/skill/read":
            return {"contents": self.markdown}
        if method == "thread/start":
            return {"thread": {"id": "thread-mock"}, "cwd": str(self.cwd),
                    "approvalPolicy": "never", "sandbox": {"type": "workspaceWrite", "networkAccess": False}}
        if method == "turn/start":
            self.started.append(("thread-mock", "turn-real-shaped-mock"))
            return {"turn": {"id": "turn-real-shaped-mock", "status": "inProgress"}}
        if method == "turn/interrupt":
            self.interrupted = True
            return {}
        if method == "thread/read":
            return {"thread": {"id": "thread-mock"}}
        if method == "thread/items/list":
            return {"data": [{"turnId": "turn-real-shaped-mock", "item": {
                "id": "item-mock", "type": "agentMessage", "text": "mock only"}}],
                "nextCursor": self.page_cursor}
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
        saved = json.loads((self.evidence / "native-run.json").read_text())
        self.assertFalse(saved["evidence"]["customer_isolation_verified"])
        self.assertEqual(saved["mode"], "customer")

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
        transport.log, transport.log_bytes = io.StringIO(), 64 * 1024 * 1024 - 5
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

    def test_inventory_mismatch_is_not_silently_enabled_or_reinstalled(self):
        class Command:
            returncode = 0
            stdout = json.dumps({"installed": [inventory("1.0.12")]}).encode()
            stderr = b""
        with patch("suiroai.integration.native.subprocess.run", return_value=Command()) as command:
            with self.assertRaises(_Stop) as caught:
                NativeHost(plugin=SPEC)._inventory("/mock/codex", self.cwd,
                    __import__("time").monotonic() + 20, None)
        self.assertEqual(caught.exception.code, "integrity_error")
        self.assertEqual(command.call_args.args[0], ["/mock/codex", "plugin", "list", "--json"])

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
