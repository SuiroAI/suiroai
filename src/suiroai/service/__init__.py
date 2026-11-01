"""Integration service layer: joins the governed backend to a frontend.

This package is the thin seam described in ``docs/frontend-mapping/INTEGRATION_SPEC.md``.
It *calls* the existing modules (``contracts``, ``parent``, ``intake``, ``modeling``,
``replenishment``, ``reporting``, ``verification``, ``integration``); it never forks their
logic or re-implements a business rule. Nothing here establishes analytical acceptance,
authenticates evidence or authorises parent transitions — those remain owned upstream.

Phase A (this phase) covers the backend seam only: a store/fixture loader, an orchestration
driver, record-to-view translation, server-side derived fields, a minimal HTTP surface and a
run-progress channel. Product-tier concerns (identity, editing, approvals, reminders,
notifications, delivery, discovery) are later phases per the plan.
"""

from .store import open_store, load_fixture_bundle, FixtureError

__all__ = ["open_store", "load_fixture_bundle", "FixtureError"]
