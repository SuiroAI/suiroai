"""DSC-60 independent delivered-output arithmetic, without executing Data code.

https://linear.app/gr3enarr0w/issue/DSC-60
Reads generated outputs only; no raw sales, withheld outcomes or fitting.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import csv
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'artifacts/demo/8d99bf86d50541e19a6afa142746809c/runs/investigation-3146a4fb9c3d4784b1d982e04f91797a/output'
DEST = Path(__file__).parent


def rows(name):
    with (OUT / name).open(newline='') as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


headers, orders = rows('restocking.csv')
result = json.loads((OUT / 'result.json').read_text())
measured = json.loads((OUT / 'measured_results.json').read_text())
summary_headers, summary = rows('comparison_summary.csv')
_, origins = rows('scores_by_origin.csv')
checks = {}
checks['required_result_keys'] = set(result) == {'disposition', 'output_file', 'output_sha256'}
checks['result_points_to_csv'] = result['disposition'] == 'analysis' and result['output_file'] == 'restocking.csv'
actual_hash = hashlib.sha256((OUT / 'restocking.csv').read_bytes()).hexdigest()
checks['csv_checksum_matches_result_and_measured'] = actual_hash == result['output_sha256'] == measured['csv_sha256']
checks['required_csv_headers'] = {'Product_ID', 'Product_Name', 'Store_ID', 'OrderQty', 'Quantity_Unit'} <= set(headers)
checks['unique_product_store_keys'] = len({(r['Product_ID'], r['Store_ID']) for r in orders}) == len(orders)
quantities = [Decimal(r['OrderQty']) for r in orders]
checks['nonnegative_integer_quantities'] = all(q >= 0 and q == q.to_integral_value() for q in quantities)
checks['product_units'] = all(r['Quantity_Unit'] == 'product_unit' for r in orders)
checks['measured_counts_units_match'] = (sum(q > 0 for q in quantities) == measured['positive_orders'] and
    sum(q == 0 for q in quantities) == measured['zero_orders'] and sum(quantities) == measured['total_units'])
checks['review_flag_count_matches'] = sum(r['Review_Before_Arrival'] == 'Yes' for r in orders) == measured['prearrival_shortfall_flags']
pack_mismatches = []
for r, q in zip(orders, quantities):
    multiple, minimum = Decimal(r['Order_Multiple_Units']), Decimal(r['Minimum_Order_Units'])
    if multiple <= 0 or minimum < 0 or q % multiple != 0 or (q > 0 and q < minimum):
        pack_mismatches.append([r['Product_ID'], r['Store_ID'], 'pack_or_minimum'])
    gap = max(Decimal(0), Decimal(r['Forecast_Coverage_Units']) + Decimal(r['Safety_Stock_Units'])
              - Decimal(r['Usable_Stock_Units']) - Decimal(r['Incoming_Within_Coverage_Units']))
    expected = (max(gap, minimum) / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple if gap > 0 else Decimal(0)
    if expected != q:
        pack_mismatches.append([r['Product_ID'], r['Store_ID'], 'rounded_displayed_gap', str(expected), str(q)])
checks['pack_minimum_and_displayed_gap_arithmetic'] = not pack_mismatches
aggregates = defaultdict(lambda: defaultdict(float))
for r in origins:
    g = aggregates[r['variant'], r['model'], r['horizon']]
    n = int(r['n'])
    g['n'] += n
    g['ae'] += n * float(r['mae'])
    g['bias_sum'] += n * float(r['bias'])
    g['actual'] += float(r['actual_units'])
score_mismatches = []
for r in summary:
    g = aggregates[r['variant'], r['model'], r['horizon']]
    expected = {'n': g['n'], 'mae': g['ae'] / g['n'], 'bias': g['bias_sum'] / g['n'],
                'absolute_sum': g['ae'], 'actual_sum': g['actual'], 'wape': g['ae'] / g['actual']}
    for key, value in expected.items():
        if abs(float(r[key]) - value) > 1e-9:
            score_mismatches.append([r['variant'], r['model'], r['horizon'], key])
checks['summary_matches_weighted_origin_scores'] = not score_mismatches
primary = {r['model']: float(r['mae']) for r in summary if r['variant'] == 'gross' and r['horizon'] == '7'}
reduction = 1 - primary[measured['selected']] / primary['recent13']
checks['relative_improvement_arithmetic'] = abs(reduction - measured['relative_MAE_reduction_vs_analytical_baseline']) < 1e-12
checks['primary_mae_values_match'] = all(abs(v - measured['primary_mae'][k]) < 1e-12 for k, v in primary.items())
weekly_by_origin = defaultdict(dict)
month_totals = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
for r in origins:
    if r['variant'] == 'gross' and r['horizon'] == '7' and r['model'] in ['recent13', measured['selected']]:
        weekly_by_origin[r['origin']][r['model']] = float(r['mae'])
        acc = month_totals[r['origin'][:7]][r['model']]
        acc[0] += int(r['n'])
        acc[1] += int(r['n']) * float(r['mae'])
month_summary = {}
for month, models in month_totals.items():
    values = {m: total / n for m, (n, total) in models.items()}
    month_summary[month] = {'weighted_mae': values, 'relative_gain': 1 - values[measured['selected']] / values['recent13']}
coverage = {r['model']: float(r['mae']) for r in summary if r['variant'] == 'gross' and r['horizon'] == 'coverage'}
routine_path = OUT / 'routine_orders.csv'
if routine_path.exists():
    routine_headers, routine_orders = rows('routine_orders.csv')
    checks['routine_orders_same_row_order_and_shared_values'] = (len(routine_orders) == len(orders) and set(routine_headers) <= set(headers) and all(all(a[k] == b[k] for k in routine_headers) for a, b in zip(routine_orders, orders)))
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.cells = []; self.current = None
    def handle_starttag(self, tag, attrs):
        if tag in ['th', 'td']: self.current = ''
    def handle_data(self, data):
        if self.current is not None: self.current += data
    def handle_endtag(self, tag):
        if tag in ['th', 'td'] and self.current is not None:
            self.cells.append(self.current); self.current = None
htmls = list(OUT.glob('presented-html-*.html'))
if len(htmls) == 1:
    table = TableParser(); table.feed(htmls[0].read_text())
    expected_cells = headers + [r[h] for r in orders for h in headers]
    checks['presented_html_exact_headers_row_order_values'] = table.cells == expected_cells
response = OUT / 'response.md'
report = {'scope': 'delivered_output_consistency_only', 'output_path': str(OUT.relative_to(ROOT)), 'checks': checks,
    'all_checks_pass': all(checks.values()), 'rows': len(orders), 'positive_rows': sum(q > 0 for q in quantities),
    'zero_rows': sum(q == 0 for q in quantities), 'total_units': int(sum(quantities)), 'csv_sha256': actual_hash,
    'headers': headers, 'row_order': 'exact delivered order preserved; starts P001/AUS-01; browser equality not yet checked',
    'selected_model': measured['selected'], 'weekly_mae_baseline': primary['recent13'],
    'weekly_mae_selected': primary[measured['selected']], 'weekly_relative_mae_reduction': reduction,
    'weekly_mae_difference_selected_minus_baseline': primary[measured['selected']] - primary['recent13'],
    'selected_beats_baseline_origin_count': sum(v[measured['selected']] < v['recent13'] for v in weekly_by_origin.values()),
    'weekly_origin_count': len(weekly_by_origin), 'monthly_primary_aggregate_arithmetic': month_summary,
    'secondary_coverage_mae': coverage, 'secondary_coverage_relative_gain': 1 - coverage[measured['selected']] / coverage['recent13'],
    'metric_units': 'MAE is recorded product units per evaluated entity-window; WAPE is absolute error sum divided by actual units; bias is signed units per evaluated entity-window.',
    'origin_counts': sorted({r['origin'] for r in origins if r['variant'] == 'gross' and r['horizon'] == '7'}),
    'pack_mismatches': pack_mismatches, 'score_mismatches': score_mismatches,
    'response_available': response.exists(), 'response_sha256': hashlib.sha256(response.read_bytes()).hexdigest() if response.exists() else None, 'routine_schema_note': 'Routine CSV intentionally contains five columns, delivered CSV seventeen; all five shared column values and row order compared exactly.', 'source_output_hashes': {n: hashlib.sha256((OUT / n).read_bytes()).hexdigest()
        for n in ['restocking.csv','result.json','measured_results.json','comparison_summary.csv','scores_by_origin.csv']},
    'limits': ['Checks producer aggregate arithmetic, not truth/completeness of source data or method validity.',
               'Ordering reconstruction uses rounded delivered forecast columns; no source policy/inbound files opened.',
               'Workload figures are producer-reported measurements, not independently timed.',
               'No producer executed, raw sales inspected, models built/selected, or withheld outcomes evaluated.']}
(DEST / 'output-consistency.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
