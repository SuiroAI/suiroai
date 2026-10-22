"""Independent all-row quantity and time-phasing checks; no forecast helper imports."""
import json,math,hashlib,subprocess,sys
from pathlib import Path
import numpy as np
import pandas as pd

date=pd.Timestamp('2025-11-30')
raw=pd.read_csv('../released/input-4.csv');d=raw.drop_duplicates().copy()
d['date']=pd.to_datetime(d.Order_Date);d['status']=d.Order_Status.str.strip().str.lower()
target=d[(d.Quantity>0)&d.status.isin(['completed','shipped','returned'])].copy()
target['week']=target.date.dt.to_period('W-SUN')
first=d.groupby(['Product_ID','Store_ID']).date.min()
groups=target.groupby(['Product_ID','Store_ID','week']).Quantity.sum()
stock=pd.read_csv('../released/input-3.csv').set_index(['Product_ID','Store_ID'])
policy=pd.read_csv('../released/input-1.csv').set_index(['Product_ID','Store_ID'])
receipts=pd.read_csv('../released/input-2.csv');receipts['due']=pd.to_datetime(receipts.Expected_Arrival_Date)
out=pd.read_csv('restocking.csv',keep_default_na=False)
assert len(out)==336 and not out.duplicated(['Product_ID','Store_ID']).any()
assert (out.OrderQty>=0).all() and (out.OrderQty%1==0).all()
assert not any(x.lower() in ['provenance','synthetic','illustrative'] for x in out.columns)
errors=[]
for _,row in out.iterrows():
 key=(row.Product_ID,row.Store_ID);start=first.loc[key]
 monday=start if start.weekday()==0 else start+pd.Timedelta(days=7-start.weekday())
 weeks=pd.period_range(monday,date,freq='W-SUN')
 series=groups.loc[key].reindex(weeks,fill_value=0).to_numpy()
 positions=np.where(series>0)[0]
 if len(positions):
  amount=series[positions[0]];gap=positions[0]+1.
  for j in range(1,len(positions)):
   amount+=.1*(series[positions[j]]-amount)
   gap+=.1*(positions[j]-positions[j-1]-gap)
  daily=.95*amount/gap/7
 else:daily=0.
 p=policy.loc[key];s=stock.loc[key]
 h=int(p.Supplier_Lead_Time_Days+p.Review_Period_Days);lead=int(p.Supplier_Lead_Time_Days)
 r=receipts[(receipts.Product_ID==key[0])&(receipts.Store_ID==key[1])]
 incoming=int(r.loc[(r.due>date)&(r.due<=date+pd.Timedelta(days=h)),'Incoming_Qty'].sum())
 need=max(0.,daily*h+p.Safety_Stock_Qty-s.Usable_On_Hand_Qty-incoming)
 qty=math.ceil(max(need,p.Minimum_Order_Qty)/p.Order_Multiple_Qty)*p.Order_Multiple_Qty if need>1e-12 else 0
 assert np.isclose(row.Forecast_Next_7_Days,daily*7,atol=1e-6)
 assert np.isclose(row.Net_Need_Before_Rounding,need,atol=1e-6)
 assert row.OrderQty==qty
 assert row.OrderQty==0 or (row.OrderQty>=p.Minimum_Order_Qty and row.OrderQty%p.Order_Multiple_Qty==0)
 before=0.;overall=0.;balance=float(s.Usable_On_Hand_Qty)
 for k in range(1,h+1):
  balance+=float(r.loc[r.due==date+pd.Timedelta(days=k),'Incoming_Qty'].sum())
  if k==lead:balance+=qty
  balance-=daily
  if k<lead:before=max(before,-balance)
  overall=max(overall,-balance)
 assert row.Expected_Shortage_Before_New_Order_Qty==math.ceil(before)
 assert row.Projected_Timing_Shortage_With_Order_Qty==math.ceil(overall)
 assert row.Incoming_Within_Coverage_Qty==incoming
 assert row.Product_Name in set(d.loc[d.Product_ID==key[0],'Product_Name'].dropna())
 errors.append(abs(row.Forecast_Next_7_Days-daily*7))
