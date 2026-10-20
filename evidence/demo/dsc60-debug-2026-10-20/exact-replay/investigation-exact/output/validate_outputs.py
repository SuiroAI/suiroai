import csv, math, json, hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
rows=list(csv.DictReader((root/'restocking.csv').open()))
assert len(rows)==336
assert len({(r['Product_ID'],r['Store_ID']) for r in rows})==336
total=0
for r in rows:
 qty=int(r['OrderQty']); multiple=int(r['Order_Multiple_Qty'])
 gap=max(0,float(r['Forecast_Protection_Units'])+int(r['Safety_Stock_Qty'])-int(r['Usable_On_Hand_Qty'])-int(r['Incoming_In_Protection_Units']))
 expected=math.ceil(max(gap,multiple)/multiple)*multiple if gap>0 else 0
 assert qty==expected and qty>=0 and qty%multiple==0
 assert r['Quantity_Unit']=='product_unit' and r['Product_Name']
 total+=qty
digest=hashlib.sha256((root/'restocking.csv').read_bytes()).hexdigest()
manifest=json.loads((root/'result.json').read_text())
assert set(manifest)=={'disposition','output_file','output_sha256'}
assert manifest['output_sha256']==digest and manifest['disposition']=='analysis'
assert total==888
words=len((root/'response.md').read_text().split())
assert 150<=words<=250,words
result={'rows':len(rows),'total_units':total,'positive_orders':sum(int(r['OrderQty'])>0 for r in rows),'zero_orders':sum(int(r['OrderQty'])==0 for r in rows),'independent_order_recomputation':'all rows agree','response_words':words,'sha256':digest}
(root/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
