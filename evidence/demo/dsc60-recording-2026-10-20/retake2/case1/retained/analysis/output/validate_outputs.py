"""Independent quantity checks and validation of delivered artifacts."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd

def run():
    r=pd.read_csv('restocking.csv'); p=pd.read_csv('../released/input-1.csv'); st=pd.read_csv('../released/input-3.csv'); ins=pd.read_csv('../released/input-2.csv')
    raw=pd.read_csv('../released/input-4.csv'); sales=raw.drop_duplicates().copy(); sales.Order_Date=pd.to_datetime(sales.Order_Date)
    good=sales[(sales.Quantity>0)&sales.Order_Status.str.lower().isin(['completed','shipped','returned'])&sales.Order_Date.between('2024-01-01','2025-11-30')]
    merged=r.merge(p,on=['Product_ID','Store_ID'],validate='one_to_one',suffixes=('','_rule')).merge(st,on=['Product_ID','Store_ID'],validate='one_to_one',suffixes=('','_stock'))
    assert len(merged)==336 and len(r)==336
    assert r.OrderQty.ge(0).all() and (r.OrderQty%1==0).all()
    assert r.Quantity_Unit.eq('product_unit').all()
    assert not set(['Provenance','Synthetic','Illustrative_Synthetic_Stock']) & set(r)
    assert ((merged.OrderQty==0)|((merged.OrderQty>=merged.Minimum_Order_Qty)&(merged.OrderQty%merged.Order_Multiple_Qty==0))).all()
    differences=[]
    for _,row in merged.iterrows():
        x=good[(good.Product_ID==row.Product_ID)&(good.Store_ID==row.Store_ID)].groupby('Order_Date').Quantity.sum().sort_index()
        rate=0.
        if len(x):
            z=float(x.iloc[0]); gap=float((x.index[0]-pd.Timestamp('2024-01-01')).days+1)
            for k in range(1,len(x)):
                z=.9*z+.1*x.iloc[k]; gap=.9*gap+.1*(x.index[k]-x.index[k-1]).days
            rate=.95*z/gap
        h=int(row.Supplier_Lead_Time_Days+row.Review_Period_Days)
        inbound=ins[(ins.Product_ID==row.Product_ID)&(ins.Store_ID==row.Store_ID)]
        timely=inbound[pd.to_datetime(inbound.Expected_Arrival_Date).between(pd.Timestamp('2025-12-01'),pd.Timestamp('2025-11-30')+pd.Timedelta(days=h))].Incoming_Qty.sum()
        need=max(0,rate*h+row.Safety_Stock_Qty_rule-row.Usable_On_Hand_Qty_stock-timely)
        qty=0 if need<=1e-9 else math.ceil(max(need,row.Minimum_Order_Qty)/row.Order_Multiple_Qty)*row.Order_Multiple_Qty
        assert qty==row.OrderQty
        differences.append(abs(rate*h-row.Forecast_Coverage_Units))
    scores=pd.read_csv('comparison_scores.csv',index_col=0); detail=pd.read_csv('comparison_detail.csv')
    recompute=detail.groupby('method').absolute_error.mean()
    assert np.allclose(recompute.sort_index(),scores.primary_mae.sort_index())
    assert scores.primary_mae.idxmin()=='croston_sba'
    d=detail.pivot(index=['origin','Product_ID','Store_ID'],columns='method',values='absolute_error')
    origin_delta=(d.mean84-d.croston_sba).groupby('origin').mean()
    store_delta=(d.mean84-d.croston_sba).groupby('Store_ID').mean()
    hashes={'input-1.csv':'333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6','input-2.csv':'1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a','input-3.csv':'3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9','input-4.csv':'48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8'}
    assert all(hashlib.sha256((Path('../released')/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
    v={'independent_order_recomputation_all_rows':True,'independent_aggregation':'Long-form daily fulfilled rows and observed inter-sale date gaps; no forecast/calendar helper used','max_forecast_display_rounding_error':max(differences),'integer_nonnegative_unit_and_policy_checks':True,'all_336_keys_covered':True,'released_hashes_match_manifest':True,'aggregate_scores_recomputed_from_detail':True,'origin_wins':int((origin_delta>0).sum()),'origins':len(origin_delta),'store_wins':int((store_delta>0).sum()),'stores':len(store_delta),'origin_mae_improvements_units':origin_delta.to_dict(),'store_mae_improvements_units':store_delta.to_dict(),'zero_recent_sales_flags':int(r.Review_Flag.fillna('').str.contains('No fulfilled').sum()),'positive_orders_among_zero_recent_flags':int(((r.OrderQty>0)&r.Review_Flag.fillna('').str.contains('No fulfilled')).sum()),'limitation':'Same released data, alternative arithmetic checks; not independent external stock verification. Origins overlap and are development only.','reserved_outcomes_accessed':False}
    Path('validation.json').write_text(json.dumps(v,indent=2))
    digest=hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()
    Path('result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':digest},indent=2))
    print(json.dumps(v,indent=2));return v

if __name__=='__main__':run()
