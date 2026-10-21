#!/usr/bin/env python3
"""Local weekly product-unit replenishment; no network or language-model calls."""
import argparse
import calendar
import json
import math
from pathlib import Path
import time
import warnings
import numpy as np
import pandas as pd

SELECTED_MODEL = 'shrinkage84'  # frozen by evaluation_plan.json v1, not tuned by the routine
KEYS = ['Product_ID', 'Store_ID']
STATUSES = {'completed', 'shipped', 'returned'}

def clean_sales(path, planning_date):
    required=KEYS+['Transaction_ID','Order_Date','Quantity','Order_Status','Return_Flag','Product_Name']
    s=pd.read_csv(path, usecols=required).drop_duplicates()
    if s[KEYS+['Transaction_ID','Order_Date','Quantity','Order_Status','Return_Flag']].isna().any().any():
        raise ValueError('Missing required sales values')
    # Deduplicate exact source rows before selecting columns: distinct lines cannot be silently merged.
    raw=pd.read_csv(path).drop_duplicates()
    if raw.Transaction_ID.duplicated().any():
        raise ValueError('Conflicting repeated transaction IDs')
    s=raw[required].copy()
    s['date']=pd.to_datetime(s.Order_Date,format='%Y-%m-%d',errors='raise')
    if (s.date>planning_date).any():
        raise ValueError('Sales contain dates after planning date; supply a bounded extract')
    s['Quantity']=pd.to_numeric(s.Quantity,errors='raise')
    if not np.isfinite(s.Quantity).all() or (s.Quantity % 1 != 0).any():
        raise ValueError('Sales quantities must be finite integer product units')
    s['status']=s.Order_Status.str.strip().str.lower()
    if not set(s.status)<=STATUSES|{'cancelled','processing'}:
        raise ValueError('Unrecognized order statuses')
    return s, s[s.status.isin(STATUSES)&s.Quantity.ge(0)].copy()

def totals(s, keys, start, end):
    # Window totals of records, not filled daily demand observations. Absence means no recorded units,
    # conditional on the extract's completeness, never proof of zero latent demand.
    g=s.loc[s.date.between(start,end)].groupby(KEYS).Quantity.sum()
    return g.reindex(pd.MultiIndex.from_frame(keys),fill_value=0).to_numpy(dtype=float)

def calendar_features(dates):
    d=pd.DatetimeIndex(dates)
    phase=2*np.pi*(d.dayofyear.to_numpy()-1)/365.25
    trend=(d-pd.Timestamp('2022-01-03')).days.to_numpy()/365.25
    return np.column_stack([np.sin(phase),np.cos(phase),trend])

