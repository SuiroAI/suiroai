"""Bounded development comparison: run from output; never reads outside four released files."""
import hashlib
import json
import platform
import resource
import time
from pathlib import Path
import numpy as np
import pandas as pd
from restock_routine import load_inputs,daily_sales,fit_forecaster,predict_days

def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,default=str))

def main():
    start=time.perf_counter()
    source=Path('../released')
    raw=pd.read_csv(source/'input-4.csv')
    sales,stock,inbound,policy,date,pairs=load_inputs(source/'input-4.csv',source/'input-3.csv',source/'input-2.csv',source/'input-1.csv','2025-11-30')
    daily=daily_sales(sales,pairs,date)
    profile={
      'source_files':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(source.glob('*.csv'))},
      'source_provenance':{'operations':'supplied source files with synthetic provenance classifications; authorized roleplay treats operations as scenario facts; no independent real-stock verification','sales':'released development partition, byte hash differs from original approved raw source as declared by controller; do not seek original'},
      'raw_rows':len(raw),'exact_duplicates_removed':len(raw)-len(sales),'conflicting_transaction_ids':int(sales.Transaction_ID.duplicated().sum()),'order_ids_repeated':int(sales.Order_ID.duplicated().sum()),
      'status_counts':sales.status.value_counts().to_dict(),'status_return_counts':pd.crosstab(sales.status,sales.Return_Flag).to_dict(),
      'nonpositive_quantities':sales.loc[sales.Quantity.le(0),['Order_Status','Return_Flag','Quantity']].to_dict('records'),
      'target_rows':int((sales.status.isin(['completed','shipped']) & sales.Quantity.gt(0)).sum()),'target_units':float(daily.to_numpy().sum()),
      'date_range':[str(daily.index.min().date()),str(date.date())],'global_missing_calendar_days':len(pd.date_range(sales.Order_Date.min(),date).difference(sales.Order_Date)),
      'store_days_with_any_transaction':sales.groupby('Store_ID').Order_Date.nunique().to_dict(),'pairs':len(pairs),'product_names_nonnull_distinct':sales.groupby('Product_ID').Product_Name.nunique().to_dict(),
      'positive_pair_day_fraction':float((daily.to_numpy()>0).mean()),'pair_days_shape':daily.shape,'daily_array_bytes':daily.to_numpy().nbytes,
      'weekly_zero_fraction':float((daily.resample('W-SUN').sum().to_numpy()==0).mean()),
      'pair_first_last_transactions':sales.groupby(['Product_ID','Store_ID']).Order_Date.agg(['min','max']).reset_index().astype(str).to_dict('records'),
      'operational_checks':{'stock_policy_unique_rows':len(stock),'inbound_lines':len(inbound),'inbound_units':int(inbound.Incoming_Qty.sum()),'stock_on_order_units':int(stock.On_Order_Qty.sum()),'matched_all_pairs':True,'ledger_complete_all':True,'stock_snapshot':str(date.date()),'stock_units':int(stock.Usable_On_Hand_Qty.sum()),'coverage_days':sorted((policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).unique().tolist())},
      'treatment_effects':{'order_ids':'Not deduplicated: order may contain distinct legitimate transaction lines','inventory_level_in_sales':'Not used: transaction-level values cannot establish current stock or stockout history','return_credit':'No return stock credit; usable stock already supplied','zero_recorded_sales':'Calendar zeros are absent recorded transaction events, conditional on continuous capture; no claim store open or unmet demand zero','status_availability':'Final statuses lack change timestamps. Targets are frozen supplied labels; no historical status or inventory features used'},
      'seasonal_monthly_units_by_year':sales.loc[sales.status.isin(['completed','shipped']) & sales.Quantity.gt(0)].groupby([sales.Order_Date.dt.year,sales.Order_Date.dt.month]).Quantity.sum().to_dict().__str__()
    }
    dump('source_treatment.json',profile)
    origins=pd.to_datetime(json.loads(Path('evaluation_plan.json').read_text())['origins'])
    model_names=['mean56','mean182','poisson']
    records=[]; timings=[]
    coverage=(policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).to_numpy(dtype=int)
    for origin in origins:
        train=daily.loc[:origin]
        actual=daily.loc[origin+pd.Timedelta(days=1):origin+pd.Timedelta(days=14)].to_numpy().cumsum(axis=0)
        for model in model_names:
            t=time.perf_counter(); fitted=fit_forecaster(train,origin,model); fit_time=time.perf_counter()-t
            t=time.perf_counter(); predicted=predict_days(fitted,origin,14,len(pairs)).cumsum(axis=0); infer_time=time.perf_counter()-t
            timings.append(dict(origin=str(origin.date()),model=model,fit_seconds=fit_time,inference_seconds=infer_time,iterations=getattr(fitted,'n_iter_',None)))
            for j,pair in enumerate(pairs):
                for horizon in [7,int(coverage[j])]:
                    y,yhat=float(actual[horizon-1,j]),float(predicted[horizon-1,j])
                    records.append(dict(origin=str(origin.date()),model=model,Product_ID=pair[0],Store_ID=pair[1],horizon_type='next_week' if horizon==7 else 'policy_coverage',horizon_days=horizon,actual=y,forecast=yhat,error=yhat-y,absolute_error=abs(yhat-y)))
    scores=pd.DataFrame(records);scores.to_csv('comparison_predictions.csv',index=False)
    aggregate=scores.groupby(['model','horizon_type']).agg(MAE=('absolute_error','mean'),bias=('error','mean'),actual_units=('actual','sum'),absolute_error_units=('absolute_error','sum')).reset_index()
    aggregate.to_csv('comparison_scores.csv',index=False)
    by_origin=scores.groupby(['model','horizon_type','origin']).absolute_error.mean().unstack('model')
    by_origin.to_csv('scores_by_origin.csv')
    scores.groupby(['model','horizon_type','Store_ID']).absolute_error.mean().to_csv('scores_by_store.csv')
    primary=aggregate[aggregate.horizon_type.eq('next_week')].set_index('model').MAE
    minimum=primary.min(); selected=next(m for m in model_names if primary[m]<=minimum+1e-6)
    selected_errors=scores[scores.model.eq(selected)]
    residuals=selected_errors.groupby('horizon_type').error.quantile([.1,.5,.9]).to_dict()
    ru=resource.getrusage(resource.RUSAGE_SELF)
    summary={'selected_model':selected,'selection_rule':'Lowest next-week MAE; simpler tie within 1e-6','primary_scores':primary.to_dict(),'relative_error_reduction_vs_mean56':float(1-primary[selected]/primary['mean56']),'by_origin':by_origin.reset_index().to_dict('records'),'residual_error_quantiles':str(residuals),'timings':timings,'analysis_compute_seconds':time.perf_counter()-start,'process_peak_rss_bytes':ru.ru_maxrss if platform.system()=='Darwin' else ru.ru_maxrss*1024,'limitations':'Development data already inspected; no independent holdout. Quantiles describe pooled historical signed errors, not calibrated intervals for individual future products. No business cost, availability or savings measured.','performance_success_gate':{'ready':False,'missing':['external meaningful improvement threshold','genuinely untouched independent outcomes with frozen artifacts']}}
    dump('comparison_results.json',summary)
    print(aggregate.to_string(index=False));print('selected',selected);print('peak_bytes',summary['process_peak_rss_bytes']);print('seconds',summary['analysis_compute_seconds'])

if __name__=='__main__':main()
