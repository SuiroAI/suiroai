"""MOCK artifacts only: local storage checks never establish native acceptance.

Exercise immutable writes, measured reads, safe paths, and release staging
to reject corrupted content, conflicting references, and unauthorized files.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from suiroai.contracts import digest, record_ref
from suiroai.integration.artifacts import ArtifactError, ArtifactStore, read_stage_file


ROOT = Path(__file__).resolve().parents[2]


class MockArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dsc26-mock-artifacts-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.store = ArtifactStore(self.directory / "store")

    def test_approved_fixture_record_uses_shared_canonical_digest(self):
        fixture = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
        record = next(r for r in fixture["records"] if r["kind"] == "stage_request")
        self.assertEqual(record["provenance"], "mock")
        ref = self.store.put_record(record)
        self.assertEqual(ref, record_ref(record))
        self.assertEqual(ref["sha256"], digest(record))
        self.assertEqual(self.store.read_record(ref), record)
        self.assertEqual(hashlib.sha256(self.store.read_bytes(ref)).hexdigest(), ref["sha256"])
        # Caller changes cannot change stored content or returned receipts.
        record["attempt"] += 1
        receipt = self.store.get_receipt(ref)
        receipt["ref"]["provenance"] = "supplied"
        self.assertEqual(self.store.get_receipt(ref)["ref"]["provenance"], "mock")
        self.assertNotEqual(self.store.read_record(ref)["attempt"], record["attempt"])

    def test_raw_byte_hash_and_reopened_registry(self):
        data = b"MOCK raw content\n"
        ref = self.store.put_bytes("mock-raw", 2, "mock", data)
        self.assertEqual(ref["sha256"], hashlib.sha256(data).hexdigest())
        reopened = ArtifactStore(self.store.root)
        self.assertEqual(reopened.read_bytes(ref), data)
        self.assertEqual(reopened.get_receipt(ref)["bytes"], len(data))
        with self.assertRaises(ArtifactError):
            reopened.read_record(ref)

    def test_exact_reference_includes_version_provenance_and_digest(self):
        ref = self.store.put_bytes("mock-exact", 1, "mock", b"MOCK")
        for key, value in [("version", 2), ("provenance", "supplied"), ("sha256", "0" * 64)]:
            with self.subTest(key=key):
                changed = dict(ref, **{key: value})
                with self.assertRaises(ArtifactError):
                    self.store.read_bytes(changed)

    def test_same_version_cannot_be_rebound_and_idempotence_is_allowed(self):
        ref = self.store.put_bytes("mock-immutable", 1, "mock", b"MOCK first")
        self.assertEqual(self.store.put_bytes("mock-immutable", 1, "mock", b"MOCK first"), ref)
        with self.assertRaises(ArtifactError):
            self.store.put_bytes("mock-immutable", 1, "mock", b"MOCK changed")
        with self.assertRaises(ArtifactError):
            self.store.put_bytes("mock-immutable", 1, "derived", b"MOCK first")
        self.assertEqual(self.store.read_bytes(ref), b"MOCK first")

    def test_identity_preflight_distinguishes_absence_collision_and_corruption(self):
        prospective = {"artifact_id": "mock-preflight", "version": 1,
                       "sha256": hashlib.sha256(b"MOCK").hexdigest(), "provenance": "mock"}
        self.assertIsNone(self.store.check_identity(prospective))
        self.assertEqual(list((self.store.root / "refs").iterdir()), [])
        exact = self.store.put_bytes("mock-preflight", 1, "mock", b"MOCK")
        self.assertIsNone(self.store.check_identity(exact))
        for conflicting in [dict(exact, sha256="0" * 64), dict(exact, provenance="derived")]:
            with self.subTest(ref=conflicting), self.assertRaises(ArtifactError):
                self.store.check_identity(conflicting)
        blob = self.store.root / "objects" / exact["sha256"]
        blob.chmod(0o600)
        blob.write_bytes(b"FAIL")
        with self.assertRaisesRegex(ArtifactError, "measured artifact"):
            self.store.check_identity(exact)
        # A dangling receipt symlink is an unsafe existing identity, not absent.
        registry = self.store.root / "refs" / self.store._registry_name(exact)
        registry.unlink()
        registry.symlink_to(self.directory / "nonexistent-receipt")
        with self.assertRaises(ArtifactError):
            self.store.check_identity(exact)

    def test_changed_blob_is_detected_even_at_same_size(self):
        ref = self.store.put_bytes("mock-tamper", 1, "mock", b"MOCK one")
        blob = self.store.root / "objects" / ref["sha256"]
        blob.chmod(0o600)
        blob.write_bytes(b"MOCK two")
        with self.assertRaisesRegex(ArtifactError, "measured artifact"):
            self.store.get_receipt(ref)

    def test_modified_record_envelope_cannot_satisfy_reference(self):
        fixture = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
        record = copy.deepcopy(fixture["records"][0])
        ref = self.store.put_record(record)
        # Even a forged byte receipt cannot make changed record versions match.
        record["artifact_version"] += 1
        raw = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        sha = hashlib.sha256(raw).hexdigest()
        (self.store.root / "objects" / sha).write_bytes(raw)
        registry = self.store.root / "refs" / self.store._registry_name(ref)
        registry.chmod(0o600)
        receipt = {"ref": ref, "encoding": "canonical_json", "byte_sha256": sha, "bytes": len(raw)}
        registry.write_text(json.dumps(receipt))
        with self.assertRaises(ArtifactError):
            self.store.read_record(ref)

    def test_only_explicit_release_is_copied_with_exact_provenance(self):
        released = self.store.put_bytes("mock-development", 3, "mock", b"MOCK development only")
        holdout = self.store.put_bytes("mock-unreleased-holdout", 1, "mock", b"MOCK do not expose")
        destination = self.directory / "stage" / "attempt-1"
        manifest = self.store.stage_released([released], destination)
        self.assertEqual(json.loads((destination / "manifest.json").read_text()), manifest)
        self.assertEqual(len(manifest["artifacts"]), 1)
        item = manifest["artifacts"][0]
        self.assertEqual(item["ref"], released)
        self.assertEqual((destination / item["relative_path"]).read_bytes(), b"MOCK development only")
        self.assertNotIn(holdout["sha256"], json.dumps(manifest))
        self.assertNotIn(str(self.store.root), json.dumps(manifest))
        self.assertEqual(len(list((destination / "inputs").iterdir())), 1)
        self.assertFalse(os.stat(destination / item["relative_path"]).st_mode & 0o222)
        with self.assertRaisesRegex(ArtifactError, "already exists"):
            self.store.stage_released([released], destination)

    def test_release_validation_happens_before_namespace_creation(self):
        ref = self.store.put_bytes("mock-released", 1, "mock", b"MOCK")
        destination = self.directory / "bad-stage"
        with self.assertRaises(ArtifactError):
            self.store.stage_released([ref, dict(ref, version=2)], destination)
        self.assertFalse(destination.exists())
        with self.assertRaisesRegex(ArtifactError, "duplicate"):
            self.store.stage_released([ref, ref], destination)
        self.assertFalse(destination.exists())

    def test_byte_and_release_limits(self):
        store = ArtifactStore(self.directory / "limited", max_bytes=5, max_total_bytes=7)
        with self.assertRaisesRegex(ArtifactError, "byte limit"):
            store.put_bytes("mock-large", 1, "mock", b"123456")
        a = store.put_bytes("mock-a", 1, "mock", b"1234")
        b = store.put_bytes("mock-b", 1, "mock", b"5678")
        destination = self.directory / "too-many"
        with self.assertRaisesRegex(ArtifactError, "total byte limit"):
            store.stage_released([a, b], destination)
        self.assertFalse(destination.exists())
        lower_limit = ArtifactStore(self.store.root, max_bytes=2)
        existing = self.store.put_bytes("mock-existing", 1, "mock", b"MOCK")
        with self.assertRaises(ArtifactError):
            lower_limit.read_bytes(existing)

    def test_symlink_root_blob_registry_and_destination_are_rejected(self):
        ref = self.store.put_bytes("mock-link", 1, "mock", b"MOCK")
        link = self.directory / "link"
        link.symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(ArtifactError):
            ArtifactStore(link)
        with self.assertRaises(ArtifactError):
            self.store.stage_released([ref], link / "stage")
        blob = self.store.root / "objects" / ref["sha256"]
        original = self.directory / "original"
        blob.rename(original)
        blob.symlink_to(original)
        with self.assertRaises(ArtifactError):
            self.store.read_bytes(ref)
        blob.unlink()
        original.rename(blob)
        registry = self.store.root / "refs" / self.store._registry_name(ref)
        registry.rename(self.directory / "receipt")
        registry.symlink_to(self.directory / "receipt")
        with self.assertRaises(ArtifactError):
            self.store.read_bytes(ref)

    def test_traversal_nonregular_and_invalid_reference_are_rejected(self):
        with self.assertRaises(ArtifactError):
            ArtifactStore(self.directory / "other" / ".." / "escape")
        with self.assertRaises(ArtifactError):
            self.store.stage_released([], self.directory / "other" / ".." / "stage")
        ref = self.store.put_bytes("../../mock-id-is-not-a-path", 1, "mock", b"MOCK")
        self.assertEqual(self.store.read_bytes(ref), b"MOCK")
        blob = self.store.root / "objects" / ref["sha256"]
        blob.unlink()
        os.mkfifo(blob)
        with self.assertRaises(ArtifactError):
            self.store.read_bytes(ref)
        for bad in [{}, dict(ref, version=True), dict(ref, provenance=[]),
                    dict(ref, sha256="../escape"), dict(ref, extra=1)]:
            with self.subTest(ref=bad), self.assertRaises(ArtifactError):
                self.store.read_bytes(bad)

    def test_output_read_is_bounded_and_refuses_symlink_and_traversal(self):
        stage = self.directory / "output-stage"
        (stage / "nested").mkdir(parents=True)
        (stage / "nested/result.json").write_bytes(b'{"MOCK":true}')
        self.assertEqual(read_stage_file(stage, "nested/result.json"), b'{"MOCK":true}')
        (stage / "link").symlink_to(stage / "nested", target_is_directory=True)
        (stage / "result-link").symlink_to(stage / "nested/result.json")
        for path in ["link/result.json", "result-link", "../output-stage/nested/result.json",
                     str(stage / "nested/result.json"), "."]:
            with self.subTest(path=path), self.assertRaises(ArtifactError):
                read_stage_file(stage, path)
        with self.assertRaises(ArtifactError):
            read_stage_file(stage, "nested/result.json", max_bytes=3)
        with self.assertRaises(ArtifactError):
            self.store.stage_released([], "/")

    def test_release_metadata_count_is_bounded_even_for_empty_artifacts(self):
        refs = [self.store.put_bytes("mock-empty-" + str(i), 1, "mock", b"")
                for i in range(257)]
        with self.assertRaisesRegex(ArtifactError, "count exceeds"):
            self.store.stage_released(refs, self.directory / "too-many-empty-files")


if __name__ == "__main__":
    unittest.main()
