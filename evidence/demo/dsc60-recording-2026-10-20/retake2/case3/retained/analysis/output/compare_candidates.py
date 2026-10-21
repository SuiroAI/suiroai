"""Frozen-plan development comparison. Does not access December outcomes."""
import argparse, json, time
from pathlib import Path
import restock_routine as rr
import numpy as np
import pandas as pd

def run(method,target):
    start=time.perf_counter(); plan=json.loads(Path('evaluation_plan.json').read_text())
    day,s,names=rr.prepare_sales('../released/input-4.csv',pd.Timestamp('2025-11-30'),target=target)
    prep=time.perf_counter()-start; rows=[]; workloads=[]; residual=[]
    for orig in plan['origins']:
        o=pd.Timestamp(orig); pred,t=rr.forecast(day,o,method,14); workloads.append({'origin':orig,**t})
        for h in range(7,15):
            y=day.loc[o+pd.Timedelta(days=1):o+pd.Timedelta(days=h)].sum().values
            f=pred[:h].sum(axis=0); err=f-y
            for k,yy,ff,ee in zip(day.columns,y,f,err):
                rows.append({'method':method,'target':target,'origin':orig,'horizon':h,'Product_ID':k[0],'Store_ID':k[1],'actual':yy,'forecast':ff,'error':ee,'abs_error':abs(ee)})
    scores=pd.DataFrame(rows); scores.to_csv(f'comparison_{method}_{target}.csv',index=False)
    primary=scores[scores.horizon==7]; cover=scores[scores.horizon>7]
    result={'method':method,'target':target,'primary_MAE_7day':primary.abs_error.mean(),'WAPE_7day':primary.abs_error.sum()/primary.actual.sum(),'mean_signed_error':primary.error.mean(),'MAE_8_to_14day':cover.abs_error.mean(),'actual_7day_units':primary.actual.sum(),'zero_target_fraction':primary.actual.eq(0).mean(),'per_origin_MAE':primary.groupby('origin').abs_error.mean().to_dict(),'per_store_MAE':primary.groupby('Store_ID').abs_error.mean().to_dict(),'residual_actual_minus_forecast_quantiles':(-primary.error).quantile([.1,.5,.9]).to_dict(),'preparation_seconds':prep,'origins_workloads':workloads,'total_process_work_seconds':time.perf_counter()-start,'peak_process_rss_mb':rr.peak_mb(),'daily_panel_bytes':int(day.memory_usage(index=True).sum())}
    Path(f'measured_{method}_{target}.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--candidate',required=True);a.add_argument('--target',default='fulfilled');v=a.parse_args();run(v.candidate,v.target)
