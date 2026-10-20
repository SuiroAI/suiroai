"""Exercise forecast-only sealing with authored synthetic fixtures, never labels.

Check byte preservation, source/model identity, fixed origins, full common scope
and daily/weekly arithmetic. Passing these checks does not verify a producer's
model or permit final acceptance; no model code or December outcomes execute.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import csv
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("dsc60_freeze", Path(__file__).resolve().parents[2] / "scripts/dsc60_freeze.py")
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)


def csv_bytes(rows, columns):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


@pytest.fixture
def producer(tmp_path):
    root = tmp_path.resolve()
    source = root / "producer"
    source.mkdir()
    original = root / "original-selected-model.npz"
    original.write_bytes(b"SYNTHETIC saved model bytes; not executed")
    population = [{"Product_ID": "P" + str(n), "Store_ID": "S"} for n in range(336)]
    roles = sorted(freeze.REQUIRED_ROLES)
    artifacts = []
    for role in roles:
        path = role + ".bin"
        data = original.read_bytes() if role == "selected_model" else ("SYNTHETIC " + role).encode()
        (source / path).write_bytes(data)
        artifacts.append({"path": path, "role": role, "sha256": sha256(data).hexdigest()})
    protocol = {"format": "dsc60-final-freeze-protocol-v1", "as_of_date": freeze.AS_OF,
        "origin": freeze.AS_OF, "selected_model": "selected", "baseline_model": "baseline",
        "population": population, "artifacts": artifacts}
    protocol.update({key: "SYNTHETIC prespecified " + key for key in
        ("target_definition", "baseline_definition", "primary_metric", "coverage_rule", "evaluation_rule")})
    (source / "protocol.json").write_text(json.dumps(protocol))
    weekly, daily = [], []
    for model in ("selected", "baseline"):
        for pair in population:
            common = dict(pair, model=model, as_of_date=freeze.AS_OF, origin=freeze.AS_OF)
            for start in freeze.WEEK_STARTS:
                weekly.append(dict(common, target_start=start.isoformat(),
                    target_end=(start + freeze.timedelta(days=6)).isoformat(), horizon_days="7", forecast_units="7.125"))
            for day in freeze.DAYS:
                daily.append(dict(common, date=day.isoformat(), forecast_units=str(freeze.Decimal("7.125") / 7)))
    (source / "fixed_forecasts.csv").write_bytes(csv_bytes(weekly, sorted(freeze.WEEK_COLUMNS)))
    (source / "daily_forecasts.csv").write_bytes(csv_bytes(daily, sorted(freeze.DAY_COLUMNS)))
    return source, original, root / "frozen", protocol, weekly, daily


def invoke(producer):
    source, original, destination = producer[:3]
    return freeze.freeze_forecasts(source, destination, selected_model_original=original,
        expected_selected_model_sha256=sha256(b"SYNTHETIC saved model bytes; not executed").hexdigest())


def test_exact_bytes_shape_and_no_acceptance_promotion(producer):
    source, original, destination = producer[:3]
    before = original.read_bytes()
    result = invoke(producer)
    assert original.read_bytes() == before
    assert result["provenance_pending"] is True
    assert result["independent_model_verified"] is False
    assert result["parent_acceptance_granted"] is False
    assert result["outcomes_read_by_utility"] is False
    assert result["checks"]["weekly_rows"] == 2688
    assert result["checks"]["daily_rows"] == 20832
    for item in result["files"]:
        assert (destination / item["path"]).read_bytes() == (source / item["path"]).read_bytes()
        assert sha256((destination / item["path"]).read_bytes()).hexdigest() == item["sha256"]
        assert not (destination / item["path"]).stat().st_mode & 0o222
    with pytest.raises(FileExistsError):
        invoke(producer)
    assert json.loads((destination / "manifest.json").read_text()) == result


@pytest.mark.parametrize("variant", ["NaN", "Infinity", "-1", "duplicate", "missing", "origin", "cross_sum"])
def test_invalid_forecast_cannot_be_frozen(producer, variant):
    source, _, destination, _, weekly, daily = producer
    if variant in {"NaN", "Infinity", "-1"}:
        weekly[0]["forecast_units"] = variant
    elif variant == "duplicate":
        daily.append(daily[0])
    elif variant == "missing":
        weekly.pop()
    elif variant == "origin":
        daily[0]["origin"] = "2025-12-07"
    else:
        daily[0]["forecast_units"] = "99"
    (source / "fixed_forecasts.csv").write_bytes(csv_bytes(weekly, sorted(freeze.WEEK_COLUMNS)))
    (source / "daily_forecasts.csv").write_bytes(csv_bytes(daily, sorted(freeze.DAY_COLUMNS)))
    with pytest.raises(ValueError):
        invoke(producer)
    assert not destination.exists()


@pytest.mark.parametrize("variant", ["original", "artifact", "symlink", "population"])
def test_tampered_dependencies_cannot_be_frozen(producer, variant):
    source, original, destination, protocol = producer[:4]
    if variant == "original":
        original.write_bytes(b"Changed selected model")
    elif variant == "artifact":
        (source / protocol["artifacts"][0]["path"]).write_bytes(b"changed")
    elif variant == "symlink":
        path = source / "daily_forecasts.csv"
        backup = path.with_name("daily-backup.csv")
        path.rename(backup)
        path.symlink_to(backup)
    else:
        protocol["population"][0] = protocol["population"][1]
        (source / "protocol.json").write_text(json.dumps(protocol))
    with pytest.raises(ValueError):
        invoke(producer)
    assert not destination.exists()


def test_concurrent_original_change_rejects_and_removes_staging(producer, monkeypatch):
    original_reader = freeze.read_stage_file
    original = producer[1]
    reads = 0

    def reader(root, relative_path, **kwargs):
        nonlocal reads
        result = original_reader(root, relative_path, **kwargs)
        if Path(root) / relative_path == original:
            reads += 1
            if reads == 1:
                original.write_bytes(b"changed during freeze")
        return result

    monkeypatch.setattr(freeze, "read_stage_file", reader)
    with pytest.raises(ValueError, match="changed during freeze"):
        invoke(producer)
    assert not producer[2].exists()
    assert not list(producer[2].parent.glob(".frozen*"))
