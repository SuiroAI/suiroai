"""Joint horizon-demand quantile: the counterexample and dependence policy."""

from __future__ import annotations

from fractions import Fraction

import pytest

from suiroai.replenishment.horizon import (
    HorizonError,
    joint_horizon_quantile,
    prob_total_exceeds,
)


def _two_day_0_or_100():
    # Each day: demand 0 w.p. 0.96, 100 w.p. 0.04. Step CDF: support [0,100], cum [0.96, 1].
    day = ([0, 100], [Fraction(96, 100), Fraction(1)])
    return [day, day]


def test_counterexample_joint_is_100_not_zero() -> None:
    per_day = _two_day_0_or_100()
    # The naive daily-quantile SUM would be 0 + 0 = 0 (each daily 95th pct is 0).
    assert all(support[0] == 0 for support, _ in per_day)  # daily 95th pct = 0
    # The correct joint two-day 95th percentile is exactly 100.
    q = joint_horizon_quantile(per_day, service_level=Fraction(95, 100), dependence_model="independent")
    assert q == 100


def test_counterexample_prob_total_exceeds_zero_is_0784() -> None:
    per_day = _two_day_0_or_100()
    p = prob_total_exceeds(per_day, 0, dependence_model="independent")
    assert p == Fraction(784, 10000)  # 1 - 0.96^2 = 0.0784 exactly
    assert float(p) == pytest.approx(0.0784, abs=1e-9)


def test_comonotonic_rejected() -> None:
    per_day = _two_day_0_or_100()
    with pytest.raises(HorizonError):
        joint_horizon_quantile(per_day, service_level=Fraction(95, 100), dependence_model="comonotonic")


def test_empirical_copula_without_fitted_joint_withholds() -> None:
    per_day = _two_day_0_or_100()
    with pytest.raises(HorizonError):
        joint_horizon_quantile(per_day, service_level=Fraction(95, 100), dependence_model="empirical_copula")


def test_incomplete_cdf_rejected() -> None:
    bad = [([0, 100], [Fraction(96, 100), Fraction(99, 100)])]  # never reaches 1
    with pytest.raises(HorizonError):
        joint_horizon_quantile(bad, service_level=Fraction(95, 100), dependence_model="independent")


def test_service_level_bounds() -> None:
    per_day = _two_day_0_or_100()
    for bad in (Fraction(1, 2), Fraction(1), Fraction(0)):
        with pytest.raises(HorizonError):
            joint_horizon_quantile(per_day, service_level=bad, dependence_model="independent")


def test_degenerate_certain_demand_sums_normally() -> None:
    # Two days each exactly 3 units (CDF jumps to 1 at 3): horizon total is certainly 6.
    day = ([3], [Fraction(1)])
    q = joint_horizon_quantile([day, day], service_level=Fraction(95, 100), dependence_model="independent")
    assert q == 6
