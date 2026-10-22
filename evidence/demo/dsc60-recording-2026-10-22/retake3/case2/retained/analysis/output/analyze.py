"""Bounded, frozen development comparison. Reads released inputs only."""
import json, hashlib, time, resource, sys, platform
from pathlib import Path
import numpy as np
import pandas as pd
from forecasting import prepare_sales, predict, weekly_panel, KEYS, MODELS

def dump(name, data):
    Path(name).write_text(json.dumps(data, indent=2, default=str))

def run():
    start=time.perf_counter()
    plan=json.loads(Path('evaluation_plan.json').read_text())
    assert plan['version']==1 and Path('task_refinement.json').exists()
    source=Path('../released')
    raw,names,duplicates=prepare_sales(source/'input-4.csv',pd.Timestamp('2025-11-30'))
    rules=pd.read_csv(source/'input-1.csv')
    stock=pd.read_csv(source/'input-3.csv')
    ledger=pd.read_csv(source/'input-2.csv')
    keys=rules[KEYS].sort_values(KEYS).reset_index(drop=True)
    idx=pd.MultiIndex.from_frame(keys)
    for d in [rules,stock]:
        assert not d.duplicated(KEYS).any()
        assert set(map(tuple,d[KEYS].values))==set(idx)
    assert not ledger.PO_Line_ID.duplicated().any()
    assert set(map(tuple,ledger[KEYS].values)).issubset(set(idx))
    incoming=ledger.groupby(KEYS).Incoming_Qty.sum().reindex(idx,fill_value=0)
    onorder=stock.set_index(KEYS).On_Order_Qty.reindex(idx)
    assert (incoming==onorder).all()
    assert stock.Open_Order_Ledger_Complete.all()
    assert set(raw.set_index(KEYS).index)==set(idx)
    source_audit={
      'sources':[{'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'actual_provenance_values':pd.read_csv(f).Provenance.unique().tolist() if 'Provenance' in pd.read_csv(f,nrows=0).columns else ['supplied transactions; controller-released development partition']} for f in sorted(source.glob('*.csv'))],
      'provenance_note':'Operational CSVs internally label every row synthetic; explicitly authorized as assumed scenario operating facts. Sales released hash differs from original approved hash due to development partition. No originals or December outcomes read.',
      'sales_rows_raw':len(raw)+duplicates,'exact_duplicate_rows_removed':duplicates,
      'conflicting_transaction_ids':int(raw.Transaction_ID.duplicated().sum()),
      'repeated_order_ids_note':'Order IDs are not transaction-line keys; 3224 repeat after exact deduplication, retained distinct Transaction_ID lines.',
      'dates':[raw.Order_Date.min(),raw.Order_Date.max()],
      'global_missing_calendar_dates':len(pd.date_range(raw.Order_Date.min(),raw.Order_Date.max()).difference(raw.Order_Date)),
      'status_rows_and_units':raw.groupby('status').Quantity.agg(['count','sum']).to_dict(),
      'status_return_cross':pd.crosstab(raw.status,raw.Return_Flag).to_dict(),
      'nonpositive_quantity_rows':raw.loc[raw.Quantity<=0].groupby(['status','Return_Flag']).size().to_dict().__str__(),
      'target_rows':int(raw.fulfilled.sum()),'target_units':int(raw.loc[raw.fulfilled,'Quantity'].sum()),
      'fulfilled_return_flag_rows':int((raw.fulfilled & raw.Return_Flag.str.lower().eq('yes')).sum()),
      'product_name_conflicts':int(raw.groupby('Product_ID').Product_Name.nunique().gt(1).sum()),
      'missing_product_names':int(raw.Product_Name.isna().sum()),
      'inventory_transaction_field':'Ignored: transaction-time Inventory_Level is not present-day usable stock and cannot reconstruct historical stockout exposure.',
      'operational_checks':{'keys':len(keys),'inventory_rule_key_agreement':True,'sales_key_agreement':True,'ledger_complete_all':True,'incoming_totals_match_on_order_all':True,'incoming_total':int(incoming.sum()),'on_hand_total':int(stock.Usable_On_Hand_Qty.sum()),'units':rules.Quantity_Unit.unique().tolist(),'stock_dates':stock.Snapshot_Date.unique().tolist(),'policy_dates':rules.Effective_Date.unique().tolist()},
      'target_interpretation':'Recorded positive fulfilled units, gross of return flags. Returned status excluded because actual prior fulfilment and return dates unknown; no negative adjustment to stock without evidence of usable returns. Current statuses may have changed after historical origins; unknown timing limits comparison validity.',
      'coverage_interpretation':'Store_ID used for all sales channels because no channel allocation instructions. No evidence of open-day calendar or assortment exposure: within active store-weeks missing product lines mean zero recorded transactions only, not fabricated measured demand zeros. Store-inactive weeks remain missing. Current roster conditions historical comparison.',
      'reserved_outcomes_accessed':False}
    panel=weekly_panel(raw,keys,pd.Timestamp('2025-11-30'))
    source_audit.update(weekly_panel_cells=int(panel.size),unknown_pair_weeks=int(panel.isna().sum().sum()),zero_recorded_fraction=float((panel==0).sum().sum()/panel.notna().sum().sum()),raw_store_week_coverage=raw.groupby('week').Store_ID.nunique().value_counts().to_dict())
    dump('source_treatment.json',source_audit)
    output=[]; timings=[]
    coverage=rules.set_index(KEYS).reindex(idx).Supplier_Lead_Time_Days.to_numpy()+7
    for origin_str in plan['forecast_origins']:
        origin=pd.Timestamp(origin_str)
        targets={}
        for h in [7,14,'coverage']:
            days=np.repeat(h,len(keys)) if h!='coverage' else coverage
            target=[]; known=[]
            for i,key in enumerate(idx):
                window=raw.loc[(raw.Order_Date>origin)&(raw.Order_Date<=origin+pd.Timedelta(days=int(days[i])))&(raw.Store_ID==key[1])]
                known.append(len(window)>0)
                target.append(window.loc[window.fulfilled & window.Product_ID.eq(key[0]),'Quantity'].sum())
            targets[h]=(np.array(target),np.array(known),days)
        for method in MODELS:
            pred,timing=predict(raw,keys,origin,method)
            timings.append(dict(origin=origin_str,method=method,**timing))
            for h,(target,known,days) in targets.items():
                for i in np.where(known)[0]:
                    output.append(dict(origin=origin_str,method=method,horizon=str(h),Product_ID=idx[i][0],Store_ID=idx[i][1],days=int(days[i]),actual=float(target[i]),forecast=float(pred[i]*days[i]/7)))
    scores=pd.DataFrame(output)
    scores['abs_error']=(scores.forecast-scores.actual).abs()
    scores['error']=scores.forecast-scores.actual
    scores.to_csv('development_predictions.csv',index=False)
    def metric(d):
        return dict(n=len(d),actual_units=float(d.actual.sum()),mae=float(d.abs_error.mean()),wape=float(d.abs_error.sum()/d.actual.sum()),bias=float(d.error.mean()),rmse=float(np.sqrt((d.error**2).mean())))
    pooled={str(h):{m:metric(scores.loc[(scores.method==m)&(scores.horizon==str(h))]) for m in MODELS} for h in [7,14,'coverage']}
    winner=min(MODELS,key=lambda m:(round(pooled['7'][m]['mae'],8),MODELS.index(m)))
    per_origin={o:{m:metric(scores.loc[(scores.origin==o)&(scores.method==m)&(scores.horizon=='7')]) for m in MODELS} for o in plan['forecast_origins']}
    group_scores=[]
    for col in ['Product_ID','Store_ID']:
        for (group,m),g in scores.loc[scores.horizon=='7'].groupby([col,'method']):
            group_scores.append(dict(dimension=col,group=group,method=m,**metric(g)))
    pd.DataFrame(group_scores).to_csv('segment_scores.csv',index=False)
    diff=np.array([per_origin[o][winner]['mae']-per_origin[o]['baseline_month']['mae'] for o in per_origin])
    rng=np.random.default_rng(123)
    boot=diff[rng.integers(0,len(diff),(10000,len(diff)))].mean(axis=1)
    loo={o:min(MODELS,key=lambda m:np.mean([per_origin[oo][m]['mae'] for oo in per_origin if oo!=o])) for o in per_origin}
    sensitivity={}
    # Rescore identical frozen predictions against alternative plausible targets; no selection change.
    for treatment in ['exclude_return_flags','include_processing']:
        alt=raw.copy()
        alt['included']=alt.fulfilled & alt.Return_Flag.str.lower().eq('no') if treatment=='exclude_return_flags' else (alt.status.isin(['completed','shipped','processing']) & alt.Quantity.gt(0))
        entries=[]
        for o,g in scores.loc[scores.horizon=='7'].groupby('origin'):
            date=pd.Timestamp(o)
            actual=alt.loc[alt.included & alt.Order_Date.between(date+pd.Timedelta(days=1),date+pd.Timedelta(days=7))].groupby(KEYS).Quantity.sum()
            for m,gg in g.groupby('method'):
                v=actual.reindex(pd.MultiIndex.from_frame(gg[KEYS]),fill_value=0).to_numpy()
                entries.append((m,float(np.abs(gg.forecast.to_numpy()-v).sum()),len(v)))
        sensitivity[treatment]={m:sum(x[1] for x in entries if x[0]==m)/sum(x[2] for x in entries if x[0]==m) for m in MODELS}
    # Frequency strata preserve comparable rows for all models.
    strata={}
    prior=weekly_panel(raw.loc[raw.Order_Date<=pd.Timestamp('2025-09-28')],keys,pd.Timestamp('2025-09-28')).iloc[:,-52:]
    frequent=set(prior.index[(prior>0).mean(axis=1)>.25])
    z=scores.loc[scores.horizon=='7'].copy()
    z['more_frequent']=[(p,s) in frequent for p,s in zip(z.Product_ID,z.Store_ID)]
    for name,g in z.groupby('more_frequent'):
        strata[str(name)]={m:metric(gg) for m,gg in g.groupby('method')}
    yearly=raw.loc[raw.fulfilled].groupby([raw.Order_Date.dt.year,raw.Order_Date.dt.month]).Quantity.sum()
    result=dict(plan_version=1,status='development only; not independent evaluation',selected=winner,pooled=pooled,per_origin=per_origin,leave_one_origin_out_winners=loo,paired_origin_bootstrap_difference_mae_95pct=np.quantile(boot,[.025,.975]).tolist(),target_definition_sensitivity_fixed_predictions=sensitivity,frequency_strata=strata,year_month_units={str(k):int(v) for k,v in yearly.items()},selection_limit='No independent outcome evidence or externally declared meaningful threshold; performance-success recording gate remains open. No cost or availability conclusion.',runtime_seconds=time.perf_counter()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,host=platform.platform(),timings=timings)
    dump('comparison_results.json',result)
    dump('selected_method.json',{'method':winner,'plan_version':1,'fit_through':'2025-11-30'})
    print(json.dumps({'winner':winner,'scores':pooled,'runtime':result['runtime_seconds']},indent=2))

if __name__=='__main__': run()
