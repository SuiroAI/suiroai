"""DSC-29 candidate arithmetic; no model selection or approval authority."""

from .context import Handoff, InputError
from .calculation import calculate_candidate

__all__ = ["Handoff", "InputError", "calculate_candidate"]
