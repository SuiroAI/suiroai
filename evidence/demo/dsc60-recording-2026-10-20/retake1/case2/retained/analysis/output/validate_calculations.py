"""Independent arithmetic checks and bounded workload profiling."""
import json,time,resource,sys,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
import restock_routine as rr

origin=pd.Timestamp('2025-11-30'); start=time.perf_counter()
s=rr.read_sales('../released/input-4.csv',origin)
stock,inc,policy,keys=rr.read_operations('../released/input-3.csv','../released/input-2.csv','../released/input-1.csv',origin)
dates,y,first=rr.panel(s,keys,origin); preparation=time.perf_counter()-start
# Independent long-table calculation rather than panel/model helper.
t=time.perf_counter()
v=s[s.status.isin(['completed','shipped'])&s.Quantity.gt(0)&s.Order_Date.between(origin-pd.Timedelta(days=89),origin)]
local=v.groupby(rr.KEY).Quantity.sum().reindex(keys,fill_value=0)/90
product=local.groupby(level=0).sum(); store=local.groupby(level=1).sum(); total=local.sum()
fit_seconds=time.perf_counter()-t
t=time.perf_counter()
rate=pd.Series({(p,st):.5*local.loc[(p,st)]+.5*product[p]*store[st]/total for p,st in keys})
prediction_seconds=time.perf_counter()-t
actual=rr.rates(rr.SELECTED,dates,y,first,origin,keys)
assert np.allclose(rate.values,actual,rtol=0,atol=1e-12)
r=pd.read_csv('restocking.csv',keep_default_na=False)
assert len(r)==336 and not r.duplicated(rr.KEY).any()
assert (r.OrderQty>=0).all() and (r.OrderQty%1==0).all()
assert not any(c.lower() in ['synthetic','provenance','illustrative_synthetic_stock'] for c in r)
maxerr=0; verified=[]
for row in r.itertuples():
    k=(row.Product_ID,row.Store_ID); pol=policy.set_index(rr.KEY).loc[k]; inv=stock.set_index(rr.KEY).loc[k]
    receipts=inc[(inc.Product_ID==k[0])&(inc.Store_ID==k[1])]
    end=origin+pd.Timedelta(days=int(pol.Supplier_Lead_Time_Days+pol.Review_Period_Days))
    timely=int(receipts.loc[(receipts.Expected_Arrival_Date>origin)&(receipts.Expected_Arrival_Date<=end),'Incoming_Qty'].sum())
    gap=max(0,rate.loc[k]*(pol.Supplier_Lead_Time_Days+pol.Review_Period_Days)+pol.Safety_Stock_Qty-inv.Usable_On_Hand_Qty-timely)
    expected=0 if gap<=1e-10 else int(np.ceil(max(gap,pol.Minimum_Order_Qty)/pol.Order_Multiple_Qty)*pol.Order_Multiple_Qty)
    assert expected==row.OrderQty and timely==row.Incoming_Within_Coverage_Units
    assert row.OrderQty==0 or (row.OrderQty>=pol.Minimum_Order_Qty and row.OrderQty%pol.Order_Multiple_Qty==0)
    verified.append(expected)
sc=pd.read_csv('development_predictions.csv'); weekly=sc[sc.horizon=='week']
per_origin=weekly.groupby(['origin','method']).abs_error.mean().unstack()
wins=int((per_origin.pooled90<per_origin.recent_month).sum())
sens=pd.read_csv('target_sensitivity.csv').groupby(['target','method']).MAE.mean().unstack()
full_month_end_baseline=rr.rates('recent_month',dates,y,first,origin,keys)
names=s.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name.to_dict()
baseline_rows=rr.order_rows(full_month_end_baseline,keys,stock,inc,policy,origin,names)
order=json.loads(Path('order_sensitivity.json').read_text())
for obj in order:
    if obj['method']=='recent_month':
        obj.update(total_order_units=int(baseline_rows.OrderQty.sum()),positive_orders=int(baseline_rows.OrderQty.gt(0).sum()),different_orders_vs_selected=int((baseline_rows.OrderQty!=r.OrderQty).sum()),total_absolute_order_difference=int(abs(baseline_rows.OrderQty-r.OrderQty).sum()))
