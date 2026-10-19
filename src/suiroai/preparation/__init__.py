"""DSC-27 preparation; no import-time I/O, runtime host, or customer output.

Expose deterministic preparation, initial-feature, and result-building
helpers for processing the inputs released by the approved parent workflow.
"""

from .worker import PreparationError, partition_sales, prepare_development
from .features import build_features, fit_categories, transform_categories, horizon_target
from .result import build_result

__all__ = ["PreparationError", "partition_sales", "prepare_development", "build_features",
           "fit_categories", "transform_categories", "horizon_target", "build_result"]
