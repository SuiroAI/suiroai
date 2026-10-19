"""MOCK kernel verification only: no real preparation or execution acceptance.

Exercise cutoff partitioning, deduplication, target treatment, sparse dates,
and operational alignment under exact mocked execution permits.
"""
from copy import deepcopy
import unittest

from mock_data import artifact, authority, operations, packet, sale
from suiroai.preparation.worker import (SALES, PreparationError, align_operations,
    csv_bytes, encoded, partition_sales, prepare_development, sha, table)


class MockPartitionTests(unittest.TestCase):
    def partition(self, rows, *, permit=True):
        data = csv_bytes(list(SALES), rows)
        ref = artifact("raw-sales", data)
        execution, request = authority([ref])
        return partition_sales(data, ref, execution=execution, request=request, parent_permits=lambda *_: permit)

    def test_generated_18045_rows_45_exact_duplicates_are_mock_reconciliation(self):
        rows = [sale(n, Order_Date="2025-12-01" if n % 7 == 0 else "2025-11-01") for n in range(1, 18001)]
        original = deepcopy(rows)
        rows += deepcopy(rows[:45])
        result = self.partition(rows)
        counts = result["controller_audit"]["counts"]
        self.assertEqual((counts["raw_records"], counts["distinct_records"], counts["exact_duplicate_excess"]), (18045, 18000, 45))
        self.assertEqual(counts["development_raw"] + counts["reserved_raw"], 18045)
        self.assertEqual(counts["development_distinct"] + counts["reserved_distinct"], 18000)
        self.assertEqual(rows[:18000], original)
        self.assertEqual(result["controller_audit"]["raw_sha256"], sha(csv_bytes(list(SALES), rows)))
        self.assertEqual(result["development_receipt"]["development_sha256"], sha(result["development_csv"]))
        _, reserved = table(result["reserved_csv"], SALES)
        self.assertTrue(all(r["Order_Date"] >= "2025-12-01" for r in reserved))
        self.assertNotIn("reserved", str(result["development_receipt"]))

    def test_exact_identity_before_cosmetic_normalization_and_shared_order(self):
        a, b = sale(1), sale(2, Order_Status=" completed ")
        result = self.partition([a, b, deepcopy(a)])
        self.assertEqual(result["controller_audit"]["counts"]["distinct_records"], 2)
        lineage = result["controller_audit"]["row_lineage"]
        self.assertEqual([r["duplicate_of"] for r in lineage], [None, None, 1])
        self.assertEqual(lineage[0]["record_sha256"], sha(encoded([a[c] for c in SALES])))

    def test_authority_cannot_be_supplied_by_contract_contents_only(self):
        with self.assertRaisesRegex(PreparationError, "trusted parent"):
            self.partition([sale()], permit=False)

    def test_hash_mismatch_rejected_before_parsing(self):
        ref = artifact("raw-sales", b"original")
        execution, request = authority([ref])
        with self.assertRaisesRegex(PreparationError, "hash mismatch"):
            partition_sales(b"changed", ref, execution=execution, request=request, parent_permits=lambda *_: True)


