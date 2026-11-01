"""Record → frontend-view translation (read models).

Pure functions that turn immutable backend records into the shapes the frontend data contract
(``docs/frontend-mapping/../types.d.ts``) expects. One-way, no business logic, no fabrication:
where the backend does not carry a value the frontend wants, the view says so (``null`` /
``"unavailable"``) rather than inventing one — consistent with the product's "never guess, show
Not enough data" rule.

Security (R11): all free text that originates from model/evidence output is HTML-escaped, and any
URL is allowed only when it is ``http``/``https``. These helpers are applied at the view boundary
so a downstream renderer receives already-safe strings.

Field-name correspondence is documented in ``docs/frontend-mapping/FRONTEND_TO_BACKEND_MAP.md``
§2. Notably the backend keys order lines by ``{source_namespace, product_id, store_id}`` and works
in forecast horizons, while the frontend ``OrderLine`` uses ``productId``/``store`` and weekly
framing; derived presentation fields (coverWeeks, flags, weeklyPace) are **not** produced here —
they are computed in ``service/derive.py`` (A-PR4), which is the only place allowed to add them.
"""
from __future__ import annotations

from html import escape as _html_escape

# File role mapping: backend source_role -> frontend FileRole (map §2.1).
_ROLE_TO_FRONTEND = {
    "transactions": "Sales history",
    "usable_stock": "Stock on hand",
    "inbound_ledger": "Incoming shipments",
    "ordering_policy": "Supplier rules",
    "dictionary": "Other",          # data dictionary; frontend has no dedicated role yet
    "other": "Other",
}


def esc(value) -> str:
    """HTML-escape untrusted text for safe rendering (R11). ``None`` becomes an empty string."""
    if value is None:
        return ""
    return _html_escape(str(value), quote=True)


def safe_url(value) -> str:
    """Return ``value`` only if it is an http/https URL, else an empty string (R11)."""
    if not isinstance(value, str):
        return ""
    v = value.strip()
    return v if (v.startswith("http://") or v.startswith("https://")) and " " not in v else ""


# ---------------------------------------------------------------------------
# step 1/2: submission -> Analysis + DataFile[]
# ---------------------------------------------------------------------------
def data_files(submission: dict) -> list[dict]:
    """Map ``submission.files[]`` to frontend ``DataFile[]`` (R1)."""
    out = []
    for f in submission.get("files", []):
        out.append({
            "id": esc(f.get("file_id")),
            "name": esc(f.get("original_name")),
            "role": _ROLE_TO_FRONTEND.get(f.get("source_role"), "Other"),
            "sourceRole": f.get("source_role"),          # keep the backend role for round-trips
            "access": f.get("access"),
            "sizeBytes": f.get("size_bytes"),
        })
    return out


def analysis(submission: dict, *, status: str) -> dict:
    """Map a ``submission`` (+ orchestrator-derived status) to the frontend ``Analysis`` head."""
    return {
        "question": esc(submission.get("original_request")),
        "status": status,
        "files": data_files(submission),
    }


# ---------------------------------------------------------------------------
# step 3: evaluation_result -> ModelResult[] + ModelRun
# ---------------------------------------------------------------------------
def _scores_view(scores: list[dict]) -> list[dict]:
    """Faithfully expose the generic metric records the backend carries.

    The frontend's four named metrics (accuracy/typicalError/shortagesCaught/unneededOrders)
    are a product framing the backend does not store as such. We surface each metric by its
    ``metric_id`` with value/unit and population/observation context, and leave the named-metric
    slots unavailable rather than fabricate them (R3: map exactly; no guessing).
    """
    view = []
    for s in scores:
        view.append({
            "metricId": esc(s.get("metric_id")),
            "value": s.get("value"),
            "unit": esc(s.get("unit")),
            "populationId": esc(s.get("population_id")),
            "observationCount": s.get("observation_count"),
        })
    return view


def model_results(evaluation: dict) -> list[dict]:
    """Map ``evaluation_result`` candidates (+ baseline) to ModelResult-like rows (R3, R4).

    The baseline is always included and flagged (``isBaseline``), matching "always show the
    user's existing method as a baseline". The recommended candidate is the frozen selection.
    """
    recommended = (evaluation.get("frozen") or {}).get("selected_candidate_id")
    rows = [{
        "id": esc(evaluation.get("baseline_id")),
        "name": esc(evaluation.get("baseline_id")),
        "isBaseline": True,
        "isRecommended": False,
        "scores": _scores_view(evaluation.get("baseline_scores", [])),
    }]
    for c in evaluation.get("candidates", []):
        cid = c.get("candidate_id")
        rows.append({
            "id": esc(cid),
            "name": esc(cid),
            "isBaseline": False,
            "isRecommended": cid == recommended,
            "scores": _scores_view(c.get("scores", [])),
        })
    return rows


