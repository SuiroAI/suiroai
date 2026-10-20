"""Inference-only freeze. Run with /opt/anaconda3/bin/python generate_freeze.py.
Never imports or executes supplied development programs; never fits shrink26.
Writes only beside this program. Input allowlist is explicit and hash-pinned.
"""
from pathlib import Path
import hashlib, json, sys, time, platform
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / 'released'
EXPECTED = {
 'input-1.csv': ('development_source','333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6'),
 'input-2.csv': ('development_source','1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a'),
 'input-3.csv': ('development_source','3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9'),
 'input-4.csv': ('development_source','48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8'),
 'selected_model.npz': ('selected_model','93219f444604d55aa000ba36f7ff4ac8eb89ae0da11874e505e0d73ec4ce377e'),
 'restock_model.py': ('model_code','b6fabfe363c3271485c612e8ba7b38bdac74d79bdefe8c6b5453ded9d4f4403e'),
 'prepare.py': ('preprocessing_code','2196d3902cd327dd52967a54ff9438b3109c694dccd51e296572427dfa8092a9'),
 'analysis.py': ('analysis_code','2fdf077e2e0aa2f1f7dfd7b00fb870bbba3c0dba054bd8b5b1531ac0c51f7188'),
 'task_refinement.json': ('feature_definition','70d162c1adaa4816633723f15cc29f90c0ed56e0f76352c5402ca28af91744d4'),
 'evaluation_plan.json': ('evaluation_plan_v1','954c799bd19942d3813fb15932794008daa9155eeb4dade6c93cf0d73741d0cb'),
 'evaluation_plan_v2.json': ('evaluation_plan_v2','ecb257e9f957201741d47cae392654598a5c50f71f5ccea6bb5a6dd27f9a10e0'),
 'implementation_correction.json': ('implementation_correction','d33c2964c92c6664d780bfe1fdd28c76562705210309728ada0d5ee33413f8f6'),
 'routine_workload.json': ('dependencies','f545cb7286a57d9475034d7d0a1aa0ff2c18c00268468c726adf0553719a1d44')}
