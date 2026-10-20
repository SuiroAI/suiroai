"""Routine selected non-LLM model. CPU only; pandas and numpy, no model/API calls.
Frozen selected method, as-of 2025-11-30, approved source CSVs only.
Writes internal routine_orders.csv and routine_workload.json; does not change delivered CSV.
"""
import time
START=time.perf_counter()
import json, resource, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent; SRC=ROOT.parent/'released'
CPU=time.process_time()

def run():
 prep_start=time.perf_counter()
 cols=['Transaction_ID','Product_ID','Store_ID','Order_Date','Product_Name','Quantity','Order_Status','Return_Flag']
 d=pd.read_csv(SRC/'input-4.csv',usecols=cols).drop_duplicates('Transaction_ID')
 p=pd.read_csv(SRC/'input-1.csv').sort_values(['Product_ID','Store_ID']).reset_index(drop=True)
 i=pd.read_csv(SRC/'input-3.csv'); r=pd.read_csv(SRC/'input-2.csv'); K=['Product_ID','Store_ID']
 origin=pd.Timestamp('2025-11-30'); d['date']=pd.to_datetime(d.Order_Date)
 assert d.date.max()<=origin and p.Effective_Date.eq('2025-11-30').all() and i.Snapshot_Date.eq('2025-11-30').all()
 d['week']=d.date.dt.to_period('W-SUN').dt.start_time
 pairs=pd.MultiIndex.from_frame(p[K]); weeks=pd.date_range(end=origin-pd.Timedelta(days=6),periods=26,freq='W-MON')
 s=p.Store_ID.unique(); prod=p.Product_ID.unique(); si=pd.Categorical(p.Store_ID,categories=s).codes; pi=pd.Categorical(p.Product_ID,categories=prod).codes
 observed=d.groupby(['week','Store_ID']).size().unstack().reindex(index=weeks,columns=s).notna().to_numpy()[:,si]
 first=d.groupby(K).date.min().reindex(pairs)
 known=observed & (weeks.to_numpy()[:,None]>first.to_numpy()[None,:])
 valid=d[(d.Quantity>0)&d.Order_Status.str.strip().str.lower().ne('cancelled')]
 hist=valid.groupby(['week']+K).Quantity.sum().unstack(K).reindex(index=weeks,columns=pairs).fillna(0).to_numpy(float)
 hist[~known]=np.nan
 prep_seconds=time.perf_counter()-prep_start
 fit_start=time.perf_counter()
 local=np.nanmean(hist,axis=0); count=np.isfinite(hist).sum(axis=0)
 pm=np.array([np.nanmean(hist[:,pi==j]) for j in range(len(prod))]); sm=np.array([np.nanmean(hist[:,si==j]) for j in range(len(s))])
 pooled=pm[pi]*sm[si]/max(np.nanmean(hist),1e-12)
 model=(count*local+13*pooled)/(count+13)
 np.savez(ROOT/'selected_model.npz',weekly_recorded_units=model,Product_ID=p.Product_ID.to_numpy(dtype=str),Store_ID=p.Store_ID.to_numpy(dtype=str))
 fit_seconds=time.perf_counter()-fit_start
 infer_start=time.perf_counter()
 a=p.merge(i,on=K,validate='one_to_one',suffixes=('','_stock'))
 horizon=a.Supplier_Lead_Time_Days+a.Review_Period_Days; forecast=model*horizon/7
 inc=[]
 for j,row in a.iterrows():
  inc.append(r.loc[(r.Product_ID==row.Product_ID)&(r.Store_ID==row.Store_ID)&(pd.to_datetime(r.Expected_Arrival_Date)<=origin+pd.Timedelta(days=int(horizon.iloc[j]))),'Incoming_Qty'].sum())
 need=np.maximum(0,forecast+a.Safety_Stock_Qty-a.Usable_On_Hand_Qty-np.array(inc))
 qty=np.where(need>1e-10,np.ceil(np.maximum(need,a.Minimum_Order_Qty)/a.Order_Multiple_Qty)*a.Order_Multiple_Qty,0).astype(int)
 out=a[K].copy(); out['OrderQty']=qty; out['Forecast_Next_Week_Units']=np.round(model,3); out['Quantity_Unit']='product_unit'
 out.to_csv(ROOT/'routine_orders.csv',index=False)
 infer_seconds=time.perf_counter()-infer_start
 delivered=pd.read_csv(ROOT/'restocking.csv')
 assert delivered[K+['OrderQty','Quantity_Unit','Forecast_Next_Week_Units']].equals(out[K+['OrderQty','Quantity_Unit','Forecast_Next_Week_Units']])
 peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
 workload={'preparation_seconds':prep_seconds,'fit_seconds':fit_seconds,'inference_and_order_calculation_seconds':infer_seconds,'end_to_end_including_imports_seconds':time.perf_counter()-START,'cpu_seconds_after_imports':time.process_time()-CPU,'process_peak_rss_bytes_including_imports_and_preparation':peak,'fit_and_inference_peak_memory_conservative_upper_bound_bytes':peak,'retained_model_bytes':model.nbytes,'training_array_bytes':hist.nbytes,'dependencies':{'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__},'workload':'26 weeks, 336 series; read 17,406 sales CSV rows, deduplicate to 17,364. Current receipts, stock and policy. No network or model-service calls. Single CPU thread configuration.','limits':'OS process high-water RSS gives a conservative bound on both fit and inference, including preparation and retained arrays. Run on 128 GiB host, not a machine capped at 8 GB; time will vary. Measured capacity leaves substantial room below 8 GB for OS and other applications. Does not establish arbitrary future scalability.','cost':'No paid model/API required for routine weekly run. Existing computer plus electricity or hosting still costs money; no applicable local rates or AI-build usage/pricing available.'}
 (ROOT/'routine_workload.json').write_text(json.dumps(workload,indent=2)+'\n')
 print(json.dumps(workload,indent=2))
if __name__=='__main__': run()
