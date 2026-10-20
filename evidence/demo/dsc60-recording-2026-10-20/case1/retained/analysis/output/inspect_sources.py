import json, hashlib
from pathlib import Path
import pandas as pd

def main():
    source=Path('../released')
    frames={i:pd.read_csv(source/f'input-{i}.csv') for i in range(1,5)}
    p,l,v,s=(frames[i] for i in range(1,5))
    s=s.drop_duplicates().copy()
    s['date']=pd.to_datetime(s.Order_Date)
    s['status']=s.Order_Status.str.strip().str.lower()
    keys=['Product_ID','Store_ID']
    pairs=set(map(tuple,v[keys].values))
    q={}
    q['sources']={str(i):{'path':str(source/f'input-{i}.csv'),'rows':len(d),'sha256':hashlib.sha256((source/f'input-{i}.csv').read_bytes()).hexdigest(),'exact_duplicates':int(d.duplicated().sum())} for i,d in frames.items()}
    q['sales']={'unique_transactions':int(s.Transaction_ID.nunique()),'duplicate_id_after_exact_dedup':int(s.Transaction_ID.duplicated().sum()),'dates':[str(s.date.min().date()),str(s.date.max().date())],'missing_global_dates':len(pd.date_range(s.date.min(),s.date.max()).difference(s.date)), 'status_counts':s.status.value_counts().to_dict(),'nonpositive_quantities':int(s.Quantity.le(0).sum()),'return_counts':s.Return_Flag.value_counts().to_dict(),'status_return_units':s.groupby(['status','Return_Flag']).Quantity.agg(['size','sum']).reset_index().to_dict('records'),'unmatched_sales_pairs':len(set(map(tuple,s[keys].values))-pairs),'product_names_unique_nonnull':s.groupby('Product_ID').Product_Name.nunique().value_counts().to_dict(),'pair_first_date_range':[str(x.date()) for x in [s.groupby(keys).date.min().min(),s.groupby(keys).date.min().max()]],'pair_last_date_range':[str(x.date()) for x in [s.groupby(keys).date.max().min(),s.groupby(keys).date.max().max()]]}
    joined=v.merge(l.groupby(keys).Incoming_Qty.sum().rename('ledger_total'),on=keys,how='left').fillna({'ledger_total':0})
    q['operations']={'policy_duplicate_pairs':int(p.duplicated(keys).sum()),'stock_duplicate_pairs':int(v.duplicated(keys).sum()),'ledger_duplicate_lines':int(l.PO_Line_ID.duplicated().sum()),'policy_stock_pair_match':set(map(tuple,p[keys].values))==pairs,'ledger_unmatched_pairs':len(set(map(tuple,l[keys].values))-pairs),'ledger_stock_mismatch_count':int(joined.On_Order_Qty.ne(joined.ledger_total).sum()),'all_ledger_complete':bool(v.Open_Order_Ledger_Complete.all()),'units':{str(i):d.Quantity_Unit.unique().tolist() for i,d in frames.items() if i<4},'provenance':{str(i):d.Provenance.unique().tolist() for i,d in frames.items() if i<4},'date_bounds':{c:[l[c].min(),l[c].max()] for c in ['Order_Date','Expected_Arrival_Date']},'all_stock_nonnegative':bool(v[['Usable_On_Hand_Qty','On_Order_Qty']].ge(0).all().all()),'policy_ranges':{c:[int(p[c].min()),int(p[c].max())] for c in ['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']}}
    q['monthly_units']=s[s.Quantity.gt(0)&s.status.isin(['completed','shipped','returned'])].groupby(s.date.dt.strftime('%Y-%m')).Quantity.sum().to_dict()
    Path('source_profile.json').write_text(json.dumps(q,indent=2))
    print(json.dumps(q,indent=2))

if __name__=='__main__': main()
