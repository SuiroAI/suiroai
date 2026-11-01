"""Problem-agnostic rule model.

The system is domain-neutral: it solves whatever problem it is given. Retail restocking is the
first worked instance (the current demo), not the system's definition. So this module carries **no
domain semantics** — no "cover", "stock-out" or "supplier minimum". It defines a small, generic
vocabulary for expressing *derived values* and *flags* as declarative rules that a caller supplies
per problem. Retail's specific rules are provided as data (see ``service/instances/`` for the
demo's ruleset), never embedded here.

A ``RuleSet`` is pure data:

- ``metrics``: named derived values, each computed by a registered, side-effect-free function from
  a record's fields (e.g. for retail, "cover" = on_hand / daily_demand). The engine does not know
  what a metric *means*; it only evaluates the referenced function against supplied inputs.
- ``flags``: named conditions with a severity tier, each a predicate over the record and its
  computed metrics. Severity tiers are themselves just an ordered list the ruleset declares.

Because rules are data, a different problem supplies a different ``RuleSet`` with different metrics
and flags, and the engine (``service/derive.py``) is unchanged. Nothing is baked in.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Mapping, Sequence

# A metric function: given the record dict and the metrics computed so far, return a value or None
# (None = "not enough data", never a guess). Pure; no I/O, no globals.
MetricFn = Callable[[dict, Mapping[str, object]], object]

# A flag predicate: given the record and computed metrics, return True if the flag applies.
FlagFn = Callable[[dict, Mapping[str, object]], bool]


@dataclass(frozen=True)
class MetricRule:
    """A named derived value computed by ``fn``. ``requires`` lists record fields it reads, so a
    deployment can validate a ruleset against a record schema without running it."""
    name: str
    fn: MetricFn
    requires: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class FlagRule:
    """A named condition with a severity tier.

    ``fn`` is the predicate when the flag is derivable from available data. When a flag is declared
    but cannot yet be evaluated (the data it needs is absent), ``fn`` is ``None`` and ``needs``
    states what unlocks it — so the engine can report it as explicitly unavailable rather than
    silently omit or fabricate it.
    """
    code: str
    severity: str
    fn: FlagFn | None = None
    needs: str | None = None
    description: str = ""

    @property
    def derivable(self) -> bool:
        return self.fn is not None


@dataclass(frozen=True)
class RuleSet:
    """A declarative, domain-neutral rule set supplied per problem.

    The engine evaluates ``metrics`` in order (later metrics may read earlier ones), then
    ``flags``. ``severity_order`` is the ruleset's own ordering of tiers (first = highest).
    Nothing here is retail- or domain-specific; retail is one supplied instance.
    """
    metrics: Sequence[MetricRule] = ()
    flags: Sequence[FlagRule] = ()
    severity_order: tuple[str, ...] = ()

    def severity_rank(self, severity: str) -> int:
        try:
            return self.severity_order.index(severity)
        except ValueError:
            return len(self.severity_order)

    def with_overrides(self, **overrides) -> "RuleSet":
        return replace(self, **overrides)


# An empty ruleset: the engine computes nothing and flags nothing. The default is intentionally
# empty because the base system has no domain. A problem must supply its own ruleset.
EMPTY_RULES = RuleSet()
