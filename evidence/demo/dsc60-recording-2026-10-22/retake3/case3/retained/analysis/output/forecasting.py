"""Bounded CPU-only forecasts of recorded gross units. No network/model APIs."""
import time
import numpy as np
import pandas as pd

KEYS=['Product_ID','Store_ID']
SALES_COLS=['Transaction_ID','Order_Date','Product_ID','Store_ID','Product_Name','Quantity','Order_Status','Return_Flag']

def load_sales(path, planning_date, treatment='fulfilled'):
    d=pd.read_csv(path,usecols=SALES_COLS)
    # Only exact duplicates in these selected columns may hide distinct full records:
    # verify duplicate transaction identifiers against full source rows when present.
    if d.Transaction_ID.duplicated().any():
        full=pd.read_csv(path)
        full=full.drop_duplicates()
        if full.Transaction_ID.duplicated().any():
            raise ValueError('Conflicting transaction IDs')
        d=full[SALES_COLS].copy()
    if d[['Transaction_ID','Order_Date']+KEYS+['Quantity','Order_Status','Return_Flag']].isna().any().any():
        raise ValueError('Missing required sales values')
    d['date']=pd.to_datetime(d.Order_Date,format='%Y-%m-%d',errors='raise')
    if (d.date>planning_date).any():
        raise ValueError('Sales contains dates after planning date; provide an as-of extract')
    d.Quantity=pd.to_numeric(d.Quantity,errors='raise')
    if not np.isfinite(d.Quantity).all() or (d.Quantity%1!=0).any():
        raise ValueError('Sales units must be finite integers')
    d['status']=d.Order_Status.str.strip().str.lower()
    if not d.status.isin(['completed','shipped','returned','cancelled','processing']).all():
        raise ValueError('Unknown sales status')
    if not d.Return_Flag.str.strip().str.lower().isin(['yes','no']).all():
        raise ValueError('Unknown return flag')
    pairs=d.groupby(KEYS).date.min().sort_index()
    names=d.dropna(subset=['Product_Name']).groupby('Product_ID').Product_Name.agg(lambda x: x.iloc[0] if x.nunique()==1 else '')
    statuses={'fulfilled':['completed','shipped','returned'],'shipped_only':['completed','shipped'],'noncancelled':['completed','shipped','returned','processing']}[treatment]
    target=d[(d.Quantity>0)&d.status.isin(statuses)].copy()
    return d,target,pairs,names

def weekly_panel(target, first, origin):
    # Full observed calendar weeks only, after pair's first transaction.
    end=origin-pd.Timedelta(days=(origin.weekday()+1)%7)
    starts=first+pd.to_timedelta((7-first.dt.weekday)%7,unit='D')
    pieces=[]
    for (product,store),start in starts.items():
        ends=pd.date_range(start+pd.Timedelta(days=6),end,freq='7D')
        pieces.append(pd.DataFrame({'Product_ID':product,'Store_ID':store,'week_end':ends}))
    panel=pd.concat(pieces,ignore_index=True)
    t=target[target.date<=end].copy()
    t['week_end']=t.date+pd.to_timedelta(6-t.date.dt.weekday,unit='D')
    totals=t.groupby(KEYS+['week_end']).Quantity.sum().rename('units')
    panel=panel.join(totals,on=KEYS+['week_end'])
    panel['units']=panel.units.fillna(0.)
    return panel.sort_values(KEYS+['week_end']).reset_index(drop=True)

def design(frame, products, stores):
    day=(pd.to_datetime(frame.week_end)-pd.Timestamp('2022-01-01')).dt.days.to_numpy()/365.25
    return np.column_stack([(frame.Product_ID.to_numpy()[:,None]==np.array(products)[None,:]).astype(float),
                            (frame.Store_ID.to_numpy()[:,None]==np.array(stores)[None,:]).astype(float),
                            np.sin(2*np.pi*day),np.cos(2*np.pi*day),day])

def forecast(panel, pairs, origin, method, max_days=14):
    begin=time.perf_counter()
    groups=panel.groupby(KEYS,sort=True)
    if method.startswith('recent_'):
        n=int(method.split('_')[1]); vals=groups.tail(n).groupby(KEYS).units.mean().reindex(pairs).to_numpy()
        fitted=time.perf_counter(); result=np.repeat((vals/7)[:,None],max_days,axis=1)
    elif method=='croston_sba':
        vals=[]
        for key in pairs:
            y=groups.get_group(key).units.to_numpy(); nz=np.flatnonzero(y>0)
            if not len(nz): vals.append(0.);continue
            z=y[nz[0]]; interval=float(nz[0]+1);last=nz[0]
            for idx in nz[1:]:
                z=.1*y[idx]+.9*z;interval=.1*(idx-last)+.9*interval;last=idx
            vals.append(.95*z/interval)
        fitted=time.perf_counter();result=np.repeat((np.array(vals)/7)[:,None],max_days,axis=1)
    elif method=='pooled_poisson':
        from sklearn.linear_model import PoissonRegressor
        products=sorted(panel.Product_ID.unique());stores=sorted(panel.Store_ID.unique())
        x=design(panel,products,stores)
        model=PoissonRegressor(alpha=.1,max_iter=300,tol=1e-7).fit(x,panel.units.to_numpy())
        fitted=time.perf_counter()
        future=[]
        for k in range(1,max_days+1):
            date=origin+pd.Timedelta(days=k)
            # Evaluate same weekly midpoint convention in each future week.
            week_end=date+pd.Timedelta(days=6-date.weekday())
            f=pd.DataFrame(list(pairs),columns=KEYS);f['week_end']=week_end
            future.append(model.predict(design(f,products,stores))/7)
        result=np.column_stack(future)
    else: raise ValueError('Unsupported method')
    return np.maximum(result,0),{'fit_seconds':fitted-begin,'inference_seconds':time.perf_counter()-fitted,'training_rows':len(panel)}

def actual(target,pairs,origin,horizon):
    a=target[(target.date>origin)&(target.date<=origin+pd.Timedelta(days=horizon))].groupby(KEYS).Quantity.sum()
    return a.reindex(pairs,fill_value=0).to_numpy(dtype=float)
