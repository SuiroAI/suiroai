"""Independently audit the third recorded retail demo's delivered output.

Recompute observed-week demand, pooled and seasonal rates, ordering constraints
and stock warnings directly from the released CSVs with exact fractions.
Check browser DOM/HTML/CSV identity and immutable receipt hashes independently.
No generated producer code is imported or executed; retain no personal rows.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
from datetime import date,timedelta,datetime,timezone
from hashlib import sha256
import csv,io,json,math
base=Path('artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-8640daf60556438891ffee678b5631ad')
measured={}
def read(path):
 data=path.read_bytes();measured[str(path.relative_to(base))]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
 reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''));return list(reader),reader.fieldnames
inputs={}
for path in (base/'released').glob('*.csv'):
 rows,headers=read(path);inputs[frozenset(headers)]=rows
sales=next(v for k,v in inputs.items() if 'Transaction_ID' in k)
stocks=next(v for k,v in inputs.items() if 'Usable_On_Hand_Qty' in k)
rules=next(v for k,v in inputs.items() if 'Supplier_Lead_Time_Days' in k)
receipts=next(v for k,v in inputs.items() if 'PO_Line_ID' in k)
result,headers=read(base/'output/restocking.csv')
key=lambda r:(r['Product_ID'],r['Store_ID'])
stock={key(r):r for r in stocks};policy={key(r):r for r in rules}
assert len(stock)==len(stocks)==len(policy)==len(rules)==len(result)==336
assert set(map(key,result))==set(stock)==set(policy)
firstweek=date(2022,1,3);lastweek=date(2025,11,24)
weeks=[firstweek+timedelta(weeks=n) for n in range((lastweek-firstweek).days//7+1)]
priorweeks=[w for w in weeks if w.year<2025]
recentweeks=set(weeks[-52:]);active=set();weekly=defaultdict(int);networkweekly=defaultdict(int)
seen=set();duplicates=0
for row in sales:
 identity=tuple(row.items())
 if identity in seen:duplicates+=1;continue
 seen.add(identity);when=date.fromisoformat(row['Order_Date']);assert when<=date(2025,11,30)
 week=when-timedelta(days=when.weekday())
 active.add((week,row['Store_ID']))
 if week<firstweek or int(row['Quantity'])<=0 or row['Order_Status'].strip().lower() not in {'completed','shipped','returned'}:continue
 weekly[(week,key(row))]+=int(row['Quantity']);networkweekly[week]+=int(row['Quantity'])
count={s:sum((w,s) in active for w in recentweeks) for _,s in policy}
direct={k:F(sum(weekly[(w,k)] for w in recentweeks),count[k[1]]) for k in policy}
products=defaultdict(F);stores=defaultdict(F)
for (p,s),rate in direct.items():products[p]+=rate;stores[s]+=rate
network=sum(direct.values())
decweeks=[w for w in priorweeks if w.month==12]
factor=F(sum(networkweekly[w] for w in decweeks),len(decweeks))/F(sum(networkweekly[w] for w in priorweeks),len(priorweeks))
factor=min(F(8,5),max(F(13,20),factor))
units=0;warnings=0;low=0;high=0;incomingtotal=0
def order(rate,horizon,rule,inv,incoming):
 gap=rate*horizon+int(rule['Safety_Stock_Qty'])-int(inv['Usable_On_Hand_Qty'])-incoming
 return 0 if gap<=0 else math.ceil(max(gap,int(rule['Minimum_Order_Qty']))/int(rule['Order_Multiple_Qty']))*int(rule['Order_Multiple_Qty'])
for row in result:
 k=key(row);p,s=k;inv=stock[k];rule=policy[k];n=count[s]
 pooled=products[p]*stores[s]/network
 weekrate=(n*direct[k]+8*pooled)/(n+8)*factor
 daily=weekrate/7;horizon=int(rule['Supplier_Lead_Time_Days'])+int(rule['Review_Period_Days'])
 incoming=sum(int(r['Incoming_Qty']) for r in receipts if key(r)==k and date(2025,11,30)<date.fromisoformat(r['Expected_Arrival_Date'])<=date(2025,11,30)+timedelta(days=horizon))
 assert incoming==int(inv['On_Order_Qty'])==int(row['Incoming_In_Planning_Window'])
 assert int(row['Usable_On_Hand_Qty'])==int(inv['Usable_On_Hand_Qty'])
 assert int(row['Planning_Days'])==horizon
 for column in ['Supplier_Lead_Time_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']:assert row[column]==rule[column]
 assert abs(float(weekrate)-float(row['Forecast_Next_Week_Units']))<=.000500001
 expected=order(daily,horizon,rule,inv,incoming);assert expected==int(row['OrderQty']),(k,expected,row['OrderQty'])
 lower=order(daily*F(3,4),horizon,rule,inv,incoming);upper=order(daily*F(5,4),horizon,rule,inv,incoming)
 assert lower==int(row['OrderQty_Demand_25pct_Lower']) and upper==int(row['OrderQty_Demand_25pct_Higher'])
 warning=int(inv['Usable_On_Hand_Qty'])<daily*int(rule['Supplier_Lead_Time_Days'])
 assert bool(row['Expedite_Review'])==warning
 units+=expected;warnings+=warning;low+=lower;high+=upper;incomingtotal+=incoming
arithmetic={'rows_checked':len(result),'order_units':units,'stock_only_warning_rows':warnings,'duplicates_removed':duplicates,'incoming_units_reconciled':incomingtotal,'demand25pct_lower_units':low,'demand25pct_higher_units':high,'method':'Independent exact-rational reconstruction of 52 observed-week local means, product/store pooled means with 8-week prior weight, prior-year weekly seasonal factor, stock/eligible-receipt/buffer/minimum/multiple arithmetic.','limits':'Chosen-scenario arithmetic only. Stock warnings compare current stock to lead demand and do not model receipt timing. No demand-completeness/model-superiority/frozen-holdout/authenticated verifier gate acceptance.'}

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
receipt=session/'runs/attempt-9c979328dc7a4c7081bbddb062366b3b.json';stage=json.loads(receipt.read_text())['stage_result']
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
dom_path=Path(__file__).with_name('case3-table-dom.json')
assert json.loads(dom_path.read_text())==rows
identity.update(live_browser_dom_equals_csv=True,browser_dom_sha256=sha256(dom_path.read_bytes()).hexdigest(),receipt_sha256=sha256(receipt.read_bytes()).hexdigest())
for name in ['output/result.json','output/response.md','output/model_comparisons.csv','output/audit.json']:
 data=(base/name).read_bytes();measured[name]={'sha256':sha256(data).hexdigest(),'bytes':len(data)}
assert json.loads((base/'output/result.json').read_bytes())['output_sha256']==identity['csv_sha256']
assert stage['unverified_investigation_text']==(base/'output/response.md').read_text()
scores,_=read(base/'output/model_comparisons.csv')
later=defaultdict(list);earlier=defaultdict(list)
for row in scores:
 (later if row['split']=='confirmation' else earlier)[row['method']].append(float(row['mae']))
mean=lambda values:sum(values)/len(values)
assert min(earlier,key=lambda m:mean(earlier[m]))=='pooled_52_seasonal'
gain=1-mean(later['pooled_52_seasonal'])/mean(later['average_4'])
details=json.loads((base/'output/audit.json').read_bytes())
assert abs(gain-details['confirmation_improvement_vs_baseline'])<1e-12 and round(gain*100)==9
assert any(mean(values)<mean(later['pooled_52_seasonal']) for m,values in later.items() if m.startswith('average'))
result={'reviewer':'Codex / plain-language-and-CSV-preview reviewer','reviewed_at':datetime.now(timezone.utc).isoformat(),
 'source_commit':'b243957ed381528908f7594cd8e5d1b7b98203ba','run_root':str(base),'auditor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
 'decision':'pass_for_exploratory_outputs_and_chosen_scenario_arithmetic','arithmetic':arithmetic,'identity':identity,'measured_files':measured,'checked_mae_improvement':gain,
 'manual_response_review':{
  'current_process':'Explicit continuation without current approach. Response calls four-week average a comparison baseline and explicitly says it is not the current process.',
  'comparison':'Best in earlier selection, about 9% lower later error versus four-week baseline, explicitly admits other averages did better later and results are mixed.',
  'local_cost':'Actual local Python/pandas/numpy computation and measured 0.286 s support ordinary computer/no paid routine AI calls. Computer/electricity/hosting costs acknowledged; separate AI build price unknown.',
  'scope':'Stock-only warning asks stock checks; does not claim exact shortage accounting for inbound timing. No full frozen December holdout, authenticated verifier/parent gate or milestone acceptance granted.'}}
Path(__file__).with_name('case3-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'decision':result['decision'],'arithmetic':arithmetic,'identity':identity}))
