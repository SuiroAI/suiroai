"""Previously planned diagnostics and operational sensitivity; no new model search."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

R=Path(__file__).parent; S=R.parent/'released'
pred=pd.read_csv(R/'development_predictions.csv')
raw=pd.read_csv(S/'input-4.csv').drop_duplicates(); raw['date']=pd.to_datetime(raw.Order_Date)
raw['status']=raw.Order_Status.str.strip().str.lower()
sales=raw[raw.status.isin(['completed','shipped','returned'])&raw.Quantity.ge(0)]
category=raw.groupby('Product_ID').Product_Category.first()
pred['category']=pred.Product_ID.map(category)
pred.groupby(['method','horizon','category']).absolute_error.agg(['mean','size']).to_csv(R/'category_results.csv')
hist=sales[sales.date.between('2025-09-08','2025-11-30')]
actual=pd.read_csv(R/'restocking.csv',keep_default_na=False)
policy=pd.read_csv(S/'input-1.csv').set_index(['Product_ID','Store_ID'])
active=raw[raw.date.between('2025-09-08','2025-11-30')].groupby('Store_ID').date.nunique()
counts=hist.groupby(['Product_ID','Store_ID']).size()
scenarios=[]
for r in actual.itertuples(index=False):
    # Upper exposure scenario: all absent store dates were unavailable observations, future dates all active.
    # This is NOT an inferred operating calendar and does NOT become the selected forecast.
    scale=84/active[r.Store_ID]
    forecast=r.Forecast_Coverage_Units*scale
    op=policy.loc[(r.Product_ID,r.Store_ID)]
    need=forecast+r.Safety_Stock_Units-r.Usable_Stock_Units-r.Incoming_Within_Coverage_Units
    qty=0 if need<=1e-9 else int(np.ceil(max(need,op.Minimum_Order_Qty)/op.Order_Multiple_Qty)*op.Order_Multiple_Qty)
    scenarios.append(dict(Product_ID=r.Product_ID,Store_ID=r.Store_ID,observed_store_dates_last84=int(active[r.Store_ID]),scaling=scale,selected_order=r.OrderQty,active_dates_scenario_order=qty,recent_pair_rows=int(counts.get((r.Product_ID,r.Store_ID),0))))
scenario=pd.DataFrame(scenarios); scenario.to_csv(R/'coverage_sensitivity.csv',index=False)
selected=pred[pred.method.eq('shrinkage84')]
diagnostics={
 'scope':'Completion of v1 planned diagnostics; no candidate additions, retuning or replacement primary metric.',
 'missingness':{'global_recorded_date_coverage':'1430 of 1430 calendar dates, 2022-01-01 to 2025-11-30. This is not proof of store-day completeness.','store_active_dates_last84':active.to_dict(),'scenario_order_changed_rows':int(scenario.selected_order.ne(scenario.active_dates_scenario_order).sum()),'scenario_total_order_units':int(scenario.active_dates_scenario_order.sum()),'selected_total_order_units':int(scenario.selected_order.sum()),'interpretation':'Upper-exposure scenario assumes absent store days are missing observations and all future days active. If absence means ordinary no-sales or closures, this would overstate need. Selected recorded-calendar throughput assumes future reporting/opening patterns like recent past. Scenario is evidence of sensitivity, not a coverage fact; unknown quantities are not imputed.'},
 'sparsity':{'recent84_no_eligible_sale_pairs':int(scenario.recent_pair_rows.eq(0).sum()),'recent84_at_most_two_rows_pairs':int(scenario.recent_pair_rows.le(2).sum()),'action':'Positive pooled forecasts can remain for pairs without recent sales; review quiet items before committing to pack/minimum-size purchases. All pairs have earlier eligible history.'},
 'uncertainty':{str(h):{'absolute_error_quantiles':g.absolute_error.quantile([.5,.8,.9,.95]).to_dict(),'underprediction_share':float(g.error.lt(0).mean()),'interpretation':'Pooled development residual distribution, not pair-specific prediction intervals or guaranteed service levels.'} for h,g in selected.groupby('horizon')},
 'annual_seasonality':'November recorded-unit total exceeds October in all four years (ratios in selection_evidence.json); nevertheless seasonal Poisson did worse on next-week primary MAE. Only three earlier Decembers available; current December not accessed. No assumption that aggregate seasonality is stable in each sparse pair.',
 'pooling':'Product/store independence shares evidence across sparse pairs; not proof each store carries every item historically. Current population and sales keys match; no historical ranging dates. No future information in origin fits.',
 'selection_sensitivity':'shrinkage84 wins all eight leave-one-origin-out averages; loses to previous-month on four individual origins. Primary improvement 1.3%, bootstrap difference crosses zero. Return-exclusion sensitivity and fully observed subset retain the same winner. Store/category results vary: inspect csvs; no blanket superiority claim.',
 'horizon_alignment':'Primary selection next 7 days, deployment 8-14 days according to supplied rules. Both 14-day and variable-coverage secondary MAE also favor the same method; no winner mismatch. November 30 rules are not asserted to have applied historically.',
 'success_gate':'Not closed: external meaningful threshold absent and no untouched independent evaluation; all scores development-only.',
 'operating_assumptions':{'planning_date':'End of 2025-11-30. Existing receipts arrive and become usable at start of due day; new order at start of planning date plus supplied lead time. Daily expected demand is uniform for selected model.','order_formula':'Round max(0, coverage forecast + supplied safety stock - usable stock - dated existing receipts through coverage end) to supplied minimum and multiple. On-order total is checked against ledger, never deducted twice. Receipts after coverage are excluded.','timing':'Projection includes new recommended order on its assumed arrival date; earlier deficits require acceleration or an available transfer. End coverage balance reaches supplied safety stock but temporary shortages can still occur. Quantities of projected shortages are fractional expectations, not certain lost sales.','safety':'Use supplied absolute safety stock; no invented service level or economic objective. No policy redesign.'}
}
(R/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
print(json.dumps(diagnostics['missingness'],indent=2));print(diagnostics['sparsity'])
