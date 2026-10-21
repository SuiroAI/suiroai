#!/usr/bin/env python3
"""Weekly, local, non-LLM restocking. See routine_usage.md. No network operations."""
import os
for _v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[_v]='1'
import argparse, json, math, time, resource, sys
from pathlib import Path
import numpy as np
import pandas as pd

KEY=['Product_ID','Store_ID']
SELECTED='pooled_13week'  # Frozen after evaluation; see selected_method.json.

def require(ok, message):
    if not ok: raise ValueError(message)

def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)

def read_csv(path, columns):
    d=pd.read_csv(path)
    require(set(columns)<=set(d),f'{path}: missing columns {set(columns)-set(d)}')
    require(not d[columns].isna().any().any(),f'{path}: null required values')
    return d

def numeric(d,cols,positive=()):
    for c in cols:
        d[c]=pd.to_numeric(d[c],errors='raise')
        require(bool(np.isfinite(d[c]).all() and (d[c]>=0).all() and (d[c]%1==0).all()),f'Invalid nonnegative integer {c}')
        if c in positive: require(bool((d[c]>0).all()),f'{c} must be positive')

def dates(d,cols):
    for c in cols:
        d[c]=pd.to_datetime(d[c],format='%Y-%m-%d',errors='raise')

def prepare_sales(path,origin,keys=None,target='fulfilled'):
    cols=KEY+['Transaction_ID','Order_Date','Quantity','Order_Status','Return_Flag']
    s=read_csv(path,cols).drop_duplicates()
    require(not s.Transaction_ID.duplicated().any(),'Conflicting transaction identifiers')
    dates(s,['Order_Date'])
    require(s.Order_Date.max()<=origin,'Sales contain dates after planning date')
    require(s.Order_Date.max()==origin,'Sales must extend through planning date')
    s['Quantity']=pd.to_numeric(s.Quantity,errors='raise')
    require(bool(np.isfinite(s.Quantity).all() and (s.Quantity%1==0).all()),'Invalid sales quantity')
    s['status']=s.Order_Status.str.strip().str.lower()
    require(set(s.status)<=set(['completed','shipped','returned','cancelled','processing']),'Unknown order status')
    require(set(s.Return_Flag.str.strip().str.lower())<=set(['yes','no']),'Unknown return flag')
    calendar=pd.date_range(s.Order_Date.min(),origin)
    require(len(calendar.difference(s.Order_Date))==0,'Globally missing sales dates: incomplete observation calendar')
    if keys is None: keys=pd.MultiIndex.from_frame(s[KEY].drop_duplicates().sort_values(KEY))
    require(set(map(tuple,s[KEY].values))==set(keys),'Sales and operational populations differ')
    first=s.groupby(KEY).Order_Date.min().reindex(keys)
    mask=s.status.isin(['completed','shipped','returned'])
    if target=='noncancelled': mask=s.status!='cancelled'
    if target=='nonreturned': mask=s.status.isin(['completed','shipped']) & s.Return_Flag.str.lower().eq('no')
    good=s.loc[mask & (s.Quantity>0)]
    day=good.groupby(['Order_Date']+KEY).Quantity.sum().unstack(KEY).reindex(index=calendar,columns=keys).fillna(0.).astype(float)
    day=day.mask(day.index.values[:,None]<first.values[None,:])
    names=s.dropna(subset=['Product_Name']) if 'Product_Name' in s else pd.DataFrame()
    name_map={}
    if len(names):
        for k,g in names.groupby('Product_ID'):
            vals=g.Product_Name.dropna().unique()
            if len(vals)==1: name_map[k]=vals[0]
    return day,s,name_map

