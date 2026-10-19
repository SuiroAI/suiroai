"""Evidence-bound DSC-29 drafts; no delivery or parent transition authority.

Expose report builders for success, validation failure, execution failure,
and missing-input guidance using the corresponding immutable evidence.

Prepare one supported customer response: a restocking report with verified
findings, specific capability guidance, or an evidenced terminal explanation.

Linear: https://linear.app/gr3enarr0w/issue/DSC-29
"""

from .drafts import draft_execution_failure, draft_missing_inputs, draft_success, draft_validation_failure

__all__ = ["draft_success", "draft_missing_inputs", "draft_validation_failure", "draft_execution_failure"]
