"""Deterministic non-LLM restocking analysis; run from this output directory.
Dependencies: Python 3, numpy, pandas. Sources restricted to ../released/input-[1-4].csv.
Evaluation plan is required and is never overwritten by this program.
"""
import hashlib
import json
import math
import platform
import time
from pathlib import Path
import numpy as np
import pandas as pd

START = time.perf_counter()
OUT = Path(__file__).resolve().parent
SRC = OUT.parent / 'released'
KEY = ['Product_ID', 'Store_ID']
NAMES = ['local28', 'local91', 'local182', 'local364', 'shared', 'seasonal']
TIES = ['local91', 'local28', 'local182', 'local364', 'shared', 'seasonal']
CUTOFF = pd.Timestamp('2025-11-30')
ORIGIN = pd.Timestamp('2025-12-01')
PLAN = json.loads((OUT/'evaluation_plan.json').read_text())
assert PLAN['comparison_contract_sha256'] == '5619c9d87d3534a7835bb0e58d7d81617a6d1830a2de325c1113662edf98fbeb'

def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, indent=2, default=str, allow_nan=False)+'\n')

def load():
    return [pd.read_csv(SRC/f'input-{i}.csv') for i in range(1,5)]

policy, inbound, stock, raw = load()
keys = pd.MultiIndex.from_frame(policy[KEY])
assert len(keys) == 336 and keys.is_unique
assert pd.MultiIndex.from_frame(stock[KEY]).is_unique
assert set(keys) == set(pd.MultiIndex.from_frame(stock[KEY]))
assert set(pd.MultiIndex.from_frame(raw[KEY])) == set(keys)
assert set(pd.MultiIndex.from_frame(inbound[KEY])).issubset(set(keys))
assert inbound.PO_Line_ID.is_unique
assert (policy.Review_Period_Days == 7).all()
assert (policy.Supplier_Lead_Time_Days >= 0).all()
assert (policy.Order_Multiple_Qty > 0).all()
assert (policy.Minimum_Order_Qty >= 0).all()
assert (stock[['Usable_On_Hand_Qty','On_Order_Qty']] >= 0).all().all()
assert stock.Open_Order_Ledger_Complete.all()
for df in [policy,inbound,stock]:
    assert set(df.Quantity_Unit) == {'product_unit'}
assert pd.to_datetime(policy.Effective_Date).max() <= CUTOFF
assert set(stock.Snapshot_Date) == {'2025-11-30'}
assert pd.to_datetime(inbound.Order_Date).max() <= CUTOFF
assert (pd.to_datetime(inbound.Expected_Arrival_Date) > CUTOFF).all()
assert (pd.to_datetime(inbound.Expected_Arrival_Date) >= pd.to_datetime(inbound.Order_Date)).all()
assert (inbound.Incoming_Qty > 0).all()
dedup = raw.drop_duplicates().copy()
dedup['status'] = dedup.Order_Status.str.strip().str.lower()
dedup['returned_flag'] = dedup.Return_Flag.str.strip().str.lower().eq('yes')
dedup['date'] = pd.to_datetime(dedup.Order_Date, errors='raise')
assert dedup.date.max() <= CUTOFF
assert not dedup.Transaction_ID.duplicated().any()
assert dedup.date.dt.year.eq(dedup.Order_Year).all()
first = dedup.groupby(KEY).date.min().reindex(keys)
dates = pd.date_range(dedup.date.min(), CUTOFF)
assert first.max() <= pd.Timestamp('2025-06-30')-pd.Timedelta(days=364), 'Contract needs full exposure for all keys'
assert dedup.groupby('Product_ID').Product_Name.nunique().eq(1).all()
product_names = dedup.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name
positive = dedup.Quantity.gt(0)
target_rows = dedup[positive & dedup.status.ne('cancelled')]

def matrix(rows):
    daily = rows.groupby(['date']+KEY).Quantity.sum().unstack(KEY).reindex(index=dates, columns=keys).fillna(0.0)
    # Pre-appearance exposure remains unknown, not zero. All comparison windows start after every first appearance.
    for j, f in enumerate(first):
        daily.iloc[dates < f,j] = np.nan
    return daily

