"""Measured local intake behavior, MOCK model/customer boundary only.

These tests do not establish live LangChain, genuine customer consent, parent
transition enforcement or native analytical execution acceptance.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from suiroai.contracts import record_ref, validate_handoff
from suiroai.intake import (
    IntakeError, Response, SuppliedFile, approved_handoff, capture_response,
    draft_proposal, present_proposal, receive_submission,
)


class MockRunnable:
    """Explicitly mocked structured-model boundary; records exact input."""

    def __init__(self, output):
        self.output = deepcopy(output)
        self.calls = []

    def invoke(self, value):
        self.calls.append(json.loads(value["context"]))
        return deepcopy(self.output)


class ConversationTests(unittest.TestCase):
    REVIEW = "Use November 30, 2025 as the review date and same-product units."
    INBOUND = "The complete inbound ledger has no open orders."
    REQUEST = (
        "Recommend restocking for Store A, only its supplied products, within "
        "a 14-day purchasing review period. " + REVIEW + " " + INBOUND
    )
    GOAL = "Recommend restocking for Store A's supplied products within a 14-day review period."
    CSV = (
        b"sku,shop,sale_date,units_sold,usable_units,supplier_days,review_days\n"
        b"MOCK-P1,MOCK-A,2025-11-29,3,8,4,14\n"
        b"MOCK-P1,MOCK-A,2025-11-29,3,8,4,14\n"
        b"MOCK-P2,MOCK-A,2025-11-30,-1,0,4,14\n"
    )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dsc25-behavior-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "actual-supplied-mock.csv"
        self.path.write_bytes(self.CSV)

    def file(self, path=None, file_id="mock-sales", **kwargs):
        return SuppliedFile(file_id, str(path or self.path), "transactions", "mock-retail",
                            provenance="mock", **kwargs)

    def receipt(self, files=None, request=None, input_version=1, **kwargs):
        return receive_submission(
            original_request=self.REQUEST if request is None else request,
            files=[self.file()] if files is None else files,
            task_id="mock-retail-restocking", task_version=1,
            input_version=input_version, received_at="2026-10-17T12:00:00Z", **kwargs,
        )

    def understanding(self, receipt, *, complete=True):
        coverage = []
        if complete:
            for need, columns in (
                ("sales_history", ["sku", "shop", "sale_date", "units_sold"]),
                ("quantity_meaning", ["units_sold"]),
                ("usable_stock", ["sku", "shop", "usable_units"]),
                ("ordering_rules", ["supplier_days", "review_days"]),
            ):
                coverage.append({"need": need, "file_id": "mock-sales", "columns": columns,
                                 "request_quote": None,
                                 "explanation": "MOCK understanding of explicit source meanings; no row fitness claim."})
            for need, quote in (("review_context", self.REVIEW), ("inbound_position", self.INBOUND)):
                coverage.append({"need": need, "file_id": None, "columns": [],
                                 "request_quote": quote, "explanation": "Exact supplied request statement."})
        return {
            "supports_restocking": True, "goal": self.GOAL,
            "assumptions": [{"assumption_id": "mock-scope", "classification": "supplied_fact",
                             "statement": "Store A only, 14-day review; historical November 30, 2025 context.",
                             "status": "confirmed", "source_refs": []}],
            "gaps": [], "coverage": coverage, "alternatives": [],
        }

    def presentation(self, receipt=None, *, version=1, understanding=None):
        receipt = receipt or self.receipt()
        role = MockRunnable(understanding or self.understanding(receipt))
        draft = draft_proposal(receipt, understanding=role, proposal_version=version)
        humanizer = MockRunnable({"summary": "MOCK plain-language summary for a source-reviewed proposal."})
        reviews = []

        def review(packet, actual_receipt):
            # A deterministic test parent independently checks original source
            # bindings and scoped goal; it does not ask the model to self-verify.
            self.assertEqual(actual_receipt.submission["original_request"], receipt.submission["original_request"])
            self.assertEqual(packet["proposal"], draft.proposal)
            self.assertEqual(packet["proposal"]["source_refs"], receipt.external_refs)
            self.assertEqual(packet["proposal"]["goal"], self.GOAL)
            self.assertIn(f"proposal v{version}", packet["customer_message"])
            reviews.append(deepcopy(packet))
            return True

        presentation = present_proposal(receipt, draft, humanizer=humanizer, parent_review=review)
        self.assertEqual(len(reviews), 1)
        return receipt, draft, presentation, role, humanizer

    def response(self, presentation, decision="approve", *, changes=False, ref=None):
        return Response(decision, "MOCK customer event; no actual customer consent.",
                        "mock-customer", "2026-10-17T12:01:00Z",
                        ref or record_ref(presentation.proposal), changes)

    def capture(self, receipt, presentation, response, *, approval_version=1, **kwargs):
        return capture_response(
            presentation, response=response, approval_version=approval_version,
            current_submission=kwargs.get("current_submission", receipt.submission),
            current_proposal_ref=kwargs.get("current_proposal_ref", record_ref(presentation.proposal)),
        )

    def test_absent_inputs_never_discover_prepared_demo(self):
        with patch("suiroai.intake.receipt._read_local", side_effect=AssertionError("unlisted read")) as read:
            receipt = self.receipt(files=[])
        read.assert_not_called()
        self.assertEqual(receipt.sources, ())
        receipt, draft, presentation, role, _ = self.presentation(
            receipt, understanding=self.understanding(receipt, complete=False))
        self.assertEqual(draft.proposal["source_refs"], [])
        self.assertEqual(presentation.packet["status"], "needs_inputs")
        self.assertEqual(role.calls[0]["inspections"], [])
        for fragment in ("sales quantities", "usable stock", "inbound commitments", "supplier lead times"):
            self.assertIn(fragment, presentation.message.lower())
        self.assertIn("to avoid ordering stock already arriving", presentation.message)
        self.assertIn("No response means waiting", presentation.message)

    def test_missing_and_remote_inputs_explicitly_not_inspected(self):
        files = [self.file(self.root / "missing.csv", "mock-missing"),
                 self.file("https://example.invalid/private.csv", "mock-private")]
        receipt = self.receipt(files=files)
        self.assertEqual([f["access"] for f in receipt.submission["files"]], ["missing", "inaccessible"])
        self.assertEqual(receipt.inspections, [])
        _, _, presentation, _, _ = self.presentation(
            receipt, understanding=self.understanding(receipt, complete=False))
        self.assertIn("missing.csv is missing; it was not inspected", presentation.message)
        self.assertIn("private.csv is inaccessible; it was not inspected", presentation.message)
        self.assertIn("Provide an accessible copy", presentation.message)

    def test_partial_input_explains_only_unresolved_needs(self):
        receipt = self.receipt()
        understanding = self.understanding(receipt)
        understanding["coverage"] = [c for c in understanding["coverage"] if c["need"] == "sales_history"]
        _, draft, presentation, _, _ = self.presentation(receipt, understanding=understanding)
        gaps = {g["gap_id"] for g in draft.proposal["gaps"]}
        self.assertNotIn("intake:sales_history", gaps)
        self.assertIn("intake:usable_stock", gaps)
        self.assertIn("to subtract available stock", presentation.message)
        self.assertEqual(presentation.packet["status"], "needs_inputs")

    def test_read_only_receipt_measures_actual_bytes_without_cleaning(self):
        receipt = self.receipt()
        source = receipt.sources[0]
        self.assertEqual(source.data, self.CSV)
        self.assertEqual(source.sha256, hashlib.sha256(self.CSV).hexdigest())
        self.assertEqual(receipt.submission["files"][0]["size_bytes"], len(self.CSV))
        self.assertFalse(source.inspection["analytical_preparation_performed"])
        self.assertEqual(source.inspection["dictionary_preview"], [])
        self.assertEqual(self.path.read_bytes(), self.CSV)
        self.assertEqual(source.data.count(b"MOCK-P1"), 2)
        self.assertIn(b",-1,", source.data)

    def test_alternate_columns_and_actual_request_reach_focused_roles(self):
        receipt, draft, presentation, role, humanizer = self.presentation()
        self.assertEqual(draft.proposal["readiness"], "ready")
        self.assertEqual(role.calls[0]["submission"]["original_request"], self.REQUEST)
        self.assertEqual(role.calls[0]["inspections"][0]["columns"],
                         ["sku", "shop", "sale_date", "units_sold", "usable_units", "supplier_days", "review_days"])
        self.assertEqual(humanizer.calls[0]["proposal"], draft.proposal)
        self.assertEqual(len(role.calls), 1)
        self.assertEqual(len(humanizer.calls), 1)
        self.assertIn(self.GOAL, presentation.message)
        self.assertIn("14-day", presentation.message)

    def test_dictionary_inspection_bounded_to_40_actual_records(self):
        dictionary = self.root / "dictionary.csv"
        dictionary.write_text("field,meaning\n" + "\n".join(f"f{i},meaning{i}" for i in range(50)))
        file = SuppliedFile("mock-dictionary", str(dictionary), "dictionary", "mock-retail", provenance="mock")
        inspection = self.receipt(files=[file]).inspections[0]
        self.assertEqual(len(inspection["dictionary_preview"]), 40)
        self.assertEqual(inspection["dictionary_preview"][-1], ["f39", "meaning39"])
        self.assertIn("preview may be partial", inspection["inspection"])

    def test_invented_file_columns_and_request_quotes_rejected(self):
        receipt = self.receipt()
        for key, value in (("file_id", "prepared-demo"), ("columns", ["Inventory_Level"]),
                           ("columns", [])):
            with self.subTest(key=key, value=value):
                output = self.understanding(receipt)
                output["coverage"][0][key] = value
                with self.assertRaisesRegex(IntakeError, "absent file/column"):
                    draft_proposal(receipt, understanding=MockRunnable(output), proposal_version=1)
        output = self.understanding(receipt)
        output["coverage"][-1]["request_quote"] = "Use today's stock and a guessed lead time."
        with self.assertRaisesRegex(IntakeError, "exact supplied request quote"):
            draft_proposal(receipt, understanding=MockRunnable(output), proposal_version=1)

    def test_partial_coverage_business_gap_blocks_signoff_without_algorithm_questions(self):
        receipt = self.receipt()
        understanding = self.understanding(receipt)
        understanding["gaps"] = [{"gap_id": "mock:coverage", "description": "Stock omits one requested product.",
                                  "material": True, "blocks": ["approval", "execution"],
                                  "request_to_user": "Supply usable stock for the omitted product to calculate its order."}]
        _, _, presentation, _, _ = self.presentation(receipt, understanding=understanding)
        self.assertEqual(presentation.packet["status"], "needs_material_facts")
        result = self.capture(receipt, presentation, self.response(presentation))
        self.assertEqual(result.approval["decision"], "pending")
        for choice in ("imputation", "hyperparameter", "choose an algorithm"):
            self.assertNotIn(choice, presentation.message.lower())

    def test_parent_review_rejects_misleading_humanization_and_nonliteral_true(self):
        receipt = self.receipt()
        draft = draft_proposal(receipt, understanding=MockRunnable(self.understanding(receipt)), proposal_version=1)
        humanizer = MockRunnable({"summary": "All rows cleaned and the recommendation is approved."})
        reviewed = []

        def independent_review(packet, receipt):
            reviewed.append(packet)
            return "All rows cleaned" not in packet["customer_message"]

        with self.assertRaisesRegex(IntakeError, "Parent source review"):
            present_proposal(receipt, draft, humanizer=humanizer, parent_review=independent_review)
        self.assertEqual(len(reviewed), 1)
        with self.assertRaisesRegex(IntakeError, "Parent source review"):
            present_proposal(receipt, draft, humanizer=MockRunnable({"summary": "MOCK summary"}),
                             parent_review=lambda packet, receipt: 1)

    def test_parent_callback_cannot_mutate_presented_snapshot(self):
        receipt = self.receipt()
        draft = draft_proposal(receipt, understanding=MockRunnable(self.understanding(receipt)), proposal_version=1)

        def review(packet, receipt):
            packet["proposal"]["goal"] = "mutated goal"
            return True

        presentation = present_proposal(receipt, draft, humanizer=MockRunnable({"summary": "MOCK summary"}),
                                        parent_review=review)
        self.assertEqual(presentation.proposal["goal"], self.GOAL)

    def test_silence_and_ambiguous_reply_wait_without_approval(self):
        receipt, _, presentation, _, _ = self.presentation()
        for response in (None, self.response(presentation, "unclear")):
            with self.subTest(response=response):
                result = self.capture(receipt, presentation, response)
                self.assertEqual(result.status, "awaiting_confirmation")
                self.assertEqual(result.approval["decision"], "pending")
                self.assertIsNone(result.approval["actor"])
                with self.assertRaises(IntakeError):
                    approved_handoff(receipt, presentation, result,
                                     current_submission=receipt.submission,
                                     current_proposal_ref=record_ref(presentation.proposal))

    def test_rejection_correction_new_material_and_qualified_yes_require_revision(self):
        receipt, _, presentation, _, _ = self.presentation()
        for decision, changes in (("reject", False), ("correct", False),
                                  ("new_material", False), ("approve", True)):
            with self.subTest(decision=decision, changes=changes):
                result = self.capture(receipt, presentation, self.response(presentation, decision, changes=changes))
                self.assertEqual(result.status, "revise_proposal")
                self.assertEqual(result.approval["decision"], "rejected")
                self.assertIn("revised proposal", result.message)
                self.assertIn("Execution has not started", result.message)

    def test_revised_input_and_proposal_require_new_exact_consent(self):
        receipt, _, original, _, _ = self.presentation()
        old_response = self.response(original)
        changed = self.root / "corrected.csv"
        changed.write_bytes(self.CSV.replace(b",8,4,14", b",9,4,14"))
        new_receipt = self.receipt(files=[self.file(changed, version=2)], input_version=2)
        _, _, revised, _, _ = self.presentation(new_receipt, version=2)
        self.assertNotEqual(receipt.ref, new_receipt.ref)
        self.assertNotEqual(record_ref(original.proposal), record_ref(revised.proposal))
        with self.assertRaisesRegex(IntakeError, "current exact proposal"):
            self.capture(new_receipt, revised, old_response)
        with self.assertRaisesRegex(IntakeError, "Stale proposal or input"):
            self.capture(receipt, original, old_response, current_submission=new_receipt.submission)
        revised_result = self.capture(new_receipt, revised, self.response(revised), approval_version=2)
        self.assertEqual(revised_result.status, "approved")
        self.assertEqual(revised_result.approval["binding"]["input_version"], 2)
        self.assertEqual(revised_result.approval["binding"]["proposal_version"], 2)

    def test_revised_proposal_same_input_still_invalidates_old_signoff(self):
        receipt, _, original, _, _ = self.presentation()
        _, _, revised, _, _ = self.presentation(receipt, version=2)
        with self.assertRaisesRegex(IntakeError, "current exact proposal"):
            self.capture(receipt, revised, self.response(original))

    def test_draft_cannot_be_presented_against_changed_input(self):
        receipt = self.receipt()
        draft = draft_proposal(receipt, understanding=MockRunnable(self.understanding(receipt)), proposal_version=1)
        new_receipt = self.receipt(input_version=2)
        with self.assertRaisesRegex(IntakeError, "different supplied input version"):
            present_proposal(new_receipt, draft, humanizer=MockRunnable({"summary": "MOCK"}),
                             parent_review=lambda packet, receipt: True)

    def test_exact_approved_proposal_survives_immutable_handoff_without_execution(self):
        with patch("suiroai.integration.adapter.StageAdapter.execute", side_effect=AssertionError("analytical stage dispatched")) as adapter, \
             patch("suiroai.integration.native.NativeHost.execute", side_effect=AssertionError("native analytical execution")) as native:
            receipt, draft, presentation, _, _ = self.presentation()
            result = self.capture(receipt, presentation, self.response(presentation))
            records = approved_handoff(receipt, presentation, result,
                                       current_submission=receipt.submission,
                                       current_proposal_ref=record_ref(presentation.proposal))
        adapter.assert_not_called()
        native.assert_not_called()
        self.assertEqual([r["kind"] for r in records], ["submission", "task_proposal", "task_approval"])
        self.assertEqual(records[1], draft.proposal)
        self.assertEqual(records[1], presentation.proposal)
        self.assertEqual(records[2]["proposal_ref"], record_ref(draft.proposal))
        self.assertEqual(validate_handoff(records, receipt.external_refs), [])
        records[1]["goal"] = "attempted downstream mutation"
        records[0]["original_request"] = "attempted receipt mutation"
        self.assertEqual(presentation.proposal, draft.proposal)
        self.assertEqual(receipt.submission["original_request"], self.REQUEST)
        self.assertEqual(self.path.read_bytes(), self.CSV)

    def test_absent_inputs_cannot_be_approved(self):
        receipt = self.receipt(files=[])
        _, _, presentation, _, _ = self.presentation(receipt, understanding=self.understanding(receipt, complete=False))
        result = self.capture(receipt, presentation, self.response(presentation))
        self.assertEqual(result.status, "needs_inputs")
        self.assertEqual(result.approval["decision"], "pending")

    def test_model_failure_is_not_missing_data_or_approval(self):
        receipt = self.receipt()

        class FailingRunnable:
            def invoke(self, context):
                raise RuntimeError("MOCK model unavailable")

        with self.assertRaisesRegex(RuntimeError, "MOCK model unavailable"):
            draft_proposal(receipt, understanding=FailingRunnable(), proposal_version=1)
        with self.assertRaisesRegex(IntakeError, "Invalid focused role output"):
            draft_proposal(receipt, understanding=MockRunnable({"approve": True}), proposal_version=1)

    def test_narrower_alternative_requires_confirmation_without_changing_goal(self):
        receipt = self.receipt(files=[])
        understanding = self.understanding(receipt, complete=False)
        understanding["alternatives"] = ["A sales-only exploration after you supply sales data."]
        _, draft, presentation, _, _ = self.presentation(receipt, understanding=understanding)
        self.assertEqual(draft.proposal["goal"], self.GOAL)
        self.assertIn("Alternative requiring confirmation: A sales-only exploration", presentation.message)
        self.assertEqual(draft.proposal["readiness"], "needs_inputs")
        self.assertEqual(self.capture(receipt, presentation, None).approval["decision"], "pending")

    def test_other_business_request_has_no_restocking_proposal_or_signoff(self):
        receipt = self.receipt(files=[], request="Schedule staff shifts for our retail store.")
        output = self.understanding(receipt, complete=False)
        output.update(supports_restocking=False, goal="The supplied request is staffing, outside this retail restocking MVP.")
        draft = draft_proposal(receipt, understanding=MockRunnable(output), proposal_version=1)
        humanizer = MockRunnable({"summary": "Must not be called for unsupported tasks."})
        reviewed = []

        def review(packet, receipt):
            reviewed.append(packet)
            return packet["proposal"] is None and "staffing" in packet["customer_message"]

        presentation = present_proposal(receipt, draft, humanizer=humanizer, parent_review=review)
        self.assertIsNone(draft.proposal)
        self.assertEqual(presentation.packet["status"], "unsupported_task")
        self.assertEqual(humanizer.calls, [])
        self.assertEqual(len(reviewed), 1)
        with self.assertRaisesRegex(IntakeError, "Unsupported task"):
            capture_response(presentation, response=None, approval_version=1,
                             current_submission=receipt.submission, current_proposal_ref={})

    def test_oversized_and_nonregular_inputs_require_accessible_bounded_copy(self):
        receipt = self.receipt(files=[self.file(), self.file(self.root, "mock-directory")], max_file_bytes=10)
        self.assertEqual(receipt.sources, ())
        self.assertEqual([f["access"] for f in receipt.submission["files"]], ["inaccessible", "inaccessible"])
        self.assertIn("bounded readable extract", receipt.submission["files"][0]["access_reason"])
        self.assertTrue(receipt.submission["files"][1]["access_reason"])
        self.assertEqual(self.path.read_bytes(), self.CSV)

    def test_connector_errors_do_not_expose_private_details(self):
        def denied(file, limit):
            raise PermissionError("private token SECRET-MOCK-TOKEN should never reach customer")

        receipt = self.receipt(read_bytes=denied)
        self.assertEqual(receipt.sources, ())
        self.assertNotIn("SECRET-MOCK-TOKEN", receipt.submission_json)
        self.assertIn("authorized accessible bytes", receipt.submission["files"][0]["access_reason"])

    def test_assumption_cannot_claim_unmeasured_provenance(self):
        receipt = self.receipt()
        output = self.understanding(receipt)
        output["assumptions"][0]["source_refs"] = [{"artifact_id": "unlisted-stock", "version": 1,
                                                    "sha256": "0" * 64, "provenance": "mock"}]
        with self.assertRaisesRegex(IntakeError, "absent or unmeasured source"):
            draft_proposal(receipt, understanding=MockRunnable(output), proposal_version=1)

    def test_missing_business_meaning_or_review_context_requests_facts_not_more_files(self):
        receipt = self.receipt()
        for unresolved_need in ("quantity_meaning", "review_context"):
            with self.subTest(unresolved_need=unresolved_need):
                output = self.understanding(receipt)
                output["coverage"] = [c for c in output["coverage"] if c["need"] != unresolved_need]
                _, draft, presentation, _, _ = self.presentation(receipt, understanding=output)
                self.assertEqual(draft.proposal["readiness"], "needs_material_facts")
                self.assertEqual(presentation.packet["status"], "needs_material_facts")
                self.assertEqual(presentation.packet["capability"], "needs_material_facts")
                material = [g for g in draft.proposal["gaps"] if g["material"]]
                self.assertEqual([g["gap_id"] for g in material], [f"intake:{unresolved_need}"])
                self.assertIn("to ", material[0]["request_to_user"])
                result = self.capture(receipt, presentation, self.response(presentation))
                self.assertEqual(result.status, "needs_material_facts")
                self.assertEqual(result.approval["decision"], "pending")

    def test_ready_with_disclosed_assumptions_still_waits_for_explicit_signoff(self):
        receipt = self.receipt()
        for classification in ("supported_interpretation", "synthetic_assumption"):
            with self.subTest(classification=classification):
                output = self.understanding(receipt)
                output["assumptions"].append({
                    "assumption_id": "mock-disclosed-assumption", "classification": classification,
                    "statement": "MOCK proposed same-product unit interpretation, disclosed for sign-off.",
                    "status": "proposed", "source_refs": receipt.external_refs,
                })
                _, draft, presentation, _, _ = self.presentation(receipt, understanding=output)
                self.assertEqual(draft.proposal["readiness"], "ready")
                self.assertEqual(presentation.packet["capability"], "ready_with_assumptions")
                self.assertEqual(presentation.packet["status"], "awaiting_confirmation")
                self.assertIn(classification + ": MOCK proposed", presentation.message)
                pending = self.capture(receipt, presentation, None)
                self.assertEqual(pending.status, "awaiting_confirmation")
                self.assertEqual(pending.approval["decision"], "pending")
                approved = self.capture(receipt, presentation, self.response(presentation))
                records = approved_handoff(receipt, presentation, approved,
                                           current_submission=receipt.submission,
                                           current_proposal_ref=record_ref(draft.proposal))
                self.assertEqual(records[1], draft.proposal)
                self.assertEqual(records[1]["assumptions"][-1]["classification"], classification)

    def test_oversized_understanding_context_rejected_before_model_call(self):
        # Multi-byte text makes this a byte-boundary check, not a character bound.
        receipt = self.receipt(request=self.REQUEST + " é" * 50000)
        model = MockRunnable(self.understanding(receipt))
        with self.assertRaisesRegex(IntakeError, "context exceeds 128 KiB"):
            draft_proposal(receipt, understanding=model, proposal_version=1)
        self.assertEqual(model.calls, [])

    def test_store_correction_preserves_original_request_and_reaches_exact_revised_handoff(self):
        original_request = self.REQUEST.replace("Store A", "S01")
        with patch("suiroai.integration.adapter.StageAdapter.execute", side_effect=AssertionError("execution before parent")) as execute:
            first = self.receipt(request=original_request)
            first_output = self.understanding(first)
            first_output["goal"] = "Recommend restocking for S01's supplied products within a 14-day review period."
            first_draft = draft_proposal(first, understanding=MockRunnable(first_output), proposal_version=1)
            first_presentation = present_proposal(
                first, first_draft, humanizer=MockRunnable({"summary": "MOCK S01 proposal"}),
                parent_review=lambda packet, receipt: packet["proposal"]["goal"] == first_output["goal"],
            )
            old_consent = self.response(first_presentation)
            correction = Response(
                "correct", "Correction: use store S02 instead of S01; all other requested scope remains unchanged.",
                "mock-customer", "2026-10-17T12:02:00Z", record_ref(first_presentation.proposal), True,
            )
            rejected = self.capture(first, first_presentation, correction)
            self.assertEqual(rejected.status, "revise_proposal")
            self.assertEqual(rejected.approval["decision"], "rejected")

            revised = receive_submission(
                original_request=original_request, files=[self.file()],
                task_id="mock-retail-restocking", task_version=2, input_version=2,
                received_at="2026-10-17T12:03:00Z",
            )
            revised_output = self.understanding(revised)
            revised_output["goal"] = "Recommend restocking for S02's supplied products within a 14-day review period."
            role = MockRunnable(revised_output)
            draft = draft_proposal(revised, understanding=role, proposal_version=2, clarifications=(correction,))
            self.assertEqual(role.calls[0]["submission"]["original_request"], original_request)
            self.assertEqual(role.calls[0]["customer_clarifications"][0]["text"], correction.text)
            self.assertEqual(role.calls[0]["customer_clarifications"][0]["reply_to"], correction.reply_to)

            def revised_review(packet, receipt):
                return (receipt.submission["original_request"] == original_request
                        and packet["proposal"]["goal"] == revised_output["goal"]
                        and correction.text in packet["customer_message"])

            presented = present_proposal(
                revised, draft, humanizer=MockRunnable({"summary": "MOCK corrected S02 proposal"}),
                parent_review=revised_review,
            )
            self.assertIn(correction.text, presented.message)
            clarification_fact = draft.proposal["assumptions"][-1]
            self.assertEqual(clarification_fact["classification"], "supplied_fact")
            self.assertIn(correction.actor, clarification_fact["statement"])
            self.assertIn(correction.at, clarification_fact["statement"])
            with self.assertRaisesRegex(IntakeError, "current exact proposal"):
                self.capture(revised, presented, old_consent)
            approved = self.capture(revised, presented, self.response(presented), approval_version=2)
            handoff = approved_handoff(revised, presented, approved,
                                       current_submission=revised.submission,
                                       current_proposal_ref=record_ref(presented.proposal))
            self.assertEqual(handoff[1], draft.proposal)
            self.assertEqual(handoff[1]["goal"], revised_output["goal"])
            self.assertEqual(handoff[1]["assumptions"][-1], clarification_fact)
            self.assertEqual(handoff[0]["original_request"], original_request)
            self.assertEqual(handoff[1]["binding"]["task_version"], 2)
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
