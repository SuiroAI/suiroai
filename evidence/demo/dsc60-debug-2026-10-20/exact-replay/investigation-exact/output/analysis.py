import pandas as pd, numpy as np, json, hashlib, time, platform
from pathlib import Path
START=time.perf_counter()
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent/'released'
KEY=['Product_ID','Store_ID']
policy, inbound, stock, raw=[pd.read_csv(ROOT/f'input-{i}.csv') for i in range(1,5)]
audit={'source_files':{f'input-{i}.csv':{'rows':len(d),'sha256':hashlib.sha256((ROOT/f'input-{i}.csv').read_bytes()).hexdigest()} for i,d in enumerate([policy,inbound,stock,raw],1)}}
s=raw.drop_duplicates().copy()
assert not s.Transaction_ID.duplicated().any()
s['date']=pd.to_datetime(s.Order_Date)
s['status']=s.Order_Status.str.strip().str.lower()
s['valid']=s.Quantity.gt(0)&s.Quantity.mod(1).eq(0)
fulfilled=s.status.isin(['completed','shipped','returned'])
s['target']=np.where(s.valid & fulfilled,s.Quantity,0)
dates=pd.date_range(s.date.min(),s.date.max())
assert set(dates)==set(s.date.unique())
pairs=pd.MultiIndex.from_frame(policy[KEY].sort_values(KEY))
assert set(pairs)==set(pd.MultiIndex.from_frame(stock[KEY]))==set(pd.MultiIndex.from_frame(s[KEY]))
daily=s.groupby(['date']+KEY).target.sum().unstack(KEY).reindex(index=dates,columns=pairs).fillna(0)
# Zeros denote no recorded qualifying transaction on dates present in the network ledger;
# not proven no latent demand, no lost sales correction or stockout assumptions.
Y=daily.to_numpy(float)
products=pairs.get_level_values(0).unique(); stores=pairs.get_level_values(1).unique()
P=len(products); S=len(stores)
assert list(pairs)==[(p,st) for p in products for st in stores]
def rates(origin):
 history=Y[dates<=origin]
 result={f'local_{w}w':history[-7*w:].mean(axis=0) for w in [4,8,13,26,52]}
 # Structured shrinkage: recent product velocity times smoothed store share.
 for w in [8,13,26]:
  recent=history[-7*w:].reshape(-1,P,S)
  long=history[-364:].reshape(-1,P,S).sum(axis=0)
  store_share=(long.sum(axis=0)+1)/(long.sum()+S)
  share=(long+30*store_share)/(long.sum(axis=1,keepdims=True)+30)
  result[f'pooled_{w}w']=(recent.sum(axis=(0,2))[:,None]/len(recent)*share).ravel()
 # Historical month effect only from earlier calendar years, smoothed toward no effect.
 prior=(dates<=origin)&(dates.year<origin.year)
 hist=Y[prior].sum(axis=1)
 hd=dates[prior]
 month=(origin+pd.Timedelta(days=4)).month
 same=hd.month==month
 factor=(hist[same].sum()+60*hist.mean())/((same.sum()+60)*hist.mean()) if len(hist) else 1
 result['pooled_13w_seasonal']=result['pooled_13w']*factor
 return result
lead=policy.set_index(KEY).reindex(pairs).Supplier_Lead_Time_Days.to_numpy()
horizon=lead+7
origins=pd.date_range('2025-01-05','2025-11-16',freq='W-SUN')
records=[]; residuals=[]
for origin in origins:
 r=rates(origin)
 future=Y[(dates>origin)&(dates<=origin+pd.Timedelta(days=int(horizon.max())))]
 actual7=future[:7].sum(axis=0)
 actualH=np.array([future[:h,j].sum() for j,h in enumerate(horizon)])
 for name,rate in r.items():
  for label,actual,pred in [('week',actual7,rate*7),('protection',actualH,rate*horizon)]:
   error=pred-actual
   records.append({'origin':str(origin.date()),'phase':'selection' if origin<pd.Timestamp('2025-09-01') else 'evaluation','model':name,'horizon':label,'mae':np.abs(error).mean(),'rmse':np.sqrt((error**2).mean()),'bias':error.mean(),'actual_units':actual.sum(),'forecast_units':pred.sum()})
  residuals.append((origin,name,actualH-rate*horizon))