def fit_forecast(s, keys, origin, method):
    """Return a predictor producing n_keys x n_future_days arrays and workload evidence."""
    t=time.perf_counter()
    s=s[s.date.le(origin)]
    if method=='previous_month':
        end=origin.replace(day=1)-pd.Timedelta(days=1)
        start=end.replace(day=1)
        if s.date.min()>start:
            raise ValueError('Need complete previous calendar month history')
        rate=totals(s,keys,start,end)/end.day
        predict=lambda dates:np.repeat(rate[:,None],len(dates),axis=1)
        retained=rate.nbytes
    elif method=='shrinkage84':
        start=origin-pd.Timedelta(days=83)
        if s.date.min()>start:
            raise ValueError('Need 84 days of history')
        q=totals(s,keys,start,origin)
        frame=keys.assign(q=q)
        product=frame.groupby('Product_ID').q.transform('sum').to_numpy()
        store=frame.groupby('Store_ID').q.transform('sum').to_numpy()
        pooled=product*store/max(q.sum(),1)/84
        rate=(q+28*pooled)/(84+28)
        predict=lambda dates:np.repeat(rate[:,None],len(dates),axis=1)
        retained=rate.nbytes
    elif method=='poisson_seasonal':
        from scipy import sparse
        from sklearn.linear_model import PoissonRegressor
        from sklearn.preprocessing import OneHotEncoder
        # Only complete weeks. Bounded sparse generalized linear model, no model search.
        start=max(pd.Timestamp('2022-01-03'),s.date.min().normalize())
        start+=pd.Timedelta(days=(-start.weekday())%7)
        end=origin-pd.Timedelta(days=(origin.weekday()-6)%7)
        weeks=pd.date_range(start,end-pd.Timedelta(days=6),freq='7D')
        if len(weeks)<52:
            raise ValueError('Seasonal model requires at least 52 complete weeks')
        tr=s[s.date.between(start,end)].copy()
        tr['week']=tr.date-pd.to_timedelta(tr.date.dt.weekday,unit='D')
        grid=pd.MultiIndex.from_tuples([(p,st,w) for p,st in keys.to_numpy() for w in weeks],names=KEYS+['week'])
        y=tr.groupby(KEYS+['week']).Quantity.sum().reindex(grid,fill_value=0).to_numpy(float)/7
        frame=grid.to_frame(index=False)
        enc=OneHotEncoder(handle_unknown='error',sparse_output=True,dtype=float)
        cats=enc.fit_transform(frame[KEYS])
        X=sparse.hstack([cats,sparse.csr_matrix(calendar_features(frame.week+pd.Timedelta(days=3)))],format='csr')
        model=PoissonRegressor(alpha=.01,max_iter=150,tol=1e-7)
        with warnings.catch_warnings(record=True) as caught:
            model.fit(X,y)
        if caught:
            raise RuntimeError('Poisson fit warning: '+str(caught[0].message))
        def predict(dates):
            f=keys.loc[keys.index.repeat(len(dates))].reset_index(drop=True)
            d=pd.DatetimeIndex(np.tile(pd.DatetimeIndex(dates).to_numpy(),len(keys)))
            z=sparse.hstack([enc.transform(f[KEYS]),sparse.csr_matrix(calendar_features(d))],format='csr')
            return model.predict(z).reshape(len(keys),len(dates))
        # Training matrices released when fit_forecast returns; predictor retains only keys/encoder/model.
        retained=int(model.coef_.nbytes+sum(a.nbytes for a in enc.categories_))
        training_bytes=int(X.data.nbytes+X.indices.nbytes+X.indptr.nbytes+y.nbytes)
    else:
        raise ValueError('Unknown frozen model')
    info={'method':method,'fit_and_preparation_seconds':time.perf_counter()-t,'retained_numeric_bytes':int(retained)}
    if method=='poisson_seasonal':
        info.update(training_rows=len(y),training_features=X.shape[1],training_matrix_and_target_bytes=training_bytes,iterations=int(model.n_iter_))
    return predict,info

def integer_columns(df, names, positive=False):
    for name in names:
        x=pd.to_numeric(df[name],errors='raise')
        if x.isna().any() or not np.isfinite(x).all() or (x%1!=0).any() or (x<(1 if positive else 0)).any():
            raise ValueError('Invalid integer quantity/rule: '+name)
        df[name]=x.astype('int64')

