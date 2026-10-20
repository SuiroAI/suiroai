"""Synthetic labels only: never touch the real reserved partition."""
import csv
from datetime import timedelta
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location('reserved_verifier', Path(__file__).parents[2]/'scripts/dsc60_verify_reserved.py')
v = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v)


def csv_bytes(columns, rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out,fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def transaction(tx, product='p0', store='s', day='2025-12-01', qty='1', status='Completed', **extra):
    row = dict.fromkeys(v.ORIGINAL_COLUMNS,'')
    row.update(Transaction_ID=tx,Product_ID=product,Store_ID=store,Order_Date=day,Quantity=qty,Order_Status=status)
    row.update(extra)
    return row


def forecasts(candidate='0', baseline='1'):
    population = {(f'p{i}','s') for i in range(336)}
    weekly = {(m,p,s,d):Decimal(val) for m,val in [('shrink26',candidate),('recent13',baseline)] for p,s in population for d in v.STARTS}
    return population, weekly


def test_target_exposure_status_and_common_exclusions():
    population, weekly = forecasts()
    rows = [transaction('one',qty='2',status=' returned '), transaction('two',qty='3',status='Processing'),
            transaction('three',day='2025-12-08',qty='90',status=' CANCELLED '),
            transaction('four',day='2025-12-15',qty='-2'),transaction('five',day='2025-12-22',qty='0')]
    result = v.score_outcomes(csv_bytes(v.ORIGINAL_COLUMNS,rows),population,weekly)
    assert result['combined']['eligible'] == 1344
    assert Decimal(result['combined']['shrink26']['absolute_error_sum']) == 5
    assert Decimal(result['combined']['recent13']['absolute_error_sum']) == 1347
    assert result['combined']['strictly_lower_mae'] is True
    # An unrelated store cannot create exposure for population store s.
    rows = [transaction(str(i),store='other',day=d.isoformat()) for i,d in enumerate(v.STARTS)]
    with pytest.raises(ValueError,match='No eligible'):
        v.score_outcomes(csv_bytes(v.ORIGINAL_COLUMNS,rows),population,weekly)


def test_exact_original_row_dedup_ignores_lineage_but_conflicts_fail():
    population, weekly = forecasts()
    rows = [transaction(str(i),day=d.isoformat(),_lineage='first') for i,d in enumerate(v.STARTS)]
    rows.append(dict(rows[0],_lineage='different'))
    result = v.score_outcomes(csv_bytes([*v.ORIGINAL_COLUMNS,'_lineage'],rows),population,weekly)
    assert result['exact_duplicates_removed'] == 1
    assert Decimal(result['combined']['shrink26']['absolute_error_sum']) == 4
    rows.append(dict(rows[0],Quantity='2'))
    with pytest.raises(ValueError,match='conflicting'):
        v.score_outcomes(csv_bytes([*v.ORIGINAL_COLUMNS,'_lineage'],rows),population,weekly)


def test_tie_fails_and_full_precision_difference_survives():
    population, weekly = forecasts('1','1')
    rows = [transaction(str(i),day=d.isoformat()) for i,d in enumerate(v.STARTS)]
    raw = csv_bytes(v.ORIGINAL_COLUMNS,rows)
    assert v.score_outcomes(raw,population,weekly)['combined']['strictly_lower_mae'] is False
    population, weekly = forecasts('0.99999999999999999999999999999999999999999999999999','1')
    assert v.score_outcomes(raw,population,weekly)['combined']['strictly_lower_mae'] is True


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path/'bundle'
    root.mkdir()
    population, _ = forecasts()
    model = b'synthetic saved weights, not executed'
    model_hash = v.digest(model)
    protocol = {'as_of_date':'2025-11-30','origin':'2025-11-30','selected_model':'shrink26','baseline_model':'recent13',
        'population':[dict(Product_ID=p,Store_ID=s) for p,s in sorted(population)],
        'artifacts':[{'path':'model.npz','role':'selected_model','sha256':model_hash}]}
    weekrows, dayrows = [], []
    for m in ('shrink26','recent13'):
        for p,s in sorted(population):
            common = dict(model=m,Product_ID=p,Store_ID=s,as_of_date='2025-11-30',origin='2025-11-30')
            for d in v.STARTS:
                weekrows.append(dict(common,target_start=d.isoformat(),target_end=(d+timedelta(days=6)).isoformat(),horizon_days='7',forecast_units='7'))
            for n in range(31):
                dayrows.append(dict(common,date=(v.STARTS[0]+timedelta(days=n)).isoformat(),forecast_units='1'))
    files = {'protocol.json':json.dumps(protocol).encode(),'model.npz':model,
        'fixed_forecasts.csv':csv_bytes(v.WEEK_COLUMNS,weekrows),'daily_forecasts.csv':csv_bytes(v.DAY_COLUMNS,dayrows)}
    for name,raw in files.items(): (root/name).write_bytes(raw)
    manifest = {'format':'dsc60-final-forecast-freeze-v1','selected_model_sha256':model_hash,
        'files':[dict(path=name,bytes=len(raw),sha256=v.digest(raw)) for name,raw in files.items()]}
    raw = json.dumps(manifest).encode()
    (root/'manifest.json').write_bytes(raw)
    spec = {'format':'dsc60-reserved-evaluation-spec-v1','as_of_date':'2025-11-30','selected_model':'shrink26','baseline_model':'recent13',
        'primary_target_starts':[d.isoformat() for d in v.STARTS],'primary_horizon_days':7,'expected_product_store_count':336}
    specraw = json.dumps(spec).encode()
    specpath = tmp_path/'spec.json'
    specpath.write_bytes(specraw)
    return root,v.digest(raw),specpath,v.digest(specraw),model_hash


def test_independent_bundle_validation_and_no_producer_execution(bundle):
    root,manifest,spec,spec_hash,model_hash = bundle
    population, weekly = v.validate_bundle(root,manifest,spec,spec_hash,model_hash)
    assert len(population) == 336 and len(weekly) == 2688


def test_tamper_fails_before_any_outcome_read(bundle,tmp_path):
    root,manifest,spec,spec_hash,model_hash = bundle
    (root/'model.npz').write_bytes(b'tamper')
    with pytest.raises(ValueError,match='hash'):
        v.verify(root,manifest,spec,spec_hash,tmp_path/'does-not-exist.csv','no hash',model_hash)


def test_manifest_external_binding_and_unsafe_member(bundle):
    root,manifest,spec,spec_hash,model_hash = bundle
    with pytest.raises(ValueError,match='hash'):
        v.validate_bundle(root,'0'*64,spec,spec_hash,model_hash)
    raw = json.loads((root/'manifest.json').read_bytes())
    raw['files'][0]['path'] = '../outside'
    data = json.dumps(raw).encode()
    (root/'manifest.json').write_bytes(data)
    with pytest.raises(ValueError,match='Unsafe'):
        v.validate_bundle(root,v.digest(data),spec,spec_hash,model_hash)


def test_source_period_and_nonfinite_rejected():
    population,weekly = forecasts()
    for row in [transaction('bad',day='2025-11-30'),transaction('bad',qty='NaN')]:
        with pytest.raises(ValueError):
            v.score_outcomes(csv_bytes(v.ORIGINAL_COLUMNS,[row]),population,weekly)
