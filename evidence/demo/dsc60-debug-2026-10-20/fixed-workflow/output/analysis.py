"""Reproducible, non-LLM development comparison and illustrative ordering.
Run from this output directory: python analysis.py
Only reads the four released CSVs and prewritten evaluation_plan.json.
"""
from pathlib import Path
import hashlib
import json
import math
import platform
import time
import numpy as np
import pandas as pd

START = time.perf_counter()
OUT = Path(__file__).resolve().parent
SRC = OUT.parent / 'released'
PLAN = json.loads((OUT / 'evaluation_plan.json').read_text())
assert hashlib.sha256(json.dumps(PLAN['comparison_contract']['definition'], sort_keys=True, separators=(',', ':')).encode()).hexdigest() == PLAN['comparison_contract_sha256']
K = ['Product_ID', 'Store_ID']
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + '\n')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

files = [SRC / f'input-{i}.csv' for i in range(1, 5)]
expected = ['333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6',
            '1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a',
            '3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9',
            '48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8']
assert [sha(p) for p in files] == expected
policy, inbound, stock, raw = [pd.read_csv(p) for p in files]
for frame in (policy, stock):
    assert not frame.duplicated(K).any()
assert not inbound.PO_Line_ID.duplicated().any()
keys = pd.MultiIndex.from_frame(policy[K])
assert len(keys) == 336
assert set(keys) == set(pd.MultiIndex.from_frame(stock[K]))
assert set(pd.MultiIndex.from_frame(inbound[K])).issubset(set(keys))
assert set(pd.MultiIndex.from_frame(raw[K])) == set(keys)
assert all((x.Quantity_Unit == 'product_unit').all() for x in (policy, stock, inbound))
assert (policy.Review_Period_Days == 7).all()
assert (policy.Effective_Date == '2025-11-30').all()
assert (stock.Snapshot_Date == '2025-11-30').all()
assert stock.Open_Order_Ledger_Complete.all()
assert (stock[['Usable_On_Hand_Qty','On_Order_Qty']] >= 0).all().all()
assert (policy[['Supplier_Lead_Time_Days','Order_Multiple_Qty','Minimum_Order_Qty']] > 0).all().all()
assert (policy.Safety_Stock_Qty >= 0).all() and (inbound.Incoming_Qty > 0).all()
for c in ['Order_Date','Expected_Arrival_Date']:
    inbound[c] = pd.to_datetime(inbound[c], errors='raise')
assert (inbound.Order_Date <= pd.Timestamp('2025-11-30')).all()
assert (inbound.Expected_Arrival_Date > pd.Timestamp('2025-11-30')).all()
assert (inbound.Expected_Arrival_Date >= inbound.Order_Date).all()
onorder = inbound.groupby(K).Incoming_Qty.sum().reindex(keys, fill_value=0)
assert np.array_equal(onorder.values, stock.set_index(K).reindex(keys).On_Order_Qty.values)
d = raw.drop_duplicates().copy()
d['Order_Date'] = pd.to_datetime(d.Order_Date, errors='raise')
assert d.Order_Date.max() <= pd.Timestamp('2025-11-30')
assert not d.Transaction_ID.duplicated().any()
d['status'] = d.Order_Status.str.strip().str.lower()
assert set(d.status) == {'completed','shipped','returned','processing','cancelled'}
assert (d.Quantity == np.floor(d.Quantity)).all()
first = d.groupby(K).Order_Date.min().reindex(keys)
last = d.groupby(K).Order_Date.max().reindex(keys)
clean = d[(d.Quantity > 0) & (d.status != 'cancelled')].copy()
dates = pd.date_range(d.Order_Date.min(), '2025-11-30', freq='D')

def panel(frame):
    return frame.groupby(['Order_Date']+K).Quantity.sum().unstack(K).reindex(index=dates, columns=keys).fillna(0).astype(float)

y = panel(clean)
# Zero padding before first appearance is only storage: all calculations assert full observed windows.
def window(origin, n, source=y):
    assert (first <= origin - pd.Timedelta(days=n)).all(), 'Unsupported pre-appearance exposure'
    return source.loc[origin-pd.Timedelta(days=n):origin-pd.Timedelta(days=1)]

