"""Frozen v1 development comparison; never reads reserved outcomes."""
import json, time, resource
from pathlib import Path
import numpy as np
import pandas as pd
import restock_routine as r

def run():
    plan=json.loads(Path('evaluation_plan.json').read_text())
    date=pd.Timestamp('2025-11-30'); s=r.load_sales('../released/input-4.csv',date)
    st,ins,p=r.load_operations('../released/input-3.csv','../released/input-2.csv','../released/input-1.csv',date)
    y=r.calendar(s,st.index,date); horizons=(p.Supplier_Lead_Time_Days+p.Review_Period_Days).to_numpy()
    rows=[]; profiles=[]; residuals=[]
    for origin_text in plan['origins']:
        origin=pd.Timestamp(origin_text)
        actual=y.loc[origin+pd.Timedelta(days=1):].iloc[:int(horizons.max())].to_numpy()
        for entry in plan['candidates']:
            method=entry['name']; pred,timing=r.forecast(y,origin,len(actual),method)
            profiles.append(dict(origin=origin_text,method=method,**timing))
            for j,key in enumerate(st.index):
                h=int(horizons[j]); truth=actual[:h,j].sum(); guess=pred[:h,j].sum()
                rows.append(dict(origin=origin_text,method=method,Product_ID=key[0],Store_ID=key[1],actual=truth,prediction=guess,error=guess-truth,absolute_error=abs(guess-truth),error7=pred[:7,j].sum()-actual[:7,j].sum(),absolute_error7=abs(pred[:7,j].sum()-actual[:7,j].sum())))
    detail=pd.DataFrame(rows); detail.to_csv('comparison_detail.csv',index=False)
    summary=detail.groupby('method').agg(primary_mae=('absolute_error','mean'),bias=('error','mean'),next_week_mae=('absolute_error7','mean'),next_week_bias=('error7','mean'))
    minimum=summary.primary_mae.min(); selected=next(x['name'] for x in plan['candidates'] if summary.loc[x['name'],'primary_mae']<=minimum+1e-8)
    summary.to_csv('comparison_scores.csv'); detail.groupby(['method','origin']).absolute_error.mean().to_csv('comparison_by_origin.csv'); detail.groupby(['method','Store_ID']).absolute_error.mean().to_csv('comparison_by_store.csv')
    pd.DataFrame(profiles).to_csv('candidate_workload.csv',index=False)
    orders,timing=r.make_orders(s,st,ins,p,date,selected); orders.to_csv('restocking_expected.csv',index=False)
    base,_=r.make_orders(s,st,ins,p,date,'mean84')
    sensitivities={}
    for target in ['retained','orders']:
        ys=r.calendar(s,st.index,date,target)
        pred,_=r.forecast(ys,date,int(horizons.max()),selected)
        sensitivities[target]={'forecast_coverage_units':float(sum(pred[:horizons[j],j].sum() for j in range(len(horizons))))}
    sparse=(y.iloc[-84:]>0).sum()
    selected_errors=detail.loc[detail.method==selected,'error']
    result={'status':'development only; no independent performance success', 'selected':selected,'scores':summary.to_dict('index'),'reduction_vs_baseline':float(1-summary.loc[selected,'primary_mae']/summary.loc['mean84','primary_mae']),'population':len(st),'order_units':int(orders.OrderQty.sum()),'positive_orders':int((orders.OrderQty>0).sum()),'zero_orders':int((orders.OrderQty==0).sum()),'timing_shortages':int((orders.Expected_Shortage_Before_Arrival_Units>0).sum()),'any_timing_shortages':int((orders.Expected_Max_Timing_Shortage_Units>0).sum()),'baseline_order_units':int(base.OrderQty.sum()),'orders_differ_from_baseline':int((orders.OrderQty!=base.OrderQty).sum()),'recent_84_day_nonzero_days':sparse.describe().to_dict(),'recent_zero_keys':int((sparse==0).sum()),'residual_quantiles_signed_prediction_minus_actual':selected_errors.quantile([.05,.5,.95]).to_dict(),'sensitivity':sensitivities,'deployment_profile':timing,'comparison_process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rss_platform':'macOS bytes; whole process including imports, all candidates and retained evaluation arrays; not per-method isolated peak'}
    Path('comparison_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__': run()
