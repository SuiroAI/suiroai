"""SuiroAI application package; components are owned by their MVP issues.

SuiroAI uses dscraft as its single data-science backend: all EDA and modeling
run through dscraft rather than importing numpy/pandas/scikit-learn/statsforecast
directly. :func:`validate_backend` checks that the installed dscraft capability
stack matches dscraft's own known-good, conflict-free version set, so a subtly
incompatible environment fails loudly up front instead of deep inside a model
fit. It is intentionally NOT called at import time -- importing ``suiroai`` must
stay cheap and must not force dscraft's heavy stack to load -- so an application
entrypoint should call it explicitly during startup.
"""
from __future__ import annotations


def validate_backend(groups=("tabular",)):
    """Validate the dscraft data-science backend against its known-good set.

    Args:
        groups: dscraft capability group(s) SuiroAI relies on. Defaults to
            ``("tabular",)`` -- the modeling path (seeded GBT quantile models).
            Pass additional groups (e.g. ``("tabular", "forecast", "eda")``)
            from an entrypoint that also uses forecasting or EDA.

    Returns:
        The mapping returned by ``dscraft.validate_environment`` (installed
        versions that are present and in range).

    Raises:
        RuntimeError: dscraft is not importable (the dependency is missing).
        dscraft.EnvironmentValidationError: an installed dependency version is
            outside dscraft's tested, conflict-free window.
    """
    try:
        import dscraft
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise RuntimeError(
            "SuiroAI requires its dscraft[analytics] dependency; install the "
            "application with its declared dependencies"
        ) from exc
    results = {}
    for group in groups:
        results.update(dscraft.validate_environment(group))
    return results


__all__ = ["validate_backend"]
