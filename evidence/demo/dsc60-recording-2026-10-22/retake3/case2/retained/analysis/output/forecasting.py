"""Frozen lightweight forecast definitions; no network or model-service calls."""
import calendar
import time
import numpy as np
import pandas as pd

KEYS = ['Product_ID', 'Store_ID']
MODELS = ['baseline_month', 'recent13', 'seasonal_pool', 'ridge']

def prepare_sales(path, planning_date):
    use = ['Transaction_ID', 'Product_ID', 'Product_Name', 'Store_ID', 'Order_Date',
           'Order_Status', 'Return_Flag', 'Quantity']
    # Exact-row deduplication must precede reducing columns: unrelated genuine lines stay distinct.
    raw = pd.read_csv(path)
    needed = set(use)
    if not needed.issubset(raw.columns):
        raise ValueError('Missing sales columns: ' + str(needed-set(raw.columns)))
    if raw[use].drop(columns=['Product_Name']).isna().any().any():
        raise ValueError('Missing required sales values')
    raw['Order_Date'] = pd.to_datetime(raw.Order_Date, errors='raise')
    if (raw.Order_Date > planning_date).any():
        raise ValueError('Sales contain dates after planning date; supply an as-of extract')
    duplicate_count = int(raw.duplicated().sum())
    raw = raw.drop_duplicates().copy()
    if raw.Transaction_ID.duplicated().any():
        raise ValueError('Conflicting transaction IDs')
    raw['Quantity'] = pd.to_numeric(raw.Quantity, errors='raise')
    if not np.isfinite(raw.Quantity).all() or (raw.Quantity % 1 != 0).any():
        raise ValueError('Sales quantities must be finite integers')
    raw['status'] = raw.Order_Status.str.strip().str.lower()
    if not raw.status.isin(['completed','shipped','returned','cancelled','processing']).all():
        raise ValueError('Unrecognized sales status')
    if not raw.Return_Flag.str.lower().isin(['yes','no']).all():
        raise ValueError('Unrecognized return flags')
    raw['week'] = raw.Order_Date.dt.to_period('W-SUN').dt.start_time
    raw['fulfilled'] = raw.status.isin(['completed','shipped']) & (raw.Quantity > 0)
    names = raw.dropna(subset=['Product_Name']).groupby('Product_ID').Product_Name
    reliable = names.agg(lambda x: x.iloc[0] if x.nunique() == 1 else '')
    return raw, reliable.to_dict(), duplicate_count

def weekly_panel(raw, keys, origin):
    past = raw.loc[raw.Order_Date <= origin]
    start = raw.Order_Date.min().to_period('W-SUN').start_time
    if start < raw.Order_Date.min():
        start += pd.Timedelta(days=7)
    last = origin.to_period('W-SUN').start_time
    if origin.weekday() != 6:
        last -= pd.Timedelta(days=7)
    weeks = pd.date_range(start, last, freq='W-MON')
    idx = pd.MultiIndex.from_frame(keys[KEYS])
    fulfilled = past.loc[past.fulfilled]
    counts = fulfilled.groupby(KEYS+['week']).Quantity.sum().unstack('week')
    # Zero means no recorded fulfilled line in a store-active week only.
    panel = counts.reindex(index=idx, columns=weeks).fillna(0.)
    active = past.groupby(['Store_ID','week']).size()
    for i, (_, store) in enumerate(idx):
        known = np.array([(store, w) in active.index for w in weeks])
        panel.iloc[i, ~known] = np.nan
    first = past.groupby(KEYS).Order_Date.min()
    for i, key in enumerate(idx):
        if key not in first:
            raise ValueError('No sales history for operating key ' + str(key))
        panel.iloc[i, weeks < first[key].to_period('W-SUN').start_time] = np.nan
    return panel

