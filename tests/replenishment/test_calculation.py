"""Independent DSC-29 MOCK examples; no genuine model/integration acceptance.

Expected numbers below were calculated by hand from the displayed inputs. The
producer under test is never used to derive an expected quantity.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import localcontext
import unittest

from suiroai.replenishment.calculation import _calculate_key, _csv, STOCK_FIELDS
from suiroai.replenishment.context import InputError


AS_OF = date(2025, 11, 30)
KEY = ("mock-retail", "MOCK-P001", "MOCK-STORE")


def inputs(*, demands=(1, 1, 4, 4), usable=4, safety=2, minimum=1,
           multiple=1, receipts=(), complete="true", key=KEY):
    """Normalized adapter data only; all operational rows explicitly synthetic."""
    refs = [{"artifact_id": label, "version": 1, "sha256": "0" * 64,
             "provenance": "mock"} for label in ("forecast", "stock", "receipts", "policy")]
    stock = {"Product_ID": key[1], "Store_ID": key[2], "Snapshot_Date": "2025-11-30",
             "Usable_On_Hand_Qty": str(usable), "On_Order_Qty": str(sum(q for _, q in receipts)),
             "Open_Order_Ledger_Complete": complete, "Quantity_Unit": "product_unit",
             "Provenance": "synthetic"}
    policy = {"Product_ID": key[1], "Store_ID": key[2], "Effective_Date": "2025-11-30",
              "Supplier_Lead_Time_Days": "2", "Review_Period_Days": "2",
              "Order_Multiple_Qty": str(multiple), "Minimum_Order_Qty": str(minimum),
              "Safety_Stock_Qty": str(safety), "Quantity_Unit": "product_unit",
              "Provenance": "synthetic"}
    ledger = [{"PO_Line_ID": f"MOCK-LINE-{i}", "Product_ID": key[1], "Store_ID": key[2],
               "Order_Date": "2025-11-29", "Expected_Arrival_Date": (AS_OF + timedelta(days=day)).isoformat(),
               "Incoming_Qty": str(q), "Quantity_Unit": "product_unit", "Provenance": "synthetic"}
              for i, (day, q) in enumerate(receipts)]
    forecast = [{"key": dict(zip(("source_namespace", "product_id", "store_id"), key)),
                 "date": (AS_OF + timedelta(days=i)).isoformat(), "quantity": str(q),
                 "quantity_unit": "product_unit", "as_of_date": "2025-11-30",
                 "latest_information_available_date": "2025-11-30"}
                for i, q in enumerate(demands, 1)]
    indexed = [defaultdict(list) for _ in range(4)]
    for index, rows in zip(indexed, ([stock], ledger, [policy], forecast)):
        index[key] = list(enumerate(rows, 2))
    execution = {"inbound_ledger_policy": "complete_synthetic_ledger_absence_is_zero",
                 "synthetic_operational_source_refs": deepcopy(refs[1:])}
    return key, indexed, execution, AS_OF, refs[0], refs


class IndependentArithmeticExamples(unittest.TestCase):
    def test_zero_need_does_not_trigger_positive_minimum(self):
        row, audit = _calculate_key(*inputs(usable=20, safety=2, minimum=100, multiple=12))
        # 10 + 2 - 20 - 0 = -8; clamp to 0, positive-only minimum never applies.
        self.assertEqual(row["raw_order_need"], 0)
        self.assertEqual(row["rounded_order_quantity"], 0)
        self.assertEqual(audit["signed_need_exact"], "-8")
        self.assertIsNone(row["approved_order_quantity"])

    def test_positive_minimum_then_multiple(self):
        row, audit = _calculate_key(*inputs(demands=("0.5", "0.5", 1, 2),
                                            usable=3, safety=0, minimum=7, multiple=5))
        # 4 - 3 = 1; max(1,7)=7; next multiple of 5 is 10.
        self.assertEqual(row["raw_order_need"], 1)
        self.assertEqual(row["rounded_order_quantity"], 10)
        self.assertEqual(audit["candidate_arrival_date"], "2025-12-02")
        self.assertEqual(row["forecast_horizon_start"], "2025-12-01")
        self.assertEqual(row["forecast_horizon_end"], "2025-12-04")

    def test_decimal_boundary_uses_exact_sum_before_rounding(self):
        row, audit = _calculate_key(*inputs(demands=("0.1", "0.2", "1.1", "1.6"),
                                            usable=1, safety=0))
        # 0.1+0.2+1.1+1.6 = exactly 3.0; need=2.0, so order exactly 2.
        self.assertEqual(audit["forecast_quantity_exact"], "3.0")
        self.assertEqual(audit["raw_order_need_exact"], "2.0")
        self.assertEqual(row["rounded_order_quantity"], 2)

    def test_unrepresentable_decimal_boundary_is_withheld(self):
        # Need=2.0000000000000001 would round to 3. The shared JSON numeric
        # contract cannot preserve this input; silently turning it into 2 is forbidden.
        with self.assertRaisesRegex(InputError, "precision_not_representable"):
            _calculate_key(*inputs(demands=("0.1", "0.2", "1.1", "1.6000000000000001"),
                                   usable=1, safety=0))

    def test_tiny_positive_need_is_never_silently_erased_by_precision(self):
        # Forecast=2+10^-29 and stock=2 leaves positive need=10^-29,
        # requiring one unit mathematically. Exact support is bounded; withhold
        # instead of reporting a fictitious zero need after Decimal rounding.
        with self.assertRaisesRegex(InputError, "forecast_precision_exceeds_exact_arithmetic_support"):
            _calculate_key(*inputs(demands=("1e-29", 0, 1, 1), usable=2, safety=0))

    def test_just_above_multiple_rounds_up_independent_of_ambient_precision(self):
        # 6.000000000000001 / 3 is just above 2 packs, so order 3 packs=9.
        # No demand precedes the supplier arrival. Final stock is exactly
        # 9-6.000000000000001=2.999999999999999, even in a low precision caller.
        with localcontext() as context:
            context.prec = 2
            row, audit = _calculate_key(*inputs(demands=(0, 0, 0, "6.000000000000001"),
                                                usable=0, safety=0, multiple=3))
        self.assertEqual(row["rounded_order_quantity"], 9)
        self.assertEqual(audit["raw_order_need_exact"], "6.000000000000001")
        self.assertEqual(audit["daily_balances"][-1]["closing"], "2.999999999999999")

    def test_unsupported_policy_calendar_horizon_is_an_input_exception(self):
        args = inputs()
        args[1][2][KEY][0][1]["Supplier_Lead_Time_Days"] = str(10 ** 33)
        with self.assertRaisesRegex(InputError, "policy_horizon_outside_supported_calendar"):
            _calculate_key(*args)

    def test_receipt_ledger_summary_is_not_second_supply(self):
        row, audit = _calculate_key(*inputs(receipts=((2, 3),)))
        # 10 + 2 - 4 - 3 = 5, rather than the double-subtracted result 2.
        self.assertEqual(row["on_order_summary_quantity"], 3)
        self.assertEqual(row["eligible_receipt_quantity"], 3)
        self.assertEqual(row["raw_order_need"], 5)
        self.assertEqual(row["rounded_order_quantity"], 5)
        self.assertIs(audit["summary_subtracted"], False)
        self.assertEqual(audit["ledger_total_quantity"], 3)
        self.assertEqual(audit["daily_balances"][-1]["closing"], "2")

    def test_after_horizon_receipt_reconciles_summary_but_cannot_reduce_need(self):
        row, audit = _calculate_key(*inputs(receipts=((5, 3),)))
        # Dec 5 is outside Dec 1-4 protection horizon: 10+2-4-0=8.
        self.assertEqual(row["on_order_summary_quantity"], 3)
        self.assertEqual(row["eligible_receipt_quantity"], 0)
        self.assertEqual(row["rounded_order_quantity"], 8)
        self.assertEqual(audit["outside_horizon_receipt_quantity"], 3)
        self.assertFalse(audit["receipts"][0]["within_horizon"])

    def test_late_receipt_cannot_cure_earlier_shortage(self):
        # Total demand=8, usable=3, Dec 4 receipt=8 means aggregate need=0;
        # Dec 2 demand=4 exceeds the remaining 1 before that later delivery.
        with self.assertRaisesRegex(InputError, r"shortage: 2025-12-02"):
            _calculate_key(*inputs(demands=(2, 4, 1, 1), usable=3, safety=0,
                                   receipts=((4, 8),)))

    def test_same_day_recovery_is_withheld_for_timing_ambiguity(self):
        with self.assertRaisesRegex(InputError, r"timing_ambiguity: 2025-12-02"):
            _calculate_key(*inputs(demands=(2, 4, 1, 1), usable=3, safety=0,
                                   receipts=((2, 8),)))

    def test_new_purchase_cannot_cure_demand_before_supplier_arrival(self):
        with self.assertRaisesRegex(InputError, r"shortage: 2025-12-01"):
            _calculate_key(*inputs(demands=(4, 1, 1, 1), usable=3, safety=0))

    def test_210_absent_ledger_keys_are_zero_only_under_complete_contract(self):
        for i in range(210):
            key = ("mock-retail", f"MOCK-P{i:03}", "MOCK-STORE")
            with self.subTest(mock_key=key):
                row, audit = _calculate_key(*inputs(key=key))
                self.assertEqual(row["rounded_order_quantity"], 8)
                self.assertEqual(audit["ledger_total_quantity"], 0)
                self.assertEqual(audit["receipts"], [])
                with self.assertRaisesRegex(InputError, "receipt_ledger_completeness_unknown"):
                    _calculate_key(*inputs(key=key, complete="false"))

    def test_input_gaps_and_mismatches_are_explicit_errors(self):
        cases = {
            "missing_stock": (lambda a: a[1][0][KEY].clear(), "missing_or_duplicate_stock_or_policy"),
            "duplicate_stock": (lambda a: a[1][0][KEY].append(deepcopy(a[1][0][KEY][0])), "missing_or_duplicate_stock_or_policy"),
            "missing_policy": (lambda a: a[1][2][KEY].clear(), "missing_or_duplicate_stock_or_policy"),
            "duplicate_policy": (lambda a: a[1][2][KEY].append(deepcopy(a[1][2][KEY][0])), "missing_or_duplicate_stock_or_policy"),
            "stale_stock": (lambda a: a[1][0][KEY][0][1].update(Snapshot_Date="2025-11-29"), "stale_or_future_stock_or_policy"),
            "future_policy": (lambda a: a[1][2][KEY][0][1].update(Effective_Date="2025-12-01"), "stale_or_future_stock_or_policy"),
            "stock_unit": (lambda a: a[1][0][KEY][0][1].update(Quantity_Unit="case"), "incompatible_quantity_unit"),
            "policy_provenance": (lambda a: a[1][2][KEY][0][1].update(Provenance="supplied"), "declared_synthetic"),
            "partial_forecast": (lambda a: a[1][3][KEY].pop(), "partial_daily_forecast"),
            "duplicate_forecast": (lambda a: a[1][3][KEY].append(deepcopy(a[1][3][KEY][0])), "duplicate_daily_forecast"),
            "forecast_unit": (lambda a: a[1][3][KEY][0][1].update(quantity_unit="case"), "incompatible_forecast_unit"),
            "forecast_future": (lambda a: a[1][3][KEY][0][1].update(latest_information_available_date="2025-12-01"), "forecast_not_frozen"),
            "forecast_asof": (lambda a: a[1][3][KEY][0][1].update(as_of_date="2025-11-29"), "forecast_not_frozen"),
            "receipt_summary": (lambda a: a[1][0][KEY][0][1].update(On_Order_Qty="7"), "receipt_summary_mismatch"),
            "undeclared_synthetic": (lambda a: a[2].update(synthetic_operational_source_refs=[]), "operational_sources_not_declared_synthetic"),
            "unknown_ledger_policy": (lambda a: a[2].update(inbound_ledger_policy="unknown"), "receipt_ledger_completeness_unknown"),
        }
        for name, (mutate, fragment) in cases.items():
            with self.subTest(mock_case=name):
                args = inputs()
                mutate(args)
                with self.assertRaisesRegex(InputError, fragment):
                    _calculate_key(*args)

    def test_bad_receipt_rows_do_not_become_eligible_supply(self):
        for changes, fragment in (
            ({"Order_Date": "2025-12-01"}, "future_order_or_overdue"),
            ({"Expected_Arrival_Date": "2025-11-30"}, "future_order_or_overdue"),
            ({"Quantity_Unit": "case"}, "incompatible_quantity_unit"),
            ({"Provenance": "unknown"}, "declared_synthetic"),
            ({"Incoming_Qty": "1.5"}, "integer quantity"),
        ):
            args = inputs(receipts=((2, 3),))
            args[1][1][KEY][0][1].update(changes)
            with self.subTest(mock_changes=changes), self.assertRaisesRegex(InputError, fragment):
                _calculate_key(*args)

    def test_nonfinite_negative_boolean_forecasts_and_invalid_policy_rejected(self):
        for value in ("NaN", "Infinity", "-1", True):
            args = inputs()
            args[1][3][KEY][0][1]["quantity"] = value
            with self.subTest(mock_forecast=value), self.assertRaises(InputError):
                _calculate_key(*args)
        for field in ("Supplier_Lead_Time_Days", "Review_Period_Days", "Minimum_Order_Qty", "Order_Multiple_Qty"):
            args = inputs()
            args[1][2][KEY][0][1][field] = "0"
            with self.subTest(mock_policy=field), self.assertRaises(InputError):
                _calculate_key(*args)

    def test_malformed_csv_headers_and_rows_fail_loudly(self):
        for blob in (b"a,a\n1,2\n", b"Product_ID\nP\n", b"a,b\n1,2,3\n", b"\xff"):
            with self.subTest(mock_bytes=blob), self.assertRaises(InputError):
                _csv(blob, STOCK_FIELDS)


if __name__ == "__main__":
    unittest.main()
