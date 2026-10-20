"""Deterministic non-LLM restocking analysis. Run with Python, pandas, numpy.
Only four approved CSVs are read. December sales outcomes are never read.
Evaluation plan is immutable input, written before this program's first run.
"""
from pathlib import Path
import json, hashlib, time, math, platform
import numpy as np
import pandas as pd

START = time.perf_counter()
OUT = Path(__file__).resolve().parent
SRC = OUT.parent / 'released'
PLAN = json.loads((OUT / 'evaluation_plan.json').read_text())
KEY = ['Product_ID', 'Store_ID']
CUTOFF = pd.Timestamp('2025-11-30')
ORIGIN = CUTOFF + pd.Timedelta(days=1)
METHODS = ['local_28', 'baseline_91', 'local_182', 'local_364', 'shared', 'seasonal']
def savej(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, default=str, allow_nan=False)+'\n')

files = [SRC/f'input-{i}.csv' for i in range(1,5)]
policy, inbound, inventory, raw = [pd.read_csv(f) for f in files]
assert raw.Order_Date.max() <= '2025-11-30'
s = raw.drop_duplicates().copy()
s['date'] = pd.to_datetime(s.Order_Date, errors='raise')
s['status'] = s.Order_Status.str.strip().str.lower()
s['returned'] = s.Return_Flag.str.strip().str.lower().eq('yes')
assert not s.Transaction_ID.duplicated().any()
assert not policy.duplicated(KEY).any() and not inventory.duplicated(KEY).any()
assert not inbound.PO_Line_ID.duplicated().any()
assert policy[KEY].sort_values(KEY).reset_index(drop=True).equals(inventory[KEY].sort_values(KEY).reset_index(drop=True))
keys = pd.MultiIndex.from_frame(policy.sort_values(KEY)[KEY])
assert len(keys) == 336
assert set(map(tuple,s[KEY].values)) == set(keys)
assert set(map(tuple,inbound[KEY].values)).issubset(set(keys))
for d in [policy, inbound, inventory]:
    assert not d.isna().any().any()
    assert d.Quantity_Unit.eq('product_unit').all()
assert inventory.Open_Order_Ledger_Complete.all()
assert inventory.Snapshot_Date.eq('2025-11-30').all()
assert policy.Effective_Date.eq('2025-11-30').all()
for c in ['Usable_On_Hand_Qty','On_Order_Qty']:
    assert (inventory[c] >= 0).all()
for c in ['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty']:
    assert (policy[c]>0).all()
assert (policy.Safety_Stock_Qty>=0).all()
inbound['due'] = pd.to_datetime(inbound.Expected_Arrival_Date)
assert (pd.to_datetime(inbound.Order_Date)<=CUTOFF).all()
assert (inbound.due > CUTOFF).all() and (inbound.Incoming_Qty>0).all()
ledger = inbound.groupby(KEY).Incoming_Qty.sum().reindex(keys,fill_value=0)
inv = inventory.set_index(KEY).reindex(keys)
assert np.array_equal(ledger.values,inv.On_Order_Qty.values)
p = policy.set_index(KEY).reindex(keys)
eligible = s.loc[(s.Quantity>0)&s.status.ne('cancelled')].copy()
dates = pd.date_range(s.date.min(),CUTOFF)
first = s.groupby(KEY).date.min().reindex(keys)
daily = eligible.groupby(['date']+KEY).Quantity.sum().unstack(KEY).reindex(index=dates,columns=keys)
arr = daily.fillna(0).to_numpy(float)
for k, f in enumerate(first):
    arr[dates<f,k] = np.nan
net = np.nansum(arr,axis=1)
product = np.array(keys.get_level_values(0))
store = np.array(keys.get_level_values(1))
names = s.groupby('Product_ID').Product_Name.agg(lambda x: sorted(x.dropna().unique().tolist()))
assert names.map(len).eq(1).all()
name_map = names.map(lambda x:x[0]).to_dict()

