"""Independent retail output checks; parent orchestration retains authority.

Expose independent arithmetic, claim, guidance, and output-verifier helpers
for checking evidence before the parent considers permitted delivery.

Support independent output checks before parent-authorized delivery of the
confirmed task outcome, including supported guidance and terminal explanations.

Linear: https://linear.app/gr3enarr0w/issue/DSC-30
"""

from .engine import OutputVerifier, SourceReaders, VerificationError

__all__ = ["OutputVerifier", "SourceReaders", "VerificationError"]