daily = matrix(target_rows)
product_codes = np.array(keys.get_level_values('Product_ID'))
store_codes = np.array(keys.get_level_values('Store_ID'))
horizons = (policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy(int)

def predict(data, origin, horizon=7, capture_active_only=False):
    origin = pd.Timestamp(origin)
    history = data.loc[data.index < origin]
    def local(days):
        window = history.loc[history.index >= origin-pd.Timedelta(days=days)]
        return window.where(window > 0).mean().fillna(0).to_numpy() if capture_active_only else window.mean().to_numpy()
    rates = {f'local{d}': local(d) for d in [28,91,182,364]}
    recent91 = history.loc[history.index >= origin-pd.Timedelta(days=91)]
    recent364 = history.loc[history.index >= origin-pd.Timedelta(days=364)]
    totals = recent364.sum().to_numpy()
    total = totals.sum()
    products = {p:totals[product_codes==p].sum()/total for p in np.unique(product_codes)}
    stores = {s:totals[store_codes==s].sum()/total for s in np.unique(store_codes)}
    network91 = recent91.sum(axis=1).mean()
    rates['shared'] = .5*rates['local364'] + .5*network91*np.array([products[p]*stores[s] for p,s in keys])
    past_years = history.loc[history.index.year < origin.year].sum(axis=1)
    factors = past_years.groupby(past_years.index.month).mean().reindex(range(1,13))
    assert not factors.isna().any()
    factors = factors/factors.mean()
    trailing_factor = np.mean([factors.loc[d.month] for d in pd.date_range(origin-pd.Timedelta(days=91), periods=91)])
    h = np.broadcast_to(np.asarray(horizon), (len(keys),)).astype(int)
    future_factor = np.array([np.mean([factors.loc[d.month] for d in pd.date_range(origin, periods=int(n))]) for n in h])
    predictions = {n:r*h for n,r in rates.items()}
    predictions['seasonal'] = rates['shared']*h*future_factor/trailing_factor
    return predictions

origins = {'initial':pd.date_range('2025-06-30','2025-09-15',freq='W-MON'),
           'later_development':pd.date_range('2025-10-06','2025-11-24',freq='W-MON')}

def evaluate(data, coverage=False, active=False, retain=False):
    records = []
    for period, os in origins.items():
        for origin in os:
            h = horizons if coverage else np.full(len(keys),7)
            if origin+pd.Timedelta(days=int(h.max())-1) > CUTOFF:
                continue  # Identical full-population fully observed origins for all six candidates.
            pred = predict(data, origin, h, active)
            actual = np.array([data.iloc[(data.index>=origin)&(data.index<origin+pd.Timedelta(days=int(h[j]))),j].sum() for j in range(len(keys))])
            for model in NAMES:
                for j, (p,s) in enumerate(keys):
                    records.append((period,str(origin.date()),model,p,s,int(h[j]),float(actual[j]),float(pred[model][j])))
    frame = pd.DataFrame(records, columns=['Period','Origin','Model']+KEY+['HorizonDays','Actual','Prediction'])
    frame['Error'] = frame.Prediction-frame.Actual
    summary=[]
    for (period,model), g in frame.groupby(['Period','Model'],sort=False):
        err=g.Error.to_numpy()
        summary.append({'Period':period,'Model':model,'MAE':float(abs(err).mean()),'RMSE':float(np.sqrt((err**2).mean())),
                        'Bias':float(err.mean()),'WAPE':float(abs(err).sum()/g.Actual.sum()),'KeyOrigins':len(g),
                        'Origins':g.Origin.nunique()})
    return pd.DataFrame(summary), frame

scores,predictions = evaluate(daily)
scores.to_csv(OUT/'comparison_scores.csv',index=False)
predictions.to_csv(OUT/'development_predictions.csv',index=False)
origin_mae = predictions.assign(AbsError=predictions.Error.abs()).groupby(['Period','Origin','Model']).AbsError.mean().reset_index()
origin_mae.to_csv(OUT/'origin_mae.csv',index=False)
scoremap = scores.set_index(['Period','Model']).MAE
best = min(scoremap['initial'])
winner = next(n for n in TIES if scoremap['initial',n] <= best+1e-12)
improvements={p:float(1-scoremap[p,winner]/scoremap[p,'local91']) for p in origins}
selected = winner if all(v>=.05 for v in improvements.values()) else 'local91'
coverage_scores,coverage_predictions = evaluate(daily,coverage=True)
coverage_scores.to_csv(OUT/'coverage_scores.csv',index=False)
coverage_predictions.to_csv(OUT/'coverage_predictions.csv',index=False)

sensitivities = []
for label,rows in [('completed_shipped_only',dedup[positive & dedup.status.isin(['completed','shipped'])]),
                   ('exclude_return_status_and_flags',target_rows[target_rows.status.ne('returned') & ~target_rows.returned_flag])]:
    sc,_ = evaluate(matrix(rows))
    sc['Sensitivity']=label
    sensitivities.append(sc)
active_scores,_=evaluate(daily,active=True)
active_scores['Sensitivity']='active_days_only_capture_stress_not_primary'
sensitivities.append(active_scores)
pd.concat(sensitivities).to_csv(OUT/'sensitivity_scores.csv',index=False)

rng=np.random.default_rng(60)
stability={}
for p in origins:
    pivot=origin_mae[origin_mae.Period.eq(p)].pivot(index='Origin',columns='Model',values='AbsError')
    sampled=rng.integers(0,len(pivot),size=(5000,len(pivot)))
    gains=1-pivot[winner].to_numpy()[sampled].mean(axis=1)/pivot.local91.to_numpy()[sampled].mean(axis=1)
    stability[p]={'winner_better_origins':int((pivot[winner]<pivot.local91).sum()),'origin_count':len(pivot),
                  'paired_origin_bootstrap_95pct_improvement':np.quantile(gains,[.025,.975]).tolist(),
                  'interpretation':'Descriptive origin resampling of inspected development, not untouched acceptance.'}

def ordering(policy,inbound,stock,data,model):
    order=policy.merge(stock,on=KEY,validate='one_to_one',suffixes=('','_stock'))
    assert list(map(tuple,order[KEY].to_numpy())) == list(keys)
    h=(order.Supplier_Lead_Time_Days+order.Review_Period_Days).to_numpy(int)
    pred=predict(data,ORIGIN,h)[model]
    weekly=predict(data,ORIGIN,7)[model]
    due=pd.to_datetime(inbound.Expected_Arrival_Date)
    ledger_groups={k:g for k,g in inbound.assign(due=due).groupby(KEY)}
    rows=[]
    for j,k in enumerate(keys):
        r=order.iloc[j]
        ledger=ledger_groups.get(k,pd.DataFrame(columns=['due','Incoming_Qty']))
        end=ORIGIN+pd.Timedelta(days=int(h[j])-1)
        receipts=ledger[(ledger.due>=ORIGIN)&(ledger.due<=end)]
        incoming=int(receipts.Incoming_Qty.sum())
        assert incoming<=r.On_Order_Qty
        short=max(0,float(pred[j]+r.Safety_Stock_Qty-r.Usable_On_Hand_Qty-incoming))
        multiple=int(r.Order_Multiple_Qty)
        qty=0 if short<=1e-12 else multiple*math.ceil(max(short,r.Minimum_Order_Qty)/multiple-1e-12)
        balance=float(r.Usable_On_Hand_Qty)
        first_short=None
        lead=int(r.Supplier_Lead_Time_Days)
        daily_rate=pred[j]/h[j] # Selected local mean has constant rate. Seasonal option spreads its horizon mean.
        for day in pd.date_range(ORIGIN,periods=lead):
            balance+=float(ledger.loc[ledger.due.eq(day),'Incoming_Qty'].sum())
            balance-=daily_rate
            if balance < -1e-12 and first_short is None:
                first_short=day.date().isoformat()
        rows.append({'Product_ID':k[0],'Product_Name':product_names[k[0]],'Store_ID':k[1],
          'OrderQty':qty,'Quantity_Unit':'product_unit','Forecast_Next_7_Days':round(weekly[j],4),
          'Coverage_Days':int(h[j]),'Forecast_Coverage_Units':round(pred[j],4),
          'Usable_On_Hand':int(r.Usable_On_Hand_Qty),'Incoming_Within_Coverage':incoming,
          'Safety_Stock':int(r.Safety_Stock_Qty),'Order_Multiple':multiple,'Minimum_Order':int(r.Minimum_Order_Qty),
          'Expected_New_Arrival':(ORIGIN+pd.Timedelta(days=lead)).date().isoformat(),
          'Coverage_End':end.date().isoformat(),'Shortage_Before_New_Arrival':first_short is not None,
          'First_Projected_Shortage_Date':first_short or '', 'Input_Basis':'supplied_synthetic_stock_and_policy'})
    return pd.DataFrame(rows)

ledger_total=inbound.groupby(KEY).Incoming_Qty.sum().reindex(keys,fill_value=0).to_numpy()
stock_sorted=stock.set_index(KEY).reindex(keys)
assert np.array_equal(ledger_total,stock_sorted.On_Order_Qty.to_numpy())

# Measure a real complete local routine: input loading, preparation, selected prediction and order calculation.
routine_start=time.perf_counter()
rp,ri,rs,rt=load()
rt=rt.drop_duplicates()
rt['status']=rt.Order_Status.str.strip().str.lower()
rt['date']=pd.to_datetime(rt.Order_Date)
rd=matrix(rt[rt.Quantity.gt(0)&rt.status.ne('cancelled')])
orders=ordering(rp,ri,rs,rd,selected)
routine_seconds=time.perf_counter()-routine_start
orders=orders.sort_values(['Shortage_Before_New_Arrival','OrderQty','Product_ID','Store_ID'],ascending=[False,False,True,True])
orders.to_csv(OUT/'restocking.csv',index=False,lineterminator='\n')
check=pd.read_csv(OUT/'restocking.csv',keep_default_na=False)
assert len(check)==336 and not check.duplicated(KEY).any()
assert (check.OrderQty>=0).all() and (check.OrderQty%1==0).all()
assert (check.OrderQty%check.Order_Multiple==0).all()
assert ((check.OrderQty==0)|(check.OrderQty>=check.Minimum_Order)).all()
assert set(pd.MultiIndex.from_frame(check[KEY]))==set(keys)
sha=hashlib.sha256((OUT/'restocking.csv').read_bytes()).hexdigest()
save('result.json',{'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha})

# Independent direct-source arithmetic checks for every selected local91 order, not only shared helper reuse.
if selected=='local91':
    direct=target_rows[target_rows.date.between('2025-09-01','2025-11-30')].groupby(KEY).Quantity.sum().reindex(keys,fill_value=0)/91
    bykey=check.set_index(KEY).reindex(keys)
    assert np.allclose(bykey.Forecast_Next_7_Days,direct*7,atol=.000051)
    desired=np.maximum(0,direct.to_numpy()*horizons+policy.Safety_Stock_Qty.to_numpy()-stock_sorted.Usable_On_Hand_Qty.to_numpy()-ledger_total)
    independently_ordered=np.where(desired>1e-12,np.ceil(np.maximum(desired,policy.Minimum_Order_Qty.to_numpy())/policy.Order_Multiple_Qty.to_numpy()-1e-12)*policy.Order_Multiple_Qty.to_numpy(),0).astype(int)
    assert np.array_equal(bykey.OrderQty.to_numpy(),independently_ordered)
    for origin in pd.DatetimeIndex([origins['initial'][0],origins['later_development'][-1]]):
        history=target_rows[target_rows.date.ge(origin-pd.Timedelta(days=91)) & target_rows.date.lt(origin)]
        direct_pred=history.groupby(KEY).Quantity.sum().reindex(keys,fill_value=0).to_numpy()*7/91
        retained=predictions[predictions.Origin.eq(str(origin.date()))&predictions.Model.eq('local91')].set_index(KEY).reindex(keys)
        assert np.allclose(direct_pred,retained.Prediction)

yearly=[]
network=daily.sum(axis=1)
for year in [2022,2023,2024]:
    n=network[network.index.year==year]
    f=n.groupby(n.index.month).mean()
    f=f/f.mean()
    yearly.extend([{'Year':year,'Month':int(m),'Factor':float(v)} for m,v in f.items()])
pd.DataFrame(yearly).to_csv(OUT/'seasonal_factor_stability.csv',index=False)
weekly_actual=predictions[predictions.Model.eq('local91')]
active_cells=np.array([[d>=f for f in first] for d in dates])
diagnostics={
 'source_files':{f'input-{i}.csv':{'sha256':hashlib.sha256((SRC/f'input-{i}.csv').read_bytes()).hexdigest(),'bytes':(SRC/f'input-{i}.csv').stat().st_size} for i in range(1,5)},
 'raw_rows':len(raw),'exact_duplicates_removed':len(raw)-len(dedup),'nonpositive_rows':int((~positive).sum()),
 'cancelled_positive_rows_excluded':int((positive & dedup.status.eq('cancelled')).sum()),
 'normalized_statuses':dedup.status.value_counts().to_dict(),
 'positive_rows_by_status':target_rows.status.value_counts().to_dict(),
 'target_rows':len(target_rows),'target_total_units':int(target_rows.Quantity.sum()),
 'quantity_range':[int(dedup.Quantity.min()),int(dedup.Quantity.max())],
 'return_flag_yes':int(dedup.returned_flag.sum()),'return_flag_yes_nonreturned_status':int((dedup.returned_flag & dedup.status.ne('returned')).sum()),
 'source_date_bounds':[str(dedup.date.min().date()),str(dedup.date.max().date())],
 'first_key_appearance_bounds':[str(first.min().date()),str(first.max().date())],
 'source_days_present':int(dedup.date.nunique()),'calendar_days':len(dates),
 'absent_target_pair_days_after_first_appearance_fraction':float(((daily.to_numpy()==0)&active_cells).sum()/active_cells.sum()),
 'zero_evaluation_week_fraction':float(weekly_actual.Actual.eq(0).mean()),
 'key_week_actual_quantiles':weekly_actual.Actual.quantile([0,.5,.9,.95,.99,1]).to_dict(),
 'selected_absolute_week_error_quantiles':predictions[predictions.Model.eq(selected)].Error.abs().quantile([.5,.9,.95,.99]).to_dict(),
 'ledger_units':int(inbound.Incoming_Qty.sum()),'stock_on_order_units':int(stock.On_Order_Qty.sum()),'ledger_mismatched_keys':int((ledger_total!=stock_sorted.On_Order_Qty.to_numpy()).sum()),
 'stock_rows':len(stock),'policy_rows':len(policy),'ledger_rows':len(inbound),
 'operational_provenance':{name:df.Provenance.value_counts().to_dict() for name,df in [('policy',policy),('stock',stock),('ledger',inbound)]},
 'complete_ledger_flags':int(stock.Open_Order_Ledger_Complete.sum()),
 'missing_product_name_rows':int(dedup.Product_Name.isna().sum()),'product_name_conflicts':int((dedup.groupby('Product_ID').Product_Name.nunique()>1).sum()),
 'key_coverage':'All 336 keys in sales, stock and policy; inbound subset; no join multiplication.',
 'ignored_columns':'Transaction Inventory_Level is undated per-row contextual stock, not reliable current usable stock. Customer/payment columns not used. No currency/cost optimization.',
 'selection':{'initial_winner':winner,'selected':selected,'same_winner_improvement_vs_local91':improvements,'rule_passed':all(v>=.05 for v in improvements.values()),'stability':stability},
 'orders':{'units':int(check.OrderQty.sum()),'positive_keys':int(check.OrderQty.gt(0).sum()),'zero_keys':int(check.OrderQty.eq(0).sum()),'prearrival_risk_keys':int(check.Shortage_Before_New_Arrival.sum()),
            'weekly_forecast_units':float(check.Forecast_Next_7_Days.sum()),'coverage_days_min_max':[int(horizons.min()),int(horizons.max())],
            'unrounded_net_shortfall_total':float(np.maximum(0,predict(daily,ORIGIN,horizons)[selected]+policy.Safety_Stock_Qty.to_numpy()-stock_sorted.Usable_On_Hand_Qty.to_numpy()-ledger_total).sum())},
 'routine_execution':{'local_calculation_seconds':routine_seconds,'input_rows':sum(map(len,[rp,ri,rs,raw])),'input_bytes':sum((SRC/f'input-{i}.csv').stat().st_size for i in range(1,5)),
                      'dependencies':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__},'language_model_calls':0,'network_calls':0,'paid_model_api_required':False,
                      'scope':'Load all released CSVs, deduplicate/filter, aggregate daily data, predict using selected method, calculate orders; excludes this AI-assisted analysis/build.'},
 'analysis_script_local_seconds':time.perf_counter()-START,
 'validation':'CSV reread, nonnegative integral units, all 336 keys, multiples/minimums, ledger matches, date boundaries; independent direct source baseline forecasts at two origins and all baseline orders when selected.'
}
save('measured_results.json',diagnostics)
print(scores.to_string(index=False))
print(json.dumps({'selection':diagnostics['selection'],'orders':diagnostics['orders'],'routine':diagnostics['routine_execution']},indent=2))
