"""DSC-24 draft.3 MOCK consumer examples; no real model/execution acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from suiroai.contracts.validation import input_digest, proposal_digest, record_ref, validate_record
from suiroai.replenishment.context import Handoff, InputError
from suiroai.reporting import draft_execution_failure, draft_missing_inputs, draft_success, draft_validation_failure


ROOT = Path(__file__).resolve().parents[2]


def mock_handoff(name="successful_analysis", parent_confirms=lambda ref, decision: True):
    bundle = json.loads((ROOT / f"examples/contracts/v0.1.0/{name}.json").read_text())
    records = [r for r in bundle["records"] if r["kind"] not in {"report_draft", "output_verification"}
               and r.get("requirement_id") != "mock-terminal-evidence-binding"]
    refs = [a["ref"] for a in bundle["mock_artifacts"]]
    content = {a["ref"]["artifact_id"]: json.dumps(a["content_marker"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode() for a in bundle["mock_artifacts"]}
    return Handoff(records, refs, lambda ref: content[ref["artifact_id"]], parent_confirms, allow_mock=True)


def revise_mock(h, mutate):
    """Build a new explicitly mock immutable chain after fixture-only changes."""
    replacements = {}
    def replace(value):
        if isinstance(value, dict):
            key = json.dumps(value, sort_keys=True)
            if key in replacements:
                return deepcopy(replacements[key])
            return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return value
    records = []
    for original in h.records:
        revised = deepcopy(original)
        mutate(revised)
        revised = replace(revised)
        replacements[json.dumps(record_ref(original), sort_keys=True)] = record_ref(revised)
        records.append(revised)
    return Handoff(records, h.external_refs, h._read_bytes, h._parent_confirms, allow_mock=True)


class ReportingTests(unittest.TestCase):
    def test_mock_success_preserves_exact_approved_values_and_evidence(self):
        h = mock_handoff()
        result = draft_success(h, artifact_id="mock-new-report")
        quantity = h.one("quantity_result")
        self.assertEqual(result["orders"], quantity["orders"])
        self.assertEqual(result["exceptions"], quantity["exceptions"])
        self.assertEqual(result["quantity_result_ref"], record_ref(quantity))
        self.assertEqual(result["orders"][0]["approved_order_quantity"], 15)
        self.assertIn("15 product_unit", result["customer_draft"])
        self.assertIn("synthetic", result["customer_draft"])
        self.assertIn("MOCK DEVELOPMENT EXAMPLE", result["customer_draft"])
        self.assertIn("baseline", result["customer_draft"])
        self.assertIn("Reserved unseen evaluation", result["customer_draft"])
        self.assertEqual(validate_record(result), [])
        self.assertNotIn("permitted_response", result)

    def test_humanizer_cannot_add_or_omit_claims(self):
        for humanizer in (lambda claims: ["invented benefit"], lambda claims: [], lambda claims: [c["claim_id"] for c in claims] + [claims[0]["claim_id"]]):
            with self.assertRaises(InputError):
                draft_success(mock_handoff(), artifact_id="mock-rejected", humanizer=humanizer)
        result = draft_success(mock_handoff(), artifact_id="mock-reordered", humanizer=lambda claims: [c["claim_id"] for c in reversed(claims)])
        self.assertEqual(result["customer_draft"], "\n\n".join(c["statement"] for c in reversed(result["claims"])))

    def test_parent_approval_precedes_humanizing(self):
        called = []
        h = mock_handoff(parent_confirms=lambda ref, decision: False)
        with self.assertRaises(InputError):
            draft_success(h, artifact_id="mock-untrusted", humanizer=lambda claims: called.append(True))
        self.assertEqual(called, [])

    def test_execution_action_gate_blocks_every_report_path_before_reads_or_humanizing(self):
        for fixture, method in (("successful_analysis", draft_success), ("validation_failed", draft_validation_failure), ("execution_failed", draft_execution_failure)):
            def mutate(record):
                if record["kind"] == "execution_contract":
                    record["allowed_actions"] = [action for action in record["allowed_actions"] if action != "draft_report"]
            h = revise_mock(mock_handoff(fixture), mutate)
            reads, humanizer_calls = [], []
            h._read_bytes = lambda ref: reads.append(ref)
            kwargs = {"artifact_id": "mock-disallowed-report"}
            if method is draft_success:
                kwargs["humanizer"] = lambda claims: humanizer_calls.append(True)
            if method is draft_execution_failure:
                kwargs["failed_stage_ref"] = record_ref(h.one("stage_result"))
            with self.subTest(fixture=fixture), self.assertRaisesRegex(InputError, "does not allow draft_report"):
                method(h, **kwargs)
            self.assertEqual(reads, [])
            self.assertEqual(humanizer_calls, [])

    def test_claim_source_bytes_must_match_before_humanizing(self):
        called = []
        h = mock_handoff()
        h._read_bytes = lambda ref: b"corrupted evidence, even though graph refs are intact"
        with self.assertRaisesRegex(InputError, "bytes do not match"):
            draft_success(h, artifact_id="mock-corrupt-source", humanizer=lambda claims: called.append(True))
        self.assertEqual(called, [])

    def test_success_claims_have_resolvable_exact_refs(self):
        h = mock_handoff()
        result = draft_success(h, artifact_id="mock-claim-bindings")
        known_refs = h.external_refs + [record_ref(r) for r in h.records]
        self.assertTrue(all(ref in known_refs for claim in result["claims"] for ref in claim["evidence_refs"]))
        order_claims = [claim for claim in result["claims"] if claim["claim_id"].startswith("order-")]
        self.assertEqual(order_claims[0]["evidence_refs"], [record_ref(h.one("quantity_result"))])
        self.assertEqual(set(result["customer_draft"].split("\n\n")), {c["statement"] for c in result["claims"]})

    def test_humanizer_cannot_mutate_the_original_claims(self):
        def humanizer(claims):
            ids = [c["claim_id"] for c in claims]
            claims[0]["statement"] = "Invented profit benefit of 99999 dollars"
            return ids
        result = draft_success(mock_handoff(), artifact_id="mock-mutating-callable", humanizer=humanizer)
        self.assertNotIn("99999", result["customer_draft"])

    def test_missing_material_findings_block_success(self):
        h = mock_handoff()
        # No mutations to contract refs: replace Handoff.one's returned content
        # after validation only to exercise the consumer's stricter completeness.
        original = h.one
        def one(kind):
            result = deepcopy(original(kind))
            if kind == "feature_result":
                result["findings"] = []
            return result
        h.one = one
        with self.assertRaises(InputError):
            draft_success(h, artifact_id="mock-incomplete-findings")

    def test_measured_failure_has_no_orders_and_retains_failed_score(self):
        h = mock_handoff("validation_failed")
        result = draft_validation_failure(h, artifact_id="mock-failure-draft")
        self.assertEqual(result["outcome"], "validation_failure")
        self.assertEqual(result["orders"], [])
        self.assertIsNone(result["quantity_result_ref"])
        self.assertIn("= 12 product_unit", result["customer_draft"])
        self.assertIn("could not produce a reliable solution", result["customer_draft"])
        self.assertIn("direction upper_bound, threshold 10 product_unit", result["customer_draft"])
        self.assertIn("minimum observation count 1", result["customer_draft"])
        self.assertIn("Required validation check fully_observed: pass", result["customer_draft"])
        self.assertEqual(validate_record(result), [])

    def test_failure_paths_are_distinct(self):
        h = mock_handoff("execution_failed")
        failed = h.one("stage_result")
        result = draft_execution_failure(h, artifact_id="mock-runtime-draft", failed_stage_ref=record_ref(failed))
        self.assertEqual(result["outcome"], "execution_failure")
        self.assertEqual(result["failure"]["error_code"], "plugin_unavailable")
        self.assertEqual(result["orders"], [])
        self.assertIsNone(result["final_validation_ref"])
        self.assertNotIn("failed the predeclared", result["customer_draft"])
        self.assertIn(failed["failure"]["reason"], result["customer_draft"])
        self.assertEqual(result["failure"]["reason"], failed["failure"]["reason"])
        self.assertEqual(validate_record(result), [])
        with self.assertRaises(InputError):
            draft_validation_failure(mock_handoff(), artifact_id="mock-not-failed")

    def test_missing_input_guidance_preserves_specific_requests_without_execution(self):
        h = mock_handoff("missing_inputs")
        result = draft_missing_inputs(h)
        self.assertEqual(result["outcome"], "missing_inputs")
        self.assertEqual(result["orders"], [])
        self.assertFalse(result["delivery_authorized"])
        self.assertEqual(result["gaps"], h.one("task_proposal")["gaps"])
        self.assertIn("accessible sales file and source dictionary", result["customer_draft"])
        self.assertIn(h.one("task_proposal")["goal"], result["customer_draft"])
        self.assertIn("No supplied source is currently accessible", result["customer_draft"])
        self.assertIn("review the updated proposal for the same business goal", result["customer_draft"])
        self.assertNotIn("execution_contract_ref", result)

    def test_approved_product_name_is_copied_exactly_and_unsafe_names_block(self):
        def named(name):
            def mutate(record):
                if record["kind"] == "quantity_result":
                    record["orders"][0]["product_name"] = name
            return revise_mock(mock_handoff(), mutate)
        result = draft_success(named("MOCK Oat & Almond Cereal"), artifact_id="mock-named-report")
        self.assertIn("product name MOCK Oat & Almond Cereal", result["customer_draft"])
        self.assertEqual(result["orders"][0]["product_name"], "MOCK Oat & Almond Cereal")
        for name in ("MOCK\nINJECTED", "<script>unsafe</script>", "[click](https://example.com)", "MOCK\u202e15"):
            with self.assertRaises(InputError):
                draft_success(named(name), artifact_id="mock-unsafe-name")

    def test_missing_name_mapping_is_disclosed_without_changing_approved_rows(self):
        h = mock_handoff()
        quantity = h.one("quantity_result")
        result = draft_success(h, artifact_id="mock-no-name-mapping")
        claim = next(c for c in result["claims"] if c["claim_id"] == "missing-product-name-mapping")
        self.assertEqual(claim["statement"], "No verified product-name mapping was supplied for some approved rows; those items are identified by source, product ID and store ID.")
        self.assertEqual(claim["evidence_refs"], [record_ref(quantity)])
        self.assertIn(claim["statement"], result["customer_draft"])
        self.assertEqual(result["orders"], quantity["orders"])
        self.assertEqual(result["exceptions"], quantity["exceptions"])

    def test_checkpoint_names_are_enforced_before_humanizing(self):
        for kind, field, method, fixture in (("quantity_result", "parent_decision", draft_success, "successful_analysis"),
                                             ("final_validation_result", "parent_review", draft_success, "successful_analysis"),
                                             ("final_validation_result", "parent_review", draft_validation_failure, "validation_failed")):
            def mutate(record):
                if record["kind"] == kind and record.get(field):
                    record[field]["checkpoint"] = "output_verification"
            with self.subTest(kind=kind, method=method.__name__):
                h = revise_mock(mock_handoff(fixture), mutate)
                with self.assertRaisesRegex(InputError, "exact .* checkpoint"):
                    method(h, artifact_id="mock-wrong-checkpoint")

    def test_execution_failure_rejects_logs_and_wrong_checkpoint(self):
        for reason, checkpoint in (("MOCK traceback\nraw diagnostics", "approved_execution"),
                                   ("MOCK provider unavailable", "output_verification")):
            def mutate(record):
                if record["kind"] == "stage_result":
                    record["failure"]["reason"] = reason
                    record["parent_decision"]["checkpoint"] = checkpoint
            h = revise_mock(mock_handoff("execution_failed"), mutate)
            with self.assertRaises(InputError):
                draft_execution_failure(h, artifact_id="mock-unsafe-failure", failed_stage_ref=record_ref(h.one("stage_result")))

    def test_failed_required_check_is_named_in_validation_explanation(self):
        def mutate(record):
            if record["kind"] == "final_validation_result":
                record["checks"][0]["status"] = "fail"
        h = revise_mock(mock_handoff("validation_failed"), mutate)
        result = draft_validation_failure(h, artifact_id="mock-failed-coverage")
        self.assertIn("Required validation check fully_observed: fail", result["customer_draft"])

    def test_missing_input_supported_work_names_only_accessible_supplied_sources(self):
        h = mock_handoff("missing_inputs")
        available = mock_handoff("approved_execution")
        source = available.one("submission")["files"][1]
        submission = h.one("submission")
        submission["files"].append(source)
        submission["binding"]["input_digest"] = input_digest(submission)
        proposal = h.one("task_proposal")
        proposal["submission_ref"] = record_ref(submission)
        proposal["binding"]["input_digest"] = submission["binding"]["input_digest"]
        proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
        combined = Handoff([submission, proposal], available.external_refs, available._read_bytes, available._parent_confirms, allow_mock=True)
        result = draft_missing_inputs(combined)
        self.assertIn("limited to read-only inspection", result["customer_draft"])
        self.assertIn(f"Accessible source: {source['original_name']}; declared role {source['source_role']}", result["customer_draft"])
        self.assertNotIn("Accessible source: mock-unavailable-sales.csv", result["customer_draft"])
        combined._read_bytes = lambda ref: b"MOCK inaccessible or altered source"
        with self.assertRaisesRegex(InputError, "bytes do not match"):
            draft_missing_inputs(combined)

    def test_mutated_approved_rows_are_rejected_before_humanizing(self):
        h = mock_handoff()
        quantity = max((r for r in h.records if r["kind"] == "quantity_result"), key=lambda r: r["artifact_version"])
        quantity["orders"][0]["approved_order_quantity"] = 16
        with self.assertRaises(InputError):
            draft_success(h, artifact_id="mock-altered-quantity")

    def test_missing_independent_numerical_evidence_cannot_be_reported(self):
        h = mock_handoff()
        quantity = max((r for r in h.records if r["kind"] == "quantity_result"), key=lambda r: r["artifact_version"])
        quantity["independent_check_refs"] = []
        with self.assertRaises(InputError):
            draft_success(h, artifact_id="mock-no-independent-evidence")


if __name__ == "__main__":
    unittest.main()
