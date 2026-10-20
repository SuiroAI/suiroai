"""Compare saved Data outputs with separately authored reserved-period arithmetic.

Reconstruct cell targets and eligibility from the pinned released source, compare
all reported Decimal metrics and inspect saved bootstrap draws and receipts.
This reviewer imports only its own verifier and never executes producer code.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
Linear: https://linear.app/gr3enarr0w/issue/DSC-9
"""
import csv
from datetime import date, timedelta
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[4]
LOCAL = Path(__file__).resolve().parent
DATA = ROOT/'artifacts/dsc60-final-evaluation-2026-10-20/evaluation/output'
RELEASE = ROOT/'artifacts/dsc60-final-evaluation-2026-10-20/evaluation/released'
spec = importlib.util.spec_from_file_location('own_reserved',ROOT/'scripts/dsc60_verify_reserved.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def main():
    own = json.loads((LOCAL/'final-reserved-verification.json').read_text())
    measured = json.loads((DATA/'measured_results.json').read_text())
    checks = []
    def require(condition,label):
        if not condition: raise AssertionError(label)
        checks.append(label)
    def scope(a,b,label):
        for name,dataname in [('eligible','eligible_cells'),('possible','possible_cells'),('excluded','excluded_cells'),('eligible_fraction','eligible_fraction'),('strictly_lower_mae','strictly_lower_selected_error')]:
            require(a[name] == b[dataname],label+':'+name)
        for model in ('shrink26','recent13'):
            for name,dataname in [('absolute_error_sum','absolute_error_sums'),('mae','mae'),('mean_signed_error_forecast_minus_recorded','bias_mean_prediction_minus_actual')]:
                require(Decimal(a[model][name]) == Decimal(b[dataname][model]),label+':'+model+':'+name)
        require(Decimal(a['relative_mae_gain']) == Decimal(b['gain_baseline_minus_selected_over_baseline']),label+':gain')
        require(Decimal(a['paired_mae_difference_selected_minus_baseline']) == Decimal(b['mae_difference_selected_minus_baseline']),label+':difference')
    scope(own['combined'],measured['primary'],'pooled')
    for week in measured['per_week']:
        scope(own['weeks'][week['target_start']],week,week['target_start'])
    scope(own['complete_seven_observed_day_subset_secondary'],measured['complete_7_observed_day_subset'],'complete7secondary')
    require(own['coverage_pair_windows_by_observed_days'] == measured['primary']['observed_days_cell_histogram'],'coverage_histogram')
    population,weekly = v.validate_bundle(ROOT/'artifacts/dsc60-final-evaluation-2026-10-20/frozen',own['bindings']['manifest_sha256'],
        ROOT/'evidence/demo/dsc60-debug-2026-10-20/final-evaluation/evaluation-spec.json',own['bindings']['evaluation_spec_sha256'])
    source = v.read_checked(RELEASE/'december2025.csv',own['bindings']['outcomes_sha256'])
    reader = csv.DictReader(source.decode().splitlines())
    require(set(reader.fieldnames)==set(v.ORIGINAL_COLUMNS),'actual_partition_original_columns_only')
    unique = {tuple(r[c] for c in v.ORIGINAL_COLUMNS) for r in reader}
    presence,targets = {},{}
    with localcontext() as ctx:
        ctx.prec=80
        for cells in unique:
            r=dict(zip(v.ORIGINAL_COLUMNS,cells))
            day=date.fromisoformat(r['Order_Date'])
            presence.setdefault(r['Store_ID'],set()).add(day)
            quantity=Decimal(r['Quantity'])
            if quantity>0 and r['Order_Status'].strip().lower()!='cancelled':
                key=(r['Product_ID'],r['Store_ID'],day)
                targets[key]=targets.get(key,Decimal(0))+quantity
        rows=list(csv.DictReader((DATA/'per_key_week.csv').open()))
        expected_keys={(p,s,d) for p,s in population for d in v.STARTS}
        received_keys=set()
        checked_fields=0
        for r in rows:
            p,s,d=r['Product_ID'],r['Store_ID'],date.fromisoformat(r['target_start'])
            key=(p,s,d)
            require(key in expected_keys and key not in received_keys,'unique_valid_cell_'+str(len(received_keys)))
            received_keys.add(key)
            days={d+timedelta(days=i) for i in range(7)}
            observed=len(days & presence.get(s,set()))
            actual=sum((targets.get((p,s,t),Decimal(0)) for t in days),Decimal(0))
            assert r['target_end']==(d+timedelta(days=6)).isoformat()
            assert int(r['observed_days'])==observed and r['eligible']==str(observed>0)
            assert Decimal(r['actual_recorded_units'])==actual
            reason='observed_store_window_complete' if observed==7 else 'observed_store_window_partial'
            assert r['eligibility_reason']==reason
            checked_fields+=6
            for model in ('shrink26','recent13'):
                forecast=weekly[(model,p,s,d)]
                assert Decimal(r[model+'_forecast_original'])==forecast
                assert Decimal(r[model+'_signed_error'])==forecast-actual
                assert Decimal(r[model+'_absolute_error'])==abs(forecast-actual)
                checked_fields+=3
        require(received_keys==expected_keys,'all1344_cell_keys')
        bootstrap=list(csv.DictReader((DATA/'bootstrap_resamples.csv').open()))
        require(len(bootstrap)==2000,'bootstrap_count')
        rng=random.Random(603)
        differences=[]
        maximum_float_difference=0.
        for index,r in enumerate(bootstrap,1):
            drawn=[rng.randrange(4) for _ in range(4)]
            assert int(r['resample'])==index
            assert r['sampled_week_indices_1_based']==' '.join(str(i+1) for i in drawn)
            weeks=[own['weeks'][v.STARTS[i].isoformat()] for i in drawn]
            n=sum(w['eligible'] for w in weeks)
            assert int(r['eligible_cells'])==n
            expected=sum((Decimal(w['shrink26']['absolute_error_sum'])-Decimal(w['recent13']['absolute_error_sum']) for w in weeks),Decimal(0))/n
            saved=float(r['mae_difference_selected_minus_baseline_float'])
            maximum_float_difference=max(maximum_float_difference,abs(saved-float(expected)))
            differences.append(float(expected))
        require(maximum_float_difference<1e-12,'bootstrap_draw_statistics_within_float_roundoff')
        differences.sort()
        for q,name in [(0.025,'percentile_2_5'),(.975,'percentile_97_5')]:
            pos=(len(differences)-1)*q
            lo=int(pos)
            expected=differences[lo]+(differences[lo+1]-differences[lo])*(pos-lo)
            require(abs(expected-measured['bootstrap'][name])<1e-12,'bootstrap_'+name)
    evidence=json.loads((DATA/'execution_evidence.json').read_text())
    require(evidence['status']=='success' and evidence['execution_count']==1,'producer_success_single_execution_receipt')
    require(evidence['inputs_before']==evidence['inputs_after'],'producer_input_hashes_unchanged')
    for name,item in evidence['outputs'].items():
        raw=(DATA/name).read_bytes()
        require(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'receipt_output_hash:'+name)
    report={'format':'dsc60-independent-output-agreement-v1','status':'passed','aggregate_checks':len(checks),
        'per_key_week_rows':len(rows),'cell_fields_checked':checked_fields,'bootstrap_draws_checked':len(bootstrap),
        'max_bootstrap_float_roundoff':maximum_float_difference,
        'producer_metrics_sha256':v.digest((DATA/'measured_results.json').read_bytes()),
        'producer_code_sha256':v.digest((DATA/'evaluation.py').read_bytes()),
        'producer_receipt_sha256':v.digest((DATA/'execution_evidence.json').read_bytes()),
        'independent_result_sha256':v.digest((LOCAL/'final-reserved-verification.json').read_bytes()),
        'scope':'Own target/eligibility/error reconstruction and saved-result comparison; no producer execution; bootstrap descriptive only; no model changes or new primary evaluation.'}
    (LOCAL/'final-reserved-agreement.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
