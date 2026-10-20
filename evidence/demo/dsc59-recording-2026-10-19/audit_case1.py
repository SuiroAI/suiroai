"""Independently audit the actual first recorded retail demo output.

Recompute the chosen 91-day recorded-sales scenario directly from released
CSV files using standard-library exact fractions. Parse the displayed HTML
and bind its cells, the CSV and immutable receipts without executing Data's
producer code. Retain hashes and aggregate results, never personal source rows.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
import csv,math,json
from hashlib import sha256
from datetime import datetime,timezone
from collections import defaultdict
from fractions import Fraction as F
from datetime import date,timedelta
base=Path('artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-c49ead0546fe49fbb29d9a64972a9e93')
files={}
measured={}
for path in (base/'released').glob('*.csv'):
 data=path.read_bytes();measured[str(path.relative_to(base))]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
 with path.open(newline='') as f:
  reader=csv.DictReader(f);rows=list(reader);files[frozenset(reader.fieldnames)]=rows
sales=next(v for k,v in files.items() if 'Transaction_ID' in k)
stocks=next(v for k,v in files.items() if 'Usable_On_Hand_Qty' in k)
rules=next(v for k,v in files.items() if 'Supplier_Lead_Time_Days' in k)
receipts=next(v for k,v in files.items() if 'PO_Line_ID' in k)
with (base/'output/restocking.csv').open(newline='') as f:result=list(csv.DictReader(f))
key=lambda r:(r['Product_ID'],r['Store_ID'])
stock={key(r):r for r in stocks};policy={key(r):r for r in rules}
seen=set();recent=defaultdict(int);duplicates=0
for row in sales:
 signature=tuple(row.items())
 if signature in seen:duplicates+=1;continue
 seen.add(signature);when=date.fromisoformat(row['Order_Date'])
 assert when<=date(2025,11,30)
 if int(row['Quantity'])<=0 or row['Order_Status'].strip().lower() not in {'completed','shipped','returned'}:continue
 if date(2025,9,1)<=when<=date(2025,11,30):recent[key(row)]+=int(row['Quantity'])
risks=0;total=0
for row in result:
 pair=key(row);p,s=pair;inv=stock[pair];rule=policy[pair]
 rate=F(recent[pair],91)
 horizon=int(rule['Supplier_Lead_Time_Days'])+int(rule['Review_Period_Days'])
 through=date(2025,11,30)+timedelta(days=horizon)
 lines=[r for r in receipts if key(r)==pair]
 incoming=sum(int(r['Incoming_Qty']) for r in lines if date(2025,11,30)<date.fromisoformat(r['Expected_Arrival_Date'])<=through)
 assert incoming==int(inv['On_Order_Qty'])==int(row['Incoming_Units'])
 assert int(row['Usable_Stock_Units'])==int(inv['Usable_On_Hand_Qty'])
 need=rate*horizon
 assert abs(float(need)-float(row['Expected_Units_Through_Protection_Window']))<=.005000001
 gap=need+int(rule['Safety_Stock_Qty'])-int(inv['Usable_On_Hand_Qty'])-incoming
 expected=0 if gap<=0 else math.ceil(max(gap,int(rule['Minimum_Order_Qty']))/int(rule['Order_Multiple_Qty']))*int(rule['Order_Multiple_Qty'])
 assert expected==int(row['OrderQty']),(pair,expected,row['OrderQty'])
 balance=F(int(inv['Usable_On_Hand_Qty']));risk=False
 for offset in range(int(rule['Supplier_Lead_Time_Days'])):
  day=date(2025,12,1)+timedelta(days=offset)
  balance+=sum(int(r['Incoming_Qty']) for r in lines if date.fromisoformat(r['Expected_Arrival_Date'])==day)
  balance-=rate;risk|=balance<0
 assert row['Check_Earlier_Delivery'].lower()==str(risk).lower()
 risks+=risk;total+=expected
arithmetic={'rows_checked':len(result),'quantity_units':total,'prearrival_flags':risks,'duplicates_removed':duplicates,'method':'Independent stdlib Fraction reconstruction:91-day totals,stock/due-receipts/buffer/minimum/multiple; no producer execution','limits':'Chosen-scenario arithmetic only, not model merit/completeness/acceptance'}

from pathlib import Path
from html.parser import HTMLParser
from hashlib import sha256
import csv,io,json
class Cells(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.cell=None;self.tables=0;self.style=False;self.outside=[]
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.rows.append([])
  if tag in ('th','td'):self.cell=''
  if tag=='style':self.style=True
  if tag=='table':self.tables+=1
 def handle_endtag(self,tag):
  if tag in ('th','td'):self.rows[-1].append(self.cell);self.cell=None
  if tag=='style':self.style=False
 def handle_data(self,data):
  if self.cell is not None:self.cell+=data
  elif not self.style and data.strip():self.outside.append(data)
session=Path('artifacts/demo/f8567dcea15e473380dbcfc067ccf092')
receipt=session/'runs/attempt-37815bfcf0354e84981b23c58fc75360.json';stage=json.loads(receipt.read_text())['stage_result']
csvdata=Path(stage['unverified_report_path']).read_bytes();html=Path(stage['html_report_path']).read_bytes()
p=Cells();p.feed(html.decode());p.close();rows=list(csv.reader(io.StringIO(csvdata.decode('utf-8-sig'),newline='')))
assert p.rows==rows and len(rows)==337 and p.tables==1
assert p.outside==['Restocking list','Restocking list']
for ref,data in [(stage['restocking_ref'],csvdata),(stage['html_report_ref'],html)]:
 assert sha256(data).hexdigest()==ref['sha256']
 assert (session/'store/objects'/ref['sha256']).read_bytes()==data
assert stage['native_outcome']=='completed' and not stage.get('output_error')
identity={'receipt':str(receipt),'native_outcome':stage['native_outcome'],'rows':len(rows)-1,'columns':len(rows[0]),'exact_cells_and_order':True,'no_narrative':True,'csv_sha256':sha256(csvdata).hexdigest(),'html_sha256':sha256(html).hexdigest(),'immutable_bytes_match':True,'response_words':len(stage['unverified_investigation_text'].split())}


for name in ['output/restocking.csv','output/result.json','output/response.md']:
 data=(base/name).read_bytes()
 measured[name]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
manifest=json.loads((base/'output/result.json').read_bytes())
assert manifest['output_sha256']==identity['csv_sha256']
assert stage['unverified_investigation_text']==(base/'output/response.md').read_text()
result={
 'reviewer':'Codex / plain-language-and-CSV-preview reviewer',
 'reviewed_at':datetime.now(timezone.utc).isoformat(),
 'source_commit':'b243957ed381528908f7594cd8e5d1b7b98203ba',
 'run_root':str(base),
 'auditor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
 'decision':'pass_for_exploratory_outputs_and_chosen_scenario_arithmetic',
 'arithmetic':arithmetic,'identity':identity,'measured_files':measured,
 'manual_response_review':{
  'current_process':'Explicit question describes looking at recent months; exact quantity rule absent. Response says comparison cannot establish improvement over the real process.',
  'comparison':'Seasonal challenger has approximately 1.69% higher later average error; response rounds to about 2% higher and retains simple method.',
  'local_cost':'Generated calculation uses local Python/pandas/numpy with small source CSVs; ordinary computer/no paid routine model calls is supported. Electricity/computer costs acknowledged, separate AI build price unknown.',
  'scope':'Exploratory app evidence only. No full frozen December holdout, authenticated verifier/parent gate or milestone acceptance granted.'
 }
}
destination=Path(__file__).with_name('case1-independent-audit.json')
destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'decision':result['decision'],'arithmetic':arithmetic,'identity':identity}))
