"""Retail-domain rule library for the agnostic engine — the end-to-end retail chain.

The engine (``service/derive.py``) is domain-neutral and evaluates whatever
:class:`~suiroai.service.rules.RuleSet` it is given. This package is the **retail domain's** rule
library, and retail here means the **whole retail chain**, not a single problem:

    demand → forecasting → replenishment/restocking → suppliers / procurement →
    inventory & stock health → pricing / markdown → assortment → fulfilment

Each stage of the chain is a problem *area*; each area contributes one or more rulesets built from
shared retail primitives. Adding or extending a chain area means adding a ruleset here, never
changing the engine. Restocking and suppliers are the first built areas (the current demo focus);
the registry and structure anticipate the rest of the chain.

Thresholds live with each ruleset and are overridable — nothing is baked into the engine.
"""

from .restocking import RETAIL_RESTOCKING_RULES, build_restocking_ruleset
from .suppliers import RETAIL_SUPPLIER_RULES, build_supplier_ruleset

# Registry of retail-chain problem areas → their default ruleset. This is the map of the chain as
# currently built; extend it as each stage is implemented. Callers select an area by key.
RETAIL_PROBLEMS = {
    "restocking": RETAIL_RESTOCKING_RULES,
    "suppliers": RETAIL_SUPPLIER_RULES,
}

# The retail chain stages, in order, with which are built vs planned. Kept as data so the
# architecture of the chain is discoverable from code, not only from docs.
RETAIL_CHAIN = (
    {"stage": "demand", "status": "planned"},
    {"stage": "forecasting", "status": "planned"},
    {"stage": "restocking", "status": "built"},
    {"stage": "suppliers", "status": "built"},
    {"stage": "inventory_health", "status": "planned"},
    {"stage": "pricing_markdown", "status": "planned"},
    {"stage": "assortment", "status": "planned"},
    {"stage": "fulfilment", "status": "planned"},
)


def ruleset_for(problem_area: str):
    """Return the default ruleset for a retail-chain problem area (e.g. ``"restocking"``).

    Raises ``KeyError`` listing the known areas if the area is not registered — the engine never
    silently falls back to an unrelated area's rules.
    """
    try:
        return RETAIL_PROBLEMS[problem_area]
    except KeyError:
        raise KeyError(
            f"unknown retail problem area {problem_area!r}; known: {sorted(RETAIL_PROBLEMS)}"
        ) from None


__all__ = [
    "RETAIL_PROBLEMS",
    "RETAIL_CHAIN",
    "ruleset_for",
    "RETAIL_RESTOCKING_RULES",
    "build_restocking_ruleset",
    "RETAIL_SUPPLIER_RULES",
    "build_supplier_ruleset",
]