def factors(origin, source=y):
    previous = source.loc[source.index.year < origin.year].sum(axis=1)
    for year in previous.index.year.unique():
        assert len(previous.loc[str(year)]) == (366 if pd.Timestamp(year,12,31).is_leap_year else 365)
    monthly = previous.groupby(previous.index.month).mean().reindex(range(1,13))
    assert monthly.notna().all() and (monthly > 0).all()
    return monthly / monthly.mean()

def forecasts(origin, horizons=7, source=y):
    horizons = np.broadcast_to(np.asarray(horizons), len(keys))
    result = {f'local{n}': window(origin,n,source).mean().values*horizons for n in [28,91,182,364]}
    w364 = window(origin,364,source).sum()
    product = w364.groupby(level='Product_ID').sum()/w364.sum()
    store = w364.groupby(level='Store_ID').sum()/w364.sum()
    shared = 0.5*result['local364']/horizons + 0.5*window(origin,91,source).sum(axis=1).mean()*np.array([product[p]*store[s] for p,s in keys])
    result['shared'] = shared*horizons
    fac = factors(origin,source)
    past = fac.reindex(pd.date_range(origin-pd.Timedelta(days=91),periods=91).month).mean()
    future = {int(h): fac.reindex(pd.date_range(origin,periods=int(h)).month).mean() for h in np.unique(horizons)}
    result['seasonal'] = result['shared']*np.array([future[int(h)]/past for h in horizons])
    return result

origins = {'initial':pd.date_range('2025-06-30','2025-09-15',freq='W-MON'),
           'later_development':pd.date_range('2025-10-06','2025-11-24',freq='W-MON')}
priority = ['local91','local28','local182','local364','shared','seasonal']
records=[]
for period, starts in origins.items():
    for origin in starts:
        pred = forecasts(origin)
        actual = y.loc[origin:origin+pd.Timedelta(days=6)].sum().values
        for name in priority:
            for j,(product,store) in enumerate(keys):
                records.append((period,origin.strftime('%Y-%m-%d'),product,store,name,float(actual[j]),float(pred[name][j])))
predictions=pd.DataFrame(records,columns=['period','origin']+K+['candidate','actual','prediction'])
predictions['error']=predictions.prediction-predictions.actual
predictions['absolute_error']=predictions.error.abs()
predictions['squared_error']=predictions.error**2
predictions.to_csv(OUT/'development_predictions.csv',index=False)
def metrics(frame):
    return {'MAE':float(frame.absolute_error.mean()), 'RMSE':float(np.sqrt(frame.squared_error.mean())),
            'bias_prediction_minus_recorded':float(frame.error.mean()),
            'WAPE':float(frame.absolute_error.sum()/frame.actual.sum()),'n':len(frame)}
scores={period:{name:metrics(predictions[(predictions.period==period)&(predictions.candidate==name)]) for name in priority} for period in origins}
minimum=min(v['MAE'] for v in scores['initial'].values())
winner=next(n for n in priority if scores['initial'][n]['MAE'] <= minimum+1e-12)
improvements={p:1-scores[p][winner]['MAE']/scores[p]['local91']['MAE'] for p in origins}
selected=winner if all(v>=0.05 for v in improvements.values()) else 'local91'
selection={'initial_winner':winner,'initial_winner_relative_MAE_reduction':improvements,'selected':selected,
           'comparison_contract_sha256':PLAN['comparison_contract_sha256'],
           'rule':PLAN['selection'],'performance_success_ready':False,
           'evaluation_plan_sha256':sha(OUT/'evaluation_plan.json'), 'comparison_contract':PLAN['comparison_contract']}
save('selection_evidence.json',selection)
save('measured_results.json',scores)
origin_scores=predictions.groupby(['period','origin','candidate']).absolute_error.mean().unstack('candidate')
origin_scores.to_csv(OUT/'origin_mae.csv')
rng=np.random.default_rng(260)
stability={}
for period in origins:
    frame=origin_scores.loc[period]
    delta=(frame.local91-frame[winner]).values
    draws=delta[rng.integers(0,len(delta),size=(10000,len(delta)))].mean(axis=1)
    stability[period]={'origins_initial_winner_beats_baseline':int((delta>0).sum()),'origins':len(delta),
                      'paired_origin_block_bootstrap_95pct_MAE_difference_units':np.quantile(draws,[.025,.975]).tolist(),
                      'interpretation':'Development uncertainty only; origins resampled jointly across keys, not independent keys; not final acceptance.'}

