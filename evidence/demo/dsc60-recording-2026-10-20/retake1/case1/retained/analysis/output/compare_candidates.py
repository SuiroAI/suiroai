"""Frozen v1 development comparison. No December outcomes; no parameter search."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import json,time,resource,sys
from pathlib import Path
import numpy as np
import pandas as pd
from restock_routine import load_sales,forecast

def main():
    start=time.perf_counter()
    plan=json.loads(Path('evaluation_plan.json').read_text())
    pth=Path(sys.argv[1]);p=pd.read_csv(pth/'input-1.csv').sort_values(['Product_ID','Store_ID'])
    keys=list(map(tuple,p[['Product_ID','Store_ID']].values));h=(p.Supplier_Lead_Time_Days+p.Review_Period_Days).to_numpy()
    matrix,_=load_sales(pth/'input-4.csv',pd.Timestamp('2025-11-30'),keys)
    check_end=matrix.index.max();assert check_end==pd.Timestamp('2025-11-30')
    prep=time.perf_counter()-start;rows=[];timings=[]
    for origin in plan['origins']:
        origin=pd.Timestamp(origin);actual=matrix.loc[origin+pd.Timedelta(days=1):origin+pd.Timedelta(days=14)].to_numpy()
        assert len(actual)==14
        for method in plan['candidates']:
            t=time.perf_counter();pred,stats=forecast(matrix,origin,14,method,keys)
            timings.append({'origin':str(origin.date()),'method':method,'fit_and_inference_total_seconds':time.perf_counter()-t,**stats})
            for j,key in enumerate(keys):
                train=matrix.loc[origin-pd.Timedelta(days=83):origin].iloc[:,j]
                for days in [7,int(h[j])]:
                    y=float(actual[:days,j].sum());f=float(pred[:days,j].sum())
                    rows.append({'origin':str(origin.date()),'method':method,'Product_ID':key[0],'Store_ID':key[1],'horizon':days,'kind':'next7' if days==7 else 'coverage','actual':y,'forecast':f,'error':f-y,'absolute_error':abs(f-y),'training_nonzero_days':int(train.gt(0).sum())})
    scores=pd.DataFrame(rows);scores.to_csv('comparison_predictions.csv',index=False)
    summary=scores.groupby(['method','kind']).agg(MAE=('absolute_error','mean'),bias=('error','mean'),total_actual=('actual','sum'),absolute_error_sum=('absolute_error','sum')).reset_index()
    summary['WAPE']=summary.absolute_error_sum/summary.total_actual
    summary.to_csv('comparison_scores.csv',index=False)
    primary=summary[summary.kind.eq('coverage')].set_index('method').MAE
    best=primary.min();winner=next(m for m in plan['candidates'] if primary[m]<=best+1e-9)
    origin_scores=scores.groupby(['method','kind','origin']).absolute_error.mean().unstack('method');origin_scores.to_csv('comparison_by_origin.csv')
    scores.groupby(['method','kind','Store_ID']).absolute_error.mean().to_csv('comparison_by_store.csv')
    scores.assign(sparse_group=np.where(scores.training_nonzero_days<=2,'0-2_nonzero_days','3+_nonzero_days')).groupby(['method','kind','sparse_group']).absolute_error.mean().to_csv('comparison_by_sparsity.csv')
    differences=origin_scores.loc['coverage',winner]-origin_scores.loc['coverage','mean84']
    residual=scores[scores.method.eq(winner)].groupby('kind').error.quantile([.1,.5,.9]).to_dict()
    out={'selected_method':winner,'primary_reduction_vs_baseline_fraction':float(1-primary[winner]/primary['mean84']),'preparation_seconds':prep,'comparison_total_seconds':time.perf_counter()-start,'process_peak_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)),'timings':timings,'paired_coverage_MAE_differences_by_origin':differences.to_dict(),'descriptive_error_quantiles':{str(k):v for k,v in residual.items()},'interpretation':'Development evidence only; eight overlapping origins, no threshold or untouched evaluation; no savings/service claims.'}
    Path('comparison_results.json').write_text(json.dumps(out,indent=2));print(summary.to_string(index=False));print('SELECTED',winner)
if __name__=='__main__':main()
