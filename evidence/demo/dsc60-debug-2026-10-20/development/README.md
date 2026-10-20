# DSC-60 development reproduction only

This is local engineering evidence for the failed run, not a substitute for the Codex Data workflow, a new production model, or final DSC-9 acceptance. No paid calls were made here. The generated producer `analyze.py` was inspected, not executed. `scripts/dsc60_evaluate.py` independently reproduces all 24 producer MAEs to 1e-12 and performs the checks predeclared in `protocol.json`. October–November is already used development data.

The original four authoritative input files are hashed against the recording receipts. The full sales upload (SHA-256 `520fa470…`) is **never parsed**: only the already released cutoff-only `released/input-4.csv` (`48238e68…`) is parsed. Its max date is checked as November 30. This lineage is recorded in `diagnostics.json`. No December outcome file was opened or evaluated.

Seven-day aggregate product-store MAE remains the primary controlled comparison. The 13-week baseline means trailing 91 calendar days of positive non-cancelled recorded-order units after first activity, multiplied by seven. It is a fair declared interpretation, not a claim to reproduce the customer's exact method.

| Comparison | Baseline MAE | Seasonal MAE | Relative gain |
|---|---:|---:|---:|
| Early development, 12 origins | 0.797848 | 0.782790 | +1.887% |
| Late development, 8 origins | 0.975647 | 1.034078 | −5.989% |
| Combined, 20 origins | 0.868967 | 0.883305 | −1.650% |

Paired whole-origin bootstrap (10,000 draws, seed 60) gives early gain interval [0.166%, 3.444%], late [−8.597%, −3.185%], combined [−4.039%, 0.667%]. Few origins, serial dependence and post-selection uncertainty limit these descriptive intervals. Leave-one-early-origin-out selects seasonal in all 12 folds; early selection stability does not imply temporal stability. Six original candidates suffice for diagnosis; no new model search is performed.

The pragmatic engineering proposal is at least 5% relative seven-day MAE gain and positive origin-block 95% lower bound. It is not a supplied business benefit threshold, cost estimate, ROI, service level or stakeholder approval. The development stability control applies this requirement separately to early, late and combined development, and therefore retains the baseline. Final recording acceptance separately requires an approved criterion, an independently evidenced untouched final interval, a frozen Data-generated rule/code/input/prediction bundle, multiple non-overlapping origins, and one post-freeze evaluation. A minimum of two origins is only a structural floor, not a claim of adequate statistical power.

`frozen_predictions.csv` is an illustrative **single-origin development freeze** for December 1–7, with baseline retained. It cannot establish temporal robustness and is not DSC-9 final acceptance. `freeze_manifest.json` binds protocol, rule, predictions, code and input hashes; local hashes do not establish an immutable pre-holdout timestamp or independent provenance. `recording_readiness.json` is deliberately false. The bounded helper checks supplied local file hashes and receipt consistency. It does not parse protocol/rule semantics, validate prediction populations or numeric values, recompute metrics, verify actual external source/code bytes, authenticate external approval/exposure/chronology, or certify source truth. Those require independent caller review; this is not the DSC-9 final acceptance validator. It is never called by the ordinary application result path.

Data is very sparse: 96.47% of active entity-days and 76.73% of evaluated entity-weeks have zero recorded units. Zero-fill requires a complete extract; network date coverage alone cannot prove entity completeness. The observed-day training sensitivity uses a zero fallback for entities with no observations in the training window and is a diagnostic only. Status sensitivity holds the target fixed while changing the training proxy; better error under excluding processing/returns does not establish true demand. Final status lacks historical change timestamps, and stockout exposure is unavailable.

Policy protection periods are 8–14 days, so seven-day accuracy is not itself an ordering-outcome measure. The fully observed, fixed-population lead-plus-review diagnostic gives MAE 1.213454 baseline versus 1.201187 seasonal (about 1.01% gain). It cannot promote a winner over the primary metric. Its windows overlap and must not be treated as independent weekly outcomes; 14-day and policy-horizon diagnostics are secondary only. Pooling improves some squared-error measures without establishing primary MAE superiority; annual network month factors improve bias while worsening later weekly MAE.

Reproduce with the existing pandas/numpy development environment:

```sh
.venv/bin/python scripts/dsc60_evaluate.py \
  --source /private/tmp/dsc59-four-inputs \
  --output evidence/demo/dsc60-debug-2026-10-20/development \
  --producer-output artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-fd2a074d16e7401ca1682ad64e944847/output
.venv/bin/pytest -q tests/demo/test_readiness.py
```

The optional reproduction uses pandas/numpy already installed locally; they are not added to application runtime dependencies. Recording helper uses only the standard library. Nine meaningful gate tests cover missing evidence, tampered predictions, development promotion, repeated evaluation, wrong objective, small/nonrobust gain, missing independent provenance and insufficient origins.
