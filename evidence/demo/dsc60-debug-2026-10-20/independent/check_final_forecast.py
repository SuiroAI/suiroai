"""Independently verify Data's fixed forecast bytes before reserved outcomes.

Reads only the frozen protocol, saved model, forecasts and hash-pinned
November-only source copy. Does not execute producer code or inspect December
outcome rows; the baseline reconstruction checks a fixed definition, not search.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-9
"""
import csv
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'artifacts/dsc60-final-evaluation-2026-10-20/forecast'
OUT = BASE / 'output'
DEST = Path(__file__).parent
MODEL_HASH = '93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e'
SALES_HASH = '48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def rows(name):
    with (OUT / name).open(newline='') as handle:
        return list(csv.DictReader(handle))


protocol = json.loads((OUT / 'protocol.json').read_text())
call = json.loads((BASE / 'call.json').read_text())
checks = {}
model_path = OUT / 'assets/selected_model.npz'
checks['protected_model_hash_exact'] = digest(model_path) == digest(BASE / 'released/selected_model.npz') == MODEL_HASH
lineage = []
by_release = {r['relative_path']: r for r in call['trace']['released_files']}
for item in protocol['artifacts']:
    path = OUT / item['path']
    assert path.resolve().is_relative_to(OUT.resolve())
    identity = digest(path)
    source = by_release[path.name]
    lineage.append(identity == item['sha256'] == source['released_byte_sha256'] == digest(BASE / 'released' / path.name))
checks['all_thirteen_protocol_assets_match_dispatch_and_release'] = len(lineage) == 13 and all(lineage)
keys = [(r['Product_ID'], r['Store_ID']) for r in protocol['population']]
policy = rows('assets/input-1.csv')
checks['fixed_336_unique_sorted_policy_keys'] = len(keys) == len(set(keys)) == 336 and keys == sorted((r['Product_ID'], r['Store_ID']) for r in policy)
with np.load(model_path, allow_pickle=False) as model:
    model_keys = list(zip(model['Product_ID'].tolist(), model['Store_ID'].tolist()))
    saved = dict(zip(model_keys, model['weekly_recorded_units'].tolist()))
checks['saved_model_ids_exact_population_order'] = model_keys == keys
rates = { (r['Product_ID'],r['Store_ID']): r for r in rows('frozen_rates.csv') }
checks['selected_rates_bit_exact_to_saved_float64'] = set(rates) == set(keys) and all(float(rates[k]['shrink26_weekly_recorded_units']) == saved[k] for k in keys)
# Guard exact known cutoff-only bytes BEFORE parsing; never open full upload.
assert digest(OUT / 'assets/input-4.csv') == SALES_HASH
with (OUT / 'assets/input-4.csv').open(newline='') as handle:
    reader = csv.DictReader(handle); fields = reader.fieldnames; source_rows = list(reader)
seen = set(); ids = set(); first = {}; observed_weeks = set(); totals = defaultdict(float)
source_dates = []
for r in source_rows:
    signature = tuple(r[f] for f in fields)
    if signature in seen: continue
    seen.add(signature)
    assert r['Transaction_ID'] not in ids, 'Conflicting transaction IDs'
    ids.add(r['Transaction_ID'])
    day = date.fromisoformat(r['Order_Date']); source_dates.append(day)
    assert day <= date(2025,11,30)
    key = r['Product_ID'],r['Store_ID']
    first[key] = min(first.get(key, day), day)
    week = day - timedelta(days=day.weekday())
    observed_weeks.add((r['Store_ID'],week))
    q = float(r['Quantity'])
    if q > 0 and r['Order_Status'].strip().lower() != 'cancelled':
        totals[key,week] += q
weeks = [date(2025,9,1) + timedelta(days=7*i) for i in range(13)]
baseline = {}; counts = {}
for key in keys:
    eligible = [w for w in weeks if w > first[key] and (key[1],w) in observed_weeks]
    counts[key] = len(eligible)
    baseline[key] = sum(totals[key,w] for w in eligible) / len(eligible)
