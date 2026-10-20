"""Weekly CPU-only recorded-sales forecast and policy arithmetic. No network or model API."""
import argparse
import math
import json
import platform
import resource
import time
from pathlib import Path
import numpy as np
import pandas as pd

KEY = ['Product_ID', 'Store_ID']
SELECTED_MODEL = 'mean182'  # Frozen by evaluation_plan.json and comparison_results.json.
LAST_MEASUREMENTS = {}

def peak_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if platform.system() == 'Darwin' else peak*1024)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def load_inputs(sales_path, stock_path, deliveries_path, policy_path, planning_date):
    date = pd.Timestamp(planning_date)
    require(not pd.isna(date) and date == date.normalize() and date.tz is None, 'Use a calendar planning date YYYY-MM-DD')
    sales = pd.read_csv(sales_path).drop_duplicates()
    stock = pd.read_csv(stock_path)
    inbound = pd.read_csv(deliveries_path)
    policy = pd.read_csv(policy_path)
    for frame, cols in [(sales, KEY + ['Transaction_ID','Order_Date','Quantity','Order_Status','Return_Flag','Product_Name']), (stock, KEY+['Snapshot_Date','Usable_On_Hand_Qty','On_Order_Qty','Open_Order_Ledger_Complete','Quantity_Unit']), (inbound, KEY+['PO_Line_ID','Order_Date','Expected_Arrival_Date','Incoming_Qty','Quantity_Unit']), (policy, KEY+['Effective_Date','Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty','Quantity_Unit'])]:
        require(set(cols).issubset(frame.columns), 'Missing required columns')
        require(frame[[x for x in cols if x != 'Product_Name']].notna().all().all(), 'Missing required values')
    for frame, cols in [(sales,['Order_Date']), (stock,['Snapshot_Date']), (inbound,['Order_Date','Expected_Arrival_Date']), (policy,['Effective_Date'])]:
        for c in cols:
            frame[c] = pd.to_datetime(frame[c], format='%Y-%m-%d', errors='raise')
    require(not sales.Transaction_ID.duplicated().any(), 'Conflicting transaction identifiers')
    require(not inbound.PO_Line_ID.duplicated().any(), 'Duplicate incoming delivery lines')
    for frame in [stock, policy]:
        require(not frame.duplicated(KEY).any(), 'Duplicate product/store operational rows')
        require(frame.Quantity_Unit.eq('product_unit').all(), 'Unsupported quantity unit')
    require(inbound.Quantity_Unit.eq('product_unit').all(), 'Unsupported inbound unit')
    require(stock.Snapshot_Date.eq(date).all(), 'Stock snapshot must equal planning date')
    require(policy.Effective_Date.le(date).all(), 'Policy effective after planning date')
    require(sales.Order_Date.max() <= date, 'Sales include dates beyond planning boundary')
    require(sales.Order_Date.max() == date, 'Sales are stale at planning date')
    require(inbound.Order_Date.le(date).all(), 'Incoming orders not known on planning date')
    require(inbound.Expected_Arrival_Date.gt(date).all(), 'Overdue inbound needs review before calculation')
    require(inbound.Expected_Arrival_Date.ge(inbound.Order_Date).all(), 'Arrival before order')
    require(stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true').all(), 'Incomplete inbound ledger')
    for frame, cols in [(stock,['Usable_On_Hand_Qty','On_Order_Qty']), (inbound,['Incoming_Qty']), (policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty'])]:
        for c in cols:
            require(pd.api.types.is_numeric_dtype(frame[c]) and np.isfinite(frame[c]).all() and frame[c].ge(0).all() and frame[c].eq(np.floor(frame[c])).all(), 'Operational quantities/days must be nonnegative integers')
    require(policy[['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty']].gt(0).all().all(), 'Lead, review and multiple must be positive')
    require(pd.api.types.is_numeric_dtype(sales.Quantity) and np.isfinite(sales.Quantity).all() and sales.Quantity.eq(np.floor(sales.Quantity)).all(), 'Sales quantity must be integer')
    sales['status'] = sales.Order_Status.str.strip().str.lower()
    require(sales.status.isin(['completed','shipped','returned','cancelled','processing']).all(), 'Unknown sales status')
    require(sales.Return_Flag.str.strip().str.lower().isin(['yes','no']).all(), 'Unknown return flag')
    pairs = pd.MultiIndex.from_frame(policy.sort_values(KEY)[KEY])
    require(set(pairs) == set(pd.MultiIndex.from_frame(stock[KEY])), 'Policy/stock population mismatch')
    require(set(pd.MultiIndex.from_frame(inbound[KEY])).issubset(set(pairs)), 'Unmatched inbound product/store')
    require(set(pd.MultiIndex.from_frame(sales[KEY])).issubset(set(pairs)), 'Sales outside policy assortment')
    ledger = inbound.groupby(KEY).Incoming_Qty.sum().reindex(pairs, fill_value=0)
    require(np.array_equal(ledger.to_numpy(), stock.set_index(KEY).reindex(pairs).On_Order_Qty.to_numpy()), 'Incoming deliveries disagree with stock on-order quantities')
    calendar = pd.date_range(sales.Order_Date.min(), date)
    require(len(calendar.difference(sales.Order_Date)) == 0, 'Missing whole-ledger calendar dates: cannot infer zeros')
    return sales, stock.set_index(KEY).reindex(pairs), inbound, policy.set_index(KEY).reindex(pairs), date, pairs

def daily_sales(sales, pairs, end, exclude_returns=False):
    s = sales[sales.Order_Date.le(end)]
    dates = pd.date_range(s.Order_Date.min(), end)
    valid = s.status.isin(['completed','shipped']) & s.Quantity.gt(0)
    if exclude_returns:
        valid &= s.Return_Flag.str.lower().eq('no')
    grouped = s.loc[valid].groupby(['Order_Date']+KEY).Quantity.sum().unstack(KEY)
    # Absence means zero RECORDED transactions conditional on capture, not latent demand.
    return grouped.reindex(index=dates, columns=pairs).fillna(0).astype(float)

def features(dates, n_pairs):
    from scipy.sparse import csr_matrix, hstack
    dates = pd.DatetimeIndex(dates)
    pair_ids = np.tile(np.arange(n_pairs), len(dates))
    months = np.repeat(dates.month.to_numpy()-1, n_pairs)
    rows = np.arange(len(pair_ids))
    pair_x = csr_matrix((np.ones(len(rows)), (rows, pair_ids)), shape=(len(rows), n_pairs))
    month_x = csr_matrix((np.ones(len(rows)), (rows, months)), shape=(len(rows),12))
    trend = np.repeat((dates-pd.Timestamp('2022-01-01')).days.to_numpy()/365.25, n_pairs)
    return hstack([pair_x, month_x, csr_matrix(trend[:,None])], format='csr')

def fit_forecaster(daily, origin, model):
    if model.startswith('mean'):
        window = int(model[4:])
        require(len(daily) >= window, 'Insufficient calendar history for selected model')
        return daily.loc[:origin].tail(window).mean().to_numpy()
    from sklearn.linear_model import PoissonRegressor
    last_sunday = origin-pd.Timedelta(days=(origin.dayofweek+1)%7)
    ends = pd.date_range(end=last_sunday, periods=156, freq='W-SUN')
    ends = ends[ends-pd.Timedelta(days=6) >= daily.index.min()]
    require(len(ends) >= 52, 'Poisson seasonal model needs at least 52 full weeks')
    y = np.stack([daily.loc[e-pd.Timedelta(days=6):e].sum().to_numpy() for e in ends]).ravel()
    fit = PoissonRegressor(alpha=.01, max_iter=300, tol=1e-5)
    fit.fit(features(ends, daily.shape[1]), y)
    require(fit.n_iter_ < 300, 'Poisson fit did not converge')
    return fit

def predict_days(fit, origin, days, n_pairs):
    if isinstance(fit, np.ndarray):
        return np.tile(fit, (days,1))
    dates = pd.date_range(origin+pd.Timedelta(days=1), periods=days)
    return fit.predict(features(dates,n_pairs)).reshape(days,n_pairs)/7

def order_table(sales, stock, inbound, policy, date, pairs, predicted, multiplier=1.0):
    rows = []
    name_map = sales.groupby('Product_ID').Product_Name.agg(lambda x: next(iter(x.dropna().unique())) if x.dropna().nunique()==1 else '')
    grouped_in = {k:g for k,g in inbound.groupby(KEY)}
    for j, pair in enumerate(pairs):
        p, s = policy.iloc[j], stock.iloc[j]
        lead, horizon = int(p.Supplier_Lead_Time_Days), int(p.Supplier_Lead_Time_Days+p.Review_Period_Days)
        pred = predicted[:horizon,j]*multiplier
        incoming = grouped_in.get(pair, inbound.iloc[:0])
        within = incoming.loc[incoming.Expected_Arrival_Date.le(date+pd.Timedelta(days=horizon))]
        incoming_qty = int(within.Incoming_Qty.sum())
        raw = max(0.0, float(pred.sum()+p.Safety_Stock_Qty-s.Usable_On_Hand_Qty-incoming_qty))
        multiple = int(p.Order_Multiple_Qty)
        order = 0 if raw<=1e-10 else math.ceil(max(raw,float(p.Minimum_Order_Qty))/multiple-1e-12)*multiple
        # Conservative end-of-day receipts; maximum cumulative supply gap before new order arrives.
        balance, shortage = float(s.Usable_On_Hand_Qty), 0.0
        for day in range(1,lead+1):
            balance -= pred[day-1]
            shortage = max(shortage, -balance)
            balance += incoming.loc[incoming.Expected_Arrival_Date.eq(date+pd.Timedelta(days=day)), 'Incoming_Qty'].sum()
        rows.append(dict(Product_ID=pair[0],Product_Name=name_map.get(pair[0],''),Store_ID=pair[1],OrderQty=int(order),Quantity_Unit='product_unit',Usable_Stock_Qty=int(s.Usable_On_Hand_Qty),Incoming_Within_Coverage_Qty=incoming_qty,Incoming_After_Coverage_Qty=int(incoming.Incoming_Qty.sum()-incoming_qty),Forecast_Next_Week_Qty=round(float(pred[:7].sum()),4),Coverage_Days=horizon,Forecast_Coverage_Qty=round(float(pred.sum()),4),Safety_Stock_Qty=int(p.Safety_Stock_Qty),Order_Multiple_Qty=multiple,Minimum_Order_Qty=int(p.Minimum_Order_Qty),New_Order_Expected_Date=(date+pd.Timedelta(days=lead)).strftime('%Y-%m-%d'),Coverage_End_Date=(date+pd.Timedelta(days=horizon)).strftime('%Y-%m-%d'),Expected_Shortage_Before_New_Order_Qty=round(max(0.0,shortage),4),Review_Before_Arrival=bool(shortage>1e-10)))
    return pd.DataFrame(rows)

def calculate(args):
    t = time.perf_counter()
    sales, stock, inbound, policy, date, pairs = load_inputs(args.sales_path,args.stock_path,args.deliveries_path,args.policy_path,args.planning_date)
    daily = daily_sales(sales,pairs,date)
    LAST_MEASUREMENTS.update(preparation_seconds=time.perf_counter()-t, preparation_peak_rss_bytes=peak_bytes(), daily_array_bytes=int(daily.to_numpy().nbytes),sales_frame_deep_bytes=int(sales.memory_usage(deep=True).sum()))
    t = time.perf_counter()
    fitted = fit_forecaster(daily,date,SELECTED_MODEL)
    LAST_MEASUREMENTS.update(fitting_seconds=time.perf_counter()-t, fitting_cumulative_peak_rss_bytes=peak_bytes(),retained_model_bytes=int(fitted.nbytes) if isinstance(fitted,np.ndarray) else None)
    t = time.perf_counter()
    predicted = predict_days(fitted,date,int((policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).max()),len(pairs))
    LAST_MEASUREMENTS.update(inference_seconds=time.perf_counter()-t,inference_cumulative_peak_rss_bytes=peak_bytes(),prediction_array_bytes=int(predicted.nbytes))
    t = time.perf_counter()
    result = order_table(sales,stock,inbound,policy,date,pairs,predicted)
    LAST_MEASUREMENTS.update(order_calculation_seconds=time.perf_counter()-t,calculation_cumulative_peak_rss_bytes=peak_bytes())
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['sales_path','stock_path','deliveries_path','policy_path','planning_date','output_path']:
        parser.add_argument('--'+name.replace('_','-'),required=True)
    args=parser.parse_args()
    output=Path(args.output_path).resolve()
    sources=[Path(getattr(args,n)).resolve() for n in ['sales_path','stock_path','deliveries_path','policy_path']]
    require(output not in sources,'Output must not overwrite a source')
    require(not output.exists(),'Output already exists; choose a new filename')
    result=calculate(args)
    require(result.OrderQty.ge(0).all() and result.OrderQty.eq(result.OrderQty.astype(int)).all(),'Invalid order output')
    result.to_csv(output,index=False)
    print(f'Wrote {len(result)} rows; {int(result.OrderQty.sum())} product units')
    print(json.dumps(LAST_MEASUREMENTS))

if __name__=='__main__':
    main()