# Diagnostic coverage horizon: never read or score a partially observed target.
coverage=[]
horizons=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).values
for period, starts in origins.items():
    for origin in starts:
        valid=origin+pd.to_timedelta(horizons-1,unit='D') <= dates.max()
        pred=forecasts(origin,horizons)
        actual=np.array([y.iloc[:,j].loc[origin:origin+pd.Timedelta(days=int(h)-1)].sum() if valid[j] else np.nan for j,h in enumerate(horizons)])
        for name in priority:
            error=pred[name][valid]-actual[valid]
            coverage.append({'period':period,'origin':str(origin.date()),'candidate':name,'n':int(valid.sum()),
                             'absolute_error_sum':float(np.abs(error).sum()),'squared_error_sum':float((error**2).sum()),'error_sum':float(error.sum())})
pd.DataFrame(coverage).to_csv(OUT/'coverage_horizon_diagnostic.csv',index=False)

# Separate alternative targets/capture assumptions; none can change selected method.
strict=panel(d[(d.Quantity>0)&d.status.isin(['completed','shipped'])&(d.Return_Flag.str.strip().str.lower()!='yes')])
sensitivity={}
for period, starts in origins.items():
    rows=[]
    for origin in starts:
        actual=strict.loc[origin:origin+pd.Timedelta(days=6)].sum().values
        alt=forecasts(origin,source=strict)
        observed_days=(panel(d.assign(Quantity=1)).loc[origin-pd.Timedelta(days=91):origin-pd.Timedelta(days=1)]>0).sum().values
        cond=window(origin,91).sum().values/np.maximum(observed_days,1)*7
        rows.append({'origin':str(origin.date()), 'strict_status_MAE':{n:float(np.abs(v-actual).mean()) for n,v in alt.items()},
                     'baseline_if_zero_days_are_unobserved_mean_prediction':float(cond.mean()),
                     'controlling_baseline_mean_prediction':float(forecasts(origin)['local91'].mean()),
                     'strict_status_baseline_mean_prediction':float(alt['local91'].mean())})
    sensitivity[period]=rows

# December 1 ordering from November 30 end-of-day snapshot.
origin=pd.Timestamp('2025-12-01')
routine_start=time.perf_counter()
rates=forecasts(origin)[selected]/7
names=d.groupby('Product_ID').Product_Name.agg(lambda v: sorted(set(v.dropna().str.strip())) )
assert names.map(len).eq(1).all()
st=stock.set_index(K).reindex(keys)
orders=[]
for j, row in policy.iterrows():
    product, store = row.Product_ID,row.Store_ID
    h=int(horizons[j]); lead=int(row.Supplier_Lead_Time_Days)
    deliveries=inbound[(inbound.Product_ID==product)&(inbound.Store_ID==store)]
    eligible=deliveries[deliveries.Expected_Arrival_Date < origin+pd.Timedelta(days=h)]
    incoming=int(eligible.Incoming_Qty.sum())
    onhand=int(st.iloc[j].Usable_On_Hand_Qty)
    expected=float(rates[j]*h)
    target=expected+int(row.Safety_Stock_Qty)
    gap=max(0.,target-onhand-incoming)
    multiple=int(row.Order_Multiple_Qty)
    qty=0 if gap<=1e-12 else multiple*math.ceil(max(gap,int(row.Minimum_Order_Qty))/multiple)
    # Deliveries available start of due day; demand accrued uniformly within day.
    timing_risk=False
    lowest=onhand
    for day in range(lead):
        known=deliveries.loc[deliveries.Expected_Arrival_Date <= origin+pd.Timedelta(days=day),'Incoming_Qty'].sum()
        projected=onhand+known-rates[j]*(day+1)
        lowest=min(lowest,projected)
        timing_risk |= projected < -1e-12
    orders.append({'Product_ID':product,'Product_Name':names[product][0],'Store_ID':store,'OrderQty':int(qty),
                   'Quantity_Unit':'product_unit','Order_Date':'2025-12-01',
                   'Expected_New_Order_Arrival':str((origin+pd.Timedelta(days=lead)).date()),
                   'Coverage_Days':h,'Forecast_Coverage_Units':round(expected,6),
                   'Usable_On_Hand_Qty':onhand,'Incoming_Within_Coverage_Qty':incoming,
                   'Safety_Stock_Qty':int(row.Safety_Stock_Qty),'Order_Multiple_Qty':multiple,
                   'Minimum_Order_Qty':int(row.Minimum_Order_Qty),
                   'Risk_Before_New_Order_Arrives':bool(timing_risk),
                   'Illustrative_Synthetic_Inputs':True})
