"""Independent hand-calculated MOCK examples; no customer-run acceptance evidence.

Compare independent source reconciliation with hand-calculated orders,
including receipt timing, coverage gaps, minimums, and order multiples.

Requirement context for these component checks:
Recompute candidate quantities against frozen forecasts, usable stock, timely
receipts, units, dates, and purchasing constraints; expose unsupported keys
rather than hiding exceptions or counting the receipt summary twice.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""
from __future__ import annotations

import copy
import unittest

from suiroai.verification.arithmetic import reconcile_orders


KEY = {"source_namespace": "mock-retail", "product_id": "P001", "store_id": "S01"}
EVIDENCE = {"artifact_id": "mock-source-stock", "version": 1, "sha256": "0" * 64, "provenance": "mock"}


def example():
    raw = {"source_namespace": "mock-retail", "Product_ID": "P001", "Store_ID": "S01",
           "Quantity_Unit": "product_unit", "Provenance": "mock"}
    forecast = [{"key": KEY, "date": f"2025-12-0{i}", "quantity": q,
                 "quantity_unit": "product_unit", "as_of_date": "2025-11-30",
                 "latest_information_available_date": "2025-11-30"}
                for i, q in enumerate([2, 3, 4, 1], 1)]
    order = {"key": KEY, "product_name": "Mock chair", "quantity_unit": "product_unit",
             "forecast_horizon_start": "2025-12-01", "forecast_horizon_end": "2025-12-04",
             "forecast_quantity": 10, "usable_on_hand_quantity": 5,
             "on_order_summary_quantity": 2, "eligible_receipt_quantity": 2,
             "supplier_lead_calendar_days": 2, "review_period_calendar_days": 2,
             "safety_stock_quantity": 2, "order_multiple": 4,
             "minimum_positive_order_quantity": 5, "raw_order_need": 5,
             "rounded_order_quantity": 8, "approved_order_quantity": 8}
    inputs = {"scope_keys": [KEY], "forecast_rows": forecast,
              "inventory_rows": [{**raw, "Snapshot_Date": "2025-11-30",
                                  "Usable_On_Hand_Qty": 5, "On_Order_Qty": 2,
                                  "Open_Order_Ledger_Complete": "true"}],
              "receipt_rows": [{**raw, "PO_Line_ID": "MOCK-PO-1", "Order_Date": "2025-11-29",
                                "Expected_Arrival_Date": "2025-12-02", "Incoming_Qty": 2}],
              "policy_rows": [{**raw, "Effective_Date": "2025-11-30",
                               "Supplier_Lead_Time_Days": 2, "Review_Period_Days": 2,
                               "Order_Multiple_Qty": 4, "Minimum_Order_Qty": 5,
                               "Safety_Stock_Qty": 2}],
              "name_rows": [{"key": KEY, "product_name": "Mock chair",
                             "latest_information_available_date": "2025-11-30"}],
              "ledger_complete": True}
    return [order], [], inputs


class ReconcileOrdersTests(unittest.TestCase):
    def run_case(self, mutate=None, **extra):
        orders, exceptions, inputs = example()
        if mutate:
            mutate(orders, exceptions, inputs)
        return reconcile_orders(orders, exceptions, **inputs, **extra)

    def assert_pass(self, result):
        self.assertEqual([], result["exceptions"])
        self.assertTrue(result["checks"])
        self.assertTrue(all(c["status"] == "pass" for c in result["checks"]), result["checks"])

    def assert_reason(self, result, reason):
        self.assertTrue(any(reason in e["reason"] for e in result["exceptions"]), result)
        self.assertEqual([], result["expected_orders"])

    def test_independent_integer_arithmetic_and_summary_counted_once(self):
        # 2+3+4+1 demand +2 safety -5 stock -2 incoming =5; ceil(5/4)*4=8.
        result = self.run_case()
        self.assert_pass(result)
        self.assertEqual("5", result["expected_orders"][0]["raw_order_need"])
        self.assertEqual("8", result["expected_orders"][0]["rounded_order_quantity"])

    def test_producer_pass_flag_is_not_evidence(self):
        def change(o, e, i):
            o[0].update(rounded_order_quantity=4, approved_order_quantity=4, passed=True)
        result = self.run_case(change)
        self.assertTrue(any(c["check_id"] == "rounded_order_quantity" and c["status"] == "fail" for c in result["checks"]))

    def test_every_intermediate_and_name_are_compared(self):
        for field, wrong in [("forecast_quantity", 9), ("eligible_receipt_quantity", 4),
                             ("raw_order_need", 3), ("forecast_horizon_end", "2025-12-05"),
                             ("product_name", "Wrong product"), ("quantity_unit", "case")]:
            with self.subTest(field=field):
                result = self.run_case(lambda o, e, i: o[0].update({field: wrong}))
                self.assertTrue(any(c["check_id"] == field and c["status"] == "fail" for c in result["checks"]))

    def test_zero_clamp_does_not_trigger_minimum(self):
        def change(o, e, i):
            i["inventory_rows"][0]["Usable_On_Hand_Qty"] = 20
            o[0].update(usable_on_hand_quantity=20, raw_order_need=0,
                        rounded_order_quantity=0, approved_order_quantity=0)
        result = self.run_case(change)
        self.assert_pass(result)
        self.assertEqual("0", result["expected_orders"][0]["rounded_order_quantity"])

    def test_minimum_then_multiple_and_fractional_forecast(self):
        def change(o, e, i):
            i["forecast_rows"][3]["quantity"] = "0.1"
            o[0].update(forecast_quantity="9.1", raw_order_need="4.1")
        result = self.run_case(change)
        self.assert_pass(result)
        self.assertEqual("8", result["expected_orders"][0]["rounded_order_quantity"])

    def test_candidate_without_parent_approval_is_arithmetically_checkable(self):
        self.assert_pass(self.run_case(lambda o, e, i: o[0].update(approved_order_quantity=None)))

    def test_numeric_candidate_may_omit_names_but_final_report_requires_them(self):
        def change(o, e, i):
            o[0].pop("product_name")
            i["name_rows"] = []
        result = self.run_case(change, require_product_names=False)
        self.assert_pass(result)
        self.assertNotIn("product_name", result["expected_orders"][0])
        self.assert_reason(self.run_case(change), "missing_or_duplicate_inventory_policy_or_name")

    def test_numeric_candidate_supplied_name_still_needs_independent_mapping(self):
        self.assert_reason(self.run_case(lambda o, e, i: i.update(name_rows=[]),
                                        require_product_names=False), "missing_or_duplicate_inventory_policy_or_name")
        result = self.run_case(lambda o, e, i: o[0].update(product_name="Invented name"),
                               require_product_names=False)
        self.assertTrue(any(c["check_id"] == "product_name" and c["status"] == "fail" for c in result["checks"]))

    def test_numeric_candidate_null_name_is_unbound_but_final_still_needs_mapping(self):
        def change(o, e, i):
            o[0]["product_name"] = None
            i["name_rows"] = []
        self.assert_pass(self.run_case(change, require_product_names=False))
        self.assert_reason(self.run_case(change), "missing_or_duplicate_inventory_policy_or_name")

    def test_optional_names_still_validate_any_provided_source_mapping(self):
        def change(o, e, i):
            o[0].pop("product_name")
            i["name_rows"][0]["latest_information_available_date"] = "2025-12-01"
        self.assert_reason(self.run_case(change, require_product_names=False), "name_not_available_as_of")

    def test_missing_daily_forecast_is_not_zero(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["forecast_rows"].pop(1)), "incomplete_daily_forecast")

    def test_duplicate_daily_forecast_is_rejected(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["forecast_rows"].append(copy.deepcopy(i["forecast_rows"][0]))), "duplicate_forecast_date")

    def test_large_policy_horizon_with_only_short_forecast_is_incomplete(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["policy_rows"][0].update(Supplier_Lead_Time_Days=1_000_000)), "incomplete_daily_forecast")

    def test_nonfinite_negative_and_wrong_unit_inputs(self):
        for invalid in ("NaN", "Infinity", "-1", True):
            with self.subTest(invalid=invalid):
                self.assert_reason(self.run_case(lambda o, e, i: i["forecast_rows"][0].update(quantity=invalid)), "quantity must")
        self.assert_reason(self.run_case(lambda o, e, i: i["inventory_rows"][0].update(Quantity_Unit="case")), "unit_mismatch")

    def test_stale_stock_and_future_information_are_explicit(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["inventory_rows"][0].update(Snapshot_Date="2025-11-29")), "stale_or_future_stock")
        self.assert_reason(self.run_case(lambda o, e, i: i["forecast_rows"][0].update(latest_information_available_date="2025-12-01")), "forecast_stale_or_future")
        self.assert_reason(self.run_case(lambda o, e, i: i["name_rows"][0].update(latest_information_available_date="2025-12-01")), "name_not_available")

    def test_missing_provenance_and_incomplete_ledger(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["policy_rows"][0].pop("Provenance")), "missing_provenance")
        self.assert_reason(self.run_case(lambda o, e, i: i["policy_rows"][0].update(Provenance="SYNTHETIC")), "invalid_provenance")
        self.assert_reason(self.run_case(lambda o, e, i: i["policy_rows"][0].update(Provenance="supplied")), "not_labeled_synthetic")
        self.assert_reason(self.run_case(lambda o, e, i: i.update(ledger_complete=False)), "ledger_not_explicitly_complete")
        self.assert_reason(self.run_case(lambda o, e, i: i["inventory_rows"][0].update(Open_Order_Ledger_Complete=False)), "ledger_not_explicitly_complete")

    def test_zero_open_order_requires_explicit_complete_ledger(self):
        def change(o, e, i):
            i["receipt_rows"] = []
            i["inventory_rows"][0]["On_Order_Qty"] = 0
            o[0].update(on_order_summary_quantity=0, eligible_receipt_quantity=0, raw_order_need=7)
        self.assert_pass(self.run_case(change))

    def test_summary_reconciles_even_receipts_after_horizon(self):
        def change(o, e, i):
            i["receipt_rows"][0]["Expected_Arrival_Date"] = "2025-12-05"
            o[0].update(eligible_receipt_quantity=0, raw_order_need=7)
        self.assert_pass(self.run_case(change))
        self.assert_reason(self.run_case(lambda o, e, i: i["inventory_rows"][0].update(On_Order_Qty=3)), "summary_does_not_reconcile")

    def test_duplicate_po_line_and_future_created_order(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["receipt_rows"].append(copy.deepcopy(i["receipt_rows"][0]))), "duplicate_po_line_id")
        self.assert_reason(self.run_case(lambda o, e, i: i["receipt_rows"][0].update(PO_Line_ID=[])), "duplicate_po_line_id")
        self.assert_reason(self.run_case(lambda o, e, i: i["receipt_rows"][0].update(Order_Date="2025-12-01")), "receipt_dates_not_open")

    def test_lead_time_shortage_cannot_be_repaired_by_recommendation(self):
        self.assert_reason(self.run_case(lambda o, e, i: i["inventory_rows"][0].update(Usable_On_Hand_Qty=0)), "timing_shortage_on_2025-12-01")

    def test_late_receipt_cannot_cover_earlier_shortage(self):
        def change(o, e, i):
            i["policy_rows"][0].update(Supplier_Lead_Time_Days=1, Review_Period_Days=3,
                                       Safety_Stock_Qty=0, Minimum_Order_Qty=1, Order_Multiple_Qty=1)
            i["inventory_rows"][0].update(Usable_On_Hand_Qty=0, On_Order_Qty=8)
            i["receipt_rows"][0].update(Incoming_Qty=8, Expected_Arrival_Date="2025-12-04")
            for row, q in zip(i["forecast_rows"], [8, 0, 0, 2]):
                row["quantity"] = q
        # Net need 10-8=2 arrives day1, but cannot cover 8 demand before day4 receipt.
        self.assert_reason(self.run_case(change, receipt_timing="before_daily_demand"), "timing_shortage_on_2025-12-01")

    def test_same_day_arrival_needs_explicit_convention(self):
        def change(o, e, i):
            i["inventory_rows"][0]["Usable_On_Hand_Qty"] = 4
            o[0].update(usable_on_hand_quantity=4, raw_order_need=6)
        self.assert_reason(self.run_case(change), "timing_ambiguity_on_2025-12-02")
        self.assert_pass(self.run_case(change, receipt_timing="before_daily_demand"))

    def test_key_identity_is_exact_and_namespace_never_inferred(self):
        for field, wrong in [("source_namespace", "other"), ("Product_ID", "p001"), ("Product_ID", 1), ("Store_ID", "S01 ")]:
            with self.subTest(field=field, wrong=wrong):
                result = self.run_case(lambda o, e, i: i["inventory_rows"][0].update({field: wrong}))
                self.assertTrue(any(c["status"] == "fail" for c in result["checks"]))
                self.assertEqual([], result["expected_orders"])

    def test_cross_store_conflicting_product_names_withholds_every_affected_key(self):
        orders, exceptions, inputs = example()
        other_orders, _, other_inputs = copy.deepcopy(example())
        other_key = {**KEY, "store_id": "S02"}
        for label, rows in other_inputs.items():
            if isinstance(rows, list):
                for row in rows:
                    if "key" in row:
                        row["key"] = other_key
                    elif "Store_ID" in row:
                        row["Store_ID"] = "S02"
                    else:
                        row.update(other_key)
                    if "PO_Line_ID" in row:
                        row["PO_Line_ID"] = "MOCK-PO-2"
        other_orders[0].update(key=other_key, product_name="Conflicting mock table")
        other_inputs["name_rows"][0]["product_name"] = "Conflicting mock table"
        for label, rows in other_inputs.items():
            if isinstance(rows, list):
                inputs[label].extend(rows)
        result = reconcile_orders(orders + other_orders, exceptions, **inputs)
        self.assertEqual([], result["expected_orders"])
        conflicts = [item for item in result["exceptions"]
                     if item["reason"] == "conflicting_product_names_across_stores"]
        self.assertEqual([KEY, other_key], [item["key"] for item in conflicts])

    def test_missing_order_and_order_exception_overlap_are_detected(self):
        result = self.run_case(lambda o, e, i: o.clear())
        self.assertTrue(any(c["check_id"] == "key_output_coverage" and c["status"] == "fail" for c in result["checks"]))
        result = self.run_case(lambda o, e, i: e.append({"key": KEY, "reason": "mock exception"}))
        self.assertTrue(any(c["check_id"] == "key_output_identity" and c["status"] == "fail" for c in result["checks"]))

    def test_honest_exception_retained_without_any_expected_order(self):
        def change(o, e, i):
            o.clear()
            e.append({"key": KEY, "reason": "stale snapshot; refresh required", "evidence_refs": [EVIDENCE]})
            i["inventory_rows"][0]["Snapshot_Date"] = "2025-11-29"
        result = self.run_case(change)
        self.assert_reason(result, "stale_or_future_stock")
        self.assertTrue(all(c["status"] == "pass" for c in result["checks"]))
        self.assertTrue(any(c["check_id"] == "unresolved_exception_reported" and c["status"] == "pass" for c in result["checks"]))

    def test_missing_exception_evidence_or_recommendation_despite_gap_fails(self):
        for refs in (None, [], [None], [{**EVIDENCE, "provenance": "guessed"}], [{**EVIDENCE, "provenance": []}]):
            with self.subTest(refs=refs):
                def change(o, e, i):
                    o.clear()
                    e.append({"key": KEY, "reason": "stale snapshot", "evidence_refs": refs})
                    i["inventory_rows"][0]["Snapshot_Date"] = "2025-11-29"
                result = self.run_case(change)
                self.assertTrue(any(c["check_id"] == "source_reconciliation" and c["status"] == "fail" for c in result["checks"]))
        def change(o, e, i):
            e.append({"key": KEY, "reason": "stale snapshot", "evidence_refs": [EVIDENCE]})
            i["inventory_rows"][0]["Snapshot_Date"] = "2025-11-29"
        result = self.run_case(change)
        self.assertTrue(any(c["check_id"] == "source_reconciliation" and c["status"] == "fail" for c in result["checks"]))

    def test_partial_report_retains_evidenced_gap_and_other_verified_key(self):
        orders, exceptions, inputs = example()
        other_orders, _, other_inputs = copy.deepcopy(example())
        other_key = {**KEY, "product_id": "P002"}
        for label, rows in other_inputs.items():
            if isinstance(rows, list):
                for row in rows:
                    if "key" in row:
                        row["key"] = other_key
                    elif "Product_ID" in row:
                        row["Product_ID"] = "P002"
                    else:
                        row.update(other_key)
                    if "PO_Line_ID" in row:
                        row["PO_Line_ID"] = "MOCK-PO-2"
        other_orders[0]["key"] = other_key
        for label, rows in other_inputs.items():
            if isinstance(rows, list):
                inputs[label].extend(rows)
        inputs["inventory_rows"][0]["Snapshot_Date"] = "2025-11-29"
        exceptions.append({"key": KEY, "reason": "stale stock snapshot; refresh required", "evidence_refs": [EVIDENCE]})
        result = reconcile_orders(other_orders, exceptions, **inputs)
        self.assertTrue(all(c["status"] == "pass" for c in result["checks"]), result)
        self.assertEqual([other_key], [o["key"] for o in result["expected_orders"]])
        self.assertEqual(KEY, result["exceptions"][0]["key"])


if __name__ == "__main__":
    unittest.main()
