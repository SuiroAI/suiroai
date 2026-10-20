import pandas as pd, numpy as np, json, hashlib, time, platform
from pathlib import Path
START=time.perf_counter()
ROOT=Path(__file__).parent
PLAN=json.loads((ROOT/'evaluation_plan.json').read_text())
K=['Product_ID','Store_ID']; ASOF=pd.Timestamp('2025-11-30')
policy=pd.read_csv(ROOT/'../released/input-1.csv').set_index(K).sort_index()
inventory=pd.read_csv(ROOT/'../released/input-3.csv').set_index(K).reindex(policy.index)
inbound=pd.read_csv(ROOT/'../released/input-2.csv')
raw=pd.read_csv(ROOT/'../released/input-4.csv')
s=raw.drop_duplicates().copy()
assert not s.Transaction_ID.duplicated().any()
s['date']=pd.to_datetime(s.Order_Date);s['status']=s.Order_Status.str.strip().str.lower()
assert s.date.max()==ASOF
assert (pd.to_datetime(inbound.Order_Date)<=ASOF).all()
assert policy.index.is_unique and inventory.index.is_unique
assert (inventory.On_Order_Qty==inbound.groupby(K).Incoming_Qty.sum().reindex(policy.index,fill_value=0)).all()
assert (policy.Quantity_Unit=='product_unit').all() and (inventory.Quantity_Unit=='product_unit').all()
idx=policy.index; dates=pd.date_range(s.date.min(),ASOF)
def target(mode='gross'):
 mask=s.status.isin(['completed','shipped','returned']) & s.Quantity.gt(0)
 if mode=='exclude_returns':mask &= s.Return_Flag.ne('Yes') & s.status.ne('returned')
 if mode=='include_processing':mask=s.status.isin(['completed','shipped','returned','processing']) & s.Quantity.gt(0)
 return s[mask].groupby(['date']+K).Quantity.sum().unstack(K).reindex(index=dates,columns=idx).fillna(0)
