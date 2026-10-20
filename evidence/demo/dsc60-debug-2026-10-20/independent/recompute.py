"""Independent DSC-60 audit from released pre-December source inputs.

Does not import or execute producer code. Reconstructs original candidates from
its documented equations, independently scores identical origins, and inspects
coverage/seasonal stability. Never opens original full-history sales/December.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
RUN=ROOT/'artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-fd2a074d16e7401ca1682ad64e944847'
sources={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted((RUN/'released').glob('*.csv'))}
raw=pd.read_csv(RUN/'released/input-4.csv')
# This assertion precedes reading any outcome column into calculations.
d=pd.to_datetime(raw['Order_Date']); assert d.max()<=pd.Timestamp('2025-11-30')
sales=raw.drop_duplicates().copy(); sales['day']=pd.to_datetime(sales.Order_Date)
sales['status']=sales.Order_Status.str.strip().str.lower()
pol=pd.read_csv(RUN/'released/input-1.csv'); keys=list(zip(pol.Product_ID,pol.Store_ID)); lookup={k:i for i,k in enumerate(keys)}
calendar=pd.date_range(sales.day.min(),sales.day.max()); tmap={d:i for i,d in enumerate(calendar)}
Y=np.zeros((len(calendar),len(keys))); seen=np.zeros_like(Y,dtype=bool); first=np.full(len(keys),len(calendar))
for r in sales.itertuples():
 i,j=tmap[r.day],lookup[(r.Product_ID,r.Store_ID)];seen[i,j]=True;first[j]=min(first[j],i)
 if r.Quantity>0 and r.status!='cancelled':Y[i,j]+=r.Quantity
for j,i in enumerate(first):Y[:i,j]=np.nan
product=np.array([k[0] for k in keys]);store=np.array([k[1] for k in keys])
def predict(origin,h):
 n=tmap[origin]+1; hist=Y[:n]; recent=hist[-91:]; year=hist[-364:]
 annual=np.nanmean(year,axis=0);total=np.nansum(year)
 ps={p:np.nansum(year[:,product==p])/total for p in set(product)}
 ss={s:np.nansum(year[:,store==s])/total for s in set(store)}
 pooled=np.array([ps[p]*ss[s] for p,s in keys])*np.nansum(recent)/len(recent)
 blend=(annual+pooled)/2
 old=hist[calendar[:n].year<origin.year];od=calendar[:len(old)]
 m=np.array([np.nansum(old[od.month==month])/sum(od.month==month) for month in range(1,13)])
 factor=m/m.mean()
 future=pd.date_range(origin+pd.Timedelta(days=1),periods=h)
 adjust=np.mean(factor[future.month-1])/np.mean(factor[calendar[n-91:n].month-1])
 return {'recent_13_weeks':np.nanmean(recent,axis=0)*h,'recent_4_weeks':np.nanmean(hist[-28:],axis=0)*h,'recent_26_weeks':np.nanmean(hist[-182:],axis=0)*h,'annual_average':annual*h,'shared_patterns':blend*h,'shared_seasonal':blend*adjust*h}
rows=[]
for o in pd.date_range('2025-06-29','2025-11-23',freq='W-SUN'):
 if pd.Timestamp('2025-09-16')<=o<pd.Timestamp('2025-10-05'):continue
 for h in (7,14):
  if o+pd.Timedelta(days=h)>calendar[-1]:continue
  actual=np.nansum(Y[tmap[o]+1:tmap[o]+h+1],axis=0)
  for model,pred in predict(o,h).items():
   err=pred-actual
   rows.append(dict(origin=str(o.date()),split='selection' if o.month<10 else 'holdout',horizon_days=h,model=model,absolute_error_sum=np.abs(err).sum(),squared_error_sum=(err**2).sum(),actual_units=actual.sum(),n=len(keys),bias_sum=err.sum()))
detail=pd.DataFrame(rows);detail.to_csv(HERE/'independent_evaluation_detail.csv',index=False)
metric=detail.groupby(['split','horizon_days','model']).sum(numeric_only=True)
metric['mae']=metric.absolute_error_sum/metric.n;metric['rmse']=np.sqrt(metric.squared_error_sum/metric.n)
metric['wape']=metric.absolute_error_sum/metric.actual_units;metric['bias_fraction']=metric.bias_sum/metric.actual_units
metric.to_csv(HERE/'independent_evaluation_summary.csv')
producer=pd.read_csv(RUN/'output/evaluation_summary.csv').set_index(['split','horizon_days','model'])
maxdiff=float((metric[['mae','rmse','wape','bias_fraction']]-producer[['mae','rmse','wape','bias_fraction']]).abs().max().max())
monthly=[]
for (year,month),g in sales[(sales.Quantity>0)&(sales.status!='cancelled')].groupby([sales.day.dt.year,sales.day.dt.month]):
 monthly.append({'year':int(year),'month':int(month),'units':int(g.Quantity.sum()),'days':int(sum((calendar.year==year)&(calendar.month==month))),'units_per_day':float(g.Quantity.sum()/sum((calendar.year==year)&(calendar.month==month)))})
pd.DataFrame(monthly).to_csv(HERE/'pre_december_monthly_recorded_units.csv',index=False)
origin_records=[]
for (split,h),g in detail.groupby(['split','horizon_days']):
 base=g[g.model=='recent_13_weeks'].set_index('origin').absolute_error_sum
 for model in ('shared_patterns','shared_seasonal'):
  e=g[g.model==model].set_index('origin').absolute_error_sum
  origin_records.append({'split':split,'horizon':int(h),'model':model,'origins':len(e),'origins_better':int((e<base).sum()),'relative_mae_gain':float(1-e.sum()/base.sum()),'origin_relative_gains':(1-e/base).to_dict()})
report={'scope':'Only final take released pre-December input CSVs read. Producer analyze.py never executed.','sources':sources,'raw_rows':len(raw),'distinct_rows':len(sales),'duplicates':len(raw)-len(sales),'latest_released_date':str(calendar[-1].date()),'status_rows':sales.status.value_counts().to_dict(),'status_units':sales.groupby('status').Quantity.sum().to_dict(),'nonpositive_rows':int((sales.Quantity<=0).sum()),'returns':sales.Return_Flag.value_counts().to_dict(),'pairs':len(keys),'calendar_days':len(calendar),'observed_pair_days':int(seen.sum()),'pair_day_observed_fraction':float(seen.mean()),'positive_proxy_pair_days':int((Y>0).sum()),'network_days_with_any_record':int(seen.any(axis=1).sum()),'first_pair_date_latest':str(calendar[first.max()].date()),'protection_days':pol.Supplier_Lead_Time_Days.add(pol.Review_Period_Days).value_counts().sort_index().to_dict(),'metric_max_absolute_difference_vs_retained_summary':maxdiff,'paired_origins':origin_records}
(HERE/'independent_calculation_results.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
print(json.dumps(report,indent=2,default=str))
print(metric[['mae','rmse','bias_fraction']].to_string())
# Additional diagnostics are development-only, never used as a final-test rule.
diag=[]
for name,start,end in [('selection','2025-06-29','2025-09-14'),('later_development','2025-10-05','2025-11-23')]:
 a=[];p=[];b=[]
 for o in pd.date_range(start,end,freq='W-SUN'):
  a.append(np.nansum(Y[tmap[o]+1:tmap[o]+8],axis=0));ps=predict(o,7);p.append(ps['shared_seasonal']);b.append(ps['recent_13_weeks'])
 a=np.array(a);p=np.array(p);b=np.array(b)
 diag.append({'split':name,'zero_target_fraction':float((a==0).mean()),'mean_target':float(a.mean()),'median_target':float(np.median(a)),'seasonal_mean_forecast':float(p.mean()),'baseline_mean_forecast':float(b.mean()),'seasonal_error_on_zero_targets':float(p[a==0].sum()),'baseline_error_on_zero_targets':float(b[a==0].sum()),'seasonal_error_on_nonzero_targets':float(np.abs(p-a)[a>0].sum()),'baseline_error_on_nonzero_targets':float(np.abs(b-a)[a>0].sum())})
season=[]
for y in (2022,2023,2024,2025):
 mask=calendar.year==y
 for label,months in [('July_September',[7,8,9]),('October_November',[10,11])]:
  z=mask&np.isin(calendar.month,months);season.append({'year':y,'period':label,'units_per_day':float(np.nansum(Y[z])/sum(z))})
(HERE/'sparsity_seasonality_diagnostics.json').write_text(json.dumps({'weekly_target_diagnostics':diag,'network_seasonality':season},indent=2)+'\n')
print(json.dumps({'weekly_target_diagnostics':diag,'network_seasonality':season},indent=2))
# Deliberately degenerate diagnostic; NEVER eligible for model selection.
zero_diag=[]
for split in ('selection','holdout'):
 g=detail[(detail.split==split)&(detail.horizon_days==7)&(detail.model=='recent_13_weeks')]
 z=float(g.actual_units.sum()/g.n.sum());base=float(g.absolute_error_sum.sum()/g.n.sum())
 zero_diag.append({'split':split,'all_zero_mae':z,'baseline_mae':base,'relative_mae_gain':1-z/base,'aggregate_bias_fraction':-1.0,'eligible_winner':False,'interpretation':'Sanity diagnostic of sparse-target absolute loss, not a replenishment recommendation or protocol candidate.'})
(HERE/'all_zero_sanity_diagnostic.json').write_text(json.dumps(zero_diag,indent=2)+'\n')
print(json.dumps(zero_diag,indent=2))
