"""Exercise DSC-59 blocked execution boundaries with explicit test doubles.

These tests verify receipt retention and refusal to invent analytical success;
patched inventory calls do not establish live native integration acceptance.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from suiroai.demo.backend import MeasuredReview
from suiroai.demo.runtime import DemoNativeHost
from suiroai.demo.worker import audit_development_partition
from suiroai.integration.artifacts import ArtifactStore
from suiroai.integration.native import NativeHost
from suiroai.integration.native_profile import NativePolicyError


class NativeBoundaryTests(unittest.TestCase):
    """Keep discovery errors precise and never silently fall through to a turn."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.release, self.output, self.evidence = [self.root / name for name in ("released", "output", "native")]
        for path in (self.release, self.output, self.evidence):
            path.mkdir()

    def attempt(self):
        return DemoNativeHost().execute(cwd=self.output, prompt="TEST preflight only",
            evidence_dir=self.evidence, timeout_seconds=5, released_root=self.release)

    def test_actual_discovery_failure_retains_receipt_and_never_starts_model(self):
        with patch("suiroai.demo.runtime.policy.validate_supported_plugin"), \
             patch("suiroai.demo.runtime.shutil.which", return_value="/test/codex"), \
             patch("suiroai.demo.runtime.policy.bounded_plugin_inventory",
                side_effect=NativePolicyError("unsupported_integration", "TEST marketplace fallback")), \
             patch.object(NativeHost, "_initialize") as initialize:
            result = self.attempt()
        self.assertEqual(result.error_code, "unsupported_integration")
        self.assertEqual(result.message, "TEST marketplace fallback")
        self.assertFalse(result.evidence["analytical_model_turn_requested"])
        self.assertIsNone(result.thread_id)
        initialize.assert_not_called()
        self.assertTrue((self.evidence / "native-run.json").is_file())
        self.assertEqual(result.evidence["artifact_receipts"][-1]["relative_path"], "native-run.json")

    def test_successful_inventory_still_blocks_unsafe_development_release(self):
        with patch("suiroai.demo.runtime.policy.validate_supported_plugin"), \
             patch("suiroai.demo.runtime.shutil.which", return_value="/test/codex"), \
             patch("suiroai.demo.runtime.policy.bounded_plugin_inventory", return_value=({}, {})), \
             patch.object(NativeHost, "_initialize") as initialize:
            result = self.attempt()
        self.assertEqual(result.outcome, "execution_failed")
        self.assertIn("excluding December", result.message)
        self.assertIsNone(result.turn_id)
        initialize.assert_not_called()

    def test_symlinked_release_is_rejected_without_evidence_write(self):
        self.release.rmdir()
        self.release.symlink_to(self.output, target_is_directory=True)
        result = self.attempt()
        self.assertEqual(result.error_code, "unsupported_integration")
        self.assertFalse((self.evidence / "native-run.json").exists())

    def test_exact_bytes_cannot_substitute_for_independent_numerical_review(self):
        store = ArtifactStore(self.root / "store")
        reviewer = MeasuredReview(store, {})
        self.assertFalse(reviewer.evidence({"artifacts": [{"bytes": 0,
            "byte_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}]}, (b"",)))
        self.assertTrue(reviewer.events[-1]["measured_bytes_match"])
        self.assertFalse(reviewer.events[-1]["accepted"])

    def test_controller_audit_preserves_duplicates_and_never_zero_fills_or_asserts_availability(self):
        store = ArtifactStore(self.root / "store")
        header = b"Product_ID,Store_ID,Transaction_ID,Order_ID,Order_Date,Quantity,Order_Status,Return_Flag,Product_Name,Store_Name\n"
        line = b"TEST-P,TEST-S,T1,O1,2025-11-29,2,Completed,No,TEST product,TEST store\n"
        future = b"TEST-P,TEST-S,T2,O2,2025-12-01,999,Completed,No,TEST product,TEST store\n"
        raw = header + line + line + future
        source = store.put_bytes("test-sales", 1, "supplied", raw)
        submission = {"files": [{"source_role": "transactions", "file_id": "test-sales", "sha256": source["sha256"]}]}
        summary = audit_development_partition(store, submission, {"source_refs": [source]})
        audit = json.loads(store.read_bytes(summary["audit_ref"]))
        development = store.read_bytes(audit["development_ref"])
        reserved = store.read_bytes(audit["controller_only_reserved_ref"])
        self.assertNotIn(b"2025-12-01", development)
        self.assertIn(b"2025-12-01", reserved)
        self.assertEqual(development.count(b"2025-11-29"), 2)
        self.assertEqual(audit["development_observed_pair_dates"], 1)
        self.assertFalse(audit["missing_dates_zero_filled"])
        self.assertIsNone(audit["latest_information_available_date"])
        self.assertFalse(audit["analytical_model_inputs_released"])
        self.assertEqual(store.read_bytes(source), raw)
