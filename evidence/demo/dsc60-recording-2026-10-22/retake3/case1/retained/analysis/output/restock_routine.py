#!/usr/bin/env python3
"""Local non-LLM recorded-sales forecasting and rule-based weekly replenishment."""
import argparse
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd

KEYS = ['Product_ID', 'Store_ID']
SELECTED_METHOD = 'sba'  # Frozen from evaluation_results.json by declared selection rule.
LAST_PROFILE = {}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_sales(path, planning_date, include_processing=False, exclude_returns=False):
    d = pd.read_csv(path).drop_duplicates()
    needed = KEYS+['Transaction_ID','Product_Name','Order_Date','Quantity','Order_Status','Return_Flag']
    require(set(needed).issubset(d.columns), 'Sales columns missing')
    require(not d[[c for c in needed if c!='Product_Name']].isna().any().any(), 'Missing required sales value')
    require(not d.Transaction_ID.duplicated().any(), 'Conflicting transaction identifiers')
    d['date'] = pd.to_datetime(d.Order_Date, errors='raise').dt.normalize()
    require(d.date.max() <= planning_date, 'Sales contain dates after planning date')
    require(d.date.max() == planning_date, 'Sales must be current through planning date')
    d['Quantity'] = pd.to_numeric(d.Quantity, errors='raise')
    require(np.isfinite(d.Quantity).all() and (d.Quantity % 1 == 0).all(), 'Invalid sales quantities')
    status = d.Order_Status.str.strip().str.lower()
    require(status.isin(['completed','shipped','returned','processing','cancelled']).all(), 'Unrecognized order status')
    keep = status.isin(['completed','shipped','returned'] + (['processing'] if include_processing else [])) & d.Quantity.gt(0)
    if exclude_returns:
        keep &= ~status.eq('returned') & ~d.Return_Flag.str.strip().str.lower().eq('yes')
    return d, d.loc[keep].copy()

def daily_panel(sales, pairs, end):
    index = pd.date_range(sales.date.min(),end)
    grouped = sales.groupby(['date']+KEYS).Quantity.sum().unstack(KEYS)
    panel = grouped.reindex(index=index, columns=pairs).fillna(0.).astype(float)
    first = sales.groupby(KEYS).date.min().reindex(pairs)
    require(not first.isna().any(), 'A supplied product at a store has no fulfilled-sales history; quantity unsupported')
    for j, start in enumerate(first):
        panel.iloc[panel.index < start, j] = np.nan
    return panel

def weekly_panel(panel, origin):
    d = panel.loc[:origin]
    # W-SUN groups Monday-Sunday. Require every day of the week to be exposed.
    sums = d.resample('W-SUN').sum(min_count=7)
    counts = d.resample('W-SUN').count()
    return sums.where(counts.eq(7)).loc[lambda x:x.index<=origin]

def features(dates, ids, n_pairs):
    from scipy import sparse
    dates = pd.DatetimeIndex(dates)
    n = len(ids); rows = np.arange(n)
    month = (dates-pd.Timedelta(days=3)).month.to_numpy()-1
    trend = ((dates-pd.Timestamp('2022-01-01')).days.to_numpy()/365.25)
    x = sparse.csr_matrix((np.ones(n*2),(np.r_[rows,rows],np.r_[ids,n_pairs+month])),shape=(n,n_pairs+12))
    return sparse.hstack([x,sparse.csr_matrix(trend[:,None])],format='csr')

