"""Execute fixed prospective development plan. No reserved outcomes accessed."""
import json, time, resource, platform, hashlib, sys
from pathlib import Path
import numpy as np
import pandas as pd
import restock_routine as rr

def write(name,obj): Path(name).write_text(json.dumps(obj,indent=2,default=str))
start=time.perf_counter()
origin=pd.Timestamp('2025-11-30')
stock,inbound,policy,keys=rr.read_operations('../released/input-3.csv','../released/input-2.csv','../released/input-1.csv',origin)
raw=pd.read_csv('../released/input-4.csv'); s=rr.read_sales('../released/input-4.csv',origin)
dates,y,first=rr.panel(s,keys,origin)
prep=time.perf_counter()-start
plan=json.loads(Path('evaluation_plan.json').read_text())
origins=pd.to_datetime(plan['origins']); methods=list(plan['candidates']); records=[]; workload=[]; forecasts={}
h=policy.set_index(rr.KEY).reindex(keys).Supplier_Lead_Time_Days.to_numpy()+7
for o in origins:
    idx=dates.get_loc(o)
    # Truncate arrays as well as training indices at every origin.
    for method in methods:
        t=time.perf_counter(); rate=rr.rates(method,dates[:idx+1],y[:idx+1],first,o,keys); elapsed=time.perf_counter()-t
        forecasts[(str(o.date()),method)]=rate
        workload.append(dict(origin=str(o.date()),method=method,fit_and_inference_seconds=elapsed))
        for horizon in ['week','coverage']:
            hs=np.full(len(keys),7) if horizon=='week' else h
            if idx+int(hs.max())>=len(dates): continue
            actual=np.array([y[idx+1:idx+1+int(hh),j].sum() for j,hh in enumerate(hs)])
            pred=rate*hs
            for j,(p,store) in enumerate(keys):
                records.append(dict(origin=str(o.date()),method=method,horizon=horizon,Product_ID=p,Store_ID=store,actual=actual[j],forecast=pred[j],error=pred[j]-actual[j],abs_error=abs(pred[j]-actual[j])))
sc=pd.DataFrame(records); sc.to_csv('development_predictions.csv',index=False)
summary=sc.groupby(['method','horizon']).agg(MAE=('abs_error','mean'),bias=('error','mean'),observations=('actual','size'),recorded_units=('actual','sum')).reset_index()
summary.to_csv('comparison_scores.csv',index=False)
primary=summary[summary.horizon=='week'].sort_values('MAE'); best=primary.MAE.min()
selected=next(m for m in methods if primary.set_index('method').loc[m,'MAE']<=best+1e-9)
sc.groupby(['method','horizon','origin']).abs_error.mean().to_csv('origin_scores.csv')
sc[sc.horizon=='week'].groupby(['method','Store_ID']).abs_error.mean().to_csv('store_scores.csv')
last90=y[-90:].sum(axis=0); sparse={keys[j]:last90[j]<5 for j in range(len(keys))}
sc['sparse_last90']=[sparse[(p,st)] for p,st in zip(sc.Product_ID,sc.Store_ID)]
sc.groupby(['method','horizon','sparse_last90']).abs_error.mean().to_csv('sparsity_scores.csv')
sens=[]
for target in ['no_returns','processing']:
    _,yt,_=rr.panel(s,keys,origin,target)
    for o in origins:
        idx=dates.get_loc(o); actual=yt[idx+1:idx+8].sum(axis=0)
        for m in methods:
            # Fixed original forecasts scored against alternative target definitions, not retrained models.
            e=forecasts[(str(o.date()),m)]*7-actual
            sens.append(dict(target=target,method=m,origin=str(o.date()),MAE=float(abs(e).mean())))