orders=pd.DataFrame(orders)
orders.to_csv(OUT/'restocking.csv',index=False)
routine_seconds=time.perf_counter()-routine_start
assert len(orders)==336 and not orders.duplicated(K).any()
assert (orders.OrderQty>=0).all() and np.equal(orders.OrderQty,np.floor(orders.OrderQty)).all()
positive=orders.OrderQty>0
assert (orders.loc[positive,'OrderQty']%orders.loc[positive,'Order_Multiple_Qty']==0).all()
assert (orders.loc[positive,'OrderQty']>=orders.loc[positive,'Minimum_Order_Qty']).all()
assert (orders.OrderQty+orders.Usable_On_Hand_Qty+orders.Incoming_Within_Coverage_Qty+1e-5 >= orders.Forecast_Coverage_Units+orders.Safety_Stock_Qty).all()
# Independent arithmetic check for baseline weekly forecast from filtered transaction rows.
if selected=='local91':
    direct=clean[(clean.Order_Date>=origin-pd.Timedelta(days=91))&(clean.Order_Date<origin)].groupby(K).Quantity.sum().reindex(keys,fill_value=0)/91
    assert np.allclose(direct.values,rates)
    independent_target=direct.values*horizons+policy.Safety_Stock_Qty.values
    independent_qty=[]
    for j,v in enumerate(independent_target):
        available=orders.iloc[j].Usable_On_Hand_Qty+orders.iloc[j].Incoming_Within_Coverage_Qty
        m=int(policy.iloc[j].Order_Multiple_Qty)
        q=0
        while available+q < v-1e-12 or (q>0 and q<int(policy.iloc[j].Minimum_Order_Qty)):
            q+=m
        independent_qty.append(q)
    assert np.array_equal(independent_qty,orders.OrderQty)

