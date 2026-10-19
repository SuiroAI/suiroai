"""Exercise DSC-59 execution boundaries with explicit test doubles.

These tests verify receipt retention and refusal to invent analytical success;
patched inventory calls do not establish live native integration acceptance.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from suiroai.demo.runtime import DemoNativeHost
from suiroai.demo.worker import audit_development_partition
from suiroai.integration.artifacts import ArtifactStore
from suiroai.integration.native import NativeHost
from suiroai.preparation.worker import PreparationError, inspect_sales_partition


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

    def test_demo_host_uses_shared_native_execution_without_a_preflight_stop(self):
        self.assertIs(DemoNativeHost.execute, NativeHost.execute)

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
        expected = inspect_sales_partition(raw, source)
        self.assertEqual(development, expected["development_csv"])
        self.assertEqual(reserved, expected["reserved_csv"])
        lineage = json.loads(store.read_bytes(audit["controller_only_partition_lineage_ref"]))
        self.assertEqual(lineage, expected["controller_audit"])
        self.assertEqual([row["duplicate_of"] for row in lineage["row_lineage"]], [None, 1, None])
        self.assertEqual(audit["development_distinct_records"], 1)
        self.assertEqual(audit["development_exact_duplicate_excess"], 1)
        self.assertEqual(audit["development_receipt"], expected["development_receipt"])
        self.assertNotIn("reserved", str(audit["development_receipt"]))
        self.assertEqual(set(summary), {"audit_ref", "development_source_records",
            "development_product_store_pairs", "development_unobserved_pair_dates",
            "analytical_model_inputs_released"})
        self.assertEqual(audit["development_observed_pair_dates"], 1)
        self.assertFalse(audit["missing_dates_zero_filled"])
        self.assertIsNone(audit["latest_information_available_date"])
        self.assertFalse(audit["analytical_model_inputs_released"])
        self.assertEqual(store.read_bytes(source), raw)

    def test_controller_inspection_rejects_forged_source_identity_and_lineage_columns(self):
        store = ArtifactStore(self.root / "store")
        raw = b"Product_ID,Store_ID,Transaction_ID,Order_ID,Order_Date,Quantity,Order_Status,Return_Flag,Product_Name,Store_Name,_duplicate_of\n"
        source = store.put_bytes("test-sales", 1, "supplied", raw)
        with self.assertRaisesRegex(PreparationError, "reserved lineage"):
            inspect_sales_partition(raw, source)
        with self.assertRaisesRegex(PreparationError, "hash mismatch"):
            inspect_sales_partition(raw + b"changed", source)

class ApprovedInvestigationTests(unittest.TestCase):
    """Verify production backend dispatch and honest investigation publication.

    Test doubles prove wiring only, never live Data acceptance.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """

    def test_approved_backend_calls_real_investigation_entrypoint(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            store = ArtifactStore(root / "store")
            record = {"artifact_id": "test", "artifact_version": 1, "provenance": "derived"}
            native = {"native_outcome": "completed", "unverified_investigation_text": "TEST findings"}
            consent = lambda approval, proposal: True
            with patch("suiroai.demo.backend.run_investigation", return_value=native) as investigate:
                result = run_approved(store, record, record, record, None, root / "runs", consent)
            investigate.assert_called_once()
            self.assertIs(investigate.call_args.args[5], consent)
            self.assertEqual(result.status, "investigation_completed")
            self.assertEqual(Path(result.investigation_path).read_text(), "TEST findings")
            receipt = json.loads(Path(result.evidence_path).read_text())
            self.assertFalse(receipt["verified_report_available"])
            self.assertEqual(store.read_bytes(result.evidence_ref), Path(result.evidence_path).read_bytes())
            self.assertIsNone(result.download_bytes)

    def test_revoked_investigation_cannot_publish_result(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            with patch("suiroai.demo.backend.run_investigation", return_value={"native_outcome": "completed"}):
                with self.assertRaisesRegex(ValueError, "revoked"):
                    run_approved(ArtifactStore(root / "store"), {}, {}, {}, None,
                        root / "runs", lambda approval, proposal: False)
            self.assertEqual(list((root / "runs").glob("attempt-*.json")), [])

    def test_report_download_uses_immutable_reference_and_stays_unverified(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            store = ArtifactStore(root / "store")
            ref = store.put_bytes("TEST-report", 1, "derived", b"Product_ID,Store_ID,Order_Qty\nTEST-P,TEST-S,5\n")
            record = {"artifact_id": "test", "artifact_version": 1, "provenance": "derived"}
            native = {"native_outcome": "completed", "unverified_report_ref": ref}
            with patch("suiroai.demo.backend.run_investigation", return_value=native):
                result = run_approved(store, record, record, record, None,
                    root / "runs", lambda *_: True)
            self.assertEqual(result.status, "analysis_completed")
            self.assertEqual(result.message, "Analysis complete. Your restocking list is ready to download.")
            self.assertEqual(result.download_name, "restocking.csv")
            self.assertEqual(result.download_mime, "text/csv")
            self.assertEqual(Path(result.report_path).suffix, ".csv")
            self.assertEqual(result.download_bytes, store.read_bytes(ref))
            self.assertEqual(Path(result.report_path).read_bytes(), store.read_bytes(ref))
            self.assertFalse(result.report_verified)

    def test_output_contract_failure_preserves_real_native_receipt(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            store = ArtifactStore(root / "store")
            record = {"artifact_id": "test", "artifact_version": 1, "provenance": "derived"}
            native = {"native_outcome": "completed", "thread_id": "TEST-real-thread",
                "immutable_native_evidence_refs": [], "output_error": "TEST report hash mismatch",
                "unverified_investigation_text": "TEST partial findings"}
            with patch("suiroai.demo.backend.run_investigation", return_value=native):
                result = run_approved(store, record, record, record, None,
                    root / "runs", lambda *_: True)
            self.assertEqual(result.status, "execution_failed")
            self.assertIn("hash mismatch", result.message)
            receipt = json.loads(Path(result.evidence_path).read_text())
            self.assertEqual(receipt["stage_result"]["thread_id"], "TEST-real-thread")
            self.assertEqual(receipt["stage_result"]["native_outcome"], "completed")
            self.assertIsNone(result.download_bytes)

    def test_csv_deliverable_cannot_be_a_renamed_html_report(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            store = ArtifactStore(root / "store")
            ref = store.put_bytes("TEST-html", 1, "derived", b"<html>TEST findings</html>")
            record = {"artifact_id": "test", "artifact_version": 1, "provenance": "derived"}
            native = {"native_outcome": "completed", "unverified_report_ref": ref,
                "unverified_report_name": "report.html", "unverified_report_mime": "text/html"}
            with patch("suiroai.demo.backend.run_investigation", return_value=native):
                result = run_approved(store, record, record, record, None,
                    root / "runs", lambda *_: True)
            self.assertEqual(result.status, "execution_failed")
            self.assertIn("CSV file", result.message)
            self.assertIsNone(result.report_path)
            self.assertIsNone(result.download_bytes)

    def test_primary_csv_and_secondary_html_keep_exact_stored_bytes(self):
        from suiroai.demo.backend import run_approved
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            store = ArtifactStore(root / "store")
            csv_ref = store.put_bytes("TEST-csv", 1, "derived", b"Product_ID,Store_ID,Order_Qty\nP,S,5\n")
            html_ref = store.put_bytes("TEST-html", 1, "derived", b"<html>TEST demo</html>")
            record = {"artifact_id": "test", "artifact_version": 1, "provenance": "derived"}
            native = {"native_outcome": "completed", "unverified_report_ref": csv_ref,
                "unverified_report_name": "restocking.csv", "unverified_report_mime": "text/csv",
                "html_report_ref": html_ref, "html_report_name": "report.html", "html_report_mime": "text/html"}
            with patch("suiroai.demo.backend.run_investigation", return_value=native):
                result = run_approved(store, record, record, record, None,
                    root / "runs", lambda *_: True)
            self.assertEqual(result.status, "analysis_completed")
            self.assertEqual(result.download_bytes, store.read_bytes(csv_ref))
            self.assertEqual(result.html_download_bytes, store.read_bytes(html_ref))
            self.assertEqual(result.html_download_name, "report.html")
            self.assertEqual(Path(result.html_report_path).read_bytes(), store.read_bytes(html_ref))
