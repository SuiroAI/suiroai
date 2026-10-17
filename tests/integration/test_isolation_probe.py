"""Engineering probe request checks; mock responses never establish isolation."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import struct
import tempfile
import time
import tomllib
import unittest
from unittest.mock import patch, MagicMock
import zlib

from jsonschema import Draft7Validator
from suiroai.integration.native import _Stop, _Transport

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("isolation_probe_under_test", ROOT / "evidence/integration/probe_native_isolation.py")
PROBE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROBE)


def disabled_row(name="mock-disabled"):
    """Actual native disabled-row shape; MOCK only, no connector invocation."""
    return {"name": name, "runtimeStatus": "disabled", "pluginId": None, "httpOrigin": None,
        "serverInfo": None, "serverCapabilities": None, "tools": {}, "toolsError": None,
        "resources": [], "resourceTemplates": [], "authStatus": "unsupported"}


def control_payload():
    return {"positive": {"row_count": 3, "group_totals": {"A": 5, "B": 5}, "total_units": 10},
        "checks": {name: {"denied": True, "type": "PermissionError", "errno": 13}
            for name in ("sentinel_open", "symlink_open", "input_write", "outside_write", "network")}}


class MockRPC:
    """Schema-check actual outgoing requests; responses/artifacts are mock only."""
    def __init__(self, schemas, paths, profile, mcp=False):
        self.schemas, self.paths, self.profile = schemas, paths, profile
        self.calls, self.events, self.rejected_requests = [], [], []
        self.mcp = mcp

    def request(self, method, params, deadline, cancellation=None):
        names = {"initialize": "v1/InitializeParams.json", "config/read": "v2/ConfigReadParams.json",
            "permissionProfile/list": "v2/PermissionProfileListParams.json", "command/exec": "v2/CommandExecParams.json",
            "thread/start": "v2/ThreadStartParams.json", "mcpServerStatus/list": "v2/ListMcpServerStatusParams.json",
            "plugin/skill/read": "v2/PluginSkillReadParams.json", "turn/start": "v2/TurnStartParams.json",
            "thread/read": "v2/ThreadReadParams.json", "thread/items/list": "v2/ThreadItemsListParams.json"}
        Draft7Validator(self.schemas[names[method]]).validate(params)
        self.calls.append((method, params))
        if method == "initialize": return {"userAgent": "MOCK only; no model"}
        if method == "config/read": return {"config": {"mcp_servers": {"secret-server": {"authorization": "DO_NOT_LOG"}}}}
        if method == "permissionProfile/list": return {"data": [{"id": self.profile, "allowed": True}]}
        if method == "command/exec":
            if params["command"][0] == "/bin/cat":
                return {"exitCode": 1, "stdout": "", "stderr": "cat: Permission denied"}
            return {"exitCode": 0, "stderr": "", "stdout": json.dumps({
                "positive": {"row_count": 3, "group_totals": {"A": 5, "B": 5}, "total_units": 10},
                "checks": {key: {"denied": True, "type": "PermissionError", "errno": 13}
                           for key in ("sentinel_open", "symlink_open", "input_write", "outside_write", "network")}})}
        if method == "thread/start":
            return {"thread": {"id": "mock-thread"}, "activePermissionProfile": {"id": self.profile, "extends": None},
                "runtimeWorkspaceRoots": [str(self.paths["output"])], "cwd": str(self.paths["output"]),
                "approvalPolicy": "never", "sandbox": {"type": "readOnly", "networkAccess": False}}
        if method == "mcpServerStatus/list":
            return {"data": [{"name": "unresolved-mock", "toolsError": "mock error"}] if self.mcp
                else [disabled_row()], "nextCursor": None}
        if method == "plugin/skill/read": return {"contents": "MOCK Data skill; no execution"}
        if method == "turn/start": return {"turn": {"id": "mock-turn", "status": "inProgress"}}
        if method == "thread/read": return {"thread": {"id": "mock-thread"}}
        if method == "thread/items/list":
            commands = [{"id": "read-mock", "type": "commandExecution", "command": "cat " + str(PROBE.DATA_ROOT / "skills/index/SKILL.md"),
                "status": "completed", "exitCode": 0, "aggregatedOutput": "MOCK skill read"},
                {"id": "control-mock", "type": "commandExecution", "command": shlex.join(PROBE.model_control_argv(self.paths)),
                "status": "completed", "exitCode": 0, "aggregatedOutput": json.dumps(control_payload())},
                {"id": "exec-mock", "type": "commandExecution", "command": "python3 isolation_calculation.py",
                "status": "completed", "exitCode": 0, "aggregatedOutput": None}]
            for item in commands: item["cwd"] = str(self.paths["output"])
            self.events = [{"threadId": "mock-thread", "turnId": "mock-turn", "item": item} for item in commands]
            return {"data": [{"turnId": "mock-turn", "item": item} for item in commands]}
        raise AssertionError(method)

    def send(self, message):
        Draft7Validator(self.schemas["ClientNotification.json"]).validate(message)
        self.calls.append(("initialized-notification", message))

    def wait_terminal(self, thread, turn, deadline):
        return {"id": turn, "status": "completed", "error": None}


class IsolationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = shutil.which("codex")
        if not executable: raise unittest.SkipTest("Installed Codex schemas unavailable")
        directory = tempfile.TemporaryDirectory(prefix="dsc26-isolation-schemas-")
        cls.addClassCleanup(directory.cleanup)
        path = Path(directory.name)
        generated = subprocess.run([executable, "app-server", "generate-json-schema", "--experimental", "--out", str(path)],
            capture_output=True, text=True, timeout=30, check=False)
        if generated.returncode: raise AssertionError(generated.stderr)
        cls.schemas = {str(file.relative_to(path)): json.loads(file.read_text()) for file in path.rglob("*.json")}

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="dsc26-MOCK-isolation-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        released, output = root / "released", root / "output"
        released.mkdir(); output.mkdir()
        self.paths = {"output": output, "released": released, "input": released / "synthetic.csv",
            "input_bytes": b"product,units\nA,2\nA,3\nB,5\n", "sentinel": root / "denied.txt",
            "link": output / "denied-link", "control_result": output / "control.json",
            "outside_write": root / "outside-write-denied.txt",
            "model_control_script": released / "control_check.py", "model_control_result": output / "model-control-result.json",
            "allowed_image": released / "allowed.png", "denied_image": root / "denied.png",
            "image_link": output / "denied-image-link"}
        self.paths["input"].write_bytes(self.paths["input_bytes"])
        self.paths["sentinel"].write_text("RANDOM_SYNTHETIC_VALUE_NOT_IN_PROMPT")
        self.paths["allowed_image"].write_bytes(PROBE.PNG); self.paths["denied_image"].write_bytes(PROBE.PNG)
        self.paths["link"].symlink_to(self.paths["sentinel"])
        self.paths["image_link"].symlink_to(self.paths["denied_image"])
        expected = json.dumps({"row_count": 3, "group_totals": {"A": 5, "B": 5}, "total_units": 10})
        self.paths["control_result"].write_text(expected)
        (output / "isolation_result.json").write_text(expected)
        (output / "isolation_calculation.py").write_text("# MOCK ARTIFACT ONLY; NOT EXECUTED\n")
        self.paths["model_control_result"].write_text(expected)
        self.paths["model_control_script"].write_text(PROBE.control_code(self.paths["input"], self.paths["sentinel"],
            self.paths["link"], self.paths["model_control_result"], self.paths["outside_write"], ("127.0.0.1", 12345)))
        self.rpc = MockRPC(self.schemas, self.paths, "mock-profile")

    def model_report(self, **values):
        return {"model_control_source": {"path": str(self.paths["model_control_script"]),
            "sha256": PROBE.sha256(self.paths["model_control_script"].read_bytes()).hexdigest()}, **values}

    def test_all_actual_emitted_request_shapes_use_experimental_native_schema(self):
        PROBE.initialize(self.rpc, time.monotonic() + 20)
        self.rpc.request("config/read", {"cwd": str(self.paths["output"]), "includeLayers": False}, time.monotonic() + 20)
        report = self.model_report(model_turn_requested=False)
        listener = MagicMock()
        listener.__enter__.return_value = listener
        listener.getsockname.return_value = ("127.0.0.1", 12345)
        listener.accept.return_value = (MagicMock(), ("127.0.0.1", 11111))
        with patch.object(PROBE.socket, "socket", return_value=listener), \
             patch.object(PROBE.socket, "create_connection", return_value=MagicMock()):
            PROBE.run_control(self.rpc, self.paths, "mock-profile", report, time.monotonic() + 20)
        fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
        with patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
             patch.object(PROBE, "expected_resource_bytes", return_value=b"MOCK skill read"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", report)
        methods = {method for method, _ in self.rpc.calls}
        self.assertEqual(methods, {"initialize", "initialized-notification", "config/read", "permissionProfile/list",
            "command/exec", "thread/start", "mcpServerStatus/list", "plugin/skill/read", "turn/start", "thread/read", "thread/items/list"})
        thread = next(params for method, params in self.rpc.calls if method == "thread/start")
        self.assertEqual(thread["permissions"], "mock-profile")
        self.assertNotIn("sandbox", thread)
        command = next(params for method, params in self.rpc.calls if method == "command/exec")
        self.assertEqual(command["permissionProfile"], "mock-profile")
        self.assertNotIn("sandboxPolicy", command)
        turn = next(params for method, params in self.rpc.calls if method == "turn/start")
        self.assertEqual(turn["input"][1]["path"], "plugin://data-analytics@openai-curated-remote")
        self.assertNotIn("MOCK Data skill", turn["input"][0]["text"])
        self.assertNotIn('"total_units": 10', turn["input"][0]["text"])
        self.assertNotIn('"row_count": 3', turn["input"][0]["text"])
        self.assertIn(shlex.join([str(Path(PROBE.sys.executable).resolve()), "-I", "-S",
            str(self.paths["model_control_script"].resolve())]), turn["input"][0]["text"])
        self.assertEqual(report["model_control_receipts"][0]["command_id"], "control-mock")
        self.assertTrue(report["mcp_inventory_after"]["validated_disabled_only"])
        self.assertTrue(report["mcp_inventory"]["validated_disabled_only"])
        self.assertEqual(report["mcp_inventory"]["pages"][0]["rows"], [disabled_row()])

    def test_unresolved_mcp_inventory_blocks_before_any_model_turn(self):
        self.rpc.mcp = True
        with self.assertRaisesRegex(_Stop, "MCP inventory row is not safely disabled"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", {"model_turn_requested": False})
        self.assertNotIn("turn/start", [method for method, _ in self.rpc.calls])

    def test_complete_disabled_inventory_is_retained_across_all_pages(self):
        rpc = MagicMock()
        rpc.request.side_effect = [{"data": [disabled_row("computer-use")], "nextCursor": "1"},
            {"data": [disabled_row("node_repl")], "nextCursor": None}]
        report = {}
        PROBE.inventory_disabled_only(rpc, "actual-shaped-thread", time.monotonic() + 20, report)
        calls = rpc.request.call_args_list
        for call in calls:
            Draft7Validator(self.schemas["v2/ListMcpServerStatusParams.json"]).validate(call.args[1])
        self.assertNotIn("cursor", calls[0].args[1])
        self.assertEqual(calls[1].args[1]["cursor"], "1")
        self.assertTrue(report["mcp_inventory"]["validated_disabled_only"])
        self.assertEqual([page["rows"][0]["name"] for page in report["mcp_inventory"]["pages"]],
            ["computer-use", "node_repl"])

    def test_only_explicit_disabled_complete_empty_capabilities_are_accepted(self):
        invalid_rows = []
        for status in ("connected", "starting", "failed", "notStarted", "authenticationRequired", "cancelled", None, "unknown"):
            invalid_rows.append({**disabled_row(), "runtimeStatus": status})
        for key, value in (("tools", {"mock_tool": {}}), ("tools", []), ("toolsError", "mock discovery failure"),
            ("resources", [{"uri": "mock://resource"}]), ("resourceTemplates", [{"uriTemplate": "mock://{id}"}]),
            ("serverInfo", {}), ("serverCapabilities", {}), ("authStatus", "unrecognized"), ("unknownCapability", {})):
            invalid_rows.append({**disabled_row(), key: value})
        for key in disabled_row():
            row = disabled_row(); del row[key]; invalid_rows.append(row)
        for row in invalid_rows:
            rpc = MagicMock(); rpc.request.return_value = {"data": [row], "nextCursor": None}
            report = {}
            with self.subTest(row=row), self.assertRaisesRegex(_Stop, "not safely disabled"):
                PROBE.inventory_disabled_only(rpc, "thread", time.monotonic() + 20, report)
            self.assertFalse(report["mcp_inventory"]["validated_disabled_only"])
            self.assertEqual(report["mcp_inventory"]["pages"][0]["rows"], [row])

    def test_empty_inventory_still_requires_complete_terminal_pagination(self):
        rpc = MagicMock(); rpc.request.return_value = {"data": [], "nextCursor": None}
        report = {}
        PROBE.inventory_disabled_only(rpc, "thread", time.monotonic() + 20, report)
        self.assertTrue(report["mcp_inventory"]["validated_disabled_only"])
        for pages in ([{"data": []}], [{"data": [], "nextCursor": "loop"}, {"data": [], "nextCursor": "loop"}],
            [{"data": [disabled_row()], "nextCursor": "1"}, {"data": [disabled_row()], "nextCursor": None}]):
            rpc = MagicMock(); rpc.request.side_effect = pages; report = {}
            with self.subTest(pages=pages), self.assertRaises(_Stop):
                PROBE.inventory_disabled_only(rpc, "thread", time.monotonic() + 20, report)
            self.assertFalse(report["mcp_inventory"]["validated_disabled_only"])

    def test_override_values_are_native_toml_and_disable_each_known_source(self):
        values = PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"],
            ["server.with.dots"], ["browser@openai-bundled", PROBE.SPEC.plugin_id])
        parsed = {}
        for value in values: parsed.update(tomllib.loads(value))
        self.assertEqual(parsed["default_permissions"], "mock-profile")
        rules = parsed["permissions"]["mock-profile"]
        self.assertEqual(rules["filesystem"][":root"], "deny")
        self.assertFalse(rules["network"]["enabled"])
        self.assertFalse(parsed["mcp_servers"]["server.with.dots"]["enabled"])
        self.assertFalse(parsed["features"]["apps"])
        self.assertFalse(parsed["features"]["view_image"])
        self.assertFalse(parsed["features"]["memories"])
        self.assertEqual(parsed["web_search"], "disabled")
        self.assertTrue(parsed["features"]["plugins"])
        self.assertTrue(parsed["features"]["code_mode_host"])
        self.assertTrue(parsed["plugins"][PROBE.SPEC.plugin_id]["enabled"])
        self.assertFalse(parsed["plugins"]["browser@openai-bundled"]["enabled"])
        self.assertFalse(parsed["plugins"]["_default"]["enabled"])
        self.assertNotIn("extends", rules)

    def test_transport_passes_literal_overrides_without_shell_or_global_mutation(self):
        values = ['features={"apps"=false}', 'default_permissions="literal$(not-a-command)"']
        with patch("suiroai.integration.native.subprocess.Popen") as launch, \
             patch("suiroai.integration.native.selectors.DefaultSelector"):
            _Transport("codex", self.paths["output"], io.StringIO(), config_overrides=values)
        self.assertEqual(launch.call_args.args[0], ["codex", "-c", values[0], "-c", values[1],
            "app-server", "--listen", "stdio://"])
        self.assertNotIn("shell", launch.call_args.kwargs)
        with patch("suiroai.integration.native.subprocess.Popen") as launch:
            with self.assertRaises(ValueError):
                _Transport("codex", self.paths["output"], io.StringIO(), config_overrides="")
            launch.assert_not_called()

    def test_physical_scratch_and_current_tmpdir_denies_preserve_narrow_positive_grants(self):
        current_tmpdir = self.paths["released"].parent / "native-current-temp"
        with patch.dict(PROBE.os.environ, {"TMPDIR": str(current_tmpdir)}):
            values = PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"], [], [])
        filesystem = tomllib.loads(values[1])["permissions"]["mock-profile"]["filesystem"]
        for root in ("/private/tmp", "/private/var/tmp", str(current_tmpdir.resolve())):
            self.assertEqual(filesystem[root], "deny")
        self.assertEqual(filesystem[str(self.paths["released"].resolve())], "read")
        self.assertEqual(filesystem[str(self.paths["output"].resolve())], "write")
        self.assertEqual(filesystem[str(PROBE.DATA_ROOT)], "read")
        self.assertEqual(filesystem[str(Path(PROBE.sys.base_prefix).resolve())], "read")
        self.assertEqual(filesystem[":root"], "deny")
        self.assertEqual(filesystem[":minimal"], "read")
        with patch.dict(PROBE.os.environ, {"TMPDIR": "/tmp"}):
            values = PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"], [], [])
        filesystem = tomllib.loads(values[1])["permissions"]["mock-profile"]["filesystem"]
        self.assertEqual(filesystem[str(Path("/tmp").resolve())], "deny")

    def test_actual_control_failure_shape_retains_allowed_when_denied_before_exit_guard(self):
        original = self.rpc.request
        def request(method, params, deadline, cancellation=None):
            result = original(method, params, deadline, cancellation)
            if method == "command/exec":
                parsed = json.loads(result["stdout"])
                for name in ("sentinel_open", "symlink_open", "outside_write"):
                    parsed["checks"][name] = {"denied": False}
                result.update({"exitCode": 7, "stdout": json.dumps(parsed)})
            return result
        self.rpc.request = request
        listener = MagicMock()
        listener.__enter__.return_value = listener
        listener.getsockname.return_value = ("127.0.0.1", 12345)
        listener.accept.return_value = (MagicMock(), ("127.0.0.1", 11111))
        report = {"model_turn_requested": False}
        with patch.object(PROBE.socket, "socket", return_value=listener), \
             patch.object(PROBE.socket, "create_connection", return_value=MagicMock()), \
             self.assertRaisesRegex(_Stop, "Deterministic native permission controls failed"):
            PROBE.run_control(self.rpc, self.paths, "mock-profile", report, time.monotonic() + 20)
        self.assertEqual(report["allowed_when_denied"], ["sentinel_open", "symlink_open", "outside_write"])
        self.assertEqual(report["native_control_checks"]["network"], {"denied": True, "error_type": "PermissionError", "errno": 13})
        self.assertFalse(report["model_turn_requested"])

    def test_control_code_is_harness_authored_compilable_without_execution(self):
        source = PROBE.control_code(self.paths["input"], self.paths["sentinel"], self.paths["link"],
            self.paths["control_result"], self.paths["outside_write"], ("127.0.0.1", 12345))
        compile(source, "harness_authored_control", "exec")
        self.assertIn("except PermissionError", source)
        self.assertNotIn("token_hex", source)

    def test_config_response_projected_before_logging(self):
        transport = PROBE.ProjectedTransport.__new__(PROBE.ProjectedTransport)
        transport.log, transport.log_bytes, transport.recording_exhausted = io.StringIO(), 0, False
        transport.record("received", {"id": 2, "result": {"config": {"mcp_servers": {
            "server": {"authorization": "DO_NOT_LOG", "other": "SENSITIVE_OTHER"}}, "private_unknown": "PRIVATE"}}})
        captured = transport.log.getvalue()
        self.assertIn("server", captured)
        self.assertNotIn("DO_NOT_LOG", captured)
        self.assertNotIn("SENSITIVE_OTHER", captured)
        self.assertNotIn("PRIVATE", captured)
        transport.record("received", {"id": 3, "result": {"contents": "PRIVATE_SKILL_MARKDOWN"}})
        transport.record("received", {"item": {"id": "r", "type": "reasoning", "summary": "PRIVATE_SUMMARY"}})
        captured = transport.log.getvalue()
        self.assertNotIn("PRIVATE", captured)
        self.assertIn("contents_sha256", captured)

    def test_generated_png_all_crcs_and_decoded_scanline_are_valid(self):
        data, offset, raw = PROBE.PNG, 8, b""
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        kinds = []
        while offset < len(data):
            length = struct.unpack(">I", data[offset:offset+4])[0]
            kind = data[offset+4:offset+8]; payload = data[offset+8:offset+8+length]
            crc = struct.unpack(">I", data[offset+8+length:offset+12+length])[0]
            self.assertEqual(crc, zlib.crc32(kind + payload) & 0xffffffff)
            if kind == b"IDAT": raw += payload
            kinds.append(kind); offset += length + 12
        self.assertEqual(kinds, [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(zlib.decompress(raw), b"\0\xff\0\0\xff")

    def test_resource_attribution_rejects_echo_and_shell_masks(self):
        path = str(PROBE.DATA_ROOT / "skills/index/SKILL.md")
        self.assertTrue(PROBE.reads_data_resource(f'/bin/zsh -lc "cat {path}"'))
        self.assertFalse(PROBE.reads_data_resource(f'echo cat {path}'))
        self.assertFalse(PROBE.reads_data_resource(f'cat {path} || false'))

    def test_protected_file_hashes_detect_replacement(self):
        before = PROBE.protected_hashes(self.paths)
        self.paths["sentinel"].write_text("changed")
        self.assertNotEqual(before, PROBE.protected_hashes(self.paths))

    def test_missing_or_malformed_config_is_blocked(self):
        for response in ({}, {"config": None}, {"config": {"mcp_servers": []}}, {"config": {"plugins": {"bad": False}}}):
            with self.subTest(response=response), self.assertRaises(_Stop): PROBE.config_maps(response)

    def test_effective_feature_or_profile_mismatch_is_blocked(self):
        values = PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"], [], [])
        config = {}
        for value in values: config.update(tomllib.loads(value))
        fs = config["permissions"]["mock-profile"]["filesystem"]
        PROBE.verify_effective_config(config, "mock-profile", fs)
        config["features"]["apps"] = True
        with self.assertRaises(_Stop): PROBE.verify_effective_config(config, "mock-profile", fs)
        config["features"]["apps"] = False
        config["features"]["code_mode_host"] = False
        with self.assertRaises(_Stop): PROBE.verify_effective_config(config, "mock-profile", fs)

    def test_exact_native_serialized_null_metadata_is_equivalent_without_changing_grants(self):
        config = {}
        for value in PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"], [], []):
            config.update(tomllib.loads(value))
        profile = config["permissions"]["mock-profile"]
        expected = dict(profile["filesystem"])
        # Exact Rust structs derive Serialize: absent Option fields become null.
        profile.update({"description": None, "extends": None, "workspace_roots": None})
        profile["filesystem"]["glob_scan_max_depth"] = None
        profile["network"].update({"domains": None, "proxy_url": None, "allow_local_binding": None})
        PROBE.verify_effective_config(config, "mock-profile", expected)
        comparison = PROBE.profile_comparison(config, "mock-profile", expected)
        self.assertEqual(comparison["filesystem_differences"], {})
        self.assertTrue(comparison["filesystem_matches"])
        self.assertTrue(comparison["network_matches"])
        self.assertEqual(comparison["normalization"], ["glob_scan_max_depth:null equivalent to absent"])
        self.assertIsNone(profile["filesystem"]["glob_scan_max_depth"])

    def test_nonnull_metadata_extra_grant_or_wrong_network_still_fail_closed_with_diagnostic(self):
        for case in ("depth", "extra", "grant", "network", "unknown_null"):
            config = {}
            for value in PROBE.profile_overrides("mock-profile", self.paths["released"], self.paths["output"], [], []):
                config.update(tomllib.loads(value))
            profile = config["permissions"]["mock-profile"]
            expected = dict(profile["filesystem"])
            if case == "depth": profile["filesystem"]["glob_scan_max_depth"] = 3
            if case == "extra": profile["filesystem"]["/unexpected-read"] = "read"
            if case == "grant": profile["filesystem"][":root"] = "read"
            if case == "network": profile["network"]["enabled"] = True
            if case == "unknown_null": profile["filesystem"]["unknown_metadata"] = None
            with self.subTest(case=case), self.assertRaises(_Stop):
                PROBE.verify_effective_config(config, "mock-profile", expected)
            comparison = PROBE.profile_comparison(config, "mock-profile", expected)
            self.assertFalse(comparison["filesystem_matches"] and comparison["network_matches"])
            self.assertEqual(comparison["expected"]["filesystem"], expected)

    def test_selected_profile_log_projection_omits_other_profiles_and_network_secrets(self):
        config = {"permissions": {"mock-profile": {"filesystem": {":root": "deny", "glob_scan_max_depth": None},
            "network": {"enabled": False, "proxy_url": "PRIVATE_PROXY_URL", "mitm": {"secret": "PRIVATE_MITM"}}},
            "OTHER_PRIVATE_PROFILE": {"description": "PRIVATE_DESCRIPTION"}}, "private": "PRIVATE_CONFIG"}
        transport = PROBE.ProjectedTransport.__new__(PROBE.ProjectedTransport)
        transport.log, transport.log_bytes, transport.recording_exhausted = io.StringIO(), 0, False
        transport.selected_profile = "mock-profile"
        transport.record("received", {"id": 5, "result": {"config": config}})
        captured = transport.log.getvalue()
        self.assertNotIn("PRIVATE", captured)
        result = json.loads(captured)["message"]["result"]["selected_profile"]
        self.assertEqual(result["filesystem"], {":root": "deny", "glob_scan_max_depth": None})
        self.assertEqual(result["network"]["enabled"], False)
        self.assertEqual(result["network"]["other_nonnull_field_names"], ["mitm", "proxy_url"])

    def test_resource_read_receipt_preserves_truncation_without_faking_output_equality(self):
        item = {"type": "commandExecution", "id": "read", "status": "completed", "exitCode": 0,
                "cwd": str(self.paths["output"]), "command": "cat " + str(PROBE.DATA_ROOT / "skills/index/SKILL.md"),
                "aggregatedOutput": "MOCK\n... command output truncated for persistence ...\nresource"}
        event_item = {**item, "aggregatedOutput": "MOCK full streamed resource"}
        with patch.object(PROBE, "expected_resource_bytes", return_value=b"MOCK full streamed resource"):
            receipts = PROBE.resource_receipts([{"turnId": "t", "item": item}],
                [{"threadId": "r", "turnId": "t", "item": event_item}], "r", "t")
        self.assertEqual(len(receipts), 1)
        self.assertFalse(receipts[0]["stream_and_persisted_output_equal"])

    def test_empty_wrong_or_unexplained_resource_output_never_proves_application(self):
        base = {"type": "commandExecution", "id": "read", "status": "completed", "exitCode": 0,
            "cwd": str(self.paths["output"]), "command": "cat " + str(PROBE.DATA_ROOT / "skills/index/SKILL.md")}
        for streamed, persisted in ((None, None), ("", ""), ("echoed fake", "echoed fake"), ("REAL", "unexplained mismatch")):
            item, event = {**base, "aggregatedOutput": persisted}, {**base, "aggregatedOutput": streamed}
            with self.subTest(streamed=streamed), patch.object(PROBE, "expected_resource_bytes", return_value=b"REAL"):
                self.assertEqual(PROBE.resource_receipts([{"turnId": "t", "item": item}],
                    [{"threadId": "r", "turnId": "t", "item": event}], "r", "t"), [])

    def test_unexpected_model_tool_is_not_accepted(self):
        original = self.rpc.request
        def request(method, params, deadline, cancellation=None):
            result = original(method, params, deadline, cancellation)
            if method == "thread/items/list": result["data"].append({"turnId": "mock-turn", "item": {"type": "webSearch"}})
            return result
        self.rpc.request = request
        fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
        with patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
             self.assertRaisesRegex(_Stop, "Unexpected native tool/item"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", self.model_report())

    def test_other_script_or_echo_cannot_satisfy_exact_calculation_receipt(self):
        for command in ("echo python3 isolation_calculation.py", "python3 nested/isolation_calculation.py",
                        "python3 isolation_calculation.py || true"):
            rpc = MockRPC(self.schemas, self.paths, "mock-profile")
            original = rpc.request
            def request(method, params, deadline, cancellation=None):
                result = original(method, params, deadline, cancellation)
                if method == "thread/items/list":
                    for entry in result["data"]:
                        if entry["item"]["id"] == "exec-mock": entry["item"]["command"] = command
                return result
            rpc.request = request
            fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
            with self.subTest(command=command), patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
                 self.assertRaisesRegex(_Stop, "No verified execution of the exact calculation script"):
                PROBE.run_model(rpc, self.paths, "mock-profile", self.model_report())

    def test_completed_prose_only_turn_has_explicit_zero_command_evidence(self):
        original = self.rpc.request
        def request(method, params, deadline, cancellation=None):
            result = original(method, params, deadline, cancellation)
            if method == "thread/items/list":
                result["data"] = [{"turnId": "mock-turn", "item": {"type": "agentMessage",
                    "text": "MOCK unverified diagnostic: code-mode host is disabled"}}]
                self.rpc.events = []
            return result
        self.rpc.request = request
        fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
        report = self.model_report()
        with patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
             self.assertRaisesRegex(_Stop, "without actual command execution evidence"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", report)
        self.assertEqual(report["native_turn_item_types"], ["agentMessage"])
        self.assertEqual(report["command_execution_evidence"], {"persisted_count": 0, "streamed_count": 0,
            "matched_count": 0, "matched_command_ids": [], "agent_reported_errors_are_unverified": True})

    def test_unmatched_native_command_observations_are_distinct_from_no_commands(self):
        original = self.rpc.request
        def request(method, params, deadline, cancellation=None):
            result = original(method, params, deadline, cancellation)
            if method == "thread/items/list": self.rpc.events = []
            return result
        self.rpc.request = request
        fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
        report = self.model_report()
        with patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
             self.assertRaisesRegex(_Stop, "did not match persisted command execution evidence"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", report)
        self.assertEqual(report["command_execution_evidence"]["persisted_count"], 3)
        self.assertEqual(report["command_execution_evidence"]["matched_count"], 0)

    def test_delegated_control_receipt_rejects_echo_wrong_script_and_non_os_denials(self):
        base = {"id": "mock-control", "command": shlex.join(PROBE.model_control_argv(self.paths)),
            "cwd": str(self.paths["output"]), "exitCode": 0, "aggregatedOutput": json.dumps(control_payload())}
        self.assertEqual(len(PROBE.model_control_receipts([base], self.paths)), 1)
        shell = {**base, "command": "/bin/zsh -lc " + repr(base["command"])}
        self.assertEqual(len(PROBE.model_control_receipts([shell], self.paths)), 1)
        invalid = [{**base, "command": "echo " + base["command"]}, {**base, "exitCode": 7},
            {**base, "command": base["command"] + " || true"},
            {**base, "command": "python3 " + str(self.paths["output"] / "control_check.py")},
            {**base, "cwd": str(self.paths["released"])}, {**base, "aggregatedOutput": "Permission denied (MOCK prose)"}]
        for runner in ("python3", "./python3", str(self.paths["output"] / "python3"), str(self.paths["output"] / "bin/python3")):
            invalid.append({**base, "command": shlex.join([runner, "-I", "-S", str(self.paths["model_control_script"].resolve())])})
        for flags in ([], ["-I"], ["-S"], ["-S", "-I"], ["-I", "-S", "-B"]):
            invalid.append({**base, "command": shlex.join([str(Path(PROBE.sys.executable).resolve()),
                *flags, str(self.paths["model_control_script"].resolve())])})
        for wrapper in ("zsh", "./sh", str(self.paths["output"] / "zsh"), str(self.paths["output"] / "bin/bash")):
            invalid.append({**base, "command": shlex.join([wrapper, "-lc", base["command"]])})
        invalid.append({**base, "command": "printf '%s\\n' '# fake' > other.py\n" + base["command"]})
        for name in control_payload()["checks"]:
            payload = control_payload(); payload["checks"][name] = {"denied": True, "type": "RuntimeError", "errno": 13}
            invalid.append({**base, "aggregatedOutput": json.dumps(payload)})
            payload = control_payload(); payload["checks"][name] = {"denied": False}
            invalid.append({**base, "aggregatedOutput": json.dumps(payload)})
        for item in invalid:
            with self.subTest(item=item): self.assertEqual(PROBE.model_control_receipts([item], self.paths), [])

    def test_released_control_integrity_is_measured_even_when_model_turn_fails(self):
        for tamper in (False, True):
            listener = MagicMock(); listener.__enter__.return_value = listener
            listener.getsockname.return_value = ("127.0.0.1", 12345)
            listener.accept.return_value = (MagicMock(), ("127.0.0.1", 11111))
            def fail_model(*args):
                if tamper: self.paths["model_control_script"].write_text("# MOCK altered source\n")
                raise _Stop("runtime_error", "MOCK native failure")
            report = {}
            with self.subTest(tamper=tamper), patch.object(PROBE.socket, "socket", return_value=listener), \
                 patch.object(PROBE.socket, "create_connection", return_value=MagicMock()), \
                 patch.object(PROBE, "run_model", side_effect=fail_model), self.assertRaises(_Stop):
                PROBE.run_model_with_control(self.rpc, self.paths, "mock-profile", report)
            self.assertTrue(report["model_control_listener_positive"])
            self.assertEqual(report["model_control_source"]["unchanged"], not tamper)
            self.assertIn("sha256_after", report["model_control_source"])

    def test_newly_active_mcp_after_data_turn_blocks_and_retains_both_inventories(self):
        original = self.rpc.request
        calls = 0
        def request(method, params, deadline, cancellation=None):
            nonlocal calls
            result = original(method, params, deadline, cancellation)
            if method == "mcpServerStatus/list":
                calls += 1
                if calls == 2: result["data"][0]["runtimeStatus"] = "connected"
            return result
        self.rpc.request = request
        fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest(); report = self.model_report()
        with patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
             self.assertRaisesRegex(_Stop, "not safely disabled"):
            PROBE.run_model(self.rpc, self.paths, "mock-profile", report)
        self.assertTrue(report["mcp_inventory"]["validated_disabled_only"])
        self.assertFalse(report["mcp_inventory_after"]["validated_disabled_only"])
        self.assertEqual(report["mcp_inventory_after"]["pages"][0]["rows"][0]["runtimeStatus"], "connected")

    def test_delegated_control_must_precede_calculation_and_outside_write_must_remain_absent(self):
        for case in ("late_control", "outside_write"):
            rpc = MockRPC(self.schemas, self.paths, "mock-profile"); original = rpc.request
            def request(method, params, deadline, cancellation=None):
                result = original(method, params, deadline, cancellation)
                if method == "thread/items/list":
                    if case == "late_control": result["data"][1], result["data"][2] = result["data"][2], result["data"][1]
                    else: self.paths["outside_write"].write_text("MOCK denied-path violation")
                return result
            rpc.request = request; report = self.model_report()
            fake_hash = PROBE.sha256(b"MOCK Data skill; no execution").hexdigest()
            expected_error = "did not precede calculation" if case == "late_control" else "write outside"
            with self.subTest(case=case), patch.object(PROBE, "SPEC", PROBE.DataPluginSpec(skill_sha256=fake_hash)), \
                 self.assertRaisesRegex(_Stop, expected_error):
                PROBE.run_model(rpc, self.paths, "mock-profile", report)

    def test_report_omits_all_reasoning_fields_and_redacts_credentials(self):
        result = PROBE.retained_report({"items": [{"type": "reasoning", "id": "r", "content": "PRIVATE",
            "summary": "PRIVATE_SUMMARY"}], "credentials": {"api_key": "PRIVATE_KEY"},
            "safe": "Bearer PRIVATE_BEARER"})
        text = json.dumps(result)
        self.assertNotIn("PRIVATE", text)
        self.assertTrue(result["items"][0]["content_omitted"])
        self.assertEqual(result["items"][0]["id"], "r")


if __name__ == "__main__": unittest.main()
