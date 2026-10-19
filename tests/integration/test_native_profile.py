"""Local policy and fake Python CLI checks; no native/model acceptance.

Verify supported plugin metadata, restricted roots, effective host settings,
and bounded inventory handling using local fixtures and fake CLI behavior.

Requirement context for these component checks:
Check deployment compatibility and isolation for the demonstrated native
worker before dispatch; experimental host settings remain deployment-specific.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
"""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import os
import tempfile
import time
import tomllib
import unittest
from unittest.mock import patch

from suiroai.integration import native_profile as policy
from suiroai.integration.native import DataPluginSpec, _Transport


def disabled_row():
    return {"name": "mock-disabled", "runtimeStatus": "disabled", "pluginId": None, "httpOrigin": None,
        "serverInfo": None, "serverCapabilities": None, "tools": {}, "toolsError": None,
        "resources": [], "resourceTemplates": [], "authStatus": "unsupported"}


class NativeProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsc26-MOCK-native-profile-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release, self.output = self.root / "released", self.root / "output"
        self.release.mkdir(); self.output.mkdir()
        self.plugin = DataPluginSpec()
        self.overrides = policy.profile_overrides("mock-profile", self.release, self.output,
            ["mock-mcp"], {self.plugin.plugin_id, "mock-other"}, self.plugin)
        self.config = {}
        for value in self.overrides: self.config.update(tomllib.loads(value))
        self.filesystem = self.config["permissions"]["mock-profile"]["filesystem"]

    def verify(self, config):
        policy.verify_restrictions(config, "mock-profile", self.filesystem, ["mock-mcp"],
            {self.plugin.plugin_id, "mock-other"}, self.plugin)

    def test_exact_profile_restricts_scratch_and_preserves_narrow_release_and_output(self):
        self.verify(self.config)
        self.assertEqual(self.filesystem[str(self.release)], "read")
        self.assertEqual(self.filesystem[str(self.output)], "write")
        self.assertEqual(self.filesystem["/private/tmp"], "deny")
        self.assertEqual(self.filesystem["/private/var/tmp"], "deny")
        if os.environ.get("TMPDIR"):
            self.assertEqual(self.filesystem[str(Path(os.environ["TMPDIR"]).resolve())], "deny")
        self.assertEqual(self.filesystem[":root"], "deny")
        self.assertTrue(self.config["features"]["code_mode_host"])
        self.assertFalse(self.config["features"]["apps"])
        serialized = deepcopy(self.config)
        serialized["permissions"]["mock-profile"]["filesystem"]["glob_scan_max_depth"] = None
        self.verify(serialized)

    def test_extra_filesystem_network_or_plugin_privileges_are_rejected(self):
        for defect in ("read", "network", "socket", "plugin", "mcp", "feature", "depth"):
            config = deepcopy(self.config)
            if defect == "read": config["permissions"]["mock-profile"]["filesystem"]["/unreleased"] = "read"
            if defect == "network": config["permissions"]["mock-profile"]["network"]["enabled"] = True
            if defect == "socket": config["permissions"]["mock-profile"]["network"]["dangerously_allow_all_unix_sockets"] = True
            if defect == "plugin": config["plugins"]["new-active"] = {"enabled": True}
            if defect == "mcp": config["mcp_servers"]["new-active"] = {"enabled": True}
            if defect == "feature": config["features"]["code_mode_host"] = False
            if defect == "depth": config["permissions"]["mock-profile"]["filesystem"]["glob_scan_max_depth"] = 4
            with self.subTest(defect=defect), self.assertRaises(policy.NativePolicyError): self.verify(config)

    def test_disabled_inventory_requires_complete_pages_and_explicit_empty_capabilities(self):
        class RPC:
            def __init__(self, pages): self.pages = iter(pages); self.calls = []
            def request(self, method, params, *args):
                self.calls.append((method, params))
                return next(self.pages)
        receipt = {}
        rpc = RPC([{"data": [disabled_row()], "nextCursor": "p2"}, {"data": [], "nextCursor": None}])
        policy.disabled_inventory(rpc,
            "mock-thread", time.monotonic() + 1, None, receipt)
        self.assertTrue(receipt["validated_disabled_only"])
        self.assertEqual(len(receipt["pages"]), 2)
        self.assertTrue(all(params["detail"] == "full" for _, params in rpc.calls))
        self.assertEqual(rpc.calls[1][1]["cursor"], "p2")
        for row in ({**disabled_row(), "runtimeStatus": "notStarted"}, {**disabled_row(), "tools": {"active": {}}},
                    {**disabled_row(), "toolsError": "MOCK_ERROR"}):
            receipt = {}
            with self.subTest(row=row), self.assertRaises(policy.NativePolicyError):
                policy.disabled_inventory(RPC([{"data": [row], "nextCursor": None}]), "mock-thread", time.monotonic() + 1, None, receipt)
            self.assertFalse(receipt["validated_disabled_only"])
            self.assertNotIn("MOCK_ERROR", json.dumps(receipt))

    def test_inventory_missing_terminal_cursor_or_duplicate_names_never_establishes_completeness(self):
        class RPC:
            def __init__(self, pages): self.pages = iter(pages)
            def request(self, *args): return next(self.pages)
        cases = [([{"data": []}], "terminal cursor is missing"),
            ([{"data": [disabled_row(), disabled_row()], "nextCursor": None}], "duplicate server names"),
            ([{"data": [disabled_row()], "nextCursor": "p2"},
              {"data": [disabled_row()], "nextCursor": None}], "duplicate server names")]
        for pages, message in cases:
            receipt = {}
            with self.subTest(message=message), self.assertRaisesRegex(policy.NativePolicyError, message):
                policy.disabled_inventory(RPC(pages), "mock-thread", time.monotonic() + 1, None, receipt)
            self.assertFalse(receipt["validated_disabled_only"])
            if message == "terminal cursor is missing":
                self.assertFalse(receipt["pages"][-1]["next_cursor_present"])
                self.assertFalse(receipt["pages"][-1]["complete"])

    def test_command_output_delta_log_hashes_all_payload_fields_and_preserves_completed_evidence(self):
        transport = _Transport.__new__(_Transport)
        transport.log, transport.log_bytes, transport.recording_exhausted = io.StringIO(), 0, False
        resource = "# PRIVATE_FULL_SKILL_BODY\nNever retain this streamed resource text.\n"
        payload = {"delta": resource, "unexpected_string_payload": resource}
        message = {"method": "item/commandExecution/outputDelta", "params": {
            "threadId": "mock-thread", "turnId": "mock-turn", "itemId": "mock-command", **payload}}
        transport.consume("stdout", json.dumps(message).encode())
        logged = transport.log.getvalue()
        self.assertNotIn("PRIVATE_FULL_SKILL_BODY", logged)
        projected = json.loads(logged)["message"]["params"]
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        self.assertEqual(projected["payload_canonical_json_sha256"], sha256(encoded).hexdigest())
        self.assertEqual(projected["payload_canonical_json_bytes"], len(encoded))
        self.assertEqual(projected["itemId"], "mock-command")
        self.assertTrue(projected["output_payload_omitted"])
        self.assertNotIn("PRIVATE_FULL_SKILL_BODY", json.dumps(policy.sanitize(message)))
        completed = {"method": "item/completed", "params": {"item": {"type": "commandExecution",
            "command": "python3 calculation.py", "aggregatedOutput": "actual calculation result"}}}
        transport.record("received", completed)
        self.assertIn("actual calculation result", transport.log.getvalue())

    def test_fresh_evidence_and_all_root_symlinks_are_rejected_before_use(self):
        evidence = self.root / "native"
        evidence.mkdir()
        (evidence / "native-rpc.jsonl").symlink_to(self.release / "input")
        with self.assertRaisesRegex(policy.NativePolicyError, "fresh and empty"):
            policy.validate_roots(self.release, self.output, evidence)
        (evidence / "native-rpc.jsonl").unlink()
        policy.validate_roots(self.release, self.output, evidence)
        (self.release / "link").symlink_to(self.output)
        with self.assertRaisesRegex(policy.NativePolicyError, "symlink"):
            policy.validate_roots(self.release, self.output, evidence)

    def test_log_projection_omits_full_config_skill_and_every_reasoning_field(self):
        transport = _Transport.__new__(_Transport)
        transport.log, transport.log_bytes, transport.recording_exhausted = io.StringIO(), 0, False
        messages = [{"id": 1, "result": {"config": {"unknown_private": "PRIVATE_CONFIG", "plugins": {}, "mcp_servers": {}}}},
            {"id": 2, "result": {"contents": "PRIVATE_SKILL_BODY"}},
            {"params": {"item": {"type": "reasoning", "id": "r", "content": "PRIVATE_CONTENT",
                "summary": "PRIVATE_SUMMARY", "encrypted_content": "PRIVATE_ENCRYPTED"}}},
            {"method": "item/reasoning/summaryTextDelta", "params": {"text": "PRIVATE_DELTA"}}]
        for message in messages: transport.record("received", message)
        transport.consume("stderr", b"PRIVATE_UNSTRUCTURED_DIAGNOSTIC")
        logged = transport.log.getvalue()
        self.assertNotIn("PRIVATE_", logged)
        self.assertIn("contents_sha256", logged)
        self.assertIn("content_omitted", logged)
        self.assertNotIn("PRIVATE_", json.dumps(policy.sanitize(messages)))


