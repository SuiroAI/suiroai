"""Reproduce the fixed development experiment and illustrative order calculation.
Run: /opt/anaconda3/bin/python analysis.py
Only released inputs are read. All outputs stay beside this script.
"""
from pathlib import Path
import hashlib, json, time, platform
import numpy as np
import pandas as pd

START=time.perf_counter()
OUT=Path(__file__).resolve().parent
SRC=OUT.parent/'released'
K=['Product_ID','Store_ID']
audit={'sources':{},'assumptions':[
    'Missing pair-days after first record are zero recorded orders only conditional on complete extract. Capture completeness is not proven.',
    'Order statuses are supplied final/current labels; when past statuses changed is unknown. Evaluation is conditional on these supplied labels, not a historical availability replay.',
    'Positive returns remain ordered units; negative quantities are not netted. No unconstrained demand or lost-sales estimate.',
    'Decision is at start of December 1, 2025 with November 30 synthetic operational inputs. No December sales read.',
    'Lead time is calendar days from December 1; receipts available at start of scheduled day; new order arrives December 1 plus lead days.',
    'No automatic quantified service-level safety buffer; supplied safety stocks used. No savings or production-readiness claim.']}
tables=[]
for n in range(1,5):
    p=SRC/f'input-{n}.csv'; d=pd.read_csv(p)
    audit['sources'][p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'rows':len(d),'columns':list(d),'exact_duplicates':int(d.duplicated().sum()),'missing':{c:int(v) for c,v in d.isna().sum().items() if v}}
    tables.append(d)
policy,inbound,stock,raw=tables
assert len(policy)==336 and not policy.duplicated(K).any() and not stock.duplicated(K).any()
keys=pd.MultiIndex.from_frame(policy[K].sort_values(K)); assert len(keys)==336
assert set(map(tuple,stock[K].values))==set(keys)
for d in [policy,inbound,stock]:
    assert (d.Quantity_Unit=='product_unit').all()
    assert set(map(tuple,d[K].values))<=set(keys)
