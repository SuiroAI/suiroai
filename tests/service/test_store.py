"""A-PR1 (DSC-70): the integration-service store factory and fixture loader.

These tests load a committed mock contract fixture into a real ArtifactStore and check that every
record and external byte artifact round-trips, that the index is well formed, and that the loader
fails closed on unknown refs and invalid records. They assert interface behaviour only; the
fixtures are mock interface examples and establish no analytical acceptance.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from suiroai.contracts import record_ref
from suiroai.contracts.validation import digest
from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.service import FixtureError, load_fixture_bundle, open_store

FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "contracts" / "v0.1.0"


class ServiceStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "store"
        self.store = open_store(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_open_store_returns_artifact_store(self):
        self.assertIsInstance(self.store, ArtifactStore)

    def test_loads_successful_analysis_and_round_trips_records(self):
        index = load_fixture_bundle(self.store, FIXTURES / "successful_analysis.json")

        # Every stage kind is present and refs resolve to identical records.
        self.assertIn("submission", index["records"])
        self.assertIn("report_draft", index["records"])
        self.assertIn("quantity_result", index["records"])
        self.assertEqual(index["provenance"], "mock")
        self.assertTrue(index["notice"])

        bundle = json.loads((FIXTURES / "successful_analysis.json").read_text())
        originals = {record_ref(r)["sha256"]: r for r in bundle["records"]}
        for refs in index["records"].values():
            for ref in refs:
                stored = self.store.read_record(ref)
                self.assertEqual(stored, originals[ref["sha256"]])

    def test_external_byte_artifacts_round_trip(self):
        index = load_fixture_bundle(self.store, FIXTURES / "successful_analysis.json")
        self.assertTrue(index["external_refs"])
        for ref in index["external_refs"]:
            # Bytes read back and their hash matches the contract reference.
            data = self.store.read_bytes(ref)
            self.assertEqual(digest(json.loads(data.decode())), ref["sha256"])

    def test_records_sorted_latest_version_first(self):
        index = load_fixture_bundle(self.store, FIXTURES / "successful_analysis.json")
        for refs in index["records"].values():
            versions = [r["version"] for r in refs]
            self.assertEqual(versions, sorted(versions, reverse=True))

    def test_all_shipped_fixtures_load(self):
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.name):
                with tempfile.TemporaryDirectory() as tmp:
                    store = open_store(Path(tmp) / "s")
                    index = load_fixture_bundle(store, path)
                    self.assertTrue(index["records"])

    def test_unknown_ref_is_rejected(self):
        load_fixture_bundle(self.store, FIXTURES / "successful_analysis.json")
        bogus = {"artifact_id": "does-not-exist", "version": 1,
                 "sha256": "0" * 64, "provenance": "mock"}
        with self.assertRaises(ArtifactError):
            self.store.read_record(bogus)

    def test_invalid_record_fails_closed(self):
        bundle = json.loads((FIXTURES / "successful_analysis.json").read_text())
        bundle["records"][0] = {"kind": "submission", "not": "a valid record"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(bundle, fh)
            bad_path = fh.name
        try:
            with self.assertRaises(FixtureError):
                load_fixture_bundle(self.store, bad_path)
        finally:
            Path(bad_path).unlink(missing_ok=True)

    def test_tampered_marker_hash_fails_closed(self):
        bundle = json.loads((FIXTURES / "successful_analysis.json").read_text())
        if not bundle.get("mock_artifacts"):
            self.skipTest("fixture has no external artifacts")
        tampered = copy.deepcopy(bundle)
        tampered["mock_artifacts"][0]["content_marker"] += " TAMPERED"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(tampered, fh)
            bad_path = fh.name
        try:
            with self.assertRaises(FixtureError):
                load_fixture_bundle(self.store, bad_path)
        finally:
            Path(bad_path).unlink(missing_ok=True)

    def test_missing_records_key_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"schema_version": "x"}, fh)
            bad_path = fh.name
        try:
            with self.assertRaises(FixtureError):
                load_fixture_bundle(self.store, bad_path)
        finally:
            Path(bad_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