K = ['Product_ID','Store_ID']
STAMP = '2025-11-30'
ORIGIN = pd.Timestamp(STAMP)
FIXED = ['model',*K,'as_of_date','origin','target_start','target_end','horizon_days','forecast_units']
DAILY = ['model',*K,'as_of_date','origin','date','forecast_units']
COVERAGE = FIXED.copy()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n, v): (ROOT/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def main():
 started = datetime.now(timezone.utc).isoformat(); tic = time.perf_counter()
 events = []
 def event(s):
  events.append({'event':s,'utc':datetime.now(timezone.utc).isoformat()})
  print(s,flush=True)
 assets = ROOT/'assets'; assets.mkdir(exist_ok=True)
 artifacts=[]
 for name,(role,digest) in EXPECTED.items():
  source=SRC/name
  assert sha(source)==digest, f'Source identity mismatch: {name}'
  copied=assets/name
  if copied.exists(): assert sha(copied)==digest
  else: copied.write_bytes(source.read_bytes())
  assert sha(copied)==digest
  artifacts.append({'path':'assets/'+name,'role':role,'sha256':digest})
 event('Verified and copied all 13 supplied artifacts byte-for-byte')
 p=pd.read_csv(assets/'input-1.csv').sort_values(K).reset_index(drop=True)
 i=pd.read_csv(assets/'input-3.csv'); receipts=pd.read_csv(assets/'input-2.csv')
 assert len(p)==336 and not p.duplicated(K).any()
 population=p[K].to_dict('records'); pairs=pd.MultiIndex.from_frame(p[K])
 assert not i.duplicated(K).any() and set(map(tuple,i[K].values))==set(pairs)
 assert p.Effective_Date.eq(STAMP).all() and i.Snapshot_Date.eq(STAMP).all()
 assert pd.to_datetime(receipts.Order_Date).le(ORIGIN).all()
 assert pd.to_datetime(receipts.Expected_Arrival_Date).gt(ORIGIN).all()
 with np.load(assets/'selected_model.npz',allow_pickle=False) as m:
  assert set(m.files)=={'weekly_recorded_units',*K}
  assert list(zip(m['Product_ID'].tolist(),m['Store_ID'].tolist()))==list(pairs)
  selected=m['weekly_recorded_units'].copy()
 assert selected.shape==(336,) and np.isfinite(selected).all() and (selected>=0).all()
 raw=pd.read_csv(assets/'input-4.csv')
 d=raw.drop_duplicates().copy()
 assert not d.Transaction_ID.duplicated().any(), 'Conflicting transaction IDs: do not silently choose a line'
 assert not d[K+['Transaction_ID','Order_Date','Quantity','Order_Status','Return_Flag']].isna().any().any()
 d['date']=pd.to_datetime(d.Order_Date)
 assert d.date.max()==ORIGIN and d.date.le(ORIGIN).all()
 assert set(map(tuple,d[K].values))==set(pairs)
 d['status']=d.Order_Status.str.strip().str.lower()
 d['week']=d.date.dt.to_period('W-SUN').dt.start_time
 first=d.groupby(K).date.min().reindex(pairs)
 assert first.lt(pd.Timestamp('2025-10-05')).all()
 H=(p.Supplier_Lead_Time_Days+p.Review_Period_Days).to_numpy()
 assert np.isfinite(H).all() and (H==H.astype(int)).all() and ((H>=8)&(H<=14)).all()
 protocol={
  'format':'dsc60-final-freeze-protocol-v1','as_of_date':STAMP,'origin':STAMP,
  'selected_model':'shrink26','baseline_model':'recent13','population':population,
  'target_definition': 'Product units, all store-attributed channels: remove exact duplicate full rows first, then require unique Transaction_ID (conflicts stop evaluation); retain repeated Order_ID as distinct transaction lines. Parse Order_Date as calendar date, normalize Order_Status by strip/lower. Sum Quantity strictly >0 with status != cancelled, including processing and returned regardless of Return_Flag; no return reuse credit. Observed recording day means any deduplicated source transaction at that Store_ID/date before quantity/status filtering. At an observed store-day a missing product contribution is zero recorded units. Absent store-days remain unknown; target is the sum of eligible recorded contributions over observed days only, without rescaling. No complete-demand, stockout, lost-sales or historically-known-status assertion. Use supplied final statuses; knowledge/update timestamps are unavailable.',
  'baseline_definition': 'recent13 exactly as analysis.py: last 13 complete Monday-Sunday calendar weeks ending at origin, 2025-09-01..2025-11-30 inclusive. Build weekly per-key eligible recorded-unit sums. A key/week is known only if week start is strictly after the key first transaction date and the store has any deduplicated transaction in that week. Known weeks with no eligible product contribution have zero; unknown weeks are NaN. Arithmetic nanmean over these 13 calendar positions, not the last 13 observed weeks; no zero filling unknown store-weeks, no denominator 13 when weeks are missing. Freeze resulting weekly rate at origin; every future day = weekly rate / 7, no seasonal adjustment. shrink26 uses only the supplied full-precision weekly_recorded_units and saved IDs, with the same daily allocation; no fit or reselection.',
  'primary_metric': 'Equal-key/window seven-day recorded-unit MAE: sum abs(forecast_units - recorded_units) over common eligible key/week cells divided by their count, pooling the four nonoverlapping December weeks. No unit-volume, price, service or stock weighting; not an equal average of weekly MAEs when eligible counts differ.',
  'coverage_rule': 'Forecast every one of the 336 fixed current policy keys for both methods. Evaluation eligibility is identical: a key/window is eligible if that store has >=1 observed recording day in the window (all fixed keys are historically observed before origin). Exclude an entirely unobserved store-window for both; never infer a demand zero from absence. Retain partial observed windows without rescaling. Report each excluded key/window and reason, observed day counts 0..7, eligible counts and eligible/(336*4) overall and eligible/336 per week; also complete-7-observed-day subset. Date presence does not prove complete demand. Diagnostic coverage totals use origin+1 through origin+(Supplier_Lead_Time_Days+Review_Period_Days), inclusive, 8..14 days; supplied current synthetic policy is not historical policy. Known operational future due dates are not sales outcomes.',
  'evaluation_rule': 'All predictions issued at fixed 2025-11-30; no later information, rolling update or refit. Primary windows inclusive: 2025-12-01..07, 08..14, 15..21, 22..28. MVP question: does this fixed shrink26 have lower pooled absolute weekly recorded-unit forecast error than frozen recent13 on common eligibility? Report both MAEs, paired MAE difference selected minus baseline, relative difference (MAE_selected/MAE_baseline - 1; if baseline=0 report undefined and absolute difference), per-week MAE, bias mean(forecast-actual), eligible counts, all exclusions and recording/population coverage. Strictly lower error answers yes; no invented 5% gate. Exact ties do not establish improvement. If candidate loses report failure and retain baseline option; no runner-up promotion, target/metric change or tuning. Descriptive uncertainty: paired week-cluster bootstrap, seed 603, 2000 resamples of four weeks with replacement, recompute pooled paired error difference from summed errors/counts, 2.5/97.5 percentiles; four weeks and cross-key dependence limit interpretation, no superiority guarantee. Complete-store-week subset and lead-plus-review, last three days and month totals are secondary only. No purchasing savings or service-level claim. This call emits no outcomes or accuracy scores. Broader typed DSC28 acceptance/completeness contract remains separate; no parent-contract or final-approval flags are manufactured.',
  'artifacts':artifacts}
 # Mandatory ordering: protocol is persisted and read back BEFORE any forecast generation.
 protocol_path=ROOT/'protocol.json'
 if protocol_path.exists():
  assert json.loads(protocol_path.read_text())==protocol, 'Existing freeze differs; refusing to overwrite'
 else: save('protocol.json',protocol)
 assert json.loads(protocol_path.read_text())==protocol
 protocol_digest=sha(protocol_path)
 event('protocol.json persisted and verified BEFORE generating forecasts')
 weeks=pd.date_range('2025-09-01','2025-11-24',freq='W-MON')
 stores=p.Store_ID.unique(); si=pd.Categorical(p.Store_ID,categories=stores).codes
 obs=d.groupby(['week','Store_ID']).date.nunique().unstack().reindex(index=weeks,columns=stores)
 known=(weeks.to_numpy()[:,None]>first.to_numpy()[None,:]) & np.isfinite(obs.to_numpy()[:,si])
 valid=d[(d.Quantity>0)&d.status.ne('cancelled')]
 hist=valid.groupby(['week']+K).Quantity.sum().unstack(K).reindex(index=weeks,columns=pairs).fillna(0).to_numpy(float)
 hist[~known]=np.nan
 baseline=np.nanmean(hist,axis=0)
 # Alternate scalar reconstruction of original baseline on every key, not another model.
 alternate=[]
 for key in pairs:
  vals=[]
  for w in weeks:
   end=w+pd.Timedelta(days=6)
   if w>first.loc[key] and ((d.Store_ID==key[1])&d.date.between(w,end)).any():
    vals.append(valid.loc[(valid.Product_ID==key[0])&(valid.Store_ID==key[1])&valid.date.between(w,end),'Quantity'].sum())
  alternate.append(float(np.mean(vals)))
 baseline_delta=float(np.max(np.abs(baseline-np.array(alternate))))
 assert baseline_delta<1e-12, 'Original recent13 reconstruction mismatch'
 rates={'shrink26':selected,'recent13':baseline}
 frozen_rates=p[K].copy()
 frozen_rates['shrink26_weekly_recorded_units']=selected
 frozen_rates['recent13_weekly_recorded_units']=baseline
 frozen_rates['recent13_observed_weeks']=known.sum(axis=0)
 frozen_rates.to_csv(ROOT/'frozen_rates.csv',index=False,float_format='%.17g')
 frows=[]; drows=[]; crows=[]
 for model,rate in rates.items():
  assert np.isfinite(rate).all() and (rate>=0).all()
  for j,(product,store) in enumerate(pairs):
   daily=rate[j]/7
   for date in pd.date_range('2025-12-01','2025-12-31'):
    drows.append([model,product,store,STAMP,STAMP,str(date.date()),daily])
   for start in pd.date_range('2025-12-01',periods=4,freq='7D'):
    frows.append([model,product,store,STAMP,STAMP,str(start.date()),str((start+pd.Timedelta(days=6)).date()),7,rate[j]])
   h=int(H[j])
   crows.append([model,product,store,STAMP,STAMP,'2025-12-01',str((ORIGIN+pd.Timedelta(days=h)).date()),h,float(np.sum(np.repeat(daily,h)))])
 for name,rows,cols in [('fixed_forecasts.csv',frows,FIXED),('daily_forecasts.csv',drows,DAILY),('coverage_forecasts.csv',crows,COVERAGE)]:
  pd.DataFrame(rows,columns=cols).to_csv(ROOT/name,index=False,float_format='%.17g')
 event('Wrote full-precision weekly, daily and lead-plus-review forecasts')
 fixed=pd.read_csv(ROOT/'fixed_forecasts.csv',float_precision='round_trip')
 daily=pd.read_csv(ROOT/'daily_forecasts.csv',float_precision='round_trip')
 cov=pd.read_csv(ROOT/'coverage_forecasts.csv',float_precision='round_trip')
 for frame,cols,n in [(fixed,FIXED,2688),(daily,DAILY,20832),(cov,COVERAGE,672)]:
  assert list(frame.columns)==cols and len(frame)==n
  assert frame.model.isin(rates).all() and set(frame.model)==set(rates)
  assert frame.as_of_date.eq(STAMP).all() and frame.origin.eq(STAMP).all()
  assert np.isfinite(frame.forecast_units).all() and frame.forecast_units.ge(0).all()
  assert not frame.duplicated([c for c in cols if c!='forecast_units']).any()
  for name in rates:
   assert set(map(tuple,frame.loc[frame.model==name,K].values))==set(pairs)
 assert fixed.horizon_days.eq(7).all()
 assert set(zip(fixed.target_start,fixed.target_end))=={(f'2025-12-{s:02}',f'2025-12-{s+6:02}') for s in [1,8,15,22]}
 assert set(daily.date)==set(pd.date_range('2025-12-01','2025-12-31').strftime('%Y-%m-%d'))
 assert daily.groupby(['model']+K).size().eq(31).all()
 assert fixed.groupby(['model']+K).size().eq(4).all()
 dg={key:g for key,g in daily.groupby(['model']+K)}
 weekly_error=0.; coverage_error=0.
 for frame,is_weekly in [(fixed,True),(cov,False)]:
  for row in frame.itertuples(index=False):
   block=dg[(row.model,row.Product_ID,row.Store_ID)]
   b=block.loc[block.date.between(row.target_start,row.target_end),'forecast_units']
   assert len(b)==row.horizon_days
   diff=abs(float(b.sum())-row.forecast_units)
   assert diff<=1e-9
   if is_weekly: weekly_error=max(weekly_error,diff)
   else:
    j=pairs.get_loc((row.Product_ID,row.Store_ID))
    assert row.horizon_days==H[j] and row.target_start=='2025-12-01'
    assert row.target_end==str((ORIGIN+pd.Timedelta(days=int(H[j]))).date())
    coverage_error=max(coverage_error,diff)
 # Check serialized weekly predictions exactly preserve the saved float64 rates.
 for model,rate in rates.items():
  for start,g in fixed[fixed.model==model].groupby('target_start'):
   assert np.array_equal(g.set_index(K).reindex(pairs).forecast_units.to_numpy(),rate)
 for name,(_,digest) in EXPECTED.items():
  assert sha(SRC/name)==sha(assets/name)==digest
 assert sha(protocol_path)==protocol_digest
 event('All generation checks passed; selected model and sources unchanged')
 audit=p[K].copy()
 audit['eligible_training_weeks']=known.sum(axis=0)
 audit['unknown_training_weeks']=13-known.sum(axis=0)
 audit.to_csv(ROOT/'baseline_coverage.csv',index=False)
 excluded=[]
 for wi,j in zip(*np.where(~known)):
  excluded.append([pairs[j][0],pairs[j][1],str(weeks[wi].date()),str((weeks[wi]+pd.Timedelta(days=6)).date()),'no_observed_store_week' if not np.isfinite(obs.to_numpy()[wi,si[j]]) else 'week_not_strictly_after_first_key_observation'])
 pd.DataFrame(excluded,columns=K+['week_start','week_end','reason']).to_csv(ROOT/'baseline_exclusions.csv',index=False)
 dependencies={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__}
 source_deps=json.loads((assets/'routine_workload.json').read_text())['dependencies']
 checks={
  'status':'passed','scope':'Author-generated execution checks; not independent validation or final business acceptance',
  'checks':{'saved_ids_equal_sorted_current_policy_and_stock':True,'source_and_copied_model_hash_before_and_after':True,'all_13_source_and_copy_identities':True,'no_sales_after_cutoff':True,'protocol_written_before_predictions':True,'protocol_unchanged_during_generation':True,'exact_output_schemas_and_population':True,'exact_date_boundaries':True,'finite_nonnegative':True,'full_precision_selected_weekly_values_preserved':True,'weekly_daily_sums_within_1e-9':True,'coverage_daily_sums_within_1e-9':True,'baseline_reconstructed_from_original_definition':True},
  'selected_model_sha256':EXPECTED['selected_model.npz'][1], 'protocol_sha256':protocol_digest,
  'population':336,'forecast_population_coverage':{'shrink26':'336/336','recent13':'336/336'},
  'forecast_exclusions':[], 'evaluation_eligibility':'Unmeasured until reserved outcomes are released; do not equate forecast coverage to observed evaluation coverage',
  'counts':{'fixed_forecasts':len(fixed),'daily_forecasts':len(daily),'coverage_forecasts':len(cov),'raw_development_rows':len(raw),'deduplicated_rows':len(d),'exact_duplicate_rows_removed':len(raw)-len(d),'conflicting_transaction_ids':0,'target_included_rows':len(valid),'nonpositive_quantity_rows_excluded':int(d.Quantity.le(0).sum()),'cancelled_rows_excluded':int(d.status.eq('cancelled').sum()),'union_target_excluded_rows':int(((d.Quantity<=0)|d.status.eq('cancelled')).sum())},
  'development_dates':{'min':str(d.date.min().date()),'max':str(d.date.max().date()),'post_cutoff_sales_rows':0},
  'baseline_training':{'calendar_weeks':13,'start':'2025-09-01','end':STAMP,'known_pair_weeks':int(known.sum()),'unknown_pair_weeks_excluded':int((~known).sum()),'observed_weeks_per_pair_min':int(known.sum(axis=0).min()),'observed_weeks_per_pair_max':int(known.sum(axis=0).max()),'alternate_computation_max_abs_difference':baseline_delta},
  'max_abs_weekly_daily_difference':weekly_error,'max_abs_coverage_daily_difference':coverage_error,
  'source_dependency_record':source_deps,'execution_dependencies':dependencies,
  'dependency_version_matches':{k:dependencies[k]==v for k,v in source_deps.items()},
  'outputs':[{'path':n,'sha256':sha(ROOT/n)} for n in ['fixed_forecasts.csv','daily_forecasts.csv','coverage_forecasts.csv','frozen_rates.csv','baseline_coverage.csv','baseline_exclusions.csv']],
  'program_sha256':sha(Path(__file__)), 'input_artifacts':artifacts}
 save('freeze_checks.json',checks)
 save('internal_provenance.json',{'scope':'Internal evaluation provenance only','qualification':'Earlier project AI sessions saw pooled full-history summaries. December is not certified globally pristine or untouched. This call accessed only the authorized released November-ending inputs and generated pre-release forecasts; no December transaction outcomes were accessed. Legacy preserved plans contain older untouched-boundary statements; those are historical source bytes, not a certification by this freeze.','contract':'Broader typed DSC28 completeness/acceptance contract remains separate; no authentic parent-contract or final-approval flags are asserted.'})
 save('execution_evidence.json',{'command':'/opt/anaconda3/bin/python generate_freeze.py','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.perf_counter()-tic,'events':events,'platform':platform.platform(),'dependencies':dependencies,'program_sha256':sha(Path(__file__)),'protocol_sha256':protocol_digest,'checks_sha256':sha(ROOT/'freeze_checks.json'),'execution_status':'completed'})
 print(json.dumps({'status':'passed','fixed_rows':len(fixed),'daily_rows':len(daily),'coverage_rows':len(cov),'baseline_unknown_pair_weeks':int((~known).sum()),'dependency_version_matches':checks['dependency_version_matches']}),flush=True)

if __name__=='__main__': main()
