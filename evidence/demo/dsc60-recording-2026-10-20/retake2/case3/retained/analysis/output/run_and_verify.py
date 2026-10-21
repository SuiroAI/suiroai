"""Measure the actual CLI, then independently check quantities, flags and file agreement."""
import subprocess, sys, time, json, hashlib, platform, importlib.metadata
from pathlib import Path
import pandas as pd
import numpy as np

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

cmd=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv','--planning-date','2025-11-30','--output-path','restocking.csv']
start=time.perf_counter(); proc=subprocess.run(cmd,capture_output=True,text=True,check=True); elapsed=time.perf_counter()-start
metrics=json.loads(proc.stdout)
out=pd.read_csv('restocking.csv',keep_default_na=False)
policy=pd.read_csv('../released/input-1.csv').set_index(['Product_ID','Store_ID']).sort_index()
stock=pd.read_csv('../released/input-3.csv').set_index(['Product_ID','Store_ID']).sort_index()
receipts=pd.read_csv('../released/input-2.csv');receipts.Expected_Arrival_Date=pd.to_datetime(receipts.Expected_Arrival_Date)
raw=pd.read_csv('../released/input-4.csv').drop_duplicates();raw.Order_Date=pd.to_datetime(raw.Order_Date)
valid=raw.Order_Status.str.strip().str.lower().isin(['completed','shipped','returned']) & raw.Quantity.gt(0)
recent=raw.loc[valid & raw.Order_Date.between('2025-09-01','2025-11-30')].groupby(['Product_ID','Store_ID']).Quantity.sum().reindex(policy.index,fill_value=0)/91
shared=recent.groupby(level=0).transform('mean'); rate=(91*recent+28*shared)/119
require=[]; matched=0; pre_flags=0; timing_flags=0
expected_rows=[]
for row in out.itertuples(index=False):
    key=(row.Product_ID,row.Store_ID);p=policy.loc[key];s=stock.loc[key]
    h=int(p.Supplier_Lead_Time_Days+p.Review_Period_Days);lead=int(p.Supplier_Lead_Time_Days)
    inc=receipts.loc[(receipts.Product_ID==key[0])&(receipts.Store_ID==key[1])]
    arrived=inc.loc[inc.Expected_Arrival_Date<=pd.Timestamp('2025-11-30')+pd.Timedelta(days=h)].Incoming_Qty.sum()
    deficit=max(0,float(rate[key])*h+int(p.Safety_Stock_Qty)-int(s.Usable_On_Hand_Qty)-int(arrived))
    expected=0 if deficit<1e-10 else int(np.ceil(max(deficit,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty)
    assert expected==row.OrderQty
    assert abs(row.Forecast_Coverage_Units-rate[key]*h)<=.000501
    assert row.Incoming_Within_Coverage_Units==arrived
    assert row.OrderQty>=0 and row.OrderQty%int(p.Order_Multiple_Qty)==0
    assert not row.OrderQty or row.OrderQty>=p.Minimum_Order_Qty
    # Independent cumulative path, receipts start of due date, new order start of lead date.
    days=np.arange(1,h+1);received=np.array([inc.loc[inc.Expected_Arrival_Date<=pd.Timestamp('2025-11-30')+pd.Timedelta(days=int(x))].Incoming_Qty.sum() for x in days])
    balance=int(s.Usable_On_Hand_Qty)+received+np.where(days>=lead,row.OrderQty,0)-days*rate[key]
    pre=max(0.,-min([float(s.Usable_On_Hand_Qty),*balance[days<lead]])); timing=max(0.,-min([float(s.Usable_On_Hand_Qty),*balance]))
    assert abs(pre-row.Projected_Shortage_Before_New_Order_Units)<=.000501
    assert abs(timing-row.Projected_Timing_Shortage_Units)<=.000501
    first=np.where(balance < -1e-9)[0]
    expectdate='' if not len(first) else (pd.Timestamp('2025-12-01')+pd.Timedelta(days=int(first[0]))).strftime('%Y-%m-%d')
    assert expectdate==row.First_Projected_Shortage_Date
    assert ('Review shortage before new order arrives' in row.Review_Flags)==(pre>1e-9)
    pre_flags+=pre>1e-9;timing_flags+=timing>1e-9
    expected_rows.append((key[0],key[1],expected))
    matched+=1
assert len(out)==len(policy)==336 and not out.duplicated(['Product_ID','Store_ID']).any()
assert set(out.Quantity_Unit)=={'product_unit'}
assert not any(c.lower() in ['provenance','synthetic','illustrative_synthetic_stock'] for c in out)
assert len(raw.loc[raw.Order_Date>'2025-11-30'])==0
summary={'rows':len(out),'positive_orders':int(out.OrderQty.gt(0).sum()),'zero_orders':int(out.OrderQty.eq(0).sum()),'total_units':int(out.OrderQty.sum()),'shortage_before_new_arrival_rows':int(pre_flags),'timing_shortage_rows':int(timing_flags),'stores':out.Store_ID.nunique(),'products':out.Product_ID.nunique(),'order_units_by_store':out.groupby('Store_ID').OrderQty.sum().to_dict(),'top_orders':out.sort_values('OrderQty',ascending=False).head(10)[['Product_ID','Product_Name','Store_ID','OrderQty']].to_dict('records')}
Path('order_summary.json').write_text(json.dumps(summary,indent=2))
digest=sha('restocking.csv')
measure={'command':cmd,'planning_date':'2025-11-30','local_weekly_calculation_elapsed_seconds_including_process_startup':elapsed,'routine_reported':metrics,'dependency_versions':{x:importlib.metadata.version(x) for x in ['numpy','pandas']},'python':sys.version,'platform':platform.platform(),'source_hashes':{f'input-{i}.csv':sha(f'../released/input-{i}.csv') for i in range(1,5)},'program_sha256':sha('restock_routine.py'),'output_sha256':digest,'output_agreement':{'delivered_file_is_cli_output':True,'all_order_quantities_independently_recomputed':matched,'coverage_forecasts_and_incoming_checked':True,'all_timing_shortage_quantities_and_first_dates_checked':True,'csv_round_trip_checked':True},'measurement_scope':'One actual 2025-11-30 invocation, isolated from candidate fitting. Wall time includes interpreter startup, imports, all input preparation, forecast fitting/inference, ordering and CSV output. Process RSS is absolute OS high-water memory, includes imports, prepared frames, arrays and output. It upper-bounds fit and inference, not their separate incremental peaks. Not full AI-assisted analysis/build elapsed time; not a guarantee on other hardware.','cpu_and_memory_assessment':{'threads':1,'cpu_only':True,'gpu':False,'selected_model_retained_rate_bytes':2688,'dense_daily_panel_bytes':3888344,'ordinary_8GB_suitability':'Measured process peak far below 1 GB at supplied 5 MB / 17k-row sales scale. Leaves multiple GB for OS and apps within an 8 GB computer. Host RAM is not assumed to be 8 GB; projection conditional on comparable Python environment and data scale. Memory grows with calendar length times active products at stores plus input rows; future much larger files require remeasurement.'},'routine_running_usage':{'paid_model_or_api_calls':0,'network_calls':0,'language_model_required':False,'AI_assisted_build_cost':'Not measured; distinct from this routine invocation'}}
Path('routine_measurements.json').write_text(json.dumps(measure,indent=2))
Path('result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest},indent=2))
print(json.dumps({'summary':summary,'elapsed_seconds':elapsed,'routine':metrics,'sha256':digest},indent=2))
