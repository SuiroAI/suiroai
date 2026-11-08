"""Mock protocol checks against schemas emitted by the installed Codex CLI.

These tests never start app-server or a model, and never establish Data loading
or DSC-26 acceptance. The only native command generates local protocol schemas.
"""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from jsonschema import Draft7Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "dsc26_engineering_probe_under_test",
    ROOT / "evidence/integration/probe_data_stage.py",
)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class MockItemsRequestReached(Exception):
    """Stop before supplying any invented execution or artifact evidence."""


class SchemaCheckingMockRPC:
    """Synthetic responses only; validate every actual outgoing probe request."""

    def __init__(self, schemas, stage, *, timeout=False, skill_path=None,
                 installed=True):
        self.schemas = schemas
        self.stage = stage
        self.timeout = timeout
        self.skill_path = skill_path
        self.installed = installed
        self.requests = []
        self.notifications = []
        self.waits = 0
        self.started_turns = []
        self.rejected_requests = []
        self.command_events = {}

    def request(self, method, params, timeout=None):
        names = {
            "initialize": "v1/InitializeParams.json",
            "plugin/read": "v2/PluginReadParams.json",
            "plugin/skill/read": "v2/PluginSkillReadParams.json",
            "thread/start": "v2/ThreadStartParams.json",
            "turn/start": "v2/TurnStartParams.json",
            "turn/interrupt": "v2/TurnInterruptParams.json",
            "thread/read": "v2/ThreadReadParams.json",
            "thread/items/list": "v2/ThreadItemsListParams.json",
        }
        Draft7Validator(self.schemas[names[method]]).validate(params)
        self.requests.append((method, copy.deepcopy(params)))
        if method == "initialize":
            return {"userAgent": "MOCK protocol-only host; no inference"}
        if method == "plugin/read":
            return {"plugin": {
                "marketplaceName": PROBE.MARKETPLACE,
                "summary": {
                    "id": PROBE.PLUGIN + "@" + PROBE.MARKETPLACE,
                    "remotePluginId": PROBE.REMOTE_ID,
                    "name": PROBE.PLUGIN,
                    "installed": self.installed,
                    "enabled": self.installed,
                    "version": PROBE.VERSION,
                    "localVersion": None,
                },
                "skills": [{"name": "index", "path": self.skill_path,
                            "enabled": True}],
            }}
        if method == "plugin/skill/read":
            return {"contents": "MOCK_REMOTE_SKILL_EVIDENCE_ONLY_DO_NOT_INLINE"}
        if method == "thread/start":
            return {"thread": {"id": "mock-thread"}, "cwd": str(self.stage),
                    "approvalPolicy": "never", "sandbox": {"type": "workspaceWrite"}}
        if method == "turn/start":
            return {"turn": {"id": "mock-turn", "status": "inProgress"}}
        if method == "turn/interrupt":
            return {}
        if method == "thread/read":
            return {"thread": {"id": "mock-thread"}}
        if method == "thread/items/list":
            raise MockItemsRequestReached()
        raise AssertionError("Unexpected mock request: " + method)

    def send(self, message):
        Draft7Validator(self.schemas["ClientNotification.json"]).validate(message)
        self.notifications.append(copy.deepcopy(message))

    def wait_terminal(self, thread_id, turn_id, deadline):
        assert (thread_id, turn_id) == ("mock-thread", "mock-turn")
        self.waits += 1
        if self.timeout and self.waits == 1:
            raise TimeoutError("MOCK deadline; no model was started")
        return {"id": turn_id,
                "status": "interrupted" if self.timeout else "completed",
                "error": None}


class NativeProbeProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = shutil.which("codex")
        if executable is None:
            raise unittest.SkipTest("Codex CLI unavailable; cannot generate native schemas")
        directory = tempfile.TemporaryDirectory(prefix="dsc26-protocol-tests-")
        cls.addClassCleanup(directory.cleanup)
        schema_root = Path(directory.name)
        generated = subprocess.run(
            [executable, "app-server", "generate-json-schema", "--out", str(schema_root)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if generated.returncode:
            raise AssertionError("Native schema generation failed: " + generated.stderr)
        cls.schemas = {
            str(path.relative_to(schema_root)): json.loads(path.read_text())
            for path in schema_root.rglob("*.json")
        }

    def exercise(self, **kwargs):
        temporary = tempfile.TemporaryDirectory(prefix="dsc26-mock-probe-")
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name)
        stage = output / "synthetic-stage"
        stage.mkdir()
        rpc = SchemaCheckingMockRPC(self.schemas, stage, **kwargs)
        report = {"model_turn_requested": False, "independent_checks_passed": False}
        return rpc, stage, output, report

    def test_actual_probe_requests_conform_without_claiming_mock_execution(self):
        for skill_path in (None, "/mock/native-returned/index/SKILL.md"):
            with self.subTest(skill_path=skill_path):
                rpc, stage, output, report = self.exercise(skill_path=skill_path)
                with self.assertRaises(MockItemsRequestReached):
                    PROBE.run_probe(rpc, stage, output, report)
                self.assertEqual([name for name, _ in rpc.requests], [
                    "initialize", "plugin/read", "plugin/skill/read", "thread/start",
                    "turn/start", "thread/read", "thread/items/list",
                ])
                requests = dict(rpc.requests)
                self.assertEqual(requests["plugin/read"]["pluginName"], PROBE.REMOTE_ID)
                self.assertEqual(requests["plugin/skill/read"]["remotePluginId"], PROBE.REMOTE_ID)
                self.assertEqual(requests["thread/start"]["sandbox"], "workspace-write")
                self.assertEqual(report["thread_start"]["sandbox"]["type"], "workspaceWrite")
                self.assertEqual(requests["thread/start"]["approvalPolicy"], "never")
                self.assertEqual(rpc.notifications, [{"method": "initialized", "params": {}}])
                turn_input = requests["turn/start"]["input"]
                self.assertNotIn("MOCK_REMOTE_SKILL_EVIDENCE_ONLY", turn_input[0]["text"])
                self.assertEqual(turn_input[1]["type"], "skill" if skill_path else "mention")
                self.assertEqual(turn_input[1]["path"], skill_path or
                                 "plugin://" + PROBE.PLUGIN + "@" + PROBE.MARKETPLACE)
                binding = json.loads((stage / "binding.json").read_text())
                self.assertEqual(binding["probe_kind"], "engineering_synthetic_only")
                self.assertNotIn("approval_version", binding)
                self.assertFalse((stage / "probe_calculation.py").exists())
                self.assertFalse((stage / "probe_result.json").exists())
                self.assertFalse(report["independent_checks_passed"])
                self.assertNotIn("fetched_artifacts", report)

    def test_timeout_interrupt_payload_conforms_and_cannot_become_success(self):
        rpc, stage, output, report = self.exercise(timeout=True)
        with self.assertRaisesRegex(PROBE.ProbeError, "turn_deadline_expired_never_success"):
            PROBE.run_probe(rpc, stage, output, report)
        self.assertEqual(rpc.requests[-1], (
            "turn/interrupt", {"threadId": "mock-thread", "turnId": "mock-turn"}))
        self.assertTrue(report["deadline_expired"])
        self.assertTrue(report["interruption_confirmed"])
        self.assertEqual(report["terminal"]["status"], "interrupted")
        self.assertFalse(report["independent_checks_passed"])
        self.assertNotIn("thread/read", [method for method, _ in rpc.requests])

    def test_disabled_native_metadata_stops_before_any_mock_model_turn(self):
        rpc, stage, output, report = self.exercise(installed=False)
        with self.assertRaisesRegex(PROBE.ProbeError, "not_installed_and_enabled"):
            PROBE.run_probe(rpc, stage, output, report)
        self.assertEqual([method for method, _ in rpc.requests], ["initialize", "plugin/read"])
        self.assertFalse(report["model_turn_requested"])
        self.assertFalse((stage / "binding.json").exists())

    def test_native_request_and_effective_response_use_distinct_sandbox_enums(self):
        request_schema = self.schemas["v2/ThreadStartParams.json"]
        Draft7Validator(request_schema).validate({"sandbox": "workspace-write"})
        with self.assertRaises(ValidationError):
            Draft7Validator(request_schema).validate({"sandbox": "workspaceWrite"})
        response_schema = self.schemas["v2/ThreadStartResponse.json"]
        policy_schema = {"$ref": "#/definitions/SandboxPolicy",
                         "definitions": response_schema["definitions"]}
        Draft7Validator(policy_schema).validate({"type": "workspaceWrite"})
        with self.assertRaises(ValidationError):
            Draft7Validator(policy_schema).validate({"type": "workspace-write"})


if __name__ == "__main__":
    unittest.main()