y=target(); h=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy()
def forecast(frame, origin, horizons):
 train=frame.loc[:origin]; a=train.tail(84).mean(); b=train.tail(28).mean()
 prod=a.groupby(level=0).sum(); store=a.groupby(level=1).sum(); total=a.sum()
 pooled=np.array([prod[p]*store[t]/total if total else 0 for p,t in idx])
 # Prior-year calendar season factors available at the origin, chain-wide pooling only.
 factors=[]
 for horizon in horizons:
  month=(origin+pd.Timedelta(days=int(horizon)//2+1)).month
  previous=train[train.index.year<origin.year].sum(axis=1)
  annual=[]
  for year in sorted(previous.index.year.unique()):
   end=origin.replace(year=int(year)); trailing=previous.loc[end-pd.Timedelta(days=83):end].mean()
   month_mean=previous[(previous.index.year==year)&(previous.index.month==month)].mean()
   if trailing>0 and pd.notna(month_mean):annual.append(month_mean/trailing)
  factors.append(float(np.clip(np.mean(annual),.5,2)) if annual else 1.)
 return {'mean84':a.to_numpy()*horizons,'mean28':b.to_numpy()*horizons,'pooled84':(.5*a.to_numpy()+.5*pooled)*horizons,'seasonal84':a.to_numpy()*horizons*np.array(factors)}
rows=[]
for origin in map(pd.Timestamp,PLAN['origins']):
 for label,horizon in [('coverage',h),('next_week',np.repeat(7,len(idx)))]:
  actual=np.array([y.iloc[y.index.get_loc(origin)+1:y.index.get_loc(origin)+1+int(n),j].sum() for j,n in enumerate(horizon)])
  for model,pred in forecast(y,origin,horizon).items():
   for j,(p,t) in enumerate(idx): rows.append([str(origin.date()),label,model,p,t,int(horizon[j]),actual[j],pred[j]])
predictions=pd.DataFrame(rows,columns=['origin','horizon','model']+K+['days','actual','forecast'])
predictions['error']=predictions.forecast-predictions.actual
predictions.to_csv(ROOT/'development_predictions.csv',index=False)
def metrics(g):
 return pd.Series({'RMSE':np.sqrt(np.mean(g.error**2)),'MAE':np.mean(abs(g.error)),'Bias':g.error.mean(),'WAPE':abs(g.error).sum()/g.actual.sum(),'n':len(g)})
scores=predictions.groupby(['horizon','model']).apply(metrics,include_groups=False)
scores.to_csv(ROOT/'comparison_results.csv')
predictions.groupby(['horizon','origin','model']).apply(metrics,include_groups=False).to_csv(ROOT/'origin_results.csv')
primary=scores.loc['coverage','RMSE'];eligible=primary[primary<=primary.min()*1.01].index
selected=next(m for m in ['mean84','mean28','pooled84','seasonal84'] if m in eligible)
pred=forecast(y,ASOF,h)[selected]; week=forecast(y,ASOF,np.repeat(7,len(idx)))[selected]
inbound['arrival']=pd.to_datetime(inbound.Expected_Arrival_Date)
due=[];due_lead=[]
for (p,t),n,l in zip(idx,h,policy.Supplier_Lead_Time_Days):
 lines=inbound[(inbound.Product_ID==p)&(inbound.Store_ID==t)]
 due.append(lines.loc[lines.arrival<=ASOF+pd.Timedelta(days=int(n)),'Incoming_Qty'].sum())
 due_lead.append(lines.loc[lines.arrival<=ASOF+pd.Timedelta(days=int(l)),'Incoming_Qty'].sum())
def orders(f):
 gap=np.maximum(0,f+policy.Safety_Stock_Qty.to_numpy()-inventory.Usable_On_Hand_Qty.to_numpy()-due)
 rounded=np.ceil(np.maximum(np.ceil(gap),policy.Minimum_Order_Qty.to_numpy())/policy.Order_Multiple_Qty.to_numpy())*policy.Order_Multiple_Qty.to_numpy()
 return np.where(gap>0,rounded,0).astype(int)
out=policy.reset_index()[K].copy()
names=s.dropna(subset=['Product_Name']).groupby('Product_ID').Product_Name.agg(lambda v:v.iloc[0] if v.nunique()==1 else '')
out.insert(1,'Product_Name',out.Product_ID.map(names));out['OrderQty']=orders(pred);out['Quantity_Unit']='product_unit'
out['Next_Week_Recorded_Units_Estimate']=np.round(week,2);out['Coverage_Days']=h
out['Coverage_Recorded_Units_Estimate']=np.round(pred,2);out['Usable_Stock']=inventory.Usable_On_Hand_Qty.to_numpy()
out['Incoming_By_Coverage_End']=due;out['Safety_Stock']=policy.Safety_Stock_Qty.to_numpy()
out['Order_Multiple']=policy.Order_Multiple_Qty.to_numpy();out['Supplier_Lead_Days']=policy.Supplier_Lead_Time_Days.to_numpy()
leadpred=forecast(y,ASOF,policy.Supplier_Lead_Time_Days.to_numpy())[selected]
out['Expected_Shortfall_Before_New_Order_Arrives']=np.round(np.maximum(0,leadpred-inventory.Usable_On_Hand_Qty.to_numpy()-due_lead),2)
# Daily arrival timing: any cumulative forecast exceeds supply, even when later inbound covers total.
rates=pred/h; early=[]
for j,((p,t),l) in enumerate(zip(idx,policy.Supplier_Lead_Time_Days)):
 lines=inbound[(inbound.Product_ID==p)&(inbound.Store_ID==t)]
 gaps=[rates[j]*d-inventory.Usable_On_Hand_Qty.iloc[j]-lines.loc[lines.arrival<=ASOF+pd.Timedelta(days=d),'Incoming_Qty'].sum() for d in range(1,int(l)+1)]
 early.append(max([0]+gaps))
out['Check_Stock_Before_Delivery']=np.array(early)>0
out['Input_Basis']='synthetic stock, inbound and policy'
out.to_csv(ROOT/'restocking.csv',index=False)
assert out.OrderQty.ge(0).all() and (out.OrderQty%out.Order_Multiple==0).all()
assert len(out)==336 and not out.duplicated(K).any()
res=predictions[(predictions.model==selected)&(predictions.horizon=='coverage')]
q=np.quantile(-res.error,[.1,.5,.9]); uplift=max(0,q[2])
sens={}
for mode in ['exclude_returns','include_processing']:
 f=forecast(target(mode),ASOF,h)[selected];o=orders(f)
 sens[mode]={'order_units':int(o.sum()),'changed_rows':int((o!=out.OrderQty).sum()),'forecast_units':float(f.sum())}
season={}
for year in [2022,2023,2024]:
 chain=y.sum(axis=1);season[year]={m:float(chain[(chain.index.year==year)&(chain.index.month==m)].mean()) for m in [9,10,11,12]}
summary={'selected':selected,'scores':scores.reset_index().to_dict('records'),'order_units':int(out.OrderQty.sum()),'positive_orders':int(out.OrderQty.gt(0).sum()),'zero_orders':int(out.OrderQty.eq(0).sum()),'early_risk_rows':int(out.Check_Stock_Before_Delivery.sum()),'coverage_forecast_units':float(pred.sum()),'next_week_forecast_units':float(week.sum()),'target_sensitivities':sens,'residual_quantiles_actual_minus_forecast':q.tolist(),'illustrative_90pct_residual_uplift_order_units':int(orders(pred+uplift).sum()),'zero_record_window_fraction':float((res.actual==0).mean()),'zero_forecast_coverage_RMSE':float(np.sqrt(np.mean(res.actual**2))),'per_key_positive_days_quantiles':y.gt(0).sum().quantile([0,.25,.5,.75,1]).to_dict(),'seasonal_chain_daily_means':season,'target_units':int(y.sum().sum()),'deduplicated_rows':len(s),'target_transaction_rows':int((s.status.isin(['completed','shipped','returned'])&s.Quantity.gt(0)).sum()),'excluded_nonpositive_rows':int(s.Quantity.le(0).sum()),'runtime_seconds':time.perf_counter()-START,'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__}
(ROOT/'measured_results.json').write_text(json.dumps(summary,indent=2))
sha=hashlib.sha256((ROOT/'restocking.csv').read_bytes()).hexdigest()
(ROOT/'result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha},indent=2))
print(json.dumps(summary,indent=2))
