# Final forecast freeze — DSC-60

[DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60) requires measured evaluation of the actual Data-selected model. [DSC-9](https://linear.app/gr3enarr0w/issue/DSC-9) additionally requires the broader authenticated parent freeze, verification and delivery chain. A forecast bundle does not close that milestone.

`scripts/dsc60_freeze.py` seals Data-produced files. It never imports/runs a producer model, fits, selects, interpolates forecasts, opens a separately supplied December outcome source or computes evaluation scores. It checks forecast structure, common population, arithmetic and exact artifact identity. Its output explicitly retains `provenance_pending: true`, `independent_model_verified: false` and `parent_acceptance_granted: false`.

## Producer files

The producer directory must contain `protocol.json`, `fixed_forecasts.csv`, `daily_forecasts.csv` and every artifact named in the protocol. Forecasts come from the previously selected Data model and the unchanged analytical baseline. Do not execute `restock_model.py` as an independent checker: that file fits again and overwrites `selected_model.npz`. A Data producer continuation should read the saved model, preserve its bytes, use only the already-released November-or-earlier inputs, and emit forecasts without selecting or refitting the selected model. Data owns any forecast trajectory definition; the sealing utility supplies none.

`protocol.json` has exactly these fields:

| Field | Required value or meaning |
| --- | --- |
| `format` | `dsc60-final-freeze-protocol-v1` |
| `as_of_date`, `origin` | Both `2025-11-30` |
| `selected_model`, `baseline_model` | Distinct nonempty names, such as the already selected `shrink26` and analytical baseline `recent13` |
| `population` | Exactly 336 unique objects with `Product_ID` and `Store_ID` strings |
| `target_definition` | Exact predeclared recorded-unit target/status/return treatment |
| `baseline_definition` | Exact existing baseline/training/coverage treatment |
| `primary_metric` | Predeclared metric and weighting; do not switch after scores |
| `coverage_rule` | Predeclared outcome observability, exclusions and coverage denominator |
| `evaluation_rule` | Predeclared interpretation/acceptance rule, including unavailable business thresholds honestly |
| `artifacts` | Objects containing exactly `path`, `role`, `sha256`; paths are safe relative files within the producer directory |

Required artifact roles are `selected_model` (exactly one), `model_code`, `preprocessing_code`, `feature_definition`, `evaluation_plan_v1`, `evaluation_plan_v2`, `implementation_correction`, `dependencies` and `development_source`. Multiple development sources and additional evidence roles are permitted. Use existing `task_refinement.json` for the feature/model specification where appropriate. Include exact source files, code/configuration, correction evidence, full dependency/version evidence and source hashes; do not substitute a summary for a missing artifact. Declared hashes must match the files, and the selected-model bytes must also match the original model and its independently supplied expected hash.

`fixed_forecasts.csv` has exactly these headers (column order is immaterial):

```text
model,Product_ID,Store_ID,as_of_date,origin,target_start,target_end,horizon_days,forecast_units
```

Each model needs one row for every population key and each of December 1–7, 8–14, 15–21 and 22–28, 2025: 2,688 rows total. Every row retains the November 30 as-of date and origin; these are fixed-origin future targets, not December refits. `horizon_days` is `7`. Preserve unrounded producer predictions rather than the rounded display CSV values.

`daily_forecasts.csv` has exactly these headers:

```text
model,Product_ID,Store_ID,as_of_date,origin,date,forecast_units
```

Each model needs every day December 1–31 and every key: 20,832 rows total. Both files require finite nonnegative units, no duplicate keys and complete common scope. Daily values must sum to each corresponding weekly total, with tolerance `1e-10 * max(1, abs(weekly_total))` for serialization arithmetic. Full forecast coverage does **not** establish full sales capture or observed outcome coverage. Days 29–31 remain explicit frozen forecasts even though the four whole-week primary windows end December 28.

The existing Data target is positive noncancelled recorded units with its observed-store-week treatment and documented unknown capture. Any later evaluation must retain that definition, report observed coverage and its limits, and distinguish forecasts from uncensored demand. Parent fully-observed-horizon requirements and any genuine shortcomings remain visible; the utility does not relabel incomplete source capture as complete daily sales.

## Seal before opening outcomes

```sh
PYTHONPATH=src .venv/bin/python scripts/dsc60_freeze.py \
  --producer-root /absolute/path/to/data-produced-freeze-output \
  --destination /absolute/path/to/new-frozen-bundle \
  --selected-model-original /absolute/path/to/original/selected_model.npz \
  --expected-selected-model-sha256 ORIGINAL_SAVED_MODEL_SHA256
```

The original NPZ hash must come from the prior saved-model receipt, not a producer-reported replacement. The utility checks that original before and after copying and rechecks every declared producer artifact before sealing. It copies exact bytes to read-only files in a temporary sibling directory and atomically publishes a new bundle with `manifest.json`, a UTC `frozen_at`, validation counts and all file hashes. A lock coordinates concurrent invocations; existing destination directories are refused. No existing model, run artifact or bundle is rewritten.

After sealing, separately review the protocol, identity and chronology before outcome evaluation. The manifest does not certify that source data was untouched, that the producer implemented the model correctly, that a historical knowledge timestamp exists, or that an earlier exposure never occurred. Freezing now cannot undo prior provenance exposure. Keep original evidence and report any resulting limitation honestly; do not tune, refit, select a runner-up, change the frozen predictions or lower coverage/acceptance requirements after inspecting outcomes. The broader typed parent contract must not be fabricated merely to label this MVP comparison accepted.