def features(panel, target_week):
    history = panel.loc[:, panel.columns < target_week]
    def avg(n):
        return history.iloc[:, -n:].mean(axis=1).fillna(0).to_numpy()
    fallback = avg(52)
    def lag(n):
        col = target_week-pd.Timedelta(weeks=n)
        return panel[col].fillna(pd.Series(fallback,index=panel.index)).to_numpy() if col in panel else fallback
    numeric = np.column_stack([lag(1), avg(4), avg(13), fallback, lag(52),
                               np.repeat((target_week-pd.Timestamp('2022-01-03')).days/365.25,len(panel))])
    products = sorted(panel.index.get_level_values(0).unique())
    stores = sorted(panel.index.get_level_values(1).unique())
    product_hot = np.eye(len(products))[[products.index(k[0]) for k in panel.index]]
    store_hot = np.eye(len(stores))[[stores.index(k[1]) for k in panel.index]]
    month_hot = np.tile(np.eye(12)[target_week.month-1], (len(panel),1))
    return np.column_stack([numeric, product_hot, store_hot, month_hot])

def predict(raw, keys, origin, method):
    origin = pd.Timestamp(origin)
    start = time.perf_counter()
    past = raw.loc[raw.Order_Date <= origin]
    idx = pd.MultiIndex.from_frame(keys[KEYS])
    fulfilled = past.loc[past.fulfilled]
    panel = weekly_panel(past, keys, origin)
    target_week = origin + pd.Timedelta(days=1)
    timings = {'preparation_seconds': time.perf_counter()-start, 'fit_seconds':0.,'inference_seconds':0.}
    tic = time.perf_counter()
    if method == 'baseline_month':
        prev_end = origin.replace(day=1)-pd.Timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        month = fulfilled.loc[fulfilled.Order_Date.between(prev_start,prev_end)]
        # No-activity store-month is not a zero-demand observation.
        store_present = set(past.loc[past.Order_Date.between(prev_start,prev_end),'Store_ID'])
        if not set(keys.Store_ID).issubset(store_present):
            raise ValueError('Missing store activity in baseline month')
        pred = month.groupby(KEYS).Quantity.sum().reindex(idx,fill_value=0).to_numpy()*7/prev_end.day
    elif method == 'recent13':
        pred = panel.iloc[:,-13:].mean(axis=1).to_numpy()
    elif method == 'seasonal_pool':
        complete_years = fulfilled.loc[fulfilled.Order_Date.dt.year < origin.year]
        # Global calendar-day exposure, not active-transaction-day exposure.
        by_month = complete_years.groupby(complete_years.Order_Date.dt.month).Quantity.sum()
        years = sorted(complete_years.Order_Date.dt.year.unique())
        exposure = {m:sum(calendar.monthrange(int(y),m)[1] for y in years) for m in range(1,13)}
        daily = by_month.reindex(range(1,13),fill_value=0)/pd.Series(exposure)
        mean_daily = complete_years.Quantity.sum()/sum(exposure.values())
        factor = np.clip(daily[target_week.month]/mean_daily, .5, 2.) if mean_daily else 1.
        pred = panel.iloc[:,-52:].mean(axis=1).to_numpy()*factor
    elif method == 'ridge':
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        fit_start=time.perf_counter()
        training_weeks = panel.columns[panel.columns >= pd.Timestamp('2023-04-03')]
        if len(training_weeks) < 13:
            raise ValueError('At least 13 eligible training weeks after 2023-04-03 required')
        xx=[]; yy=[]
        for week in training_weeks:
            y = panel[week].to_numpy()
            valid=np.isfinite(y)
            xx.append(features(panel,week)[valid]); yy.append(y[valid])
        x=np.concatenate(xx); y=np.concatenate(yy)
        scaler=StandardScaler()
        x=scaler.fit_transform(x)
        model=Ridge(alpha=100.,solver='lsqr',tol=1e-6)
        model.fit(x,y)
        timings.update(fit_seconds=time.perf_counter()-fit_start,
                       training_rows=len(y), design_columns=x.shape[1],
                       design_array_bytes=int(x.nbytes), retained_panel_bytes=int(panel.memory_usage(index=True,deep=True).sum()))
        tic=time.perf_counter()
        pred=model.predict(scaler.transform(features(panel,target_week)))
    else:
        raise ValueError('Unknown method')
    timings['inference_seconds']=time.perf_counter()-tic
    pred=np.maximum(0,np.asarray(pred,dtype=float))
    if not np.isfinite(pred).all():
        raise ValueError('Insufficient history for finite forecasts')
    return pred,timings
