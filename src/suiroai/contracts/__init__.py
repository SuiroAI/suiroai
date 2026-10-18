"""Single-case retail MVP interfaces owned by DSC-24.

Validation checks declarations and bindings; it does not run analysis, establish
source authenticity or authorize parent transitions.
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
