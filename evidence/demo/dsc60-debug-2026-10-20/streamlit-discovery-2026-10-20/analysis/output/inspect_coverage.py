import pandas as pd
d=pd.read_csv('../released/input-4.csv').drop_duplicates()
d['date']=pd.to_datetime(d.Order_Date); d['status']=d.Order_Status.str.strip().str.lower()
days=pd.date_range(d.date.min(),d.date.max())
print('network missing days',len(days.difference(d.date.unique())))
for s,g in d.groupby('Store_ID'):
 print(s,'dates',g.date.nunique(),'missing2025',len(pd.date_range('2025-01-01','2025-11-30').difference(g.date.unique())), 'first',str(g.date.min().date()))
print('bad quantities',d.loc[d.Quantity<=0,['Order_Date','Product_ID','Store_ID','Quantity','Order_Status','Return_Flag']].to_string(index=False))
print('order duplicate count',d.Order_ID.duplicated().sum())
print('all pairs',d.groupby(['Product_ID','Store_ID']).size().describe().to_dict())
print('recent store weeks complete days distribution',d.loc[d.date>='2025-01-01'].assign(week=lambda x:x.date.dt.to_period('W-SUN').dt.start_time).groupby(['Store_ID','week']).date.nunique().value_counts().sort_index().to_dict())
