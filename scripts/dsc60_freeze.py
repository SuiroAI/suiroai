"""Seal Data-produced final forecasts without fitting or examining outcomes.

Validate the declared November 30 origin, common 336-key population, four
December weekly forecasts and complete daily trajectories for selected model
and baseline. Copy exact producer artifacts into a new atomic bundle, checking
the original saved model hash before and after. This is manifest/shape evidence,
not independent model verification, untouched-data proof or parent acceptance.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-9
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from suiroai.integration.artifacts import read_stage_file


AS_OF = "2025-11-30"
WEEK_STARTS = tuple(date(2025, 12, 1) + timedelta(days=7 * n) for n in range(4))
DAYS = tuple(date(2025, 12, 1) + timedelta(days=n) for n in range(31))
WEEK_COLUMNS = {"model", "Product_ID", "Store_ID", "as_of_date", "origin", "target_start", "target_end", "horizon_days", "forecast_units"}
DAY_COLUMNS = {"model", "Product_ID", "Store_ID", "as_of_date", "origin", "date", "forecast_units"}
REQUIRED_ROLES = {"selected_model", "model_code", "preprocessing_code", "evaluation_plan_v1", "evaluation_plan_v2", "implementation_correction", "dependencies", "development_source", "feature_definition"}
PROTOCOL_FIELDS = {"format", "as_of_date", "origin", "selected_model", "baseline_model", "population", "target_definition", "baseline_definition", "primary_metric", "coverage_rule", "evaluation_rule", "artifacts"}


def _hash(data):
    return sha256(data).hexdigest()


def _safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Artifact path must be a safe relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("Artifact path must be a safe relative path")
    return path


def _value(text):
    try:
        number = Decimal(text)
    except (InvalidOperation, TypeError):
        raise ValueError("Forecast must be finite and nonnegative") from None
    if not number.is_finite() or number < 0:
        raise ValueError("Forecast must be finite and nonnegative")
    return number


def _rows(raw, columns):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames is None or set(reader.fieldnames) != columns or len(reader.fieldnames) != len(columns):
        raise ValueError("Forecast CSV columns differ from the declared schema")
    for row in reader:
        if set(row) != columns or any(value is None for value in row.values()):
            raise ValueError("Forecast CSV contains a malformed row")
        yield row


def _protocol(raw):
    protocol = json.loads(raw)
    if not isinstance(protocol, dict) or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("Protocol fields differ from the declared schema")
    if protocol["format"] != "dsc60-final-freeze-protocol-v1" or protocol["as_of_date"] != AS_OF or protocol["origin"] != AS_OF:
        raise ValueError("Protocol must declare the fixed November 30 origin")
    for key in ("selected_model", "baseline_model", "target_definition", "baseline_definition", "primary_metric", "coverage_rule", "evaluation_rule"):
        if not isinstance(protocol[key], str) or not protocol[key].strip():
            raise ValueError("Protocol definitions must be nonempty text")
    if protocol["selected_model"] == protocol["baseline_model"]:
        raise ValueError("Selected and baseline identities must be distinct")
    if not isinstance(protocol["population"], list):
        raise ValueError("Protocol population must contain exactly 336 unique keys")
    keys = []
    for key in protocol["population"]:
        if (not isinstance(key, dict) or set(key) != {"Product_ID", "Store_ID"}
                or any(not isinstance(value, str) or not value.strip() for value in key.values())):
            raise ValueError("Population keys must identify product and store")
        keys.append((key["Product_ID"], key["Store_ID"]))
    if len(keys) != 336 or len(set(keys)) != 336:
        raise ValueError("Protocol population must contain exactly 336 unique keys")
    if not isinstance(protocol["artifacts"], list):
        raise ValueError("Protocol must identify producer artifacts")
    paths, roles = set(), []
    for item in protocol["artifacts"]:
        if (not isinstance(item, dict) or set(item) != {"path", "role", "sha256"}
                or not isinstance(item["role"], str) or not item["role"].strip()
                or not isinstance(item["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None):
            raise ValueError("Invalid producer artifact declaration")
        path = str(_safe_relative(item["path"]))
        if path in paths or path in {"protocol.json", "fixed_forecasts.csv", "daily_forecasts.csv", "manifest.json"}:
            raise ValueError("Duplicate or reserved producer artifact path")
        paths.add(path)
        roles.append(item["role"])
    if not REQUIRED_ROLES <= set(roles) or roles.count("selected_model") != 1:
        raise ValueError("Required producer artifact roles are absent or selected model is ambiguous")
    return protocol, set(keys)


def validate_forecasts(protocol, keys, weekly_raw, daily_raw):
    """Check common scope and daily/weekly arithmetic without deriving forecasts."""
    models = {protocol["selected_model"], protocol["baseline_model"]}
    weekly, daily = {}, {}
    for row in _rows(weekly_raw, WEEK_COLUMNS):
        pair = (row["Product_ID"], row["Store_ID"])
        try:
            start, end = date.fromisoformat(row["target_start"]), date.fromisoformat(row["target_end"])
        except ValueError:
            raise ValueError("Invalid weekly target dates") from None
        if (row["model"] not in models or pair not in keys or row["as_of_date"] != AS_OF or row["origin"] != AS_OF
                or start not in WEEK_STARTS or end != start + timedelta(days=6) or row["horizon_days"] != "7"):
            raise ValueError("Weekly forecast scope or fixed origin differs")
        key = (row["model"], *pair, start)
        if key in weekly:
            raise ValueError("Duplicate weekly forecast")
        weekly[key] = _value(row["forecast_units"])
    for row in _rows(daily_raw, DAY_COLUMNS):
        pair = (row["Product_ID"], row["Store_ID"])
        try:
            day = date.fromisoformat(row["date"])
        except ValueError:
            raise ValueError("Invalid daily target date") from None
        if row["model"] not in models or pair not in keys or row["as_of_date"] != AS_OF or row["origin"] != AS_OF or day not in DAYS:
            raise ValueError("Daily forecast scope or fixed origin differs")
        key = (row["model"], *pair, day)
        if key in daily:
            raise ValueError("Duplicate daily forecast")
        daily[key] = _value(row["forecast_units"])
    if len(weekly) != 2 * 336 * 4 or len(daily) != 2 * 336 * 31:
        raise ValueError("Forecast coverage is incomplete")
    for (model, product, store, start), total in weekly.items():
        summed = sum(daily[(model, product, store, start + timedelta(days=n))] for n in range(7))
        if abs(summed - total) > Decimal("1e-10") * max(Decimal(1), abs(total)):
            raise ValueError("Daily forecasts do not sum to weekly forecasts")
    return {"population": 336, "models": sorted(models), "weekly_rows": len(weekly),
        "daily_rows": len(daily), "as_of_date": AS_OF, "origin": AS_OF,
        "weekly_target_starts": [day.isoformat() for day in WEEK_STARTS],
        "daily_start": DAYS[0].isoformat(), "daily_end": DAYS[-1].isoformat(),
        "sum_tolerance": "1e-10 * max(1, abs(weekly_total))"}


def freeze_forecasts(producer_root, destination, *, selected_model_original, expected_selected_model_sha256):
    """Copy exact producer bytes into a new bundle; never run code or read labels."""
    producer_root, destination = Path(producer_root).absolute(), Path(destination).absolute()
    original = Path(selected_model_original).absolute()
    if re.fullmatch(r"[0-9a-f]{64}", expected_selected_model_sha256) is None:
        raise ValueError("An external expected selected model SHA-256 is required")
    original_bytes = read_stage_file(original.parent, original.name, max_bytes=64 * 1024 * 1024)
    if _hash(original_bytes) != expected_selected_model_sha256:
        raise ValueError("Original selected model hash differs before freeze")
    payloads = {name: read_stage_file(producer_root, name, max_bytes=64 * 1024 * 1024)
        for name in ("protocol.json", "fixed_forecasts.csv", "daily_forecasts.csv")}
    protocol, keys = _protocol(payloads["protocol.json"])
    checks = validate_forecasts(protocol, keys, payloads["fixed_forecasts.csv"], payloads["daily_forecasts.csv"])
    for item in protocol["artifacts"]:
        raw = read_stage_file(producer_root, item["path"], max_bytes=64 * 1024 * 1024)
        if _hash(raw) != item["sha256"]:
            raise ValueError("Producer artifact hash differs: " + item["path"])
        if item["role"] == "selected_model" and (raw != original_bytes or item["sha256"] != expected_selected_model_sha256):
            raise ValueError("Producer selected model differs from the external frozen choice")
        payloads[item["path"]] = raw
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name("." + destination.name + ".freeze-lock")
    temporary = None
    with lock.open("x"):
        try:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError("Freeze destination already exists")
            temporary = Path(tempfile.mkdtemp(prefix="." + destination.name + "-", dir=destination.parent))
            for name, raw in payloads.items():
                path = temporary / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                path.chmod(0o400)
            if read_stage_file(original.parent, original.name, max_bytes=64 * 1024 * 1024) != original_bytes:
                raise ValueError("Original selected model changed during freeze")
            # Recheck producer bytes so the manifest never hides a concurrent edit.
            for name, raw in payloads.items():
                if read_stage_file(producer_root, name, max_bytes=64 * 1024 * 1024) != raw:
                    raise ValueError("Producer artifact changed during freeze: " + name)
            manifest = {"format": "dsc60-final-forecast-freeze-v1",
                "frozen_at": datetime.now(timezone.utc).isoformat(), "provenance_pending": True,
                "independent_model_verified": False, "parent_acceptance_granted": False,
                "outcomes_read_by_utility": False, "selected_model_sha256": expected_selected_model_sha256,
                "checks": checks, "files": [{"path": name, "bytes": len(raw), "sha256": _hash(raw)}
                    for name, raw in sorted(payloads.items())],
                "limits": "Exact byte/shape/arithmetic freeze only. Producer chronology, source provenance, untouchedness, model semantics and evaluation acceptance require separate review. No code was executed or outcomes scored."}
            (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            (temporary / "manifest.json").chmod(0o400)
            if destination.exists() or destination.is_symlink():
                raise FileExistsError("Freeze destination already exists")
            temporary.rename(destination)
            temporary = None
            return manifest
        finally:
            if temporary is not None:
                shutil.rmtree(temporary)
            lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--selected-model-original", required=True, type=Path)
    parser.add_argument("--expected-selected-model-sha256", required=True)
    args = parser.parse_args()
    manifest = freeze_forecasts(args.producer_root, args.destination,
        selected_model_original=args.selected_model_original,
        expected_selected_model_sha256=args.expected_selected_model_sha256)
    print(json.dumps({"destination": str(args.destination), "frozen_at": manifest["frozen_at"],
        "checks": manifest["checks"], "provenance_pending": True}, indent=2))


if __name__ == "__main__":
    main()
