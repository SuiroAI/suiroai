import pandas as pd, json, hashlib
from pathlib import Path
P=Path('/private/tmp/suiroai-dsc59/artifacts/demo/e62526feb0764f79b8a61f3f11f23b28/runs/investigation-eb984590f7c4424b89240c73a7de3899/released')
s=pd.read_csv(P/'input-4.csv'); p=pd.read_csv(P/'input-1.csv'); i=pd.read_csv(P/'input-3.csv'); r=pd.read_csv(P/'input-2.csv')
keys=['Product_ID','Store_ID']
d=s.drop_duplicates().copy();d['status']=d.Order_Status.str.strip().str.lower();d['date']=pd.to_datetime(d.Order_Date)
out={'source_files':{f.name:{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for f in P.glob('*.csv')},'rows':len(s),'exact_duplicates_removed':int(s.duplicated().sum()),'remaining_duplicate_transaction_ids':int(d.Transaction_ID.duplicated().sum()),'nulls':s[keys+['Order_Date','Quantity','Order_Status','Return_Flag']].isna().sum().to_dict(),'statuses':d.status.value_counts().to_dict(),'returns':pd.crosstab(d.status,d.Return_Flag).to_dict(),'invalid_quantity_rows':int((d.Quantity<=0).sum()),'date_range':[str(d.date.min()),str(d.date.max())],'global_missing_dates':len(pd.date_range(d.date.min(),d.date.max()).difference(d.date.unique())),'key_coverage':{'sales':len(d[keys].drop_duplicates()),'policy':len(p),'inventory':len(i)},'product_name_conflicts':int((d.groupby('Product_ID').Product_Name.nunique()>1).sum()),'operating_provenance':{'policy':p.Provenance.unique().tolist(),'stock':i.Provenance.unique().tolist(),'deliveries':r.Provenance.unique().tolist()},'ledger_complete':bool(i.Open_Order_Ledger_Complete.all()),'ledger_mismatches':int((i.set_index(keys).On_Order_Qty-r.groupby(keys).Incoming_Qty.sum().reindex(pd.MultiIndex.from_frame(i[keys]),fill_value=0)).ne(0).sum()),'lead_days':sorted(p.Supplier_Lead_Time_Days.unique().tolist()),'units':p.Quantity_Unit.unique().tolist(),'inbound_due_dates':[r.Expected_Arrival_Date.min(),r.Expected_Arrival_Date.max()]}
valid=d[(d.Quantity>0)&d.status.isin(['completed','shipped','returned'])]
out['target_rows']=len(valid);out['target_units']=int(valid.Quantity.sum())
out['monthly_target_units']=valid.groupby(valid.date.dt.strftime('%Y-%m')).Quantity.sum().to_dict()
out['missing_pair_days_fraction']=1-len(valid.groupby(keys+['date']))/(len(p)*len(pd.date_range(d.date.min(),d.date.max())))
out['scope_note']='All channels charged to supplied Store_ID; forecast recorded gross fulfilled/returned units, not uncensored demand. Returns not subtracted: return dates and saleable condition absent; stock already usable.'
Path('source_treatment.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
