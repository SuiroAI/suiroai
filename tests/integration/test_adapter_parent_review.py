"""MOCK parent-boundary regressions; no native or analytical acceptance.

All approvals, measurements and decisions below are the contract owner's
invented component fixtures. A completed mock host is never real Data evidence.
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

from suiroai.contracts import record_ref, validate_handoff, validate_record
from suiroai.integration.adapter import StageAdapter
from suiroai.integration.artifacts import ArtifactError, ArtifactStore, _json_bytes


ROOT = Path(__file__).resolve().parents[2]


def accept_exact(candidate, artifact_bytes):
    """MOCK trusted parent adoption, not a production parent implementation."""
    return {
        "candidate_sha256": candidate["candidate_sha256"],
        "stage_request_ref": deepcopy(candidate["stage_request_ref"]),
        "adopted_checkpoint_decisions": deepcopy(candidate["checkpoint_decision_claims"]),
        "verified_prior_authorizations": deepcopy(candidate["prior_authorization_claims"]),
    }


class MockPacketHost:
    """Writes an invented result packet locally; never starts Codex/Data."""

    def __init__(self, record, result, mutate=None):
        self.record, self.result = deepcopy(record), deepcopy(result)
        self.mutate = mutate
        self.calls = []

    def write(self, directory):
        record = deepcopy(self.record)
        if self.mutate:
            self.mutate(record)
        (directory / "candidate.json").write_text(json.dumps(record))
        (directory / "artifact-manifest.json").write_text(json.dumps([
            {"ref": record_ref(self.record), "path": "candidate.json", "encoding": "record"}
        ]))
        (directory / "stage-result.json").write_text(json.dumps(self.result))

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        self.write(kwargs["cwd"])
        return SimpleNamespace(outcome="completed", error_code=None,
            message="MOCK packet only; no model or analytical execution",
            evidence={"evidence_mode": "mock", "no_native_invocation": True},
            thread_id=None, turn_id=None, mode="customer")


class ParentReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dsc26-mock-parent-review-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixture = json.loads((ROOT / "examples/contracts/v0.1.0/successful_analysis.json").read_text())
        self.approved = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
        self.assertEqual(self.fixture["fixture_provenance"], "mock")
        self.sequence = 0

    def packet(self, kind="preparation_result", review=accept_exact, *, recheck=False, mutate=None,
               failed_validation=False, prior_actor="MOCK-FORGED-PARENT"):
        self.sequence += 1
        home = self.root / str(self.sequence)
        home.mkdir()
        store = ArtifactStore(home / "store")
        fixture = self.fixture if not failed_validation else json.loads(
            (ROOT / "examples/contracts/v0.1.0/validation_failed.json").read_text())
        records = []
        for record in fixture["records"]:
            if record["kind"] == kind:
                target = deepcopy(record)
                break
            records.append(deepcopy(record))
        stages = {"preparation_result": "preparation", "initial_evaluation_result": "initial_baseline_evaluation",
            "feature_result": "llm_features", "evaluation_result": "comparison_and_freeze",
            "final_validation_result": "final_validation", "report_draft": "recommendations"}
        request = deepcopy(next(r for r in self.approved["records"] if r["kind"] == "stage_request"))
        now = datetime.now(timezone.utc)
        request.update(stage=stages[kind], issued_at=now.isoformat(),
            deadline=(now + timedelta(seconds=120)).isoformat(), released_input_refs=[])
        request["parent_authorization"]["checkpoint"] = request["stage"]
        request["execution_contract_ref"] = record_ref(next(r for r in records if r["kind"] == "execution_contract"))
        if recheck:
            prior = deepcopy(target["parent_review"])
            prior.update(decision="allow_defect_recheck", actor=prior_actor,
                decided_at=(now - timedelta(seconds=1)).isoformat())
            target["parent_review"] = None
            target["defect_rechecks"] = [{"attempt": 1, "defect_description": "MOCK permission fixture only",
                "defect_evidence_refs": prior["evidence_refs"], "correction_refs": prior["evidence_refs"],
                "parent_authorization": prior, "model_selection_unchanged": True,
                "november_30_forecast_ref": target["november_30_forecast_ref"],
                "scores": deepcopy(target["scores"]), "checks": deepcopy(target["checks"]), "outcome": "pass"}]
        records.append(request)
        external_refs = []
        for artifact in fixture["mock_artifacts"]:
            ref = artifact["ref"]
            actual = store.put_bytes(ref["artifact_id"], ref["version"], "mock", _json_bytes(artifact["content_marker"]))
            self.assertEqual(actual, ref)
            external_refs.append(ref)
        handoff = [store.put_record(record) for record in records]
        result = StageAdapter._result(request, record_ref(request), "mock")
        result.update(outcome="completed", failure=None, output_refs=[record_ref(target)], evidence_refs=[external_refs[0]])
        if failed_validation:
            result.update(outcome="validation_failed", final_validation_result_ref=record_ref(target))
        self.assertEqual(validate_record(target), [])
        self.assertEqual(validate_handoff(records + [target, result], external_refs), [])
        host = MockPacketHost(target, result, mutate)
        adapter = StageAdapter(store, work_root=home / "attempts", parent_permits=lambda _: True,
            host=host, allow_mock_handoffs=True, parent_review=review)
        return SimpleNamespace(home=home, store=store, records=records, request=request, target=target,
            result=result, external_refs=external_refs, handoff=handoff, host=host, adapter=adapter)

    def execute(self, packet, **kwargs):
        return packet.adapter.execute(record_ref(packet.request), handoff_refs=packet.handoff,
            external_refs=packet.external_refs, **kwargs)

    def assert_unpublished(self, packet):
        with self.assertRaises(ArtifactError):
            packet.store.read_record(record_ref(packet.target))

    def assert_rejected(self, packet, **kwargs):
        result = self.execute(packet, **kwargs)
        self.assertEqual(result["outcome"], "execution_failed")
        self.assertEqual(result["failure"]["error_code"], "integrity_error")
        self.assertEqual(result["output_refs"], [])
        self.assert_unpublished(packet)
        return result

    def test_schema_valid_preparation_success_roundtrips_through_full_execute(self):
        observed = []
        def review(candidate, blobs):
            self.assertIsInstance(blobs, tuple)
            self.assertEqual(len(blobs), 1)
            self.assertEqual(json.loads(blobs[0]), candidate["records"][0])
            self.assertEqual(candidate["artifacts"][0]["byte_sha256"], hashlib.sha256(blobs[0]).hexdigest())
            self.assertEqual(candidate["checkpoint_decision_claims"][0]["json_pointer"], "/parent_decision")
            unsigned = deepcopy(candidate)
            digest = unsigned.pop("candidate_sha256")
            self.assertEqual(hashlib.sha256(_json_bytes(unsigned)).hexdigest(), digest)
            observed.append(deepcopy(candidate))
            return accept_exact(candidate, blobs)
        packet = self.packet(review=review)
        result = self.execute(packet)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(result["provenance"], "mock")
        self.assertIsNone(result["parent_decision"])
        self.assertEqual(len(packet.host.calls), 1)
        self.assertEqual(packet.store.read_record(record_ref(packet.target)), packet.target)
        self.assertEqual(validate_handoff(packet.records + [packet.target, result],
            packet.external_refs + result["evidence_refs"]), [])
        audit = json.loads(packet.store.read_bytes(result["evidence_refs"][-1]))
        self.assertTrue(audit["parent_candidate_review"]["accepted"])
        self.assertEqual(audit["parent_candidate_review"]["receipt"], accept_exact(observed[0], ()))
        self.assertFalse(audit["customer_model_turn_requested"])

    def test_other_required_parent_decision_record_kinds_can_be_accepted(self):
        for kind in ("initial_evaluation_result", "feature_result", "evaluation_result", "report_draft"):
            with self.subTest(kind=kind):
                packet = self.packet(kind)
                result = self.execute(packet)
                self.assertEqual(result["outcome"], "completed", result.get("failure"))
                self.assertEqual(packet.store.read_record(record_ref(packet.target)), packet.target)

    def test_required_parent_decision_without_callback_fails_closed(self):
        self.assert_rejected(self.packet(review=None))

    def test_measured_final_failure_requires_parent_review_and_preserves_scores(self):
        claims = []
        def review(candidate, blobs):
            claims.extend(candidate["checkpoint_decision_claims"])
            return accept_exact(candidate, blobs)
        packet = self.packet("final_validation_result", review=review, failed_validation=True)
        result = self.execute(packet)
        self.assertEqual(result["outcome"], "validation_failed")
        self.assertIsNone(result["failure"])
        self.assertEqual(result["final_validation_result_ref"], record_ref(packet.target))
        self.assertEqual(packet.store.read_record(record_ref(packet.target))["scores"], packet.target["scores"])
        self.assertEqual([claim["json_pointer"] for claim in claims], ["/parent_review"])

    def test_receipt_must_match_every_field_and_claim(self):
        def malformed(case):
            def review(candidate, blobs):
                receipt = accept_exact(candidate, blobs)
                if case == "bool": return True
                if case == "missing": del receipt["verified_prior_authorizations"]
                if case == "wrong_digest": receipt["candidate_sha256"] = "0" * 64
                if case == "wrong_request": receipt["stage_request_ref"]["sha256"] = "0" * 64
                if case == "wrong_type": receipt["stage_request_ref"]["version"] = True
                if case == "missing_claim": receipt["adopted_checkpoint_decisions"] = []
                if case == "extra_claim": receipt["adopted_checkpoint_decisions"] *= 2
                if case == "wrong_decision": receipt["adopted_checkpoint_decisions"][0]["decision_sha256"] = "0" * 64
                if case == "extra_field": receipt["accepted"] = True
                return receipt
            return review
        for case in ("bool", "missing", "wrong_digest", "wrong_request", "wrong_type", "missing_claim", "extra_claim", "wrong_decision", "extra_field"):
            with self.subTest(case=case): self.assert_rejected(self.packet(review=malformed(case)))

    def test_nested_recheck_claim_is_rejected_without_prior_ledger_authentication(self):
        self.assert_rejected(self.packet("final_validation_result", review=None, recheck=True))
        seen = []
        def refuse_forgery(candidate, blobs):
            seen.extend(candidate["prior_authorization_claims"])
            receipt = accept_exact(candidate, blobs)
            receipt["verified_prior_authorizations"] = []
            return receipt
        packet = self.packet("final_validation_result", review=refuse_forgery, recheck=True)
        self.assert_rejected(packet)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["json_pointer"], "/defect_rechecks/0/parent_authorization")

    def test_prior_authorization_can_be_verified_against_explicit_mock_ledger(self):
        ledger = {}
        def context(request, final):
            return _json_bytes({"request_ref": record_ref(request), "binding": request["binding"],
                "run_id": request["run_id"], "stage": request["stage"], "attempt": request["attempt"],
                "frozen_result_ref": final["frozen_result_ref"],
                "forecast_ref": final["november_30_forecast_ref"]})
        def review(candidate, blobs):
            for claim in candidate["prior_authorization_claims"]:
                expected_hash = ledger[context(candidate["stage_request"], candidate["records"][0])]
                self.assertEqual(claim["decision_sha256"], expected_hash)
            return accept_exact(candidate, blobs)
        packet = self.packet("final_validation_result", review=review, recheck=True,
            prior_actor="MOCK-TRUSTED-PRIOR-PARENT")
        decision = packet.target["defect_rechecks"][0]["parent_authorization"]
        # This mock ledger entry exists before the mock host executes. The
        # future result's identity is deliberately not its authorization scope.
        ledger[context(packet.request, packet.target)] = hashlib.sha256(_json_bytes(decision)).hexdigest()
        self.assertEqual(self.execute(packet)["outcome"], "completed")

    def test_post_request_recheck_authorization_never_reaches_parent_callback(self):
        calls = []
        packet = self.packet("final_validation_result", review=lambda *args: calls.append(args), recheck=True)
        packet.target["defect_rechecks"][0]["parent_authorization"]["decided_at"] = (
            datetime.fromisoformat(packet.request["issued_at"]) + timedelta(seconds=1)).isoformat()
        packet.host.record = deepcopy(packet.target)
        packet.host.result["output_refs"] = [record_ref(packet.target)]
        self.assert_rejected(packet)
        self.assertEqual(calls, [])

    def test_parent_callback_exception_is_typed_failure_without_publishing(self):
        def review(*args): raise RuntimeError("MOCK parent unavailable")
        result = self.assert_rejected(self.packet(review=review))
        self.assertIn("trusted parent candidate review failed", result["failure"]["reason"])

    def test_callback_mutation_cannot_change_measured_records_or_bindings(self):
        def review(candidate, blobs):
            receipt = accept_exact(candidate, blobs)
            candidate["records"][0]["binding"]["task_version"] = 999
            candidate["records"][0]["parent_decision"]["decision"] = "stop"
            candidate["stage_result"]["output_refs"].clear()
            candidate["stage_request"]["binding"]["input_version"] = 999
            return receipt
        packet = self.packet(review=review)
        result = self.execute(packet)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(packet.store.read_record(record_ref(packet.target)), packet.target)
        self.assertEqual(result["binding"], packet.request["binding"])

    def test_same_request_and_identical_outputs_cannot_replay_parent_receipt(self):
        receipts = []
        def review(candidate, blobs):
            if not receipts: receipts.append(accept_exact(candidate, blobs))
            return deepcopy(receipts[0])
        packet = self.packet(review=review)
        # Stop the first candidate after obtaining its receipt, so neither
        # attempt can rely on an already published target artifact.
        def first_review(candidate, blobs):
            review(candidate, blobs)
            return False
        packet.adapter.parent_review = first_review
        self.assert_rejected(packet)
        packet.adapter.parent_review = review
        result = self.assert_rejected(packet)
        self.assertIn("exact candidate", result["failure"]["reason"])

    def test_invalid_schema_hash_or_binding_is_rejected_before_parent_review(self):
        for case in ("schema", "hash", "binding"):
            calls = []
            packet = self.packet(review=lambda *args: calls.append(args))
            if case == "schema":
                packet.host.record["parent_decision"] = None
            elif case == "hash":
                packet.host.mutate = lambda record: record["findings"].clear()
            else:
                packet.host.record["binding"]["task_version"] = 99
            packet.host.result["output_refs"] = [record_ref(packet.host.record)]
            with self.subTest(case=case):
                self.assert_rejected(packet)
                self.assertEqual(calls, [])

    def test_cancellation_after_callback_prevents_output_publication(self):
        cancelled = threading.Event()
        def review(candidate, blobs):
            cancelled.set()
            return accept_exact(candidate, blobs)
        packet = self.packet(review=review)
        result = self.execute(packet, cancellation=cancelled)
        self.assertEqual(result["failure"]["error_code"], "cancelled")
        self.assert_unpublished(packet)

    def test_deadline_after_callback_prevents_output_publication(self):
        packet = self.packet()
        directory = packet.home / "direct-output"
        directory.mkdir()
        packet.host.write(directory)
        checks = []
        def stop_reason():
            checks.append(True)
            return ("timeout", "MOCK deadline expired after parent review") if len(checks) >= 2 else None
        result = packet.adapter._retrieve(packet.request, record_ref(packet.request), "mock", directory,
            packet.records, packet.external_refs, {"published_refs": []},
            lambda code, reason: {"failure": {"error_code": code}}, stop_reason)
        self.assertEqual(result["failure"]["error_code"], "timeout")
        self.assert_unpublished(packet)


if __name__ == "__main__":
    unittest.main()
