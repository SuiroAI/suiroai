"""Independently audit the second recorded retail demo's delivered output.

Reconstruct its selected non-LLM seasonal pooled forecast and daily purchasing
arithmetic directly from source CSVs with standard-library exact fractions.
Parse the HTML and bind exact headers/cells/order and immutable output hashes.
No Data producer code is imported or executed, and no personal rows are saved.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
from datetime import date,timedelta,datetime,timezone
from hashlib import sha256
import csv,io,json,calendar,math
base=Path('artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-0bc535ea9b0e4f1384799fcfdfda8f5e')
measured={}
def read(path):
 data=path.read_bytes();measured[str(path.relative_to(base))]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
 reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''));return list(reader),reader.fieldnames
inputs={}
for path in (base/'released').glob('*.csv'):
 rows,headers=read(path);inputs[frozenset(headers)]=rows
sales=next(v for k,v in inputs.items() if 'Transaction_ID' in k)
stockrows=next(v for k,v in inputs.items() if 'Usable_On_Hand_Qty' in k)
rules=next(v for k,v in inputs.items() if 'Supplier_Lead_Time_Days' in k)
receipts=next(v for k,v in inputs.items() if 'PO_Line_ID' in k)
result,headers=read(base/'output/restocking.csv')
key=lambda row:(row['Product_ID'],row['Store_ID'])
stock={key(r):r for r in stockrows};policy={key(r):r for r in rules}
assert len(stock)==len(stockrows)==len(policy)==len(rules)==len(result)==336
assert set(map(key,result))==set(stock)==set(policy)
seen=set();duplicates=0;annual=defaultdict(int);recent=defaultdict(int);yearly=defaultdict(int);monthly=defaultdict(int)
for row in sales:
 identity=tuple(row.items())
 if identity in seen:duplicates+=1;continue
 seen.add(identity)
 when=date.fromisoformat(row['Order_Date'])
 assert date(2022,1,1)<=when<=date(2025,11,30)
 if int(row['Quantity'])<=0 or row['Order_Status'].strip().lower() not in {'completed','shipped','returned'}:continue
 units=int(row['Quantity'])
 if date(2024,12,1)<=when:annual[key(row)]+=units
 if date(2025,10,6)<=when:recent[key(row)]+=units
 if when.year<2025:yearly[when.year]+=units;monthly[(when.year,when.month)]+=units
factors={}
for month in range(1,13):
 factors[month]=sum(F(monthly[(year,month)],calendar.monthrange(year,month)[1])/F(yearly[year],366 if calendar.isleap(year) else 365) for year in [2022,2023,2024])/3
level=F(sum(recent.values()))/(26*factors[10]+30*factors[11])
product=defaultdict(int);stores=defaultdict(int)
for (p,s),units in annual.items():product[p]+=units;stores[s]+=units
network=sum(annual.values())
risks=0;units_total=0;incoming_total=0
for row in result:
 pair=key(row);p,s=pair;inv=stock[pair];rule=policy[pair]
 share=(annual[pair]+20*336*F(product[p]*stores[s],network*network))/(network+20*336)
 rate=level*factors[12]*share
 lead=int(rule['Supplier_Lead_Time_Days']);horizon=lead+int(rule['Review_Period_Days'])
 lines=[r for r in receipts if key(r)==pair]
 incoming=sum(int(r['Incoming_Qty']) for r in lines)
 assert incoming==int(inv['On_Order_Qty'])==int(row['Incoming_Units'])
 assert int(row['Usable_Stock_Units'])==int(inv['Usable_On_Hand_Qty'])
 assert int(row['Safety_Stock_Units'])==int(rule['Safety_Stock_Qty'])
 assert int(row['Cover_Days'])==horizon
 assert row['Week_Start']=='2025-12-01' and row['Week_End']=='2025-12-07'
 assert row['Expected_New_Order_Arrival']==(date(2025,12,1)+timedelta(days=lead)).isoformat()
 assert abs(float(rate*7)-float(row['Forecast_Week_Units']))<=.000500001
 assert abs(float(rate*horizon)-float(row['Forecast_Cover_Units']))<=.000500001
 balance=F(int(inv['Usable_On_Hand_Qty']));need=F(0);risk=False;pre_short=F(0)
 for offset in range(horizon):
  day=date(2025,12,1)+timedelta(days=offset)
  balance+=sum(int(r['Incoming_Qty']) for r in lines if date.fromisoformat(r['Expected_Arrival_Date'])==day)
  balance-=rate
  if offset>=lead:need=max(need,int(rule['Safety_Stock_Qty'])-balance)
  elif balance<0:risk=True;pre_short=max(pre_short,-balance)
 multiple=int(rule['Order_Multiple_Qty'])
 expected=0 if need<=0 else math.ceil(max(need,int(rule['Minimum_Order_Qty']))/multiple)*multiple
 assert int(row['OrderQty'])==expected,(pair,expected,row['OrderQty'])
 assert row['Expedite_Review'].lower()==str(risk).lower()
 assert abs(float(pre_short)-float(row['Projected_Prearrival_Shortage_Units']))<=.000500001
 risks+=risk;units_total+=expected;incoming_total+=incoming
assert len({r['PO_Line_ID'] for r in receipts})==len(receipts)
assert all(key(r) in stock for r in receipts)
assert all(date.fromisoformat(r['Order_Date'])<=date(2025,11,30)<date.fromisoformat(r['Expected_Arrival_Date']) for r in receipts)
arithmetic={'rows_checked':len(result),'order_units':units_total,'prearrival_risk_rows':risks,'duplicates_removed':duplicates,'incoming_units_reconciled':incoming_total,'method':'Independent exact-rational reconstruction of 365-day product/store shares with 20 pseudo-units per pair, prior full-year monthly factors, 56-day network level, daily stock/receipt timing and order constraints.','limits':'Chosen-scenario arithmetic only; no complete-demand, model-superiority, frozen-holdout or authenticated verifier gate acceptance.'}

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
receipt=session/'runs/attempt-419c774156b44ce2b4924abbdb2dcc0b.json';stage=json.loads(receipt.read_text())['stage_result']
csvdata=Path(stage['unverified_report_path']).read_bytes();html=Path(stage['html_report_path']).read_bytes()
p=Cells();p.feed(html.decode());p.close();rows=list(csv.reader(io.StringIO(csvdata.decode('utf-8-sig'),newline='')))
assert p.rows==rows and len(rows)==337 and p.tables==1
assert p.outside==['Restocking list','Restocking list']
dom_path=Path(__file__).with_name('case2-table-dom.json')
assert json.loads(dom_path.read_text())==rows
for ref,data in [(stage['restocking_ref'],csvdata),(stage['html_report_ref'],html)]:
 assert sha256(data).hexdigest()==ref['sha256']
 assert (session/'store/objects'/ref['sha256']).read_bytes()==data
assert stage['native_outcome']=='completed' and not stage.get('output_error')
identity={'receipt':str(receipt),'receipt_sha256':sha256(receipt.read_bytes()).hexdigest(),'native_outcome':stage['native_outcome'],'rows':len(rows)-1,'columns':len(rows[0]),'exact_cells_and_order':True,'live_browser_dom_equals_csv':True,'browser_dom_sha256':sha256(dom_path.read_bytes()).hexdigest(),'no_narrative':True,'csv_sha256':sha256(csvdata).hexdigest(),'html_sha256':sha256(html).hexdigest(),'immutable_bytes_match':True,'response_words':len(stage['unverified_investigation_text'].split())}


assert Path(stage['html_report_path']).parent.resolve()==(base/'output').resolve()
for name in ['output/result.json','output/response.md','output/model_comparison.csv','output/analysis_results.json']:
 data=(base/name).read_bytes();measured[name]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
assert json.loads((base/'output/result.json').read_bytes())['output_sha256']==identity['csv_sha256']
assert stage['unverified_investigation_text']==(base/'output/response.md').read_text()
scores,_=read(base/'output/model_comparison.csv')
later={r['method']:r for r in scores if r['year']=='2025'}
gain=1-math.sqrt(float(later['pooled_seasonal']['sq_error'])/float(later['pooled_seasonal']['n']))/math.sqrt(float(later['last_month']['sq_error'])/float(later['last_month']['n']))
details=json.loads((base/'output/analysis_results.json').read_bytes())
assert abs(gain-details['rmse_improvement_over_last_month'])<1e-12
assert round(gain*100)==9
result={'reviewer':'Codex / plain-language-and-CSV-preview reviewer','reviewed_at':datetime.now(timezone.utc).isoformat(),
 'source_commit':'b243957ed381528908f7594cd8e5d1b7b98203ba','run_root':str(base),
 'auditor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
 'decision':'pass_for_exploratory_outputs_and_chosen_scenario_arithmetic',
 'arithmetic':arithmetic,'identity':identity,'measured_files':measured,'checked_rmse_improvement':gain,
 'manual_response_review':{
  'current_process':'Exact supplied answer describes using last month sales for the week. Day-count scaling is a reasonable interpretation; response explicitly says exact buying rules unavailable.',
  'comparison':'About 9% gain is explicitly qualified as errors giving more weight to large misses, consistent with RMSE; no claim that all metrics or all alternatives improve. Simple year-long average acknowledged almost as accurate.',
  'local_cost':'Actual generated calculation uses local Python/pandas/numpy with about 5 MB sources and a short measured runtime. Ordinary computer/no paid routine model calls is supported. Electricity/computer costs acknowledged, separate AI build price unknown.',
  'scope':'No full frozen December holdout, authenticated verifier/parent gate or milestone acceptance granted.'}}
Path(__file__).with_name('case2-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'decision':result['decision'],'arithmetic':arithmetic,'identity':identity}))
