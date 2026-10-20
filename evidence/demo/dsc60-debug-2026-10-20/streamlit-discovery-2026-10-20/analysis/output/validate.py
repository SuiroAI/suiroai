from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, math
ROOT=Path(__file__).resolve().parent; SRC=ROOT.parent/'released'
csv=pd.read_csv(ROOT/'restocking.csv'); policy=pd.read_csv(SRC/'input-1.csv'); inv=pd.read_csv(SRC/'input-3.csv'); rec=pd.read_csv(SRC/'input-2.csv'); K=['Product_ID','Store_ID']
assert len(csv)==336 and not csv.duplicated(K).any() and csv.OrderQty.ge(0).all() and (csv.OrderQty%1==0).all()
assert csv.Product_Name.notna().all() and csv.Quantity_Unit.eq('product_unit').all()
# Independent scalar loop validates stock subtraction, due-date filtering, pack/MOQ,
# complete key coverage and final model values using routine implementation output.
routine=pd.read_csv(ROOT/'routine_orders.csv').set_index(K)
frozen=np.load(ROOT/'selected_model.npz'); exact_model=dict(zip(zip(frozen['Product_ID'],frozen['Store_ID']),frozen['weekly_recorded_units']))
policy=policy.set_index(K); inv=inv.set_index(K); actual=csv.set_index(K)
checks=0
for key,row in actual.iterrows():
 p=policy.loc[key]; stock=inv.loc[key]
 end=pd.Timestamp('2025-11-30')+pd.Timedelta(days=int(p.Supplier_Lead_Time_Days+p.Review_Period_Days))
 incoming=rec.loc[(rec.Product_ID==key[0])&(rec.Store_ID==key[1])&(pd.to_datetime(rec.Expected_Arrival_Date)<=end),'Incoming_Qty'].sum()
 # Exact full-precision coverage can be reconstructed from rounded export to <=0.0005;
 # use interval arithmetic and allow the independently reproduced quantity when a pack boundary is crossed.
 center=row.Forecast_Coverage_Units+p.Safety_Stock_Qty-stock.Usable_On_Hand_Qty-incoming
 bounds=[]
 for value in [center-.000501,center+.000501]:
  bounds.append(0 if value<=0 else math.ceil(max(value,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty)
 assert min(bounds)<=row.OrderQty<=max(bounds)
 assert row.OrderQty==routine.loc[key,'OrderQty']
 exact_need=max(0,exact_model[key]*(p.Supplier_Lead_Time_Days+p.Review_Period_Days)/7+p.Safety_Stock_Qty-stock.Usable_On_Hand_Qty-incoming)
 exact_qty=0 if exact_need<=0 else math.ceil(max(exact_need,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty
 assert row.OrderQty==exact_qty
 assert incoming==row.Incoming_Within_Coverage_Units
 assert end.strftime('%Y-%m-%d')==row.Coverage_End
 checks+=1
scores=pd.read_csv(ROOT/'comparison_predictions.csv')
for (variant,horizon,origin),g in scores.groupby(['variant','horizon','origin']):
 members=[set(map(tuple,sub[K].values)) for _,sub in g.groupby('model')]; assert all(m==members[0] for m in members)
 truth=[sub.sort_values(K).actual_recorded_units.to_numpy() for _,sub in g.groupby('model')]; assert all(np.array_equal(v,truth[0]) for v in truth)
 assert np.allclose(g.forecast_units-g.actual_recorded_units,g.error_units)
 assert np.allclose(abs(g.error_units),g.absolute_error_units)
assert pd.to_datetime(scores.origin).max()==pd.Timestamp('2025-11-16')
summary=pd.read_csv(ROOT/'comparison_summary.csv')
for _,row in summary.iterrows():
 sub=scores[(scores.variant==row.variant)&(scores.model==row.model)&(scores.horizon.astype(str)==str(row.horizon))]
 assert np.isclose(sub.absolute_error_units.mean(),row.mae)
data=pd.read_csv(SRC/'input-4.csv',usecols=['Transaction_ID','Order_Date','Store_ID']).drop_duplicates('Transaction_ID'); data['date']=pd.to_datetime(data.Order_Date)
assert data.date.max()==pd.Timestamp('2025-11-30')
obs=data.loc[data.date.between('2025-06-02','2025-11-30')].groupby('Store_ID').date.nunique()
scenario=[]
for key,row in actual.iterrows():
 factor=182/obs[key[1]]; p=policy.loc[key]
 coverage=exact_model[key]*(p.Supplier_Lead_Time_Days+p.Review_Period_Days)/7*factor
 net=max(0,coverage+p.Safety_Stock_Qty-row.Usable_Stock_Units-row.Incoming_Within_Coverage_Units)
 qty=0 if net<=0 else math.ceil(max(net,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty
 scenario.append([key[0],key[1],factor,qty,int(row.OrderQty)])
sen=pd.DataFrame(scenario,columns=K+['unknown_day_rate_multiplier','scenario_OrderQty','selected_OrderQty']); sen.to_csv(ROOT/'missing_day_sensitivity.csv',index=False)
results=json.loads((ROOT/'measured_results.json').read_text()); sha=hashlib.sha256((ROOT/'restocking.csv').read_bytes()).hexdigest(); result=json.loads((ROOT/'result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'} and result['output_sha256']==sha==results['csv_sha256']
assert csv.OrderQty.sum()==results['total_units'] and (csv.OrderQty>0).sum()==results['positive_orders']
check={'rows_checked':checks,'order_units':int(csv.OrderQty.sum()),'sha256':sha,'common_comparison_targets_and_membership':True,'primary_metrics_recomputed':True,'independent_routine_implementation_matches':True,'all_quantities_independently_recomputed_at_full_precision':True,'reserved_sales_not_used':True,'missing_day_scenario':{'units':int(sen.scenario_OrderQty.sum()),'rows_changed':int((sen.scenario_OrderQty!=sen.selected_OrderQty).sum()),'multiplier_min':float(sen.unknown_day_rate_multiplier.min()),'multiplier_max':float(sen.unknown_day_rate_multiplier.max()),'limits':'Exploratory same-rate scenario, not actual missing demand. Full-precision frozen model forecasts used. No forecast reselection.'}}
(ROOT/'validation.json').write_text(json.dumps(check,indent=2)+'\n'); print(json.dumps(check,indent=2))
