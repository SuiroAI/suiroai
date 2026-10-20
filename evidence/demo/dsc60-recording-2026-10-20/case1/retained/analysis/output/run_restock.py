"""Routine selected-model calculation for these approved as-of inputs.

Python, numpy, pandas only. No language models, APIs or network calls.
Run: OPENBLAS_NUM_THREADS=1 python run_restock.py
For a later date supply new authorized sales and operational snapshots and change
ASOF/INPUT_DIR; refuse sales beyond ASOF rather than accidentally reading reserved outcomes.
This script reproduces point forecasts/orders; development uncertainty columns are
kept separately in restocking.csv and must not be represented as calibrated intervals.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import time, resource, sys, json, platform
from pathlib import Path
START=time.perf_counter()
import numpy as np
import pandas as pd
ASOF=pd.Timestamp('2025-11-30')
INPUT_DIR=Path('../released')
def rss():
    x=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return x/(1024**2) if sys.platform=='darwin' else x/1024
measure={'peak_RSS_at_import_MiB':rss()}
tick=time.perf_counter()
s=pd.read_csv(INPUT_DIR/'input-4.csv').drop_duplicates()
s['date']=pd.to_datetime(s.Order_Date)
assert s.date.max()==ASOF
s['status']=s.Order_Status.str.strip().str.lower()
p=pd.read_csv(INPUT_DIR/'input-1.csv').sort_values(['Product_ID','Store_ID']).reset_index(drop=True)
v=pd.read_csv(INPUT_DIR/'input-3.csv');l=pd.read_csv(INPUT_DIR/'input-2.csv')
keys=['Product_ID','Store_ID'];pairs=pd.MultiIndex.from_frame(p[keys])
assert p.Effective_Date.eq(str(ASOF.date())).all() and v.Snapshot_Date.eq(str(ASOF.date())).all()
assert not p.duplicated(keys).any() and not v.duplicated(keys).any() and not l.PO_Line_ID.duplicated().any()
assert v.Open_Order_Ledger_Complete.all()
assert all(d.Quantity_Unit.eq('product_unit').all() and d.Provenance.eq('synthetic').all() for d in [p,v,l])
assert (pd.to_datetime(l.Order_Date)<=ASOF).all() and (pd.to_datetime(l.Expected_Arrival_Date)>ASOF).all()
dates=pd.date_range(s.date.min(),ASOF)
assert len(dates.difference(s.date))==0
assert set(map(tuple,s[keys].values))==set(pairs)
first=s.groupby(keys).date.min().reindex(pairs)
firstidx=np.array([(d-dates[0]).days for d in first])
good=s.Quantity.gt(0)&s.status.isin(['completed','shipped','returned'])
y=s.loc[good].groupby(['date']+keys).Quantity.sum().unstack(keys).reindex(index=dates,columns=pairs).fillna(0).to_numpy(dtype=float)
# Only absent recorded units; not known zero demand. First observation is eligibility start.
measure.update({'load_prepare_seconds':time.perf_counter()-tick,'peak_RSS_after_prepare_MiB':rss(),'panel_shape':list(y.shape),'panel_bytes':int(y.nbytes),'input_sales_rows':len(s)+42})
tick=time.perf_counter()
size=np.zeros(len(pairs));gap=np.ones(len(pairs));last=firstidx.copy();initialized=np.zeros(len(pairs),bool)
for t,z in enumerate(y):
    new=(z>0)&~initialized
    size[new]=z[new];gap[new]=np.maximum(1,t-firstidx[new]+1)
    update=(z>0)&initialized
    size[update]=.1*z[update]+.9*size[update]
    gap[update]=.1*(t-last[update])+.9*gap[update]
    last[z>0]=t;initialized|=new
measure.update({'fit_seconds':time.perf_counter()-tick,'peak_RSS_after_fit_MiB':rss(),'retained_model_state_bytes':sum(a.nbytes for a in [size,gap,last,initialized])})
tick=time.perf_counter()
rate=.95*size/gap
joined=p.merge(v,on=keys,validate='one_to_one',suffixes=('','_stock'))
forecast7=rate*7;forecast=rate*(joined.Supplier_Lead_Time_Days+joined.Review_Period_Days).to_numpy()
measure.update({'inference_seconds':time.perf_counter()-tick,'peak_RSS_after_inference_MiB':rss()})
tick=time.perf_counter()
rows=[]
for j,row in joined.iterrows():
    lines=l[l.Product_ID.eq(row.Product_ID)&l.Store_ID.eq(row.Store_ID)]
    assert int(lines.Incoming_Qty.sum())==row.On_Order_Qty
    end=ASOF+pd.Timedelta(days=int(row.Supplier_Lead_Time_Days+row.Review_Period_Days))
    incoming=lines.loc[pd.to_datetime(lines.Expected_Arrival_Date).le(end),'Incoming_Qty'].sum()
    need=max(0,forecast[j]+row.Safety_Stock_Qty-row.Usable_On_Hand_Qty-incoming)
    qty=int(np.ceil(max(need,row.Minimum_Order_Qty)/row.Order_Multiple_Qty)*row.Order_Multiple_Qty) if need>0 else 0
    rows.append({'Product_ID':row.Product_ID,'Store_ID':row.Store_ID,'OrderQty':qty,'Forecast_Next_7_Days':forecast7[j],'Forecast_Coverage_Units':forecast[j]})
out=pd.DataFrame(rows)
out.to_csv('routine_point_calculations.csv',index=False)
measure.update({'ordering_and_save_seconds':time.perf_counter()-tick,'local_calculation_seconds':time.perf_counter()-START,'process_peak_RSS_MiB':rss(),'dependencies':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},'routine_paid_API_calls':0,'limits':'Fresh-process wall time and high-water resident memory, one host/run. Includes imports, data loading/preparation, fitting, retained arrays/model state, prediction and output. High-water memory is cumulative, not independent phase allocations. No 8GB-host test or extrapolation to much larger data. Only supplied scale. Hardware and electricity not priced.'})
Path('routine_compute_measurements.json').write_text(json.dumps(measure,indent=2))
# Compare independently implemented state and ordering to the original analytical deliverable.
check=out.merge(pd.read_csv('restocking.csv'),on=keys,validate='one_to_one',suffixes=('_routine','_analysis'))
assert check.OrderQty_routine.eq(check.OrderQty_analysis).all()
assert np.allclose(check.Forecast_Next_7_Days_routine,check.Forecast_Next_7_Days_analysis,atol=0.000051)
assert np.allclose(check.Forecast_Coverage_Units_routine,check.Forecast_Coverage_Units_analysis,atol=0.000051)
print(json.dumps(measure,indent=2))