audit = {
 'source_files':[{'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows':len(d)} for f,d in zip(files,[policy,inbound,inventory,raw])],
 'supplied_facts':{'sales_period':[str(s.date.min().date()),str(s.date.max().date())],
   'raw_sales_rows':len(raw),'exact_duplicates_removed':int(raw.duplicated().sum()),
   'status_counts_normalized':s.status.value_counts().to_dict(),
   'quantity_counts':{'negative':int((s.Quantity<0).sum()),'zero':int((s.Quantity==0).sum()),'positive':int((s.Quantity>0).sum())},
   'quantity_range':[int(s.Quantity.min()),int(s.Quantity.max())],
   'eligible_rows':len(eligible),'eligible_units':int(eligible.Quantity.sum()),
   'included_return_flag_rows':int(eligible.returned.sum()),'included_returned_status_rows':int(eligible.status.eq('returned').sum()),
   'included_processing_rows':int(eligible.status.eq('processing').sum()),
   'status_return_cross_counts':s.groupby(['status','returned']).size().rename('rows').reset_index().to_dict('records'),
   'channel_rows':s.Sales_Channel.value_counts().to_dict(),
   'all_source_keys':len(keys),'products':len(set(product)),'stores':len(set(store)),
   'network_dates_without_any_row':[str(x.date()) for x in dates.difference(s.date.unique())],
   'first_appearance_range':[str(first.min().date()),str(first.max().date())],
   'missing_product_names':int(s.Product_Name.isna().sum()),'conflicting_nonmissing_names':0,
   'ledger_matches_on_order_all_keys':True,'ledger_lines':len(inbound),'incoming_units':int(inbound.Incoming_Qty.sum()),
   'stock_total':int(inv.Usable_On_Hand_Qty.sum()),'operational_provenance':policy.Provenance.value_counts().to_dict(),
   'lead_days':sorted(p.Supplier_Lead_Time_Days.unique().tolist()),'review_days':sorted(p.Review_Period_Days.unique().tolist())},
 'supported_interpretations':['Transaction grain is unique Transaction_ID after exact deduplication; repeated order IDs are not assumed duplicate sales.',
   'Consistent one nonmissing name per product supports filling names from same product.',
   'All channels counted at assigned store; fulfillment ownership beyond these assignments is unverified.',
   'On-order aggregate and ledger agree; ledger is used once by due date rather than adding both.'],
 'controller_assumptions':['All operational inputs explicitly synthetic; recommendations are illustrative conditional calculations, not purchase authorization.',
   'Complete extract after first appearance; missing dates represent zero recorded orders only conditionally.',
   'End-of-Nov30 usable stock is available at start Dec1. Delivery is available at start of its due date; lead-time delivery is origin plus lead days.',
   'Current assortment is the fixed retrospective comparison population; current policies used only for illustrative coverage diagnostics.',
   '5 percent dual-period rule supplied for engineering stability, not a business value threshold.'],
 'unknowns_and_effects':{
   'extract_capture':'No coverage proof. Without completeness, absent days are unknown and absolute quantities cannot be identified. Observed-day sensitivity is a stress scenario, not a corrected demand estimate.',
   'status_history':'Cannot tell when old statuses changed; conditional recorded-order target, not historically observable final status reconstruction.',
   'lost_sales':'No historical stockout exposure; cannot infer unconstrained demand or claim availability/savings. Ignore transaction Inventory_Level as not a dated complete stock ledger.',
   'return_stock':'Return flag is not a dated quantity of usable recovered stock; keep original positive orders and use supplied usable stock only.',
   'costs_constraints':'No reliable purchasing currency/budget/capacity/service loss costs; no monetary optimization or savings calculation.',
   'customer_process':'Only last few months stated, no quantity rule. 91-day baseline is an analytical interpretation, not a proven incumbent.',
   'readiness':'All comparison outcomes development. No independent success evaluation or external meaningful improvement threshold supplied.'}}
savej('source_treatment.json',audit)

def month_factors(origin):
    mask = dates.year < origin.year
    # Every date in completed years; zero network days remain conditional zeros.
    m = pd.DataFrame({'month':dates[mask].month,'v':net[mask]}).groupby('month').v.mean().reindex(range(1,13))
    assert m.notna().all() and (m>0).all()
    return (m/m.mean()).to_numpy()

