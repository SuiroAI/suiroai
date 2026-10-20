#!/usr/bin/env python3
"""Weekly recorded-unit forecasting and order-up-to calculation; no network/LLM use."""
import argparse, json, math, time, sys, resource
from pathlib import Path
import numpy as np
import pandas as pd

KEYS=['Product_ID','Store_ID']
SELECTED='croston_sba'  # Frozen v1: minimum development coverage MAE, small advantage.

def check(condition,message):
    if not condition: raise ValueError(message)

def dates(frame,column):
    frame[column]=pd.to_datetime(frame[column],format='%Y-%m-%d',errors='raise')
    check(frame[column].notna().all(),f'Missing {column}')

def load_sales(path,planning,keys,mode='gross'):
    # Read only useful columns; never use transaction inventory as current stock.
    cols=['Transaction_ID','Order_Date','Product_ID','Store_ID','Product_Name','Quantity','Order_Status','Return_Flag']
    raw=pd.read_csv(path)
    raw=raw.drop_duplicates()
    check(not raw.Transaction_ID.duplicated().any(),'Conflicting transaction IDs')
    d=raw[cols].copy(); del raw
    dates(d,'Order_Date')
    check(d.Order_Date.max()<=planning,'Sales contain dates beyond planning date')
    check(d[[c for c in cols if c!='Product_Name']].notna().all().all(),'Missing required sales fields')
    d.Order_Status=d.Order_Status.str.strip().str.lower()
    check(d.Order_Status.isin(['completed','shipped','returned','processing','cancelled']).all(),'Unknown order status')
    check(d.Return_Flag.isin(['Yes','No']).all(),'Unknown return flag')
    check(pd.to_numeric(d.Quantity,errors='coerce').notna().all(),'Invalid quantity')
    check((d.Quantity%1==0).all(),'Noninteger sales quantities')
    all_dates=pd.date_range(d.Order_Date.min(),planning)
    check(len(all_dates.difference(d.Order_Date.unique()))==0,'Missing global sales dates: coverage not established')
    observed=set(map(tuple,d[KEYS].drop_duplicates().values))
    check(set(keys).issubset(observed),'Policy keys missing sales history')
    name_counts=d.groupby('Product_ID').Product_Name.nunique()
    names=d.dropna(subset=['Product_Name']).drop_duplicates('Product_ID').set_index('Product_ID').Product_Name.to_dict()
    names={k:v for k,v in names.items() if name_counts[k]==1}
    eligible=['completed','shipped','returned']+(['processing'] if mode=='include_processing' else [])
    good=d.Quantity.gt(0)&d.Order_Status.isin(eligible)
    if mode=='exclude_returns': good &= d.Order_Status.ne('returned')&d.Return_Flag.eq('No')
    s=d[good]
    matrix=s.groupby(['Order_Date']+KEYS).Quantity.sum().unstack(KEYS).reindex(index=all_dates,columns=pd.MultiIndex.from_tuples(keys,names=KEYS)).fillna(0)
    return matrix,names

def forecast(matrix,origin,days,method,keys):
    origin=pd.Timestamp(origin)
    train=matrix.loc[:origin]
    check(len(train)>=84,'At least 84 days of covered sales needed')
    future=pd.date_range(origin+pd.Timedelta(days=1),periods=days)
    if method.startswith('mean'):
        tf=time.perf_counter();n=int(method[4:]); rate=train.tail(n).mean().to_numpy()
        fit=time.perf_counter()-tf;ti=time.perf_counter();pred=np.tile(rate,(days,1))
        return pred,{'fit_seconds':fit,'inference_seconds':time.perf_counter()-ti,'retained_array_bytes':int(train.tail(n).to_numpy().nbytes)}
    end=origin-pd.Timedelta(days=(origin.weekday()+1)%7)
    weektrain=train.loc[:end].tail(104*7)
    check(len(weektrain)==104*7,'104 complete training weeks needed')
    weekly=weektrain.to_numpy().reshape(104,7,len(keys)).sum(axis=1)
    t0=time.perf_counter()
    if method=='croston_sba':
        rates=[]
        for y in weekly.T:
            z=None; interval=None; gap=0
            for value in y:
                gap+=1
                if value>0:
                    if z is None: z=float(value); interval=float(gap)
                    else: z+=.1*(value-z); interval+=.1*(gap-interval)
                    gap=0
            rates.append(0 if z is None else .95*z/interval/7)
        fitted=time.perf_counter()-t0; ti=time.perf_counter()
        pred=np.tile(rates,(days,1))
        return pred,{'fit_seconds':fitted,'inference_seconds':time.perf_counter()-ti,'retained_array_bytes':int(weekly.nbytes)}
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.linear_model import PoissonRegressor
    from scipy.sparse import hstack,csr_matrix
    def features(ds):
        return pd.DataFrame({'product':np.tile([k[0] for k in keys],len(ds)), 'store':np.tile([k[1] for k in keys],len(ds)), 'month':np.repeat(ds.month.astype(str),len(keys))})
    centers=pd.DatetimeIndex(weektrain.index[3::7])
    enc=OneHotEncoder(handle_unknown='ignore')
    Xcat=enc.fit_transform(features(centers))
    def trend(ds):return csr_matrix(np.repeat(np.asarray((ds-pd.Timestamp('2022-01-01')).days)/365.25,len(keys)).reshape(-1,1))
    X=hstack([Xcat,trend(centers)],format='csr')
    model=PoissonRegressor(alpha=.1,max_iter=300,tol=1e-7)
    model.fit(X,weekly.reshape(-1))
    fitted=time.perf_counter()-t0; ti=time.perf_counter()
    XF=hstack([enc.transform(features(future)),trend(future)],format='csr')
    pred=model.predict(XF).reshape(days,len(keys))/7
    return pred,{'fit_seconds':fitted,'inference_seconds':time.perf_counter()-ti,'retained_array_bytes':int(weekly.nbytes+X.data.nbytes+X.indices.nbytes+X.indptr.nbytes+model.coef_.nbytes),'fit_iterations':int(model.n_iter_)}

