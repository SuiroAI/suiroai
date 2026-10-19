"""DSC-28 component calculations; no runtime, checkpoint or delivery authority.

Expose the modeling component helpers for development evaluation, additional
features, immutable candidate selection, and frozen final validation.
"""
from .core import CUTOFF, Example, ModelingError, Prediction, Window
from .evaluation import CandidateSpec, RollingFold, compare_candidates, evaluate_initial
from .features import DevelopmentArtifact, generate_feature_proposal, materialize_features
from .frozen import (finalize_validation, freeze_bundle, record_defect_recheck,
                     record_failed_defect_recheck, score_frozen,
                     shared_defect_recheck, verify_frozen)
from .inference import predict_november30
from .metrics import compare_values, score
from .prepared import (DailyView, build_examples, forecast_daily_rows,
                       materialize_reserved_targets, read_development, scope_keys)
from .records import (comparison_record, feature_records, final_record,
                      initial_record, persist_candidate, put_payload)

__all__ = [
    "CUTOFF", "Example", "ModelingError", "Prediction", "Window",
    "CandidateSpec", "RollingFold", "compare_candidates", "evaluate_initial",
    "DevelopmentArtifact", "generate_feature_proposal", "materialize_features",
    "finalize_validation", "freeze_bundle", "record_defect_recheck",
    "record_failed_defect_recheck", "score_frozen", "shared_defect_recheck", "verify_frozen",
    "predict_november30", "compare_values", "score", "DailyView", "build_examples",
    "forecast_daily_rows", "materialize_reserved_targets", "read_development", "scope_keys",
    "comparison_record", "feature_records", "final_record", "initial_record",
    "persist_candidate", "put_payload",
]