checks['no_post_cutoff_source_rows'] = max(source_dates) == date(2025,11,30)
checks['baseline_all336_fixed_recent13_definition'] = all(abs(float(rates[k]['recent13_weekly_recorded_units']) - baseline[k]) < 1e-12 and int(rates[k]['recent13_observed_weeks']) == counts[k] for k in keys)
weekly = rows('fixed_forecasts.csv'); daily = rows('daily_forecasts.csv'); coverage = rows('coverage_forecasts.csv')
models = ['shrink26','recent13']
week_starts = [date(2025,12,1)+timedelta(days=i*7) for i in range(4)]
expected_week = {(m,*k,str(w),str(w+timedelta(days=6))) for m in models for k in keys for w in week_starts}
expected_day = {(m,*k,str(date(2025,12,1)+timedelta(days=i))) for m in models for k in keys for i in range(31)}
checks['both_models_exact_four_week_population'] = len(weekly)==2688 and {(r['model'],r['Product_ID'],r['Store_ID'],r['target_start'],r['target_end']) for r in weekly} == expected_week
checks['both_models_exact_all31_day_population'] = len(daily)==20832 and {(r['model'],r['Product_ID'],r['Store_ID'],r['date']) for r in daily} == expected_day
checks['all_forecasts_fixed_nov30_finite_nonnegative'] = all(r['as_of_date']==r['origin']=='2025-11-30' and math.isfinite(float(r['forecast_units'])) and float(r['forecast_units'])>=0 for r in weekly+daily+coverage)
checks['all_primary_horizons_seven_days'] = all(r['horizon_days']=='7' for r in weekly)
daily_map = {(r['model'],r['Product_ID'],r['Store_ID'],r['date']):float(r['forecast_units']) for r in daily}
rate_map = {(m,*k):saved[k] if m=='shrink26' else baseline[k] for m in models for k in keys}
checks['all_selected_and_baseline_weekly_values_direct_match'] = all(float(r['forecast_units'])==rate_map[r['model'],r['Product_ID'],r['Store_ID']] for r in weekly)
checks['all_daily_values_direct_rate_divide_seven'] = all(float(r['forecast_units'])==rate_map[r['model'],r['Product_ID'],r['Store_ID']]/7 for r in daily)
max_week_error = 0.; max_coverage_error = 0.
for collection, label in [(weekly,'weekly'),(coverage,'coverage')]:
    for r in collection:
        start,end = date.fromisoformat(r['target_start']),date.fromisoformat(r['target_end'])
        values = [daily_map[r['model'],r['Product_ID'],r['Store_ID'],str(start+timedelta(days=i))] for i in range((end-start).days+1)]
        diff=abs(math.fsum(values)-float(r['forecast_units']))
        if label=='weekly':max_week_error=max(max_week_error,diff)
        else:max_coverage_error=max(max_coverage_error,diff)
checks['daily_sums_match_weekly_and_coverage_within1e9'] = max(max_week_error,max_coverage_error)<1e-9
horizons={(r['Product_ID'],r['Store_ID']):int(r['Supplier_Lead_Time_Days'])+int(r['Review_Period_Days']) for r in policy}
checks['coverage_exact672_policy_horizons'] = len(coverage)==672 and len({(r['model'],r['Product_ID'],r['Store_ID']) for r in coverage})==672 and all(r['model'] in models and int(r['horizon_days'])==horizons[r['Product_ID'],r['Store_ID']] and r['target_start']=='2025-12-01' and date.fromisoformat(r['target_end'])==date(2025,11,30)+timedelta(days=int(r['horizon_days'])) for r in coverage)
report={'scope':'independent_pre_outcome_forecast_verification','all_checks_pass':all(checks.values()),'checks':checks,
 'selected_model_sha256':digest(model_path),'protocol_sha256':digest(OUT/'protocol.json'),
 'baseline_observed_weeks_min':min(counts.values()),'baseline_observed_weeks_max':max(counts.values()),
 'baseline_unknown_key_weeks':sum(13-n for n in counts.values()),
 'max_weekly_daily_difference':max_week_error,'max_coverage_daily_difference':max_coverage_error,
 'forecast_hashes':{n:digest(OUT/n) for n in ['fixed_forecasts.csv','daily_forecasts.csv','coverage_forecasts.csv','frozen_rates.csv']},
 'limits':['No December outcome rows opened; no producer code executed; no new fitting/model choice.',
 'Full-history aggregate exposure in earlier project sessions is documented by dispatch; globally pristine untouched provenance cannot be asserted.',
 'Target is a partial-recording export proxy, not fully observed/unconstrained demand; strict typed DSC28 contract remains separate.',
 'This checks forecast byte/value and fixed baseline arithmetic, not final performance or milestone acceptance.']}
(DEST/'final-freeze-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