def load_operations(stock_path,deliveries_path,policy_path,planning):
    stock=pd.read_csv(stock_path); receipts=pd.read_csv(deliveries_path); policy=pd.read_csv(policy_path)
    for df,label in [(stock,'stock'),(policy,'policy'),(receipts,'deliveries')]:
        check(df[KEYS+['Quantity_Unit']].notna().all().all(),f'Missing {label} keys/units')
        check(df.Quantity_Unit.eq('product_unit').all(),f'Unsupported {label} units')
    check(not stock.duplicated(KEYS).any(),'Duplicate stock keys')
    dates(stock,'Snapshot_Date'); dates(policy,'Effective_Date');dates(receipts,'Order_Date');dates(receipts,'Expected_Arrival_Date')
    check(stock.Snapshot_Date.eq(planning).all(),'Stock snapshot must equal planning date')
    policy=policy[policy.Effective_Date<=planning].sort_values('Effective_Date')
    check(not policy.duplicated(KEYS+['Effective_Date']).any(),'Duplicate effective policy rows')
    policy=policy.drop_duplicates(KEYS,keep='last').sort_values(KEYS).reset_index(drop=True)
    for df,cols,positive in [(stock,['Usable_On_Hand_Qty','On_Order_Qty'],False),(receipts,['Incoming_Qty'],False),(policy,['Supplier_Lead_Time_Days','Review_Period_Days','Order_Multiple_Qty','Minimum_Order_Qty'],True),(policy,['Safety_Stock_Qty'],False)]:
        for c in cols:
            vals=pd.to_numeric(df[c],errors='coerce')
            check(vals.notna().all() and (vals%1==0).all() and (vals>=(1 if positive else 0)).all(),f'Invalid {c}')
    keyset=set(map(tuple,policy[KEYS].values))
    check(keyset==set(map(tuple,stock[KEYS].values)),'Policy/stock population mismatch')
    check(set(map(tuple,receipts[KEYS].values)).issubset(keyset),'Unknown delivery key')
    check(not receipts.PO_Line_ID.duplicated().any(),'Duplicate incoming purchase-order line')
    check((receipts.Order_Date<=planning).all(),'Incoming orders not yet placed as of planning date')
    check((receipts.Expected_Arrival_Date>=receipts.Order_Date).all(),'Receipt before order')
    complete=stock.Open_Order_Ledger_Complete.astype(str).str.lower().eq('true')
    check(complete.all(),'Complete incoming ledger required')
    onorder=receipts.groupby(KEYS).Incoming_Qty.sum().reindex(pd.MultiIndex.from_frame(stock[KEYS]),fill_value=0).to_numpy()
    check(np.array_equal(onorder,stock.On_Order_Qty.to_numpy()),'Incoming deliveries do not match stock on-order quantities')
    return stock,receipts,policy