pd.DataFrame(sens).to_csv('target_sensitivity.csv',index=False)
valid=s.status.isin(['completed','shipped'])&s.Quantity.gt(0)
daily_nonzero=(y>0).sum(axis=0)
source={
 'source_authority':'Released files only. Operating inputs assumed scenario facts; bytes retained unchanged. Operational Provenance fields say synthetic; no independent real-stock verification.',
 'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('../released').glob('*.csv')},
 'source_lineage':'Transactions released-byte hash differs from original approved-source hash because supplied controller partition ends November 30; no originals or December outcomes accessed.',
 'rows_raw':len(raw),'rows_after_exact_dedup':len(s),'exact_duplicates':len(raw)-len(s),'conflicting_transaction_ids':int(s.Transaction_ID.duplicated().sum()),
 'status_return_counts':s.groupby(['status','returned']).Quantity.agg(['count','sum']).reset_index().to_dict('records'),
 'nonpositive_rows':int(s.Quantity.le(0).sum()),'nonpositive_quantity_sum':int(s.loc[s.Quantity.le(0),'Quantity'].sum()),
 'recorded_target_units':int(s.loc[valid,'Quantity'].sum()),'recorded_target_rows':int(valid.sum()),
 'date_min':dates.min(),'date_max':dates.max(),'calendar_dates':len(dates),'dates_with_any_raw_transaction':s.Order_Date.nunique(),
 'missing_date_policy':'Absence in an otherwise continuous ledger interpreted only as no recorded event; no inventory exposure or actual zero-demand claim. Series training masks pre-first-observation periods.',
 'zero_recorded_day_fraction':float((y==0).mean()),'positive_days_per_series_quantiles':np.quantile(daily_nonzero,[0,.25,.5,.75,1]).tolist(),
 'active_population':len(keys),'products':s.Product_ID.nunique(),'stores':s.Store_ID.nunique(),'latest_first_transaction':first.max(),
 'null_counts':raw.isna().sum().to_dict(),'name_conflicts':int(s.groupby('Product_ID').Product_Name.nunique().gt(1).sum()),
 'ledger_mismatch_count':0,'operating_key_consistency':'read_operations enforces identical stock/policy keys, ledger subset, positive units, complete ledger and on-order agreement',
 'units':'product_unit; quantities integer; separate product units across products are workload totals, not monetary or case totals',
 'target_limitation':'Gross fulfilled positive recorded outbound; later returns not subtracted, since reuse/receipt dates absent. Final statuses may be retrospectively changed. Recorded demand may be censored by stockouts; no correction is identifiable.',
 'incumbent_gap':'Previous month supplied concept only. Exact scaling, statuses, stock adjustments and rounding unknown. Baseline is analyst-defined daily-rate interpretation, not verified incumbent.',
 'context':'Self-contained supplied facts; gather-business-context retrieval skipped under its self-contained exception. No outside sources necessary.',
 'future_policy_horizons_used_for_development':'Current lead times define secondary diagnostic lengths only; not asserted historical supplier rules.'}
write('source_treatment.json',source)
s.loc[valid].assign(year=lambda x:x.Order_Date.dt.year,month=lambda x:x.Order_Date.dt.month).groupby(['year','month']).Quantity.sum().to_csv('seasonality.csv')
all_rates={m:rr.rates(m,dates,y,first,origin,keys) for m in methods}
names=s.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name.to_dict()
selected_rows=rr.order_rows(all_rates[selected],keys,stock,inbound,policy,origin,names)
selected_rows.to_csv('expected_restocking.csv',index=False)
order_sensitivity=[]
for m in methods:
    rows=rr.order_rows(all_rates[m],keys,stock,inbound,policy,origin,names)
    order_sensitivity.append(dict(method=m,total_order_units=int(rows.OrderQty.sum()),positive_orders=int(rows.OrderQty.gt(0).sum()),different_orders_vs_selected=int((rows.OrderQty!=selected_rows.OrderQty).sum()),total_absolute_order_difference=int(abs(rows.OrderQty-selected_rows.OrderQty).sum())))
write('order_sensitivity.json',order_sensitivity)
write('development_results.json',dict(selected=selected,selection_rule=plan['selection'],scores=summary.to_dict('records'),workload=workload,preparation_seconds=prep,total_comparison_seconds=time.perf_counter()-start,process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if sys.platform=='darwin' else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,platform=platform.platform(),plan_sha256=hashlib.sha256(Path('evaluation_plan.json').read_bytes()).hexdigest(),status='Development only; no independent success gate, no externally declared meaningful threshold, no untouched evaluation.'))
code=Path('restock_routine.py').read_text().replace("SELECTED = 'PENDING'",f"SELECTED = '{selected}'")
Path('restock_routine.py').write_text(code)
print(summary.to_string(index=False));print('Selected',selected);print('orders',order_sensitivity);print('timing flags',selected_rows.Review_Flag.value_counts().to_dict())