def forecasts(origin, horizon=7, observed_only=False):
    future = pd.date_range(origin,periods=int(horizon))
    local = {}
    for w in [28,91,182,364]:
        a = arr[(dates>=origin-pd.Timedelta(days=w))&(dates<origin)]
        denominator = np.sum(a>0,axis=0) if observed_only else np.sum(~np.isnan(a),axis=0)
        local[w] = np.divide(np.nansum(a,axis=0),denominator,out=np.zeros(len(keys)),where=denominator>0)
    a364=arr[(dates>=origin-pd.Timedelta(days=364))&(dates<origin)]
    volume=np.nansum(a364,axis=0); total=volume.sum()
    ps={x:volume[product==x].sum()/total for x in set(product)}
    ss={x:volume[store==x].sum()/total for x in set(store)}
    mask91=(dates>=origin-pd.Timedelta(days=91))&(dates<origin)
    nr=net[mask91].mean()
    shared=.5*local[364]+.5*nr*np.array([ps[x] for x in product])*np.array([ss[x] for x in store])
    factors=month_factors(origin)
    seasonal=shared*(factors[future.month-1].sum()/factors[dates[mask91].month-1].mean())
    return {'local_28':local[28]*horizon,'baseline_91':local[91]*horizon,
      'local_182':local[182]*horizon,'local_364':local[364]*horizon,
      'shared':shared*horizon,'seasonal':seasonal}

origins = {'initial':pd.date_range('2025-06-30','2025-09-15',freq='W-MON'),
           'later_development':pd.date_range('2025-10-06','2025-11-24',freq='W-MON')}
rows=[]
for period, os in origins.items():
    for origin in os:
        assert (first<origin-pd.Timedelta(days=364)).all()
        for h in sorted(set([7]+(p.Supplier_Lead_Time_Days+p.Review_Period_Days).tolist())):
            end=origin+pd.Timedelta(days=h-1)
            if end>CUTOFF: continue
            truth=np.nansum(arr[(dates>=origin)&(dates<=end)],axis=0)
            pred=forecasts(origin,h)
            use=np.ones(len(keys),bool) if h==7 else (p.Supplier_Lead_Time_Days+p.Review_Period_Days).values==h
            for method in METHODS:
                for i in np.flatnonzero(use):
                    rows.append((period,str(origin.date()),h,method,keys[i][0],keys[i][1],truth[i],pred[method][i]))
comparison=pd.DataFrame(rows,columns=['period','origin','horizon_days','method']+KEY+['actual_units','forecast_units'])
comparison['error']=comparison.forecast_units-comparison.actual_units
comparison['abs_error']=comparison.error.abs()
comparison['squared_error']=comparison.error**2
comparison.to_csv(OUT/'comparison_rows.csv',index=False)
def summarize(d,groups):
    r=d.groupby(groups).agg(MAE=('abs_error','mean'),bias=('error','mean'),MSE=('squared_error','mean'),n=('error','size')).reset_index()
    r['RMSE']=np.sqrt(r.pop('MSE')); return r
weekly=comparison.loc[comparison.horizon_days==7]
scores=summarize(weekly,['period','method'])
scores.to_csv(OUT/'comparison_results.csv',index=False)
summarize(comparison.loc[comparison.horizon_days!=7],['period','method']).to_csv(OUT/'coverage_results.csv',index=False)
summarize(weekly,['period','origin','method']).to_csv(OUT/'origin_results.csv',index=False)
summarize(weekly,['period','method','Product_ID']).to_csv(OUT/'product_results.csv',index=False)
summarize(weekly,['period','method','Store_ID']).to_csv(OUT/'store_results.csv',index=False)
rank_order=['baseline_91','local_28','local_182','local_364','shared','seasonal']
initial=scores.loc[scores.period.eq('initial')].set_index('method').MAE
best=min(initial)
winner=next(m for m in rank_order if abs(initial[m]-best)<=1e-12)
gain={}
for period in origins:
    v=scores.loc[scores.period.eq(period)].set_index('method').MAE
    gain[period]=float(1-v[winner]/v['baseline_91'])
