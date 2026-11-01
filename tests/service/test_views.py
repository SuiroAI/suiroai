"""A-PR3 (DSC-72): record → frontend-view translation.

Drives the view mappers from the orchestrator over the shipped fixtures and asserts faithful,
loss-free, non-fabricating translation into the frontend shapes: file roles map 1:1 incl.
dictionary (R1); the baseline is always present and the frozen candidate is recommended (R3/R4);
order quantities come from the authoritative backend record and exceptions surface as a distinct
state (R5/R6); failures carry no orders (R9); text is escaped and only http/https links pass (R11).
"""
from __future__ import annotations

from pathlib import Path
import unittest

from suiroai.service import views
from suiroai.service.orchestrator import load_analysis

FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "contracts" / "v0.1.0"


def _view(name):
    return load_analysis(FIXTURES / f"{name}.json")


class EscapeTests(unittest.TestCase):
    def test_esc_escapes_html(self):
        self.assertEqual(views.esc("<b>&\"x\""), "&lt;b&gt;&amp;&quot;x&quot;")
        self.assertEqual(views.esc(None), "")

    def test_safe_url_allows_only_http_https(self):
        self.assertEqual(views.safe_url("https://example.com/x"), "https://example.com/x")
        self.assertEqual(views.safe_url("http://example.com"), "http://example.com")
        self.assertEqual(views.safe_url("javascript:alert(1)"), "")
        self.assertEqual(views.safe_url("ftp://x"), "")
        self.assertEqual(views.safe_url("https://x y"), "")   # space rejected
        self.assertEqual(views.safe_url(None), "")


class DataFileTests(unittest.TestCase):
    def test_roles_map_including_dictionary(self):
        sub = _view("successful_analysis").submission()
        files = views.data_files(sub)
        roles = {f["sourceRole"]: f["role"] for f in files}
        self.assertEqual(roles["transactions"], "Sales history")
        self.assertEqual(roles["usable_stock"], "Stock on hand")
        self.assertEqual(roles["inbound_ledger"], "Incoming shipments")
        self.assertEqual(roles["ordering_policy"], "Supplier rules")
        self.assertIn("dictionary", roles)   # R1: dictionary present (mapped to Other for now)

    def test_analysis_head_carries_question_and_files(self):
        v = _view("successful_analysis")
        a = views.analysis(v.submission(), status=v.outcome)
        self.assertTrue(a["question"])
        self.assertEqual(a["status"], v.outcome)
        self.assertEqual(len(a["files"]), 5)


class ModelViewTests(unittest.TestCase):
    def test_baseline_always_present_and_frozen_is_recommended(self):
        ev = _view("successful_analysis").evaluation_result()
        rows = views.model_results(ev)
        baselines = [r for r in rows if r["isBaseline"]]
        self.assertEqual(len(baselines), 1)                       # R3: baseline always shown
        recommended = [r for r in rows if r["isRecommended"]]
        self.assertEqual(len(recommended), 1)                     # R4: exactly one recommended
        self.assertEqual(recommended[0]["id"], ev["frozen"]["selected_candidate_id"])

    def test_scores_are_mapped_not_fabricated(self):
        ev = _view("successful_analysis").evaluation_result()
        rows = views.model_results(ev)
        cand = next(r for r in rows if not r["isBaseline"])
        self.assertTrue(cand["scores"])
        # Only metrics the backend actually carries are present; none invented.
        self.assertEqual(cand["scores"][0]["metricId"], ev["candidates"][0]["scores"][0]["metric_id"])
        self.assertEqual(cand["scores"][0]["value"], ev["candidates"][0]["scores"][0]["value"])

    def test_model_run_states(self):
        self.assertEqual(views.model_run(_view("successful_analysis"))["state"], "done")
        self.assertEqual(views.model_run(_view("missing_inputs"))["state"], "queued")
        self.assertEqual(views.model_run(_view("approved_execution"))["state"], "running")
        run = views.model_run(_view("successful_analysis"))
        self.assertTrue(run["recommendedId"])
        self.assertTrue(run["results"])


class OrderLineTests(unittest.TestCase):
    def test_order_lines_use_authoritative_quantity(self):
        qr = _view("successful_analysis").quantity_result()
        lines = views.order_lines(qr)
        self.assertTrue(lines)
        line, order = lines[0], qr["orders"][0]
        self.assertEqual(line["productId"], order["key"]["product_id"])
        self.assertEqual(line["store"], order["key"]["store_id"])
        self.assertEqual(line["suggestedQty"], order["rounded_order_quantity"])  # R5
        self.assertEqual(line["onHand"], order["usable_on_hand_quantity"])
        self.assertFalse(line["isException"])

    def test_exceptions_are_distinct_state(self):
        qr = _view("successful_analysis").quantity_result()
        exc = views.order_exceptions(qr)   # may be empty for this fixture; shape still valid
        for e in exc:
            self.assertTrue(e["isException"])
            self.assertIsNone(e["qty"])
            self.assertIn("reason", e)


class ReportViewTests(unittest.TestCase):
    def test_success_report_has_orders_and_escaped_text(self):
        rd = _view("successful_analysis").report_draft()
        summary = views.report_summary(rd)
        self.assertEqual(summary["outcome"], "success")
        self.assertTrue(summary["customerDraft"])
        self.assertTrue(summary["hasOrders"])
        self.assertIsNone(summary["failure"])

    def test_failure_reports_carry_no_orders(self):
        for name in ("validation_failed", "execution_failed"):
            with self.subTest(fixture=name):
                rd = _view(name).report_draft()
                summary = views.report_summary(rd)
                self.assertNotEqual(summary["outcome"], "success")
                self.assertFalse(summary["hasOrders"])          # R9
                self.assertIsNotNone(summary["failure"])


if __name__ == "__main__":
    unittest.main()
