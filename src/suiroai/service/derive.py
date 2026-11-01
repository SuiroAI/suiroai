"""Generic, domain-neutral rule evaluator.

Given a record (any dict) and a :class:`~suiroai.service.rules.RuleSet`, compute the ruleset's
metrics and flags. The engine contains **no domain knowledge** — no "cover", "stock-out" or
"supplier minimum". Those belong to a supplied ruleset (retail's is one instance under
``service/instances/``). A different problem supplies a different ruleset and this engine is
unchanged; that is what makes the system agnostic.

Honesty is enforced structurally: a metric function returning ``None`` means "not enough data"
and is surfaced as such; a flag declared without a predicate (``fn is None``) is reported as
explicitly unavailable with the data it needs, never silently dropped or guessed. Results are
server-computed from the record only, so a client cannot override a derived value.
"""
from __future__ import annotations

from typing import Mapping

from .rules import RuleSet


def evaluate_metrics(record: dict, ruleset: RuleSet) -> dict:
    """Compute the ruleset's metrics over ``record``, in declared order.

    Returns ``{metric_name: value_or_None}``. Later metrics may read earlier results (passed in as
    the second argument to each metric function). A metric whose function raises or returns ``None``
    is recorded as ``None`` ("not enough data"), never fabricated.
    """
    computed: dict[str, object] = {}
    for metric in ruleset.metrics:
        try:
            computed[metric.name] = metric.fn(record, computed)
        except Exception:
            # A rule that cannot compute from the available data yields "not enough data",
            # not a crash and not a guess.
            computed[metric.name] = None
    return computed


def evaluate_flags(record: dict, ruleset: RuleSet, metrics: Mapping[str, object]) -> dict:
    """Evaluate the ruleset's flags, split into active, inactive and unavailable.

    Returns:
        {
          "active":      [{"code","severity"} ...],   # derivable and currently true, priority-sorted
          "inactive":    ["code" ...],                 # derivable but currently false
          "unavailable": [{"code","needs"} ...],        # declared but not derivable from this data
        }
    """
    active, inactive, unavailable = [], [], []
    for flag in ruleset.flags:
        if not flag.derivable:
            unavailable.append({"code": flag.code, "needs": flag.needs})
            continue
        try:
            applies = bool(flag.fn(record, metrics))
        except Exception:
            # Cannot evaluate from available data → treat as unavailable, not false.
            unavailable.append({"code": flag.code, "needs": flag.needs or "data to evaluate the rule"})
            continue
        (active if applies else inactive).append(
            {"code": flag.code, "severity": flag.severity} if applies else flag.code)
    active.sort(key=lambda f: ruleset.severity_rank(f["severity"]))
    return {"active": active, "inactive": inactive, "unavailable": unavailable}


def derive(record: dict, ruleset: RuleSet) -> dict:
    """Compute all derived values for one record under ``ruleset``.

    The engine is agnostic: the keys and meaning of ``metrics``/``flags`` come entirely from the
    supplied ruleset. With :data:`~suiroai.service.rules.EMPTY_RULES` this returns empty results,
    because the base system has no domain of its own.
    """
    metrics = evaluate_metrics(record, ruleset)
    flags = evaluate_flags(record, ruleset, metrics)
    return {"metrics": metrics, "flags": flags}
