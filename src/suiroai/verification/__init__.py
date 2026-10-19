"""Independent retail output checks; parent orchestration retains authority.

Expose independent arithmetic, claim, guidance, and output-verifier helpers
for checking evidence before the parent considers permitted delivery.
"""

from .engine import OutputVerifier, SourceReaders, VerificationError

__all__ = ["OutputVerifier", "SourceReaders", "VerificationError"]