selected=winner if all(g>=.05 for g in gain.values()) else 'baseline_91'
selection={'initial_winner':winner,'winner_MAE_reductions_vs_baseline':gain,'selected':selected,
  'selection_rule':PLAN['selection'],'both_periods_development':True,'recording_readiness_established':False,
  'primary_horizon_days':7,'deployment_horizon_days':sorted(set((p.Supplier_Lead_Time_Days+p.Review_Period_Days).tolist())),
  'horizon_mismatch':'Selection on seven-day recorded units; orders cover supplied lead+review days. Secondary coverage results do not choose model.'}
savej('selection.json',selection)

# Frozen-model exploratory diagnostics: no selection changes.
recent_mask=dates>=ORIGIN-pd.Timedelta(days=91)
recent=arr[recent_mask]
sparse=pd.DataFrame(list(keys),columns=KEY)
sparse['recorded_positive_days_91']=np.sum(recent>0,axis=0)
sparse['units_91']=np.nansum(recent,axis=0)
sparse['absent_or_zero_fraction_91']=1-sparse.recorded_positive_days_91/91
sparse.to_csv(OUT/'sparsity.csv',index=False)
yearly=[]
for year in sorted(set(dates.year)):
    dd=pd.DataFrame({'month':dates[dates.year==year].month,'v':net[dates.year==year]})
    mm=dd.groupby('month').v.mean()
    for month,value in (mm/mm.mean()).items(): yearly.append({'year':year,'month':int(month),'factor':float(value),'complete_year':year<2025})
pd.DataFrame(yearly).to_csv(OUT/'seasonal_stability.csv',index=False)
sens=[]
for period,os in origins.items():
    for origin in os:
        # Alternative denominator is NOT validated truth; scores retain main conditional targets.
        alt=forecasts(origin,7,observed_only=True)['baseline_91']
        actual=np.nansum(arr[(dates>=origin)&(dates<origin+pd.Timedelta(days=7))],axis=0)
        sens.append({'period':period,'origin':str(origin.date()),'MAE_observed_day_denominator':float(np.mean(abs(alt-actual))),
                     'mean_weekly_units':float(alt.mean())})
pd.DataFrame(sens).to_csv(OUT/'missing_date_sensitivity.csv',index=False)

def order_qty(target,stock, incoming, safety, multiple, minimum):
    short=max(0.,target+safety-stock-incoming)
    return 0 if short<=1e-10 else int(math.ceil(max(short,minimum)/multiple)*multiple)

out=[]
for i,k in enumerate(keys):
    pol=p.iloc[i]; stock=int(inv.iloc[i].Usable_On_Hand_Qty)
    lead=int(pol.Supplier_Lead_Time_Days); h=int(lead+pol.Review_Period_Days)
    due=inbound.loc[(inbound.Product_ID==k[0])&(inbound.Store_ID==k[1])]
    end=ORIGIN+pd.Timedelta(days=h-1)
    inc=int(due.loc[due.due<=end].Incoming_Qty.sum())
    fc=forecasts(ORIGIN,h)
    target=float(fc[selected][i]); week=float(forecasts(ORIGIN,7)[selected][i])
    args=(stock,inc,int(pol.Safety_Stock_Qty),int(pol.Order_Multiple_Qty),int(pol.Minimum_Order_Qty))
    qty=order_qty(target,*args)
    pre=[]
    for day in range(lead):
        today=ORIGIN+pd.Timedelta(days=day)
        received=int(due.loc[due.due<=today].Incoming_Qty.sum())
        consumed=float(forecasts(ORIGIN,day+1)[selected][i])
        pre.append(stock+received-consumed)
    before=max(0.,-min(pre))
    # Empirical development error spread, pooled across keys with the same coverage length.
    errors=comparison.loc[(comparison.method==selected)&(comparison.horizon_days==h),'error']
    low=max(0.,target-float(errors.quantile(.9)))
    high=max(0.,target-float(errors.quantile(.1)))
    alt=float(forecasts(ORIGIN,h,True)['baseline_91'][i])
    out.append({'Product_ID':k[0],'Product_Name':name_map[k[0]],'Store_ID':k[1],
      'OrderQty':qty,'Quantity_Unit':'product_unit','Forecast_Next_7_Days':round(week,4),
      'Coverage_Days':h,'Forecast_Coverage_Units':round(target,4),'Usable_Stock':stock,
      'Incoming_Within_Coverage':inc,'Safety_Stock':args[2],'Order_Multiple':args[3],'Minimum_Order':args[4],
      'Expected_New_Order_Arrival':str((ORIGIN+pd.Timedelta(days=lead)).date()),
      'Expected_Shortfall_Before_Arrival':round(before,4),
      'Priority':'check faster delivery or transfer' if before>1e-10 else ('order' if qty else 'no order'),
      'OrderQty_28_Day_Average_Scenario':order_qty(float(fc['local_28'][i]),*args),
      'OrderQty_182_Day_Average_Scenario':order_qty(float(fc['local_182'][i]),*args),
      'OrderQty_Lower_Recorded_Units_Scenario':order_qty(low,*args),
      'OrderQty_Higher_Recorded_Units_Scenario':order_qty(high,*args),
      'OrderQty_Observed_Days_Only_Stress':order_qty(alt,*args),
      'Operational_Inputs':'synthetic'})
