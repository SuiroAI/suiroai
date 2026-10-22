"""Frozen v1 development comparison; never reads any outcome after November 30."""
import json, time, resource, sys
from pathlib import Path
import numpy as np
import pandas as pd
import restock_routine as rr

ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'released'
plan=json.loads((ROOT/'evaluation_plan.json').read_text())
started=time.perf_counter()
date=pd.Timestamp('2025-11-30')
stock,incoming,policy=rr.load_operations(SRC/'input-3.csv',SRC/'input-2.csv',SRC/'input-1.csv',date)
raw,sales=rr.read_sales(SRC/'input-4.csv',date)
panel=rr.daily_panel(sales,policy.index,date)
prep_seconds=time.perf_counter()-started
horizons=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy().astype(int)
rows=[]; profiles=[]
for origin_string in plan['forecast_origins']:
    origin=pd.Timestamp(origin_string)
    future=panel.loc[origin+pd.Timedelta(days=1):origin+pd.Timedelta(days=14)].to_numpy()
    assert future.shape==(14,336) and np.isfinite(future).all()
    actual={'7':future[:7].sum(axis=0),'14':future.sum(axis=0),'policy':np.array([future[:h,j].sum() for j,h in enumerate(horizons)])}
    for method in ['recent84','sba','poisson']:
        pred=rr.forecast(panel,origin,method)
        profiles.append({'origin':origin_string,'method':method,**rr.LAST_PROFILE})
        predtot={'7':pred[:7].sum(axis=0),'14':pred.sum(axis=0),'policy':np.array([pred[:h,j].sum() for j,h in enumerate(horizons)])}
        for j,key in enumerate(policy.index):
            row={'origin':origin_string,'method':method,'Product_ID':key[0],'Store_ID':key[1]}
            for h in actual:
                row['actual_'+h]=actual[h][j]; row['prediction_'+h]=predtot[h][j]
            rows.append(row)
results=pd.DataFrame(rows)
results.to_csv(ROOT/'evaluation_predictions.csv',index=False)

def metric(d,h):
    error=d['prediction_'+h]-d['actual_'+h]
    return {'mae':float(error.abs().mean()),'bias':float(error.mean()),'wape':float(error.abs().sum()/d['actual_'+h].sum()),'absolute_error_p50':float(error.abs().quantile(.5)),'absolute_error_p90':float(error.abs().quantile(.9)),'zero_actual_fraction':float(d['actual_'+h].eq(0).mean()),'mae_positive_actual':float(error.loc[d['actual_'+h].gt(0)].abs().mean())}

scores={m:{h:metric(d,h) for h in ['7','14','policy']} for m,d in results.groupby('method')}
best=min(scores,key=lambda m:scores[m]['7']['mae'])
selected='recent84' if scores['recent84']['7']['mae']<=1.01*scores[best]['7']['mae'] else ('sba' if scores['sba']['7']['mae']<=1.01*scores[best]['7']['mae'] else best)
per_origin={str(o):{m:metric(d,'7') for m,d in group.groupby('method')} for o,group in results.groupby('origin')}
per_store={str(s):{m:metric(d,'7') for m,d in group.groupby('method')} for s,group in results.groupby('Store_ID')}
periods={name:{m:metric(d,'7') for m,d in group.groupby('method')} for name,group in results.groupby(np.where(results.origin<'2025-10-26','October','November'))}
season=[]
for (year,month),group in panel.groupby([panel.index.year,panel.index.month]):
    season.append({'year':int(year),'month':int(month),'units_per_exposed_pair_day':float(group.sum().sum()/group.count().sum())})
pd.DataFrame(season).to_csv(ROOT/'seasonal_stability.csv',index=False)
weekly=rr.weekly_panel(panel,date)
measure={'selected':selected,'scores':scores,'relative_mae_reduction_against_baseline':1-scores[selected]['7']['mae']/scores['recent84']['7']['mae'],'per_origin':per_origin,'per_store':per_store,'period_sensitivity':periods,'profiles':profiles,'panel':{'shape':list(panel.shape),'bytes':int(panel.memory_usage(index=True,deep=True).sum()),'pre_first_sale_unknown_cells':int(panel.isna().sum().sum()),'zero_observed_week_fraction':float(weekly.eq(0).sum().sum()/weekly.notna().sum().sum())},'data_preparation_wall_seconds':prep_seconds,'total_comparison_wall_seconds':time.perf_counter()-started,'process_peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),'score_status':'Development only; final exported statuses known retrospectively; no untouched evaluation.','selection_horizon_mismatch':'Selection uses 7 days; orders use 8-14 days. Both 14-day and per-policy horizons reported. Current coverage lengths are diagnostics, not historical policies.','success_gate':'Open; independent untouched outcomes and external threshold absent.'}
(ROOT/'evaluation_results.json').write_text(json.dumps(measure,indent=2))
print(json.dumps({'selected':selected,'scores':scores,'seconds':measure['total_comparison_wall_seconds'],'peak_mib':measure['process_peak_rss_mib']},indent=2))
