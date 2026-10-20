"""Check paired experiment rows against independent source-based reconstruction.

Never execute either generated arm. Only reads the already-released November
inputs through our own recompute.py and the arms' development prediction CSVs.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import contextlib,io,json,runpy
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):n=runpy.run_path(str(HERE/'recompute.py'))
ROOT=n['ROOT'];RUN=ROOT/'artifacts/dsc60-paired-normal-host-2026-10-20'
models={'local_28':'recent_4_weeks','local_91':'recent_13_weeks','baseline_91':'recent_13_weeks','local_182':'recent_26_weeks','local_364':'annual_average','shared':'shared_patterns','seasonal':'shared_seasonal'}
results=[]
for arm in ('historical','structured'):
 p=RUN/arm/'output/comparison_rows.csv'
 if not p.exists():
  results.append({'arm':arm,'status':'pending comparison rows'});continue
 frame=pd.read_csv(p)
 if "method" in frame:frame=frame.rename(columns={"method":"model"})
 if "horizon_days" in frame:frame=frame[frame.horizon_days==7]
 required={'origin','model','Product_ID','Store_ID','actual_units','forecast_units'}
 if not required<=set(frame):
  results.append({'arm':arm,'status':'unsupported columns','columns':list(frame)});continue
 max_a=max_p=0.;unexpected=[];seen=set()
 for (origin,model),g in frame.groupby(['origin','model']):
  start=pd.Timestamp(origin);cutoff=start-pd.Timedelta(days=1)
  if start>pd.Timestamp('2025-11-24'):raise ValueError('Forbidden target period')
  method=models.get(model,model)
  expected=n['predict'](cutoff,7)[method]
  actual=np.nansum(n['Y'][n['tmap'][cutoff]+1:n['tmap'][cutoff]+8],axis=0)
  for r in g.itertuples():
   j=n['lookup'][(r.Product_ID,r.Store_ID)];max_a=max(max_a,abs(float(r.actual_units)-actual[j]));max_p=max(max_p,abs(float(r.forecast_units)-expected[j]))
   key=(origin,method,r.Product_ID,r.Store_ID)
   if key in seen:unexpected.append('duplicate prediction key')
   seen.add(key)
 expected_count=20*6*336
 results.append({'arm':arm,'rows':len(frame),'expected_rows':expected_count,'max_actual_absolute_difference':max_a,'max_prediction_absolute_difference':max_p,'unique_prediction_keys':len(seen),'unexpected':unexpected,'pass':bool(len(frame)==expected_count and len(seen)==expected_count and max_a<1e-10 and max_p<1e-10)})
(HERE/'paired_prediction_crosscheck.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