def model_run(view) -> dict:
    """Map an orchestrator ``AnalysisView`` to the frontend ``ModelRun`` state shape.

    ``state`` reflects the run outcome; ``results``/``recommendedId`` are present once a
    comparison exists. Imported lazily to keep this module dependency-light.
    """
    from .orchestrator import OUTCOME_RUNNING, OUTCOME_MISSING_INPUTS

    evaluation = view.evaluation_result()
    if view.outcome == OUTCOME_MISSING_INPUTS:
        state = "queued"
    elif view.outcome == OUTCOME_RUNNING:
        state = "running"
    elif evaluation is None:
        state = "failed"
    else:
        state = "done"
    run = {"state": state, "results": [], "recommendedId": None}
    if evaluation is not None:
        run["results"] = model_results(evaluation)
        run["recommendedId"] = esc((evaluation.get("frozen") or {}).get("selected_candidate_id"))
    return run


# ---------------------------------------------------------------------------
# step 5: quantity_result -> OrderLine[] (+ exceptions)
# ---------------------------------------------------------------------------
def order_lines(quantity_result: dict) -> list[dict]:
    """Map ``quantity_result.orders[]`` to frontend ``OrderLine``-shaped rows (R5, R6).

    The backend's ``approved_order_quantity`` / ``rounded_order_quantity`` is **authoritative**
    for the suggested/ordered quantity; the frontend's own weekly formula is only an
    approximation and is not computed here. Derived presentation fields (coverWeeks, flags) are
    added later by ``service/derive.py``.
    """
    out = []
    for o in quantity_result.get("orders", []):
        key = o.get("key", {})
        suggested = o.get("rounded_order_quantity")
        approved = o.get("approved_order_quantity")
        out.append({
            "sourceNamespace": esc(key.get("source_namespace")),
            "productId": esc(key.get("product_id")),
            "store": esc(key.get("store_id")),
            "onHand": o.get("usable_on_hand_quantity"),
            "incoming": o.get("eligible_receipt_quantity"),
            "suggestedQty": suggested,
            # qty = the authoritative approved quantity if present, else the suggested value.
            "qty": approved if approved is not None else suggested,
            "forecastHorizonStart": esc(o.get("forecast_horizon_start")),
            "forecastHorizonEnd": esc(o.get("forecast_horizon_end")),
            "quantityUnit": esc(o.get("quantity_unit")),
            "isException": False,
        })
    return out


def order_exceptions(quantity_result: dict) -> list[dict]:
    """Map ``quantity_result.exceptions[]`` to a distinct line state (R6): no quantity, a reason."""
    out = []
    for e in quantity_result.get("exceptions", []):
        key = e.get("key", {})
        out.append({
            "sourceNamespace": esc(key.get("source_namespace")),
            "productId": esc(key.get("product_id")),
            "store": esc(key.get("store_id")),
            "suggestedQty": None,
            "qty": None,
            "isException": True,
            "reason": esc(e.get("reason")),
        })
    return out


# ---------------------------------------------------------------------------
# step 4: report_draft -> report summary / claims / findings
# ---------------------------------------------------------------------------
def report_summary(report_draft: dict) -> dict:
    """Map ``report_draft`` to a safe report summary view (R9, R11).

    Claims and findings are evidence-bound, customer-facing sentences; escaped for rendering.
    """
    return {
        "outcome": report_draft.get("outcome"),
        "customerDraft": esc(report_draft.get("customer_draft")),
        "claims": [esc(c.get("statement")) for c in report_draft.get("claims", [])],
        "findings": [
            {"statement": esc(f.get("statement")), "classification": f.get("classification")}
            for f in report_draft.get("findings", [])
        ],
        "hasOrders": bool(report_draft.get("orders")),
        "failure": _failure_view(report_draft.get("failure")),
    }


def _failure_view(failure):
    if not failure:
        return None
    return {
        "stage": esc(failure.get("stage")),
        "reason": esc(failure.get("reason")),
        "scopeLimitation": esc(failure.get("scope_limitation")),
    }