def forecast(panel, origin, method, days=14, window=84):
    global LAST_PROFILE
    started=time.perf_counter(); cpu_start=time.process_time()
    origin = pd.Timestamp(origin)
    d = panel.loc[:origin]
    n = d.shape[1]
    if method == 'recent84':
        rate = d.loc[origin-pd.Timedelta(days=window-1):].mean().to_numpy()
        fit_end=time.perf_counter(); fit_cpu=time.process_time()
        out=np.tile(rate,(days,1))
        LAST_PROFILE={'fit_prepare_wall_seconds':fit_end-started,'fit_prepare_cpu_seconds':fit_cpu-cpu_start,'inference_wall_seconds':time.perf_counter()-fit_end,'inference_cpu_seconds':time.process_time()-fit_cpu}
        return out
    weekly = weekly_panel(d,origin)
    if method == 'sba':
        rates = []
        for j in range(n):
            values = weekly.iloc[:,j].dropna().to_numpy()
            positives = np.flatnonzero(values>0)
            if not len(positives):
                rates.append(0.); continue
            first = positives[0]; size = values[first]; interval = float(first+1); previous = first
            for pos in positives[1:]:
                size += .1*(values[pos]-size)
                interval += .1*(pos-previous-interval)
                previous = pos
            rates.append(.95*size/interval/7)
        fit_end=time.perf_counter(); fit_cpu=time.process_time()
        out=np.tile(rates,(days,1))
        LAST_PROFILE={'fit_prepare_wall_seconds':fit_end-started,'fit_prepare_cpu_seconds':fit_cpu-cpu_start,'inference_wall_seconds':time.perf_counter()-fit_end,'inference_cpu_seconds':time.process_time()-fit_cpu}
        return out
    if method == 'poisson':
        from sklearn.linear_model import PoissonRegressor
        from threadpoolctl import threadpool_limits
        vals = weekly.to_numpy(); wi, pj = np.where(np.isfinite(vals))
        x = features(weekly.index[wi],pj,n)
        with threadpool_limits(limits=1):
            model = PoissonRegressor(alpha=.001,max_iter=300,tol=1e-7).fit(x,vals[wi,pj])
            fit_end=time.perf_counter(); fit_cpu=time.process_time()
            future = pd.date_range(origin+pd.Timedelta(days=1),periods=days)
            ends = future.to_period('W-SUN').end_time.normalize()
            pred = model.predict(features(np.repeat(ends,n),np.tile(np.arange(n),days),n)).reshape(days,n)/7
        LAST_PROFILE={'fit_prepare_wall_seconds':fit_end-started,'fit_prepare_cpu_seconds':fit_cpu-cpu_start,'inference_wall_seconds':time.perf_counter()-fit_end,'inference_cpu_seconds':time.process_time()-fit_cpu,'iterations':int(model.n_iter_),'training_rows':len(wi),'sparse_design_bytes':int(x.data.nbytes+x.indices.nbytes+x.indptr.nbytes),'coefficients':len(model.coef_)}
        return pred
    raise ValueError('Unknown method')

