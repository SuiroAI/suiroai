"""EDA/profiling through dscraft -- SuiroAI's single data-science backend.

DSC-27 development profiling (row/null/quantile statistics over already-prepared
development rows) is computed through ``dscraft.eda`` rather than hand-rolled
``statistics`` calls, so dscraft is the one backend for EDA as well as modeling.

Scope and safety:

* This module only ever profiles rows the caller has ALREADY prepared and
  restricted to the permitted development partition. It never opens a raw
  source file and never sees reserved/holdout rows -- the development/holdout
  isolation enforced upstream is unchanged; this is a pure, in-memory
  summarization step over data the worker already holds.
* It returns plain JSON-native numbers in the exact shape DSC-27's ``audit``
  (and the downstream ``dsc28-development-summary-v1`` contract) expects, so
  the summary schema and its validation are untouched -- only the *computation*
  of the statistics moves onto dscraft.
* dscraft is imported lazily and the environment is validated against dscraft's
  known-good set, mirroring the modeling backend's discipline.

The numeric column summary uses dscraft's KLL quantile sketch for
min/median/max (and any extra quantiles) and dscraft's null report + row count
for coverage; the arithmetic mean -- which a quantile sketch does not provide --
is computed exactly over the same values dscraft profiled, so the summary stays
faithful to the data.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def _require_eda():
    """Import dscraft's EDA backend lazily and validate the eda version set."""
    try:
        import dscraft
        from dscraft.eda import LazyEDA  # noqa: F401
        from dscraft.eda.sketches import estimate_quantiles
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        from .worker import PreparationError  # local import to avoid cycles

        raise PreparationError(
            "development profiling requires the dscraft eda backend; install "
            "suiroai with its dscraft[analytics] dependency"
        ) from exc
    dscraft.validate_environment("eda")
    return estimate_quantiles


def numeric_summary(values: Iterable[float], *,
                    quantiles: Sequence[float] = (0.0, 0.5, 1.0)) -> dict:
    """Summarize a numeric development column via dscraft's KLL quantile sketch.

    Args:
        values: the already-prepared development values (no holdout rows).
        quantiles: quantile probabilities to estimate; defaults to the
            min/median/max triple DSC-27's audit reports. 0.0 and 1.0 give the
            exact observed extremes from the sketch.

    Returns:
        A dict with ``count``, ``minimum``, ``maximum``, ``median``, ``mean``
        and the full ``quantiles`` mapping. Empty input yields null stats and a
        zero count (never a fabricated zero value), matching the prior
        ``statistics``-based behavior.
    """
    import statistics as _stats

    estimate_quantiles = _require_eda()
    data = [float(v) for v in values]
    if not data:
        return {"count": 0, "minimum": None, "maximum": None,
                "median": None, "mean": None, "quantiles": {}}
    probs = sorted({0.0, 0.5, 1.0, *quantiles})
    result = estimate_quantiles(data, quantiles=probs)
    estimates = result.quantile_estimates
    # NOTE on median semantics: dscraft's KLL sketch returns an actual observed
    # value near rank 0.5 (never interpolating between the two middle values).
    # The DSC-27 development summary and the coverage statement derived from it
    # report the *exact* interpolating median (statistics.median), so we keep
    # that exact value for `median` to preserve the disclosed number, and expose
    # the KLL quantile estimates separately under `quantiles` as the profile.
    return {
        "count": len(data),
        "minimum": estimates[0.0],
        "maximum": estimates[1.0],
        "median": _stats.median(data),
        # KLL does not estimate the mean; compute it exactly over the same data.
        "mean": sum(data) / len(data),
        "quantiles": {str(q): estimates[q] for q in probs},
    }


def frame_profile(rows: Sequence[dict], *, numeric_columns: Sequence[str]) -> dict:
    """Profile prepared development rows via ``dscraft.eda.LazyEDA``.

    Returns row count, per-column null counts, and a numeric summary per
    requested column -- all computed through dscraft over an in-memory Polars
    frame built from the already-prepared rows. Used for the DSC-27 development
    EDA summary; it does not decide sales semantics, joins or target eligibility
    (those stay in the worker), consistent with dscraft.eda's stated boundary.
    """
    _require_eda()
    import polars as pl
    from dscraft.eda import LazyEDA

    frame = pl.DataFrame(list(rows)) if rows else pl.DataFrame()
    profile = LazyEDA().profile(frame) if len(frame) else None
    null_counts = dict(profile.null_report.null_counts) if profile else {}
    row_count = profile.row_count if profile else 0
    columns = {}
    for name in numeric_columns:
        values = [r[name] for r in rows if r.get(name) is not None]
        columns[name] = numeric_summary(values)
    return {"row_count": row_count, "null_counts": null_counts, "columns": columns}