def forecast(day,origin,method,horizon=14):
    """Fit at origin; return future daily recorded-unit means, fit/inference timings."""
    t=time.perf_counter(); hist=day.loc[:origin]; n=hist.shape[1]
    if method in ('recent_8week','pooled_13week'):
        window=56 if method=='recent_8week' else 91
        require(bool(hist.tail(window).notna().all().all() and len(hist)>=window),'Insufficient observed history')
        rate=hist.tail(window).mean().values
        if method=='pooled_13week':
            pooled=pd.Series(rate,index=hist.columns).groupby(level=0).transform('mean').values
            rate=(91*rate+28*pooled)/119
        fit=time.perf_counter()-t; t=time.perf_counter()
        pred=np.tile(rate,(horizon,1)); infer=time.perf_counter()-t
        return pred,{'fit_seconds':fit,'inference_seconds':infer,'retained_rate_bytes':int(rate.nbytes)}
    require(method=='poisson_calendar','Unknown method')
    from scipy import sparse
    from sklearn.linear_model import PoissonRegressor
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    wk=hist.resample('W-SUN').sum(min_count=7)
    wk=wk.loc[wk.index<=origin]
    lag4=wk.shift(1).rolling(4,min_periods=4).mean()
    lag13=wk.shift(1).rolling(13,min_periods=13).mean()
    last=wk.tail(104).index; y=wk.loc[last].to_numpy(); a=lag4.loc[last].to_numpy(); b=lag13.loc[last].to_numpy()
    valid=np.isfinite(y)&np.isfinite(a)&np.isfinite(b)
    rows,pairs=np.where(valid)
    require(len(rows)>n*13,'Insufficient model history')
    def design(pair_idx,dt,x4,x13):
        dt=pd.DatetimeIndex(dt); m=dt.month.to_numpy()-1
        # Weekly totals, sparse pair and calendar effects; bounded univariate trend.
        z=np.column_stack([np.log1p(x4),np.log1p(x13),(dt-pd.Timestamp('2022-01-01')).days.to_numpy()/365.25])
        r=np.arange(len(pair_idx))
        return sparse.hstack([sparse.csr_matrix((np.ones(len(r)),(r,pair_idx)),shape=(len(r),n)),sparse.csr_matrix((np.ones(len(r)),(r,m)),shape=(len(r),12)),sparse.csr_matrix(z)],format='csr')
    x=design(pairs,last[rows]-pd.Timedelta(days=3),a[valid],b[valid])
    model=PoissonRegressor(alpha=.1,max_iter=200,tol=1e-6)
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always',ConvergenceWarning); model.fit(x,y[valid])
    converged=not any(issubclass(w.category,ConvergenceWarning) for w in ws)
    fit=time.perf_counter()-t; t=time.perf_counter()
    future=pd.date_range(origin+pd.Timedelta(days=1),periods=horizon)
    xnew=design(np.tile(np.arange(n),horizon),future.repeat(n),np.tile(wk.tail(4).mean().values,horizon),np.tile(wk.tail(13).mean().values,horizon))
    pred=model.predict(xnew).reshape(horizon,n)/7
    return pred,{'fit_seconds':fit,'inference_seconds':time.perf_counter()-t,'converged':converged,'iterations':int(model.n_iter_),'training_rows':len(rows),'features':x.shape[1],'sparse_training_bytes':int(x.data.nbytes+x.indices.nbytes+x.indptr.nbytes),'prepared_daily_bytes':int(day.memory_usage(index=True).sum()),'coefficient_bytes':int(model.coef_.nbytes)}

def operations(stock_path,deliveries_path,policy_path,origin):
    pc=KEY+['Effective_Date','Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty','Quantity_Unit']
    sc=KEY+['Snapshot_Date','Usable_On_Hand_Qty','On_Order_Qty','Open_Order_Ledger_Complete','Quantity_Unit']
    dc=KEY+['PO_Line_ID','Order_Date','Expected_Arrival_Date','Incoming_Qty','Quantity_Unit']
    p=read_csv(policy_path,pc); s=read_csv(stock_path,sc); d=read_csv(deliveries_path,dc)
    dates(p,['Effective_Date']); dates(s,['Snapshot_Date']); dates(d,['Order_Date','Expected_Arrival_Date'])
    numeric(p,pc[3:-1],['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty'])
    numeric(s,['Usable_On_Hand_Qty','On_Order_Qty']); numeric(d,['Incoming_Qty'])
    require(not s.duplicated(KEY).any(),'Duplicate stock keys')
    require(not p.duplicated(KEY+['Effective_Date']).any(),'Duplicate policy versions')
    p=p.loc[p.Effective_Date<=origin].sort_values('Effective_Date').drop_duplicates(KEY,keep='last').sort_values(KEY).set_index(KEY)
    s=s.set_index(KEY).sort_index()
    require(p.index.equals(s.index),'Policy and stock keys differ')
    require((s.Snapshot_Date==origin).all(),'Stock snapshot must match planning date')
    require(s.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(),'Incomplete open order ledger')
    require(not d.PO_Line_ID.duplicated().any(),'Duplicate purchase-order lines')
    require(set(map(tuple,d[KEY].values))<=set(p.index),'Unknown delivery keys')
    require((d.Order_Date<=origin).all(),'Delivery ordered after planning date')
    require((d.Expected_Arrival_Date>=d.Order_Date).all(),'Delivery arrival precedes order')
    require(all(x.Quantity_Unit.eq('product_unit').all() for x in (p,s,d)),'Inconsistent quantity units')
    sums=d.groupby(KEY).Incoming_Qty.sum().reindex(s.index,fill_value=0)
    require((sums==s.On_Order_Qty).all(),'Incoming ledger does not match stock on order')
    return p,s,d