def load_operations(stock_path, deliveries_path, policy_path, planning_date):
    stock, incoming, policy = [pd.read_csv(p) for p in [stock_path,deliveries_path,policy_path]]
    required = [(stock,KEYS+['Snapshot_Date','Usable_On_Hand_Qty','On_Order_Qty','Open_Order_Ledger_Complete','Quantity_Unit']), (policy,KEYS+['Effective_Date','Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty','Quantity_Unit']), (incoming,KEYS+['PO_Line_ID','Order_Date','Expected_Arrival_Date','Incoming_Qty','Quantity_Unit'])]
    for frame, cols in required:
        require(set(cols).issubset(frame.columns), 'Required operational columns missing')
        require(not frame[cols].isna().any().any(), 'Missing operational values')
        require(frame.Quantity_Unit.eq('product_unit').all(), 'Unsupported quantity unit')
    for frame in [stock,policy]:
        require(not frame.duplicated(KEYS).any(), 'Duplicate stock/policy keys')
    require(not incoming.PO_Line_ID.duplicated().any(), 'Duplicate incoming line identifiers')
    require(pd.to_datetime(stock.Snapshot_Date,errors='raise').eq(planning_date).all(), 'Stock snapshot must equal planning date')
    require(pd.to_datetime(policy.Effective_Date,errors='raise').le(planning_date).all(), 'Policy not yet effective')
    require(stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(), 'Incomplete incoming ledger')
    for frame,cols in [(stock,['Usable_On_Hand_Qty','On_Order_Qty']), (incoming,['Incoming_Qty']), (policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty'])]:
        for col in cols:
            frame[col] = pd.to_numeric(frame[col],errors='raise')
            require(np.isfinite(frame[col]).all() and frame[col].ge(0).all() and frame[col].mod(1).eq(0).all(), f'Invalid {col}')
    require(policy[['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty']].ge(1).all().all(), 'Lead time/review/multiple must be positive')
    stock = stock.set_index(KEYS).sort_index(); policy = policy.set_index(KEYS).sort_index()
    require(stock.index.equals(policy.index), 'Stock and policy keys differ')
    require(pd.MultiIndex.from_frame(incoming[KEYS]).isin(policy.index).all(), 'Unknown incoming product/store')
    incoming['arrival'] = pd.to_datetime(incoming.Expected_Arrival_Date,errors='raise')
    placed = pd.to_datetime(incoming.Order_Date,errors='raise')
    require(placed.le(planning_date).all() and incoming.arrival.gt(planning_date).all() and incoming.arrival.ge(placed).all(), 'Incoming order dates invalid or overdue; review required')
    ledger = incoming.groupby(KEYS).Incoming_Qty.sum().reindex(stock.index,fill_value=0)
    require(ledger.eq(stock.On_Order_Qty).all(), 'Incoming deliveries do not match stock on-order totals')
    return stock, incoming, policy

def make_orders(stock, incoming, policy, predictions, names, planning_date):
    rows = []
    for j, key in enumerate(policy.index):
        rule = policy.loc[key]; s = stock.loc[key]
        lead, review = int(rule.Supplier_Lead_Time_Days),int(rule.Review_Period_Days)
        h = lead+review
        arrivals = incoming.loc[incoming.Product_ID.eq(key[0]) & incoming.Store_ID.eq(key[1])]
        end = planning_date+pd.Timedelta(days=h)
        timely = int(arrivals.loc[arrivals.arrival.le(end),'Incoming_Qty'].sum())
        later = int(arrivals.loc[arrivals.arrival.gt(end),'Incoming_Qty'].sum())
        coverage = float(predictions[:h,j].sum()); next_week = float(predictions[:7,j].sum())
        raw = max(0.,coverage+rule.Safety_Stock_Qty-s.Usable_On_Hand_Qty-timely)
        qty = 0 if raw<=1e-10 else int(math.ceil(max(raw,rule.Minimum_Order_Qty)/rule.Order_Multiple_Qty)*rule.Order_Multiple_Qty)
        balance = float(s.Usable_On_Hand_Qty); shortage = 0.; first_shortage = ''
        # Arrivals available at start of their due day; new order arrives at start of day lead.
        # Pre-arrival shortage concerns end of days 1 .. lead-1.
        for day in range(1,lead):
            date = planning_date+pd.Timedelta(days=day)
            balance += arrivals.loc[arrivals.arrival.eq(date),'Incoming_Qty'].sum()
            balance -= predictions[day-1,j]
            if balance < -1e-10 and not first_shortage:
                first_shortage = str(date.date())
            shortage = max(shortage,-balance)
        flags=[]
        if shortage>1e-10: flags.append('Review supply before new order arrives')
        full_balance=float(s.Usable_On_Hand_Qty); full_shortage=0.; first_full_shortage=''
        for day in range(1,h+1):
            due=planning_date+pd.Timedelta(days=day)
            full_balance += arrivals.loc[arrivals.arrival.eq(due),'Incoming_Qty'].sum()
            if day==lead: full_balance+=qty
            full_balance -= predictions[day-1,j]
            if full_balance < -1e-10 and not first_full_shortage: first_full_shortage=str(due.date())
            full_shortage=max(full_shortage,-full_balance)
        if full_shortage>1e-10 and not shortage>1e-10: flags.append('Review delivery timing within coverage')
        if later: flags.append('Later delivery excluded from coverage')
        if qty and qty-raw>1e-10: flags.append('Minimum or pack rounding adds units')
        rows.append({'Product_ID':key[0],'Product_Name':names.get(key[0],''),'Store_ID':key[1], 'OrderQty':qty,'Quantity_Unit':'product_unit','Planning_Date':str(planning_date.date()),'New_Order_Arrival_Date':str((planning_date+pd.Timedelta(days=lead)).date()),'Coverage_End_Date':str(end.date()),'Forecast_Next_7_Days':round(next_week,4),'Forecast_Coverage_Units':round(coverage,4),'Usable_On_Hand_Qty':int(s.Usable_On_Hand_Qty),'Incoming_Within_Coverage_Qty':timely,'Incoming_After_Coverage_Qty':later,'Safety_Stock_Qty':int(rule.Safety_Stock_Qty),'Expected_Pre_Arrival_Shortage_Units':round(max(0,shortage),4),'First_Expected_Shortage_Date':first_shortage,'Expected_Coverage_Shortage_Units':round(max(0,full_shortage),4),'First_Coverage_Shortage_Date':first_full_shortage,'Review_Notes':'; '.join(flags)})
    return pd.DataFrame(rows)

def run(args):
    date = pd.Timestamp(args.planning_date)
    require(date == date.normalize() and not pd.isna(date), 'Planning date must be YYYY-MM-DD')
    output = Path(args.output_path).resolve()
    sources=[Path(p).resolve() for p in [args.sales_path,args.stock_path,args.deliveries_path,args.policy_path]]
    require(output not in sources, 'Output must not overwrite any source')
    stock, incoming, policy = load_operations(args.stock_path,args.deliveries_path,args.policy_path,date)
    raw,sales = read_sales(args.sales_path,date)
    require(pd.MultiIndex.from_frame(raw[KEYS]).isin(policy.index).all(), 'Sales contain unknown product/store keys')
    panel = daily_panel(sales,policy.index,date)
    pred = forecast(panel,date,SELECTED_METHOD,days=max(7,int((policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).max())))
    names={k:v.Product_Name.dropna().iloc[0] for k,v in raw.groupby('Product_ID') if v.Product_Name.nunique()==1}
    result=make_orders(stock,incoming,policy,pred,names,date)
    require(result.OrderQty.ge(0).all() and result.OrderQty.mod(1).eq(0).all(), 'Invalid output orders')
    output.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(output,index=False,lineterminator='\n')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ['sales-path','stock-path','deliveries-path','policy-path','planning-date','output-path']:
        parser.add_argument('--'+option,required=True)
    args=parser.parse_args()
    try:
        result=run(args)
    except (ValueError,KeyError,TypeError) as exc:
        parser.error(str(exc))
    print(f'Wrote {len(result)} rows; {int(result.OrderQty.sum())} product units')

if __name__=='__main__':
    main()
