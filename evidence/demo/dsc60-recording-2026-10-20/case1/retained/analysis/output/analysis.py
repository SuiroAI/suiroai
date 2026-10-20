"""Bounded CPU-only development forecasting and illustrative restocking.
Run: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis.py
Requires only approved released CSVs; never accesses reserved outcomes.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import time, json, hashlib, resource, sys, platform
from pathlib import Path
START=time.perf_counter()
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

assert Path('evaluation_plan.json').exists() and Path('task_refinement.json').exists()
PLAN_HASH=hashlib.sha256(Path('evaluation_plan.json').read_bytes()).hexdigest()
KEYS=['Product_ID','Store_ID']
METHODS=['recent_91d','sba_croston','pooled_ridge']
TIMES=[]
def rss():
    x=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return x/(1024**2) if sys.platform=='darwin' else x/1024
def phase(name,t):
    TIMES.append({'phase':name,'wall_seconds':time.perf_counter()-t,'process_peak_RSS_MiB_so_far':rss()})
def save(name,obj): Path(name).write_text(json.dumps(obj,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))

t=time.perf_counter()
sales=pd.read_csv('../released/input-4.csv').drop_duplicates()
sales['date']=pd.to_datetime(sales.Order_Date)
assert sales.date.max()==pd.Timestamp('2025-11-30')
assert not sales.Transaction_ID.duplicated().any()
sales['status']=sales.Order_Status.str.strip().str.lower()
policy=pd.read_csv('../released/input-1.csv').sort_values(KEYS).reset_index(drop=True)
stock=pd.read_csv('../released/input-3.csv')
ledger=pd.read_csv('../released/input-2.csv')
dates=pd.date_range(sales.date.min(),sales.date.max())
assert len(dates.difference(sales.date))==0
# Population from sales only, no outcome-period activity filter or stock-exposure claim.
pairs=pd.MultiIndex.from_frame(sales[KEYS].drop_duplicates().sort_values(KEYS))
assert pairs.equals(pd.MultiIndex.from_frame(policy[KEYS]))
first=sales.groupby(KEYS).date.min().reindex(pairs)
firstidx=np.array([(d-dates[0]).days for d in first])
def panel(mask):
    grouped=sales.loc[mask].groupby(['date']+KEYS).Quantity.sum()
    # These zeros count absent RECORDED units on globally observed dates, not zero latent demand.
    frame=grouped.unstack(KEYS).reindex(index=dates,columns=pairs).fillna(0)
    a=frame.to_numpy(dtype=float)
    return a,np.vstack([np.zeros((1,len(pairs))),a.cumsum(axis=0)])
primary=sales.Quantity.gt(0)&sales.status.isin(['completed','shipped','returned'])
y,cs=panel(primary)
origins=[dates.get_loc(pd.Timestamp(x)) for x in json.loads(Path('evaluation_plan.json').read_text())['forecast_origins']]
assert all((o-firstidx>=364).all() for o in origins)
phase('load_and_prepare',t)

def rates(c,t,window):
    lo=np.maximum(t-window+1,firstidx)
    return (c[t+1]-c[lo,np.arange(len(pairs))])/np.maximum(1,t-lo+1)

def croston(a):
    size=np.zeros(a.shape[1]); gap=np.ones(a.shape[1]); last=firstidx.copy(); initialized=np.zeros(a.shape[1],bool)
    out=np.zeros_like(a)
    for t,z in enumerate(a):
        new=(z>0)&~initialized
        size[new]=z[new];gap[new]=np.maximum(1,t-firstidx[new]+1)
        update=(z>0)&initialized
        size[update]=.1*z[update]+.9*size[update]
        gap[update]=.1*(t-last[update])+.9*gap[update]
        last[z>0]=t; initialized|=new
        out[t]=.95*size/gap
    return out

def features(c,t,h):
    # All feature source dates strictly before prediction target, including seasonal windows.
    rate=[rates(c,t,w) for w in [7,28,91,364]]
    middle=t-364
    lo=max(0,middle-13);hi=middle+15
    seasonal=(c[hi]-c[lo])/(hi-lo)
    prior=np.array([d.year<dates[t].year for d in dates[:t+1]])
    daily=np.diff(c[:t+2],axis=0).sum(axis=1)
    prior_mean=daily[prior].mean() if prior.any() else 1
    factors=[]
    for day in pd.date_range(dates[t]+pd.Timedelta(days=1),periods=h):
        m=prior & (dates[:t+1].month==day.month)
        factors.append(daily[m].mean()/prior_mean if m.any() and prior_mean>0 else 1)
    return np.column_stack(rate+[seasonal,rate[-1]*np.mean(factors)])*h

def fit_predict(c,a,sba,t,h):
    out={'recent_91d':rates(c,t,91)*h,'sba_croston':sba[t]*h}
    tick=time.perf_counter()
    train_origins=[dates.get_loc(d) for d in pd.date_range('2023-01-01',dates[t]-pd.Timedelta(days=h),freq='W-SUN') if d>=dates[t]-pd.Timedelta(days=730)]
    xx=[]; yy=[]
    for u in train_origins:
        eligible=(u-firstidx>=364)
        xx.append(features(c,u,h)[eligible]); yy.append((c[u+h+1]-c[u+1])[eligible])
    x=np.vstack(xx);z=np.concatenate(yy)
    scaler=StandardScaler(); transformed=scaler.fit_transform(x)
    model=Ridge(alpha=10).fit(transformed,z)
    phase('ridge_prepare_and_fit',tick)
    tick=time.perf_counter()
    out['pooled_ridge']=np.maximum(0,model.predict(scaler.transform(features(c,t,h))))
    phase('all_ridge_prediction_feature_preparation',tick)
    return out,{'training_rows':len(z),'feature_count':x.shape[1],'retained_training_arrays_bytes':int(x.nbytes+z.nbytes+transformed.nbytes),'model_coefficients':model.coef_.tolist(),'intercept':float(model.intercept_)}

t=time.perf_counter();sba=croston(y);phase('croston_fit_all_dates',t)
records=[]; fits=[]
for o in origins:
    for h in range(7,15):
        if o+h>=len(dates): continue
        predictions,fit=fit_predict(cs,y,sba,o,h)
        fits.append({'origin':str(dates[o].date()),'horizon':h,**fit})
        actual=cs[o+h+1]-cs[o+1]
        for method,pred in predictions.items():
            for j,(prod,store) in enumerate(pairs):
                records.append((str(dates[o].date()),h,method,prod,store,float(actual[j]),float(pred[j]),float(rates(cs,o,364)[j])))
res=pd.DataFrame(records,columns=['origin','horizon','method']+KEYS+['actual','prediction','prior_daily_rate'])
res['error']=res.prediction-res.actual
res.to_csv('development_predictions.csv',index=False)
def metrics(d):
    return {'MAE':float(d.error.abs().mean()),'RMSE':float(np.sqrt((d.error**2).mean())),'WAPE':float(d.error.abs().sum()/d.actual.sum()) if d.actual.sum() else None,'bias_units':float(d.error.mean()),'actual_units':float(d.actual.sum()),'prediction_units':float(d.prediction.sum()),'n':len(d)}
primary_scores={m:metrics(res[(res.method==m)&(res.horizon==7)]) for m in METHODS}
winner=min(METHODS,key=lambda m:(round(primary_scores[m]['MAE'],10),METHODS.index(m)))
summary={'plan_sha256':PLAN_HASH,'evaluation_type':'development only; no independent validation','selected':winner,'primary':primary_scores,'by_horizon':{},'coverage':{},'by_origin':{},'sparsity':{},'by_month':{}}
for h in range(8,15): summary['by_horizon'][str(h)]={m:metrics(res[(res.method==m)&(res.horizon==h)]) for m in METHODS}
cov=res.merge(policy[KEYS+['Supplier_Lead_Time_Days']],on=KEYS)
cov=cov[cov.horizon.eq(cov.Supplier_Lead_Time_Days+7)&cov.origin.ne('2025-11-23')]
summary['coverage']={m:metrics(cov[cov.method==m]) for m in METHODS}
for o in sorted(res.origin.unique()): summary['by_origin'][o]={m:metrics(res[(res.method==m)&(res.horizon==7)&(res.origin==o)]) for m in METHODS}
for month in ['2025-10','2025-11']:
    summary['by_month'][month]={m:metrics(res[(res.method==m)&(res.horizon==7)&res.origin.str.startswith(month)]) for m in METHODS}
for seg,mask in [('less_than_one_unit_per_week',res.prior_daily_rate<1/7),('at_least_one_unit_per_week',res.prior_daily_rate>=1/7)]:
    summary['sparsity'][seg]={m:metrics(res[(res.method==m)&(res.horizon==7)&mask]) for m in METHODS}
week=res[res.horizon.eq(7)].pivot(index=['origin']+KEYS,columns='method',values='error')
delta=(week[winner].abs()-week.recent_91d.abs()).groupby('origin').mean().to_numpy()
rng=np.random.default_rng(42)
boot=rng.choice(delta,(2000,len(delta)),replace=True).mean(axis=1)
summary['origin_block_bootstrap_MAE_difference_95_percentile_range']=np.quantile(boot,[.025,.975]).tolist()
summary['origins_better_than_baseline']=int((delta<0).sum())
summary['relative_MAE_reduction']=1-primary_scores[winner]['MAE']/primary_scores['recent_91d']['MAE']
pair_err=week.abs().groupby(KEYS).mean()
summary['pairs_better_than_baseline']=int((pair_err[winner]<pair_err.recent_91d).sum())
summary['recorded_zero_daily_fraction_after_first_observation']=float(sum((y[firstidx[j]:,j]==0).sum() for j in range(len(pairs)))/sum(len(dates)-firstidx))
summary['baseline_window_sensitivity']={}
for window in [28,182]:
    errors=[];actuals=[]
    for o in origins:
        actual=cs[o+8]-cs[o+1];errors.extend(rates(cs,o,window)*7-actual);actuals.extend(actual)
    summary['baseline_window_sensitivity'][str(window)]=metrics(pd.DataFrame({'error':errors,'actual':actuals,'prediction':np.array(errors)+actuals}))
save('development_results.json',summary)
save('fit_details.json',fits)

# Fixed-method target sensitivity: the original winner is retained, with no search.
sens={}
for name,mask in [('include_processing',sales.Quantity.gt(0)&~sales.status.eq('cancelled')),('exclude_returned',sales.Quantity.gt(0)&sales.status.isin(['completed','shipped'])&sales.Return_Flag.eq('No'))]:
    a,c=panel(mask); sb=croston(a);rows=[]
    for o in origins:
        preds,_=fit_predict(c,a,sb,o,7);actual=c[o+8]-c[o+1]
        for m,p in preds.items():
            rows.extend((m,float(q),float(r)) for q,r in zip(actual,p))
    df=pd.DataFrame(rows,columns=['method','actual','prediction']);df['error']=df.prediction-df.actual
    sens[name]={m:metrics(df[df.method.eq(m)]) for m in METHODS}
save('target_sensitivity.json',sens)

t=time.perf_counter()
final={};finalfits=[]
for h in range(7,15):
    preds,fit=fit_predict(cs,y,sba,len(dates)-1,h);final[h]=preds;finalfits.append({'horizon':h,**fit})
phase('final_fit_and_inference_all_candidates',t)
save('final_fit_details.json',finalfits)
join=policy.merge(stock,on=KEYS,validate='one_to_one',suffixes=('','_stock'))
names=sales.dropna(subset=['Product_Name']).groupby('Product_ID').Product_Name.first().to_dict()
lead=join.Supplier_Lead_Time_Days.to_numpy();horizon=lead+7
forecast=np.array([final[int(h)][winner][j] for j,h in enumerate(horizon)])
baseline_forecast=np.array([final[int(h)]['recent_91d'][j] for j,h in enumerate(horizon)])
due=pd.to_datetime(ledger.Expected_Arrival_Date)
orders=[]; uncertainty=[]
for j,row in join.iterrows():
    h=int(horizon[j]);lines=ledger[ledger.Product_ID.eq(row.Product_ID)&ledger.Store_ID.eq(row.Store_ID)]
    arrivals=pd.to_datetime(lines.Expected_Arrival_Date)
    assert (pd.to_datetime(lines.Order_Date)<=pd.Timestamp('2025-11-30')).all()
    incoming=int(lines.loc[arrivals.le(pd.Timestamp('2025-11-30')+pd.Timedelta(days=h)),'Incoming_Qty'].sum())
    assert int(lines.Incoming_Qty.sum())==int(row.On_Order_Qty)
    def qty(f):
        need=max(0,f+row.Safety_Stock_Qty-row.Usable_On_Hand_Qty-incoming)
        return int(np.ceil(max(need,row.Minimum_Order_Qty)/row.Order_Multiple_Qty)*row.Order_Multiple_Qty) if need>0 else 0
    residual=(res[(res.method==winner)&res.horizon.eq(h)].actual-res[(res.method==winner)&res.horizon.eq(h)].prediction)
    low,high=np.maximum(0,forecast[j]+np.quantile(residual,[.1,.9]))
    # Pre-arrival check excludes arrival day, assumes due deliveries available at start of due date.
    shortage=False
    daily=final[7][winner][j]/7
    for day in range(1,int(lead[j])):
        due_units=lines.loc[arrivals.le(pd.Timestamp('2025-11-30')+pd.Timedelta(days=day)),'Incoming_Qty'].sum()
        if daily*day>row.Usable_On_Hand_Qty+due_units: shortage=True
    orders.append({'Product_ID':row.Product_ID,'Product_Name':names.get(row.Product_ID,''),'Store_ID':row.Store_ID,'OrderQty':qty(forecast[j]),'Quantity_Unit':'product_unit','Illustrative_Synthetic_Stock':True,'Forecast_Next_7_Days':round(float(final[7][winner][j]),4),'Coverage_Days':h,'Forecast_Coverage_Units':round(float(forecast[j]),4),'Usable_Stock':int(row.Usable_On_Hand_Qty),'Incoming_Within_Coverage':incoming,'Safety_Stock':int(row.Safety_Stock_Qty),'Order_Multiple':int(row.Order_Multiple_Qty),'Baseline_OrderQty':qty(baseline_forecast[j]),'Empirical_Low_OrderQty':qty(low),'Empirical_High_OrderQty':qty(high),'Expected_Gap_Before_New_Order_Arrives':shortage})
out=pd.DataFrame(orders).sort_values(['OrderQty','Product_ID','Store_ID'],ascending=[False,True,True])
out.to_csv('restocking.csv',index=False,lineterminator='\n')
assert len(out)==336 and not out.duplicated(KEYS).any()
assert out.OrderQty.ge(0).all() and (out.OrderQty%out.Order_Multiple==0).all()
assert out.OrderQty.eq(out.OrderQty.astype(int)).all()
assert pd.read_csv('restocking.csv').equals(out.reset_index(drop=True))
sha=hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
save('result.json',{'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha})
summary_order={'total_units':int(out.OrderQty.sum()),'positive_orders':int(out.OrderQty.gt(0).sum()),'zero_orders':int(out.OrderQty.eq(0).sum()),'expected_prearrival_gaps':int(out.Expected_Gap_Before_New_Order_Arrives.sum()),'baseline_total_units':int(out.Baseline_OrderQty.sum()),'changed_orders_vs_baseline':int(out.OrderQty.ne(out.Baseline_OrderQty).sum()),'empirical_low_total_units':int(out.Empirical_Low_OrderQty.sum()),'empirical_high_total_units':int(out.Empirical_High_OrderQty.sum()),'top_orders':out.head(10).to_dict('records'),'next_week_forecast_total':float(out.Forecast_Next_7_Days.sum()),'sha256':sha}
save('order_summary.json',summary_order)
phase('complete_pipeline',START)
save('compute_measurements.json',{'phases':TIMES,'peak_RSS_MiB':rss(),'local_calculation_seconds':time.perf_counter()-START,'dependencies':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scikit_learn':sklearn.__version__},'platform':platform.platform(),'CPU_threads_requested':1,'data_rows_loaded':len(sales)+42,'daily_panel_shape':list(y.shape),'retained_primary_arrays_bytes':int(y.nbytes+cs.nbytes+sba.nbytes),'measurement_limits':'Process high-water RSS, including imports/CSV preparation, fitting, inference, sensitivities and result retention; phase RSS is cumulative, not separate phase allocation. One host/run, no 8GB-host test, no host RAM assumption. Workload at supplied scale only. Native library thread limits requested.','routine_model_API_calls':0})
print(json.dumps({'selected':winner,'scores':primary_scores,'orders':summary_order,'seconds':time.perf_counter()-START,'peak_RSS_MiB':rss()},indent=2))
