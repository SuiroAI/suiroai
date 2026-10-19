"""Private DSC-28 calculation types; shared wire contracts stay with DSC-24.

Define validated forecast windows, examples, predictions, and shared helpers
for finite values, canonical payloads, and required parent decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import math

from suiroai.contracts import digest, schema_validator

CUTOFF = date(2025, 11, 30)
UNSEEN_END = date(2025, 12, 31)
Key = tuple[str, str, str]  # source namespace, Product_ID, Store_ID


class ModelingError(ValueError):
    """Invalid/unavailable evidence, not a measured model failure."""


def finite(value, name="value") -> float:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ModelingError(f"{name} must be finite numeric evidence")
        return float(value)
    except OverflowError as exc:
        raise ModelingError(f"{name} exceeds finite numeric range") from exc


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def checked_definition(kind: str, value: dict) -> None:
    validator = schema_validator()
    errors = list(validator.evolve(schema={"$ref": f"#/$defs/{kind}",
                                         "$defs": validator.schema["$defs"]}).iter_errors(value))
    if errors:
        raise ModelingError(f"invalid {kind}: {errors[0].message}")


def utc_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ModelingError("timestamp needs a timezone")
    return parsed


def require_parent(decision: dict, checkpoint: str, *, allowed=("proceed",), evidence=True):
    """Check a supplied decision's shape; trusted DSC-10 authenticates authority."""
    checked_definition("parent_decision", decision)
    if decision["checkpoint"] != checkpoint or decision["decision"] not in allowed:
        raise ModelingError(f"parent {checkpoint} checkpoint has not authorized this operation")
    if evidence and not decision["evidence_refs"]:
        raise ModelingError("parent decision requires measured evidence references")


@dataclass(frozen=True, order=True)
class Window:
    key: Key
    origin: date
    horizon_days: int

    def __post_init__(self):
        if not isinstance(self.key, tuple) or len(self.key) != 3 or not all(isinstance(v, str) and v for v in self.key):
            raise ModelingError("window needs namespace/product/store identity")
        if type(self.origin) is not date or type(self.horizon_days) is not int or not 1 <= self.horizon_days <= 366:
            raise ModelingError("window needs a calendar origin and bounded positive protection horizon")

    @property
    def start(self):
        return self.origin + timedelta(days=1)

    @property
    def end(self):
        return self.origin + timedelta(days=self.horizon_days)

    def payload(self):
        return {"key": list(self.key), "origin": self.origin.isoformat(),
                "horizon_days": self.horizon_days, "target_start": self.start.isoformat(),
                "target_end": self.end.isoformat()}


@dataclass(frozen=True)
class Example:
    window: Window
    features: tuple[float | None, ...]
    actual: float
    available_on: date | None = None

    def __post_init__(self):
        if not isinstance(self.features, tuple) or len(self.features) > 32:
            raise ModelingError("features must be a bounded immutable vector")
        for v in self.features:
            if v is not None:
                finite(v, "feature")
        if finite(self.actual, "target") < 0:
            raise ModelingError("prepared gross-unit target cannot be negative")
        # None means only the fully observed horizon's end, never its origin.
        if self.available_on is not None and (type(self.available_on) is not date or self.available_on < self.window.end):
            raise ModelingError("target availability cannot precede target completion")

    @property
    def label_available_on(self):
        return self.available_on or self.window.end


@dataclass(frozen=True)
class Prediction:
    window: Window
    actual: float
    predicted: float

    def __post_init__(self):
        if finite(self.actual, "actual") < 0 or finite(self.predicted, "prediction") < 0:
            raise ModelingError("gross-unit observations/predictions must be nonnegative")

    def payload(self):
        return dict(self.window.payload(), actual=self.actual, predicted=self.predicted)


def prediction_signature(rows):
    rows = tuple(rows)
    if not rows or len({r.window for r in rows}) != len(rows):
        raise ModelingError("empty or duplicate forecast population")
    return tuple(sorted((r.window, r.actual) for r in rows))


def bound_payload(payload, execution: dict):
    """Attach task/run/input/proposal versions to a private numerical artifact."""
    return {"binding": execution["binding"], "run_id": execution["run_id"],
            "execution_contract_sha256": digest(execution), **payload}