def calculate(p,s,d,pred,names,origin):
    out=[]
    for j,(key,r) in enumerate(p.iterrows()):
        st=s.loc[key]; lead=int(r.Supplier_Lead_Time_Days); h=lead+int(r.Review_Period_Days)
        future=pd.date_range(origin+pd.Timedelta(days=1),periods=h)
        incoming=d.loc[(d.Product_ID==key[0])&(d.Store_ID==key[1])]
        end=future[-1]; timely=incoming.loc[incoming.Expected_Arrival_Date<=end]
        inbound=int(timely.Incoming_Qty.sum()); demand=float(pred[:h,j].sum())
        raw=max(0.,demand+int(r.Safety_Stock_Qty)-int(st.Usable_On_Hand_Qty)-inbound)
        qty=0 if raw<1e-10 else int(math.ceil(max(raw,int(r.Minimum_Order_Qty))/int(r.Order_Multiple_Qty))*int(r.Order_Multiple_Qty))
        # Arrivals at start of due day, demand during day. Overdue entries are credited at next-day start but flagged.
        bal=float(st.Usable_On_Hand_Qty); min_pre=bal; min_all=bal; first=''; overdue=int(incoming.loc[incoming.Expected_Arrival_Date<=origin,'Incoming_Qty'].sum())
        for t,dt in enumerate(future):
            receipts=incoming.loc[incoming.Expected_Arrival_Date==dt,'Incoming_Qty'].sum()
            if t==0: receipts+=overdue
            bal+=receipts
            if t+1==lead: bal+=qty
            bal-=pred[t,j]; min_all=min(min_all,bal)
            if t+1<lead: min_pre=min(min_pre,bal)
            if bal<0 and not first: first=dt.strftime('%Y-%m-%d')
        flags=[]
        if min_pre < -1e-9: flags.append('Review shortage before new order arrives')
        if min_all < -1e-9: flags.append('Projected timing shortage; expedite or transfer')
        if overdue: flags.append('Confirm overdue incoming delivery')
        late=int(incoming.loc[incoming.Expected_Arrival_Date>end,'Incoming_Qty'].sum())
        if late: flags.append('Later incoming excluded from coverage')
        if qty>raw+1e-9: flags.append('Rounded up to ordering rule')
        out.append({'Product_ID':key[0],'Product_Name':names.get(key[0],''),'Store_ID':key[1],'OrderQty':qty,'Quantity_Unit':'product_unit','Forecast_Next_7_Days':round(float(pred[:7,j].sum()),3),'Coverage_Days':h,'Forecast_Coverage_Units':round(demand,3),'Usable_Stock_Units':int(st.Usable_On_Hand_Qty),'Incoming_Within_Coverage_Units':inbound,'Incoming_After_Coverage_Units':late,'Safety_Stock_Units':int(r.Safety_Stock_Qty),'Order_Multiple_Units':int(r.Order_Multiple_Qty),'Minimum_Order_Units':int(r.Minimum_Order_Qty),'Expected_New_Order_Arrival':(origin+pd.Timedelta(days=lead)).strftime('%Y-%m-%d'),'Coverage_End_Date':end.strftime('%Y-%m-%d'),'Projected_Shortage_Before_New_Order_Units':round(max(0.,-min_pre),3),'Projected_Timing_Shortage_Units':round(max(0.,-min_all),3),'First_Projected_Shortage_Date':first,'Review_Flags':'; '.join(flags)})
    return pd.DataFrame(out)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ['sales','stock','deliveries','policy']: ap.add_argument('--'+k+'-path',required=True,type=Path)
    ap.add_argument('--planning-date',required=True)
    ap.add_argument('--output-path',required=True,type=Path)
    args=ap.parse_args(); start=time.perf_counter()
    origin=pd.Timestamp(args.planning_date)
    require(origin.tzinfo is None and origin==origin.normalize(),'Planning date must be a date without timezone/time')
    outpath=args.output_path.resolve()
    require(outpath not in [getattr(args,k+'_path').resolve() for k in ['sales','stock','deliveries','policy']],'Cannot overwrite a source')
    require(not outpath.exists(),'Output already exists; choose a new output path')
    p,s,d=operations(args.stock_path,args.deliveries_path,args.policy_path,origin)
    day,_,names=prepare_sales(args.sales_path,origin,p.index)
    prep=time.perf_counter()-start
    h=int((p.Supplier_Lead_Time_Days+p.Review_Period_Days).max())
    pred,timing=forecast(day,origin,SELECTED,max(7,h))
    result=calculate(p,s,d,pred,names,origin)
    require(result.OrderQty.ge(0).all() and result.OrderQty.mod(1).eq(0).all(),'Invalid output quantity')
    result.to_csv(outpath,index=False,lineterminator='\n')
    print(json.dumps({'selected_method':SELECTED,'rows':len(result),'positive_orders':int(result.OrderQty.gt(0).sum()),'order_units':int(result.OrderQty.sum()),'preparation_seconds':prep,**timing,'total_internal_seconds':time.perf_counter()-start,'peak_process_rss_mb':peak_mb()}))

if __name__=='__main__':
    main()