class NativeInventoryTests(unittest.TestCase):
    """Fake executable is local Python; stable CLI argv only, no Codex calls."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsc26-MOCK-native-inventory-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "fake-cli"
        self.plugin = DataPluginSpec()
        self.entry = {"pluginId": self.plugin.plugin_id, "version": self.plugin.version, "installed": True,
            "enabled": True, "source": {"source": "remote", "id": self.plugin.remote_plugin_id}, "private": "PRIVATE_ACCOUNT"}

    def fake_cli(self, code):
        self.executable.write_text("#!" + str(Path(policy.sys.executable).resolve()) + "\n" + code)
        self.executable.chmod(0o700)

    def invoke(self, seconds=3):
        self.receipt = {}
        return policy.bounded_plugin_inventory(self.executable, self.root, time.monotonic() + seconds,
            self.receipt, self.plugin)

    def test_inventory_preserves_all_ids_and_exact_native_remote_identity(self):
        payload = json.dumps({"installed": [self.entry, {"pluginId": "other-installed"}]})
        self.fake_cli("import sys\nassert sys.argv[1:]==['plugin','list','--json']\nsys.stderr.write('benign PATH alias warning\\n')\nprint(" + repr(payload) + ")\n")
        ids, selected = self.invoke()
        self.assertEqual(ids, {self.plugin.plugin_id, "other-installed"})
        self.assertEqual(selected["source_id"], self.plugin.remote_plugin_id)
        self.assertEqual(self.receipt["plugin_inventory_command"]["status"], "verified")
        self.assertNotIn("PRIVATE_ACCOUNT", json.dumps(self.receipt))

    def test_version_source_ambiguity_and_native_fallback_fail_with_receipts(self):
        for defect in ("version", "local", "duplicate", "fallback"):
            entry = deepcopy(self.entry)
            if defect == "version": entry["version"] = "wrong"
            if defect == "local": entry["source"]["source"] = "local"
            payload = json.dumps({"installed": [entry, entry] if defect == "duplicate" else [entry]})
            code = "import sys\n"
            if defect == "fallback": code += "sys.stderr.write(" + repr(policy.FALLBACK_WARNING_PREFIX + " PRIVATE_ERROR\n") + ")\n"
            self.fake_cli(code + "print(" + repr(payload) + ")\n")
            with self.subTest(defect=defect), self.assertRaises(policy.NativePolicyError): self.invoke()
            receipt = self.receipt["plugin_inventory_command"]
            self.assertTrue(receipt["cleanup"]["direct_child_reaped"])
            self.assertNotIn("PRIVATE_ERROR", json.dumps(receipt))
            self.assertEqual(receipt["diagnostics"]["fallback_observed"], defect == "fallback")

    def test_output_caps_and_timeout_terminate_group_with_measurements(self):
        for stream, count in ((1, 2 * 1024 * 1024 + 65536), (2, 64 * 1024 + 65536)):
            self.fake_cli("import os,time\nos.write(" + str(stream) + ",b'x'*" + str(count) + ")\ntime.sleep(10)\n")
            with self.subTest(stream=stream), self.assertRaises(policy.NativePolicyError) as raised: self.invoke()
            self.assertEqual(raised.exception.code, "budget_exhausted")
            receipt = self.receipt["plugin_inventory_command"]
            self.assertTrue(receipt["cleanup"]["direct_child_reaped"])
            self.assertGreater(receipt[("stdout" if stream == 1 else "stderr") + "_observed_bytes"], 0)
        self.fake_cli("import time\ntime.sleep(10)\n")
        with self.assertRaises(policy.NativePolicyError) as raised: self.invoke(seconds=.1)
        self.assertEqual(raised.exception.code, "timeout")
        self.assertTrue(self.receipt["plugin_inventory_command"]["cleanup"]["direct_child_reaped"])


if __name__ == "__main__": unittest.main()
