"""Run the selected CLI once; measure and independently check arithmetic."""
import hashlib
import json
import math
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
from restock_routine import load_inputs,daily_sales,fit_forecaster,predict_days,order_table,SELECTED_MODEL

def main():
    command=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv','--planning-date','2025-11-30','--output-path','restocking.csv']
    t=time.perf_counter()
    run=subprocess.run(command,capture_output=True,text=True,check=True)
    wall=time.perf_counter()-t
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    phases=json.loads(run.stdout.splitlines()[-1])
    output=pd.read_csv('restocking.csv')
    s,stock,inbound,policy,date,pairs=load_inputs('../released/input-4.csv','../released/input-3.csv','../released/input-2.csv','../released/input-1.csv','2025-11-30')
    daily=daily_sales(s,pairs,date)
    fitted=fit_forecaster(daily,date,SELECTED_MODEL)
    pred=predict_days(fitted,date,14,len(pairs))
    reference=order_table(s,stock,inbound,policy,date,pairs,pred)
    pd.testing.assert_frame_equal(output,reference,check_dtype=False)
    # Separate arithmetic path: transaction totals over 182 days, not the routine's daily pivot.
    window_start=date-pd.Timedelta(days=181)
    mask=s.Order_Date.between(window_start,date) & s.status.isin(['completed','shipped']) & s.Quantity.gt(0)
    totals=s[mask].groupby(['Product_ID','Store_ID']).Quantity.sum()
    errors=[]; timing_errors=[]
    for row in output.itertuples():
        key=(row.Product_ID,row.Store_ID); p=policy.loc[key]; st=stock.loc[key]
        rate=float(totals.get(key,0))/182
        h=int(p.Supplier_Lead_Time_Days+p.Review_Period_Days)
        receipts=inbound[(inbound.Product_ID==key[0]) & (inbound.Store_ID==key[1])]
        eligible=receipts[receipts.Expected_Arrival_Date<=date+pd.Timedelta(days=h)].Incoming_Qty.sum()
        gap=max(0,rate*h+float(p.Safety_Stock_Qty)-float(st.Usable_On_Hand_Qty)-eligible)
        q=0 if gap<=1e-10 else int(p.Order_Multiple_Qty)*math.ceil(max(gap,float(p.Minimum_Order_Qty))/int(p.Order_Multiple_Qty)-1e-12)
        if q!=row.OrderQty: errors.append(key)
        shortages=[]
        for day in range(1,int(p.Supplier_Lead_Time_Days)+1):
            prior=receipts[receipts.Expected_Arrival_Date<date+pd.Timedelta(days=day)].Incoming_Qty.sum()
            shortages.append(max(0,rate*day-float(st.Usable_On_Hand_Qty)-prior))
        if abs(max(shortages)-row.Expected_Shortage_Before_New_Order_Qty)>0.000051:timing_errors.append(key)
    assert not errors and not timing_errors
    assert output.OrderQty.ge(0).all() and output.OrderQty.eq(output.OrderQty.astype(int)).all()
    assert len(output)==336 and not output.duplicated(['Product_ID','Store_ID']).any()
    assert (output.OrderQty % output.Order_Multiple_Qty).eq(0).all()
    assert (output.OrderQty.eq(0) | output.OrderQty.ge(output.Minimum_Order_Qty)).all()
    sensitivities={}
    for label,mult in [('demand_minus_25_percent',.75),('demand_plus_25_percent',1.25)]:
        alt=order_table(s,stock,inbound,policy,date,pairs,pred,mult)
        sensitivities[label]={'total_order_units':int(alt.OrderQty.sum()),'rows_with_changed_order':int(alt.OrderQty.ne(output.OrderQty).sum()),'positive_orders':int(alt.OrderQty.gt(0).sum()),'timing_flags':int(alt.Review_Before_Arrival.sum())}
    alt_daily=daily_sales(s,pairs,date,exclude_returns=True)
    alt_pred=predict_days(fit_forecaster(alt_daily,date,SELECTED_MODEL),date,14,len(pairs))
    alt=order_table(s,stock,inbound,policy,date,pairs,alt_pred)
    sensitivities['exclude_return_flagged_fulfilled_rows']={'total_order_units':int(alt.OrderQty.sum()),'changed_orders':int(alt.OrderQty.ne(output.OrderQty).sum()),'units_in_target_window_removed':float(daily.tail(182).to_numpy().sum()-alt_daily.tail(182).to_numpy().sum())}
    output.groupby('Store_ID').agg(OrderQty=('OrderQty','sum'),Products_To_Order=('OrderQty',lambda x:int(x.gt(0).sum())),Timing_Reviews=('Review_Before_Arrival','sum')).to_csv('store_summary.csv')
    summary={'rows':len(output),'order_units':int(output.OrderQty.sum()),'positive_order_rows':int(output.OrderQty.gt(0).sum()),'zero_order_rows':int(output.OrderQty.eq(0).sum()),'timing_flag_rows':int(output.Review_Before_Arrival.sum()),'timing_flags_without_order':int((output.Review_Before_Arrival & output.OrderQty.eq(0)).sum()),'sensitivities':sensitivities,'independent_arithmetic_mismatches':errors,'independent_timing_mismatches':timing_errors,'flags_receipt_assumption':'Receipts arrive end of due day. Pre-new-order shortage is maximum cumulative forecast gap before new receipt, not guaranteed lost sales; existing receipts can alleviate gaps later. Demand +/-25% are scenarios, not confidence bounds.'}
    Path('order_validation.json').write_text(json.dumps(summary,indent=2))
    sha=hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
    result={'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha}
    Path('result.json').write_text(json.dumps(result,indent=2))
    record={'command':command,'planning_date':'2025-11-30','selected_model':SELECTED_MODEL,'local_calculation_wall_seconds_including_python_startup_imports_read_fit_infer_write':wall,'cpu_user_seconds':usage.ru_utime,'cpu_system_seconds':usage.ru_stime,'process_peak_rss_bytes':int(usage.ru_maxrss if platform.system()=='Darwin' else usage.ru_maxrss*1024),'phases':phases,'measurement_limits':'One local subprocess run; RSS is OS process high-water, phase peaks cumulative, not isolated allocations. Host is not assumed to have 8 GB. Background load and filesystem cache affect timing; OS memory and separate analysis/build excluded. No paid model/API calls.','dependencies':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__},'machine':platform.machine(),'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('../released').glob('*.csv'))},'routine_sha256':hashlib.sha256(Path('restock_routine.py').read_bytes()).hexdigest(),'output_sha256':sha,'output_agreement':{'matches_selected_calculation':True,'independently_recomputed_order_quantities_all_rows':True,'independently_recomputed_timing_flags_all_rows':True,'pack_minimum_unit_checks':True},'ordinary_8gb_assessment':'Observed full process peak well below 1 GB for 17,406 input rows, 336 pairs and 1,430 days. Selected mean retains only 336 rates and needs pandas/numpy; no GPU or model server. Fits 8 GB with substantial OS headroom at this workload, not a benchmark on an 8 GB host. Data preparation included.','ongoing_cost':'No paid model service required. Existing computer, power or hosting still have costs; no measured electricity or local applicable rates supplied.','ai_analysis_build_cost':'Not estimable from available evidence: actual AI usage and applicable billed pricing not provided. Local calculation timing is separate.'}
    Path('routine_measurements.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(summary,indent=2)); print('local seconds',wall,'peak bytes',record['process_peak_rss_bytes']); print(output.sort_values(['OrderQty','Store_ID'],ascending=[False,True]).head(10).to_string(index=False))

if __name__=='__main__':main()
