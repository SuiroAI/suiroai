"""Actual DSC-27 implementation -> DSC-28 consumer, on explicit MOCK CSVs.

This exercises genuine component code, not native Data execution, customer data,
complete sales coverage or approval of the blocked derived-source release path.

Requirement context for these component checks:
Connect safe preparation to evaluation without deriving daily completeness
from sparse observations, and exclude development target horizons that cross
into the reserved December holdout.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from copy import deepcopy
from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from suiroai.integration.artifacts import ArtifactStore
from suiroai.modeling.core import ModelingError, Window
from suiroai.modeling.prepared import DailyView, build_examples, read_development
from suiroai.preparation import build_result, prepare_development
from suiroai.preparation.features import FEATURE_NAMES
from suiroai.preparation.worker import PreparationError, encoded

# Reuse the DSC-27 owner's explicit mock source/authority generator read-only.
_fixture_path = Path(__file__).resolve().parents[1] / "preparation/mock_data.py"
_fixture_spec = importlib.util.spec_from_file_location("dsc28_preparation_consumer_mock_sources", _fixture_path)
_mock = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_mock)


class RecordingStore:
    def __init__(self, store):
        self.store = store
        self.reads = []

    def read_bytes(self, ref):
        self.reads.append(deepcopy(ref))
        return self.store.read_bytes(ref)


class PreparationConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.store = ArtifactStore(self.temp.name)

    def handoff(self, *, future_quantity="987654321", suffix=""):
        rows = [_mock.sale(1, Order_Date="2025-10-30", Quantity="2"),
                _mock.sale(2, Order_Date="2025-10-31", Quantity="4"),
                _mock.sale(3, Order_Date="2025-11-01", Quantity="6"),
                _mock.sale(4, Order_Date="2025-12-20", Quantity=future_quantity)]
        args, partition = _mock.packet(rows)
        prepared = prepare_development(**args)
        reserved = _mock.artifact("consumer-reserved"+suffix, partition["reserved_csv"])
        audit = _mock.artifact("consumer-controller-audit"+suffix, encoded(partition["controller_audit"]))
        decision = deepcopy(args["request"]["parent_authorization"])
        result = build_result(prepared, execution=args["execution"], request=args["request"],
            reserved_ref=reserved, reserved_receipt=partition["reserved_receipt"], partition_audit_ref=audit,
            parent_decision=decision)
        return args, partition, prepared, result

    def import_bytes(self, result):
        for artifact in result["artifacts"]:
            ref = artifact["ref"]
            if artifact["encoding"] == "bytes":
                measured = self.store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], artifact["data"])
                self.assertEqual(measured, ref)

    @staticmethod
    def features(result):
        ref = result["record"]["initial_feature_set_ref"]
        return json.loads(next(a["data"] for a in result["artifacts"] if a["ref"] == ref))

    def test_actual_prepared_result_reads_only_approved_development_bytes(self):
        args, _, prepared, result = self.handoff()
        self.import_bytes(result)
        tracked = RecordingStore(self.store)
        view = read_development(tracked, result["record"], args["execution"])
        self.assertEqual(tracked.reads, [result["record"]["prepared_development_data_ref"]])
        self.assertEqual(view.payload["rows"], prepared["daily"])
        self.assertTrue(all(r["Order_Date"] <= "2025-11-30" for r in view.payload["rows"]))
        self.assertTrue(all(r["complete_daily_sales"] is False for r in view.payload["rows"]))
        self.assertNotIn(result["record"]["reserved_unseen_data_ref"], result["record"]["development_context_allowlist"])

    def test_actual_initial_calendar_rows_align_but_cannot_create_complete_labels(self):
        args, _, _, result = self.handoff()
        self.import_bytes(result)
        view = read_development(self.store, result["record"], args["execution"])
        features = self.features(result)
        self.assertEqual(features["format"], "dsc27-initial-v1")
        self.assertTrue(features["no_fitted_transformations"])
        self.assertEqual(features["excluded_unseen_key_target_rows"], 1)
        self.assertEqual(len(features["rows"]), 2)
        self.assertFalse(any("Quantity" in r or "target_quantity" in r for r in features["rows"]))
        row = features["rows"][0]
        key = (features["source_namespace"], row["Product_ID"], row["Store_ID"])
        window = Window(key, date.fromisoformat(row["origin"]), 1)
        with self.assertRaisesRegex(ModelingError, "completeness.*not zero"):
            build_examples(view, features["rows"], FEATURE_NAMES, [window])
        self.assertTrue(all(set(r) == {"source_namespace", "Product_ID", "Store_ID", "origin"}
                            for r in features["origin_rows"]))
        self.assertTrue(all(r["origin"] == "2025-11-30" for r in features["origin_rows"]))

    def test_calendar_feature_compatibility_with_separately_hypothetical_supported_labels(self):
        args, _, _, result = self.handoff()
        self.import_bytes(result)
        original = read_development(self.store, result["record"], args["execution"])
        hypothetical = original.payload
        # Explicit new mock evidence, never a modification of DSC-27's output.
        for row in hypothetical["rows"]:
            row.update(complete_daily_sales=True, target_available_date=row["Order_Date"],
                       completeness_evidence_refs=[{"mock_notice": "hypothetical completeness, no real acceptance"}])
        supported = DailyView.from_payload(hypothetical)
        features = self.features(result)
        row = features["rows"][0]
        window = Window((features["source_namespace"], row["Product_ID"], row["Store_ID"]),
                        date.fromisoformat(row["origin"]), 1)
        examples = build_examples(supported, features["rows"], FEATURE_NAMES, [window])
        self.assertEqual(examples[0].features, tuple(row[name] for name in FEATURE_NAMES))
        self.assertEqual(examples[0].actual, 4)
        self.assertEqual(examples[0].label_available_on, date(2025, 10, 31))
        self.assertTrue(all(r["complete_daily_sales"] is False for r in original.payload["rows"]))

    def test_reserved_values_cannot_influence_development_features_or_targets(self):
        first_args, first_split, first_prepared, first = self.handoff(future_quantity="987654321", suffix="a")
        _, second_split, second_prepared, second = self.handoff(future_quantity="123456789", suffix="b")
        self.assertNotEqual(first_split["reserved_csv"], second_split["reserved_csv"])
        self.assertEqual(first_split["development_csv"], second_split["development_csv"])
        self.assertEqual(first_prepared["daily"], second_prepared["daily"])
        self.assertEqual(self.features(first), self.features(second))
        for artifact in first["artifacts"]:
            if artifact["ref"] in first["record"]["development_context_allowlist"]:
                self.assertNotIn(b"987654321", artifact["data"])
                self.assertNotIn(b"2025-12-20", artifact["data"])
        injected = deepcopy(first_args)
        injected["sources"]["sales"]["data"] = first_split["reserved_csv"]
        injected["sources"]["sales"]["ref"] = _mock.artifact("illegal-future-development", first_split["reserved_csv"])
        injected["request"]["released_input_refs"] = [injected["sources"]["sales"]["ref"],
            *[injected["sources"][role]["ref"] for role in ("dictionary", "inventory", "receipts", "policy")]]
        with self.assertRaises(PreparationError):
            prepare_development(**injected)

    def test_preparation_scope_tampering_is_rejected_before_any_store_read(self):
        args, _, _, result = self.handoff()
        bad = deepcopy(result["record"])
        bad["development_context_allowlist"].remove(bad["prepared_development_data_ref"])
        tracked = RecordingStore(self.store)
        with self.assertRaisesRegex(ModelingError, "allowlist"):
            read_development(tracked, bad, args["execution"])
        self.assertEqual(tracked.reads, [])
        bad = deepcopy(result["record"])
        meta = next(a for a in bad["availability"] if a["artifact_ref"] == bad["prepared_development_data_ref"])
        meta["latest_information_available_date"] = "2025-12-01"
        with self.assertRaisesRegex(ModelingError, "future data"):
            read_development(tracked, bad, args["execution"])
        self.assertEqual(tracked.reads, [])


if __name__ == "__main__":
    unittest.main()
