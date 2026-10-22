import hashlib,json,zipfile
from pathlib import Path
import pandas as pd

base='retail-0532a57711b44a00accad892f33bdb16'
roles=[('ordering_policy','ordering_policy.csv','policy:0','333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6'),('inbound_ledger','inbound_deliveries.csv','receipts:1','1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a'),('usable_stock','inventory_position.csv','inventory:2','3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9'),('transactions','Sales_transactions_2022_2025.csv','sales:3','520fa470ccb7ff5c7d0d8b34d157d15c05c948f7c785e48397ac676bf6cd7707')]
sources=[]
for i,(role,name,suffix,original_hash) in enumerate(roles,1):
 p=Path('../released')/f'input-{i}.csv'
 sources.append({'path':str(p),'role':role,'original_name':name,'approved_source_ref':{'artifact_id':base+':'+suffix,'version':5,'sha256':original_hash,'provenance':'supplied'},'released_byte_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'released_bytes':p.stat().st_size,'development_partition':i==4})
Path('source_manifest.json').write_text(json.dumps(sources,indent=2))
with zipfile.ZipFile('weekly_routine.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for name in ['restock_routine.py','forecasting.py','routine_usage.md','requirements.txt','routine_measurements.json']:
  z.write(name,arcname=name)
required=['restocking.csv','response.md','result.json','task_refinement.json','restock_routine.py','routine_usage.md','routine_measurements.json','evaluation_plan.json','comparison_results.json','source_treatment.json','validation_results.json']
assert all(Path(x).is_file() for x in required)
data=pd.read_csv('restocking.csv');r=json.loads(Path('result.json').read_text())
assert r=={'disposition':'analysis','output_file':'restocking.csv','output_sha256':hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()}
assert 150<=len(Path('response.md').read_text().split())<=250
assert len(data)==336 and data.OrderQty.sum()==875
assert list(data.columns[:5])==['Product_ID','Product_Name','Store_ID','OrderQty','Quantity_Unit']
assert not data.Product_Name.isna().any()
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('.').iterdir() if p.is_file() and p.name!='artifact_hashes.json'}
Path('artifact_hashes.json').write_text(json.dumps(hashes,indent=2))
print('Deliverables checked:',len(data),'rows,',data.OrderQty.sum(),'units. CSV SHA256:',r['output_sha256'])
