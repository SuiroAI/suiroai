"""Independent checks of source joins, arithmetic, timing and delivered bytes."""
import hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent; SRC=ROOT.parent/'released'
keys=['Product_ID','Store_ID']; date=pd.Timestamp('2025-11-30')
orders=pd.read_csv(ROOT/'restocking.csv',keep_default_na=False)
policy=pd.read_csv(SRC/'input-1.csv').set_index(keys)
stock=pd.read_csv(SRC/'input-3.csv').set_index(keys)
deliveries=pd.read_csv(SRC/'input-2.csv'); deliveries['due']=pd.to_datetime(deliveries.Expected_Arrival_Date)
forecast=pd.read_csv(ROOT/'final_forecast_daily.csv',header=[0,1],index_col=0)
# CSV has two column-name rows and a separate index-name row.
forecast=forecast.loc[forecast.index.notna()].copy()
forecast.index=pd.to_datetime(forecast.index)
forecast=forecast.astype(float)
assert len(orders)==336 and not orders.duplicated(keys).any()
assert set(map(tuple,orders[keys].values))==set(policy.index)
assert orders.OrderQty.ge(0).all() and orders.OrderQty.mod(1).eq(0).all()
assert orders.Quantity_Unit.eq('product_unit').all()
assert not any(x in c.lower() for c in orders.columns for x in ['synthetic','illustrative','provenance'])
assert forecast.shape==(14,336)
for row in orders.itertuples(index=False):
    k=(row.Product_ID,row.Store_ID); p=policy.loc[k]; s=stock.loc[k]
    lead=int(p.Supplier_Lead_Time_Days); h=lead+int(p.Review_Period_Days)
    horizon_end=date+pd.Timedelta(days=h)
    incoming=deliveries.loc[deliveries.Product_ID.eq(k[0]) & deliveries.Store_ID.eq(k[1])]
    available=int(incoming.loc[incoming.due.le(horizon_end),'Incoming_Qty'].sum())
    demand=forecast[k].iloc[:h].sum()
    short=max(0.,float(demand+p.Safety_Stock_Qty-s.Usable_On_Hand_Qty-available))
    expected=0 if short<=1e-10 else math.ceil(max(short,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty
    assert row.OrderQty==expected
    assert row.OrderQty==0 or (row.OrderQty>=p.Minimum_Order_Qty and row.OrderQty % p.Order_Multiple_Qty==0)
    assert abs(row.Forecast_Coverage_Units-demand)<=.000051
    assert abs(row.Forecast_Next_7_Days-forecast[k].iloc[:7].sum())<=.000051
    assert row.Incoming_Within_Coverage_Qty==available
    assert row.New_Order_Arrival_Date==str((date+pd.Timedelta(days=lead)).date())
    balance=float(s.Usable_On_Hand_Qty); lowest=0.; lowest_pre=0.; first=''; first_pre=''
    for day in range(1,h+1):
        due=date+pd.Timedelta(days=day)
        balance+=incoming.loc[incoming.due.eq(due),'Incoming_Qty'].sum()
        if day==lead: balance+=expected
        balance-=forecast[k].iloc[day-1]
        lowest=max(lowest,-balance)
        if balance < -1e-10 and not first: first=str(due.date())
        if day<lead:
            lowest_pre=max(lowest_pre,-balance)
            if balance < -1e-10 and not first_pre: first_pre=str(due.date())
    assert abs(row.Expected_Coverage_Shortage_Units-lowest)<=.000051
    assert abs(row.Expected_Pre_Arrival_Shortage_Units-lowest_pre)<=.000051
    assert row.First_Expected_Shortage_Date==first_pre and row.First_Coverage_Shortage_Date==first

# Independent hand-formula SBA reconstruction for one series, from raw transactions.
sales=pd.read_csv(SRC/'input-4.csv').drop_duplicates()
sales['date']=pd.to_datetime(sales.Order_Date)
status=sales.Order_Status.str.strip().str.lower()
units=sales.loc[status.isin(['completed','shipped','returned']) & sales.Quantity.gt(0)]
sample=units.loc[units.Product_ID.eq('P001') & units.Store_ID.eq('AUS-01')]
day=sample.groupby('date').Quantity.sum().reindex(pd.date_range(sample.date.min(),date),fill_value=0)
wk=day.resample('W-SUN').sum().loc[day.resample('W-SUN').count().eq(7)]
hits=np.flatnonzero(wk.to_numpy()>0)
z=float(wk.iloc[hits[0]]); interval=float(hits[0]+1)
for before,after in zip(hits[:-1],hits[1:]):
    z=.9*z+.1*float(wk.iloc[after]); interval=.9*interval+.1*(after-before)
assert abs(.95*z/interval/7-forecast[('P001','AUS-01')].iloc[0])<1e-12

digest=hashlib.sha256((ROOT/'restocking.csv').read_bytes()).hexdigest()
result=json.loads((ROOT/'result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'}
assert result=={'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest}
assert json.loads((ROOT/'routine_measurements.json').read_text())['program_sha256']==hashlib.sha256((ROOT/'restock_routine.py').read_bytes()).hexdigest()
e=json.loads((ROOT/'evaluation_results.json').read_text())
improvement=1-e['scores']['sba']['7']['mae']/e['scores']['recent84']['7']['mae']
summary={'checks_passed':True,'rows':len(orders),'order_units':int(orders.OrderQty.sum()),'positive_orders':int(orders.OrderQty.gt(0).sum()),'zero_orders':int(orders.OrderQty.eq(0).sum()),'shortage_rows':int(orders.Expected_Pre_Arrival_Shortage_Units.gt(0).sum()),'all_rows_independent_policy_and_trajectory_checks':True,'one_series_independent_sba_check':True,'sha256':digest,'mae_relative_improvement':improvement,'stores_with_lower_mae_than_baseline':sum(s['sba']['mae']<s['recent84']['mae'] for s in e['per_store'].values()),'weekly_origins_with_lower_mae_than_baseline':sum(s['sba']['mae']<s['recent84']['mae'] for s in e['per_origin'].values()),'true_demand_or_service_improvement_established':False}
(ROOT/'validation_results.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
