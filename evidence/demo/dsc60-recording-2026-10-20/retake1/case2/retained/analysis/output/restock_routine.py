"""Weekly recorded-unit forecast and supplied-policy orders. No network or model APIs."""
import argparse
import math
from pathlib import Path
import numpy as np
import pandas as pd

KEY = ['Product_ID', 'Store_ID']
SELECTED = 'pooled90'

def read_sales(path, cutoff):
    s = pd.read_csv(path)
    required = KEY + ['Transaction_ID', 'Order_Date', 'Order_Status', 'Return_Flag', 'Quantity', 'Product_Name']
    if not set(required).issubset(s.columns):
        raise ValueError('Missing required sales columns')
    s = s.drop_duplicates().copy()
    if s.Transaction_ID.duplicated().any():
        raise ValueError('Conflicting duplicate transaction identifiers')
    s['Order_Date'] = pd.to_datetime(s.Order_Date, errors='raise').dt.normalize()
    if s.Order_Date.max() > cutoff:
        raise ValueError('Sales include dates after planning date; supply an as-of extract')
    if s[KEY + ['Quantity', 'Order_Status', 'Return_Flag']].isna().any().any():
        raise ValueError('Missing sales keys, quantities or statuses')
    s['Quantity'] = pd.to_numeric(s.Quantity, errors='raise')
    if not np.isfinite(s.Quantity).all() or (s.Quantity % 1 != 0).any():
        raise ValueError('Sales quantities must be finite integers')
    s['status'] = s.Order_Status.str.strip().str.lower()
    s['returned'] = s.Return_Flag.str.strip().str.lower().eq('yes')
    if not s.status.isin(['completed','shipped','processing','returned','cancelled']).all():
        raise ValueError('Unrecognized order status')
    if not s.Return_Flag.str.strip().str.lower().isin(['yes','no']).all():
        raise ValueError('Unrecognized return flag')
    return s

def panel(s, keys, cutoff, treatment='gross'):
    valid = s.status.isin(['completed','shipped']) & s.Quantity.gt(0)
    if treatment == 'no_returns': valid &= ~s.returned
    if treatment == 'processing': valid |= s.status.eq('processing') & s.Quantity.gt(0)
    dates = pd.date_range(s.Order_Date.min(), cutoff)
    grouped = s.loc[valid].groupby(['Order_Date'] + KEY).Quantity.sum().unstack(KEY)
    y = grouped.reindex(index=dates, columns=keys, fill_value=0).fillna(0).to_numpy(float)
    first = s.groupby(KEY).Order_Date.min().reindex(keys)
    return dates, y, first

def features(y, idx):
    cs = np.vstack([np.zeros((1,y.shape[1])), np.cumsum(y,axis=0)])
    a = []
    for window in (7,28,91,364): a.append((cs[idx+1]-cs[idx+1-window])*7/window)
    a.append(cs[idx+1-357]-cs[idx+1-364])
    return a

def feature_matrix(y, dates, indices):
    n = y.shape[1]
    f = features(y, np.asarray(indices))
    phase = np.asarray([2*np.pi*dates[i].dayofyear/365.25 for i in indices])[:,None]
    sn = np.broadcast_to(np.sin(phase), (len(indices),n))
    co = np.broadcast_to(np.cos(phase), (len(indices),n))
    return np.stack([np.ones_like(f[0]), *f, sn, co, sn*f[3], co*f[3]],axis=-1)

