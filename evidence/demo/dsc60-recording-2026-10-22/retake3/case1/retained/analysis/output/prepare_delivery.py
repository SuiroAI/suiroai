import json, time, resource, sys
from pathlib import Path
import pandas as pd
import numpy as np
import restock_routine as rr

ROOT=Path(__file__).resolve().parent; SRC=ROOT.parent/'released'; date=pd.Timestamp('2025-11-30')
stock,incoming,policy=rr.load_operations(SRC/'input-3.csv',SRC/'input-2.csv',SRC/'input-1.csv',date)
raw,sales=rr.read_sales(SRC/'input-4.csv',date)
panel=rr.daily_panel(sales,policy.index,date)
pred=rr.forecast(panel,date,rr.SELECTED_METHOD)
final_profile=rr.LAST_PROFILE.copy()
names={k:v.Product_Name.dropna().iloc[0] for k,v in raw.groupby('Product_ID') if v.Product_Name.nunique()==1}
expected=rr.make_orders(stock,incoming,policy,pred,names,date)
expected.to_csv(ROOT/'expected_output.csv',index=False,lineterminator='\n')
daily=pd.DataFrame(pred,columns=policy.index,index=pd.date_range('2025-12-01',periods=14))
daily.to_csv(ROOT/'final_forecast_daily.csv',index_label='Forecast_Date')
sens=[]
for label,method,window in [('recent56','recent84',56),('recent84','recent84',84),('recent112','recent84',112)]:
    alternative=rr.make_orders(stock,incoming,policy,rr.forecast(panel,date,method,window=window),names,date)
    sens.append({'variant':label,'total_units':int(alternative.OrderQty.sum()),'positive_order_rows':int(alternative.OrderQty.gt(0).sum()),'rows_different_from_selected':int(alternative.OrderQty.ne(expected.OrderQty).sum()),'absolute_quantity_difference':int((alternative.OrderQty-expected.OrderQty).abs().sum())})
for label,processing,exclude in [('include_processing',True,False),('exclude_all_returns',False,True)]:
    _,s=rr.read_sales(SRC/'input-4.csv',date,include_processing=processing,exclude_returns=exclude)
    alt_panel=rr.daily_panel(s,policy.index,date)
    alternative=rr.make_orders(stock,incoming,policy,rr.forecast(alt_panel,date,rr.SELECTED_METHOD),names,date)
    sens.append({'variant':label,'total_units':int(alternative.OrderQty.sum()),'positive_order_rows':int(alternative.OrderQty.gt(0).sum()),'rows_different_from_selected':int(alternative.OrderQty.ne(expected.OrderQty).sum()),'absolute_quantity_difference':int((alternative.OrderQty-expected.OrderQty).abs().sum())})
summary={'selected_method':rr.SELECTED_METHOD,'order_rows':len(expected),'positive_orders':int(expected.OrderQty.gt(0).sum()),'zero_orders':int(expected.OrderQty.eq(0).sum()),'total_order_units':int(expected.OrderQty.sum()),'prearrival_shortage_rows':int(expected.Expected_Pre_Arrival_Shortage_Units.gt(0).sum()),'coverage_shortage_rows':int(expected.Expected_Coverage_Shortage_Units.gt(0).sum()),'rounding_rows':int(expected.Review_Notes.str.contains('rounding').sum()),'next_week_forecast_units':float(pred[:7].sum()),'sensitivities_not_selection':sens,'final_fit_inference_profile':final_profile,'missing_name_rows_filled_from_unique_product_mapping':int(raw.Product_Name.isna().sum()),'method_limit':'Intermittent forecast smooths purchase size and gaps. Fixed rate cannot anticipate a future seasonal jump; no December validation. Small MAE advantage and negative bias do not establish inventory service benefit.'}
(ROOT/'delivery_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
