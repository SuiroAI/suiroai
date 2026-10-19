"""Independently recompute DSC-59 second-run development arithmetic.

Read released CSVs and generated evidence without executing generated code.
This checks internal consistency of declared scenario choices, not full report
verification, external semantics, historical availability, or final acceptance.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date, timedelta
import calendar
import csv
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'artifacts/demo/e470ad2e91ca46aaa0df0a8684adb740/runs/investigation-7f611cfeefed4b72a9517568fe51b660'
ASOF = date(2025, 11, 30)
def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))
def key(row):
    return row['Product_ID'], row['Store_ID']
raw, stock, inbound, policy = [read(RUN / 'released' / f'input-{i}.csv') for i in range(1,5)]
output = read(RUN / 'output/restocking_list.csv')
folds = read(RUN / 'output/development_backtest.csv')
scores = read(RUN / 'output/model_comparison.csv')
evidence = json.loads((RUN / 'output/evidence.json').read_text())
seen = set()
sales = []
for row in raw:
    value = tuple(row.items())
    if value not in seen:
        seen.add(value)
        sales.append(row)
gross = [r for r in sales if int(r['Quantity']) > 0 and r['Order_Status'].strip().lower() in {'completed','shipped','returned'}]
net = [r for r in gross if r['Return_Flag'].lower() == 'no']
keys = [key(r) for r in stock]
stocks, policies = [{key(r): r for r in frame} for frame in (stock, policy)]
errors = []
def check(label, actual, expected, tolerance=1e-9):
    if isinstance(actual, (int,float)) and isinstance(expected, (int,float)):
        valid = abs(actual-expected) <= tolerance
    else:
        valid = actual == expected
    if not valid:
        errors.append({'check': label, 'actual': actual, 'expected': expected})
def units(frame, start, end):
    out = Counter()
    for row in frame:
        if start <= date.fromisoformat(row['Order_Date']) <= end:
            out[key(row)] += int(row['Quantity'])
    return out
def rates(frame, cutoff, window, weight, seasonal):
    counts = units(frame, cutoff-timedelta(days=window-1), cutoff)
    products, stores = Counter(), Counter()
    for (product, store), quantity in counts.items():
        products[product] += quantity
        stores[store] += quantity
    total = sum(counts.values())
    factor = 1.0
    if seasonal:
        ratios = []
        month = (cutoff+timedelta(days=1)).month
        for year in range(2022, (cutoff+timedelta(days=1)).year):
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year,month)[1])
            current = sum(units(frame,start,end).values())
            before = sum(units(frame,start-timedelta(days=window),start-timedelta(days=1)).values())
            if current and before and end <= cutoff:
                ratios.append((current/end.day)/(before/window))
        if ratios:
            factor = statistics.median(ratios)
    return {k: ((1-weight)*counts[k]+weight*products[k[0]]*stores[k[1]]/total)/window*factor for k in keys}, factor
# Recompute every development month with training cut strictly before that month.
fold_index = {(row['method'], row['month']): row for row in folds}
for score in scores:
    window, weight, seasonal = int(score['window']), float(score['pool_weight']), score['seasonal']=='True'
    absolute_error = actual_total = predicted_total = 0
    for month in range(6,12):
        start = date(2025,month,1)
        end = date(2025,month,calendar.monthrange(2025,month)[1])
        rate, factor = rates(gross,start-timedelta(days=1),window,weight,seasonal)
        actual = units(gross,start,end)
        predicted = {k: r*end.day for k,r in rate.items()}
        error = sum(abs(predicted[k]-actual[k]) for k in keys)
        total = sum(actual.values())
        row = fold_index[score['method'],start.isoformat()[:7]]
        for field, expected in {'absolute_error':error,'actual_units':total,'predicted_units':sum(predicted.values()),'wape':error/total,'seasonal_factor':factor}.items():
            check(f"fold {score['method']} {month} {field}",float(row[field]),expected)
        absolute_error += error
        actual_total += total
        predicted_total += sum(predicted.values())
    check(score['method']+' WAPE',float(score['WAPE']),absolute_error/actual_total)
    check(score['method']+' bias',float(score['bias']),predicted_total/actual_total-1)
selected = min(scores,key=lambda r:float(r['WAPE']))
rate, _ = rates(gross,ASOF,int(selected['window']),float(selected['pool_weight']),selected['seasonal']=='True')
ledger = defaultdict(list)
for row in inbound:
    ledger[key(row)].append(row)
counts = units(gross, ASOF-timedelta(days=89), ASOF)
totals = Counter()
for row in output:
    k = key(row)
    s,p = stocks[k],policies[k]
    horizon = int(p['Supplier_Lead_Time_Days'])+int(p['Review_Period_Days'])
    credited = sum(int(v['Incoming_Qty']) for v in ledger[k] if date.fromisoformat(v['Expected_Arrival_Date']) <= ASOF+timedelta(days=horizon))
    all_inbound = sum(int(v['Incoming_Qty']) for v in ledger[k])
    target = math.ceil(rate[k]*horizon+int(p['Safety_Stock_Qty'])-1e-10)
    gap = max(0,target-int(s['Usable_On_Hand_Qty'])-credited)
    multiple = int(p['Order_Multiple_Qty'])
    quantity = math.ceil(max(gap,int(p['Minimum_Order_Qty']))/multiple)*multiple if gap else 0
    for field, expected in {'Daily_Rate':rate[k], 'Window_Recorded_Units':counts[k], 'Credited_Inbound':credited, 'Target_Stock':target,'Unrounded_Gap':gap,'Order_Qty':quantity}.items():
        check(f'{k} {field}',float(row[field]),expected)
    check(f'{k} ledger',all_inbound,int(s['On_Order_Qty']))
    balance = minimum_pre = int(s['Usable_On_Hand_Qty'])
    first_gap = ''
    for day in range(1,horizon+1):
        today = ASOF+timedelta(days=day)
        balance += sum(int(v['Incoming_Qty']) for v in ledger[k] if date.fromisoformat(v['Expected_Arrival_Date']) == today)
        balance -= rate[k]
        if day < int(p['Supplier_Lead_Time_Days']):
            minimum_pre = min(minimum_pre,balance)
        if balance < -1e-9 and not first_gap:
            first_gap = today.isoformat()
    check(f'{k} prearrival shortfall',float(row['Pre_New_Arrival_Shortfall']),max(0,-minimum_pre))
    check(f'{k} first gap',row['First_Gap_No_New_Order'],first_gap)
    totals['recommended_units'] += quantity
    totals['recommended_pairs'] += quantity>0
    totals['expedite_pairs'] += minimum_pre < -1e-9
    totals['unrounded_gap_units'] += gap
for field, expected in totals.items():
    check(field,evidence[field],expected)
check('336 output rows',len(output),336)
check('336 unique output keys',len({key(r) for r in output}),336)
check('stock key coverage',{key(r) for r in output},set(stocks))
check('policy key coverage',{key(r) for r in output},set(policies))
for name, value in evidence['source_sha256'].items():
    check('source hash '+name,hashlib.sha256((RUN/'released'/name).read_bytes()).hexdigest(),value)
# Independently check each exported sensitivity quantity using the same declared scenarios.
net_rate, _ = rates(net, ASOF, 90, 1, False)
season_rate, season_factor = rates(gross, ASOF, 90, 1, True)
rival_rate, _ = rates(gross, ASOF, 365, .5, False)
active = defaultdict(set)
for row in sales:
    if ASOF-timedelta(days=89) <= date.fromisoformat(row['Order_Date']) <= ASOF:
        active[row['Store_ID']].add(row['Order_Date'])
def scenario_order(k, daily, delay=0, safety=None):
    st, pol = stocks[k], policies[k]
    horizon = int(pol['Supplier_Lead_Time_Days'])+int(pol['Review_Period_Days'])
    incoming = sum(int(v['Incoming_Qty']) for v in ledger[k] if date.fromisoformat(v['Expected_Arrival_Date'])+timedelta(days=delay) <= ASOF+timedelta(days=horizon))
    target = math.ceil(daily*horizon+(int(pol['Safety_Stock_Qty']) if safety is None else safety)-1e-10)
    gap = max(0,target-int(st['Usable_On_Hand_Qty'])-incoming)
    pack = int(pol['Order_Multiple_Qty'])
    return math.ceil(max(gap,int(pol['Minimum_Order_Qty']))/pack)*pack if gap else 0
sensitivity_totals = Counter()
no_safety_total = 0
for row in output:
    k = key(row)
    scenarios = {'Order_Qty_Low_Demand':(rate[k]*.75,0), 'Order_Qty_High_Demand':(rate[k]*1.25,0),
        'Order_Qty_Returns_Excluded':(net_rate[k],0), 'Order_Qty_Inbound_7d_Late':(rate[k],7),
        'Order_Qty_Store_Active_Day_Sensitivity':(rate[k]*90/len(active[k[1]]),0),
        'Order_Qty_Historical_December_Uplift':(season_rate[k],0), 'Order_Qty_Near_Tied_Model':(rival_rate[k],0)}
    for field, (daily, delay) in scenarios.items():
        expected = scenario_order(k,daily,delay)
        check(str(k)+' '+field,int(row[field]),expected)
        sensitivity_totals[field] += expected
    no_safety_total += scenario_order(k,rate[k],safety=0)
for field, expected in sensitivity_totals.items():
    check('sensitivity total '+field,evidence['sensitivity_units'][field],expected)
check('zero safety units',evidence['no_safety_order_units'],no_safety_total)
check('December uplift',evidence['historical_december_uplift'],season_factor)
summary = {'format':'dsc59-second-run-independent-development-audit-v1','scope':'Read-only independent recomputation of declared development scenario; not final milestone verification','run':str(RUN),'generated_code_executed':False,'arithmetic_and_fold_comparison_pass':not errors,'error_count':len(errors),'errors':errors,'output_rows':len(output),'development_folds':len(folds),'candidate_models':len(scores),'selected_model':selected,'totals':dict(totals),'sensitivity_totals':dict(sensitivity_totals),'source_hygiene':{'raw_rows':len(raw),'exact_duplicates_removed':len(raw)-len(sales),'nonpositive_rows':sum(int(r['Quantity'])<=0 for r in sales),'gross_lines':len(gross),'gross_units':sum(int(r['Quantity']) for r in gross),'latest_sales_date':max(r['Order_Date'] for r in sales)},'limits':['No independent source of transaction status semantics, latent demand, daily completeness, or historical information availability.','Missing recorded observations are a Data-selected recorded-throughput scenario; store-active-day exposure and demand sensitivities do not prove latent demand.','Model selection uses the same six June-November2025 development folds used for score reporting; performance is selection performance, not an untouched validation result.','Selected WAPE is approximately90.39%, poor absolute forecast accuracy; near-tied runner-up differs by only0.0106 percentage points.','Seasonal ratios for early2022 can have less than a full preceding lookback; denominator still uses full configured window. This affects seasonal comparisons, not selected flat model.','This script checks primary and all seven sensitivity quantities plus all66 model-fold scores; it does not establish final acceptance or visually validate the HTML report.']}
(Path(__file__).parent/'second-run-independent-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in {'errors','limits'}},indent=2))
