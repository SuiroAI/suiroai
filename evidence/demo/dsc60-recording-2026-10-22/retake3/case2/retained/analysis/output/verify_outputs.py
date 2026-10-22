"""Independent CSV-level checks of selected mean, order arithmetic and timing."""
import csv, datetime as dt, hashlib, json, math
from collections import defaultdict
from pathlib import Path

def read(p):
    with open(p,newline='') as f:
        return list(csv.DictReader(f))

date=dt.date(2025,11,30)
raw=read('../released/input-4.csv')
seen=set(); rows=[]
for row in raw:
    signature=tuple(row.items())
    if signature not in seen:
        rows.append(row); seen.add(signature)
active=set(); weekly=defaultdict(int)
for r in rows:
    d=dt.date.fromisoformat(r['Order_Date']); w=d-dt.timedelta(days=d.weekday())
    active.add((r['Store_ID'],w))
    if r['Order_Status'].strip().lower() in ['completed','shipped'] and int(r['Quantity'])>0:
        weekly[(r['Product_ID'],r['Store_ID'],w)]+=int(r['Quantity'])
policies={(r['Product_ID'],r['Store_ID']):r for r in read('../released/input-1.csv')}
stock={(r['Product_ID'],r['Store_ID']):r for r in read('../released/input-3.csv')}
ledger=defaultdict(list)
for r in read('../released/input-2.csv'):
    ledger[r['Product_ID'],r['Store_ID']].append((dt.date.fromisoformat(r['Expected_Arrival_Date']),int(r['Incoming_Qty'])))
out=read('restocking.csv')
assert len(out)==336 and len({(r['Product_ID'],r['Store_ID']) for r in out})==336
weeks=[dt.date(2025,9,1)+dt.timedelta(weeks=k) for k in range(13)]
errors=[]
for row in out:
    key=row['Product_ID'],row['Store_ID']
    p=policies[key]; s=stock[key]
    known=[w for w in weeks if (key[1],w) in active]
    mean=sum(weekly[key+(w,)] for w in known)/len(known)
    assert abs(mean-float(row['Forecast_Next_Week_Qty']))<=.000051
    lead=int(p['Supplier_Lead_Time_Days']); horizon=lead+int(p['Review_Period_Days'])
    inbound=sum(q for d,q in ledger[key] if date<d<=date+dt.timedelta(days=horizon))
    raw_need=max(0,mean/7*horizon+int(p['Safety_Stock_Qty'])-int(s['Usable_On_Hand_Qty'])-inbound)
    pack=int(p['Order_Multiple_Qty']); minimum=int(p['Minimum_Order_Qty'])
    expected=math.ceil(max(raw_need,minimum)/pack)*pack if raw_need>1e-10 else 0
    assert int(row['OrderQty'])==expected and expected>=0
    assert expected==0 or (expected%pack==0 and expected>=minimum)
    assert int(row['Incoming_Within_Coverage_Qty'])==inbound
    balance=int(s['Usable_On_Hand_Qty']); early=0; nextweek=0; earliest=''
    for day in range(1,max(7,horizon)+1):
        current=date+dt.timedelta(days=day)
        balance+=sum(q for d,q in ledger[key] if d==current)
        if day==max(1,lead): balance+=expected
        balance-=mean/7
        if day<lead: early=max(early,-balance)
        if day<=7: nextweek=max(nextweek,-balance)
        if balance < -1e-10 and not earliest: earliest=str(current)
    assert row['First_Projected_Shortage_Date']==earliest
    assert int(row['PreArrivalShortageQty'])==(math.ceil(early-1e-10) if early>1e-10 else 0)
    assert int(row['NextWeekShortageQty'])==(math.ceil(nextweek-1e-10) if nextweek>1e-10 else 0)
    assert ('REVIEW_EARLIER_SUPPLY' in row['Review_Flags'])==(early>1e-10)
    assert row['Quantity_Unit']=='product_unit'
assert not any(x in out[0] for x in ['Synthetic','Provenance','Illustrative_Synthetic_Stock'])
sha=hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
measurement=json.loads(Path('routine_measurements.json').read_text())
assert sha==measurement['output_sha256']
measurement['output_agreement']={'all_rows_checked':len(out),'independent_implementation':'verify_outputs.py, Python standard library CSV aggregation and arithmetic','forecast_rounding_tolerance_units':.000051,'orders_match':True,'incoming_match':True,'shortage_quantities_and_dates_match':True,'output_sha256_matches':True}
Path('routine_measurements.json').write_text(json.dumps(measurement,indent=2))
Path('result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':sha},indent=2))
checks={'rows':len(out),'order_units':sum(int(r['OrderQty']) for r in out),'positive_orders':sum(int(r['OrderQty'])>0 for r in out),'zero_orders':sum(int(r['OrderQty'])==0 for r in out),'early_shortage_products_at_stores':sum(int(r['PreArrivalShortageQty'])>0 for r in out),'csv_sha256':sha,'all_row_independent_checks_passed':True}
Path('output_checks.json').write_text(json.dumps(checks,indent=2)); print(json.dumps(checks,indent=2))
