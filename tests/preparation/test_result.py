"""MOCK result/adapter roundtrip; no native Data run or real acceptance.

Exercise measured result serialization and artifact retrieval through the
real adapter with a mock host and exact trusted parent review.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from mock_data import ROOT, artifact, packet, sale
from suiroai.contracts import record_ref, validate_handoff, validate_record
from suiroai.contracts.validation import input_digest, proposal_digest
from suiroai.integration.adapter import AdapterRejected, StageAdapter
from suiroai.integration.artifacts import ArtifactError, ArtifactStore
from suiroai.preparation.result import build_result
from suiroai.preparation.worker import PreparationError, SALES, csv_bytes, encoded, prepare_development


def mock_adopt_exact(candidate, blobs):
    """Explicit MOCK checkpoint adoption; not a production authorization."""
    return dict(candidate_sha256=candidate["candidate_sha256"],
                stage_request_ref=deepcopy(candidate["stage_request_ref"]),
                adopted_checkpoint_decisions=deepcopy(candidate["checkpoint_decision_claims"]),
                verified_prior_authorizations=deepcopy(candidate["prior_authorization_claims"]))


class MockPreparationHost:
    """Publish locally generated mock result bytes without native invocation."""
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        root = kwargs["cwd"]
        for entry in self.result["artifacts"]:
            (root / entry["path"]).write_bytes(entry["data"])
        (root / "artifact-manifest.json").write_bytes(encoded(self.result["artifact_manifest"]))
        (root / "stage-result.json").write_bytes(encoded(self.result["stage_result"]))
        return SimpleNamespace(outcome="completed", error_code=None,
            message="MOCK generated CSV preparation result only; no native Data invocation",
            evidence={"evidence_mode": "mock", "no_native_invocation": True},
            thread_id=None, turn_id=None, mode="customer")


def bound_packet(*, mock_approved_partition=False):
    """Rebind every approved fixture edge to actual generated MOCK file bytes."""
    rows = [sale(1), sale(2, Quantity="0", Order_Date="2025-11-03"),
            sale(3, Quantity="999", Order_Date="2025-12-02")]
    args, partition = packet(rows)
    prepared = prepare_development(**args)
    raw_data = csv_bytes(list(SALES), rows)
    source_items = [{"ref": partition["development_receipt"]["raw_ref"], "data": raw_data}]
    source_items += [args["sources"][role] for role in ("dictionary", "inventory", "receipts", "policy")]
    if mock_approved_partition:
        # Artificial approval fixture for serialization/retrieval ONLY. The
        # real input manifest supplies raw sales, not this sixth approved file.
        # This does not establish a supported production partition-release path.
        source_items.append(args["sources"]["sales"])
    source_refs = [item["ref"] for item in source_items]
    fixture = json.loads((ROOT / "examples/contracts/v0.1.0/approved_execution.json").read_text())
    records = [deepcopy(r) for r in fixture["records"] if r["kind"] != "stage_result"]
    submission, proposal, approval, execution, request = records
    if mock_approved_partition:
        extra_file = deepcopy(submission["files"][0])
        extra_file.update(source_role="other", original_name="MOCK-approved-development-partition.csv",
                          supplied_location="mock://artificial-approved-partition/ONLY")
        submission["files"].append(extra_file)
    for file, item in zip(submission["files"], source_items):
        file.update(file_id=item["ref"]["artifact_id"], sha256=item["ref"]["sha256"], size_bytes=len(item["data"]))
    submission["binding"]["input_digest"] = input_digest(submission)
    binding = {k: v for k, v in submission["binding"].items()}
    proposal.update(submission_ref=record_ref(submission), source_refs=deepcopy(source_refs),
                    target_policy=deepcopy(execution["target_policy"]))
    proposal["target_policy"] = deepcopy(args["execution"]["target_policy"])
    proposal["assumptions"][0]["source_refs"] = deepcopy(source_refs)
    proposal["binding"].update(binding)
    proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
    binding = deepcopy(proposal["binding"])
    approval.update(binding=deepcopy(binding), proposal_ref=record_ref(proposal))
    execution.update(binding=deepcopy(binding), proposal_ref=record_ref(proposal), approval_ref=record_ref(approval),
        source_refs=deepcopy(source_refs), synthetic_operational_source_refs=deepcopy(source_refs[2:5]),
        target_policy=deepcopy(proposal["target_policy"]), source_assumptions=deepcopy(proposal["assumptions"]))
    now = datetime.now(timezone.utc)
    request.update(binding=deepcopy(binding), execution_contract_ref=record_ref(execution), stage="preparation",
        released_input_refs=deepcopy(args["request"]["released_input_refs"]),
        issued_at=now.isoformat(), deadline=(now + timedelta(seconds=120)).isoformat())
    request["parent_authorization"].update(checkpoint="preparation", evidence_refs=[record_ref(approval)])
    decision = deepcopy(request["parent_authorization"])
    decision.update(actor="mock-preparation-review-proposal", reason="MOCK candidate; adapter requires exact parent adoption")
    reserved_data = partition["reserved_csv"]
    audit_data = encoded(partition["controller_audit"])
    reserved_ref = artifact("reserved-only", reserved_data)
    partition_audit_ref = artifact("controller-partition-audit", audit_data)
    build_args = dict(execution=execution, request=request, reserved_ref=reserved_ref,
        reserved_receipt=partition["reserved_receipt"], partition_audit_ref=partition_audit_ref, parent_decision=decision)
    external = source_items + ([] if mock_approved_partition else [args["sources"]["sales"]])
    external += [{"ref": reserved_ref, "data": reserved_data}, {"ref": partition_audit_ref, "data": audit_data}]
    return SimpleNamespace(prepared=prepared, build_args=build_args, external=external, records=records,
                           execution=execution, request=request)


class MockPreparationResultTests(unittest.TestCase):
    def setUp(self):
        self.packet = bound_packet()

    def build(self, **changes):
        args = deepcopy(self.packet.build_args)
        args.update(changes)
        return build_result(self.packet.prepared, **args)

    def test_result_and_stage_envelope_validate_and_retain_hashes(self):
        result = self.build()
        self.assertEqual(validate_record(result["record"]), [])
        self.assertEqual(validate_record(result["stage_result"]), [])
        refs = [a["ref"] for a in self.packet.external] + [a["ref"] for a in result["artifacts"] if a["encoding"] == "bytes"]
        self.assertEqual(validate_handoff(self.packet.records + [result["record"], result["stage_result"]], refs),
                         ["stage request releases inputs outside approved sources/artifacts"])
        raw_sha = self.packet.prepared["audit"]["raw_source_ref"]["sha256"]
        self.assertTrue(all(raw_sha in item["preserved_raw_hashes"] for item in result["record"]["lineage"]))
        record = result["record"]
        allowed = record["development_context_allowlist"]
        self.assertNotIn(record["reserved_unseen_data_ref"], allowed)
        self.assertNotIn(self.packet.build_args["partition_audit_ref"], allowed)
        for availability in record["availability"]:
            if availability["contains_post_cutoff_rows"]:
                self.assertEqual(availability["permitted_use"], "reserved_unseen_evaluation")
                self.assertNotIn(availability["artifact_ref"], allowed)
        self.assertTrue(any(c["status"] == "unavailable" for c in record["quality_checks"]))
        self.assertTrue(all(f["audience"] == "final_report" for f in record["findings"]))

    def test_reserved_identity_and_partition_audit_bindings_fail_closed(self):
        for field in ("reserved_sha256", "controller_audit_sha256"):
            receipt = deepcopy(self.packet.build_args["reserved_receipt"])
            receipt[field] = "0" * 64
            with self.subTest(field=field), self.assertRaisesRegex(PreparationError, "identity/scope"):
                self.build(reserved_receipt=receipt)
        request = deepcopy(self.packet.request)
        request["released_input_refs"].append(self.packet.build_args["reserved_ref"])
        with self.assertRaisesRegex(PreparationError, "reserved rows"):
            self.build(request=request)

    def test_measured_audit_or_lineage_tampering_rejected(self):
        for mutate in (lambda p: p["audit"].update(target_retained_lines=999),
                       lambda p: p["daily"][0]["target_source_records"].append(999),
                       lambda p: p["row_lineage"].append(deepcopy(p["row_lineage"][0])),
                       lambda p: p["daily"][0].update(complete_daily_sales=True)):
            prepared = deepcopy(self.packet.prepared)
            mutate(prepared)
            with self.subTest(mutate=mutate), self.assertRaisesRegex(PreparationError, "reconciliation"):
                build_result(prepared, **self.packet.build_args)

    def assert_mutation_rejected(self, mutate, reason):
        prepared = deepcopy(self.packet.prepared)
        mutate(prepared)
        with self.assertRaisesRegex(PreparationError, reason):
            build_result(prepared, **self.packet.build_args)

    def test_empty_operations_cannot_emit_passing_join_checks(self):
        self.assert_mutation_rejected(lambda p: p.update(operations=[]), "operational reconciliation")

    def test_duplicate_aligned_operation_key_rejected(self):
        self.assert_mutation_rejected(lambda p: p["operations"].append(deepcopy(p["operations"][0])),
                                      "operational reconciliation")

    def test_incoming_quantity_change_must_reconcile_to_actual_lines(self):
        self.assert_mutation_rejected(lambda p: p["operations"][0]["inbound_lines"][0].update(Incoming_Qty=999),
                                      "receipt/policy reconciliation")

    def test_missing_operational_lineage_rejected(self):
        self.assert_mutation_rejected(lambda p: p.update(operational_lineage=[]), "operational reconciliation")

    def test_wrong_operational_asof_rejected_at_result_boundary(self):
        self.assert_mutation_rejected(lambda p: p["operations"][0].update(as_of_date="2025-12-01"),
                                      "receipt/policy reconciliation")

    def test_nonmock_handoff_cannot_invent_retrospective_information_availability(self):
        # Reclassify invented fixture fields solely to exercise the nonmock
        # rejection path. These bytes remain MOCK and establish no real source
        # facts, upstream evidence or production-success fixture.
        def reclassify(value):
            if isinstance(value, list):
                return [reclassify(item) for item in value]
            if isinstance(value, dict):
                return {name: ("derived" if name == "provenance" and item == "mock" else reclassify(item))
                        for name, item in value.items()}
            return value
        prepared = reclassify(deepcopy(self.packet.prepared))
        args = reclassify(deepcopy(self.packet.build_args))
        args["request"]["execution_contract_ref"] = record_ref(args["execution"])
        self.assertEqual(args["reserved_ref"]["sha256"], args["reserved_receipt"]["reserved_sha256"])
        self.assertEqual(args["reserved_ref"]["provenance"], "derived")
        self.assertEqual(args["reserved_receipt"]["raw_ref"], prepared["audit"]["raw_source_ref"])
        fixture = json.loads((ROOT / "examples/contracts/v0.1.0/successful_analysis.json").read_text())
        mock_evidence = next(r for r in fixture["records"] if r["kind"] == "evidence_record")
        for evidence in (None, mock_evidence):
            with self.subTest(evidence="absent" if evidence is None else "mock"), self.assertRaisesRegex(
                    PreparationError, "information availability is unverified"):
                build_result(prepared, **args, information_availability_evidence=evidence)

    def adapter_packet(self, review):
        # Explicit artificial approval packet exercises the real adapter's
        # retrieval implementation without bypassing shared validation.
        self.packet = bound_packet(mock_approved_partition=True)
        temporary = tempfile.TemporaryDirectory(prefix="dsc27-MOCK-adapter-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        store = ArtifactStore(home / "store")
        for item in self.packet.external:
            ref = item["ref"]
            self.assertEqual(store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], item["data"]), ref)
        handoff = [store.put_record(r) for r in self.packet.records]
        built = self.build()
        host = MockPreparationHost(built)
        adapter = StageAdapter(store, work_root=home / "attempts", parent_permits=lambda _: True,
            host=host, allow_mock_handoffs=True, parent_review=review)
        outcome = adapter.execute(record_ref(self.packet.request), handoff_refs=handoff,
                                  external_refs=[a["ref"] for a in self.packet.external])
        return store, built, host, outcome

    def test_artificially_approved_mock_partition_roundtrips_through_stage_adapter(self):
        reviews = []
        def review(candidate, blobs):
            reviews.append(deepcopy(candidate))
            self.assertTrue(blobs)
            self.assertEqual(candidate["records"][0]["kind"], "preparation_result")
            return mock_adopt_exact(candidate, blobs)
        store, built, host, outcome = self.adapter_packet(review)
        self.assertEqual(outcome["outcome"], "completed", outcome.get("failure"))
        self.assertEqual(len(host.calls), 1)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(store.read_record(record_ref(built["record"])), built["record"])
        for artifact_entry in built["artifacts"]:
            if artifact_entry["encoding"] == "bytes":
                self.assertEqual(store.read_bytes(artifact_entry["ref"]), artifact_entry["data"])

    def test_missing_trusted_parent_review_rejects_unpublished_candidate(self):
        store, built, _, outcome = self.adapter_packet(None)
        self.assertEqual(outcome["outcome"], "execution_failed")
        self.assertEqual(outcome["failure"]["error_code"], "integrity_error")
        with self.assertRaises(ArtifactError):
            store.read_record(record_ref(built["record"]))

    def test_current_shared_contract_blocks_unapproved_derived_partition_before_dispatch(self):
        temporary = tempfile.TemporaryDirectory(prefix="dsc27-MOCK-release-blocker-", dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        store = ArtifactStore(home / "store")
        for item in self.packet.external:
            ref = item["ref"]
            store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], item["data"])
        handoff = [store.put_record(r) for r in self.packet.records]
        host = MockPreparationHost(self.build())
        adapter = StageAdapter(store, work_root=home / "attempts", parent_permits=lambda _: True,
            host=host, allow_mock_handoffs=True, parent_review=mock_adopt_exact)
        with self.assertRaisesRegex(AdapterRejected, "releases inputs outside approved sources/artifacts"):
            adapter.execute(record_ref(self.packet.request), handoff_refs=handoff,
                            external_refs=[a["ref"] for a in self.packet.external])
        self.assertEqual(host.calls, [])


if __name__ == "__main__":
    unittest.main()
