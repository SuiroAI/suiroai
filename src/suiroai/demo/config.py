"""Load optional trusted controller comparison settings for Streamlit startup.

An operator-owned environment path can select an engineering comparison without
adding customer configuration controls. Read bounded JSON before constructing a
session, validate all contract fields and reload on reruns so changed settings
revoke prior consent. Invalid settings fail closed instead of silently removing
the comparison constraint. Uploaded files never select this configuration.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import json
import os
from pathlib import Path

from suiroai.integration.artifacts import read_stage_file
from .task import comparison_contract_record


CONTRACT_ENV = "SUIROAI_DEMO_COMPARISON_CONTRACT"


class DemoConfigurationError(ValueError):
    """Report invalid operator configuration without authorizing analysis."""


def load_comparison_contract(environ=None):
    """Return a validated copied definition, or None only when the path is unset."""
    environment = os.environ if environ is None else environ
    configured = environment.get(CONTRACT_ENV)
    if configured is None:
        return None
    if not isinstance(configured, str) or not configured.strip() or not Path(configured).is_absolute():
        raise DemoConfigurationError(CONTRACT_ENV + " must name an absolute JSON file")
    path = Path(configured)
    try:
        raw = read_stage_file(path.parent, path.name, max_bytes=64 * 1024)
        definition = json.loads(raw)
        record = comparison_contract_record(definition)
        if record is None:
            raise ValueError("Configured comparison contract must be a JSON object")
    except (OSError, ValueError, UnicodeError) as exc:
        raise DemoConfigurationError("Invalid comparison contract configuration: " + str(exc)) from exc
    return record["definition"]


def configured_session(session_factory=None, *, definition=None):
    """Construct the actual session with validated trusted comparison settings.

    The caller loads configuration before this boundary. Revalidate injected
    definitions so tests/custom launchers cannot skip the contract schema.
    """
    from .service import DemoSession

    contract = comparison_contract_record(definition)
    factory = session_factory or DemoSession
    return factory(comparison_contract=contract["definition"]) if contract else factory()
