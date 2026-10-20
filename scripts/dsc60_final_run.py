"""Stage and trace Data-authored fixed-model forecasts before reserved evaluation.

This controller copies already approved November-only inputs and the selected
model into a fresh read-only release. Genuine Codex/Data writes forecasts and
the protocol; this module never fits, predicts, scores or reads December rows.
The separate manifest/checker establishes frozen identities before release.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-9
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from suiroai.demo.call_trace import begin_call_trace, finish_call_trace
from suiroai.integration.native import NativeHost


SELECTED_HASH = '93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e'


def stage_forecast(repo: Path, root: Path):
    """Stage exact authorized inputs and frozen-choice evidence, without outcomes."""
    old = repo / 'artifacts/demo/8d99bf86d50541e19a6afa142746809c/runs/investigation-3146a4fb9c3d4784b1d982e04f91797a'
    retained = repo / 'evidence/demo/dsc60-debug-2026-10-20/streamlit-discovery-2026-10-20/analysis/output'
    root.mkdir(parents=True, exist_ok=False)
    released, output, native = (root / n for n in ['released', 'output', 'native'])
    for directory in [released, output, native]:
        directory.mkdir(mode=0o700)
    manifest = []
    sources = [(old / 'released' / f'input-{i}.csv', f'input-{i}.csv', 'development_source') for i in range(1, 5)]
    roles = {'selected_model.npz': 'selected_model', 'restock_model.py': 'model_code',
             'prepare.py': 'preprocessing_code', 'analysis.py': 'analysis_code',
             'task_refinement.json': 'feature_definition', 'evaluation_plan.json': 'evaluation_plan_v1',
             'evaluation_plan_v2.json': 'evaluation_plan_v2',
             'implementation_correction.json': 'implementation_correction',
             'routine_workload.json': 'dependencies'}
    sources.extend((retained / name, name, role) for name, role in roles.items())
    for source, name, role in sources:
        data = source.read_bytes()
        digest = sha256(data).hexdigest()
        if name == 'selected_model.npz' and digest != SELECTED_HASH:
            raise ValueError('Previously selected model identity changed')
        destination = released / name
        destination.write_bytes(data)
        destination.chmod(0o400)
        manifest.append({'relative_path': name, 'source_role': role,
                         'source': str(source), 'released_byte_sha256': digest, 'released_bytes': len(data)})
    prompt = forecast_prompt(released, manifest)
    trace = begin_call_trace(native, stage='final_forecast_freeze_preparation', prompt=prompt, manifest=manifest)
    record = {'format': 'dsc60-final-forecast-call-v1', 'prepared_at': datetime.now(timezone.utc).isoformat(),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
              'controller_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_commit_is_base_with_scoped_controller_changes': True,
              'selected_model_sha256': SELECTED_HASH, 'released': str(released), 'output': str(output),
              'native': str(native), 'trace': trace,
              'limits': 'No reserved outcomes released. Earlier full-history summary exposure remains recorded; no pristine-untouched or parent acceptance is asserted.'}
    (root / 'call.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def forecast_prompt(released, manifest):
    """Ask Data to preserve its selected model and author only fixed forecasts."""
    return f'''Use the attached @Data plugin. Complete the already selected retail model's pre-evaluation freeze. This is NOT model discovery or customer rewriting.
Read-only inputs: {released}
{json.dumps(manifest, indent=2)}
The customer requires the MVP to be completed using the existing dataset. The selected model is shrink26, with exact selected_model.npz SHA256 {SELECTED_HASH}. It was selected by development seven-day recorded-unit MAE. Freeze that exact fitted model, the same recent13 baseline and all analytical definitions before December evaluation. Never refit, overwrite or reselect the selected model; load its full-precision weekly_recorded_units and IDs. Do not execute restock_model.py as-is: it refits and overwrites the model. You may author an inference-only program and calculate the baseline using ONLY the provided development records ending November30. Reproduce recent13 exactly as documented and coded in the original Data analysis, with13 complete calendar weeks and its original missing-store-week treatment. No new candidates, hyperparameters, target, metric or baseline changes. Investigate any mismatch and report it rather than silently changing the choice.
No December2025 transaction outcomes, raw originals or other files are accessible/authorized for this call. Operational future due dates are known inputs. Earlier project AI sessions saw pooled full-history summaries, so DO NOT certify December as globally pristine untouched. This call produces pre-release forecasts only. Keep that qualification internal; no new-data request. No extra AI agent/model call and no healthy execution deadline.
Write protocol.json BEFORE producing forecasts, with exact schema:
{{"format":"dsc60-final-freeze-protocol-v1","as_of_date":"2025-11-30","origin":"2025-11-30","selected_model":"shrink26","baseline_model":"recent13","population":[{{"Product_ID":"...","Store_ID":"..."}}],"target_definition":"...","baseline_definition":"...","primary_metric":"...","coverage_rule":"...","evaluation_rule":"...","artifacts":[{{"path":"relative copied artifact path","role":"...","sha256":"..."}}]}}
Population must exactly match all336 unique current policy keys and unchanged saved model IDs, sorted consistently. Copy the supplied source/model/config/code/plan/correction/dependency files into output assets/ and bind them by exact hash. Required artifact roles: selected_model, model_code, preprocessing_code, evaluation_plan_v1, evaluation_plan_v2, implementation_correction, dependencies and development_source. Also retain analysis_code and feature_definition. Preserve exact bytes. The source model must have the above original hash before and after your work.
Use the existing development target: positive noncancelled recorded units including processing/returned orders, exactduplicate/ID handling as established. Preserve the existing observed-recording-day and missing-store-week treatment, eligibility and equal-key/window seven-day MAE. Specify it precisely so a separate evaluator can implement it from reserved rows without guessing. Neither observed transactions nor date presence establish complete demand; do not invent complete_daily_sales=true, lost-sales counts or historical status knowledge. Common eligibility is identical for both methods; report all exclusions and eligible/population coverage. The broader typed DSC28 completeness/acceptance contract remains separate; do not manufacture authentic parent-contract or final-approval flags.
The predeclared MVP question is whether this fixed candidate has lower pooled absolute weekly recorded-unit forecast error than the same fair baseline in the reserved December test. No invented5% threshold: report relative difference, per-week results, eligible counts, bias, coverage and descriptive uncertainty honestly. Do not promote a runner-up or tune after evaluation. If candidate loses, report failure and retain useful baseline option. This is not a purchasing savings/service-level test.
Issue ALL predictions at fixed2025-11-30 with no later information or December refit. Primary targets are the FOUR nonoverlapping weeks2025-12-01..07,08..14,15..21,22..28. Daily trajectories cover ALL31 December days for both models; last3days/monthwide totals can be secondary only. Selected model has a constant weekly rate at this cutoff; apply its existing daily allocation, not a new seasonal adjustment. Baseline is also frozen from November-only data. Write full-precision numeric values (not rounded display CSV forecasts):
fixed_forecasts.csv EXACT columns: model,Product_ID,Store_ID,as_of_date,origin,target_start,target_end,horizon_days,forecast_units
Every model/key/four-week combination once, horizon_days7; model names shrink26 and recent13 only; all as_of_date/origin2025-11-30.
daily_forecasts.csv EXACT columns: model,Product_ID,Store_ID,as_of_date,origin,date,forecast_units
Every model/key/31Decemberdays once. Values finite, nonnegative; daily sums must agree with each weekly total within1e-9. Also calculate each supplied lead-plus-review coverage total from the same daily trajectory in coverage_forecasts.csv as a separate diagnostic; don't change primary population/horizons.
Write an inference-only generation program and freeze_checks.json verifying IDs, model hash, no post-cutoff sales, exact output schemas/populations, all date boundaries, nonnegative finite predictions, weekly/daily sums and source/dependency identities. No outcomes or accuracy scores belong in this call. Write freeze_summary.md describing what is frozen and what remains unmeasured. Always use only output workspace for writes. Execute your inference-only code and retain actual execution evidence. Do not claim independent validation merely because your own checks pass.
'''


def execute(record):
    """Trace the genuine Data forecast-authoring call; never run model code here."""
    trace = record['trace']
    try:
        result = NativeHost().execute(cwd=Path(record['output']), prompt=Path(trace['prompt_path']).read_text(),
                                     evidence_dir=Path(record['native']), released_root=Path(record['released']), timeout_seconds=None)
    except BaseException as exc:
        finish_call_trace(trace, error=exc)
        raise
    receipt = finish_call_trace(trace, native=result)
    print(json.dumps(receipt['native_execution']), flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    record = stage_forecast(Path(__file__).resolve().parents[1], args.root.resolve())
    print('Prepared no-outcome Data forecast freeze: ' + str(args.root.resolve()), flush=True)
    if not args.prepare_only:
        execute(record)


if __name__ == '__main__':
    main()
