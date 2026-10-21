"""Declared diagnostic sensitivities; does not change selected target or method."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import restock_routine as rr

origin=pd.Timestamp('2025-11-30')
p,s,d=rr.operations('../released/input-3.csv','../released/input-2.csv','../released/input-1.csv',origin)
main=pd.read_csv('restocking.csv')
diagnostics={}
for target in ['fulfilled','noncancelled','nonreturned']:
    day,_,names=rr.prepare_sales('../released/input-4.csv',origin,p.index,target)
    pred,_=rr.forecast(day,origin,rr.SELECTED)
    orders=rr.calculate(p,s,d,pred,names,origin)
    diagnostics[target]={'total_order_units':int(orders.OrderQty.sum()),'positive_orders':int(orders.OrderQty.gt(0).sum()),'quantities_changed_from_main':int((orders.OrderQty!=main.OrderQty).sum()),'primary_scores':{m:json.loads(Path(f'measured_{m}_{target}.json').read_text())['primary_MAE_7day'] for m in ['recent_8week','pooled_13week','poisson_calendar']}}
sc=pd.read_csv('comparison_pooled_13week_fulfilled.csv');a=sc[sc.horizon==7]
residuals={str(h):{'actual_minus_forecast_quantiles':(-x.error).quantile([.1,.5,.9]).to_dict(),'MAE':float(x.abs_error.mean()),'mean_forecast':float(x.forecast.mean()),'mean_actual':float(x.actual.mean())} for h,x in sc.groupby('horizon')}
diagnostics['recorded_demand_residuals']=residuals
diagnostics['metric_sparsity_warning']={'zero_target_fraction':float(a.actual.eq(0).mean()),'constant_zero_MAE_diagnostic_only':float(a.actual.mean()),'meaning':'Absolute error of sparse counts can prefer systematic low forecasts. Zero is a metric stress diagnostic, not a score-selected operational policy. Declared rates estimate average gross fulfillment; no stockout exposure or costs justify service or cost optimality.'}
diagnostics['uncertainty_limit']='Empirical residual quantiles across seven origins and heterogeneous pairs, dependent overlapping horizons. Descriptive dispersion only, neither a calibrated prediction interval nor guaranteed service level. No untested additional buffer added; supplied safety stock retained. Aggregate 90th percentile next-week underprediction is about 1.74 units per key, large relative to subunit forecasts. Individual lumpy orders remain hard to predict.'
Path('uncertainty_sensitivity.json').write_text(json.dumps(diagnostics,indent=2))
print(json.dumps(diagnostics,indent=2))