def rates(method, dates, y, first, origin, keys):
    ix = dates.get_indexer([origin])[0]
    if ix < 0 or ix < 364: raise ValueError('At least one year of recorded history required')
    if method == 'recent_month':
        end = origin if origin.is_month_end else origin.replace(day=1)-pd.Timedelta(days=1)
        start = end.replace(day=1)
        return y[(dates>=start)&(dates<=end)].sum(axis=0)/end.day
    if method in ('recent90','pooled90'):
        local = y[ix-89:ix+1].sum(axis=0)/90
        if method == 'recent90': return local
        tab = pd.Series(local,index=keys)
        total = tab.sum()
        pooled = np.array([tab.xs(p,level=0).sum()*tab.xs(st,level=1).sum()/total if total else 0 for p,st in keys])
        return .5*local+.5*pooled
    if method != 'ridge': raise ValueError('Unknown selected method')
    indices = np.array([i for i in range(364,ix-6) if dates[i].dayofweek==6 and dates[i]>=origin-pd.Timedelta(days=730)])
    x = feature_matrix(y,dates,indices)
    cs = np.vstack([np.zeros((1,y.shape[1])), np.cumsum(y,axis=0)])
    target = cs[indices+8]-cs[indices+1]
    available = dates[indices].values[:,None] >= (first.values[None,:]+np.timedelta64(364,'D'))
    x = x[available]; target=target[available]
    if len(target)<100: raise ValueError('Insufficient ridge training observations')
    mu=x.mean(axis=0); sd=x.std(axis=0); mu[0]=0; sd[sd<1e-10]=1
    z=(x-mu)/sd
    penalty=np.eye(z.shape[1])*10; penalty[0,0]=0
    beta=np.linalg.solve(z.T@z+penalty,z.T@target)
    xp=(feature_matrix(y,dates,[ix])[0]-mu)/sd
    return np.maximum(0,xp@beta)/7

