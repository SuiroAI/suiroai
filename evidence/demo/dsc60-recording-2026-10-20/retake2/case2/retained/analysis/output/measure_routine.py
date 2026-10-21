"""One measured production invocation and independent quantity verification."""
import hashlib,json,os,platform,resource,subprocess,sys,time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent.resolve(); SRC=ROOT.parent/'released'
inputs={'sales_path':SRC/'input-4.csv','stock_path':SRC/'input-3.csv','deliveries_path':SRC/'input-2.csv','policy_path':SRC/'input-1.csv'}
output=ROOT/'restocking.csv'
if output.exists(): output=ROOT/'routine_verified.csv'
command=[sys.executable,str(ROOT/'restock_routine.py')]
for key,path in inputs.items(): command+=['--'+key.replace('_','-'),str(path)]
command+=['--planning-date','2025-11-30','--output-path',str(output)]
t=time.perf_counter(); cpu0=resource.getrusage(resource.RUSAGE_CHILDREN)
run=subprocess.run(command,capture_output=True,text=True,check=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
wall=time.perf_counter()-t; used=resource.getrusage(resource.RUSAGE_CHILDREN)
stages=json.loads(run.stdout)
actual=pd.read_csv(output,keep_default_na=False)
# Independent grouped calculation, not restock_routine.calculate or its forecast function.
raw=pd.read_csv(inputs['sales_path']).drop_duplicates()
raw['date']=pd.to_datetime(raw.Order_Date)
raw['status']=raw.Order_Status.str.strip().str.lower()
history=raw[raw.date.between('2025-09-08','2025-11-30')&raw.status.isin(['completed','shipped','returned'])&raw.Quantity.ge(0)]
keys=['Product_ID','Store_ID']
q=history.groupby(keys).Quantity.sum()
prod=history.groupby('Product_ID').Quantity.sum()
store=history.groupby('Store_ID').Quantity.sum()
stock=pd.read_csv(inputs['stock_path']); policy=pd.read_csv(inputs['policy_path']); receipts=pd.read_csv(inputs['deliveries_path'])
joined=stock.merge(policy,on=keys,validate='one_to_one').set_index(keys)
forecast_diff=[]; order_diff=[]; timing_diff=[]; balance_checks=[]
for r in actual.itertuples(index=False):
    k=(r.Product_ID,r.Store_ID); op=joined.loc[k]
    rate=(q.get(k,0)+28*(prod.get(r.Product_ID,0)*store.get(r.Store_ID,0)/history.Quantity.sum()/84))/112
    horizon=int(op.Supplier_Lead_Time_Days+op.Review_Period_Days)
    inc=receipts[receipts.Product_ID.eq(r.Product_ID)&receipts.Store_ID.eq(r.Store_ID)]
    due=inc[pd.to_datetime(inc.Expected_Arrival_Date).le(pd.Timestamp('2025-11-30')+pd.Timedelta(days=horizon))].Incoming_Qty.sum()
    shortage=rate*horizon+op.Safety_Stock_Qty-op.Usable_On_Hand_Qty-due
    expected=0 if shortage<=1e-9 else int(np.ceil(max(shortage,op.Minimum_Order_Qty)/op.Order_Multiple_Qty-1e-12)*op.Order_Multiple_Qty)
    order_diff.append(abs(r.OrderQty-expected)); forecast_diff.append(abs(r.Forecast_Coverage_Units-round(rate*horizon,3)))
    # Cumulative supply minus cumulative requirement independently checks the dated projection.
    deficits=[]; pre=[]; first=''
    for day in range(1,horizon+1):
        date=pd.Timestamp('2025-11-30')+pd.Timedelta(days=day)
        supply=op.Usable_On_Hand_Qty+inc.loc[pd.to_datetime(inc.Expected_Arrival_Date).le(date),'Incoming_Qty'].sum()
        if day>=op.Supplier_Lead_Time_Days: supply+=expected
        gap=max(0.,day*rate-supply)
        if gap>1e-9 and not first: first=str(date.date())
        deficits.append(gap)
        if day<op.Supplier_Lead_Time_Days: pre.append(gap)
    timing_diff.append(first!=r.First_Projected_Shortage_Date or abs(round(max(deficits),3)-r.Projected_Max_Shortage_Units)>1e-9 or abs(round(max(pre,default=0.),3)-r.Shortage_Before_New_Order_Units)>1e-9)
    balance_checks.append(op.Usable_On_Hand_Qty+due+expected-rate*horizon>=op.Safety_Stock_Qty-1e-9)
assert len(actual)==336 and not actual.duplicated(keys).any()
assert actual.OrderQty.ge(0).all() and actual.OrderQty.mod(1).eq(0).all()
assert actual.Quantity_Unit.eq('product_unit').all()
assert max(order_diff)==0 and max(forecast_diff)==0 and not any(timing_diff) and all(balance_checks)
assert not any(c.lower() in ['synthetic','provenance','illustrative_synthetic_stock'] for c in actual.columns)
digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
measure={
 'planning_date':'2025-11-30','command':command,'command_exit_code':run.returncode,
 'local_weekly_wall_seconds_including_interpreter_imports_preparation_fit_inference_output':wall,
 'child_cpu_user_seconds':used.ru_utime-cpu0.ru_utime,'child_cpu_system_seconds':used.ru_stime-cpu0.ru_stime,
 'whole_routine_peak_rss_bytes':used.ru_maxrss if sys.platform=='darwin' else used.ru_maxrss*1024,
 'peak_measurement':'OS child-process high-water RSS in a fresh measurement process; includes imports and retained input frames, fitting, predictions and output. Single local run, not a worst-case guarantee. Host physical RAM not used as target assumption.',
 'stage_measurements':stages,'dependencies':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__},
 'runtime_environment':{'platform':platform.platform(),'machine':platform.machine(),'thread_limits':{'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}},
 'input_files':{k:{'path':str(v),'sha256':digest(v),'bytes':v.stat().st_size} for k,v in inputs.items()},
 'program_sha256':digest(ROOT/'restock_routine.py'),'output_sha256':digest(output),
 'output_agreement':{'method':'Independent aggregation and cumulative supply calculation in measure_routine.py; compare every row against measured CLI output','rows':len(actual),'max_order_difference_units':int(max(order_diff)),'max_rounded_coverage_forecast_difference_units':float(max(forecast_diff)),'timing_mismatched_rows':int(sum(timing_diff)),'all_end_balances_at_or_above_safety_stock':all(balance_checks),'delivered_csv_byte_identical':output.read_bytes()==(ROOT/'restocking.csv').read_bytes()},
 'routine_usage_cost_internal':{'paid_model_or_api_calls':0,'network_calls':0,'llm_required':False,'routine_paid_api_cost':0,'ai_assisted_build_cost':'Not available from this runtime; not estimated or inferred from routine timing.','ai_assisted_build_elapsed':'Separate from local calculation, not measured by this file.'},
 'eight_gb_assessment':'Whole measured process far below 1 GB at released 5 MB / 17,406-row sales size and 336 operational keys; comfortably leaves room for OS and ordinary applications within 8 GB. Selected pooling requires only pandas/numpy; numeric fitted rates 2,688 bytes, 336x14 forecast array 37,632 bytes. Full raw CSV is loaded for validation/deduplication. Scaling is mainly linear in transaction rows; reject input conflicts and remeasure on much larger files. No paid APIs or GPU.',
 'limitations':'Single warm-filesystem local CPU measurement; OS RSS excludes other processes and may omit some allocator/shared-library overhead. Fit/inference stage times exclude imports but whole-process wall/RSS includes them. Whole-process peak provides a conservative measured upper bound for both fitting and inference; stage-isolated RSS not sampled. Not a benchmark of AI-assisted analysis/build or a measurement of manual working time.',
 'measurement_history':'Initial CLI calculation and independent checks succeeded, but measurement serialization failed on a NumPy integer. This retained measured rerun writes a separate output and compares bytes with the initial delivered CSV; no input changes.'}
(ROOT/'routine_measurements.json').write_text(json.dumps(measure,indent=2))
(ROOT/'result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest(output)},indent=2))
summary={'rows':len(actual),'order_rows':int(actual.OrderQty.gt(0).sum()),'zero_rows':int(actual.OrderQty.eq(0).sum()),'order_units':int(actual.OrderQty.sum()),'projected_shortage_rows':int(actual.First_Projected_Shortage_Date.ne('').sum()),'prearrival_shortage_rows':int(actual.Shortage_Before_New_Order_Units.gt(0).sum()),'runtime_seconds':wall,'peak_rss_bytes':measure['whole_routine_peak_rss_bytes'],'store_orders':actual.groupby('Store_ID').OrderQty.sum().to_dict()}
(ROOT/'operational_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
print(actual.sort_values(['Shortage_Before_New_Order_Units','OrderQty'],ascending=False).head(8).to_string(index=False))
