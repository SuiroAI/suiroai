"""Single-case retail MVP interfaces owned by DSC-24.

Validation checks declarations and bindings; it does not run analysis, establish
source authenticity or authorize parent transitions.

Share versioned input, task, approval, output, and evidence interfaces so
components preserve the same confirmed retail task and distinguish outcomes.

Linear: https://linear.app/gr3enarr0w/issue/DSC-24
"""

from .validation import (
    VERSION,
    digest,
    input_digest,
    proposal_digest,
    record_ref,
    schema_validator,
    validate_bundle,
    validate_handoff,
    validate_record,
)

__all__ = [
    "VERSION", "digest", "input_digest", "proposal_digest", "record_ref",
    "schema_validator", "validate_bundle", "validate_handoff", "validate_record",
]
