"""Local recorded-unit forecasting and weekly replenishment. No network/LLM use."""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd

KEY = ['Product_ID', 'Store_ID']
SELECTED = 'croston_sba'

def load_sales(path, date):
    cols = ['Transaction_ID', 'Product_ID', 'Product_Name', 'Store_ID', 'Order_Date', 'Quantity', 'Order_Status', 'Return_Flag']
    s = pd.read_csv(path, usecols=cols)
    s['Order_Date'] = pd.to_datetime(s.Order_Date, errors='raise')
    if s.Order_Date.isna().any() or s[KEY + ['Transaction_ID', 'Quantity', 'Order_Status']].isna().any().any():
        raise ValueError('Missing sales keys, dates, quantities or statuses')
    if (s.Order_Date > date).any():
        raise ValueError('Sales include dates after planning date; supply an as-of extract')
    s = s.drop_duplicates()
    if s.Transaction_ID.duplicated().any():
        raise ValueError('Conflicting transaction identifiers')
    s['Order_Status'] = s.Order_Status.str.strip().str.lower()
    s['Quantity'] = pd.to_numeric(s.Quantity, errors='raise')
    if not np.isfinite(s.Quantity).all() or (s.Quantity % 1 != 0).any():
        raise ValueError('Quantities must be finite integral product units')
    if not s.Order_Status.isin(['completed','shipped','returned','processing','cancelled']).all():
        raise ValueError('Unrecognized sales status')
    return s

def calendar(s, keys, end, target='gross'):
    start = pd.Timestamp('2024-01-01')
    if end < start + pd.Timedelta(days=84):
        raise ValueError('At least 84 days from 2024-01-01 required')
    dates = pd.date_range(start, end)
    seen = pd.DatetimeIndex(s.loc[s.Order_Date <= end, 'Order_Date'].unique())
    if len(dates.difference(seen)):
        raise ValueError('Globally missing sales dates; exposure unknown')
    first = s.groupby(KEY).Order_Date.min().reindex(keys)
    if first.isna().any() or (first >= start).any():
        raise ValueError('New or unobserved assortment requires separate review')
    mask = s.Order_Status.isin(['completed','shipped','returned']) & (s.Quantity > 0)
    if target == 'retained':
        mask &= (s.Return_Flag.str.lower() != 'yes') & (s.Order_Status != 'returned')
    elif target == 'orders':
        mask = (s.Order_Status != 'cancelled') & (s.Quantity > 0)
    x = s.loc[mask & s.Order_Date.between(start,end)]
    y = x.groupby(['Order_Date'] + KEY).Quantity.sum().unstack(KEY).reindex(index=dates, columns=keys).fillna(0)
    return y

