#!/usr/bin/env python3
"""Weekly local restocking calculation. Run --help. No API/LLM calls."""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd
from forecasting import KEYS, prepare_sales, predict

# Frozen after the prospective development comparison; configuration travels with the routine.
SELECTED_METHOD = 'recent13'

def require(condition, message):
    if not bool(condition):
        raise ValueError(message)

def integers(data, columns, positive=()):
    for col in columns:
        data[col]=pd.to_numeric(data[col],errors='raise')
        require(np.isfinite(data[col]).all() and (data[col]%1==0).all() and (data[col]>=0).all(), 'Invalid nonnegative integer '+col)
        if col in positive:
            require((data[col]>0).all(),'Must be positive: '+col)

def calculate(sales_path, stock_path, deliveries_path, policy_path, planning_date):
    t0=time.perf_counter()
    date=pd.Timestamp(planning_date)
    require(not pd.isna(date) and date==date.normalize() and date.tzinfo is None,'Planning date must be an unzoned calendar date')
    sales,names,duplicates=prepare_sales(sales_path,date)
    require(sales.Order_Date.max()==date,'Sales extract must reach the planning date')
    stock=pd.read_csv(stock_path)
    deliveries=pd.read_csv(deliveries_path)
    policy=pd.read_csv(policy_path)
    required={
        'stock':KEYS+['Snapshot_Date','Usable_On_Hand_Qty','On_Order_Qty','Open_Order_Ledger_Complete','Quantity_Unit'],
        'deliveries':KEYS+['PO_Line_ID','Order_Date','Expected_Arrival_Date','Incoming_Qty','Quantity_Unit'],
        'policy':KEYS+['Effective_Date','Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty','Quantity_Unit']}
    for name,d in [('stock',stock),('deliveries',deliveries),('policy',policy)]:
        require(set(required[name]).issubset(d.columns),'Missing '+name+' columns')
        require(not d[required[name]].isna().any().any(),'Missing '+name+' values')
        require(d.Quantity_Unit.eq('product_unit').all(),'Only product_unit supported')
    stock['Snapshot_Date']=pd.to_datetime(stock.Snapshot_Date,errors='raise')
    policy['Effective_Date']=pd.to_datetime(policy.Effective_Date,errors='raise')
    for c in ['Order_Date','Expected_Arrival_Date']:
        deliveries[c]=pd.to_datetime(deliveries[c],errors='raise')
    require(stock.Snapshot_Date.eq(date).all(),'Stock snapshots must match planning date')
    require(not stock.duplicated(KEYS).any(),'Duplicate stock keys')
    require(not policy.duplicated(KEYS+['Effective_Date']).any(),'Duplicate effective policy keys')
    policy=policy.loc[policy.Effective_Date<=date].sort_values('Effective_Date').drop_duplicates(KEYS,keep='last')
    require(len(policy)>0,'No applicable rules')
    require(set(map(tuple,policy[KEYS].values))==set(map(tuple,stock[KEYS].values)),'Policy and stock key mismatch')
    require(not deliveries.PO_Line_ID.duplicated().any(),'Duplicate incoming line IDs')
    require(set(map(tuple,deliveries[KEYS].values)).issubset(set(map(tuple,stock[KEYS].values))),'Unknown delivery keys')
    require((deliveries.Order_Date<=date).all(),'Incoming order was not known by planning date')
    require((deliveries.Expected_Arrival_Date>=deliveries.Order_Date).all(),'Arrival precedes order')
    require(stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(),'Incomplete incoming ledger')
    integers(stock,['Usable_On_Hand_Qty','On_Order_Qty'])
    integers(deliveries,['Incoming_Qty'])
    integers(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty'],positive=['Review_Period_Days','Order_Multiple_Qty'])
    keys=policy[KEYS].sort_values(KEYS).reset_index(drop=True)
    idx=pd.MultiIndex.from_frame(keys)
    supplied=deliveries.groupby(KEYS).Incoming_Qty.sum().reindex(idx,fill_value=0)
    stock=stock.set_index(KEYS).reindex(idx)
    require(supplied.eq(stock.On_Order_Qty).all(),'Incoming deliveries do not match stock on-order totals')
    rules=policy.set_index(KEYS).reindex(idx)
    prepare_seconds=time.perf_counter()-t0
    forecast,timing=predict(sales,keys,date,SELECTED_METHOD)
    rows=[]
    for i,key in enumerate(idx):
        r=rules.loc[key]; s=stock.loc[key]
        daily=float(forecast[i]/7)
        lead=int(r.Supplier_Lead_Time_Days); coverage=lead+int(r.Review_Period_Days)
        end=date+pd.Timedelta(days=coverage)
        arrival=date+pd.Timedelta(days=lead)
        inbound=deliveries.loc[deliveries.Product_ID.eq(key[0]) & deliveries.Store_ID.eq(key[1])]
        future=inbound.loc[inbound.Expected_Arrival_Date>date]
        overdue=int(inbound.loc[inbound.Expected_Arrival_Date<=date,'Incoming_Qty'].sum())
        eligible=int(future.loc[future.Expected_Arrival_Date<=end,'Incoming_Qty'].sum())
        later=int(future.loc[future.Expected_Arrival_Date>end,'Incoming_Qty'].sum())
        cover_demand=daily*coverage
        need=max(0.,cover_demand+int(r.Safety_Stock_Qty)-int(s.Usable_On_Hand_Qty)-eligible)
        order=0 if need<=1e-10 else int(math.ceil(max(need,int(r.Minimum_Order_Qty))/int(r.Order_Multiple_Qty))*int(r.Order_Multiple_Qty))
        balance=float(s.Usable_On_Hand_Qty)
        before_shortage=0.; nextweek_shortage=0.; first_shortage=''
        for day in range(1,max(coverage,7)+1):
            dt=date+pd.Timedelta(days=day)
            balance+=float(future.loc[future.Expected_Arrival_Date.eq(dt),'Incoming_Qty'].sum())
            if day==max(1,lead):
                balance+=order
            balance-=daily
            if day < lead:
                before_shortage=max(before_shortage,-balance)
            if day<=7:
                nextweek_shortage=max(nextweek_shortage,-balance)
            if balance < -1e-10 and not first_shortage:
                first_shortage=dt.date().isoformat()
        flags=[]
        if before_shortage>1e-10: flags.append('REVIEW_EARLIER_SUPPLY')
        if overdue: flags.append('CONFIRM_OVERDUE_DELIVERY')
        if later: flags.append('DELIVERIES_AFTER_COVERAGE')
        if lead>7 and order: flags.append('NEW_ORDER_AFTER_NEXT_WEEK')
        if cover_demand<1: flags.append('SPARSE_SALES_REVIEW')
        rows.append(dict(Product_ID=key[0],Product_Name=names.get(key[0],''),Store_ID=key[1],OrderQty=order,Quantity_Unit='product_unit',
                         Forecast_Next_Week_Qty=round(float(forecast[i]),4),Coverage_Days=coverage,Forecast_Coverage_Qty=round(cover_demand,4),
                         Usable_On_Hand_Qty=int(s.Usable_On_Hand_Qty),Incoming_Within_Coverage_Qty=eligible,Incoming_After_Coverage_Qty=later,
                         Overdue_Incoming_Qty=overdue,Safety_Stock_Qty=int(r.Safety_Stock_Qty),Order_Multiple_Qty=int(r.Order_Multiple_Qty),Minimum_Order_Qty=int(r.Minimum_Order_Qty),
                         Expected_New_Order_Date=arrival.date().isoformat(),Coverage_End_Date=end.date().isoformat(),
                         PreArrivalShortageQty=int(math.ceil(max(0.,before_shortage)-1e-10)) if before_shortage>1e-10 else 0,
                         NextWeekShortageQty=int(math.ceil(max(0.,nextweek_shortage)-1e-10)) if nextweek_shortage>1e-10 else 0,
                         First_Projected_Shortage_Date=first_shortage,Review_Flags=';'.join(flags)))
    result=pd.DataFrame(rows)
    require(result.OrderQty.ge(0).all() and result.OrderQty.mod(1).eq(0).all(),'Invalid result quantities')
    return result,dict(method=SELECTED_METHOD,source_preparation_seconds=prepare_seconds,forecast=timing,exact_sales_duplicates_removed=duplicates,calculation_seconds=time.perf_counter()-t0)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for argument in ['sales-path','stock-path','deliveries-path','policy-path','planning-date','output-path']:
        parser.add_argument('--'+argument,required=True)
    args=parser.parse_args()
    sources=[Path(x).resolve() for x in [args.sales_path,args.stock_path,args.deliveries_path,args.policy_path]]
    destination=Path(args.output_path).resolve()
    require(destination not in sources,'Output must not overwrite an input')
    require(not destination.exists(),'Output exists; choose a fresh output path')
    require(destination.parent.is_dir(),'Output directory does not exist')
    result,metrics=calculate(args.sales_path,args.stock_path,args.deliveries_path,args.policy_path,args.planning_date)
    with destination.open('x',newline='') as handle:
        result.to_csv(handle,index=False,lineterminator='\n')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':
    try:
        main()
    except (ValueError,KeyError,FileNotFoundError) as error:
        raise SystemExit('Input error: '+str(error))