result=json.loads(Path('result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'}
assert result['output_sha256']==hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
assert Path('restocking.csv').read_bytes()==Path('reference_restocking.csv').read_bytes()
base=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv']
checks=[]
for name,args in [('source_overwrite',['--planning-date','2025-11-30','--output-path','../released/input-4.csv']),('mismatched_date',['--planning-date','2025-11-29','--output-path','should_not_exist.csv']),('invalid_date',['--planning-date','invalid','--output-path','should_not_exist.csv'])]:
 c=subprocess.run(base+args,capture_output=True,text=True)
 assert c.returncode!=0
 checks.append({'case':name,'exit_code':c.returncode,'message':c.stderr.strip()})
assert not Path('should_not_exist.csv').exists()
summary={'independent_rows_checked':len(out),'maximum_forecast_rounding_difference':max(errors),'integer_units_pack_minimum_and_all_shortage_checks':'passed','source_overwrite_and_date_validation':checks,'output_hash_and_byte_agreement':'passed','order_units':int(out.OrderQty.sum()),'products_at_stores_to_order':int((out.OrderQty>0).sum()),'zero_orders':int((out.OrderQty==0).sum()),'pre_arrival_risk_count':int((out.Expected_Shortage_Before_New_Order_Qty>0).sum()),'risk_rows_without_new_order':int(((out.Expected_Shortage_Before_New_Order_Qty>0)&out.OrderQty.eq(0)).sum()),'orders_by_store':out.groupby('Store_ID').OrderQty.sum().to_dict()}
Path('validation_results.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))

profile={'source_authority':'User-authorized released CSV files only; operational files assumed as scenario facts, not independently verified stock.','internal_provenance':{'policy_stock_receipts':'Provenance field is synthetic in all rows, unchanged source bytes','sales':'Released derived development partition SHA256 48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8; original approved artifact SHA256 520fa470ccb7ff5c7d0d8b34d157d15c05c948f7c785e48397ac676bf6cd7707, not accessed. Controller lineage demo-investigation-lineage-048e4cd3fd4344709d8195e77d80942e v1 derived SHA256 399100f9f6fca4f26e5aa9eff6f71c7e3ebc487fa35502d7627f6fabb266cb8e.'},'rows_raw':len(raw),'duplicate_rows_removed':len(raw)-len(d),'unique_transactions':len(d),'nonpositive_rows_excluded':int((d.Quantity<=0).sum()),'target_rows':len(target),'target_total_units':int(target.Quantity.sum()),'status_return_table_after_dedup':d.groupby(['status','Return_Flag']).Quantity.agg(['size','sum']).reset_index().to_dict('records'),'global_calendar_dates':d.date.nunique(),'all_global_calendar_dates_present':True,'pair_first_seen_latest':str(first.max().date()),'pair_zero_treatment':'Conditional complete-extract assumption only after first observed transaction and full weeks. Missing rows become zero recorded units; no assertion of zero latent demand, daily opening, assortment or stock exposure. Not all store dates have transactions. All 336 series observed before development origins. First observation may be later than actual introduction; no prior zeros invented.','status_information_boundary':'Recorded final labels used for targets and training. No status-change/return dates, so cannot reconstruct old as-of labels; identical limitation for all models. Only order dates and calendar features determine splits. These comparisons are development evidence, not untouched or faithful as-of deployment evaluation.','quantity_meaning':'All units are product_unit, not cartons or money. Positive fulfilled/returned orders estimate gross outflow, including later returns. Invalid negative/zero quantities excluded, not silently interpreted as stock credits. Return flags do not establish usable stock recovery; do not subtract them.','order_id_repetition':'Order_ID repeats across legitimate transaction lines; deduplicate exact rows by Transaction_ID, not Order_ID.','names':'135 raw name nulls; each Product_ID has exactly one non-null name, used as reliable dictionary without guessing. No direct customer identifiers in outputs.','inventory_fields':'Transaction Inventory_Level is irregular event-level historical value; not used as current usable stock, stockout exposure or future predictor. Supplied end-of-date stock governs.','cross_file_consistency':'336 unique policy and stock keys exactly match sales population; 126 unique incoming PO lines match every recorded On_Order_Qty, totaling 927 units; all ledger-complete true; single product_unit; no missing critical operational values.','date_convention':'Planning at close of day; day 1 is Dec 1. Existing deliveries and proposed new order available at start of due day. Lead is calendar days because no supplier calendars supplied. Forecast daily rate constant for selected method. Cover lead+review days inclusive through planning+h; only existing receipts due in coverage reduce order. Current stock treated usable immediately; backlog not supplied.','rounding':'OrderQty zero if no need; otherwise ceil(max(net need, minimum)/multiple)*multiple. Safety is supplied quantity, not fitted. New-order timing shortfalls cannot be fixed by increasing regular quantity that arrives later; flagged separately. Deficits use expected fractional daily units then ceil for display; no calibrated stockout probabilities.','unsupported_claims':['No exact incumbent process, hours or savings inferred.','No availability, excess-stock cost optimization, performance success threshold or independent success evidence.','No independent real-stock verification claimed.','No December transactions or external files accessed.']}
Path('source_treatment.json').write_text(json.dumps(profile,indent=2,default=str))
