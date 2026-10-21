"""Run the frozen development comparison. Never reads outside four released files/output."""
import hashlib,json,time,resource,sys
from pathlib import Path
import numpy as np
import pandas as pd
from restock_routine import clean_sales,totals,fit_forecast,KEYS

ROOT=Path(__file__).parent
SRC=ROOT.parent/'released'
plan=json.loads((ROOT/'evaluation_plan.json').read_text())
assert plan['written_before_scores']
raw,s=clean_sales(SRC/'input-4.csv',pd.Timestamp('2025-11-30'))
policy=pd.read_csv(SRC/'input-1.csv').sort_values(KEYS).reset_index(drop=True)
keys=policy[KEYS]
methods=[c['name'] for c in plan['candidates']]
rows=[]; workload=[]; sensitivity=[]
start=time.perf_counter()
for origin_text in plan['origins']:
    origin=pd.Timestamp(origin_text)
    future=pd.date_range(origin+pd.Timedelta(days=1),periods=14)
    actuals={h:totals(s,keys,future[0],future[h-1]) for h in [7,14]}
    # Alternate nonreturn target is sensitivity only; never replaces primary.
    nonreturn=s[~s.status.eq('returned') & s.Return_Flag.str.strip().str.lower().eq('no')]
    for method in methods:
        predictor,info=fit_forecast(s,keys,origin,method)
        t=time.perf_counter(); daily=predictor(future); info['inference_seconds']=time.perf_counter()-t
        info.update(origin=origin_text); workload.append(info)
        for h in [7,14]:
            for i,k in keys.iterrows():
                active=raw.loc[raw.Store_ID.eq(k.Store_ID)&raw.date.between(future[0],future[h-1]),'date'].nunique()
                pred=float(daily[i,:h].sum()); actual=actuals[h][i]
                rows.append(dict(origin=origin_text,method=method,horizon=h,Product_ID=k.Product_ID,Store_ID=k.Store_ID,
                                 actual=actual,prediction=pred,error=pred-actual,absolute_error=abs(pred-actual),store_observed_days=active))
        variable=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy(int)
        variable_actual=np.array([totals(s,keys.iloc[[i]],future[0],future[h-1])[0] for i,h in enumerate(variable)])
        variable_pred=np.array([daily[i,:h].sum() for i,h in enumerate(variable)])
        sensitivity.append(dict(origin=origin_text,method=method,type='variable_coverage',mae=float(np.mean(abs(variable_pred-variable_actual)))))
        # Independently re-fit each same method on alternate gross nonreturn target.
        pp,_=fit_forecast(nonreturn,keys,origin,method)
        pa=pp(future)[:,:7].sum(axis=1); aa=totals(nonreturn,keys,future[0],future[6])
        sensitivity.append(dict(origin=origin_text,method=method,type='exclude_all_return_rows',mae=float(np.mean(abs(pa-aa)))))
scores=pd.DataFrame(rows)
scores.to_csv(ROOT/'development_predictions.csv',index=False)
summary=scores.groupby(['method','horizon']).agg(mae=('absolute_error','mean'),bias=('error','mean'),absolute_error=('absolute_error','sum'),observed_units=('actual','sum'),zero_target_share=('actual',lambda x:float(x.eq(0).mean())),n=('actual','size')).reset_index()
summary['wape']=summary.absolute_error/summary.observed_units
summary.to_csv(ROOT/'comparison_results.csv',index=False)
byorigin=scores.groupby(['method','horizon','origin']).absolute_error.mean().reset_index()
byorigin.to_csv(ROOT/'origin_results.csv',index=False)
scores.groupby(['method','horizon','Store_ID']).absolute_error.mean().to_csv(ROOT/'store_results.csv')
pd.DataFrame(sensitivity).to_csv(ROOT/'sensitivity_results.csv',index=False)
primary=summary[summary.horizon.eq(7)].set_index('method').mae.to_dict()
winner=min(methods,key=lambda m:(round(primary[m],9),methods.index(m)))
piv=byorigin[byorigin.horizon.eq(7)].pivot(index='origin',columns='method',values='absolute_error')
delta=piv[winner]-piv['previous_month']
rng=np.random.default_rng(410)
boot=delta.to_numpy()[rng.integers(0,len(delta),size=(5000,len(delta)))].mean(axis=1)
loo={o:piv.drop(o).mean().idxmin() for o in piv.index}
full=scores[scores.horizon.eq(7)&scores.store_observed_days.eq(7)].groupby('method').absolute_error.agg(['mean','size']).to_dict('index')
last=s[s.date.between('2025-09-08','2025-11-30')]
pair_counts=last.groupby(KEYS).size().reindex(pd.MultiIndex.from_frame(keys),fill_value=0)
season=s.groupby([s.date.dt.year.rename('year'),s.date.dt.month.rename('month')]).Quantity.sum().unstack()
seasonal_ratio={str(y):float(season.loc[y,11]/season.loc[y,10]) for y in season.index}
evidence={'selected':winner,'selection_metric':primary,'improvement_vs_baseline_fraction':1-primary[winner]/primary['previous_month'],
 'bootstrap_origin_block_difference_95_percentile':np.quantile(boot,[.025,.975]).tolist(),
 'bootstrap_limit':'8 overlapping development origins; descriptive uncertainty, not independent generalization evidence.',
 'leave_one_origin_out_winners':loo,'fully_observed_store_week_subset':full,
 'recent84_pair_transaction_count_distribution':pair_counts.describe().to_dict(),
 'november_october_recorded_unit_ratio_by_year':seasonal_ratio,
 'workload':workload,'total_comparison_wall_seconds':time.perf_counter()-start,
 'comparison_process_peak_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
 'platform':sys.platform,'plan_sha256':hashlib.sha256((ROOT/'evaluation_plan.json').read_bytes()).hexdigest(),
 'gate':'Independent performance-success recording readiness not established; external threshold absent and untouched outcomes withheld.'}
(ROOT/'selection_evidence.json').write_text(json.dumps(evidence,indent=2))
print(summary.to_string(index=False)); print('Selected',winner); print('Improvement',evidence['improvement_vs_baseline_fraction']); print('Full coverage',full)