metrics=pd.DataFrame(records)
metrics.to_csv(OUT/'model_evaluation.csv',index=False)
selection=metrics.query("phase=='selection' and horizon=='protection'").groupby('model').mae.mean().sort_values()
chosen=selection.index[0]
evaluation=metrics.query("phase=='evaluation'").groupby(['horizon','model'])[['mae','rmse','bias']].mean()
print('SELECTION',selection.to_string());print('EVALUATION',evaluation.to_string());print('CHOSEN',chosen)
# As-of operational joins, no historical operational policy performance claimed.
assert not policy.duplicated(KEY).any() and not stock.duplicated(KEY).any()
assert not inbound.PO_Line_ID.duplicated().any()
assert policy.Quantity_Unit.eq('product_unit').all() and stock.Quantity_Unit.eq('product_unit').all() and inbound.Quantity_Unit.eq('product_unit').all()
assert stock.Open_Order_Ledger_Complete.all()
for d,cols in [(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']),(stock,['Usable_On_Hand_Qty','On_Order_Qty']),(inbound,['Incoming_Qty'])]:
 for c in cols:assert d[c].ge(0).all() and d[c].mod(1).eq(0).all()
assert set(pd.MultiIndex.from_frame(inbound[KEY])).issubset(set(pairs))
q=policy.set_index(KEY).reindex(pairs).join(stock.set_index(KEY).drop(columns=['Quantity_Unit','Provenance']),validate='one_to_one')
incoming=inbound.groupby(KEY).Incoming_Qty.sum().reindex(pairs,fill_value=0)
assert (incoming==q.On_Order_Qty).all()
assert (pd.to_datetime(inbound.Order_Date)<=pd.Timestamp('2025-11-30')).all()
assert (pd.to_datetime(inbound.Expected_Arrival_Date)>pd.Timestamp('2025-11-30')).all()
assert (pd.to_datetime(inbound.Expected_Arrival_Date)<=pd.Timestamp('2025-12-07')).all()
rate=rates(pd.Timestamp('2025-11-30'))[chosen]
q['Forecast_Daily_Units']=rate
q['Protection_Days']=q.Supplier_Lead_Time_Days+q.Review_Period_Days
q['Forecast_Protection_Units']=rate*q.Protection_Days
q['Incoming_In_Protection_Units']=incoming
def order(demand):
 gap=np.maximum(np.asarray(demand)+q.Safety_Stock_Qty.to_numpy()-q.Usable_On_Hand_Qty.to_numpy()-incoming.to_numpy(),0)
 return np.where(gap>0,np.ceil(np.maximum(gap,q.Minimum_Order_Qty.to_numpy())/q.Order_Multiple_Qty.to_numpy())*q.Order_Multiple_Qty.to_numpy(),0).astype(int)
q['OrderQty']=order(q.Forecast_Protection_Units)
q['OrderQty_Lower_Sales_Scenario']=order(q.Forecast_Protection_Units*.75)
q['OrderQty_Higher_Sales_Scenario']=order(q.Forecast_Protection_Units*1.25)
names=s.dropna(subset=['Product_Name']).groupby('Product_ID').Product_Name.agg(lambda x:x.mode().iloc[0])
assert s.groupby('Product_ID').Product_Name.nunique().eq(1).all()
q=q.reset_index();q['Product_Name']=q.Product_ID.map(names)
# Project stock each day using due dates; identify a potential shortfall before normal new supply.
short=[]
for row in q.itertuples():
 bal=row.Usable_On_Hand_Qty
 earliest=None
 lines=inbound[(inbound.Product_ID==row.Product_ID)&(inbound.Store_ID==row.Store_ID)]
 for day in range(1,row.Supplier_Lead_Time_Days):
  dt=pd.Timestamp('2025-11-30')+pd.Timedelta(days=day)
  bal+=lines.loc[pd.to_datetime(lines.Expected_Arrival_Date)==dt,'Incoming_Qty'].sum()
  bal-=row.Forecast_Daily_Units
  if bal<0 and earliest is None:earliest=str(dt.date())
 short.append(earliest or '')
q['Potential_Shortfall_Before_New_Delivery']=short
q['Order_Date']='2025-11-30';q['Planning_Week_Start']='2025-12-01';q['Quantity_Unit']='product_unit'
cols=['Product_ID','Product_Name','Store_ID','OrderQty','Quantity_Unit','Planning_Week_Start','Usable_On_Hand_Qty','Incoming_In_Protection_Units','Supplier_Lead_Time_Days','Protection_Days','Forecast_Protection_Units','Safety_Stock_Qty','Order_Multiple_Qty','OrderQty_Lower_Sales_Scenario','OrderQty_Higher_Sales_Scenario','Potential_Shortfall_Before_New_Delivery']
q[cols].to_csv(OUT/'restocking.csv',index=False,float_format='%.4f',lineterminator='\n')
check=pd.read_csv(OUT/'restocking.csv',keep_default_na=False)
assert len(check)==336 and not check.duplicated(KEY).any()
assert (check.OrderQty>=0).all() and check.OrderQty.mod(1).eq(0).all()
assert (check.OrderQty%check.Order_Multiple_Qty==0).all()
digest=hashlib.sha256((OUT/'restocking.csv').read_bytes()).hexdigest()
(OUT/'result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest},indent=2)+'\n')
audit.update({'raw_rows':len(raw),'deduplicated_rows':len(s),'exact_duplicates_removed':len(raw)-len(s),'invalid_quantities':int((~s.valid).sum()),'status_counts':s.status.value_counts().to_dict(),'returned_flag_by_status':pd.crosstab(s.status,s.Return_Flag).to_dict(),'date_start':str(dates.min().date()),'date_end':str(dates.max().date()),'network_observed_days':s.date.nunique(),'calendar_days':len(dates),'pair_observed_days_quantiles':s.groupby(KEY).date.nunique().quantile([0,.5,1]).to_dict(),'qualifying_rows':int((fulfilled&s.valid).sum()),'fulfilled_units':int(s.target.sum()),'chosen_model':chosen,'selection_mae':selection.to_dict(),'evaluation':evaluation.reset_index().to_dict(orient='records'),'incoming_match_rows':len(q),'incoming_total':int(incoming.sum()),'orders_positive':int(q.OrderQty.gt(0).sum()),'orders_zero':int(q.OrderQty.eq(0).sum()),'units_ordered':int(q.OrderQty.sum()),'lower_scenario_units':int(q.OrderQty_Lower_Sales_Scenario.sum()),'higher_scenario_units':int(q.OrderQty_Higher_Sales_Scenario.sum()),'scenario_changed_rows':int((q.OrderQty_Lower_Sales_Scenario!=q.OrderQty_Higher_Sales_Scenario).sum()),'potential_early_shortfalls':int(q.Potential_Shortfall_Before_New_Delivery.ne('').sum()),'top_products':q.groupby(['Product_ID','Product_Name']).OrderQty.sum().sort_values(ascending=False).head(8).reset_index().to_dict(orient='records'),'top_stores':q.groupby('Store_ID').OrderQty.sum().sort_values(ascending=False).to_dict(),'runtime_seconds':time.perf_counter()-START,'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'daily_matrix_shape':Y.shape,'daily_matrix_bytes':Y.nbytes,'origins':len(origins),'sha256':digest})
# Distribution of forecast errors; pooled across the same final evaluation origins.
res=np.concatenate([v for o,n,v in residuals if n==chosen and o>=pd.Timestamp('2025-09-01')])
audit['protection_residual_quantiles']={str(k):float(np.quantile(res,k)) for k in [.1,.5,.9,.95]}
# Paired origin-block uncertainty: preserves cross-product dependencies within each week.
rng=np.random.default_rng(2025)
comparison={}
for label in ['week','protection']:
 table=metrics.query("phase=='evaluation' and horizon==@label").pivot(index='origin',columns='model',values='mae')
 a=table[chosen].to_numpy(); b=table['local_13w'].to_numpy()
 indices=rng.integers(0,len(a),(10000,len(a)))
 delta=(b[indices].mean(axis=1)-a[indices].mean(axis=1))/b[indices].mean(axis=1)
 comparison[label]={'relative_mae_reduction':float(1-a.mean()/b.mean()),'origin_bootstrap_95_percent_interval':np.quantile(delta,[.025,.975]).tolist(),'n_origins':len(a)}
audit['baseline_comparison']=comparison
# Status scenarios refit the chosen formula with alternate recorded-quantity targets.
originalY=Y.copy()
status_scenarios={}
for label,mask in [('exclude_any_return',fulfilled & s.Return_Flag.eq('No')),('include_processing',s.status.ne('cancelled'))]:
 alternative=s.assign(alternative=np.where(s.valid & mask,s.Quantity,0)).groupby(['date']+KEY).alternative.sum().unstack(KEY).reindex(index=dates,columns=pairs).fillna(0)
 Y=alternative.to_numpy(float)
 alternative_rate=rates(pd.Timestamp('2025-11-30'))[chosen]
 alt=order(alternative_rate*q.Protection_Days.to_numpy())
 status_scenarios[label]={'ordered_units':int(alt.sum()),'changed_rows':int((alt!=q.OrderQty.to_numpy()).sum()),'historical_units':int(Y.sum())}
Y=originalY
audit['status_scenarios']=status_scenarios
audit['store_date_absent_count']=int(len(dates)*S-s.groupby(['date','Store_ID']).ngroups)
audit['runtime_seconds']=time.perf_counter()-START
(OUT/'audit.json').write_text(json.dumps(audit,indent=2,default=str)+'\n')
print('SUMMARY',json.dumps({k:v for k,v in audit.items() if k in ['orders_positive','orders_zero','units_ordered','lower_scenario_units','higher_scenario_units','potential_early_shortfalls','top_products','runtime_seconds','protection_residual_quantiles']},indent=2))