def forecast(y, origin, horizon, method):
    """Return daily forecasts; fit only y <= origin. Timings exclude imports/prep."""
    t = time.perf_counter(); cpu = time.process_time()
    a = y.loc[:origin].to_numpy(dtype=float)
    dates = pd.date_range(origin + pd.Timedelta(days=1), periods=horizon)
    if method.startswith('mean'):
        rate = a[-int(method[4:]):].mean(axis=0)
    elif method == 'croston_sba':
        rate = np.zeros(a.shape[1])
        for j in range(a.shape[1]):
            ix = np.flatnonzero(a[:,j]); z = p = 0.
            if len(ix):
                z = a[ix[0],j]; p = ix[0]+1.
                for k in range(1,len(ix)):
                    z += .1*(a[ix[k],j]-z); p += .1*((ix[k]-ix[k-1])-p)
                rate[j] = .95*z/p
    elif method == 'poisson_seasonal':
        from scipy.sparse import csr_matrix, hstack
        from sklearn.linear_model import PoissonRegressor
        n = a.shape[1]
        train = y.loc[:origin]
        periods = train.index.to_period('M')
        totals = train.groupby(periods).sum()
        exposure = pd.Series(1., index=periods).groupby(level=0).sum().to_numpy()
        months = totals.index.month.to_numpy()-1
        elapsed = ((totals.index.year-2024)*12 + months).to_numpy()/12.
        def design(ms, ts):
            length = len(ms)*n; row=np.arange(length)
            return hstack([csr_matrix((np.ones(length),(row,np.tile(np.arange(n),len(ms)))),shape=(length,n)), csr_matrix((np.ones(length),(row,np.repeat(ms,n))),shape=(length,12)),csr_matrix(np.repeat(ts,n)[:,None])],format='csr')
        X = design(months,elapsed)
        m = PoissonRegressor(alpha=.01,max_iter=300,tol=1e-7)
        m.fit(X,(totals.to_numpy()/exposure[:,None]).ravel(),sample_weight=np.repeat(exposure,n))
        fit_wall = time.perf_counter()-t; fit_cpu=time.process_time()-cpu
        t2=time.perf_counter(); c2=time.process_time()
        ms=dates.month.to_numpy()-1; ts=((dates.year-2024)*12+ms).to_numpy()/12.
        pred=m.predict(design(ms,ts)).reshape(horizon,n)
        return pred, {'fit_wall_seconds':fit_wall,'fit_cpu_seconds':fit_cpu,'inference_wall_seconds':time.perf_counter()-t2,'inference_cpu_seconds':time.process_time()-c2,'training_matrix_rows':X.shape[0],'training_matrix_columns':X.shape[1],'sparse_design_bytes':X.data.nbytes+X.indices.nbytes+X.indptr.nbytes,'retained_coefficients_bytes':m.coef_.nbytes,'daily_array_bytes':a.nbytes}
    else:
        raise ValueError('Unknown selected forecasting method')
    fit_wall=time.perf_counter()-t; fit_cpu=time.process_time()-cpu
    t2=time.perf_counter(); c2=time.process_time(); pred=np.tile(rate,(horizon,1))
    return pred, {'fit_wall_seconds':fit_wall,'fit_cpu_seconds':fit_cpu,'inference_wall_seconds':time.perf_counter()-t2,'inference_cpu_seconds':time.process_time()-c2,'daily_array_bytes':a.nbytes}

