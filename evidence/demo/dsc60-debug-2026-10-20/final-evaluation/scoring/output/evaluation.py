#!/usr/bin/env python3
"""One authorized frozen reserved-period evaluation; never fits or changes forecasts.

Only seven explicitly released inputs are opened. Existing execution evidence blocks
another invocation. Decimal arithmetic controls all scores and the strict decision.
"""
import argparse
import csv
import hashlib
import io
import json
import random
import shlex
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 80
D = Decimal
ZERO = D(0)
RELEASES = {
    'protocol.json': (29706, 'f2fc1d7bba8022789b77ffda1ca2f61361dcff84336087745a3bbb4941ff327f'),
    'fixed_forecasts.csv': (231200, '0448042eb22945c0e75c9a88fe874866188d51af877263af946731ce141e4ca8'),
    'daily_forecasts.csv': (1542159, 'ff5e6506cb935ef9fa75d3204da600caf5c49489fd43e7addc1e68d8640ffdef'),
    'freeze_manifest.json': (3551, '2e31be4a68da6e1b69afdf32022107498b6fccb885af34613a10abb8975c91fb'),
    'evaluation-spec.json': (2602, 'ff2a824aa74d3c10e04ea2203247b3088a36ee0e3a8529eac94bf35754d6d02e'),
    'december2025.csv': (183984, '523785126813d13b37f4746066825ce2780f4fe16d3a77a09660bc85943ddd7e'),
    'delivery_context.json': (456, '38631a50d70f641942e7ee322d2c892d5e154f7654bc00c992147712727b0a60'),
}


def digest(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=str, ensure_ascii=False) + '\n')


def csvwrite(path, rows, fields=None):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def days(start, length):
    return [start + timedelta(days=i) for i in range(length)]


def decimal(text):
    value = D(text)
    assert value.is_finite(), 'Nonfinite decimal'
    return value


def summarize(rows, possible):
    eligible = [r for r in rows if r['eligible']]
    n = len(eligible)
    actual = sum((r['actual_recorded_units'] for r in eligible), ZERO)
    sums = {m: sum((r[m + '_absolute_error'] for r in eligible), ZERO)
            for m in ['shrink26', 'recent13']}
    signed = {m: sum((r[m + '_signed_error'] for r in eligible), ZERO)
              for m in ['shrink26', 'recent13']}
    difference = sums['shrink26'] - sums['recent13']
    baseline = sums['recent13']
    return {
        'possible_cells': possible, 'eligible_cells': n,
        'excluded_cells': possible - n,
        'eligible_fraction': D(n) / D(possible) if possible else None,
        'excluded_fraction': D(possible-n) / D(possible) if possible else None,
        'actual_recorded_units_total': actual,
        'absolute_error_sums': sums, 'signed_error_sums_prediction_minus_actual': signed,
        'mae': {m: sums[m]/D(n) if n else None for m in sums},
        'bias_mean_prediction_minus_actual': {m: signed[m]/D(n) if n else None for m in sums},
        'absolute_error_sum_difference_selected_minus_baseline': difference,
        'mae_difference_selected_minus_baseline': difference/D(n) if n else None,
        'signed_relative_difference_selected_over_baseline_minus_one': difference/baseline if baseline else None,
        'gain_baseline_minus_selected_over_baseline': -difference/baseline if baseline else None,
        'strictly_lower_selected_error': sums['shrink26'] < baseline if n else None,
        'zero_baseline_handling': 'Relative difference and gain undefined (null) when baseline error is zero; absolute difference and strict comparison retained.',
        'observed_days_cell_histogram': {str(i): sum(r['observed_days'] == i for r in rows) for i in range(8)},
    }


def percentile(sorted_values, q):
    position = (len(sorted_values)-1)*q
    lo = int(position)
    hi = min(lo+1, len(sorted_values)-1)
    return sorted_values[lo] + (sorted_values[hi]-sorted_values[lo])*(position-lo)