save('result.json',{'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha(OUT/'restocking.csv')})
strict_retained=d[(d.Quantity>0)&d.status.isin(['completed','shipped'])&(d.Return_Flag.str.strip().str.lower()!='yes')]
profile={
 'sources':[{'released_file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],
 'raw_rows':len(raw),'deduplicated_rows':len(d),'exact_duplicates_removed':int(raw.duplicated().sum()),
 'remaining_transaction_ID_duplicates':int(d.Transaction_ID.duplicated().sum()),
 'dates':[str(d.Order_Date.min().date()),str(d.Order_Date.max().date())],
 'raw_status_counts':raw.Order_Status.value_counts().to_dict(),'normalized_status_counts':d.status.value_counts().to_dict(),
 'nonpositive_rows':int((d.Quantity<=0).sum()),'nonpositive_units':int(d.loc[d.Quantity<=0,'Quantity'].sum()),
 'cancelled_positive_rows':int(((d.Quantity>0)&(d.status=='cancelled')).sum()),
 'target_rows':len(clean),'target_units':int(clean.Quantity.sum()),'positive_returned_units':int(clean.loc[clean.status=='returned','Quantity'].sum()),
 'positive_processing_units':int(clean.loc[clean.status=='processing','Quantity'].sum()),
 'return_flag_status_cross_tab':pd.crosstab(d.status,d.Return_Flag).to_dict(),
 'quantity_quantiles':d.Quantity.quantile([0,.25,.5,.75,.95,.99,1]).to_dict(),
 'strict_status_units':int(strict_retained.Quantity.sum()),'missing_product_names':int(d.Product_Name.isna().sum()),
 'consistent_nonnull_names_per_product':bool(names.map(len).eq(1).all()),
 'source_pairs':len(keys),'products':len(policy.Product_ID.unique()),'stores':len(policy.Store_ID.unique()),
 'first_appearance_min':str(first.min().date()),'first_appearance_max':str(first.max().date()),'last_appearance_min':str(last.min().date()),
 'all_pairs_full_364_day_history_at_earliest_origin':bool((first<=pd.Timestamp('2025-06-30')-pd.Timedelta(days=364)).all()),
 'network_days_without_any_raw_record':int(len(dates.difference(pd.DatetimeIndex(d.Order_Date.unique())))),
 'policy_stock_exact_key_match':True,'ledger_matches_on_order_for_all_keys':True,'complete_open_ledger_flags':True,
 'synthetic_operational_inputs':True,'inbound_rows':len(inbound),'inbound_units':int(inbound.Incoming_Qty.sum()),
 'inbound_due_range':[str(inbound.Expected_Arrival_Date.min().date()),str(inbound.Expected_Arrival_Date.max().date())],
 'zero_pair_day_fraction_since_latest_first_appearance':float((y.loc[first.max():]==0).values.mean()),
 'weekly_zero_target_fraction':float((predictions[predictions.candidate=='local91'].actual==0).mean()),
 'monthly_target_units':{str(k):int(v) for k,v in clean.groupby(clean.Order_Date.dt.to_period('M')).Quantity.sum().items()},
 'primary_observations_per_candidate':{p:len(starts)*len(keys) for p,starts in origins.items()},
 'status_and_capture_impact':'Complete-extract zero convention is conditional, not proven by file density. Final statuses undated. Forecasts predict recorded orders, not uncensored demand. Returns do not establish usable stock. No historical stockout exposure or backorder quantities.'}
save('source_treatment.json',profile)
seasonality={str(year):factors(pd.Timestamp(year,1,1)).to_dict() for year in [2023,2024,2025]}
save('diagnostics.json',{'stability':stability,'status_and_capture_sensitivity':sensitivity,'seasonal_month_factors_by_available_year':seasonality,
 'capture_scenario':'If recording independently misses 10% of demand, demand rate is recorded rate/0.9 (11.1% higher). Hypothetical only; no capture fraction is identified.',
 'coverage_horizon_note':'Horizon 8-14 days, current synthetic policy held static; exclude individual windows ending after November30. Diagnostic only; primary model selection unchanged.'})
summary={'selected':selected,'initial_winner':winner,'order_units':int(orders.OrderQty.sum()),'positive_order_keys':int(positive.sum()),
         'zero_order_keys':int((~positive).sum()),'risk_before_new_order_keys':int(orders.Risk_Before_New_Order_Arrives.sum()),
         'by_store':orders.groupby('Store_ID').agg(OrderQty=('OrderQty','sum'),Positive_Order_Keys=('OrderQty',lambda x:int((x>0).sum()))).to_dict('index'),
         'largest_orders':orders.sort_values(['OrderQty','Product_ID','Store_ID'],ascending=[False,True,True]).head(10)[K+['Product_Name','OrderQty']].to_dict('records'),
         'deployment_week_forecast_units':float((rates*7).sum()),'deployment_coverage_forecast_units':float((rates*horizons).sum())}
save('ordering_summary.json',summary)
save('runtime.json',{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,
 'machine':platform.machine(),'platform':platform.system(),'total_elapsed_seconds':time.perf_counter()-START,
 'order_calculation_elapsed_seconds_including_all_six_deployment_forecasts':routine_seconds,
 'source_bytes':sum(p.stat().st_size for p in files),'raw_transaction_rows':len(raw),
 'daily_panel_shape':list(y.shape),'routine_model':selected,
 'routine_dependencies':'Python, pandas, numpy, local CSV files; no LLM, network, paid API or model service calls',
 'ongoing_cost':'Ordinary local computer workload; existing hardware, electricity, maintenance or optional hosting remain. No supported monetary rate supplied.',
 'analysis_build_cost':'AI assistance used to build and explain analysis; metered usage and applicable pricing unavailable, cannot estimate charge.'})
print(json.dumps({'scores':scores,'selection':{k:v for k,v in selection.items() if k!='comparison_contract'},'orders':summary,'seconds':time.perf_counter()-START},indent=2))