def load_operations(stock_path, deliveries_path, policy_path, date):
    stock=pd.read_csv(stock_path); inbound=pd.read_csv(deliveries_path); policy=pd.read_csv(policy_path)
    for d in [stock,inbound,policy]:
        if d.isna().any().any() or not (d.Quantity_Unit == 'product_unit').all():
            raise ValueError('Missing operational data or incompatible units')
    for d,c in [(stock,'Snapshot_Date'),(policy,'Effective_Date'),(inbound,'Order_Date'),(inbound,'Expected_Arrival_Date')]:
        d[c]=pd.to_datetime(d[c],errors='raise')
    if not (stock.Snapshot_Date == date).all() or (policy.Effective_Date > date).any():
        raise ValueError('Need planning-date stock and policy effective by that date')
    if (inbound.Order_Date > date).any() or (inbound.Expected_Arrival_Date < inbound.Order_Date).any():
        raise ValueError('Invalid inbound dates')
    for d in [stock,policy]:
        if d.duplicated(KEY).any(): raise ValueError('Duplicate operational keys')
    if inbound.PO_Line_ID.duplicated().any(): raise ValueError('Duplicate delivery lines')
    for d,cs in [(stock,['Usable_On_Hand_Qty','On_Order_Qty']),(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']),(inbound,['Incoming_Qty'])]:
        for c in cs:
            v=pd.to_numeric(d[c],errors='raise')
            if not np.isfinite(v).all() or (v < 0).any() or (v % 1 != 0).any(): raise ValueError('Invalid operational quantity')
            d[c]=v.astype(int)
    if (policy[['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty']] <= 0).any().any(): raise ValueError('Lead, review, multiple must be positive')
    st=stock.set_index(KEY).sort_index(); pol=policy.set_index(KEY).sort_index()
    if not st.index.equals(pol.index): raise ValueError('Stock/policy population mismatch')
    if not pd.MultiIndex.from_frame(inbound[KEY]).isin(st.index).all(): raise ValueError('Unknown inbound keys')
    if not st.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(): raise ValueError('Incomplete delivery ledger')
    ledger=inbound.groupby(KEY).Incoming_Qty.sum().reindex(st.index,fill_value=0)
    if not ledger.equals(st.On_Order_Qty): raise ValueError('Incoming deliveries disagree with on-order stock')
    return st, inbound, pol

def make_orders(s, stock, inbound, policy, date, method):
    y=calendar(s,stock.index,date)
    horizons=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy()
    pred,timing=forecast(y,date,int(horizons.max()),method)
    out=[]
    for j,key in enumerate(stock.index):
        p=policy.loc[key]; st=stock.loc[key]; h=int(horizons[j]); lead=int(p.Supplier_Lead_Time_Days)
        ins=inbound[(inbound.Product_ID==key[0]) & (inbound.Store_ID==key[1])]
        horizon_date=date+pd.Timedelta(days=h); arrival=date+pd.Timedelta(days=lead)
        overdue=ins.loc[ins.Expected_Arrival_Date <= date,'Incoming_Qty'].sum()
        timely=ins.loc[ins.Expected_Arrival_Date.between(date+pd.Timedelta(days=1),horizon_date),'Incoming_Qty'].sum()
        late=ins.loc[ins.Expected_Arrival_Date > horizon_date,'Incoming_Qty'].sum()
        need=max(0.,pred[:h,j].sum()+p.Safety_Stock_Qty-st.Usable_On_Hand_Qty-timely)
        qty=0 if need <= 1e-9 else int(math.ceil(max(need,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty)
        balance=float(st.Usable_On_Hand_Qty); worst_before=0.; first=''; worst_any=0.
        for day in range(1,h+1):
            when=date+pd.Timedelta(days=day)
            balance+=float(ins.loc[ins.Expected_Arrival_Date==when,'Incoming_Qty'].sum())
            if day==lead: balance+=qty
            balance-=pred[day-1,j]
            if balance < -1e-9 and not first: first=when.strftime('%Y-%m-%d')
            worst_any=max(worst_any,-balance)
            if day < lead: worst_before=max(worst_before,-balance)
        names=s.loc[s.Product_ID==key[0],'Product_Name'].dropna().unique()
        flags=[]
        if worst_before>1e-9: flags.append('Shortage before new order arrives')
        if worst_any>1e-9 and worst_before<=1e-9: flags.append('Timing shortage within coverage')
        if overdue: flags.append('Overdue delivery excluded; check arrival')
        if late: flags.append('Delivery beyond coverage excluded')
        if y.iloc[-84:,j].sum()==0: flags.append('No fulfilled units in last 84 days; review assortment')
        out.append(dict(Product_ID=key[0],Product_Name=names[0] if len(names)==1 else '',Store_ID=key[1],OrderQty=qty,Quantity_Unit='product_unit',Forecast_Next_7_Days=round(pred[:7,j].sum(),3),Coverage_Days=h,Forecast_Coverage_Units=round(pred[:h,j].sum(),3),Safety_Stock_Qty=int(p.Safety_Stock_Qty),Usable_On_Hand_Qty=int(st.Usable_On_Hand_Qty),Incoming_Within_Coverage_Qty=int(timely),Incoming_After_Coverage_Qty=int(late),Overdue_Incoming_Qty=int(overdue),Expected_New_Order_Arrival=arrival.strftime('%Y-%m-%d'),Coverage_End=horizon_date.strftime('%Y-%m-%d'),Expected_Shortage_Before_Arrival_Units=round(worst_before,3),Expected_Max_Timing_Shortage_Units=round(worst_any,3),First_Expected_Shortage_Date=first,Review_Flag='; '.join(flags)))
    return pd.DataFrame(out),timing

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for arg in ['sales','stock','deliveries','policy']: ap.add_argument('--'+arg+'-path',required=True)
    ap.add_argument('--planning-date',required=True); ap.add_argument('--output-path',required=True)
    args=ap.parse_args()
    date=pd.to_datetime(args.planning_date,format='%Y-%m-%d',errors='raise')
    paths=[Path(getattr(args,k+'_path')).resolve() for k in ['sales','stock','deliveries','policy']]
    dest=Path(args.output_path).resolve()
    if dest in paths: raise ValueError('Output must not overwrite an input')
    if SELECTED=='PENDING': raise ValueError('Selection has not been frozen')
    s=load_sales(paths[0],date); stock,inbound,policy=load_operations(*paths[1:],date)
    out,timing=make_orders(s,stock,inbound,policy,date,SELECTED)
    out.to_csv(dest,index=False)
    print(json.dumps({'method':SELECTED,'rows':len(out),'total_order_units':int(out.OrderQty.sum()),'timing':timing}))

if __name__=='__main__': main()
