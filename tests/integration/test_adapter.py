"""Explicit MOCK adapter checks; no model, customer run or native acceptance.

The approved_execution packet is an invented shared-contract fixture. Hosts in
these tests return failures only; no mocked analytical success is supplied.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from suiroai.contracts import record_ref, validate_handoff, validate_record
from suiroai.integration.adapter import AdapterRejected, StageAdapter
from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.integration.native import NativeHost


ROOT = Path(__file__).resolve().parents[2]


class MockFailureHost:
    """Capture one attempted mock dispatch and return an explicit failure."""

    def __init__(self, code="runtime_error"):
        self.code = code
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            outcome="execution_failed", error_code=self.code,
            message="MOCK host failure; no native process or analysis ran",
            evidence={"evidence_mode": "mock", "no_native_invocation": True},
            thread_id=None, turn_id=None, mode="customer",
        )


def replace_reference(value, old, new):
    if isinstance(value, dict):
        if value == old:
            return deepcopy(new)
        return {key: replace_reference(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_reference(item, old, new) for item in value]
    return value


class MockStageAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dsc26-mock-adapter-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ArtifactStore(self.root / "store")
        fixture = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
        self.assertEqual(fixture["fixture_provenance"], "mock")
        self.records = [deepcopy(r) for r in fixture["records"] if r["kind"] != "stage_result"]
        self.original_refs = [record_ref(r) for r in self.records]
        now = datetime.now(timezone.utc)
        self.request["issued_at"] = now.isoformat()
        self.request["deadline"] = (now + timedelta(seconds=120)).isoformat()
        self.external_refs = []
        for artifact in fixture["mock_artifacts"]:
            ref = artifact["ref"]
            data = json.dumps(artifact["content_marker"], sort_keys=True,
                              ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
            actual = self.store.put_bytes(ref["artifact_id"], ref["version"], "mock", data)
            self.assertEqual(actual, ref)
            self.external_refs.append(actual)
        self.host = MockFailureHost()

    @property
    def request(self):
        return next(r for r in self.records if r["kind"] == "stage_request")

    def record(self, kind):
        return next(r for r in self.records if r["kind"] == kind)

    def seal(self):
        # Recompute references after intentional fixture mutations so rejection
        # tests reach semantic binding/approval checks, not incidental stale refs.
        for index, old in enumerate(self.original_refs):
            if record_ref(self.records[index]) != old:
                # Each mutated mock packet is a new immutable artifact revision.
                # Existing versions in this real local store must stay intact.
                self.records[index]["artifact_version"] += 1
            new = record_ref(self.records[index])
            self.records = [replace_reference(r, old, new) for r in self.records]
        self.original_refs = [record_ref(r) for r in self.records]
        handoff = [self.store.put_record(r) for r in self.records]
        return record_ref(self.request), handoff

    def adapter(self, *, permits=None, allow_mock=True, host=None):
        return StageAdapter(self.store, work_root=self.root / "attempts",
                            parent_permits=permits or (lambda ref: True),
                            host=host or self.host, ceiling_seconds=30,
                            allow_mock_handoffs=allow_mock)

    def execute(self, **kwargs):
        request_ref, handoff = self.seal()
        return self.adapter().execute(request_ref, handoff_refs=handoff,
                                      external_refs=self.external_refs, **kwargs)

    def assert_failure(self, result, code):
        self.assertEqual(validate_record(result), [])
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(result["failure"]["error_code"], code)
        self.assertEqual(result["provenance"], "mock")
        self.assertIsNone(result["parent_decision"])
        self.assertEqual(result["output_refs"], [])
        self.assertEqual(result["gaps"], [])
        self.assertIsNone(result["final_validation_result_ref"])
        self.assertTrue(result["evidence_refs"])
        self.assertEqual(result["evidence_refs"], result["failure"]["evidence_refs"])
        self.assertEqual(self.store.read_record(record_ref(result)), result)
        for ref in result["evidence_refs"]:
            self.assertEqual(ref["provenance"], "mock")
            audit = json.loads(self.store.read_bytes(ref))
            self.assertTrue(audit["mock_handoff"])
            self.assertFalse(audit["customer_model_turn_requested"])
            self.assertFalse(audit["stage_outputs_accepted"])
            self.assertFalse(audit["working_directory_released"])
            self.assertEqual(audit["published_refs"], [])

    def test_failure_preserves_exact_task_input_proposal_run_sources_and_request(self):
        result = self.execute()
        self.assert_failure(result, "runtime_error")
        request_ref = record_ref(self.request)
        self.assertEqual(result["stage_request_ref"], request_ref)
        self.assertEqual(result["execution_contract_ref"], record_ref(self.record("execution_contract")))
        self.assertEqual(result["binding"], self.request["binding"])
        self.assertEqual(result["run_id"], self.request["run_id"])
        self.assertEqual((result["stage"], result["attempt"]),
                         (self.request["stage"], self.request["attempt"]))
        self.assertEqual(validate_handoff(self.records + [result], self.external_refs + result["evidence_refs"]), [])
        self.assertEqual(len(self.host.calls), 1)
        call = self.host.calls[0]
        self.assertEqual(call["mode"], "customer")
        self.assertGreater(call["timeout_seconds"], 0)
        self.assertLessEqual(call["timeout_seconds"], 30)
        payload = json.loads(call["prompt"].split("\n", 1)[1])
        self.assertEqual(payload["goal"], self.record("task_proposal")["goal"])
        self.assertEqual(payload["output"], self.record("task_proposal")["output"])
        self.assertEqual(payload["binding"], self.request["binding"])
        self.assertEqual(payload["stage_request"], self.request)
        self.assertEqual([a["ref"] for a in payload["released_files"]["artifacts"]],
                         self.request["released_input_refs"])
        self.assertEqual(payload["material_assumptions"], self.record("execution_contract")["source_assumptions"])

    def test_parent_must_authorize_exact_reference_and_return_literal_true(self):
        request_ref, handoff = self.seal()
        observed = []
        def rejected(ref):
            observed.append(ref)
            ref["sha256"] = "0" * 64
            return False
        with self.assertRaisesRegex(AdapterRejected, "DSC-10"):
            self.adapter(permits=rejected).execute(request_ref, handoff_refs=handoff,
                                                   external_refs=self.external_refs)
        self.assertEqual(len(observed), 1)
        self.assertNotEqual(observed[0], request_ref)
        self.assertEqual(request_ref, record_ref(self.request))
        with self.assertRaisesRegex(AdapterRejected, "DSC-10"):
            self.adapter(permits=lambda ref: 1).execute(request_ref, handoff_refs=handoff,
                                                       external_refs=self.external_refs)
        self.assertFalse(self.host.calls)

    def test_unapproved_current_proposal_cannot_dispatch(self):
        self.record("task_approval")["decision"] = "pending"
        with self.assertRaisesRegex(AdapterRejected, "explicit approved"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_changed_task_input_proposal_and_run_bindings_cannot_dispatch(self):
        for field, value in [("task_id", "mock-different-task"), ("task_version", 2),
                             ("input_version", 2), ("input_digest", "0" * 64),
                             ("proposal_version", 2), ("proposal_digest", "0" * 64)]:
            with self.subTest(field=field):
                previous = self.request["binding"][field]
                self.request["binding"][field] = value
                with self.assertRaisesRegex(AdapterRejected, "binding mismatch"):
                    self.execute()
                self.request["binding"][field] = previous
        self.request["run_id"] = "mock-different-run"
        with self.assertRaisesRegex(AdapterRejected, "run binding mismatch"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_changed_source_and_assumption_contract_cannot_redefine_approved_task(self):
        execution = self.record("execution_contract")
        execution["source_refs"] = execution["source_refs"][:-1]
        with self.assertRaisesRegex(AdapterRejected, "changed approved source_refs"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_changed_material_assumption_cannot_redefine_approved_task(self):
        self.record("execution_contract")["source_assumptions"][0]["statement"] += " MOCK changed fact"
        with self.assertRaisesRegex(AdapterRejected, "changed approved assumptions"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_changed_approval_reference_hash_is_rejected_before_host(self):
        self.record("execution_contract")["approval_ref"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(AdapterRejected, "unresolved"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_external_source_bytes_are_measured_not_trusted_from_reference(self):
        ref = self.external_refs[0]
        blob = self.store.root / "objects" / ref["sha256"]
        data = blob.read_bytes()
        blob.chmod(0o600)
        blob.write_bytes(b"X" + data[1:])
        with self.assertRaisesRegex(ArtifactError, "measured artifact bytes"):
            self.execute()
        self.assertFalse(self.host.calls)

    def test_mock_handoff_never_authorizes_default_real_dispatch(self):
        request_ref, handoff = self.seal()
        with self.assertRaisesRegex(AdapterRejected, "mock handoff"):
            self.adapter(allow_mock=False).execute(request_ref, handoff_refs=handoff,
                                                  external_refs=self.external_refs)
        self.assertFalse(self.host.calls)

    def test_zero_time_and_attempt_limits_return_exhaustion_without_dispatch(self):
        for limit in ("max_execution_seconds", "max_stage_attempts"):
            with self.subTest(limit=limit):
                previous = self.request["remaining_limits"][limit]
                self.request["remaining_limits"][limit] = 0
                self.assert_failure(self.execute(), "budget_exhausted")
                self.request["remaining_limits"][limit] = previous
        self.assertFalse(self.host.calls)

    def test_irrelevant_zero_candidate_and_feature_limits_do_not_block_other_stage(self):
        self.request["remaining_limits"]["max_candidates"] = 0
        self.request["remaining_limits"]["max_llm_feature_definitions"] = 0
        self.request["remaining_limits"]["max_parent_reviews"] = 0
        result = self.execute()
        self.assert_failure(result, "runtime_error")
        self.assertEqual(len(self.host.calls), 1)

    def test_zero_required_model_and_feature_budgets_do_not_dispatch(self):
        for stage, limit in [("initial_baseline_evaluation", "max_candidates"),
                             ("llm_features", "max_llm_feature_definitions")]:
            with self.subTest(stage=stage):
                self.request["stage"] = stage
                self.request["parent_authorization"]["checkpoint"] = stage
                # No development bytes are exposed by this exhausted mock call.
                self.request["released_input_refs"] = []
                self.request["remaining_limits"][limit] = 0
                self.assert_failure(self.execute(), "budget_exhausted")
        self.assertFalse(self.host.calls)

    def test_expired_deadline_and_precancelled_request_never_dispatch(self):
        cancellation = threading.Event()
        cancellation.set()
        self.assert_failure(self.execute(cancellation=cancellation), "cancelled")
        now = datetime.now(timezone.utc)
        self.request["issued_at"] = (now - timedelta(seconds=60)).isoformat()
        self.request["deadline"] = (now - timedelta(seconds=30)).isoformat()
        self.assert_failure(self.execute(), "timeout")
        self.assertFalse(self.host.calls)

    def test_native_failure_codes_remain_execution_failures_without_scores_or_gaps(self):
        for code in ("plugin_unavailable", "unsupported_integration", "invalid_code",
                     "timeout", "cancelled", "budget_exhausted", "integrity_error"):
            with self.subTest(code=code):
                self.host.code = code
                self.assert_failure(self.execute(), code)

    def test_customer_read_isolation_gate_fails_closed_without_native_process(self):
        request_ref, handoff = self.seal()
        with patch("subprocess.Popen") as spawn:
            result = self.adapter(host=NativeHost()).execute(
                request_ref, handoff_refs=handoff, external_refs=self.external_refs)
        spawn.assert_not_called()
        self.assert_failure(result, "unsupported_integration")
        self.assertIn("isolation", result["failure"]["reason"].lower())

    def mock_worker_packet(self, *, outcome="needs_inputs", blobs=None):
        """Make a mocked non-success receiver packet, never a native run."""
        request_ref, _ = self.seal()
        directory = Path(tempfile.mkdtemp(prefix="mock-worker-packet-", dir=self.root))
        blobs = blobs or [("mock-diagnostic", b"MOCK diagnostic; no analytical output")]
        entries, refs = [], []
        for index, (identity, data) in enumerate(blobs):
            path = f"diagnostic-{index}.txt"
            (directory / path).write_bytes(data)
            ref = {"artifact_id": identity, "version": 1, "provenance": "mock",
                   "sha256": hashlib.sha256(data).hexdigest()}
            refs.append(ref)
            entries.append({"ref": ref, "path": path, "encoding": "bytes"})
        adapter = self.adapter()
        result = adapter._result(self.request, request_ref, "mock")
        result.update(outcome=outcome, evidence_refs=refs)
        if outcome in {"needs_inputs", "needs_material_facts"}:
            result["gaps"] = [{"gap_id": "mock-gap", "material": True,
                               "description": "MOCK missing source or business fact",
                               "blocks": ["quantities"],
                               "request_to_user": "MOCK provide the specifically missing fact"}]
        (directory / "artifact-manifest.json").write_text(json.dumps(entries))
        self.write_worker_result(directory, result)
        return adapter, request_ref, directory, result, refs

    @staticmethod
    def write_worker_result(directory, result):
        (directory / "stage-result.json").write_text(json.dumps(result))

    def retrieve_mock_packet(self, packet):
        adapter, request_ref, directory, _, _ = packet
        def unexpected_failure(*args):
            raise AssertionError("Direct mocked receiver must not dispatch a failure host")
        return adapter._retrieve(self.request, request_ref, "mock", directory,
                                 self.records, self.external_refs,
                                 {"evidence_mode": "mock", "no_native_invocation": True,
                                  "published_refs": [], "stage_outputs_accepted": False},
                                 unexpected_failure)

    def test_missing_inputs_and_material_facts_remain_nonexecution_outcomes(self):
        for outcome in ("needs_inputs", "needs_material_facts"):
            with self.subTest(outcome=outcome):
                packet = self.mock_worker_packet(outcome=outcome)
                result = self.retrieve_mock_packet(packet)
                self.assertEqual(result["outcome"], outcome)
                self.assertIsNone(result["failure"])
                self.assertIsNone(result["parent_decision"])
                self.assertEqual(result["gaps"], packet[3]["gaps"])
                self.assertEqual(result["output_refs"], [])
                self.assertEqual(result["provenance"], "mock")
        self.assertFalse(self.host.calls)

    def test_worker_output_binding_tampering_never_publishes_pending_artifact(self):
        mutations = {
            "binding": dict(self.request["binding"], task_version=999),
            "run_id": "mock-wrong-run", "stage": "recommendations", "attempt": 999,
            "execution_contract_ref": dict(self.request["execution_contract_ref"], sha256="0" * 64),
            "stage_request_ref": {"artifact_id": "mock-other-request", "version": 1,
                                  "sha256": "0" * 64, "provenance": "mock"},
            "parent_decision": {"decision": "proceed"}, "provenance": "derived",
        }
        for field, changed in mutations.items():
            with self.subTest(field=field):
                packet = self.mock_worker_packet()
                packet[3][field] = changed
                self.write_worker_result(packet[2], packet[3])
                with self.assertRaisesRegex(ValueError, "worker stage result changed " + field):
                    self.retrieve_mock_packet(packet)
                with self.assertRaises(ArtifactError):
                    self.store.read_bytes(packet[4][0])
        self.assertFalse(self.host.calls)

    def test_measured_failure_requires_actual_failed_validation_reference(self):
        packet = self.mock_worker_packet(outcome="validation_failed")
        with self.assertRaises(ValueError):
            self.retrieve_mock_packet(packet)
        with self.assertRaises(ArtifactError):
            self.store.read_bytes(packet[4][0])
        self.assertFalse(self.host.calls)

    def test_second_output_identity_collision_cannot_publish_first_pending_artifact(self):
        self.store.put_bytes("mock-conflicting-output", 1, "mock", b"MOCK existing immutable version")
        packet = self.mock_worker_packet(blobs=[
            ("mock-pending-before-collision", b"MOCK must stay quarantined"),
            ("mock-conflicting-output", b"MOCK changed bytes at same version"),
        ])
        with self.assertRaises(ValueError):
            self.retrieve_mock_packet(packet)
        with self.assertRaises(ArtifactError):
            self.store.read_bytes(packet[4][0])
        self.assertFalse(self.host.calls)


if __name__ == "__main__":
    unittest.main()
