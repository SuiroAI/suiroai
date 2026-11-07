"""Joint horizon-demand quantile for distribution-aware safety stock.

retail.replenishment ONLY. This module turns a complete per-day demand trajectory
over the protection horizon into the **joint** horizon-demand quantile at a target
service level -- the quantity that actually meets that service level over the whole
horizon. It deliberately does NOT sum per-day marginal quantiles: that is wrong, and
the counterexample is in the tests (two independent days, demand 0 w.p. 0.96 and 100
otherwise -> each daily 95th pct is 0, their sum is 0, but the true joint two-day 95th
pct is 100 and P(total>0)=0.0784).

Dependence is explicit and from a closed allowlist; **comonotonic is not allowed** (it
is not a general upper bound for the horizon percentile). When no admissible dependence
model is available the caller must fail closed (withhold), never substitute a sum.

Pure stdlib (``fractions.Fraction`` for exact integer-demand convolution); no heavy
dependency at this layer.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Mapping, Sequence

#: Allowed cross-day dependence models. Comonotonic is intentionally excluded.
ALLOWED_DEPENDENCE = frozenset({"independent", "empirical_copula"})


class HorizonError(ValueError):
    """Invalid trajectory, dependence model, or service level for the horizon join."""


def _check_cdf(support: Sequence[int], cumulative: Sequence[Fraction]) -> None:
    if not support or len(support) != len(cumulative):
        raise HorizonError("per-day support and cumulative must be equal, non-empty length")
    if list(support) != sorted(set(support)) or any(s < 0 for s in support):
        raise HorizonError("support must be strictly increasing non-negative integers")
    if any(not (Fraction(0) <= p <= Fraction(1)) for p in cumulative):
        raise HorizonError("cumulative probabilities must lie in [0, 1]")
    if list(cumulative) != sorted(cumulative):
        raise HorizonError("cumulative probabilities must be non-decreasing")
    if cumulative[-1] != Fraction(1):
        raise HorizonError("cumulative probability must reach exactly 1 (incomplete_demand_distribution)")


def _pmf_from_cdf(support: Sequence[int], cumulative: Sequence[Fraction]) -> dict[int, Fraction]:
    pmf: dict[int, Fraction] = {}
    prev = Fraction(0)
    for value, cum in zip(support, cumulative):
        pmf[value] = cum - prev
        prev = cum
    return pmf


def _convolve(a: Mapping[int, Fraction], b: Mapping[int, Fraction]) -> dict[int, Fraction]:
    out: dict[int, Fraction] = {}
    for va, pa in a.items():
        for vb, pb in b.items():
            out[va + vb] = out.get(va + vb, Fraction(0)) + pa * pb
    return out


def joint_horizon_quantile(
    per_day: Sequence[tuple[Sequence[int], Sequence[Fraction]]],
    *,
    service_level: Fraction,
    dependence_model: str,
) -> int:
    """Return the smallest integer horizon total whose joint CDF >= ``service_level``.

    ``per_day`` is one ``(support, cumulative)`` integer step-CDF per horizon day.
    ``dependence_model`` must be in :data:`ALLOWED_DEPENDENCE`. Only ``independent`` is
    computed here (exact discrete convolution). ``empirical_copula`` requires a fitted
    joint and is not derivable from marginals alone -> raises so the caller withholds.
    Comonotonic (or any other) is rejected.
    """
    if dependence_model not in ALLOWED_DEPENDENCE:
        raise HorizonError(
            f"dependence_model must be one of {sorted(ALLOWED_DEPENDENCE)} "
            f"(comonotonic is not an allowed model); got {dependence_model!r}"
        )
    if not (Fraction(1, 2) < service_level < Fraction(1)):
        raise HorizonError("service_level must be in (0.5, 1)")
    if not per_day:
        raise HorizonError("empty horizon trajectory")
    if dependence_model == "empirical_copula":
        raise HorizonError(
            "empirical_copula horizon join requires a fitted joint distribution; "
            "per-day marginals alone are insufficient (withhold / supply the fitted joint)"
        )
    # independent: exact discrete convolution of the per-day PMFs.
    joint: dict[int, Fraction] = {0: Fraction(1)}
    for support, cumulative in per_day:
        _check_cdf(support, cumulative)
        joint = _convolve(joint, _pmf_from_cdf(support, cumulative))
    cumulative = Fraction(0)
    for total in sorted(joint):
        cumulative += joint[total]
        if cumulative >= service_level:
            return total
    return max(joint)  # pragma: no cover - cumulative reaches 1 by construction


def prob_total_exceeds(
    per_day: Sequence[tuple[Sequence[int], Sequence[Fraction]]],
    threshold: int,
    *,
    dependence_model: str = "independent",
) -> Fraction:
    """Exact P(horizon total > threshold) under independence (for tests/evidence)."""
    if dependence_model != "independent":
        raise HorizonError("prob_total_exceeds only supports the independent joint")
    joint: dict[int, Fraction] = {0: Fraction(1)}
    for support, cumulative in per_day:
        _check_cdf(support, cumulative)
        joint = _convolve(joint, _pmf_from_cdf(support, cumulative))
    return sum((p for total, p in joint.items() if total > threshold), Fraction(0))
