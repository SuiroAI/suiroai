"""DSC-29 candidate arithmetic; no model selection or approval authority.

Expose the handoff checks and calculation entry point that turn frozen
forecasts and operational inputs into reviewable candidate purchase quantities.
"""

from .context import Handoff, InputError
from .calculation import calculate_candidate

__all__ = ["Handoff", "InputError", "calculate_candidate"]
