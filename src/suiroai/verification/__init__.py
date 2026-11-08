"""Independent retail output checks; parent orchestration retains authority."""

from .engine import OutputVerifier, SourceReaders, VerificationError

__all__ = ["OutputVerifier", "SourceReaders", "VerificationError"]
