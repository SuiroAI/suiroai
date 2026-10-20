"""Independently audit the genuine replacement recording for the first case.

Recompute its noncancelled recorded-demand scenario directly from released
source CSVs using exact fractions, without importing or executing Data code.
Bind the replacement receipt, exact HTML/CSV cells and live browser DOM.
Retain only aggregate results and hashes; grant no full milestone acceptance.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
from datetime import date,timedelta,datetime,timezone
from hashlib import sha256
import csv,io,json,calendar,math
base=Path('artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-fd2a074d16e7401ca1682ad64e944847')
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
stock_by_pair={key(r):r for r in stockrows};rule_by_pair={key(r):r for r in rules}
assert len(stock_by_pair)==len(stockrows)==len(rule_by_pair)==len(rules)==len(result)==336
assert set(map(key,result))==set(stock_by_pair)==set(rule_by_pair)
seen=set();annual=defaultdict(int);recent=defaultdict(int);monthly=defaultdict(int);duplicates=0
for row in sales:
 signature=tuple(row.items())
 if signature in seen:duplicates+=1;continue
 seen.add(signature);when=date.fromisoformat(row['Order_Date'])
 assert when<=date(2025,11,30)
 if int(row['Quantity'])<=0 or row['Order_Status'].strip().lower()=='cancelled':continue
 units=int(row['Quantity'])
 if when>=date(2024,12,2):annual[key(row)]+=units
 if when>=date(2025,9,1):recent[key(row)]+=units
 if when.year<2025:monthly[when.month]+=units
monthmean={m:F(v,sum(calendar.monthrange(y,m)[1] for y in [2022,2023,2024])) for m,v in monthly.items()}
factor=monthmean[12]/((30*monthmean[9]+31*monthmean[10]+30*monthmean[11])/91)
product=defaultdict(int);stores=defaultdict(int)
for (p,s),units in annual.items():product[p]+=units;stores[s]+=units
network=sum(annual.values());recenttotal=sum(recent.values())
quantitytotal=0;riskcount=0;incomingtotal=0
for row in result:
 pair=key(row);p,s=pair;inv=stock_by_pair[pair];rule=rule_by_pair[pair]
 rate=(F(annual[pair],364)+F(product[p]*stores[s]*recenttotal,network*network*91))/2*factor
 lead=int(rule['Supplier_Lead_Time_Days']);horizon=lead+int(rule['Review_Period_Days'])
 lines=[r for r in receipts if key(r)==pair]
 incoming=sum(int(r['Incoming_Qty']) for r in lines if date(2025,11,30)<date.fromisoformat(r['Expected_Arrival_Date'])<=date(2025,11,30)+timedelta(days=horizon))
 assert incoming==int(inv['On_Order_Qty'])==int(row['Incoming_Within_Coverage_Units'])
 assert int(row['Usable_On_Hand_Units'])==int(inv['Usable_On_Hand_Qty'])
 assert int(row['Safety_Stock_Units'])==int(rule['Safety_Stock_Qty'])
 assert int(row['Coverage_Days'])==horizon
 assert abs(float(rate*7)-float(row['Expected_Next_Week_Units']))<=.005000001
 assert abs(float(rate*horizon)-float(row['Expected_Coverage_Units']))<=.005000001
 gap=rate*horizon+int(rule['Safety_Stock_Qty'])-int(inv['Usable_On_Hand_Qty'])-incoming
 expected=0 if gap<=0 else math.ceil(max(gap,int(rule['Minimum_Order_Qty']))/int(rule['Order_Multiple_Qty']))*int(rule['Order_Multiple_Qty'])
 assert expected==int(row['OrderQty']),(pair,expected,row['OrderQty'])
 balance=F(int(inv['Usable_On_Hand_Qty']));risk=False
 for offset in range(1,lead+1):
  day=date(2025,11,30)+timedelta(days=offset)
  balance+=sum(int(r['Incoming_Qty']) for r in lines if date.fromisoformat(r['Expected_Arrival_Date'])==day)
  balance-=rate;risk|=balance<0
 assert row['Check_Stock_Before_New_Delivery'].lower()==str(risk).lower()
 quantitytotal+=expected;riskcount+=risk;incomingtotal+=incoming
arithmetic={'rows_checked':len(result),'order_units':quantitytotal,'early_stock_risk_rows':riskcount,'incoming_units_reconciled':incomingtotal,'duplicates_removed':duplicates,'method':'Independent exact-rational reconstruction of positive noncancelled order units, 364-day annual means and product/store shares, 91-day network level, prior-year monthly factors, due receipts and ordering constraints.','limits':'Chosen demand-proxy scenario arithmetic only; includes pending requests. Timing convention counts lead days from end of Nov30 snapshot. No demand-completeness/model-superiority/frozen-December-holdout/authenticated acceptance.'}

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
receipt=session/'runs/attempt-d67168b053814fc5805b46a401d1347f.json';stage=json.loads(receipt.read_text())['stage_result']
csvdata=Path(stage['unverified_report_path']).read_bytes();html=Path(stage['html_report_path']).read_bytes()
p=Cells();p.feed(html.decode());p.close();rows=list(csv.reader(io.StringIO(csvdata.decode('utf-8-sig'),newline='')))
assert p.rows==rows and len(rows)==337 and p.tables==1
assert p.outside==['Restocking list','Restocking list']
for ref,data in [(stage['restocking_ref'],csvdata),(stage['html_report_ref'],html)]:
 assert sha256(data).hexdigest()==ref['sha256']
 assert (session/'store/objects'/ref['sha256']).read_bytes()==data
assert stage['native_outcome']=='completed' and not stage.get('output_error')
identity={'receipt':str(receipt),'native_outcome':stage['native_outcome'],'rows':len(rows)-1,'columns':len(rows[0]),'exact_cells_and_order':True,'no_narrative':True,'csv_sha256':sha256(csvdata).hexdigest(),'html_sha256':sha256(html).hexdigest(),'immutable_bytes_match':True,'response_words':len(stage['unverified_investigation_text'].split())}


assert Path(stage['html_report_path']).parent.resolve()==(base/'output').resolve()
dom_path=Path(__file__).with_name('case1-retake-table-dom.json')
assert json.loads(dom_path.read_text())==rows
identity.update(live_browser_dom_equals_csv=True,browser_dom_sha256=sha256(dom_path.read_bytes()).hexdigest(),receipt_sha256=sha256(receipt.read_bytes()).hexdigest())
for name in ['output/result.json','output/response.md','output/evaluation_summary.csv','output/audit.json']:
 data=(base/name).read_bytes();measured[name]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
assert json.loads((base/'output/result.json').read_bytes())['output_sha256']==identity['csv_sha256']
assert stage['unverified_investigation_text']==(base/'output/response.md').read_text()
scores,_=read(base/'output/evaluation_summary.csv')
early={r['model']:r for r in scores if r['split']=='selection' and r['horizon_days']=='7'}
later={r['model']:r for r in scores if r['split']=='holdout' and r['horizon_days']=='7'}
assert min(early,key=lambda m:float(early[m]['mae']))=='shared_seasonal'
larger=float(later['shared_seasonal']['mae'])/float(later['recent_13_weeks']['mae'])-1
assert round(larger*100)==6
assert abs(float(later['shared_seasonal']['bias_fraction']))<abs(float(later['recent_13_weeks']['bias_fraction']))
details=json.loads((base/'output/audit.json').read_bytes())
assert round(details['workload']['runtime_seconds'])==14
result={'reviewer':'Codex / plain-language-and-CSV-preview reviewer','reviewed_at':datetime.now(timezone.utc).isoformat(),
 'source_commit':'b243957ed381528908f7594cd8e5d1b7b98203ba','run_root':str(base),'auditor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
 'decision':'pass_for_exploratory_outputs_and_chosen_scenario_arithmetic','arithmetic':arithmetic,'identity':identity,'measured_files':measured,'checked_larger_mae_vs_13weeks':larger,
 'manual_response_review':{
  'current_process':'Original question describes recent months of sales broadly. Response says exact rule absent and cannot establish improvement over actual current process.',
  'comparison':'Selected on July-September. Later October-November errors approximately 6% larger than 13-week average are acknowledged; smaller total-demand bias is supported. No superiority claim.',
  'local_cost':'Actual local Python/pandas/numpy computation and measured 14.192 s full analysis support ordinary computer/no paid routine model service. Computer/electricity costs acknowledged; separate AI build price unknown.',
  'scope':'Held-aside October-November development periods are not the reserved December final acceptance holdout. No full frozen pipeline, authenticated verifier/parent gate or milestone acceptance granted.'}}
Path(__file__).with_name('case1-retake-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'decision':result['decision'],'arithmetic':arithmetic,'identity':identity}))
