"""Independent reserved-period arithmetic; never import or execute producer code.

Only invoke on real labels after the controller authorizes the committed freeze.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal, localcontext
import hashlib
import io
import json
from pathlib import Path

MODEL_HASH = '93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e'
STARTS = tuple(date(2025, 12, 1) + timedelta(days=7*i) for i in range(4))
ORIGINAL_COLUMNS = 'Transaction_ID Order_ID Customer_ID Customer_Name Customer_Age Customer_Gender Customer_Segment Order_Date Order_Time Sales_Channel Store_ID Store_Name Country Region City Product_ID Product_Name Product_Category Product_Subcategory Quantity Unit_Price Discount_Percentage Sales_Amount Cost_Amount Profit Payment_Method Order_Status Shipping_Method Delivery_Days Return_Flag Return_Reason Sales_Representative Promotion_Code Customer_Rating Inventory_Level Order_Year'.split()
WEEK_COLUMNS = 'model Product_ID Store_ID as_of_date origin target_start target_end horizon_days forecast_units'.split()
DAY_COLUMNS = 'model Product_ID Store_ID as_of_date origin date forecast_units'.split()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_checked(path, expected=None, maximum=256*1024*1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Unsafe, missing or oversized input')
    raw = path.read_bytes()
    if len(raw) > maximum or (expected is not None and digest(raw) != expected):
        raise ValueError('Input hash or size mismatch')
    return raw


def records(raw, required, exact=False):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    names = reader.fieldnames
    if not names or len(names) != len(set(names)) or not set(required) <= set(names) or (exact and set(names) != set(required)):
        raise ValueError('CSV schema mismatch')
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Malformed CSV row')
        yield row


def number(value):
    n = Decimal(value)
    if not n.is_finite():
        raise ValueError('Nonfinite number')
    return n


def safe_member(bundle, name):
    rel = Path(name)
    if rel.is_absolute() or not name or '\\' in name or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('Unsafe manifest path')
    path = bundle / rel
    if any(p.is_symlink() for p in [path, *path.parents] if p != bundle.parent):
        raise ValueError('Symlink in manifest path')
    return path


def validate_bundle(bundle, manifest_sha256, spec_path, spec_sha256, model_sha256=MODEL_HASH):
    """No labels opened here. Independent parsers, not freeze-utility imports."""
    bundle = Path(bundle).absolute()
    manifest = json.loads(read_checked(bundle/'manifest.json', manifest_sha256))
    spec = json.loads(read_checked(spec_path, spec_sha256))
    if manifest.get('format') != 'dsc60-final-forecast-freeze-v1' or manifest.get('selected_model_sha256') != model_sha256:
        raise ValueError('Wrong freeze or saved model')
    if (spec.get('format') != 'dsc60-reserved-evaluation-spec-v1' or spec.get('as_of_date') != '2025-11-30'
        or spec.get('selected_model') != 'shrink26' or spec.get('baseline_model') != 'recent13'
        or spec.get('primary_target_starts') != [d.isoformat() for d in STARTS]
        or spec.get('primary_horizon_days') != 7 or spec.get('expected_product_store_count') != 336):
        raise ValueError('Controller evaluation scope mismatch')
    contents = {}
    for item in manifest['files']:
        name = item['path']
        if name in contents:
            raise ValueError('Duplicate manifest member')
        raw = read_checked(safe_member(bundle, name), item['sha256'])
        if len(raw) != item['bytes']:
            raise ValueError('Manifest byte length mismatch')
        contents[name] = raw
    protocol = json.loads(contents['protocol.json'])
    if (protocol['as_of_date'] != '2025-11-30' or protocol['origin'] != '2025-11-30'
        or protocol['selected_model'] != 'shrink26' or protocol['baseline_model'] != 'recent13'):
        raise ValueError('Protocol identity mismatch')
    population = {(p['Product_ID'], p['Store_ID']) for p in protocol['population']}
    if len(population) != 336 or len(protocol['population']) != 336:
        raise ValueError('Population mismatch')
    selected_assets = [a for a in protocol['artifacts'] if a['role'] == 'selected_model']
    if len(selected_assets) != 1 or digest(contents[selected_assets[0]['path']]) != model_sha256:
        raise ValueError('Selected model bytes differ')
    for asset in protocol['artifacts']:
        if digest(contents[asset['path']]) != asset['sha256']:
            raise ValueError('Protocol asset hash mismatch')
    weekly, daily = {}, {}
    for filename, cols, target in [('fixed_forecasts.csv', WEEK_COLUMNS, weekly), ('daily_forecasts.csv', DAY_COLUMNS, daily)]:
        for r in records(contents[filename], cols, exact=True):
            pair = (r['Product_ID'], r['Store_ID'])
            if pair not in population or r['model'] not in ('shrink26', 'recent13') or r['as_of_date'] != '2025-11-30' or r['origin'] != '2025-11-30':
                raise ValueError('Forecast identity mismatch')
            day = date.fromisoformat(r['target_start'] if target is weekly else r['date'])
            if target is weekly:
                if day not in STARTS or r['target_end'] != (day+timedelta(days=6)).isoformat() or r['horizon_days'] != '7':
                    raise ValueError('Weekly date mismatch')
            elif not date(2025,12,1) <= day <= date(2025,12,31):
                raise ValueError('Daily date mismatch')
            key = (r['model'], *pair, day)
            val = number(r['forecast_units'])
            if key in target or val < 0:
                raise ValueError('Duplicate or negative forecast')
            target[key] = val
    if len(weekly) != 2688 or len(daily) != 20832:
        raise ValueError('Incomplete forecast coverage')
    with localcontext() as ctx:
        ctx.prec = 80
        for (m,p,s,d), val in weekly.items():
            total = sum((daily[(m,p,s,d+timedelta(days=i))] for i in range(7)), Decimal(0))
            if abs(total-val) > Decimal('1e-10')*max(Decimal(1),abs(val)):
                raise ValueError('Weekly daily arithmetic mismatch')
    return population, weekly


def score_outcomes(raw, population, weekly):
    """Recorded outcomes only; store-week exposure includes every deduped row."""
    seen, ids, exposure, quantities, observed_days = set(), {}, set(), {}, {}
    row_count = duplicate_count = 0
    with localcontext() as ctx:
        ctx.prec = 80
        for r in records(raw, ORIGINAL_COLUMNS):
            row_count += 1
            identity = tuple(r[c] for c in ORIGINAL_COLUMNS)
            if identity in seen:
                duplicate_count += 1
                continue
            seen.add(identity)
            tx = r['Transaction_ID']
            if not tx or (tx in ids and ids[tx] != identity):
                raise ValueError('Missing or conflicting transaction identity')
            ids[tx] = identity
            day = date.fromisoformat(r['Order_Date'])
            if not date(2025,12,1) <= day <= date(2025,12,31):
                raise ValueError('Reserved outcome partition contains another period')
            quantity = number(r['Quantity'])
            if day > date(2025,12,28):
                continue
            start = STARTS[(day-date(2025,12,1)).days//7]
            exposure.add((r['Store_ID'], start))
            observed_days.setdefault((r['Store_ID'], start), set()).add(day)
            pair = (r['Product_ID'], r['Store_ID'])
            if pair in population and quantity > 0 and r['Order_Status'].strip().lower() != 'cancelled':
                key = (*pair, start)
                quantities[key] = quantities.get(key, Decimal(0)) + quantity
        def aggregate(starts, complete_only=False):
            eligible = [(p,s,d) for p,s in sorted(population) for d in starts if (s,d) in exposure
                        and (not complete_only or len(observed_days[(s,d)]) == 7)]
            result = {'eligible':len(eligible), 'possible':336*len(starts), 'excluded':336*len(starts)-len(eligible),
                'eligible_fraction':str(Decimal(len(eligible))/(336*len(starts)))}
            if not eligible:
                result.update(shrink26=None, recent13=None, relative_mae_gain=None, strictly_lower_mae=None)
                return result
            totals = {}
            for model in ('shrink26','recent13'):
                errors = [weekly[(model,p,s,d)]-quantities.get((p,s,d),Decimal(0)) for p,s,d in eligible]
                absolute = sum(map(abs,errors), Decimal(0))
                totals[model] = absolute
                result[model] = {'absolute_error_sum':str(absolute), 'mae':str(absolute/len(eligible)), 'mean_signed_error_forecast_minus_recorded':str(sum(errors,Decimal(0))/len(eligible))}
            base = totals['recent13']
            result['paired_mae_difference_selected_minus_baseline'] = str((totals['shrink26']-base)/len(eligible))
            result['relative_mae_gain'] = str((base-totals['shrink26'])/base) if base else None
            result['relative_mae_difference_selected_over_baseline_minus_one'] = str((totals['shrink26']-base)/base) if base else None
            result['strictly_lower_mae'] = totals['shrink26'] < base
            return result
        combined = aggregate(STARTS)
        if not combined['eligible']:
            raise ValueError('No eligible primary outcomes')
        histogram = {str(n):sum(len(observed_days.get((s,d),set())) == n for p,s in population for d in STARTS) for n in range(8)}
        return {'format':'dsc60-independent-reserved-verification-v1', 'combined':combined,
            'coverage_pair_windows_by_observed_days':histogram,
            'complete_seven_observed_day_subset_secondary':aggregate(STARTS,complete_only=True),
            'weeks':{d.isoformat():aggregate([d]) for d in STARTS},
            'input_rows':row_count,'exact_duplicates_removed':duplicate_count,
            'numeric_precision':80,'criterion':'strict paired absolute-error sum comparison; tie fails',
            'qualification':'Reserved period; earlier pooled full-history summaries exposed. No globally pristine untouched or parent acceptance claim.'}


def verify(bundle, manifest_sha256, spec_path, spec_sha256, outcomes, outcomes_sha256, model_sha256=MODEL_HASH):
    population, weekly = validate_bundle(bundle,manifest_sha256,spec_path,spec_sha256,model_sha256)
    # Deliberately last: no outcome read until every frozen input passes validation.
    result = score_outcomes(read_checked(outcomes,outcomes_sha256),population,weekly)
    result['bindings'] = {'manifest_sha256':manifest_sha256,'evaluation_spec_sha256':spec_sha256,'outcomes_sha256':outcomes_sha256,'selected_model_sha256':model_sha256}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','manifest-sha256','evaluation-spec','evaluation-spec-sha256','outcomes','outcomes-sha256','output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = verify(args.bundle,args.manifest_sha256,args.evaluation_spec,args.evaluation_spec_sha256,args.outcomes,args.outcomes_sha256)
    path = Path(args.output)
    with path.open('x') as handle:
        json.dump(result,handle,indent=2)
        handle.write('\n')
    print(json.dumps({'output':str(path),'strictly_lower_mae':result['combined']['strictly_lower_mae'],'eligible':result['combined']['eligible']}))

if __name__ == '__main__':
    main()
