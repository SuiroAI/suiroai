import json,time,resource,sys,platform
from pathlib import Path
import numpy as np
import pandas as pd
from forecasting import load_sales,weekly_panel,forecast,actual,KEYS

def run():
    started=time.perf_counter()
    plan=json.loads(Path('evaluation_plan.json').read_text())
    origin=pd.Timestamp('2025-11-30')
    d,target,first,names=load_sales('../released/input-4.csv',origin)
    pairs=first.index
    policy=pd.read_csv('../released/input-1.csv').set_index(KEYS).reindex(pairs)
    coverage=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy(dtype=int)
    methods=[x['name'] for x in plan['candidates']]
    records=[]; predictions=[]; workloads=[]
    for date in plan['origins']:
        o=pd.Timestamp(date); p=weekly_panel(target,first,o)
        truth=actual(target,pairs,o,7)
        coverage_truth=np.array([actual(target,pairs,o,h)[i] for i,h in enumerate(coverage)])
        for method in methods:
            f,t=forecast(p,pairs,o,method)
            pred=f[:,:7].sum(axis=1);cov=np.array([f[i,:h].sum() for i,h in enumerate(coverage)])
            workloads.append(dict(origin=date,method=method,**t))
            records.append({'origin':date,'method':method,'mae_7':float(np.abs(pred-truth).mean()),'bias_7':float((pred-truth).mean()),'mae_coverage':float(np.abs(cov-coverage_truth).mean()),'bias_coverage':float((cov-coverage_truth).mean())})
            for i,(prod,store) in enumerate(pairs):
                predictions.append({'origin':date,'method':method,'Product_ID':prod,'Store_ID':store,'actual_7':truth[i],'forecast_7':pred[i],'actual_coverage':coverage_truth[i],'forecast_coverage':cov[i]})
    score=pd.DataFrame(records);score.to_csv('candidate_scores_by_origin.csv',index=False)
    pd.DataFrame(predictions).to_csv('development_predictions.csv',index=False)
    means=score.groupby('method')[['mae_7','bias_7','mae_coverage','bias_coverage']].mean()
    best=means.mae_7.min();selected=next(m for m in methods if means.loc[m,'mae_7']<=best+1e-8)
    rng=np.random.default_rng(42);diff=score.pivot(index='origin',columns='method',values='mae_7')
    intervals={}
    for m in methods:
        delta=(diff[m]-diff['recent_8_week_mean']).to_numpy()
        samples=delta[rng.integers(0,len(delta),size=(2000,len(delta)))].mean(axis=1)
        intervals[m]={'mae_difference_vs_baseline':float(delta.mean()),'origin_block_bootstrap_95_percentile':np.quantile(samples,[.025,.975]).tolist(),'origins_better':int((delta<0).sum())}
    full=weekly_panel(target,first,origin)
    seasonal=target.assign(year=target.date.dt.year,month=target.date.dt.month).groupby(['year','month']).Quantity.sum().unstack().to_dict('index')
    results={'plan_version':1,'status':'development_only','selected_method':selected,'aggregate_scores':means.to_dict('index'),'uncertainty':intervals,'workloads':workloads,'preparation_and_comparison_wall_seconds':time.perf_counter()-started,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'weekly_zero_fraction':float((full.units==0).mean()),'positive_week_quantiles':full.loc[full.units>0,'units'].quantile([.25,.5,.75,.95]).to_dict(),'seasonal_units_by_year_month':seasonal,'not_independent_success_evaluation':True}
    Path('comparison_results.json').write_text(json.dumps(results,indent=2))
    Path('selected_method.json').write_text(json.dumps({'selected_method':selected,'plan_version':1},indent=2))
    # Prespecified diagnostic comparisons, no additional model discovery or reselection.
    sensitivity=[]
    for treatment in ['shipped_only','noncancelled']:
        _,t,_,_=load_sales('../released/input-4.csv',origin,treatment)
        for date in plan['origins']:
            o=pd.Timestamp(date);p=weekly_panel(t,first,o);truth=actual(t,pairs,o,7)
            for m in dict.fromkeys(['recent_8_week_mean',selected]):
                f,_=forecast(p,pairs,o,m)
                sensitivity.append({'treatment':treatment,'origin':date,'method':m,'mae_7':float(np.abs(f[:,:7].sum(axis=1)-truth).mean())})
    for n in [4,13]:
        for date in plan['origins']:
            o=pd.Timestamp(date);p=weekly_panel(target,first,o);truth=actual(target,pairs,o,7)
            f,_=forecast(p,pairs,o,f'recent_{n}_week_mean')
            sensitivity.append({'treatment':'fulfilled_window_sensitivity','origin':date,'method':f'recent_{n}_week_mean','mae_7':float(np.abs(f[:,:7].sum(axis=1)-truth).mean())})
    pd.DataFrame(sensitivity).to_csv('exploratory_sensitivity.csv',index=False)
    print(means.to_string());print('SELECTED',selected);print(json.dumps(intervals,indent=2));print('peak bytes',results['process_peak_rss_bytes'])
if __name__=='__main__':run()
