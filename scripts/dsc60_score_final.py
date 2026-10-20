"""Release reserved rows once, after committed freeze checks, to genuine Data.

The controller verifies pinned manifest/spec and every local frozen asset before
reading the original sales upload, partitions calendar December without changing
CSV field values, and traces one fixed-evaluation NativeHost turn. It calculates
no outcome metrics and never executes model/producer code. Prepare and execute
are separate so the parent can establish prospective freeze authority first.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-9
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess

from suiroai.demo.call_trace import begin_call_trace, finish_call_trace
from suiroai.integration.artifacts import read_stage_file
from suiroai.integration.native import NativeHost

SOURCE_SHA256 = '520fa470ccb7ff5c7d0d8b34d157d15c05c948f7c785e48397ac676bf6cd7707'
MODEL_SHA256 = '93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e'
EVALUATION_ID = 'december2025-evaluation-1'
COMMITTED_MANIFEST = 'evidence/demo/dsc60-debug-2026-10-20/final-evaluation/frozen/manifest.json'


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_once(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)


def _member(root, name):
    if not isinstance(name, str) or not name or '\\' in name or Path(name).is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError('Unsafe frozen member path')
    return read_stage_file(root, name, max_bytes=128 * 1024 * 1024)


def _committed(repo, commit, relative):
    return subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=repo)


def verify_freeze(repo, freeze_root, manifest_sha256, spec_path, spec_sha256, freeze_commit,
                  committed_manifest_path=COMMITTED_MANIFEST):
    """Only hash/protocol checks; this function never opens reserved outcomes."""
    repo, freeze_root, spec_path = Path(repo).resolve(), Path(freeze_root).resolve(), Path(spec_path).resolve()
    manifest_raw = read_stage_file(freeze_root, 'manifest.json', max_bytes=1024 * 1024)
    spec_raw = read_stage_file(spec_path.parent, spec_path.name, max_bytes=1024 * 1024)
    if sha256(manifest_raw).hexdigest() != manifest_sha256 or sha256(spec_raw).hexdigest() != spec_sha256:
        raise ValueError('Pinned freeze manifest or evaluation spec hash mismatch')
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', freeze_commit + '^{commit}'], cwd=repo, text=True).strip()
    spec_relative = str(spec_path.relative_to(repo))
    if _committed(repo, commit, committed_manifest_path) != manifest_raw or _committed(repo, commit, spec_relative) != spec_raw:
        raise ValueError('Local freeze/spec differ from the prospective committed bytes')
    manifest, spec = json.loads(manifest_raw), json.loads(spec_raw)
    if (manifest.get('format') != 'dsc60-final-forecast-freeze-v1'
            or manifest.get('selected_model_sha256') != MODEL_SHA256
            or spec.get('format') != 'dsc60-reserved-evaluation-spec-v1'
            or spec.get('as_of_date') != '2025-11-30'
            or spec.get('selected_model') != 'shrink26' or spec.get('baseline_model') != 'recent13'
            or spec.get('primary_target_starts') != ['2025-12-01','2025-12-08','2025-12-15','2025-12-22']
            or spec.get('primary_horizon_days') != 7 or spec.get('expected_product_store_count') != 336):
        raise ValueError('Frozen evaluation scope or model identity differs')
    checked = {}
    for item in manifest['files']:
        name = item['path']
        if name in checked:
            raise ValueError('Duplicate frozen member')
        raw = _member(freeze_root, name)
        if len(raw) != item['bytes'] or sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Frozen asset hash/size mismatch: ' + name)
        checked[name] = raw
    for name in ['protocol.json', 'fixed_forecasts.csv', 'daily_forecasts.csv']:
        if name not in checked:
            raise ValueError('Required frozen forecast member absent')
    protocol = json.loads(checked['protocol.json'])
    if (protocol.get('as_of_date') != '2025-11-30' or protocol.get('origin') != '2025-11-30'
            or protocol.get('selected_model') != 'shrink26' or protocol.get('baseline_model') != 'recent13'
            or len(protocol.get('population', [])) != 336):
        raise ValueError('Frozen protocol scope differs')
    for asset in protocol['artifacts']:
        if asset['path'] not in checked or sha256(checked[asset['path']]).hexdigest() != asset['sha256']:
            raise ValueError('Protocol asset is missing or differs')
    selected = [a for a in protocol['artifacts'] if a['role'] == 'selected_model']
    if len(selected) != 1 or sha256(checked[selected[0]['path']]).hexdigest() != MODEL_SHA256:
        raise ValueError('Selected parameter artifact changed')
    return {'freeze_commit': commit, 'manifest_sha256': manifest_sha256, 'spec_sha256': spec_sha256,
        'manifest_raw': manifest_raw, 'spec_raw': spec_raw, 'files': checked,
        'frozen_at': manifest['frozen_at'], 'verified_at': _now()}


def evaluation_prompt(released, manifest):
    """Delegate the one fixed Decimal evaluation and narrative to native Data."""
    return f'''Use the attached @Data plugin for ONE final reserved-period evaluation of an already frozen model. This is not modeling, feature work or candidate search.
Read only these immutable files under {released}:
{json.dumps(manifest, indent=2)}
The exact committed evaluation-spec.json and protocol.json govern target/status/returns, duplicate identity, exposure, common eligibility, population, four primary windows and evaluation rule. Read them before writing evaluation code. No model files or development histories are released; never seek them. Never refit, reselect, tune, replace the baseline, alter predictions or regenerate restocking quantities. All forecasts were issued2025-11-30. Preserve every input byte. The last three December days are secondary only.
Read december2025.csv using the original source columns. Deduplicate exact original rows FIRST; then reject conflicting nonidentical Transaction_ID values. Use ALL deduplicated source rows, including cancelled/nonpositive rows, to establish Store_ID/day presence. Target sums positive Quantity with normalized status !=cancelled, including processing/returned. A missing product on an observed store-day is zero recorded contribution, not true zero demand; entirely unobserved store-weeks are excluded identically for both methods, never filled. Retain partial observed weeks without rescaling. Any out-of-population rows must be disclosed; no silent population changes.
Parse forecast decimal strings and Quantity as Decimal, precision at least50digits. Calculate paired absolute-error sums without float or premature rounding. Pooled primary MAE is each method's total absolute error divided by the SAME eligible key/window count. Compare total absolute-error sums DIRECTLY, no epsilon or rounded percentages. Selected strictly lower than baseline answers the predeclared MVP comparison yes; equality is not improvement. Report both signed relative difference and positive gain with clear sign definitions, zero-baseline handling, prediction-minus-actual bias, actual totals, all336x4 possible cells, eligible/excluded cells and fractions, eachweek and complete-7-observed-day subset. Write per_key_week.csv including observed-day counts0..7, explicit eligibility/reason, actual recorded units (blank if unknown), both original forecast strings, both signed and absolute errors (blank if excluded). Write scores_by_week.csv and paired_sums.json so independent Decimal arithmetic is possible. No new metric/target can replace the primary rule.
Use paired week-cluster descriptive bootstrap exactly seed603,2000resamples of four weeks with replacement, recomputing pooled MAE difference from each sampled week's paired error sums/counts, percentile2.5/97.5. Decimal primary sums/rule are authoritative; float bootstrap is descriptive and must not change the strict comparison. Four weeks and dependence limit inference. Report exclusions/coverage even when they weaken the result. No invented minimum5percent gate, purchasing savings or service improvement.
Write evaluation.py, execute it once against these released files, and retain execution_evidence.json with actual command/time/runtime/input-output checksums. Preserve any failed execution and only correct a demonstrated implementation error without changing frozen choices. If a correction would require a second primary evaluation, stop and report the defect; do not perform an unapproved recheck.
Write measured_results.json containing concise structured exact-decimal primary sums/MAEs/bias/differences, perweek/coverage, bootstrap, strict comparison result and material limits. Include existing_delivery_context copied from delivery_context.json for the separate business-writing stage; label its routine measurements as the earlier measured run, not newly timed. Include an explicit analytical_baseline_name=recent13 and never identify it as the customer's exact method. Write response.md as a useful plain-English business result: explain the reserved comparison and how much better or worse versus the simple13-week baseline, distinguishing that from the unknown exact customer process and from business-value proof. Refer to the EXISTING unchanged illustrative880-unit list across112products at stores,224zero orders,52prearrival flags; do not regenerate it or imply new independent purchasing approval. A losing model must be reported truthfully; no runner-up promotion. Mention synthetic stock/policy once with a practical check. Refer to routine local calculation0.427337seconds and138428416peakbytes (about140MB), measured on128GBhost, not a constrained8GBtest; no paid model service for routine runs, ordinary computer/electricity costs remain, AI build charges unknown. No invented hours/money/savings or automatic deployment.
Earlier project sessions saw pooled full-history summaries: the internal evidence must qualify this as first post-freeze reserved-row scoring, not globally pristine untouched validation. The typed DSC28 complete-demand/parent-acceptance contract remains separate. Do not invent complete_daily_sales=true, authenticated approval, final acceptance or hidden model knowledge. Keep the explanation useful without a wall of technical caveats. No new user questions, no other agent/model calls, and no changes outside your output workspace.
'''


def prepare_call(repo, freeze_root, manifest_sha256, spec_path, spec_sha256, freeze_commit,
                 root, source, *, ledger_root=None, committed_manifest_path=COMMITTED_MANIFEST):
    """Validate first, exclusively claim one release, then partition reserved rows."""
    repo, root, source = Path(repo).resolve(), Path(root).absolute(), Path(source).absolute()
    verified = verify_freeze(repo, freeze_root, manifest_sha256, spec_path, spec_sha256,
                             freeze_commit, committed_manifest_path)
    ledger_dir = Path(ledger_root).resolve() if ledger_root else Path(freeze_root).resolve().parent / 'release-ledger'
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / (EVALUATION_ID + '.json')
    ledger = {'format': 'dsc60-one-shot-reserved-release-v1', 'evaluation_id': EVALUATION_ID,
        'status': 'release_claimed', 'claimed_at': _now(), 'freeze_commit': verified['freeze_commit'],
        'manifest_sha256': manifest_sha256, 'spec_sha256': spec_sha256,
        'source_expected_sha256': SOURCE_SHA256, 'root': str(root),
        'historical_exposure': 'Earlier project AI saw pooled full-history summaries; not globally pristine untouched.'}
    _write_once(ledger_path, _json(ledger))
    try:
        # This is intentionally the FIRST full-source read, after all frozen checks
        # and exclusive ledger claim. No outcome quantities are interpreted here.
        raw = read_stage_file(source.parent, source.name, max_bytes=128*1024*1024)
        if sha256(raw).hexdigest() != SOURCE_SHA256:
            raise ValueError('Original sales source does not match the authorized exact hash')
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        columns = reader.fieldnames
        if not columns or len(columns) != len(set(columns)) or 'Order_Date' not in columns:
            raise ValueError('Original CSV schema is malformed')
        partition = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Malformed original source row')
            when = date.fromisoformat(row['Order_Date'])
            if date(2025,12,1) <= when <= date(2025,12,31):
                partition.append(row)
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator='\n')
        writer.writeheader(); writer.writerows(partition)
        partition_bytes = buffer.getvalue().encode()
        # Reparse to prove column order and original field values are unchanged.
        check = csv.DictReader(io.StringIO(partition_bytes.decode(), newline=''))
        if check.fieldnames != columns or list(check) != partition:
            raise ValueError('Reserved partition changed original CSV field values')
        root.mkdir(parents=True, exist_ok=False)
        released, output, native = [root / n for n in ['released','output','native']]
        for directory in [released,output,native]: directory.mkdir(mode=0o700)
        manifest = []
        def release(name, data, role):
            _write_once(released/name, data)
            manifest.append({'relative_path':name,'role':role,'released_bytes':len(data),'released_byte_sha256':sha256(data).hexdigest()})
        for name in ['protocol.json','fixed_forecasts.csv','daily_forecasts.csv']:
            release(name, verified['files'][name], 'frozen_evaluation_input')
        release('freeze_manifest.json', verified['manifest_raw'], 'committed_freeze_manifest')
        release('evaluation-spec.json', verified['spec_raw'], 'committed_evaluation_spec')
        release('december2025.csv', partition_bytes, 'reserved_outcomes_post_freeze')
        delivery = {'existing_recommendation':{'order_units':880,'positive_rows':112,'zero_rows':224,'prearrival_flags':52,
            'synthetic_stock_and_policy':True,'no_new_quantities_authorized':True},
            'routine_measurement':{'seconds_including_imports':0.42733724997378886,'peak_rss_bytes':138428416,
            'measured_host_ram_gb':128,'constrained_8gb_test':False,'paid_routine_model_service_required':False}}
        release('delivery_context.json',_json(delivery),'existing_delivery_facts_not_new_analysis')
        prompt = evaluation_prompt(released,manifest)
        trace = begin_call_trace(native,stage='one_shot_reserved_evaluation',prompt=prompt,manifest=manifest)
        record = {**ledger,'status':'prepared','prepared_at':_now(),'source_sha256':SOURCE_SHA256,
            'reserved_partition_sha256':sha256(partition_bytes).hexdigest(),'reserved_partition_bytes':len(partition_bytes),
            'partition_column_order_and_values_preserved':True,'released':str(released),'output':str(output),
            'native':str(native),'ledger_path':str(ledger_path),'trace':trace,
            'controller_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
            'controller_computed_outcome_metrics':False}
        _write_once(root/'call.json',_json(record))
        # Immutable ledger claim is never removed; progress has a separate file.
        _write_once(ledger_dir/(EVALUATION_ID+'.prepared.json'),_json(record))
        return record
    except BaseException as exc:
        failure={**ledger,'status':'preparation_failed','failed_at':_now(),'error':{'type':type(exc).__name__,'message':str(exc)}}
        _write_once(ledger_dir/(EVALUATION_ID+'.failed.json'),_json(failure))
        raise


def execute(record):
    """Dispatch exactly once; this controller never calculates evaluation scores."""
    root=Path(record['output']).parent
    _write_once(root/'execution-claimed.json',_json({'evaluation_id':EVALUATION_ID,'claimed_at':_now()}))
    for item in record['trace']['released_files']:
        raw=read_stage_file(Path(record['released']),item['relative_path'],max_bytes=128*1024*1024)
        if len(raw)!=item['released_bytes'] or sha256(raw).hexdigest()!=item['released_byte_sha256']:
            raise ValueError('Released evaluation input changed before dispatch')
    trace=record['trace']
    try:
        result=NativeHost().execute(cwd=Path(record['output']),prompt=Path(trace['prompt_path']).read_text(),
            evidence_dir=Path(record['native']),released_root=Path(record['released']),timeout_seconds=None)
    except BaseException as exc:
        finish_call_trace(trace,error=exc)
        raise
    receipt=finish_call_trace(trace,native=result)
    print(json.dumps(receipt['native_execution']),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-root',required=True,type=Path)
    parser.add_argument('--expected-manifest-sha256',required=True)
    parser.add_argument('--spec',required=True,type=Path)
    parser.add_argument('--expected-spec-sha256',required=True)
    parser.add_argument('--freeze-commit',required=True)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--source',type=Path,default=Path('/private/tmp/dsc59-four-inputs/Sales_transactions_2022_2025.csv'))
    parser.add_argument('--ledger-root',type=Path)
    parser.add_argument('--committed-manifest-path',default=COMMITTED_MANIFEST)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--execute-prepared',type=Path,help='Execute one previously prepared call.json instead of preparing')
    args=parser.parse_args()
    if args.execute_prepared:
        record=json.loads(read_stage_file(args.execute_prepared.parent,args.execute_prepared.name,max_bytes=2*1024*1024))
    else:
        record=prepare_call(Path(__file__).resolve().parents[1],args.freeze_root,args.expected_manifest_sha256,
            args.spec,args.expected_spec_sha256,args.freeze_commit,args.root,args.source,
            ledger_root=args.ledger_root,committed_manifest_path=args.committed_manifest_path)
        print('Prepared one-shot reserved release: '+str(args.root),flush=True)
    if not args.prepare_only:execute(record)


if __name__=='__main__':
    main()
