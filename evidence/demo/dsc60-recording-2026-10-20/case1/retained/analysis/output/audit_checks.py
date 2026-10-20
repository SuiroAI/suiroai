"""Independent arithmetic and planned secondary checks of saved results."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd

r=json.loads(Path('development_results.json').read_text())
d=pd.read_csv('development_predictions.csv')
for name,m in r['primary'].items():
    z=d[d.method.eq(name)&d.horizon.eq(7)]
    assert len(z)==2688 and np.isclose(abs(z.actual-z.prediction).mean(),m['MAE'])
    assert np.isclose(z.actual.sum(),1845)
for h in range(8,15):
    z=d[d.horizon.eq(h)]
    assert z.groupby('method').size().eq(2352).all()
    assert z.groupby('method').actual.sum().nunique()==1
assert pd.to_datetime(d.origin).add(pd.to_timedelta(d.horizon,unit='D')).max()<=pd.Timestamp('2025-11-30')
assert not d.duplicated(['origin','horizon','method','Product_ID','Store_ID']).any()
result=json.loads(Path('result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'}
assert result['output_sha256']==hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
o=pd.read_csv('restocking.csv');u=pd.read_csv('routine_point_calculations.csv')
z=o.merge(u,on=['Product_ID','Store_ID'],suffixes=('','_full'))
need=np.maximum(0,z.Forecast_Coverage_Units_full+z.Safety_Stock-z.Usable_Stock-z.Incoming_Within_Coverage)
p=pd.read_csv('../released/input-1.csv')
z=z.merge(p[['Product_ID','Store_ID','Minimum_Order_Qty']],on=['Product_ID','Store_ID'],validate='one_to_one')
independent_qty=np.where(need>0,np.ceil(np.maximum(need,z.Minimum_Order_Qty)/z.Order_Multiple)*z.Order_Multiple,0).astype(int)
assert (independent_qty==z.OrderQty).all()
assert z.Quantity_Unit.eq('product_unit').all() and z.OrderQty.ge(0).all()
assert z.OrderQty.gt(0).sum()==112 and z.OrderQty.sum()==877

s=pd.read_csv('../released/input-4.csv').drop_duplicates()
s['date']=pd.to_datetime(s.Order_Date);s['status']=s.Order_Status.str.strip().str.lower()
first=s.groupby(['Product_ID','Store_ID']).date.min()
good=s[s.Quantity.gt(0)&s.status.isin(['completed','shipped','returned'])]
diagnostics={'purpose':'Prespecified secondary checks, not a new candidate selection; initial primary and baseline unchanged.', 'annual_seasonality':{},'event_sparsity':{},'order_arithmetic':{'unrounded_positive_need_units':float(need.sum()),'ordered_units':int(z.OrderQty.sum()),'rounding_and_minimum_increment_units':float(z.OrderQty.sum()-need.sum()),'supplied_total_safety_stock_units':int(z.Safety_Stock.sum()),'usable_stock_total':int(z.Usable_Stock.sum()),'incoming_total':int(z.Incoming_Within_Coverage.sum())}}
for year in range(2022,2025):
    a=good[good.date.dt.year.eq(year)]
    annual_rate=a.Quantity.sum()/(366 if year==2024 else 365)
    diagnostics['annual_seasonality'][str(year)]={str(month):float(a.loc[a.date.dt.month.eq(month),'Quantity'].sum()/pd.Period(f'{year}-{month:02d}').days_in_month/annual_rate) for month in [10,11,12]}
week=d[d.horizon.eq(7)].copy()
for origin in sorted(week.origin.unique()):
    when=pd.Timestamp(origin)
    prior=good[good.date.between(when-pd.Timedelta(days=363),when)]
    days=prior.groupby(['Product_ID','Store_ID']).date.nunique().rename('positive_days')
    at=week.origin.eq(origin)
    j=week.loc[at].merge(days,on=['Product_ID','Store_ID'],how='left').fillna({'positive_days':0})
    week.loc[at,'segment']=np.where(j.positive_days.to_numpy()/364<1/28,'fewer_than_one_sale_day_per_28_days','at_least_one_sale_day_per_28_days')
for segment,group in week.groupby('segment'):
    diagnostics['event_sparsity'][segment]={name:{'MAE':float((q.actual-q.prediction).abs().mean()),'n':len(q)} for name,q in group.groupby('method')}
diagnostics['checks_passed']=['Identical candidate evaluation targets/populations/origins','All comparison outcome dates <= November 30','Primary scores recomputed from prediction rows','Full-precision independent order arithmetic agrees across all 336 rows','Nonnegative integral unit quantities and pack multiples','CSV readback and SHA-256 match exact three-key result manifest']
Path('validation_and_diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
print(json.dumps(diagnostics,indent=2))