def run(sales_path,stock_path,deliveries_path,policy_path,planning_date,output_path):
    prep=time.perf_counter(); planning=pd.Timestamp(planning_date)
    check(planning==planning.normalize(),'Planning date must be a calendar date')
    out=Path(output_path).resolve()
    inputs=[Path(x).resolve() for x in [sales_path,stock_path,deliveries_path,policy_path]]
    check(out not in inputs,'Output cannot overwrite a source file')
    stock,receipts,policy=load_operations(stock_path,deliveries_path,policy_path,planning)
    keys=list(map(tuple,policy[KEYS].values))
    matrix,names=load_sales(sales_path,planning,keys)
    prep_seconds=time.perf_counter()-prep
    horizon=int((policy.Supplier_Lead_Time_Days+policy.Review_Period_Days).max())
    ft=time.perf_counter();pred,model_stats=forecast(matrix,planning,max(7,horizon),SELECTED,keys);forecast_seconds=time.perf_counter()-ft
    op=time.perf_counter();stock=stock.set_index(KEYS);rows=[]
    for col,p in policy.iterrows():
        key=keys[col];inv=stock.loc[key]; lead=int(p.Supplier_Lead_Time_Days); cover=lead+int(p.Review_Period_Days)
        arrivals=receipts[(receipts.Product_ID==key[0])&(receipts.Store_ID==key[1])]
        due=planning+pd.Timedelta(days=lead); end=planning+pd.Timedelta(days=cover)
        overdue=arrivals.Expected_Arrival_Date.le(planning)
        eligible=arrivals.Expected_Arrival_Date.gt(planning)&arrivals.Expected_Arrival_Date.le(end)
        incoming=int(arrivals.loc[eligible,'Incoming_Qty'].sum());stockqty=int(inv.Usable_On_Hand_Qty)
        demand=float(pred[:cover,col].sum());needed=max(0,demand+int(p.Safety_Stock_Qty)-stockqty-incoming)
        multiple=int(p.Order_Multiple_Qty)
        order=0 if needed<=1e-10 else int(math.ceil(max(needed,int(p.Minimum_Order_Qty))/multiple)*multiple)
        balance=float(stockqty);short=0.;first=''
        # Receipts conservatively available at end of their due day.
        for day in range(1,lead+1):
            date=planning+pd.Timedelta(days=day);balance-=pred[day-1,col]
            if balance < -1e-10 and not first:first=date.strftime('%Y-%m-%d')
            short=max(short,-balance)
            balance+=float(arrivals.loc[arrivals.Expected_Arrival_Date.eq(date),'Incoming_Qty'].sum())
        flags=[]
        if short>1e-10:flags.append('REVIEW_SHORTAGE_BEFORE_RECEIPT')
        if overdue.any():flags.append('OVERDUE_INCOMING_EXCLUDED')
        if arrivals.Expected_Arrival_Date.gt(end).any():flags.append('INCOMING_AFTER_COVERAGE_EXCLUDED')
        if matrix.loc[planning-pd.Timedelta(days=83):planning].iloc[:,col].sum()==0:flags.append('NO_RECORDED_UNITS_LAST_84_DAYS')
        rows.append({'Product_ID':key[0],'Product_Name':names.get(key[0],''),'Store_ID':key[1],'OrderQty':order,'Quantity_Unit':'product_unit','Planning_Date':planning.strftime('%Y-%m-%d'),'Expected_New_Order_Arrival':due.strftime('%Y-%m-%d'),'Coverage_End_Date':end.strftime('%Y-%m-%d'),'Forecast_Next_7_Days':round(float(pred[:7,col].sum()),3),'Forecast_Coverage_Units':round(demand,3),'Usable_On_Hand_Qty':stockqty,'Incoming_Within_Coverage_Qty':incoming,'Safety_Stock_Qty':int(p.Safety_Stock_Qty),'Order_Multiple_Qty':multiple,'Minimum_Order_Qty':int(p.Minimum_Order_Qty),'Potential_Shortage_Before_Receipt_Qty':int(math.ceil(max(0,short)-1e-10)),'First_Potential_Shortage_Date':first,'Review_Flags':';'.join(flags)})
    result=pd.DataFrame(rows);result.to_csv(out,index=False)
    return result,{'selected_method':SELECTED,'preparation_seconds':prep_seconds,'forecast_total_seconds':forecast_seconds,'model':model_stats,'ordering_and_write_seconds':time.perf_counter()-op,'matrix_shape':list(matrix.shape),'matrix_bytes':int(matrix.to_numpy().nbytes)}

def main():
    started=time.perf_counter()
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['sales-path','stock-path','deliveries-path','policy-path','planning-date','output-path']:parser.add_argument('--'+name,required=True)
    a=parser.parse_args()
    try:
        result,stats=run(**vars(a)); print(json.dumps({'rows':len(result),'units_to_order':int(result.OrderQty.sum()),'run_seconds_excluding_imports':time.perf_counter()-started,'process_high_water_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)),**stats}))
    except (ValueError,KeyError,FileNotFoundError) as e:parser.exit(2,f'Input error: {e}\n')
if __name__=='__main__':main()