def read_operations(stock_path, deliveries_path, policy_path, origin):
    stock=pd.read_csv(stock_path); inbound=pd.read_csv(deliveries_path); policy=pd.read_csv(policy_path)
    for df in (stock,inbound,policy):
        if df.isna().any().any(): raise ValueError('Missing operating input values')
        if not df.Quantity_Unit.eq('product_unit').all(): raise ValueError('Unsupported quantity units')
    for df in (stock,policy):
        if df.duplicated(KEY).any(): raise ValueError('Duplicate operating keys')
    if inbound.PO_Line_ID.duplicated().any(): raise ValueError('Duplicate purchase-order lines')
    for df, cols in [(stock,['Snapshot_Date']), (inbound,['Order_Date','Expected_Arrival_Date']), (policy,['Effective_Date'])]:
        for col in cols: df[col]=pd.to_datetime(df[col], errors='raise').dt.normalize()
    if not stock.Snapshot_Date.eq(origin).all(): raise ValueError('Stock snapshot must match planning date')
    if policy.Effective_Date.gt(origin).any() or inbound.Order_Date.gt(origin).any(): raise ValueError('Future policy/order unavailable at planning date')
    if (inbound.Expected_Arrival_Date<inbound.Order_Date).any(): raise ValueError('Arrival precedes purchase order')
    if not stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(): raise ValueError('Complete inbound ledger required')
    quantities=[(stock,['Usable_On_Hand_Qty','On_Order_Qty']),(inbound,['Incoming_Qty']),(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty'])]
    for df,cols in quantities:
        for c in cols:
            v=pd.to_numeric(df[c],errors='raise')
            if not np.isfinite(v).all() or (v<0).any() or (v%1!=0).any(): raise ValueError('Invalid operating quantity')
            df[c]=v.astype(int)
    if policy.Order_Multiple_Qty.eq(0).any() or policy.Review_Period_Days.eq(0).any(): raise ValueError('Positive multiple/review period required')
    keys=pd.MultiIndex.from_frame(policy[KEY]).sort_values()
    if set(map(tuple,stock[KEY].values))!=set(keys) or not set(map(tuple,inbound[KEY].values)).issubset(set(keys)): raise ValueError('Operating keys do not match')
    ledger=inbound.groupby(KEY).Incoming_Qty.sum().reindex(keys,fill_value=0)
    if not np.array_equal(stock.set_index(KEY).reindex(keys).On_Order_Qty.values,ledger.values): raise ValueError('Incoming ledger does not match stock on-order total')
    return stock,inbound,policy,keys

def order_rows(rate, keys, stock, inbound, policy, origin, names):
    st=stock.set_index(KEY); pol=policy.set_index(KEY); rows=[]
    for j,(p,store) in enumerate(keys):
        rule=pol.loc[(p,store)]; inventory=st.loc[(p,store)]
        lead=int(rule.Supplier_Lead_Time_Days); horizon=lead+int(rule.Review_Period_Days)
        receipts=inbound[(inbound.Product_ID==p)&(inbound.Store_ID==store)]
        due=(receipts.Expected_Arrival_Date-origin).dt.days
        timely=int(receipts.loc[(due>0)&(due<=horizon),'Incoming_Qty'].sum())
        overdue=int(receipts.loc[due<=0,'Incoming_Qty'].sum())
        need=max(0, rate[j]*horizon+rule.Safety_Stock_Qty-inventory.Usable_On_Hand_Qty-timely)
        qty=0 if need<=1e-10 else int(math.ceil(max(need,rule.Minimum_Order_Qty)/rule.Order_Multiple_Qty)*rule.Order_Multiple_Qty)
        # Assume daily demand spread evenly, receipts usable at start of due day.
        balance=float(inventory.Usable_On_Hand_Qty); pre=0.; first_short=''
        receipt_day={d:int(receipts.loc[due==d,'Incoming_Qty'].sum()) for d in range(1,horizon+1)}
        for day in range(1,horizon+1):
            balance+=receipt_day[day]
            if day==max(1,lead): balance+=qty
            balance-=rate[j]
            if day<max(1,lead): pre=max(pre,-balance)
            if balance < -1e-9 and not first_short: first_short=(origin+pd.Timedelta(days=day)).date().isoformat()
        flags=[]
        if pre>1e-9: flags.append('Review shortage before new order arrives')
        if overdue: flags.append('Confirm overdue incoming units; excluded')
        if first_short and not pre>1e-9: flags.append('Review delivery timing shortage')
        rows.append(dict(Product_ID=p,Product_Name=names.get(p,''),Store_ID=store,OrderQty=qty,Quantity_Unit='product_unit',Forecast_Next_Week_Units=round(rate[j]*7,3),Coverage_Days=horizon,Forecast_Coverage_Units=round(rate[j]*horizon,3),Usable_Stock_Units=int(inventory.Usable_On_Hand_Qty),Incoming_Within_Coverage_Units=timely,Safety_Stock_Units=int(rule.Safety_Stock_Qty),Order_Multiple_Units=int(rule.Order_Multiple_Qty),Minimum_Order_Units=int(rule.Minimum_Order_Qty),New_Order_Expected_Date=(origin+pd.Timedelta(days=max(1,lead))).date().isoformat(),Expected_Prearrival_Shortage_Units=round(max(0,pre),3),First_Expected_Shortage_Date=first_short,Review_Flag='; '.join(flags)))
    return pd.DataFrame(rows)

def run(args):
    origin=pd.Timestamp(args.planning_date)
    if origin != origin.normalize(): raise ValueError('Planning date must be a calendar date')
    paths=[Path(getattr(args,k)).resolve() for k in ['sales_path','stock_path','deliveries_path','policy_path']]
    output=Path(args.output_path).resolve()
    if output in paths: raise ValueError('Output cannot overwrite an input')
    stock,inbound,policy,keys=read_operations(paths[1],paths[2],paths[3],origin)
    s=read_sales(paths[0],origin)
    if s.Order_Date.max()!=origin: raise ValueError('Sales must be current through planning date')
    if not set(keys).issubset(set(map(tuple,s[KEY].values))): raise ValueError('No history for operating keys')
    if s.groupby('Product_ID').Product_Name.nunique().gt(1).any(): raise ValueError('Conflicting product names')
    dates,y,first=panel(s,keys,origin)
    if (first>origin-pd.Timedelta(days=364)).any(): raise ValueError('Insufficient established history')
    names=s.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name.to_dict()
    result=order_rows(rates(SELECTED,dates,y,first,origin,keys),keys,stock,inbound,policy,origin,names)
    result.to_csv(output,index=False)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['sales-path','stock-path','deliveries-path','policy-path','planning-date','output-path']: parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try: result=run(args)
    except (ValueError,KeyError,OSError) as e: parser.exit(2,str(e)+'\n')
    print(f'Wrote {len(result)} rows; {result.OrderQty.sum()} product units; {(result.OrderQty>0).sum()} positive orders')
