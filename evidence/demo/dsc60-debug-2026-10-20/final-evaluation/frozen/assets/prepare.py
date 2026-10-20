"""Source-only inspection and prospective plans. No candidate scores."""
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib
ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'released'
def write(name,obj): (ROOT/name).write_text(json.dumps(obj,indent=2,default=str)+'\n')
p=pd.read_csv(SRC/'input-1.csv'); r=pd.read_csv(SRC/'input-2.csv'); i=pd.read_csv(SRC/'input-3.csv'); raw=pd.read_csv(SRC/'input-4.csv')
d=raw.drop_duplicates().copy(); d['date']=pd.to_datetime(d.Order_Date); d['status']=d.Order_Status.str.strip().str.lower()
keys=['Product_ID','Store_ID']; calendar=pd.date_range(d.date.min(),d.date.max())
assert d.date.max()==pd.Timestamp('2025-11-30')
assert not d.Transaction_ID.duplicated().any()
assert not p.duplicated(keys).any() and not i.duplicated(keys).any()
assert set(map(tuple,p[keys].values))==set(map(tuple,i[keys].values))==set(map(tuple,d[keys].values))
inc=r.groupby(keys).Incoming_Qty.sum().reindex(pd.MultiIndex.from_frame(i[keys]),fill_value=0).to_numpy()
assert np.array_equal(inc,i.On_Order_Qty.to_numpy())
assert r.PO_Line_ID.is_unique and (r.Order_Date<='2025-11-30').all() and (r.Expected_Arrival_Date>'2025-11-30').all()
for df in [p,i,r]: assert df.Quantity_Unit.eq('product_unit').all() and df.Provenance.eq('synthetic').all()
assert (i.Usable_On_Hand_Qty>=0).all() and (r.Incoming_Qty>0).all() and i.Open_Order_Ledger_Complete.all()
assert (p.Order_Multiple_Qty>0).all() and (p.Minimum_Order_Qty>=0).all() and (p.Safety_Stock_Qty>=0).all()
assert d.groupby('Product_ID').Product_Name.nunique().max()==1
valid=d[(d.Quantity>0)&d.status.ne('cancelled')].copy()
store_days=d.groupby('Store_ID').date.nunique()
source_audit={
 'inputs':[{ 'file':x.name,'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(SRC.glob('*.csv'))],
 'rows_raw':len(raw),'rows_deduplicated':len(d),'exact_duplicates_removed':len(raw)-len(d),'conflicting_transaction_ids':int(d.Transaction_ID.duplicated().sum()),
 'repeated_order_ids_retained_as_distinct_transaction_lines':int(d.Order_ID.duplicated().sum()),
 'date_min':str(d.date.min().date()),'date_max':str(d.date.max().date()),'network_missing_dates':len(calendar.difference(d.date.unique())),
 'store_observed_dates':store_days.to_dict(),'calendar_days':len(calendar),
 'missing_core_fields':d[['Transaction_ID','Product_ID','Store_ID','Order_Date','Quantity','Order_Status','Return_Flag']].isna().sum().to_dict(),
 'normalized_status_counts':d.status.value_counts().to_dict(),'return_status_cross_tab':pd.crosstab(d.status,d.Return_Flag).to_dict(),
 'quantity_nonpositive_rows':int((d.Quantity<=0).sum()),'negative_quantity_rows':int((d.Quantity<0).sum()),'cancelled_rows':int(d.status.eq('cancelled').sum()),
 'gross_target_rows':len(valid),'gross_target_units':int(valid.Quantity.sum()),
 'return_flagged_positive_noncancelled_units':int(valid.loc[valid.Return_Flag.eq('Yes'),'Quantity'].sum()),
 'processing_positive_units':int(valid.loc[valid.status.eq('processing'),'Quantity'].sum()),
 'population':len(p),'products':p.Product_ID.nunique(),'stores':p.Store_ID.nunique(),'latest_pair_first_observation':str(d.groupby(keys).date.min().max().date()),
 'product_names_consistent':True,'missing_product_name_rows':int(d.Product_Name.isna().sum()),'stock_receipt_mismatches':int((inc!=i.On_Order_Qty).sum()),
 'stock_policy_ledger_provenance':'All synthetic: illustrative purchase quantities, not verified business stock or constraints.',
 'source_treatment':{
  'grain':'Unique Transaction_ID is a transaction line; repeated Order_ID is not proof of duplicate demand.',
  'target':'Gross positive noncancelled recorded order units, all store-attributed channels; includes processing, shipped, completed, returned. Returned goods needed supply initially; return condition/timing unavailable, so no automatic reuse credit. Invalid nonpositive quantities excluded, not interpreted as usable returns.',
  'status_boundary':'Statuses are normalized. No knowledge/update timestamps: the replay uses final supplied statuses, cannot certify an exact historically available replay. Order dates and quantities only as predictors; no future status, inventory, price, rating, delivery, customer or outcome features.',
  'missing_dates':'No store-day demand zeros are imputed. A store-day with any source transaction establishes an observed recording day. Product contributions on those days can be zero recorded units. Absent store-days remain unknown, not demand zeros. Weekly/horizon targets sum observed contributions only; an entirely unobserved store-week remains missing. Thus forecasts describe recorded units under similar recording coverage, not uncensored demand or store-open exposure.',
  'population':'336 supplied current policy/stock pairs. Verify all were observed before first development origin; no historical active-assortment table. This is conditional on the supplied current assortment, not a claim of unbiased historical assortment selection.',
  'inventory':'Use November 30 usable stock only. Ignore transaction Inventory_Level: repeated transaction snapshots, missing values, unknown availability and definition; cannot reconstruct historical stockouts.',
  'names':'One nonmissing name per product, fill from consistent mapping; no customer identifiers exported.',
  'quantities':'All product units. Stock, safety, pack, minimum nonnegative integers, lead 1-7 days, review 7. Incoming ledger completely matches on-order totals.'
 }}
write('source_audit.json',source_audit)
context={ 'current_process':{'evidence':[{'quote':'I usually look at the last few months of sales to decide what to buy.','source':'question'}],'source':'detector_interpretation','status':'found','text':'The user wants to decide what to restock in stores next week. Their current procedure is to look at the last few months of sales to decide what to buy. The question explicitly describes this practice, but does not specify a calculation or precise ordering rule.'},'format':'dsc60-task-context-v1','original_question':'What should I restock in my stores next week? I usually look at the last few months of sales to decide what to buy.'}
write('task_refinement.json',{
 'original_question':context['original_question'],'customer_context':context,
 'attribution':'Refined analytical task authored by the Data analysis; supplied question and customer_context preserved separately and unchanged.',
 'decision':{'unit':'product at store','planning_as_of':'2025-11-30','next_week':'2025-12-01 through 2025-12-07','action':'Nonnegative integer units to order now, respecting supplied pack and minimum; zero where supported. No purchases placed.','outcomes':'Support availability while avoiding unnecessary purchasing. Relative priorities, service targets, lost-sales costs and holding costs are unknown; no optimization of these outcomes is claimed.'},
 'facts':['Customer uses recent months of sales without an exact ordering rule.','Released sales end November 30, 2025.','Current stock, incoming deliveries and policy supplied, all labeled synthetic.'],
 'supported_interpretations':['Forecast future sales as an input to stock coverage, rather than simply rank past best sellers.','Gross units are closer to replenishment needs than net revenue or subtracting unspecified returned stock.'],
 'synthetic_controller_assumptions':['336 synthetic inventory/policy rows and 126 synthetic incoming lines permit an illustrative order calculation only.','Planning date and untouched December boundary are controller scope.'],
 'analyst_assumptions':['All channels assigned to Store_ID draw on that store; cannot prove fulfillment linkage.','Recorded-unit subtotal forecasts use a recording process similar to training; missing sales could make them too low.','New orders placed November 30 arrive after the supplied lead time; existing receipts arrive on their stated dates.','Translate the forecast through lead plus review coverage using supplied safety stock. No additional service target or economic cost is invented.'],
 'unresolved':['True missing-date coverage and stockout-censored demand','When historical statuses became known','Whether returned units are usable','Real business stock/policy accuracy','Exact incumbent buying rule','Availability versus excess-stock priorities, budget and economic costs'],
 'refined_task':'Compare a fixed, bounded set of lightweight non-LLM recorded-unit forecasts on common time-ordered development origins; select by predeclared next-week absolute-unit error, show longer-coverage and target sensitivities, and apply supplied synthetic stock, receipts, safety and pack constraints to an illustrative list. Quantify actual local workload, uncertainty and limits; do not claim business savings or independent success.',
 'incumbent_evaluation':'Exact customer process cannot be replayed: lookback length, aggregation, adjustments and quantity rule absent. Preserve this as an unevaluable descriptive incumbent; recent-13-week average is an analytical baseline only.',
 'candidate_rationale':[
 {'name':'recent13','method':'13 complete calendar weeks mean of observed recorded subtotals for each pair','evidence':'Question references recent months; input-4 spans almost four years. Stable simple baseline; no exact incumbent asserted.'},
 {'name':'ses','method':'Per-pair simple exponential smoothing, alpha=0.15, initialize first 13 observed weeks; 104-week training','evidence':'input-4 monthly unit totals vary over time. Recency adaptation can react more quickly than a fixed average; one fixed smoothing weight, no tuning.'},
 {'name':'shrink26','method':'26-week pair rates shrunk toward product-by-store independent pooled rates with 13-week prior strength','evidence':'inspect_sources.py shows 336 sparse series with only 14-121 lines over the whole history; pooling reduces noisy local estimates.'},
 {'name':'poisson_calendar','method':'L2 regularized pooled Poisson regression, product/store main effects, annual Fourier harmonics 1 and 2, linear time; alpha=0.01, max_iter=300, 104-week fit','evidence':'input-4 shows higher November/December totals repeatedly in 2022-24. Pooling supports sparse series; calendar features allow modest recurring seasonality without per-series seasonal overfit. Nonnegative integer-unit target suits a Poisson mean model, not a claim of Poisson uncertainty.'}],
 'scope':'No neural models, ensembles, unbounded search, policy redesign or paid API at routine runtime. Dense small factor design and a few hundred weekly series fit practical CPU-only discovery; measure preparation, fits, inference and retained process memory.',
 'success_gate':{'ready':False,'reason':'October-November already inspected; development only. No externally predeclared meaningful gain threshold and no untouched evaluation with frozen artifacts. December never accessed.'}})
origins=[str(x.date()) for x in pd.date_range('2025-10-05','2025-11-16',freq='W-SUN')]
write('evaluation_plan.json',{
 'version':1,'written_before_candidate_scores':True,'status':'development; never independent holdout','previous_development_evidence':'Source-only inspection in inspect_sources.py and inspect_coverage.py, including monthly totals; October-November was already inspected in this project by controller notice.',
 'target':source_audit['source_treatment']['target'],'missing_date_rule':source_audit['source_treatment']['missing_dates'],'population_rule':source_audit['source_treatment']['population'],
 'dates':{'origins':origins,'training':'Only dates <= each origin. recent13=13 complete weeks, shrink26=26, SES/Poisson=104. Whole aligned Monday-Sunday weeks only; first partial week excluded.','evaluation':'2025-10-06 through 2025-11-30, depending on horizon','reserved':'December 2025 never read or scored'},
 'horizons':{'primary_days':7,'secondary_days':'Per pair lead plus review, 8-14 days; supplied current policy used as a diagnostic scenario, not known historical policy. Same origins for all methods.','forecast_shape':'Constant weekly rates within each week; Poisson calendar features evaluated separately for future calendar weeks; partial-week proportional daily allocation.'},
 'baseline':'recent13','candidates':['recent13','ses','shrink26','poisson_calendar'],'candidate_specs':'See task_refinement.json; no adaptive tuning or subsequent candidate search planned.',
 'primary_metric':{'name':'MAE','units':'absolute recorded product units per product at store per next-week origin','weighting':'Equal weight per eligible pair and origin; no price, cost, missing-stock or service weights.','justification':'Order quantities are in units. Absolute errors remain interpretable and less dominated by rare bulk lines than squared error; symmetric proxy does not establish a preferred under/overstock tradeoff.'},
 'selection_rule':'Lowest pooled next-7-day MAE. Numerical ties within 1e-9 units favor baseline, otherwise candidate order as listed. No claimed business-meaningful threshold. Longer horizon remains a disclosed diagnostic, not a changed primary criterion.',
 'secondary_diagnostics':['Coverage-horizon MAE, bias and WAPE','Per-origin results and October/November stability','Zero contribution frequency on observed store-days, sparse series strata and complete-store-week subset','Across-origin paired bootstrap 95% interval for MAE difference, seed 603, 2000 resamples; development uncertainty only','Exclude processing and exclude returns target sensitivity using same candidates, origins and primary metric, exploratory; do not reselect','Prior-year seasonal stability; no December 2025','Deploy baseline and selected forecast order sensitivity with same stock and policy','Runtime, CPU, peak RSS and array sizes, including prep and fitting/inference'],
 'coverage_exclusions':'Entire unobserved store-weeks excluded, not filled. Horizon subtotals with zero observed store-days unknown and excluded identically across models. Also report complete 7-day store coverage subset.',
 'quantity_rule':'target=coverage forecast + supplied safety; net need=max(0,target-usable stock-known receipts due by coverage end); if positive, ceil(max(minimum,net need)/pack)*pack. Order to cover lead+review. Flag projected stock shortfall before new order arrival; no expedited-order redesign.',
 'workload':'One bounded 4-method comparison, seven rolling origins, plus prespecified target sensitivities and final fits. CPU only. Measure end-to-end and fit/inference local time, process peak RSS; actual host not assumed 8GB. No paid routine model calls.',
 'revision_policy':'Retain this plan and scores. Any new candidate comparison requires a prospective versioned plan and is exploratory. No search-until-gain. No reserved outcomes.'})
print('Prepared source_audit.json, task_refinement.json and evaluation_plan.json before scoring.')
