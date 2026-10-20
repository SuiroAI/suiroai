"""Independent arithmetic checks and predeclared development diagnostics; no model reselection."""
import pandas as pd, numpy as np, json, hashlib
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
r=Path(__file__).parent
d=pd.read_csv(r/'development_predictions.csv');o=pd.read_csv(r/'restocking.csv')
policy=pd.read_csv(r/'../released/input-1.csv');stock=pd.read_csv(r/'../released/input-3.csv');ledger=pd.read_csv(r/'../released/input-2.csv')
m=json.loads((r/'measured_results.json').read_text()); selected=m['selected']
coverage=d[d.horizon.eq('coverage')]
origin=coverage.groupby(['origin','model']).error.apply(lambda v:float(np.sqrt(np.mean(v*v)))).unstack()
leave={}
for excluded in origin.index:
 sub=coverage[coverage.origin.ne(excluded)]
 scores=sub.groupby('model').error.apply(lambda v:float(np.sqrt(np.mean(v*v))))
 leave[excluded]={'lowest':scores.idxmin(),'selected_relative_improvement':float(1-scores[selected]/scores['mean84'])}
months=coverage.assign(month=coverage.origin.str[:7]).groupby(['month','model']).error.apply(lambda v:float(np.sqrt(np.mean(v*v)))).unstack()
subgroups={}
for group in ['Product_ID','Store_ID']:
 sc=coverage.groupby([group,'model']).error.apply(lambda v:float(np.sqrt(np.mean(v*v)))).unstack()
 sc.to_csv(r/f'{group}_diagnostics.csv')
 subgroups[group]={'pooled_beats_baseline':int((sc[selected]<sc.mean84).sum()),'groups':len(sc)}
# Independently recompute selected deployed pooled daily rates directly from transaction rows.
s=pd.read_csv(r/'../released/input-4.csv').drop_duplicates();s['status']=s.Order_Status.str.lower().str.strip();s['date']=pd.to_datetime(s.Order_Date)
use=s[s.status.isin(['completed','shipped','returned']) & s.Quantity.gt(0) & s.date.between('2025-09-08','2025-11-30')]
key=['Product_ID','Store_ID'];pairs=use.groupby(key).Quantity.sum();products=use.groupby('Product_ID').Quantity.sum();stores=use.groupby('Store_ID').Quantity.sum();total=use.Quantity.sum()
p=policy.set_index(key);st=stock.set_index(key)
for row in o.itertuples(index=False):
 k=(row.Product_ID,row.Store_ID); pr=p.loc[k];iv=st.loc[k]
 daily=.5*pairs.get(k,0)/84+.5*products.get(k[0],0)*stores.get(k[1],0)/total/84
 horizon=int(pr.Supplier_Lead_Time_Days+pr.Review_Period_Days)
 incoming=ledger[(ledger.Product_ID==k[0])&(ledger.Store_ID==k[1])&(pd.to_datetime(ledger.Expected_Arrival_Date)<=pd.Timestamp('2025-11-30')+pd.Timedelta(days=horizon))].Incoming_Qty.sum()
 gap=max(0,Decimal(str(daily*horizon))+int(pr.Safety_Stock_Qty)-int(iv.Usable_On_Hand_Qty)-int(incoming))
 qty=0 if gap==0 else int((max(gap,Decimal(int(pr.Minimum_Order_Qty)))/int(pr.Order_Multiple_Qty)).to_integral_value(rounding=ROUND_CEILING))*int(pr.Order_Multiple_Qty)
 assert qty==row.OrderQty,(k,qty,row.OrderQty)
 assert abs(daily*7-row.Next_Week_Recorded_Units_Estimate)<=.005001
assert list(o.columns[:5])==['Product_ID','Product_Name','Store_ID','OrderQty','Quantity_Unit']
assert o.OrderQty.dtype.kind in 'iu' and len(o)==336 and o.OrderQty.ge(0).all()
assert (o.Product_Name.notna()).all()
result=json.loads((r/'result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'}
assert hashlib.sha256((r/'restocking.csv').read_bytes()).hexdigest()==result['output_sha256']
diag={'origin_RMSE':origin.to_dict(),'leave_one_origin_out':leave,'month_RMSE':months.to_dict(),'pooling_subgroups':subgroups,'independent_order_checks':336,'stock_units':int(stock.Usable_On_Hand_Qty.sum()),'incoming_units':int(ledger.Incoming_Qty.sum()),'safety_units':int(policy.Safety_Stock_Qty.sum()),'zero_orders_with_positive_forecast':int(((o.OrderQty==0)&(o.Coverage_Recorded_Units_Estimate>0)).sum()),'top_order_products':o.groupby('Product_Name').OrderQty.sum().nlargest(8).to_dict()}
(r/'validation_results.json').write_text(json.dumps(diag,indent=2));print(json.dumps(diag,indent=2))
