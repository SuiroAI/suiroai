#!/usr/bin/env python3
"""Weekly non-LLM restocking; ship alongside forecasting.py. No network calls."""
import argparse
import json
import math
import os
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from forecasting import KEYS,load_sales,weekly_panel,forecast

SELECTED_METHOD='croston_sba'  # Frozen selection: evaluation_plan v1 / comparison_results.json.

def require(condition,message):
    if not condition: raise ValueError(message)

def read_table(path,required):
    d=pd.read_csv(path)
    require(set(required).issubset(d.columns),f'Missing columns in {path}: {set(required)-set(d.columns)}')
    require(not d[required].isna().any().any(),f'Missing required values in {path}')
    return d

def numeric(d,columns,positive=()):
    for c in columns:
        d[c]=pd.to_numeric(d[c],errors='raise')
        require(bool(np.isfinite(d[c]).all() and (d[c]>=0).all() and (d[c]%1==0).all()),f'Invalid nonnegative integer {c}')
        if c in positive: require(bool((d[c]>0).all()),f'{c} must be positive')

def calculate(sales_path,stock_path,deliveries_path,policy_path,planning_date):
    date=pd.Timestamp(planning_date)
    require(not pd.isna(date) and date==date.normalize() and date.tz is None,'Planning date must be a plain calendar date')
    stock=read_table(stock_path,KEYS+['Snapshot_Date','Usable_On_Hand_Qty','On_Order_Qty','Open_Order_Ledger_Complete','Quantity_Unit'])
    policy=read_table(policy_path,KEYS+['Effective_Date','Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty','Quantity_Unit'])
    receipts=read_table(deliveries_path,KEYS+['PO_Line_ID','Order_Date','Expected_Arrival_Date','Incoming_Qty','Quantity_Unit'])
    for t in [stock,policy,receipts]: require(bool(t.Quantity_Unit.eq('product_unit').all()),'All quantities must use product_unit')
    for t in [stock,policy]: require(not t.duplicated(KEYS).any(),'Stock/policy must have unique product and store keys')
    require(not receipts.PO_Line_ID.duplicated().any(),'Duplicate receipt line')
    numeric(stock,['Usable_On_Hand_Qty','On_Order_Qty'])
    numeric(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty'],['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty'])
    numeric(receipts,['Incoming_Qty'])
    require(bool(stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all()),'Complete incoming ledger required to calculate net needs')
    require(bool(pd.to_datetime(stock.Snapshot_Date,format='%Y-%m-%d',errors='raise').eq(date).all()),'Stock snapshot must match planning date')
    require(bool(pd.to_datetime(policy.Effective_Date,format='%Y-%m-%d',errors='raise').le(date).all()),'Policy is not yet effective')
    receipts['due']=pd.to_datetime(receipts.Expected_Arrival_Date,format='%Y-%m-%d',errors='raise')
    ordered=pd.to_datetime(receipts.Order_Date,format='%Y-%m-%d',errors='raise')
    require(bool(ordered.le(date).all() and receipts.due.ge(ordered).all()),'Invalid receipt order/due dates')
    pairs=pd.MultiIndex.from_frame(stock[KEYS]).sort_values()
    require(set(pairs)==set(pd.MultiIndex.from_frame(policy[KEYS])),'Stock and policy keys differ')
    require(set(pd.MultiIndex.from_frame(receipts[KEYS])).issubset(set(pairs)),'Receipts have unknown keys')
    ledger=receipts.groupby(KEYS).Incoming_Qty.sum().reindex(pairs,fill_value=0)
    stock=stock.set_index(KEYS).reindex(pairs);policy=policy.set_index(KEYS).reindex(pairs)
    require(bool(np.array_equal(ledger.to_numpy(),stock.On_Order_Qty.to_numpy())),'Incoming deliveries do not match stock records')
    d,target,first,names=load_sales(sales_path,date)
    require(set(pairs).issubset(set(first.index)),'No sales history for some stock keys; quantity unsupported')
    require(d.date.max()==date,'Sales extract must extend through planning date')
    # Require daily global coverage for the training extract; local omissions still require assumption.
    require(d.date.nunique()==len(pd.date_range(d.date.min(),date)),'Global missing calendar dates; completeness cannot be assumed')
    panel=weekly_panel(target,first,date)
    require(set(pairs).issubset(set(pd.MultiIndex.from_frame(panel[KEYS]))),'Insufficient completed-week history')
    require(bool((panel.groupby(KEYS).size().reindex(pairs)>=8).all()),'At least eight full calendar weeks required')
    horizons=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).astype(int)
    require(int(horizons.max())<=366,'Coverage horizon exceeds supported one-year bound')
    forecasts,timings=forecast(panel,pairs,date,SELECTED_METHOD,max(7,int(horizons.max())))
    rows=[]
    for i,(product,store) in enumerate(pairs):
        key=(product,store);s=stock.loc[key];p=policy.loc[key]
        lead=int(p.Supplier_Lead_Time_Days);h=int(horizons.loc[key])
        r=receipts[(receipts.Product_ID==product)&(receipts.Store_ID==store)]
        incoming=np.zeros(h)
        for _,receipt in r.iterrows():
            offset=(receipt.due-date).days
            if 1<=offset<=h: incoming[offset-1]+=receipt.Incoming_Qty
        cover=float(forecasts[i,:h].sum());week=float(forecasts[i,:7].sum());safe=int(p.Safety_Stock_Qty)
        raw=max(0.,cover+safe-int(s.Usable_On_Hand_Qty)-float(incoming.sum()))
        multiple=int(p.Order_Multiple_Qty);minimum=int(p.Minimum_Order_Qty)
        qty=0 if raw<=1e-12 else int(math.ceil(max(raw,minimum)/multiple)*multiple)
        demand=np.cumsum(forecasts[i,:h]);supply=int(s.Usable_On_Hand_Qty)+np.cumsum(incoming)
        pre=int(math.ceil(max(0.,float(np.max(demand[:lead-1]-supply[:lead-1]))))) if lead>1 else 0
        supply[lead-1:]+=qty
        shortage=int(math.ceil(max(0.,float(np.max(demand-supply)))))
        flags=[]
        if pre:flags.append('SHORTAGE_BEFORE_NEW_ORDER')
        if shortage:flags.append('TIMING_SHORTAGE_WITH_ORDER')
        overdue=int(r.loc[r.due<=date,'Incoming_Qty'].sum())
        if overdue:flags.append('OVERDUE_RECEIPT_EXCLUDED_CONFIRM_ARRIVAL')
        if date.weekday()!=6:flags.append('PARTIAL_CURRENT_WEEK_NOT_USED')
        if (panel.loc[(panel.Product_ID==product)&(panel.Store_ID==store),'units']>0).sum()<10:flags.append('VERY_SPARSE_SALES')
        rows.append({'Product_ID':product,'Product_Name':names.get(product,''),'Store_ID':store,'OrderQty':qty,'Quantity_Unit':'product_unit','Planning_Date':date.date().isoformat(),'Forecast_Next_7_Days':round(week,6),'Coverage_Days':h,'Forecast_Coverage_Units':round(cover,6),'Usable_On_Hand_Qty':int(s.Usable_On_Hand_Qty),'Incoming_Within_Coverage_Qty':int(incoming.sum()),'Safety_Stock_Qty':safe,'Net_Need_Before_Rounding':round(raw,6),'Order_Multiple_Qty':multiple,'Minimum_Order_Qty':minimum,'New_Order_Arrival_Date':(date+pd.Timedelta(days=lead)).date().isoformat(),'Coverage_End_Date':(date+pd.Timedelta(days=h)).date().isoformat(),'Expected_Shortage_Before_New_Order_Qty':pre,'Projected_Timing_Shortage_With_Order_Qty':shortage,'Overdue_Incoming_Qty_Excluded':overdue,'Review_Flags':';'.join(flags)})
    return pd.DataFrame(rows),timings

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['sales','stock','deliveries','policy']:parser.add_argument('--'+name+'-path',type=Path,required=True)
    parser.add_argument('--planning-date',required=True)
    parser.add_argument('--output-path',type=Path,required=True)
    a=parser.parse_args()
    try:
        pd.to_datetime(a.planning_date,format='%Y-%m-%d',errors='raise')
        inputs=[a.sales_path,a.stock_path,a.deliveries_path,a.policy_path]
        protected=inputs+[Path(__file__),Path(__file__).with_name('forecasting.py')]
        require(all(p.is_file() for p in inputs),'Input file missing')
        require(a.output_path.resolve() not in [p.resolve() for p in protected],'Output would overwrite a source file')
        require(not a.output_path.exists(),'Output exists; choose a fresh output path')
        out,timing=calculate(*inputs,a.planning_date)
        # Exclusive file creation prevents accidental overwrite, including races.
        with a.output_path.open('x',newline='') as f:out.to_csv(f,index=False,lineterminator='\n')
        print(json.dumps({'rows':len(out),'order_units':int(out.OrderQty.sum()),'method':SELECTED_METHOD,'model_workload':timing}))
    except (ValueError,KeyError,OSError) as e:parser.exit(2,f'Input/output error: {e}\n')

if __name__=='__main__':main()
