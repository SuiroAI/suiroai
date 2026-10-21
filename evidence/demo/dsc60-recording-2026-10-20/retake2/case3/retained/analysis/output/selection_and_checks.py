"""Summarize the predeclared comparison, freeze selection, and audit operating inputs."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import restock_routine as rr

methods=['recent_8week','pooled_13week','poisson_calendar']
measured=[json.loads(Path(f'measured_{m}_fulfilled.json').read_text()) for m in methods]
winner=min(measured,key=lambda x:(round(x['primary_MAE_7day'],9),methods.index(x['method'])))['method']
assert rr.SELECTED==winner
scores=pd.concat([pd.read_csv(f'comparison_{m}_fulfilled.csv') for m in methods])
pr=scores[scores.horizon==7]
loo={o:pr[pr.origin!=o].groupby('method').abs_error.mean().idxmin() for o in pr.origin.unique()}
wide=pr.pivot(index=['origin','Product_ID','Store_ID'],columns='method',values='abs_error')
diff=wide[winner]-wide.recent_8week
byorigin=diff.groupby('origin').mean()
selected={'selected_method':winner,'selection_rule':'Minimum predeclared primary MAE; no score-informed new candidates or tuning','baseline':'recent_8week, analytical baseline, not customer incumbent','relative_error_reduction':1-measured[methods.index(winner)]['primary_MAE_7day']/measured[0]['primary_MAE_7day'],'per_origin_error_difference_from_baseline':byorigin.to_dict(),'origins_improved':int((byorigin<0).sum()),'leave_one_origin_out_winners':loo,'per_store_improved':int((pr.groupby(['method','Store_ID']).abs_error.mean().unstack(0)[winner]<pr.groupby(['method','Store_ID']).abs_error.mean().unstack(0).recent_8week).sum()),'secondary_horizon_winners':scores.groupby(['horizon','method']).abs_error.mean().unstack('method').idxmin(axis=1).to_dict(),'interpretation':'Small development error difference; no externally supplied practical improvement threshold. Not proof of business benefit, true demand accuracy, or superiority over an unspecified incumbent.','performance_success_recording_readiness':False,'gate_reasons':['No untouched evaluation outcomes used','No externally predeclared meaningful improvement threshold','No claim that fixed extract statuses reconstruct historical knowledge'],'measurement_limits':'Candidate processes ran concurrently, one CPU thread each; elapsed values include contention and import effects. Absolute high-water process RSS includes preparation, fitting, inference, retained comparison outputs and imported libraries; it bounds both fit and inference but cannot isolate their incremental memory.'}
Path('selected_method.json').write_text(json.dumps(selected,indent=2))
p,s,d=rr.operations('../released/input-3.csv','../released/input-2.csv','../released/input-1.csv',pd.Timestamp('2025-11-30'))
day,sales,names=rr.prepare_sales('../released/input-4.csv',pd.Timestamp('2025-11-30'),p.index)
stats={'deduplicated_rows':len(sales),'excluded_nonpositive_rows':int((sales.Quantity<=0).sum()),'excluded_nonpositive_unit_sum':int(sales.loc[sales.Quantity<=0,'Quantity'].sum()),'normalized_status_counts':sales.status.value_counts().to_dict(),'primary_positive_target_rows':int((sales.status.isin(['completed','shipped','returned']) & sales.Quantity.gt(0)).sum()),'primary_target_units':int(sales.loc[sales.status.isin(['completed','shipped','returned']) & sales.Quantity.gt(0),'Quantity'].sum()),'returns_flag_not_returned_status':int((sales.Return_Flag.eq('Yes') & sales.status.ne('returned')).sum()),'first_activity_latest':str(sales.groupby(rr.KEY).Order_Date.min().max()),'active_pair_calendar_zero_fraction':float(day.eq(0).sum().sum()/day.notna().sum().sum()),'weekly_zero_fraction_2025':float(day.loc['2025-01-01':].resample('W-SUN').sum(min_count=7).eq(0).sum().sum()/day.loc['2025-01-01':].resample('W-SUN').sum(min_count=7).notna().sum().sum()),'stock_ledger_difference_units':int((s.On_Order_Qty-d.groupby(rr.KEY).Incoming_Qty.sum().reindex(s.index,fill_value=0)).abs().sum()),'inbound_total_units':int(d.Incoming_Qty.sum()),'stock_total_units':int(s.Usable_On_Hand_Qty.sum()),'product_names_reliable':len(names),'inventory_field_use':'Transaction Inventory_Level ignored: no trustworthy snapshot grain/time or usable-stock definition; use dedicated stock snapshot instead.','source_provenance':'input-1/2/3 supplied files contain synthetic classifications. User authorized assumed operating scenario. Retained internally; no provenance-only customer columns. input-4 is released development partition; source and released byte hashes differ as declared. No raw originals or December files read.'}
monthly=sales.loc[sales.status.isin(['completed','shipped','returned']) & sales.Quantity.gt(0)].groupby(sales.Order_Date.dt.to_period('M')).Quantity.sum()
stats['seasonal_prior_year_units']={str(k):int(v) for k,v in monthly.items() if k.year<2025 and k.month in (10,11,12)}
Path('source_treatment.json').write_text(json.dumps(stats,indent=2))
print(json.dumps(selected,indent=2)); print(json.dumps(stats,indent=2))