assert stock.Open_Order_Ledger_Complete.all()
assert not inbound.PO_Line_ID.duplicated().any()
for d,cols in [(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']),(inbound,['Incoming_Qty']),(stock,['Usable_On_Hand_Qty','On_Order_Qty'])]:
    assert (d[cols]>=0).all().all() and (d[cols]%1==0).all().all()
assert (policy.Review_Period_Days==7).all() and (policy.Order_Multiple_Qty>0).all()
assert (stock.Snapshot_Date=='2025-11-30').all() and (policy.Effective_Date=='2025-11-30').all()
for c in ['Order_Date','Expected_Arrival_Date']: inbound[c]=pd.to_datetime(inbound[c])
assert (inbound.Order_Date<=pd.Timestamp('2025-11-30')).all()
assert (inbound.Expected_Arrival_Date>=pd.Timestamp('2025-12-01')).all()
assert (inbound.Expected_Arrival_Date>=inbound.Order_Date).all()
received=inbound.groupby(K).Incoming_Qty.sum().reindex(keys,fill_value=0)
st=stock.set_index(K).reindex(keys); pol=policy.set_index(K).reindex(keys)
assert np.array_equal(received.values,st.On_Order_Qty.values)
audit['operations']={'synthetic':all((d.Provenance=='synthetic').all() for d in [policy,inbound,stock]),'ledger_matches_all_keys':True,'incoming_units':int(received.sum()),'on_hand_units':int(st.Usable_On_Hand_Qty.sum()),'lead_range':[int(pol.Supplier_Lead_Time_Days.min()),int(pol.Supplier_Lead_Time_Days.max())]}
s=raw.drop_duplicates().copy()
s['status']=s.Order_Status.str.strip().str.lower().replace({'canceled':'cancelled'})
s['date']=pd.to_datetime(s.Order_Date,errors='coerce')
assert s.date.notna().all() and s.Quantity.notna().all() and (s.Quantity%1==0).all()
assert s.date.max()==pd.Timestamp('2025-11-30')
assert set(map(tuple,s[K].values))==set(keys)
assert s.status.isin(['completed','shipped','returned','processing','cancelled']).all()
audit['sales']={'rows_after_exact_dedup':len(s),'duplicated_transaction_ids_after_dedup':int(s.Transaction_ID.duplicated().sum()),'duplicated_order_ids_after_dedup':int(s.Order_ID.duplicated().sum()),'status_counts':s.status.value_counts().to_dict(),'nonpositive_quantity_rows':int((s.Quantity<=0).sum()),'quantity_range':[int(s.Quantity.min()),int(s.Quantity.max())],'date_min':str(s.date.min().date()),'date_max':str(s.date.max().date()),'status_return_counts':s.groupby(['status','Return_Flag']).size().to_dict().__str__()}
assert not s.Transaction_ID.duplicated().any(), 'Conflicting transaction IDs need review'
eligible=s[(s.Quantity>0)&(s.status!='cancelled')].copy()
audit['sales'].update({'target_rows':len(eligible),'target_units':int(eligible.Quantity.sum()),'positive_cancelled_units_excluded':int(s.loc[(s.Quantity>0)&(s.status=='cancelled'),'Quantity'].sum()),'positive_return_flag_units_included':int(eligible.loc[eligible.Return_Flag.str.lower()=='yes','Quantity'].sum())})
names={}; name_details={}
for prod,g in s.groupby('Product_ID'):
    counts=g.Product_Name.dropna().str.strip().value_counts()
    normalized=g.Product_Name.dropna().str.strip().str.casefold().value_counts()
    name_details[prod]={'variants':counts.to_dict(),'normalized_variants':len(normalized)}
    names[prod]=counts.index[0] if len(normalized)==1 else ''
audit['names']=name_details
dates=pd.date_range(s.date.min(),pd.Timestamp('2025-11-30'))
panel=eligible.groupby(['date']+K).Quantity.sum().unstack(K).reindex(index=dates,columns=keys,fill_value=0).fillna(0)
first=s.groupby(K).date.min().reindex(keys)
for j,f in enumerate(first): panel.iloc[panel.index<f,j]=np.nan
obs=s.groupby(['date']+K).size().unstack(K).reindex(index=dates,columns=keys).notna()
audit['coverage']={'calendar_days':len(dates),'network_days_without_any_rows':int(len(dates.difference(s.date.unique()))),'pair_days_since_first':int(panel.notna().sum().sum()),'pair_days_without_rows_since_first':int(((~obs)&panel.notna()).sum().sum()),'latest_first_appearance':str(first.max().date()),'proof_of_complete_capture':False}
network=panel.sum(axis=1)
def mean_rate(origin,days):
    return panel.loc[(panel.index>=origin-pd.Timedelta(days=days))&(panel.index<origin)].mean().to_numpy()
def forecasts(origin,horizon=7):
    local={f'local_{days}':mean_rate(origin,days) for days in [28,91,182,364]}
    hist=panel.loc[(panel.index>=origin-pd.Timedelta(days=364))&(panel.index<origin)]
    totals=hist.sum(); total=totals.sum()
    prod=totals.groupby(level=0).sum()/total; store=totals.groupby(level=1).sum()/total
    net91=network.loc[(network.index>=origin-pd.Timedelta(days=91))&(network.index<origin)].mean()
    shared=.5*local['local_364']+.5*net91*np.array([prod[p]*store[t] for p,t in keys])
    completed=network.loc[network.index.year<origin.year]
    monthly=completed.groupby(completed.index.month).mean().reindex(range(1,13))
    assert monthly.notna().all()
    factor=monthly/monthly.mean()
    pastdates=pd.date_range(origin-pd.Timedelta(days=91),origin-pd.Timedelta(days=1))
    denom=np.mean([factor[d.month] for d in pastdates])
    futuredates=pd.date_range(origin,periods=horizon)
    season=np.array([factor[d.month]/denom for d in futuredates])
    daily={k:np.tile(v,(horizon,1)) for k,v in local.items()}
    daily['shared']=np.tile(shared,(horizon,1)); daily['seasonal']=season[:,None]*shared[None,:]
    return daily

periods={'initial':pd.date_range('2025-06-30','2025-09-15',freq='W-MON'),'later':pd.date_range('2025-10-06','2025-11-24',freq='W-MON')}
rows=[]; horizon_rows=[]
for period,origins in periods.items():
    for origin in origins:
        actual=panel.loc[origin:origin+pd.Timedelta(days=6)].sum().to_numpy()
        assert panel.loc[origin:origin+pd.Timedelta(days=6)].notna().all().all()
        for model,daily in forecasts(origin).items():
            pred=daily.sum(axis=0)
            for j,(product,store) in enumerate(keys):
                rows.append((period,str(origin.date()),model,product,store,actual[j],pred[j],pred[j]-actual[j]))
        # Policy horizons are diagnostics only; today's synthetic lead times are not historical facts.
        for model,daily in forecasts(origin,14).items():
            for j,key in enumerate(keys):
                h=int(pol.iloc[j].Supplier_Lead_Time_Days+7)
                end=origin+pd.Timedelta(days=h-1)
                if end<=panel.index.max():
                    a=panel.loc[origin:end].iloc[:,j].sum(); pred=daily[:h,j].sum()
                    horizon_rows.append((period,str(origin.date()),model,*key,h,a,pred,pred-a))
comp=pd.DataFrame(rows,columns=['period','origin','model',*K,'actual_units','forecast_units','error'])
comp.to_csv(OUT/'comparison_rows.csv',index=False)
def score(d):
    return pd.Series({'MAE':d.error.abs().mean(),'RMSE':np.sqrt((d.error**2).mean()),'bias':d.error.mean(),'n':len(d)})
scores=comp.groupby(['period','model']).apply(score,include_groups=False).reset_index()
scores.to_csv(OUT/'model_scores.csv',index=False)
origin_scores=comp.groupby(['period','origin','model']).apply(score,include_groups=False).reset_index()
origin_scores.to_csv(OUT/'origin_scores.csv',index=False)
hd=pd.DataFrame(horizon_rows,columns=['period','origin','model',*K,'horizon_days','actual_units','forecast_units','error'])
hd.to_csv(OUT/'horizon_comparison_rows.csv',index=False)
hd.groupby(['period','model']).apply(score,include_groups=False).to_csv(OUT/'horizon_scores.csv')
initial=scores[scores.period=='initial'].sort_values(['MAE','model'])
candidate=initial.iloc[0].model
improvements={period:float(1-scores.loc[(scores.period==period)&(scores.model==candidate),'MAE'].iloc[0]/scores.loc[(scores.period==period)&(scores.model=='local_91'),'MAE'].iloc[0]) for period in periods}
selected=candidate if candidate!='local_91' and min(improvements.values())>=.05 else 'local_91'
audit['selection']={'initial_best':candidate,'relative_MAE_improvements':improvements,'selected':selected,'stability_threshold':.05,'scores':scores.to_dict('records'),'development_only':True}

origin=pd.Timestamp('2025-12-01'); horizon=14
daily=forecasts(origin,horizon)[selected]
trailing=panel.loc[origin-pd.Timedelta(days=91):origin-pd.Timedelta(days=1)]
observed=obs.loc[trailing.index].sum().to_numpy()
observed_rate=np.divide(trailing.sum().to_numpy(),observed,out=np.full(len(keys),np.nan),where=observed>0)
base_rate=mean_rate(origin,91)
audit['missingness_sensitivity']={'method':'Alternative baseline using only days with any recorded row for that key, counting eligible zero on cancellation-only days; not a validated correction or bound. Excludes keys with no observed days; those remain unknown.','network_weekly_baseline_units':float(base_rate.sum()*7),'observed_days_only_weekly_units_known_keys':float(np.nansum(observed_rate)*7),'rate_ratio_on_known_keys':float(np.nansum(observed_rate)/base_rate[observed>0].sum()),'unknown_keys':int((observed==0).sum()),'observed_days_per_key_91_min':int(observed.min()),'max':int(observed.max())}

def round_order(gap,j):
    if gap<=0: return 0
    p=pol.iloc[j]; return int(np.ceil(max(gap,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty)
orders=[]
for j,(product,store) in enumerate(keys):
    p=pol.iloc[j]; lead=int(p.Supplier_Lead_Time_Days); h=lead+7
    onhand=int(st.iloc[j].Usable_On_Hand_Qty)
    receipts=inbound[(inbound.Product_ID==product)&(inbound.Store_ID==store)]
    due=int(receipts.loc[receipts.Expected_Arrival_Date<origin+pd.Timedelta(days=h),'Incoming_Qty'].sum())
    target=float(daily[:h,j].sum()+p.Safety_Stock_Qty)
    qty=round_order(target-onhand-due,j)
    balance=onhand; minimum=balance
    for day in range(lead):
        date=origin+pd.Timedelta(days=day)
        balance+=receipts.loc[receipts.Expected_Arrival_Date==date,'Incoming_Qty'].sum()
        balance-=daily[day,j]; minimum=min(minimum,balance)
    sensitivity_qty=round_order(observed_rate[j]*h+p.Safety_Stock_Qty-onhand-due,j) if observed[j]>0 else None
    orders.append((product,names[product],store,qty,'product_unit','2025-12-01','2025-12-07',selected,onhand,due,lead,round(float(daily[:7,j].sum()),3),round(target,3),round(max(0,-minimum),3),sensitivity_qty,'synthetic_inputs_illustrative'))
output=pd.DataFrame(orders,columns=['Product_ID','Product_Name','Store_ID','OrderQty','Quantity_Unit','Week_Start','Week_End','Forecast_Method','Usable_Stock_Units','Incoming_Within_Coverage_Units','Supplier_Lead_Days','Expected_Seven_Day_Units','Target_With_Safety_Units','Expected_PreArrival_Shortfall_Units','Observed_Days_Only_Baseline_OrderQty','Scenario'])
output=output.sort_values(['OrderQty','Expected_PreArrival_Shortfall_Units'],ascending=False,kind='stable')
output.to_csv(OUT/'decision_sensitivity.csv',index=False)
output.drop(columns=['Forecast_Method','Observed_Days_Only_Baseline_OrderQty','Scenario']).to_csv(OUT/'restocking.csv',index=False)
check=pd.read_csv(OUT/'restocking.csv',keep_default_na=False)
assert len(check)==336 and not check.duplicated(K).any() and set(map(tuple,check[K].values))==set(keys)
assert (check.OrderQty>=0).all() and (check.OrderQty%1==0).all()
for _,r in check.iterrows():
    p=pol.loc[(r.Product_ID,r.Store_ID)]
    assert r.OrderQty%p.Order_Multiple_Qty==0
    assert r.OrderQty==0 or r.OrderQty>=p.Minimum_Order_Qty
    j=keys.get_loc((r.Product_ID,r.Store_ID)); h=int(p.Supplier_Lead_Time_Days+7)
    # Independent direct 91-day source aggregation when baseline is retained.
    if selected=='local_91':
        direct=eligible[(eligible.Product_ID==r.Product_ID)&(eligible.Store_ID==r.Store_ID)&(eligible.date>=origin-pd.Timedelta(days=91))].Quantity.sum()/91
        expected=round_order(direct*h+p.Safety_Stock_Qty-r.Usable_Stock_Units-r.Incoming_Within_Coverage_Units,j)
        assert expected==r.OrderQty
audit['orders']={'units':int(check.OrderQty.sum()),'positive_keys':int((check.OrderQty>0).sum()),'zero_keys':int((check.OrderQty==0).sum()),'prearrival_shortfall_keys':int((check.Expected_PreArrival_Shortfall_Units>0).sum()),'observed_days_only_baseline_order_units_known_keys':int(output.Observed_Days_Only_Baseline_OrderQty.sum()),'name_blanks':int((check.Product_Name=='').sum()),'by_store':check.groupby('Store_ID').OrderQty.sum().to_dict(),'top_rows':check.head(8).to_dict('records')}
audit['workload']={'runtime_seconds':time.perf_counter()-START,'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'panel_shape':list(panel.shape),'comparison_rows':len(comp),'paid_model_calls':0,'dependencies':'Python standard library, pandas, numpy. No network, LLM, GPU or external model service needed.','build_cost':'AI usage and applicable billing price not supplied; cannot estimate AI-assisted analysis/build cost.'}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2,default=str)+'\n')
digest=hashlib.sha256((OUT/'restocking.csv').read_bytes()).hexdigest()
(OUT/'result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest},indent=2)+'\n')
print(scores.to_string(index=False))
print(json.dumps({k:audit[k] for k in ['selection','coverage','missingness_sensitivity','orders','workload']},indent=2,default=str))