def evaluate(source, out, evidence):
    raw = {}
    for name, (size, sha) in RELEASES.items():
        raw[name] = (source/name).read_bytes()
        check = digest(raw[name])
        evidence['inputs_before'][name] = check
        assert check == {'bytes': size, 'sha256': sha}, 'Released input mismatch: ' + name
    protocol = json.loads(raw['protocol.json'])
    spec = json.loads(raw['evaluation-spec.json'])
    manifest = json.loads(raw['freeze_manifest.json'])
    delivery = json.loads(raw['delivery_context.json'])
    assert protocol['selected_model'] == spec['selected_model'] == 'shrink26'
    assert protocol['baseline_model'] == spec['baseline_model'] == 'recent13'
    assert protocol['origin'] == protocol['as_of_date'] == spec['as_of_date'] == '2025-11-30'
    assert spec['primary_horizon_days'] == 7
    starts = [date.fromisoformat(s) for s in spec['primary_target_starts']]
    assert starts == [date(2025, 12, i) for i in [1, 8, 15, 22]]
    population = [(r['Product_ID'], r['Store_ID']) for r in protocol['population']]
    keys = set(population)
    assert len(keys) == len(population) == spec['expected_product_store_count'] == 336
    models = ('shrink26', 'recent13')
    for record in manifest['files']:
        if record['path'] in raw:
            assert digest(raw[record['path']]) == {'bytes': record['bytes'], 'sha256': record['sha256']}

    def readcsv(name):
        return csv.DictReader(io.StringIO(raw[name].decode('utf-8-sig'), newline=''))

    # Preserve the complete original source-column tuple BEFORE parsing/normalizing.
    reader = readcsv('december2025.csv')
    columns = reader.fieldnames
    original = []
    seen = set()
    source_count = 0
    for r in reader:
        source_count += 1
        assert None not in r and all(v is not None for v in r.values()), 'Malformed CSV row'
        identity = tuple(r[c] for c in columns)
        if identity not in seen:
            original.append(r)
            seen.add(identity)
    transactions = {}
    for r in original:
        tx = r['Transaction_ID']
        assert tx and tx not in transactions, 'Conflicting nonidentical Transaction_ID: ' + tx
        transactions[tx] = True

    presence = defaultdict(set)
    contributions = defaultdict(lambda: ZERO)
    outside = []
    statuses = Counter()
    status_target_units = defaultdict(lambda: ZERO)
    nonpositive = 0
    all_target_units = ZERO
    out_target_units = ZERO
    for r in original:
        day = date.fromisoformat(r['Order_Date'])
        assert date(2025, 12, 1) <= day <= date(2025, 12, 31), 'Non-December source row'
        key = (r['Product_ID'], r['Store_ID'])
        # All source rows establish store exposure, including out-of-population products.
        presence[r['Store_ID']].add(day)
        quantity = decimal(r['Quantity'])
        status = r['Order_Status'].strip().lower()
        statuses[status] += 1
        nonpositive += quantity <= 0
        target = quantity if quantity > 0 and status != 'cancelled' else ZERO
        status_target_units[status] += target
        all_target_units += target
        if key in keys:
            contributions[(key, day)] += target
        else:
            out_target_units += target
            outside.append({'Product_ID': key[0], 'Store_ID': key[1], 'date': day.isoformat(),
                            'Quantity_original': r['Quantity'], 'normalized_status': status,
                            'target_recorded_units': target})

    weekly = {}
    for r in readcsv('fixed_forecasts.csv'):
        assert r['as_of_date'] == r['origin'] == '2025-11-30'
        key = (r['Product_ID'], r['Store_ID'])
        start = date.fromisoformat(r['target_start'])
        assert key in keys and r['model'] in models and start in starts
        assert r['target_end'] == (start+timedelta(days=6)).isoformat() and r['horizon_days'] == '7'
        identity = (r['model'], key, start)
        assert identity not in weekly, 'Duplicate weekly forecast'
        weekly[identity] = (r['forecast_units'], decimal(r['forecast_units']))
    assert len(weekly) == 336*4*2
    daily = {}
    december = days(date(2025, 12, 1), 31)
    for r in readcsv('daily_forecasts.csv'):
        assert r['as_of_date'] == r['origin'] == '2025-11-30'
        key = (r['Product_ID'], r['Store_ID'])
        day = date.fromisoformat(r['date'])
        assert key in keys and r['model'] in models and day in december
        identity = (r['model'], key, day)
        assert identity not in daily, 'Duplicate daily forecast'
        daily[identity] = decimal(r['forecast_units'])
    assert len(daily) == 336*31*2
    max_discrepancy = ZERO
    for (model, key, start), (_, total) in weekly.items():
        discrepancy = abs(sum((daily[(model, key, day)] for day in days(start, 7)), ZERO)-total)
        max_discrepancy = max(max_discrepancy, discrepancy)
        # Manifest's pre-existing arithmetic freeze tolerance is a consistency check ONLY.
        # It never enters primary scoring or the strict decision.
        assert discrepancy <= D('1e-10')*max(D(1), abs(total))

    def make_rows(start, length, primary):
        result = []
        window = days(start, length)
        for key in population:
            observed = len(presence[key[1]].intersection(window))
            eligible = observed > 0
            actual = sum((contributions[(key, day)] for day in window), ZERO) if eligible else ''
            row = {'Product_ID': key[0], 'Store_ID': key[1], 'target_start': start.isoformat(),
                   'target_end': window[-1].isoformat(), 'observed_days': observed,
                   'eligible': eligible, 'eligibility_reason':
                   ('observed_store_window_partial' if observed < length else 'observed_store_window_complete')
                   if eligible else 'entire_store_window_unobserved', 'actual_recorded_units': actual}
            for model in models:
                if primary:
                    text, forecast = weekly[(model, key, start)]
                else:
                    forecast = sum((daily[(model, key, day)] for day in window), ZERO)
                    text = str(forecast)
                row[model+'_forecast_original'] = text
                row[model+'_signed_error'] = forecast-actual if eligible else ''
                row[model+'_absolute_error'] = abs(forecast-actual) if eligible else ''
            result.append(row)
        return result

    rows = []
    week_results = []
    for start in starts:
        cells = make_rows(start, 7, True)
        rows.extend(cells)
        week_results.append({'target_start': start.isoformat(), 'target_end': (start+timedelta(days=6)).isoformat(),
                             **summarize(cells, 336),
                             'complete_7_observed_day_subset': summarize([r for r in cells if r['observed_days'] == 7], 336)})
    primary = summarize(rows, 1344)
    assert primary['eligible_cells'] > 0
    complete = summarize([r for r in rows if r['observed_days'] == 7], 1344)
    csvwrite(out/'per_key_week.csv', rows)
    flat = []
    for week in week_results:
        record = {k: v for k, v in week.items() if not isinstance(v, dict)}
        for name in ['absolute_error_sums', 'signed_error_sums_prediction_minus_actual', 'mae', 'bias_mean_prediction_minus_actual']:
            for model, value in week[name].items():
                record[name+'_'+model] = value
        for i, count in week['observed_days_cell_histogram'].items():
            record['cells_observed_days_'+i] = count
        record['complete_7_observed_day_cells'] = week['complete_7_observed_day_subset']['eligible_cells']
        flat.append(record)
    csvwrite(out/'scores_by_week.csv', flat)
    csvwrite(out/'out_of_population.csv', outside,
             ['Product_ID', 'Store_ID', 'date', 'Quantity_original', 'normalized_status', 'target_recorded_units'])

    # Paired week-cluster descriptive bootstrap. No forecast/target changes.
    rng = random.Random(603)
    draws = []
    bootstrap_rows = []
    for iteration in range(2000):
        indices = [rng.randrange(4) for _ in range(4)]
        count = sum(week_results[i]['eligible_cells'] for i in indices)
        selected_sum = sum(float(week_results[i]['absolute_error_sums']['shrink26']) for i in indices)
        baseline_sum = sum(float(week_results[i]['absolute_error_sums']['recent13']) for i in indices)
        difference = (selected_sum-baseline_sum)/count
        draws.append(difference)
        bootstrap_rows.append({'resample': iteration+1, 'sampled_week_indices_1_based': ' '.join(str(i+1) for i in indices),
                               'eligible_cells': count, 'mae_difference_selected_minus_baseline_float': repr(difference)})
    ordered = sorted(draws)
    bootstrap = {'descriptive_only': True, 'seed': 603, 'resamples': 2000, 'clusters_per_resample': 4,
                 'rng': 'Python random.Random MT19937; four randrange(4) draws per resample',
                 'statistic': '(sum sampled selected absolute errors - sum sampled baseline absolute errors) / sum sampled eligible counts',
                 'percentile_method': 'linear interpolation at (N-1)*q',
                 'percentile_2_5': percentile(ordered, .025), 'percentile_97_5': percentile(ordered, .975),
                 'limits': 'Four weeks and dependence across keys/weeks limit inference; no superiority guarantee; cannot alter Decimal decision.'}
    csvwrite(out/'bootstrap_resamples.csv', bootstrap_rows)

    secondary = {}
    for name, start, length in [('last_three_days', date(2025, 12, 29), 3), ('month', date(2025, 12, 1), 31)]:
        secondary[name] = {'scope': 'secondary only; aggregate daily frozen forecasts on the stated window',
                           'target_start': start.isoformat(), 'target_end': (start+timedelta(days=length-1)).isoformat(),
                           **summarize(make_rows(start, length, False), 336)}
        # Primary histogram is specifically 0..7; longer secondary windows need their full range.
        secondary[name]['observed_days_cell_histogram'] = {
            str(i): sum(len(presence[key[1]].intersection(days(start, length))) == i for key in population)
            for i in range(length+1)}

    limits = [
        'First post-freeze reserved-row scoring, not globally pristine untouched validation: earlier project AI sessions saw pooled full-history quantity summaries.',
        'Recorded positive noncancelled units are not complete demand; missing products on observed store-days contribute zero recorded units, and absent days remain unknown. Partial windows are not rescaled.',
        'Final statuses are used; status knowledge/update timestamps are unavailable. Positive processing/returned rows count regardless of Return_Flag; no return reuse credit.',
        'All forecasts were issued 2025-11-30. Freeze validates bytes/shapes/arithmetic, not independent model semantics or source provenance; no unreleased model or history was sought.',
        'Only four primary week clusters; cross-key and temporal dependence limit descriptive bootstrap inference.',
        'Comparison is against frozen recent13, not the unknown exact customer process. No purchasing savings, service improvement or business-value proof follows.',
        'Typed DSC28 complete-demand/parent-acceptance contract remains separate. No complete_daily_sales=true, authenticated approval, parent acceptance or final acceptance is asserted.',
        'Existing illustrative restocking list is unchanged; no new purchasing approval or automatic deployment.',
    ]
    audit = {'source_columns': columns, 'original_row_count': source_count, 'deduplicated_rows': len(original),
             'exact_original_duplicates_removed': source_count-len(original), 'conflicting_transaction_ids': 0,
             'normalized_status_row_counts': dict(statuses), 'target_units_by_normalized_status': dict(status_target_units),
             'nonpositive_quantity_rows': nonpositive, 'all_population_and_outside_recorded_units_month': all_target_units,
             'out_of_population_rows': len(outside), 'out_of_population_target_units_month': out_target_units,
             'out_of_population_keys': [dict(zip(['Product_ID', 'Store_ID'], key)) for key in sorted({(r['Product_ID'], r['Store_ID']) for r in outside})],
             'out_of_population_disclosure_file': 'out_of_population.csv',
             'population_size_unchanged': len(keys), 'weekly_forecast_rows': len(weekly), 'daily_forecast_rows': len(daily),
             'max_daily_sum_vs_frozen_weekly_discrepancy': max_discrepancy,
             'store_observed_dates_all_deduplicated_rows': {store: sorted(d.isoformat() for d in values) for store, values in sorted(presence.items())},
             'primary_exclusions': [{k: r[k] for k in ['Product_ID', 'Store_ID', 'target_start', 'target_end', 'observed_days', 'eligibility_reason']} for r in rows if not r['eligible']]}
    result = {'format': 'dsc60-single-reserved-evaluation-v1', 'decimal_precision': getcontext().prec,
              'primary_rule': spec['mvp_comparison_rule'], 'models': {'selected': 'shrink26', 'baseline': 'recent13'},
              'as_of_date': '2025-11-30', 'primary': primary, 'per_week': week_results,
              'complete_7_observed_day_subset': complete, 'bootstrap': bootstrap, 'secondary_only': secondary,
              'audit': audit, 'material_limits': limits, 'existing_delivery_facts_unchanged': delivery,
              'sign_definitions': {'mae_difference': 'selected minus baseline; negative favors selected',
                                   'signed_relative_difference': '(selected-baseline)/baseline; negative favors selected',
                                   'gain': '(baseline-selected)/baseline; positive favors selected; negative indicates loss',
                                   'bias': 'mean(prediction minus actual); positive is overprediction'},
              'decimal_serialization': 'Decimal quantities are JSON strings; sums exact, nonterminating quotients rounded only at 80-digit context; fractions recoverable from sums/counts.',
              'mvp_comparison_yes': primary['strictly_lower_selected_error']}
    dump(out/'measured_results.json', result)
    dump(out/'paired_sums.json', {'numeric_policy': result['decimal_serialization'], 'primary': primary,
                                'per_week': week_results, 'complete_7_observed_day_subset': complete,
                                'sign_definitions': result['sign_definitions']})
    write_response(out, result)
    return result