restock=pd.DataFrame(out).sort_values(['OrderQty','Product_ID','Store_ID'],ascending=[False,True,True])
restock.to_csv(OUT/'restocking.csv',index=False)
check=pd.read_csv(OUT/'restocking.csv')
assert len(check)==336 and not check.duplicated(KEY).any()
assert (check.OrderQty>=0).all() and (check.OrderQty%1==0).all()
assert ((check.OrderQty==0)|((check.OrderQty>=check.Minimum_Order)&(check.OrderQty%check.Order_Multiple==0))).all()
# Independent baseline calculation and independent rounding check for every recommendation.
if selected=='baseline_91':
    manual=eligible.loc[(eligible.date>=ORIGIN-pd.Timedelta(days=91))&(eligible.date<ORIGIN)].groupby(KEY).Quantity.sum().reindex(keys,fill_value=0)/91
    assert np.allclose(manual.values*7,forecasts(ORIGIN,7)[selected])
for _,r in check.iterrows():
    need=max(0,r.Forecast_Coverage_Units+r.Safety_Stock-r.Usable_Stock-r.Incoming_Within_Coverage)
    independently=0 if need<1e-4 else int(np.ceil(max(need,r.Minimum_Order)/r.Order_Multiple)*r.Order_Multiple)
    assert independently==r.OrderQty
sha=hashlib.sha256((OUT/'restocking.csv').read_bytes()).hexdigest()
savej('result.json',{'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha})
summary={'selected_method':selected,'order_units':int(check.OrderQty.sum()),'keys_to_order':int((check.OrderQty>0).sum()),
 'zero_orders':int((check.OrderQty==0).sum()),'prearrival_shortfall_keys':int((check.Expected_Shortfall_Before_Arrival>0).sum()),
 'prearrival_shortfall_units':float(check.Expected_Shortfall_Before_Arrival.sum()),
 'forecast_next7_total':float(check.Forecast_Next_7_Days.sum()),
 'recent_positive_days_median':float(sparse.recorded_positive_days_91.median()),
 'recent_absent_zero_fraction':float(sparse.absent_or_zero_fraction_91.mean()),
 '28_day_order_total':int(check.OrderQty_28_Day_Average_Scenario.sum()),
 '182_day_order_total':int(check.OrderQty_182_Day_Average_Scenario.sum()),
 'observed_days_stress_order_total':int(check.OrderQty_Observed_Days_Only_Stress.sum()),
 'empirical_residual_scenarios':'10th/90th pooled development actual-minus-forecast errors by coverage length, not calibrated prediction intervals; no tuning/selection use.',
 'runtime_seconds':time.perf_counter()-START,'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,
 'routine_compute':'Local deterministic pandas/numpy on 17406 input transaction rows, 336 keys and daily arrays; no network or paid model API calls. Runtime includes audit comparisons and list generation.',
 'build_AI_cost':'Unknown: no observed token usage or applicable billing rates supplied. Separate from routine compute.',
 'csv_sha256':sha}
savej('run_summary.json',summary)
print(scores.to_string(index=False)); print(json.dumps(selection,indent=2)); print(json.dumps(summary,indent=2))
