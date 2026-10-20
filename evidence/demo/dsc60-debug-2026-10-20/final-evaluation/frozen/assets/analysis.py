"""Bounded CPU-only forecasting and illustrative restocking. Requires frozen v1 plans.
Run: env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /opt/anaconda3/bin/python analysis.py
No network, LLM or paid model service calls. No December sales input.
"""
from pathlib import Path
import json, time, resource, sys, threading, hashlib, platform
import numpy as np, pandas as pd, psutil, sklearn
from sklearn.linear_model import PoissonRegressor

ROOT=Path(__file__).resolve().parent; SRC=ROOT.parent/'released'
def save(n,o): (ROOT/n).write_text(json.dumps(o,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
plan=json.loads((ROOT/'evaluation_plan.json').read_text()); refinement=json.loads((ROOT/'task_refinement.json').read_text())
assert plan['version']==1
start=time.perf_counter(); cpu_start=time.process_time(); process=psutil.Process(); peak=[process.memory_info().rss]; stop=threading.Event(); phase='preparation'; phase_peaks={}; timings=[]
def sample():
 while not stop.is_set():
  rss=process.memory_info().rss; peak[0]=max(peak[0],rss); phase_peaks[phase]=max(phase_peaks.get(phase,0),rss); stop.wait(.005)
sampler=threading.Thread(target=sample,daemon=True); sampler.start()
class Timer:
 def __init__(self,name,**extra): self.name=name; self.extra=extra
 def __enter__(self):
  global phase
  phase=self.name; self.wall=time.perf_counter(); self.cpu=time.process_time(); return self
 def __exit__(self,*args): timings.append(dict(phase=self.name,wall_seconds=time.perf_counter()-self.wall,cpu_seconds=time.process_time()-self.cpu,**self.extra))
with Timer('preparation'):
 raw=pd.read_csv(SRC/'input-4.csv'); d=raw.drop_duplicates().copy(); del raw
 d['date']=pd.to_datetime(d.Order_Date); d['status']=d.Order_Status.str.strip().str.lower()
 assert d.date.max()==pd.Timestamp('2025-11-30')
 policy=pd.read_csv(SRC/'input-1.csv').sort_values(['Product_ID','Store_ID']).reset_index(drop=True)
 inventory=pd.read_csv(SRC/'input-3.csv'); receipts=pd.read_csv(SRC/'input-2.csv')
 K=['Product_ID','Store_ID']; pairs=pd.MultiIndex.from_frame(policy[K]); n=len(pairs)
 products=policy.Product_ID.unique(); stores=policy.Store_ID.unique(); pi=pd.Categorical(policy.Product_ID,categories=products).codes; si=pd.Categorical(policy.Store_ID,categories=stores).codes
 weeks=pd.date_range('2022-01-03','2025-11-24',freq='W-MON')
 d['week']=d.date.dt.to_period('W-SUN').dt.start_time
 obs=(d.groupby(['week','Store_ID']).date.nunique().unstack().reindex(index=weeks,columns=stores))
 exposure=obs.to_numpy()[:,si]
 first=d.groupby(K).date.min().reindex(pairs)
 known=(weeks.to_numpy()[:,None]>first.to_numpy()[None,:]) & np.isfinite(exposure)
 assert (first<pd.Timestamp(plan['dates']['origins'][0])).all()
 def eligible(variant):
  flag=(d.Quantity>0)&d.status.ne('cancelled')
  if variant=='no_processing': flag &= d.status.ne('processing')
  if variant=='no_returns': flag &= d.status.ne('returned')&d.Return_Flag.ne('Yes')
  return d[flag]
 def panel(v):
  a=v.groupby(['week']+K).Quantity.sum().unstack(K).reindex(index=weeks,columns=pairs)
  a=a.fillna(0).to_numpy(float); a[~known]=np.nan
  return a
 def truth(v,origin,h):
  # No daily demand zeros are inserted. These are sums of observed ledger contributions.
  end=origin+pd.Timedelta(days=int(np.max(h)))
  block=v[(v.date>origin)&(v.date<=end)]
  if np.isscalar(h): return block.groupby(K).Quantity.sum().reindex(pairs,fill_value=0).to_numpy(float)
  byday=block.groupby(K+['date']).Quantity.sum()
  out=[]
  for j,key in enumerate(pairs):
   try: s=byday.loc[key]; out.append(s.loc[s.index<=origin+pd.Timedelta(days=int(h[j]))].sum())
   except KeyError: out.append(0.)
  return np.array(out,float)
 def observed_days(origin,h):
  out=[]
  for j,key in enumerate(pairs): out.append(d.loc[(d.Store_ID==key[1])&(d.date>origin)&(d.date<=origin+pd.Timedelta(days=int(h if np.isscalar(h) else h[j]))),'date'].nunique())
  return np.array(out)
 def design(w):
  w=pd.DatetimeIndex(w); yearfrac=(w-pd.Timestamp('2022-01-03')).days.to_numpy()/365.25
  prod=np.eye(len(products))[pi][:,1:]; store=np.eye(len(stores))[si][:,1:]
  cross=np.tile(np.column_stack([prod,store]),(len(w),1))
  features=np.column_stack([yearfrac,np.sin(2*np.pi*yearfrac),np.cos(2*np.pi*yearfrac),np.sin(4*np.pi*yearfrac),np.cos(4*np.pi*yearfrac)])
  return np.column_stack([cross,np.repeat(features,n,axis=0)])
 def fit_predict(name,y,origin,variant):
  train_idx=np.flatnonzero(weeks+pd.Timedelta(days=6)<=origin)
  fw=pd.date_range(origin+pd.Timedelta(days=1),periods=2,freq='W-MON')
  with Timer('fit_'+name,variant=variant,origin=str(origin.date())):
   if name=='recent13': model=np.nanmean(y[train_idx[-13:]],axis=0)
   elif name=='ses':
    hist=y[train_idx[-104:]]; model=np.nanmean(hist[:13],axis=0)
    for row in hist[13:]: model=np.where(np.isfinite(row),.15*row+.85*model,model)
   elif name=='shrink26':
    hist=y[train_idx[-26:]]; local=np.nanmean(hist,axis=0); count=np.isfinite(hist).sum(axis=0)
    product_mean=np.array([np.nanmean(hist[:,pi==j]) for j in range(len(products))]); store_mean=np.array([np.nanmean(hist[:,si==j]) for j in range(len(stores))])
    # Means use observed pair-weeks only; unknown store-weeks never contribute zeros.
    pooled=product_mean[pi]*store_mean[si]/max(np.nanmean(hist),1e-12)
    model=(count*local+13*pooled)/(count+13)
   elif name=='poisson_calendar':
    t=train_idx[-104:]; X=design(weeks[t]); target=y[t].ravel(); mask=np.isfinite(target)
    model=PoissonRegressor(alpha=.01,max_iter=300,tol=1e-7).fit(X[mask],target[mask])
   else: raise ValueError(name)
  with Timer('inference_'+name,variant=variant,origin=str(origin.date())):
   pred=model.predict(design(fw)).reshape(2,n) if name=='poisson_calendar' else np.tile(model,(2,1))
   assert np.isfinite(pred).all() and (pred>=0).all()
  return pred
 names=plan['candidates']; origins=pd.to_datetime(plan['dates']['origins']); H=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy()
 targets={v:eligible(v) for v in ['gross','no_processing','no_returns']}; panels={v:panel(t) for v,t in targets.items()}
 coverage={str(o.date()):{'7':observed_days(o,7),'coverage':observed_days(o,H)} for o in origins}
def forecast_total(pred,h):
 h=np.broadcast_to(h,(n,)); return pred[0]*np.minimum(h,7)/7 + pred[1]*np.maximum(h-7,0)/7
rows=[]; forecasts=[]
for variant,v in targets.items():
 y=panels[variant]
 for origin in origins:
  a7=truth(v,origin,7); ah=truth(v,origin,H)
  for name in names:
   pred=fit_predict(name,y,origin,variant)
   for label,h,actual in [('7',7,a7),('coverage',H,ah)]:
    fc=forecast_total(pred,h); cnt=coverage[str(origin.date())][label]; mask=cnt>0; err=fc-actual
    for j in np.flatnonzero(mask): forecasts.append([variant,str(origin.date()),name,label,pairs[j][0],pairs[j][1],actual[j],fc[j],cnt[j],float(err[j]),float(abs(err[j]))])
    rows.append(dict(variant=variant,origin=str(origin.date()),model=name,horizon=label,n=int(mask.sum()),mae=float(np.mean(abs(err[mask]))),bias=float(np.mean(err[mask])),wape=float(np.sum(abs(err[mask]))/np.sum(actual[mask])),actual_units=float(actual[mask].sum())))
scores=pd.DataFrame(rows); scores.to_csv(ROOT/'scores_by_origin.csv',index=False)
detail=pd.DataFrame(forecasts,columns=['variant','origin','model','horizon','Product_ID','Store_ID','actual_recorded_units','forecast_units','observed_store_days','error_units','absolute_error_units']); detail.to_csv(ROOT/'comparison_predictions.csv',index=False)
summary=detail.groupby(['variant','model','horizon']).agg(n=('error_units','size'),mae=('absolute_error_units','mean'),bias=('error_units','mean'),absolute_sum=('absolute_error_units','sum'),actual_sum=('actual_recorded_units','sum')).reset_index(); summary['wape']=summary.absolute_sum/summary.actual_sum
summary.to_csv(ROOT/'comparison_summary.csv',index=False)
primary=summary[(summary.variant=='gross')&(summary.horizon=='7')].set_index('model').mae
best=primary.min(); selected=next(x for x in names if primary[x]<=best+1e-9)
baseline=primary['recent13']; improvement=1-primary[selected]/baseline
diff=(scores[(scores.variant=='gross')&(scores.horizon=='7')].pivot(index='origin',columns='model',values='mae')[selected]-scores[(scores.variant=='gross')&(scores.horizon=='7')].pivot(index='origin',columns='model',values='mae')['recent13']).to_numpy()
rng=np.random.default_rng(603); boot=np.mean(rng.choice(diff,size=(2000,len(diff)),replace=True),axis=1)
complete=detail[(detail.variant=='gross')&(detail.horizon=='7')&(detail.observed_store_days==7)].groupby('model').agg(n=('error_units','size'),mae=('absolute_error_units','mean'),bias=('error_units','mean')).reset_index()
complete.to_csv(ROOT/'complete_week_diagnostics.csv',index=False)
# Sparse demand and seasonal stability, independent of candidate selection.
daily=targets['gross'].groupby(['date']+K).Quantity.sum()
observed_total=0; zero_total=0
for store,g in d.groupby('Store_ID'):
 for day in g.date.unique():
  active=first[(first.index.get_level_values('Store_ID')==store)&(first<=day)]
  positives=targets['gross'].loc[(targets['gross'].Store_ID==store)&(targets['gross'].date==day),'Product_ID'].nunique()
  observed_total+=len(active); zero_total+=len(active)-positives
season=targets['gross'].groupby(targets['gross'].date.dt.to_period('M')).Quantity.sum()
seasonal={str(year):{'november_to_september_daily_rate':float((season.loc[f'{year}-11']/30)/(season.loc[f'{year}-09']/30)),'december_to_september_daily_rate':float((season.loc[f'{year}-12']/31)/(season.loc[f'{year}-09']/30))} for year in [2022,2023,2024]}
train_recent=panels['gross'][weeks>='2025-01-06']; sparse_rate=np.nanmean(train_recent==0,axis=0)
pair_diag=pd.DataFrame({'Product_ID':policy.Product_ID,'Store_ID':policy.Store_ID,'zero_recorded_week_fraction_2025':sparse_rate,'history_recorded_lines':d.groupby(K).size().reindex(pairs).to_numpy()})
diag=detail[(detail.variant=='gross')&(detail.horizon=='7')].merge(pair_diag,on=K,validate='many_to_one'); diag['sparsity_group']=np.where(diag.zero_recorded_week_fraction_2025>=.75,'at_least_75pct_zero_recorded_weeks','other')
diag.groupby(['sparsity_group','model']).agg(n=('error_units','size'),mae=('absolute_error_units','mean'),bias=('error_units','mean')).to_csv(ROOT/'sparsity_diagnostics.csv')
diagnostics={'zero_recorded_contribution_fraction_on_observed_store_days':zero_total/observed_total,'observed_product_store_days':observed_total,'store_week_observed_days_distribution':obs.stack().value_counts().sort_index().to_dict(),'entirely_unobserved_store_weeks':int(obs.isna().sum().sum()),'seasonality_prior_years':seasonal,'complete_week_rows':complete.to_dict('records'),'bootstrap_origin_cluster_95pct_MAE_difference_selected_minus_baseline':np.quantile(boot,[.025,.975]).tolist(),'bootstrap_limits':'Only seven overlapping development origins; interval reflects this data and selection is already made on it. Not independent evidence of superiority.','monthly_target_units':{str(k):int(v) for k,v in season.items()}}
save('diagnostics.json',diagnostics)
with Timer('final_fit_and_restocking'):
 origin=pd.Timestamp('2025-11-30'); final_predictions={}
 for name in set([selected,'recent13']): final_predictions[name]=fit_predict(name,panels['gross'],origin,'gross_final')
 chosen=final_predictions[selected]; base=final_predictions['recent13']
 out=policy.merge(inventory,on=K,validate='one_to_one',suffixes=('','_stock'))
 horizon=out.Supplier_Lead_Time_Days+out.Review_Period_Days; coverage_end=origin+pd.to_timedelta(horizon,unit='D')
 inc=[]; before=[]
 for j,row in out.iterrows():
  match=receipts[(receipts.Product_ID==row.Product_ID)&(receipts.Store_ID==row.Store_ID)]
  due=pd.to_datetime(match.Expected_Arrival_Date)
  inc.append(match.loc[due<=coverage_end.iloc[j],'Incoming_Qty'].sum())
  before.append(match.loc[due<origin+pd.Timedelta(days=int(row.Supplier_Lead_Time_Days)),'Incoming_Qty'].sum())
 coverage_forecast=forecast_total(chosen,horizon.to_numpy()); weekly=forecast_total(chosen,7)
 def order(fc):
  need=np.maximum(0,fc+out.Safety_Stock_Qty-out.Usable_On_Hand_Qty-np.array(inc))
  return np.where(need>1e-10,np.ceil(np.maximum(need,out.Minimum_Order_Qty)/out.Order_Multiple_Qty)*out.Order_Multiple_Qty,0).astype(int)
 qty=order(coverage_forecast); base_qty=order(forecast_total(base,horizon.to_numpy()))
 # Daily inventory trajectory before new order arrives; receipts dated that day usable before sales.
 prearrival=np.zeros(n,dtype=bool)
 for j,row in out.iterrows():
  balance=float(row.Usable_On_Hand_Qty)
  for day in range(1,int(row.Supplier_Lead_Time_Days)):
   date=origin+pd.Timedelta(days=day)
   arrivals=receipts.loc[(receipts.Product_ID==row.Product_ID)&(receipts.Store_ID==row.Store_ID)&(receipts.Expected_Arrival_Date==str(date.date())),'Incoming_Qty'].sum()
   balance+=arrivals-chosen[0,j]/7
   if balance<0: prearrival[j]=True
 name_map=d.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name
 result=pd.DataFrame({'Product_ID':out.Product_ID,'Product_Name':out.Product_ID.map(name_map),'Store_ID':out.Store_ID,'OrderQty':qty,'Quantity_Unit':'product_unit','Forecast_Next_Week_Units':np.round(weekly,3),'Forecast_Coverage_Units':np.round(coverage_forecast,3),'Coverage_Days':horizon,'Coverage_End':coverage_end.dt.strftime('%Y-%m-%d'),'Usable_Stock_Units':out.Usable_On_Hand_Qty,'Incoming_Within_Coverage_Units':inc,'Safety_Stock_Units':out.Safety_Stock_Qty,'Order_Multiple_Units':out.Order_Multiple_Qty,'Minimum_Order_Units':out.Minimum_Order_Qty,'Expected_New_Order_Arrival':(origin+pd.to_timedelta(out.Supplier_Lead_Time_Days,unit='D')).dt.strftime('%Y-%m-%d'),'Review_Before_Arrival':np.where(prearrival,'Yes','No'),'Input_Basis':'synthetic_stock_and_policy'})
 result.to_csv(ROOT/'restocking.csv',index=False)
 assert len(result)==336 and result.OrderQty.ge(0).all() and pd.api.types.is_integer_dtype(result.OrderQty)
 assert ((result.OrderQty==0)|((result.OrderQty%result.Order_Multiple_Units==0)&(result.OrderQty>=result.Minimum_Order_Units))).all()
 pd.DataFrame({'Product_ID':out.Product_ID,'Store_ID':out.Store_ID,'selected_qty':qty,'baseline_qty':base_qty,'difference':qty-base_qty}).to_csv(ROOT/'order_sensitivity.csv',index=False)
 sha=hashlib.sha256((ROOT/'restocking.csv').read_bytes()).hexdigest()
 save('result.json',{'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha})
 final_summary={'selected':selected,'primary_mae':primary.to_dict(),'relative_MAE_reduction_vs_analytical_baseline':float(improvement),'positive_orders':int((qty>0).sum()),'zero_orders':int((qty==0).sum()),'total_units':int(qty.sum()),'forecast_next_week_units_total':float(weekly.sum()),'prearrival_shortfall_flags':int(prearrival.sum()),'baseline_order_units':int(base_qty.sum()),'baseline_quantity_differences':int((qty!=base_qty).sum()),'csv_sha256':sha,'primary_is_development_only':True,'independent_success_gate_ready':False}
 save('measured_results.json',final_summary)
stop.set(); sampler.join()
ru=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; ru_bytes=ru if sys.platform=='darwin' else ru*1024
save('workload.json',{'wall_seconds_end_to_end':time.perf_counter()-start,'cpu_seconds_end_to_end':time.process_time()-cpu_start,'peak_process_rss_bytes':max(peak[0],ru_bytes),'peak_sampled_rss_by_phase_bytes':phase_peaks,'timings':timings,'host':{'platform':platform.platform(),'processor':platform.processor(),'python':sys.version,'logical_cpu_count':psutil.cpu_count(),'physical_ram_bytes':psutil.virtual_memory().total},'dependencies':{'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'psutil':psutil.__version__},'weekly_panel_shape':list(panels['gross'].shape),'weekly_panel_bytes_each':panels['gross'].nbytes,'maximum_design_shape':[104*n,len(products)+len(stores)-2+5],'maximum_design_bytes':104*n*(len(products)+len(stores)-2+5)*8,'measurement_limits':'Local calculation time, not AI analysis/build time. RSS high-water includes imports, full source data, preparation, all variant panels, model designs, predictions, comparisons and retained objects. Sampling 5ms may miss phase spikes; process OS high-water used for total. End-to-end is larger than a single weekly production run. No enforced 8GB cap; actual host differs. Single BLAS thread; no network or API. No external service charges; computer/electricity/hosting costs not priced. AI build usage and applicable pricing unavailable.'})
print(json.dumps(final_summary,indent=2)); print('Peak RSS MiB',max(peak[0],ru_bytes)/2**20,'local calculation seconds',time.perf_counter()-start)
