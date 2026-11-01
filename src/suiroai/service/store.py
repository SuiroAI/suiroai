"""Store factory and contract-fixture loader for the integration service.

The repository already provides a production content-addressed store,
``suiroai.integration.artifacts.ArtifactStore``, whose
``put_record``/``read_record``/``put_bytes``/``read_bytes`` interface is exactly what
``suiroai.parent.workflow.ParentWorkflow`` expects. This module does **not** add a parallel
store; it exposes a small factory over ``ArtifactStore`` and a loader that places a committed
contract fixture bundle into such a store so the orchestration driver (A-PR2) can advance a
workflow over real, integrity-checked artifacts.

Fixtures are mock interface examples only (see each bundle's ``mock_notice``); loading one
establishes no analytical acceptance. The loader is fail-closed: a record that does not validate
against the contract schema, or a bundle that is not self-consistent, is rejected rather than
silently stored.
"""
from __future__ import annotations

import json
from pathlib import Path

from suiroai.contracts import record_ref, validate_bundle, validate_record
from suiroai.contracts.validation import digest
from suiroai.integration.artifacts import ArtifactStore


class FixtureError(ValueError):
    """A fixture bundle could not be loaded as a self-consistent contract graph."""


# External byte artifacts in a fixture are addressed by the canonical JSON of their
# ``content_marker`` string (mirrors tests/contracts/test_contract.py). This keeps the loader
# faithful to how the committed fixtures encode source bytes, without inventing content.
_REF_FIELDS = {"artifact_id", "version", "sha256", "provenance"}


def open_store(root) -> ArtifactStore:
    """Return an :class:`ArtifactStore` rooted at ``root`` (created if absent).

    ``root`` is a filesystem path owned by the caller (typically a temp dir in tests or an
    ignored ``artifacts/`` path at runtime). Raw customer data must never be placed here.
    """
    return ArtifactStore(root)


def _marker_bytes(marker) -> bytes:
    """Canonical JSON bytes for a fixture ``content_marker`` (string or object).

    Mirrors ``digest`` in the contracts module so the stored bytes hash to the marker's
    ``digest`` value and match the ``sha256`` the fixture declares for the artifact.
    """
    return json.dumps(marker, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_fixture_bundle(store: ArtifactStore, path) -> dict:
    """Load a contract fixture bundle into ``store`` and return an index of what was stored.

    Validates the whole bundle (``validate_bundle``) and each record (``validate_record``)
    before writing anything. Returns a dict with:

    - ``records``: ``{kind: [ref, ...]}`` for every stored record (latest-first per kind),
    - ``external_refs``: ``[ref, ...]`` for the mock source/byte artifacts stored via ``put_bytes``,
    - ``provenance``: the bundle's declared ``fixture_provenance`` (e.g. ``"mock"``),
    - ``notice``: the bundle's ``mock_notice`` if present.

    Fail-closed: any validation error raises :class:`FixtureError` and nothing is written beyond
    artifacts already committed by an earlier call (loads are idempotent per content hash).
    """
    path = Path(path)
    try:
        bundle = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise FixtureError(f"unreadable fixture bundle: {exc}") from exc

    if not isinstance(bundle, dict) or "records" not in bundle:
        raise FixtureError("fixture must be an object with a 'records' array")

    bundle_errors = validate_bundle(bundle)
    if bundle_errors:
        raise FixtureError("; ".join(bundle_errors[:5]))

    # Store external byte artifacts first so record refs that point at them resolve.
    external_refs: list[dict] = []
    for artifact in bundle.get("mock_artifacts", []):
        ref = artifact.get("ref")
        if not isinstance(ref, dict) or set(ref) != _REF_FIELDS or "content_marker" not in artifact:
            raise FixtureError("mock artifact must carry a ref and a content_marker")
        marker = artifact["content_marker"]
        data = _marker_bytes(marker)
        if digest(marker) != ref["sha256"]:
            raise FixtureError(f"mock artifact {ref['artifact_id']} sha256 does not match its marker")
        stored = store.put_bytes(ref["artifact_id"], ref["version"], ref["provenance"], data)
        external_refs.append(stored)

    records_by_kind: dict[str, list[dict]] = {}
    for record in bundle["records"]:
        errors = validate_record(record)
        if errors:
            raise FixtureError(f"{record.get('artifact_id', '?')}: {'; '.join(errors[:3])}")
        stored = store.put_record(record)
        records_by_kind.setdefault(record["kind"], []).append(stored)

    # Latest artifact_version first within each kind, matching how consumers resolve "the one".
    for kind, refs in records_by_kind.items():
        refs.sort(key=lambda r: r["version"], reverse=True)

    return {
        "records": records_by_kind,
        "external_refs": external_refs,
        "provenance": bundle.get("fixture_provenance"),
        "notice": bundle.get("mock_notice"),
    }