class MockDevelopmentTests(unittest.TestCase):
    def prepare(self, rows=None, mutate_operations=None):
        args, _ = packet(rows, mutate_operations)
        return prepare_development(**args)

    def test_status_quantity_returns_sensitivities_and_lineage(self):
        rows = [sale(1, Quantity="3", Order_Status=" COMPLETED "),
                sale(2, Quantity="5", Return_Flag=" YES "),
                sale(3, Quantity="7", Order_Status="cAnCeLeD"),
                sale(4, Quantity="11", Order_Status="Processing"),
                sale(5, Quantity="13", Order_Status="Shipped"),
                sale(6, Quantity="0"), sale(7, Quantity="-2"),
                sale(8, Quantity="17", Order_Status="Returned"),
                sale(9, Quantity="2", Order_Date="2025-11-03", Product_Name=" mock   PRODUCT ")]
        rows.append(deepcopy(rows[0]))
        result = self.prepare(rows)
        audit = result["audit"]
        self.assertEqual(audit["distinct_development_records"], 9)
        self.assertEqual(audit["exact_duplicate_excess"], 1)
        self.assertEqual(audit["target_retained_lines"], 3)
        self.assertEqual(audit["target_excluded_lines"], 6)
        self.assertEqual(audit["development_target_quantity"], 10)
        self.assertEqual(audit["nonpositive_quantity_records"], 2)
        self.assertEqual(audit["sensitivity_units"]["completed_excluding_flagged_returns_units"], 5)
        self.assertEqual(audit["sensitivity_units"]["completed_plus_shipped_units"], 23)
        self.assertEqual(result["daily"][0]["target_source_records"], [1, 2])
        self.assertEqual(result["row_lineage"][-1]["duplicate_of"], 1)
        self.assertEqual(result["mappings"]["Product_Name"]["MOCK-P1"], "mock product")
        self.assertTrue(all(not r["complete_daily_sales"] for r in result["daily"]))
        self.assertEqual([r["Order_Date"] for r in result["daily"]], ["2025-11-01", "2025-11-03"])
        self.assertFalse(result["coverage"][0]["zero_assumption_applied"])
        self.assertEqual(audit["shared_order_ids"], 1)

    def test_december_poison_cannot_reach_development_preparation(self):
        args, _ = packet([sale()])
        columns, rows = table(args["sources"]["sales"]["data"], SALES)
        rows[0]["Order_Date"] = "2025-12-01"
        poisoned = csv_bytes(columns, rows)
        ref = artifact("development-poison", poisoned)
        args["sources"]["sales"] = {"data": poisoned, "ref": ref}
        args["request"]["released_input_refs"].append(ref)
        args["development_receipt"]["development_sha256"] = ref["sha256"]
        with self.assertRaisesRegex(PreparationError, "future/out-of-scope"):
            prepare_development(**args)

    def test_december_outcomes_do_not_change_development_values(self):
        args_a, partition_a = packet([sale(1), sale(2, Order_Date="2025-12-01", Quantity="1")])
        args_b, partition_b = packet([sale(1), sale(2, Order_Date="2025-12-01", Quantity="99999999")])
        self.assertNotEqual(partition_a["reserved_csv"], partition_b["reserved_csv"])
        self.assertEqual(partition_a["development_csv"], partition_b["development_csv"])
        result_a, result_b = prepare_development(**args_a), prepare_development(**args_b)
        for field in ("daily", "operations", "row_lineage", "quarantine", "mappings", "coverage"):
            with self.subTest(field=field):
                self.assertEqual(result_a[field], result_b[field])
        self.assertEqual(result_a["audit"]["development_target_quantity"], 3)

    def test_nonidentical_shared_transaction_id_rejected(self):
        with self.assertRaisesRegex(PreparationError, "wrong transaction grain"):
            self.prepare([sale(1), sale(1, Quantity="4")])

    def test_blank_mapping_values_preserve_unique_known_name_but_not_real_conflicts(self):
        rows = [sale(1), sale(2, Product_Name="  "), sale(3, Product_Name=" MOCK   product ")]
        result = self.prepare(rows)
        self.assertEqual(result["mappings"]["Product_Name"]["MOCK-P1"], "mock product")
        self.assertEqual(result["audit"]["missing_mapping_values"]["Product_Name"], 1)
        self.assertEqual(result["audit"]["ambiguous_mappings"]["Product_Name"], {})
        conflict = self.prepare(rows + [sale(4, Product_Name="Different mock product")])
        self.assertIsNone(conflict["mappings"]["Product_Name"]["MOCK-P1"])
        self.assertEqual(conflict["audit"]["ambiguous_mappings"]["Product_Name"]["MOCK-P1"],
                         ["different mock product", "mock product"])
        unknown = self.prepare([sale(1, Product_Name=""), sale(2, Product_Name="  ")])
        self.assertIsNone(unknown["mappings"]["Product_Name"]["MOCK-P1"])
        self.assertEqual(unknown["audit"]["missing_mapping_values"]["Product_Name"], 2)

    def test_malformed_quantities_never_inferred(self):
        for value in ("1.5", "NaN", "", " 3 ", "2e1"):
            with self.subTest(value=value), self.assertRaisesRegex(PreparationError, "integer"):
                self.prepare([sale(1, Quantity=value)])

    def test_unknown_status_and_return_are_explicit_errors(self):
        for changes in ({"Order_Status": "maybe"}, {"Return_Flag": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(PreparationError):
                self.prepare([sale(**changes)])

    def test_source_changed_after_release_is_rejected(self):
        args, _ = packet()
        args["sources"]["inventory"]["data"] += b"\n"
        with self.assertRaisesRegex(PreparationError, "hash mismatch"):
            prepare_development(**args)

    def test_unrestricted_raw_reference_in_development_release_rejected(self):
        args, _ = packet([sale(), sale(2, Order_Date="2025-12-01")])
        args["request"]["released_input_refs"].append(args["development_receipt"]["raw_ref"])
        with self.assertRaisesRegex(PreparationError, "raw"):
            prepare_development(**args)

    def test_forged_duplicate_lineage_rejected(self):
        args, _ = packet([sale(), sale(2)])
        columns, rows = table(args["sources"]["sales"]["data"], SALES)
        rows[1]["_duplicate_of"] = "1"
        changed = csv_bytes(columns, rows)
        ref = artifact("mock-forged-lineage", changed)
        args["sources"]["sales"] = {"data": changed, "ref": ref}
        args["request"]["released_input_refs"].append(ref)
        args["development_receipt"]["development_sha256"] = sha(changed)
        with self.assertRaisesRegex(PreparationError, "duplicate lineage"):
            prepare_development(**args)


class MockOperationsTests(unittest.TestCase):
    def align(self, inv=None, receipts=None, policy=None, ledger="complete_synthetic_ledger_absence_is_zero"):
        defaults = operations()
        return align_operations(defaults[0] if inv is None else inv, defaults[1] if receipts is None else receipts,
                                defaults[2] if policy is None else policy, {("MOCK-P1", "MOCK-S1")}, ledger)

    def test_many_receipt_lines_aggregate_once_and_preserve_due_dates(self):
        aligned, lineage, audit = self.align()
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["reconciled_on_order_qty"], 7)
        self.assertEqual(len(aligned[0]["inbound_lines"]), 2)
        self.assertEqual(lineage[0]["receipt_records"], [1, 2])
        self.assertEqual(audit["row_multiplier"], 1)

    def test_zero_open_orders_requires_explicit_complete_ledger(self):
        inv, _, _ = operations()
        inv[0]["On_Order_Qty"] = "0"
        aligned, _, audit = self.align(inv=inv, receipts=[])
        self.assertEqual(aligned[0]["reconciled_on_order_qty"], 0)
        self.assertEqual(audit["keys_explicitly_without_open_orders"], 1)
        inv[0]["Open_Order_Ledger_Complete"] = "False"
        with self.assertRaisesRegex(PreparationError, "absence is unknown"):
            self.align(inv=inv, receipts=[])

    def test_duplicate_keys_and_coverage_rejected(self):
        inv, _, policy = operations()
        for kwargs in ({"inv": inv + deepcopy(inv)}, {"policy": policy + deepcopy(policy)}, {"inv": []}, {"policy": []}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PreparationError):
                self.align(**kwargs)

    def test_units_asof_receipt_identity_summary_and_lead_time_fail_closed(self):
        mutations = [lambda a,b,c: a[0].update(Quantity_Unit="cases"),
                     lambda a,b,c: a[0].update(Snapshot_Date="2025-11-29"),
                     lambda a,b,c: c[0].update(Effective_Date="2025-12-01"),
                     lambda a,b,c: b[0].update(Order_Date="2025-12-01"),
                     lambda a,b,c: b[0].update(Expected_Arrival_Date="2025-11-30"),
                     lambda a,b,c: b[0].update(PO_Line_ID=b[1]["PO_Line_ID"]),
                     lambda a,b,c: b[0].update(Incoming_Qty="0"),
                     lambda a,b,c: a[0].update(On_Order_Qty="14"),
                     lambda a,b,c: c[0].update(Supplier_Lead_Time_Days="8"),
                     lambda a,b,c: c[0].update(Minimum_Order_Qty="3"),
                     lambda a,b,c: b[0].update(Product_ID="MOCK-UNKNOWN")]
        for mutate in mutations:
            inv, receipts, policy = operations()
            mutate(inv, receipts, policy)
            with self.subTest(mutation=mutations.index(mutate)), self.assertRaises(PreparationError):
                self.align(inv, receipts, policy)


if __name__ == "__main__":
    unittest.main()