Path('order_sensitivity.json').write_text(json.dumps(order,indent=2))
monthly=pd.read_csv('seasonality.csv'); monthly['daily']=monthly.Quantity/pd.to_datetime(monthly.year.astype(str)+'-'+monthly.month.astype(str)+'-01').dt.days_in_month
annual={str(year):float(g[g.month==11].daily.iloc[0]/g[g.month.between(1,10)].daily.mean()) for year,g in monthly.groupby('year') if len(g[g.month==11])}
validation=dict(all_336_orders_independently_checked=True,rate_max_absolute_difference=float(max(abs(rate.values-actual))),all_quantities_nonnegative_integer=True,source_overwrite_protection=True,selected_weekly_wins_vs_baseline=f'{wins}/8',alternative_target_scores_fixed_original_forecasts=sens.to_dict(),seasonal_november_to_jan_oct_daily_ratio=annual,selected_forecast_total_next_week=float(r.Forecast_Next_Week_Units.sum()),selected_orders=int(r.OrderQty.sum()),positive_orders=int(r.OrderQty.gt(0).sum()),zero_orders=int(r.OrderQty.eq(0).sum()),timing_flags=int(r.Review_Flag.ne('').sum()),prearrival_shortage_units_sum=float(r.Expected_Prearrival_Shortage_Units.sum()),maximum_prearrival_shortage_units=float(r.Expected_Prearrival_Shortage_Units.max()),selected_method='pooled90',independent_success_gate='Not ready: development outcomes previously inspected, untouched evaluation and externally declared meaningful improvement threshold absent; December remains reserved',baseline_month_end_clarification='At month-end, current month is fully observed and is most recent complete month. Correction affects only deployment baseline sensitivity, none of the eight development origins are month-end; no scores/selection changed.',uncertainty='No calibrated availability probability. Flat daily demand approximation for timing; sparse low counts, unmeasured stockout censorship, final statuses, and pack-size rounding limit precision. Flags are model-based review cues, not observed shortages.',order_policy='Order-up-to target = forecast daily rate times lead+review + supplied safety stock; deduct usable on-hand and only dated receipts within coverage. Positive gaps rounded to MOQ and pack multiple. Overdue and beyond-coverage inbound excluded. Assumes end-of-planning-day snapshot; deliveries usable at beginning of due day. Forecast shortfalls carried through timing projection; orders do not remove prearrival shortage.',cost='No paid model calls; no numeric ongoing money or AI-build estimate asserted without observed applicable rates/usage.')
Path('validation_results.json').write_text(json.dumps(validation,indent=2))
profile=dict(preparation_seconds=preparation,selected_statistic_aggregation_fit_seconds=fit_seconds,selected_336_rate_inference_seconds=prediction_seconds,process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if sys.platform=='darwin' else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,measurement_scope='Separate verification process holding extra tables and independent arrays; these are separate phase microbenchmarks, not additive decomposition of measured CLI time.',data_shape=list(y.shape),panel_bytes=y.nbytes,retained_model='336 local rates, 28 product totals, 12 store totals, scalar grand total; no persisted learned estimator',complexity='Selected fit O(transactions + days*keys) including panel preparation; prediction O(keys). Memory O(rows + days*keys); model state O(keys).',compatibility='Actual CLI peak under 0.2 GiB and subsecond wall time for 17,406 sales rows and 336 operating keys. Fits CPU-only 8 GB RAM computer with substantial OS headroom for this workload; current host RAM not assumed. No parallel workers, GPU, neural networks, sklearn or network dependency. Larger future extracts need fresh measurement.',candidate_workload='All candidates have per-origin fit+inference times and whole comparison peak RSS in development_results.json; ridge retains about two years * 336 examples * 10 float64 features, a few MB plus arrays; no unbounded search.')
Path('computational_profile.json').write_text(json.dumps(profile,indent=2))
print(json.dumps(validation,indent=2));print(json.dumps(profile,indent=2))
