"""DSC-24 draft.3 MOCK graph with real byte/hash mechanics, not model acceptance."""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import unittest

from suiroai.contracts.validation import digest, input_digest, proposal_digest, record_ref, walk
from suiroai.replenishment.calculation import calculate_candidate
from suiroai.replenishment.context import Handoff, InputError

from test_calculation import KEY, inputs


ROOT = Path(__file__).resolve().parents[2]
REF_FIELDS = {"artifact_id", "version", "sha256", "provenance"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def csv_bytes(rows, fieldnames):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def scenario(*, mutate_inputs=None, mutate_records=None, name_rows=None,
             parent_confirms=lambda ref, decision: True):
    """Create a fresh explicit MOCK approval around test-specific source bytes.

    This is fixture construction only, never a technique to alter a live approved
    task. Hashes, proposal input digest and record references converge together.
    """
    bundle = json.loads((ROOT / "examples/contracts/v0.1.0/successful_analysis.json").read_text())
    records = [r for r in bundle["records"] if r["kind"] not in
               {"quantity_result", "report_draft", "output_verification", "evidence_record"}]
    content = {a["ref"]["artifact_id"]: canonical(a["content_marker"]) for a in bundle["mock_artifacts"]}
    refs = [deepcopy(a["ref"]) for a in bundle["mock_artifacts"]]
    args = inputs(receipts=((2, 3),))
    if mutate_inputs:
        mutate_inputs(args)
    for kind, index in (("stock", 0), ("receipts", 1), ("policy", 2)):
        rows = [row for values in args[1][index].values() for _, row in values]
        template = inputs(receipts=((2, 3),))[1][index][KEY][0][1]
        content["mock-" + kind] = csv_bytes(rows, list(template))
    content["mock-november-30-forecast"] = canonical([row for values in args[1][3].values() for _, row in values])
    content["mock-prepared-development"] = canonical([dict(zip(("source_namespace", "product_id", "store_id"), KEY))])
    if name_rows is not None:
        content["mock-sales"] = canonical(name_rows)
    external_hashes = {ref["artifact_id"]: hashlib.sha256(content[ref["artifact_id"]]).hexdigest() for ref in refs}
    submission = next(r for r in records if r["kind"] == "submission")
    proposal = next(r for r in records if r["kind"] == "task_proposal")
    for file in submission["files"]:
        file["sha256"] = external_hashes[file["file_id"]]
        file["size_bytes"] = len(content[file["file_id"]])
    if mutate_records:
        mutate_records(records)
    for _ in range(50):
        previous = canonical([records, refs])
        frozen = next(r for r in records if r["kind"] == "evaluation_result")["frozen"]
        content["mock-freeze-manifest"] = canonical(frozen)
        external_hashes["mock-freeze-manifest"] = hashlib.sha256(content["mock-freeze-manifest"]).hexdigest()
        hashes = {(r["artifact_id"], r["artifact_version"]): digest(r) for r in records}
        hashes.update({(r["artifact_id"], r["version"]): external_hashes[r["artifact_id"]] for r in refs})
        for node in walk([records, refs]):
            if set(node) == REF_FIELDS:
                node["sha256"] = hashes[(node["artifact_id"], node["version"])]
        current_input = input_digest(submission)
        for record in records:
            record["binding"]["input_digest"] = current_input
        current_proposal = proposal_digest(proposal)
        for record in records:
            if "proposal_digest" in record["binding"]:
                record["binding"]["proposal_digest"] = current_proposal
        if canonical([records, refs]) == previous:
            break
    else:
        raise AssertionError("MOCK fixture graph did not converge")
    handoff = Handoff(records, refs, lambda ref: content[ref["artifact_id"]], parent_confirms, allow_mock=True)
    scope = next(ref for ref in refs if ref["artifact_id"] == "mock-prepared-development")
    return handoff, scope, content


def calculate(handoff, scope, **kwargs):
    return calculate_candidate(handoff, artifact_id="mock-generated-candidate", scope_ref=scope,
                               scope_reader=json.loads, forecast_reader=json.loads,
                               source_namespace="mock-retail", **kwargs)


def name_mapping(name="MOCK Oat & Almond Cereal", available="2025-11-29"):
    return {"key": dict(zip(("source_namespace", "product_id", "store_id"), KEY)),
            "product_name": name, "latest_information_available_date": available}


def name_reference(handoff):
    return next(ref for ref in handoff.external_refs if ref["artifact_id"] == "mock-sales")


class PublicHandoffTests(unittest.TestCase):
    def test_passed_mock_validation_produces_unapproved_candidate_with_exact_bindings(self):
        h, scope, _ = scenario()
        result = calculate(h, scope)
        self.assertEqual(result["provenance"], "mock")
        self.assertEqual(result["orders"][0]["rounded_order_quantity"], 5)
        self.assertIsNone(result["orders"][0]["approved_order_quantity"])
        self.assertIsNone(result["parent_decision"])
        self.assertEqual(result["independent_check_refs"], [])
        self.assertEqual(result["exceptions"], [])
        self.assertEqual(result["final_validation_ref"], record_ref(h.one("final_validation_result")))
        self.assertEqual(result["orders"][0]["forecast_ref"], h.one("evaluation_result")["frozen"]["november_30_forecast_ref"])
        self.assertIn(scope, result["arithmetic_source_refs"])
        audit = json.loads(result["arithmetic_checks"][0]["actual"])
        self.assertEqual(audit["source_rows"], {"stock": [2], "receipts": [2], "policy": [2], "forecast": [1, 2, 3, 4]})
        self.assertEqual(audit["raw_order_need_exact"], "5")
        self.assertEqual(audit["receipt_convention"], "end_of_day_conservative")
        self.assertNotIn("product_name", result["orders"][0])
        self.assertNotIn("names", audit["source_rows"])

    def test_optional_bound_name_is_present_before_numerical_approval(self):
        mapping = name_mapping()
        h, scope, _ = scenario(name_rows=[mapping])
        ref = name_reference(h)
        result = calculate(h, scope, name_ref=ref, name_reader=json.loads)
        row = result["orders"][0]
        self.assertEqual(row["product_name"], "MOCK Oat & Almond Cereal")
        self.assertEqual(row["rounded_order_quantity"], 5)
        self.assertIsNone(row["approved_order_quantity"])
        self.assertIn(ref, result["arithmetic_source_refs"])
        self.assertIn(ref, row["arithmetic_input_refs"])
        self.assertIn(ref, row["evidence_refs"])
        audit = json.loads(result["arithmetic_checks"][0]["actual"])
        self.assertEqual(audit["product_name"], mapping["product_name"])
        self.assertEqual(audit["product_name_latest_information_available_date"], "2025-11-29")
        self.assertEqual(audit["source_rows"]["names"], [1])

    def test_optional_name_bytes_are_immutable_before_adapter_runs(self):
        h, scope, content = scenario(name_rows=[name_mapping()])
        ref = name_reference(h)
        content["mock-sales"] = canonical([name_mapping("MOCK altered name")])
        called = []
        with self.assertRaisesRegex(InputError, "immutable reference"):
            calculate(h, scope, name_ref=ref,
                      name_reader=lambda data: called.append(True) or json.loads(data))
        self.assertEqual(called, [])

    def test_missing_duplicate_conflicting_or_future_name_withholds_scoped_key(self):
        for rows, reason in (
            ([], "missing_product_name_mapping"),
            ([name_mapping(), name_mapping()], "duplicate_product_name_mapping"),
            ([name_mapping(), name_mapping("MOCK conflicting name")], "conflicting_product_name_mapping"),
            ([name_mapping(available="2025-12-01")], "product_name_mapping_uses_future_information"),
            ([{"key": name_mapping()["key"], "product_name": "MOCK incomplete"}], "product_name_adapter_missing_fields"),
        ):
            with self.subTest(mock_names=rows):
                h, scope, _ = scenario(name_rows=rows)
                ref = name_reference(h)
                result = calculate(h, scope, name_ref=ref, name_reader=json.loads)
                self.assertEqual(result["orders"], [])
                self.assertEqual(len(result["exceptions"]), 1)
                self.assertIn(reason, result["exceptions"][0]["reason"])
                self.assertIn(ref, result["exceptions"][0]["evidence_refs"])
                audit = json.loads(result["arithmetic_checks"][0]["actual"])
                self.assertEqual(audit["source_rows"]["names"], list(range(1, len(rows) + 1)))

    def test_unsafe_or_rewritten_names_never_enter_candidate(self):
        for name in ("", " ", " MOCK leading space", "MOCK trailing space ",
                     "MOCK\nlog", "MOCK\u202e15", "MOCK\u200bhidden", "MOCK<script>",
                     "[click](https://example.com)", "```code```", "**MOCK**", "MOCK_name"):
            with self.subTest(mock_name=name):
                h, scope, _ = scenario(name_rows=[name_mapping(name)])
                result = calculate(h, scope, name_ref=name_reference(h), name_reader=json.loads)
                self.assertEqual(result["orders"], [])
                self.assertIn("unsafe_or_empty_product_name_mapping", result["exceptions"][0]["reason"])

    def test_name_adapter_requires_paired_arguments_and_approved_reference(self):
        h, scope, _ = scenario(name_rows=[name_mapping()])
        ref = name_reference(h)
        for kwargs, reason in (
            ({"name_ref": ref}, "supplied together"),
            ({"name_reader": json.loads}, "supplied together"),
            ({"name_ref": ref, "name_reader": "not callable"}, "explicit product name reader"),
            ({"name_ref": h.one("evaluation_result")["frozen"]["model_ref"], "name_reader": json.loads}, "must bind an approved source"),
        ):
            with self.subTest(mock_args=kwargs), self.assertRaisesRegex(InputError, reason):
                calculate(h, scope, **kwargs)

    def test_wrong_name_namespace_does_not_join_into_requested_key(self):
        mapping = name_mapping()
        mapping["key"]["source_namespace"] = "mock-other-source"
        h, scope, _ = scenario(name_rows=[mapping])
        result = calculate(h, scope, name_ref=name_reference(h), name_reader=json.loads)
        self.assertEqual(result["orders"], [])
        reasons = {row["key"]["source_namespace"]: row["reason"] for row in result["exceptions"]}
        self.assertIn("missing_product_name_mapping", reasons["mock-retail"])
        self.assertIn("product_name_mapping_source_namespace_mismatch", reasons["mock-other-source"])

    def test_exact_parent_checkpoint_authentication_precedes_reading(self):
        calls = []
        h, scope, _ = scenario(parent_confirms=lambda ref, decision: False)
        original_reader = h._read_bytes
        h._read_bytes = lambda ref: (calls.append(ref), original_reader(ref))[1]
        with self.assertRaisesRegex(InputError, "unauthenticated"):
            calculate(h, scope)
        self.assertEqual(calls, [])

    def test_immutable_external_bytes_are_verified(self):
        h, scope, content = scenario()
        content["mock-stock"] += b"\n"
        with self.assertRaisesRegex(InputError, "immutable reference"):
            calculate(h, scope)

    def test_mock_handoff_requires_explicit_development_opt_in(self):
        h, _, _ = scenario()
        with self.assertRaisesRegex(InputError, "allow_mock=True"):
            Handoff(h.records, h.external_refs, h._read_bytes, h._parent_confirms)

    def test_wrong_saved_forecast_binding_invalidates_handoff(self):
        def wrong(records):
            final = next(r for r in records if r["kind"] == "final_validation_result")
            frozen = next(r for r in records if r["kind"] == "evaluation_result")["frozen"]
            final["november_30_forecast_ref"] = deepcopy(frozen["model_ref"])
        with self.assertRaisesRegex(InputError, "saved November 30 forecast changed"):
            scenario(mutate_records=wrong)

    def test_failed_validation_does_not_construct_orders_or_read_sources(self):
        def fail(records):
            final = next(r for r in records if r["kind"] == "final_validation_result")
            final["outcome"] = "fail"
            final["scores"][0]["value"] = 12
            final["parent_review"]["decision"] = "stop"
        h, scope, _ = scenario(mutate_records=fail)
        called = []
        h._read_bytes = lambda ref: called.append(ref)
        with self.assertRaisesRegex(InputError, "passed final validation"):
            calculate(h, scope)
        self.assertEqual(called, [])

    def test_partial_scope_input_becomes_key_exception_not_silent_drop(self):
        def missing_stock(args):
            args[1][0][KEY].clear()
        h, scope, _ = scenario(mutate_inputs=missing_stock)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertEqual(len(result["exceptions"]), 1)
        self.assertEqual(result["exceptions"][0]["key"]["product_id"], "MOCK-P001")
        self.assertIn("missing_or_duplicate_stock_or_policy", result["exceptions"][0]["reason"])
        self.assertEqual(result["arithmetic_checks"][0]["status"], "unavailable")

    def test_duplicate_receipt_id_withholds_every_affected_key(self):
        def duplicate(args):
            receipt = deepcopy(args[1][1][KEY][0])
            other = (KEY[0], "MOCK-OTHER", KEY[2])
            receipt[1]["Product_ID"] = other[1]
            args[1][1][other].append(receipt)
        h, scope, _ = scenario(mutate_inputs=duplicate)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertEqual(len(result["exceptions"]), 2)
        self.assertTrue(all("duplicate_or_empty_receipt_line_id" in row["reason"] for row in result["exceptions"]))

    def test_late_receipt_exception_retains_arithmetic_and_daily_shortage_evidence(self):
        def late_receipt(args):
            stock = args[1][0][KEY][0][1]
            stock.update(Usable_On_Hand_Qty="3", On_Order_Qty="8")
            args[1][2][KEY][0][1]["Safety_Stock_Qty"] = "0"
            receipt = args[1][1][KEY][0][1]
            receipt.update(Expected_Arrival_Date="2025-12-04", Incoming_Qty="8")
            for (_, forecast), quantity in zip(args[1][3][KEY], (2, 4, 1, 1)):
                forecast["quantity"] = str(quantity)
        h, scope, _ = scenario(mutate_inputs=late_receipt)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertIn("shortage: 2025-12-02", result["exceptions"][0]["reason"])
        audit = json.loads(result["arithmetic_checks"][0]["actual"])
        self.assertEqual(audit["signed_need_exact"], "-3")
        self.assertEqual(audit["rounded_order_quantity"], 0)
        self.assertEqual(audit["source_rows"]["receipts"], [2])
        self.assertEqual(audit["receipts"][0]["arrival_date"], "2025-12-04")
        self.assertEqual(audit["receipts"][0]["quantity"], 8)
        self.assertEqual(audit["daily_balances"][-1]["date"], "2025-12-02")
        self.assertEqual(audit["daily_balances"][-1]["before_arrivals"], "-3")

    def test_scope_namespace_mismatch_is_never_silently_joined(self):
        h, scope, _ = scenario()
        with self.assertRaisesRegex(InputError, "scope/source namespace mismatch"):
            calculate_candidate(h, artifact_id="mock-wrong-scope", scope_ref=scope,
                scope_reader=lambda data: [{"source_namespace": "wrong", "product_id": KEY[1], "store_id": KEY[2]}],
                forecast_reader=json.loads, source_namespace="mock-retail")

    def test_mismatched_forecast_key_preserves_both_scope_gap_and_unexpected_key(self):
        def mismatched(args):
            other = (KEY[0], "MOCK-UNREQUESTED", KEY[2])
            rows = args[1][3].pop(KEY)
            for _, row in rows:
                row["key"]["product_id"] = other[1]
            args[1][3][other] = rows
        h, scope, _ = scenario(mutate_inputs=mismatched)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        exceptions = {row["key"]["product_id"]: row["reason"] for row in result["exceptions"]}
        self.assertIn("partial_daily_forecast", exceptions["MOCK-P001"])
        self.assertIn("unexpected_key_outside_requested_scope", exceptions["MOCK-UNREQUESTED"])

    def test_scope_requires_approved_source_or_frozen_development_binding(self):
        h, _, _ = scenario()
        unapproved_scope = h.one("evaluation_result")["frozen"]["model_ref"]
        with self.assertRaisesRegex(InputError, "scope must bind"):
            calculate(h, unapproved_scope)

    def test_unknown_ledger_completeness_is_a_public_per_key_exception(self):
        def unknown(args):
            args[1][0][KEY][0][1]["Open_Order_Ledger_Complete"] = "false"
        h, scope, _ = scenario(mutate_inputs=unknown)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertEqual(len(result["exceptions"]), 1)
        self.assertIn("receipt_ledger_completeness_unknown", result["exceptions"][0]["reason"])

    def test_calendar_overflow_is_a_public_per_key_exception(self):
        def unsupported_horizon(args):
            args[1][2][KEY][0][1]["Supplier_Lead_Time_Days"] = str(10 ** 33)
        h, scope, _ = scenario(mutate_inputs=unsupported_horizon)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertEqual(len(result["exceptions"]), 1)
        self.assertIn("policy_horizon_outside_supported_calendar", result["exceptions"][0]["reason"])

    def test_excess_precision_is_a_public_exception_without_a_zero_order(self):
        def excess_precision(args):
            args[1][0][KEY][0][1].update(Usable_On_Hand_Qty="2", On_Order_Qty="0")
            args[1][1][KEY].clear()
            args[1][2][KEY][0][1]["Safety_Stock_Qty"] = "0"
            for (_, forecast), quantity in zip(args[1][3][KEY], ("1e-29", "0", "1", "1")):
                forecast["quantity"] = quantity
        h, scope, _ = scenario(mutate_inputs=excess_precision)
        result = calculate(h, scope)
        self.assertEqual(result["orders"], [])
        self.assertEqual(len(result["exceptions"]), 1)
        self.assertIn("forecast_precision_exceeds_exact_arithmetic_support", result["exceptions"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
