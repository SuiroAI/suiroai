"""Frozen selection sensitivity and independent arithmetic validation, no candidate revision."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import json,sys,math,hashlib,time
from pathlib import Path
import numpy as np,pandas as pd
import scipy,sklearn
from restock_routine import load_sales,forecast,SELECTED,run

P=Path(sys.argv[1]);planning=pd.Timestamp('2025-11-30')
p=pd.read_csv(P/'input-1.csv').sort_values(['Product_ID','Store_ID']).reset_index(drop=True)
keys=list(map(tuple,p[['Product_ID','Store_ID']].values));h=(p.Supplier_Lead_Time_Days+p.Review_Period_Days).to_numpy()
plan=json.loads(Path('evaluation_plan.json').read_text()); summaries=[]
for mode in ['include_processing','exclude_returns']:
    matrix,_=load_sales(P/'input-4.csv',planning,keys)
    # Apply same alternate target for training and scored outcomes, not changing the primary decision.
    matrix,_=load_sales(P/'input-4.csv',planning,keys,mode)
    for method in plan['candidates']:
        errors=[];seven=[]
        for o in plan['origins']:
            origin=pd.Timestamp(o);pred,_=forecast(matrix,origin,14,method,keys)
            actual=matrix.loc[origin+pd.Timedelta(days=1):origin+pd.Timedelta(days=14)].to_numpy()
            errors.extend([abs(pred[:n,j].sum()-actual[:n,j].sum()) for j,n in enumerate(h)])
            seven.extend(abs(pred[:7].sum(axis=0)-actual[:7].sum(axis=0)))
        summaries.append({'target':mode,'method':method,'coverage_MAE':float(np.mean(errors)),'next7_MAE':float(np.mean(seven))})
pd.DataFrame(summaries).to_csv('target_sensitivity.csv',index=False)

d=pd.read_csv('restocking.csv');s=pd.read_csv(P/'input-3.csv').set_index(['Product_ID','Store_ID']);r=pd.read_csv(P/'input-2.csv');r.Expected_Arrival_Date=pd.to_datetime(r.Expected_Arrival_Date)
matrix,_=load_sales(P/'input-4.csv',planning,keys)
# Independently implement per-key interval/size smoothing and ordering, without using forecast/run.
recomputed=[];shortages=[]
for j,policy in p.iterrows():
    y=matrix.iloc[-728:,j].to_numpy().reshape(104,7).sum(axis=1)
    nonzero=np.flatnonzero(y>0);smooth_size=float(y[nonzero[0]]) if len(nonzero) else 0
    smooth_gap=float(nonzero[0]+1) if len(nonzero) else 1
    for a,b in zip(nonzero[:-1],nonzero[1:]):
        smooth_size=.9*smooth_size+.1*y[b];smooth_gap=.9*smooth_gap+.1*(b-a)
    rate=.95*smooth_size/smooth_gap/7
    key=keys[j]; lead=int(policy.Supplier_Lead_Time_Days);end=planning+pd.Timedelta(days=int(h[j]))
    receipts=r[(r.Product_ID==key[0])&(r.Store_ID==key[1])]
    incoming=int(receipts.loc[(receipts.Expected_Arrival_Date>planning)&(receipts.Expected_Arrival_Date<=end),'Incoming_Qty'].sum())
    required=rate*h[j]+policy.Safety_Stock_Qty-int(s.loc[key].Usable_On_Hand_Qty)-incoming
    multiple=int(policy.Order_Multiple_Qty)
    qty=0 if required<=1e-10 else math.ceil(max(required,int(policy.Minimum_Order_Qty))/multiple)*multiple
    recomputed.append(qty)
    cum=0.;worst=0.
    for n in range(1,lead+1):
        before=receipts.loc[(receipts.Expected_Arrival_Date>planning)&(receipts.Expected_Arrival_Date<planning+pd.Timedelta(days=n)),'Incoming_Qty'].sum()
        worst=max(worst,n*rate-int(s.loc[key].Usable_On_Hand_Qty)-before)
    shortages.append(math.ceil(max(0,worst)-1e-10))
assert np.array_equal(d.OrderQty,recomputed)
assert np.array_equal(d.Potential_Shortage_Before_Receipt_Qty,shortages)
assert len(d)==336 and not d.duplicated(['Product_ID','Store_ID']).any()
assert d.OrderQty.ge(0).all() and (d.OrderQty%1==0).all()
assert ((d.OrderQty==0)|((d.OrderQty>=d.Minimum_Order_Qty)&(d.OrderQty%d.Order_Multiple_Qty==0))).all()
assert d.Product_Name.notna().all() and d.Quantity_Unit.eq('product_unit').all()
assert not any('synthetic' in str(x).lower() or 'provenance' in str(x).lower() for x in d.columns)
agree,detail=run(P/'input-4.csv',P/'input-3.csv',P/'input-2.csv',P/'input-1.csv','2025-11-30','agreement_check.csv')
assert Path('agreement_check.csv').read_bytes()==Path('restocking.csv').read_bytes()
Path('agreement_check.csv').unlink()
out={'rows':len(d),'products':d.Product_ID.nunique(),'stores':d.Store_ID.nunique(),'order_rows':int(d.OrderQty.gt(0).sum()),'zero_rows':int(d.OrderQty.eq(0).sum()),'order_units':int(d.OrderQty.sum()),'shortage_rows':int(d.Potential_Shortage_Before_Receipt_Qty.gt(0).sum()),'no_recent_recorded_units_rows':int(d.Review_Flags.fillna('').str.contains('NO_RECORDED').sum()),'orders_without_recent_units':int((d.Review_Flags.fillna('').str.contains('NO_RECORDED')&d.OrderQty.gt(0)).sum()),'by_store_units':d.groupby('Store_ID').OrderQty.sum().to_dict(),'independent_full_order_agreement':True,'independent_shortage_agreement':True,'rerun_byte_agreement':True,'comparison_dependency_versions':{'scipy':scipy.__version__,'scikit-learn':sklearn.__version__},'max_source_product_name_nulls':int(pd.read_csv(P/'input-4.csv').Product_Name.isna().sum()),'target_sensitivities':summaries,'source_boundaries':'Only released four CSVs and output files accessed; no reserved outcomes. Initial code-only corrections for missing optional names and pandas Index conversion preceded scores; later timing instrumentation reran unchanged v1 scoring, identical scores.'}
Path('validation_results.json').write_text(json.dumps(out,indent=2))
measurement=json.loads(Path('routine_measurements.json').read_text());measurement['output_agreement']={'independent_full_order_arithmetic':True,'independent_shortage_arithmetic':True,'rerun_byte_identical':True,'validated_rows':336};Path('routine_measurements.json').write_text(json.dumps(measurement,indent=2))
sha=hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
Path('result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha},indent=2))
print(json.dumps(out,indent=2))
