"""Independent direct-source baseline verification, source integrity and output checks."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parent
expected=['333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6','1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a','3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9','48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8']
for i,sha in enumerate(expected,1):
    assert hashlib.sha256((root.parent/'released'/f'input-{i}.csv').read_bytes()).hexdigest()==sha
raw=pd.read_csv(root.parent/'released'/'input-4.csv')
dedup=raw.drop_duplicates().copy()
normalized=dedup.copy()
normalized.Order_Status=normalized.Order_Status.str.strip().str.lower()
assert normalized.duplicated().sum()==0
dedup['status']=normalized.Order_Status
dedup['date']=pd.to_datetime(dedup.Order_Date)
target=dedup[dedup.Quantity.gt(0)&dedup.status.ne('cancelled')]
key=['Product_ID','Store_ID']
policy=pd.read_csv(root.parent/'released'/'input-1.csv')
keys=pd.MultiIndex.from_frame(policy[key])
pred=pd.read_csv(root/'development_predictions.csv')
base=pred[pred.Model.eq('local91')]
checks=[]
for origin,g in base.groupby('Origin'):
    o=pd.Timestamp(origin)
    past=target[target.date.ge(o-pd.Timedelta(days=91))&target.date.lt(o)]
    future=target[target.date.ge(o)&target.date.lt(o+pd.Timedelta(days=7))]
    p=past.groupby(key).Quantity.sum().reindex(keys,fill_value=0)*7/91
    y=future.groupby(key).Quantity.sum().reindex(keys,fill_value=0)
    g=g.set_index(key).reindex(keys)
    assert np.allclose(p,g.Prediction) and np.array_equal(y,g.Actual)
    checks.append({'Origin':origin,'Period':g.Period.iloc[0],'DirectMAE':float(abs(p-y).mean())})
direct=pd.DataFrame(checks)
scores=pd.read_csv(root/'comparison_scores.csv')
for period,g in direct.groupby('Period'):
    reference=scores[scores.Period.eq(period)&scores.Model.eq('local91')].MAE.iloc[0]
    assert abs(g.DirectMAE.mean()-reference)<1e-12
orders=pd.read_csv(root/'restocking.csv',keep_default_na=False)
result=json.loads((root/'result.json').read_text())
assert set(result)=={'disposition','output_file','output_sha256'}
assert result['disposition']=='analysis' and result['output_file']=='restocking.csv'
assert result['output_sha256']==hashlib.sha256((root/'restocking.csv').read_bytes()).hexdigest()
assert len(orders)==336 and orders.OrderQty.sum()==873
assert orders.OrderQty.gt(0).sum()==111 and orders.OrderQty.eq(0).sum()==225
assert orders.Shortage_Before_New_Arrival.sum()==56
assert not orders.duplicated(key).any()
assert set(pd.MultiIndex.from_frame(orders[key]))==set(keys)
assert (orders.OrderQty>=0).all() and (orders.OrderQty%1==0).all()
assert (orders.OrderQty%orders.Order_Multiple==0).all()
assert ((orders.OrderQty==0)|(orders.OrderQty>=orders.Minimum_Order)).all()
assert set(orders.Quantity_Unit)=={'product_unit'}
assert 150<=len((root/'response.md').read_text().split())<=250
pd.DataFrame(checks).to_csv(root/'independent_baseline_checks.csv',index=False)
record={'source_byte_hashes_match':True,'normalized_extra_duplicates':0,'independent_baseline_key_origin_predictions_and_targets_checked':len(base),
        'origin_primary_MAE_checked':len(checks),'CSV_rows':len(orders),'CSV_sha256':result['output_sha256'],
        'response_words':len((root/'response.md').read_text().split()),'all_checks_passed':True}
(root/'validation_results.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