def write_response(out, r):
    p = r['primary']
    gain = p['gain_baseline_minus_selected_over_baseline']
    rel = p['signed_relative_difference_selected_over_baseline_minus_one']
    yes = r['mvp_comparison_yes']
    verdict = 'Yes' if yes else 'No'
    direction = 'lower' if yes else ('higher' if p['mae_difference_selected_minus_baseline'] > 0 else 'equal')
    percent = f'{abs(gain)*100:.4f}%' if gain is not None else 'undefined relative percentage (zero baseline error)'
    lines = [
        f'{verdict}: the frozen selected model (shrink26) has {direction} pooled recorded-unit forecast error than the simple 13-week baseline (recent13). The relative magnitude is {percent}.',
        '',
        'This is the reserved comparison of forecasts issued on 30 November 2025 against recorded product units in four seven-day windows, 1–28 December. Each eligible product/store/week has equal weight. The baseline is the frozen mean over the last 13 complete calendar-week positions, using known weeks; neither method was refitted, reselected or updated.',
        '',
        f"Pooled MAE is {p['mae']['shrink26']:.6f} units for shrink26 versus {p['mae']['recent13']:.6f} for recent13. Selected minus baseline is {p['mae_difference_selected_minus_baseline']:+.6f} units per eligible cell. Signed relative difference is {rel*100:+.4f}% (negative favors selected); gain is {gain*100:+.4f}% (positive means improvement, negative means loss)." if gain is not None else 'The baseline error is zero, so relative difference and percentage gain are undefined; the absolute MAE difference remains authoritative.',
        '',
        f"Exact total absolute errors are {p['absolute_error_sums']['shrink26']} (selected) and {p['absolute_error_sums']['recent13']} (baseline), on the same {p['eligible_cells']} cells. The strict lower-sum rule gives **{verdict.lower()}** to the predeclared MVP comparison; equality would not be improvement. There is no minimum percentage gate.",
        '',
        '| Week | Eligible / 336 | Coverage | Selected MAE | Baseline MAE | Recorded units |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for w in r['per_week']:
        lines.append(f"| {w['target_start']}–{w['target_end']} | {w['eligible_cells']} | {w['eligible_fraction']*100:.2f}% | {w['mae']['shrink26']:.6f} | {w['mae']['recent13']:.6f} | {w['actual_recorded_units_total']} |")
    c = r['complete_7_observed_day_subset']
    audit = r['audit']
    lines += [
        '',
        f"Coverage is {p['eligible_cells']}/1344 possible cells ({p['eligible_fraction']*100:.2f}%); {p['excluded_cells']} cells ({p['excluded_fraction']*100:.2f}%) are excluded because their store-week has no recorded source rows. Partial observed weeks remain without rescaling. All cells, observed-day counts from 0 to 7, and exclusions are in per_key_week.csv. Recorded actual units total {p['actual_recorded_units_total']}. Mean prediction-minus-actual bias is {p['bias_mean_prediction_minus_actual']['shrink26']:+.6f} units for selected and {p['bias_mean_prediction_minus_actual']['recent13']:+.6f} for baseline; positive means overprediction.",
        '',
        f"The secondary complete-seven-observed-day subset has {c['eligible_cells']} cells ({c['eligible_fraction']*100:.2f}% of all possible cells), recorded units {c['actual_recorded_units_total']}, and MAEs {c['mae']['shrink26']:.6f} selected versus {c['mae']['recent13']:.6f} baseline." if c['eligible_cells'] else 'There are no complete-seven-observed-day cells; that secondary subset cannot be scored.',
        '',
        f"The paired week-cluster bootstrap (seed 603; 2,000 resamples of four weeks with replacement) gives a descriptive 2.5th–97.5th percentile interval of [{r['bootstrap']['percentile_2_5']:.6f}, {r['bootstrap']['percentile_97_5']:.6f}] units for selected-minus-baseline pooled MAE. Four weeks and dependence limit inference; this is not a superiority guarantee and cannot override the exact Decimal comparison.",
        '',
        f"Data handling removed {audit['exact_original_duplicates_removed']} exact duplicates using every original column before checking Transaction_ID; no conflicting nonidentical IDs remained. There are {audit['out_of_population_rows']} out-of-population source rows ({audit['out_of_population_target_units_month']} positive noncancelled units across December), disclosed in out_of_population.csv. The fixed 336-key population is unchanged; all deduplicated rows establish store-day presence before status or quantity filtering.",
        '',
        'The target includes positive processing and returned quantities, uses final normalized statuses, and excludes cancelled or nonpositive contributions. A missing product on an observed store-day contributes zero recorded units; it does not prove zero demand. Missing store-days remain unknown, and even seven observed days do not prove complete capture. Status-update timestamps are unavailable. December 29–31 and monthwide results are secondary only in measured_results.json; lead-plus-review diagnostics were not generated because current policy fields were not among the released inputs.',
        '',
        'This is the first post-freeze reserved-row scoring, not globally pristine untouched validation: earlier project AI sessions saw pooled full-history summaries. The freeze establishes input bytes and forecast shape/arithmetic, not independent verification of model internals or source provenance. The separate typed DSC28 complete-demand/parent-acceptance contract remains unresolved here; this evaluation asserts no complete_daily_sales=true, authenticated approval or final acceptance.',
        '',
        'The result compares against recent13, not the customer’s unknown exact current process. It proves neither purchasing savings nor service improvement. ' + ('It supports only the specified forecast-error comparison, with the coverage and inference limits above.' if yes else 'The selected model fails the predeclared improvement comparison; retain the baseline option. No runner-up was promoted.'),
        '',
        'The existing illustrative list remains unchanged: 880 units across 112 positive product-at-store rows, 224 zero orders and 52 prearrival flags. It has not been regenerated and provides no new independent purchasing approval. Stock and policy are synthetic; check real stock, open orders, lead times and ordering policy before any purchasing use. No automatic deployment follows.',
        '',
        'The existing routine local calculation measurement is 0.427337 seconds and 138428416 peak bytes (about 140 MB), measured on a 128 GB host; this was not a constrained 8 GB test. Routine runs require no paid model service, while ordinary computer/electricity costs remain and AI build charges are unknown. This historical runtime is separate from this evaluation’s measured execution time in execution_evidence.json.',
        '',
        'Inspect measured_results.json for exact Decimal results and limits, paired_sums.json and scores_by_week.csv for independently recoverable numerators/denominators, and execution_evidence.json for the actual command, timestamps, runtime and input/output checksums. The script ran once; no model files, development histories or other outcome sources were read.',
    ]
    (out/'response.md').write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--released-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    evidence_path = out/'execution_evidence.json'
    # Refuse another primary execution; preserve failed execution evidence as well.
    with evidence_path.open('x') as f:
        f.write('{"status":"started"}\n')
    started = time.perf_counter()
    evidence = {'status': 'started', 'execution_count': 1,
                'command': shlex.join(['python', *sys.argv]),
                'resolved_python_executable': sys.executable, 'python_version': sys.version,
                'started_at_utc': datetime.now(timezone.utc).isoformat(), 'cwd': str(Path.cwd()),
                'inputs_before': {}, 'inputs_after': {}, 'outputs': {},
                'script': digest(Path(__file__).read_bytes()),
                'scope': 'Exactly seven released input files; no model/history access; one primary scoring.',
                'pre_scoring_tool_failure': 'A source-inspection heredoc was denied temporary-file creation before Python started; no evaluation code existed or outcome scoring occurred. Inspection succeeded using python -c.',
                'checksum_note': 'Evidence file excludes its own checksum to avoid self-reference; output hashes cover every produced artifact other than this evidence file.'}
    try:
        result = evaluate(args.released_dir, out, evidence)
        evidence['status'] = 'success'
        evidence['mvp_comparison_yes'] = result['mvp_comparison_yes']
        print(json.dumps({'status': 'success', 'mvp_comparison_yes': result['mvp_comparison_yes'],
                          'eligible_cells': result['primary']['eligible_cells']}, indent=2))
    except BaseException:
        evidence['status'] = 'failed_no_recheck_authorized'
        evidence['exception'] = traceback.format_exc()
        (out/'failed_execution.txt').write_text(evidence['exception'])
        raise
    finally:
        for name in RELEASES:
            evidence['inputs_after'][name] = digest((args.released_dir/name).read_bytes())
        evidence['input_bytes_preserved'] = evidence['inputs_before'] == evidence['inputs_after']
        for name in ['per_key_week.csv', 'scores_by_week.csv', 'paired_sums.json', 'measured_results.json',
                     'response.md', 'out_of_population.csv', 'bootstrap_resamples.csv', 'failed_execution.txt']:
            path = out/name
            if path.exists():
                evidence['outputs'][name] = digest(path.read_bytes())
        evidence['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        evidence['runtime_seconds'] = time.perf_counter()-started
        dump(evidence_path, evidence)


if __name__ == '__main__':
    main()
