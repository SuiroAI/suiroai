"""Independently recompute the DSC-59 final run's CSV and development scores.

Use only Python's standard library and exact released inputs. Never execute
Data-generated code. Check declared analytical choices and cross-file agreement;
this is bounded evidence, not a claim of full milestone acceptance.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
from datetime import date,timedelta
from collections import Counter,defaultdict
import calendar,csv,hashlib,json,math
ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'artifacts/demo/b0236c43fec24b4d8840031f9bae3120/runs/investigation-d840e0b79fe8469e911482ad6d956ef8'
ASOF=date(2025,11,30)
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
def key(r):return r['Product_ID'],r['Store_ID']
raw,stock,inbound,policy=[read(RUN/'released'/f'input-{i}.csv') for i in range(1,5)]
out=read(RUN/'output/restocking.csv');audit=json.loads((RUN/'output/audit.json').read_text());scores=read(RUN/'output/model_comparison.csv');folds=read(RUN/'output/backtest_origins.csv')
seen=set();sales=[]
for r in raw:
    value=tuple(r.items())
    if value not in seen:seen.add(value);sales.append(r)
gross=[r for r in sales if int(r['Quantity'])>0 and r['Order_Status'].strip().lower() in {'completed','shipped','returned'}]
net=[r for r in gross if r['Order_Status'].strip().lower()!='returned' and r['Return_Flag'].lower()!='yes']
keys=[key(r) for r in stock];stocks,policies=[{key(r):r for r in f} for f in [stock,policy]]
errors=[]
def check(label,actual,expected,tolerance=1e-8):
    valid=abs(actual-expected)<=tolerance if isinstance(actual,(int,float)) and isinstance(expected,(int,float)) else actual==expected
    if not valid:errors.append({'check':label,'actual':actual,'expected':expected})
def quantities(data,start,end):
    totals=Counter()
    for row in data:
        if start<=date.fromisoformat(row['Order_Date'])<=end:totals[key(row)]+=int(row['Quantity'])
    return totals
def rates(data,origin,window,shrink,seasonal):
    q=quantities(data,origin-timedelta(days=window-1),origin);products,stores=Counter(),Counter()
    for (p,s),n in q.items():products[p]+=n;stores[s]+=n
    total=sum(q.values());factor=1.
    if seasonal:
        exposure=Counter();d=date(2022,1,1);end=date(origin.year-1,12,31)
        while d<=end:exposure[d.month]+=1;d+=timedelta(days=1)
        historical=Counter()
        for r in data:
            d=date.fromisoformat(r['Order_Date'])
            if d.year<origin.year:historical[d.month]+=int(r['Quantity'])
        month=(origin+timedelta(days=1)).month
        factor=(historical[month]/exposure[month])/(sum(historical.values())/sum(exposure.values()))
    return {k:((q[k]+shrink*products[k[0]]*stores[k[1]]/total/window)/(window+shrink) if shrink else q[k]/window)*factor for k in keys},factor
fold_index={(r['Origin'],int(r['Window']),int(r['Shrink']),r['Seasonal']=='True'):r for r in folds}
for score in scores:
    window,shrink,seasonal=int(score['Window']),int(score['Shrink']),score['Seasonal']=='True';ae=se=actual_total=bias=0
    for year,month in [(2024,12)]+[(2025,m) for m in range(1,11)]:
        origin=date(year,month,calendar.monthrange(year,month)[1]);rate,_=rates(gross,origin,window,shrink,seasonal);actual=quantities(gross,origin+timedelta(days=1),origin+timedelta(days=14));pred={k:r*14 for k,r in rate.items()};a=sum(abs(pred[k]-actual[k]) for k in keys);s=sum((pred[k]-actual[k])**2 for k in keys);t=sum(actual.values());b=sum(pred[k]-actual[k] for k in keys)
        row=fold_index[origin.isoformat(),window,shrink,seasonal]
        for field,value in {'AbsoluteError':a,'SquaredError':s,'ActualUnits':t,'BiasUnits':b}.items():check(f'fold{origin}/{window}/{shrink}/{seasonal}/{field}',float(row[field]),value)
        ae+=a;se+=s;actual_total+=t;bias+=b
    for field,value in {'AbsoluteError':ae,'SquaredError':se,'ActualUnits':actual_total,'BiasUnits':bias,'WAPE':ae/actual_total,'RMSE':math.sqrt(se/(11*336))}.items():check(f'score{window}/{shrink}/{seasonal}/{field}',float(score[field]),value)
best=min(scores,key=lambda r:float(r['RMSE']));w,sh,season=int(best['Window']),int(best['Shrink']),best['Seasonal']=='True';rate,factor=rates(gross,ASOF,w,sh,season);netrate,_=rates(net,ASOF,w,sh,season);ledger=defaultdict(list)
for r in inbound:ledger[key(r)].append(r)
def order(k,r,receipts=True):
    s,p=stocks[k],policies[k];h=int(p['Supplier_Lead_Time_Days'])+int(p['Review_Period_Days']);credit=sum(int(v['Incoming_Qty']) for v in ledger[k] if date.fromisoformat(v['Expected_Arrival_Date'])<=ASOF+timedelta(days=h)) if receipts else 0;target=math.ceil(r*h+int(p['Safety_Stock_Qty'])-1e-10);gap=max(0,target-int(s['Usable_On_Hand_Qty'])-credit);pack=int(p['Order_Multiple_Qty']);qty=math.ceil(max(gap,int(p['Minimum_Order_Qty']))/pack)*pack if gap else 0
    risk=max([0.]+[r*d-int(s['Usable_On_Hand_Qty'])-sum(int(v['Incoming_Qty']) for v in ledger[k] if date.fromisoformat(v['Expected_Arrival_Date'])<=ASOF+timedelta(days=d)) for d in range(1,int(p['Supplier_Lead_Time_Days']))])
    return qty,target,credit,r*h,risk
sums=Counter();sens=defaultdict(Counter)
for row in out:
    k=key(row);qty,target,credit,demand,risk=order(k,rate[k]);p=policies[k]
    expected={'OrderQty':qty,'Target_Stock_Qty':target,'Credited_Inbound_Qty':credit,'Forecast_Protection_Units':round(demand,4),'Expected_PreArrival_Shortfall_Units':round(risk,4),'Protection_Days':int(p['Supplier_Lead_Time_Days'])+int(p['Review_Period_Days'])}
    for field,value in expected.items():check(str(k)+'/'+field,float(row[field]),value)
    for field in ['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty','Safety_Stock_Qty']:check(str(k)+'/'+field,int(row[field]),int(p[field]))
    check(str(k)+'/onhand',int(row['Usable_On_Hand_Qty']),int(stocks[k]['Usable_On_Hand_Qty']));check(str(k)+'/ledger',sum(int(v['Incoming_Qty']) for v in ledger[k]),int(stocks[k]['On_Order_Qty']));check(str(k)+'/units',row['Quantity_Unit'],'product_unit')
    check(str(k)+'/end',row['Protection_End_Date'],(ASOF+timedelta(days=expected['Protection_Days'])).isoformat())
    scenarios={'Demand_Minus25Pct':(rate[k]*.75,True),'Demand_Plus25Pct':(rate[k]*1.25,True),'Demand_Double':(rate[k]*2,True),'No_Inbound_Arrives':(rate[k],False),'Exclude_Returned_Sales':(netrate[k],True)}
    for name,(r,rec) in scenarios.items():
        value=order(k,r,rec)[0];check(str(k)+'/'+name,int(row[name+'_OrderQty']),value);sens[name]['total_units']+=value;sens[name]['positive_pairs']+=value>0;sens[name]['changed_pairs']+=value!=qty
    sums['units']+=qty;sums['positive_pairs']+=qty>0;sums['zero_pairs']+=qty==0;sums['prearrival_risk_pairs']+=round(risk,4)>0;sums['onhand']+=int(stocks[k]['Usable_On_Hand_Qty']);sums['inbound']+=credit
for field,value in sums.items():check('total/'+field,audit['orders'][field],value)
for name,values in sens.items():
    for field,value in values.items():check('sensitivity/'+name+'/'+field,audit['sensitivities'][name][field],value)
check('rows',len(out),336);check('unique keys',len({key(r) for r in out}),336);check('key coverage',{key(r) for r in out},set(stocks));check('duplicate removed',audit['exact_duplicates_removed'],len(raw)-len(sales));check('gross units',audit['fulfilled_positive_units'],sum(int(r['Quantity']) for r in gross));check('seasonfactor',audit['december_factor'],factor)
# Compare HTML's rendered recommendation cells with the CSV, independently.
from html.parser import HTMLParser
class RecommendationCells(HTMLParser):
    def __init__(self):
        super().__init__();self.in_table=False;self.in_cell=False;self.buffer=[];self.cells=[]
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.in_table=dict(attrs).get('id')=='recommendations'
        if tag=='td' and self.in_table:self.in_cell=True;self.buffer=[]
    def handle_data(self,data):
        if self.in_cell:self.buffer.append(data)
    def handle_endtag(self,tag):
        if tag=='td' and self.in_cell:self.cells.append(''.join(self.buffer));self.in_cell=False
        if tag=='table':self.in_table=False
html_path=RUN/'output/report.html';html_agreement=None
if html_path.exists():
    parser=RecommendationCells();parser.feed(html_path.read_text())
    expected_cells=[row[field] for row in out for field in out[0]]
    html_agreement=parser.cells==expected_cells
    check('HTML CSV exact cell agreement',html_agreement,True)
# Recover labels only from nonmissing source labels for their own product IDs.
names=defaultdict(set)
for row in sales:
    if row['Product_Name']:names[row['Product_ID']].add(row['Product_Name'])
for row in out:
    check(str(key(row))+'/product name',names[row['Product_ID']],{row['Product_Name']})
for row in read(RUN/'output/store_summary.csv'):
    subset=[v for v in out if v['Store_ID']==row['Store_ID']]
    for field,value in {'OrderUnits':sum(int(v['OrderQty']) for v in subset),'PositivePairs':sum(int(v['OrderQty'])>0 for v in subset),'PreArrivalRiskPairs':sum(float(v['Expected_PreArrival_Shortfall_Units'])>0 for v in subset)}.items():check('store/'+row['Store_ID']+'/'+field,int(row[field]),value)
check('latest source date',max(row['Order_Date'] for row in sales),'2025-11-30')
manifest=json.loads((RUN/'output/result.json').read_text())
check('manifest CSV hash',manifest['output_sha256'],hashlib.sha256((RUN/'output/restocking.csv').read_bytes()).hexdigest())
if html_path.exists():check('manifest HTML hash',manifest['html_sha256'],hashlib.sha256(html_path.read_bytes()).hexdigest())
summary={'format':'dsc59-final-independent-audit-v1','scope':'Independent bounded recomputation; not full milestone verification','generated_code_executed':False,'run':str(RUN),'pass':not errors,'error_count':len(errors),'errors':errors,'rows':len(out),'html_csv_exact_cell_agreement':html_agreement,'html_sha256':hashlib.sha256(html_path.read_bytes()).hexdigest() if html_path.exists() else None,'folds':len(folds),'candidate_models':len(scores),'selected_model':best,'totals':dict(sums),'sensitivities':{k:dict(v) for k,v in sens.items()},'source_sha256':{f'input-{i}.csv':hashlib.sha256((RUN/'released'/f'input-{i}.csv').read_bytes()).hexdigest() for i in range(1,5)},'output_sha256':hashlib.sha256((RUN/'output/restocking.csv').read_bytes()).hexdigest(),'limits':['Checks declared Data treatment; does not establish transaction semantics, complete latent demand, or historical information availability.','Selection and performance use same11development origins; no untouchedDecember holdout used.','Selected model chosen byRMSE, WAPE120.87%; measured improvement over zero forecast does not prove high precision.','HTML recommendation table matches all CSV cells; browser rendering and downloaded-byte acceptance are handled separately by the parent.']}
(Path(__file__).parent/'final-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in {'errors','source_sha256','limits','sensitivities'}},indent=2))