def read_operations(stock_path, deliveries_path, policy_path, date):
    stock=pd.read_csv(stock_path); inbound=pd.read_csv(deliveries_path); policy=pd.read_csv(policy_path)
    for df in [stock,inbound,policy]:
        if df[KEYS+['Quantity_Unit']].isna().any().any() or not df.Quantity_Unit.eq('product_unit').all():
            raise ValueError('All operations require product_unit and nonmissing keys')
    for df in [stock,policy]:
        if df.duplicated(KEYS).any(): raise ValueError('Nonunique operational product/store key')
    if inbound.PO_Line_ID.isna().any() or inbound.PO_Line_ID.duplicated().any():
        raise ValueError('Missing or repeated incoming order line')
    for df,col in [(stock,'Snapshot_Date'),(policy,'Effective_Date'),(inbound,'Order_Date'),(inbound,'Expected_Arrival_Date')]:
        df[col]=pd.to_datetime(df[col],format='%Y-%m-%d',errors='raise')
        if df[col].isna().any(): raise ValueError('Missing operating date')
    if not stock.Snapshot_Date.eq(date).all(): raise ValueError('Stock snapshot must equal planning date')
    if policy.Effective_Date.gt(date).any(): raise ValueError('Policy not yet effective')
    if inbound.Order_Date.gt(date).any() or inbound.Expected_Arrival_Date.le(date).any() or (inbound.Expected_Arrival_Date<inbound.Order_Date).any():
        raise ValueError('Incoming ledger dates must be known orders with future arrivals; resolve overdue lines first')
    if not stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all():
        raise ValueError('A complete dated incoming ledger is required')
    integer_columns(stock,['Usable_On_Hand_Qty','On_Order_Qty'])
    integer_columns(inbound,['Incoming_Qty'])
    integer_columns(policy,['Safety_Stock_Qty','Minimum_Order_Qty'])
    integer_columns(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty'],True)
    ks=lambda d:set(map(tuple,d[KEYS].to_numpy()))
    if ks(stock)!=ks(policy) or not ks(inbound)<=ks(stock): raise ValueError('Operational keys do not match')
    ledger=inbound.groupby(KEYS).Incoming_Qty.sum().reindex(pd.MultiIndex.from_frame(stock[KEYS]),fill_value=0).to_numpy()
    if not np.array_equal(ledger,stock.On_Order_Qty.to_numpy()): raise ValueError('Incoming deliveries do not match stock on-order quantities')
    ops=stock.merge(policy.drop(columns=['Quantity_Unit','Provenance'],errors='ignore'),on=KEYS,validate='one_to_one').sort_values(KEYS).reset_index(drop=True)
    if (ops.Supplier_Lead_Time_Days+ops.Review_Period_Days).max()>366: raise ValueError('Coverage exceeds supported one-year operational horizon')
    return ops,inbound

def calculate(sales_path,stock_path,deliveries_path,policy_path,planning_date):
    t=time.perf_counter()
    calculation_started=t
    origin=pd.Timestamp(planning_date)
    if origin!=origin.normalize() or pd.isna(origin): raise ValueError('Planning date must be a date')
    raw,s=clean_sales(sales_path,origin)
    if raw.date.max()!=origin: raise ValueError('Sales must extend through planning date')
    ops,inbound=read_operations(stock_path,deliveries_path,policy_path,origin)
    keys=ops[KEYS]
    if not set(map(tuple,keys.to_numpy()))<=set(map(tuple,s[KEYS].to_numpy())):
        raise ValueError('Missing sales support for an operational key')
    names=raw.groupby('Product_ID').Product_Name.agg(lambda x:sorted(set(x.dropna())))
    preparation=time.perf_counter()-t
    predictor,info=fit_forecast(s,keys,origin,SELECTED_MODEL)
    horizon=max(7,int((ops.Supplier_Lead_Time_Days+ops.Review_Period_Days).max()))
    dates=pd.date_range(origin+pd.Timedelta(days=1),periods=horizon)
    t=time.perf_counter(); daily=predictor(dates); prediction_time=time.perf_counter()-t
    rows=[]
    for i,r in ops.iterrows():
        lead=int(r.Supplier_Lead_Time_Days); h=lead+int(r.Review_Period_Days)
        receipts=inbound[(inbound.Product_ID==r.Product_ID)&(inbound.Store_ID==r.Store_ID)]
        due=receipts[receipts.Expected_Arrival_Date.le(origin+pd.Timedelta(days=h))]
        incoming=int(due.Incoming_Qty.sum())
        need=float(daily[i,:h].sum()+r.Safety_Stock_Qty-r.Usable_On_Hand_Qty-incoming)
        qty=0 if need<=1e-9 else int(math.ceil(max(need,float(r.Minimum_Order_Qty))/r.Order_Multiple_Qty-1e-12)*r.Order_Multiple_Qty)
        balance=float(r.Usable_On_Hand_Qty); first=''; maximum_gap=0.; minimum_before=float(r.Usable_On_Hand_Qty)
        # Receipts assumed usable at start of due date; new order arrives start of origin+lead.
        for day,d in enumerate(dates[:h],1):
            balance+=float(receipts.loc[receipts.Expected_Arrival_Date.eq(d),'Incoming_Qty'].sum())
            if day==lead: balance+=qty
            balance-=daily[i,day-1]
            if day<lead: minimum_before=min(minimum_before,balance)
            if balance < -1e-9:
                if not first: first=str(d.date())
                maximum_gap=max(maximum_gap,-balance)
        active=raw[raw.Store_ID.eq(r.Store_ID)&raw.date.between(origin-pd.Timedelta(days=27),origin)].date.nunique()
        flags=[]
        if minimum_before < -1e-9: flags.append('SHORTAGE_BEFORE_NEW_ORDER_ARRIVES')
        if first: flags.append('PROJECTED_SHORTAGE_REVIEW_TIMING')
        if len(names.get(r.Product_ID,[]))!=1: flags.append('PRODUCT_NAME_UNRESOLVED')
        rows.append({'Product_ID':r.Product_ID,'Product_Name':names[r.Product_ID][0] if len(names.get(r.Product_ID,[]))==1 else '',
          'Store_ID':r.Store_ID,'OrderQty':qty,'Quantity_Unit':'product_unit',
          'Forecast_Next_7_Days':round(float(daily[i,:7].sum()),3),'Coverage_Days':h,'Forecast_Coverage_Units':round(float(daily[i,:h].sum()),3),
          'Usable_Stock_Units':int(r.Usable_On_Hand_Qty),'Incoming_Within_Coverage_Units':incoming,
          'Incoming_After_Coverage_Units':int(receipts.Incoming_Qty.sum())-incoming,'Safety_Stock_Units':int(r.Safety_Stock_Qty),
          'Order_Multiple_Units':int(r.Order_Multiple_Qty),'Minimum_Order_Units':int(r.Minimum_Order_Qty),
          'New_Order_Arrival_Date':str((origin+pd.Timedelta(days=lead)).date()),'Coverage_End_Date':str((origin+pd.Timedelta(days=h)).date()),
          'First_Projected_Shortage_Date':first,'Projected_Max_Shortage_Units':round(maximum_gap,3),
          'Shortage_Before_New_Order_Units':round(max(0.,-minimum_before),3),'Store_Recorded_Days_Last_28':active,
          'Exception':';'.join(flags)})
    result=pd.DataFrame(rows)
    info.update(input_preparation_seconds=preparation,inference_seconds=prediction_time,forecast_array_bytes=daily.nbytes,
                calculation_seconds=time.perf_counter()-calculation_started)
    return result,info

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['sales','stock','deliveries','policy']:
        parser.add_argument('--'+name+'-path',required=True,type=Path)
    parser.add_argument('--planning-date',required=True)
    parser.add_argument('--output-path',required=True,type=Path)
    args=parser.parse_args()
    try:
        if len(args.planning_date)!=10: raise ValueError('Use YYYY-MM-DD')
        pd.to_datetime(args.planning_date,format='%Y-%m-%d',errors='raise')
        inputs=[args.sales_path,args.stock_path,args.deliveries_path,args.policy_path]
        if args.output_path.resolve() in {p.resolve() for p in inputs}: raise ValueError('Output cannot overwrite an input')
        if args.output_path.exists(): raise ValueError('Output already exists; choose a new output path')
        result,info=calculate(*inputs,args.planning_date)
        result.to_csv(args.output_path,index=False,lineterminator='\n')
        print(json.dumps(info))
    except (ValueError,KeyError,FileNotFoundError) as e:
        parser.exit(2,'Input error: '+str(e)+'\n')

if __name__=='__main__': main()
