import pandas as pd
from pathlib import Path
for p in sorted(Path('../released').glob('*.csv')):
 d=pd.read_csv(p); print(p.name,d.shape); print('nulls',d.isna().sum().to_dict()); print('duplicates',d.duplicated().sum())
 if p.name!='input-4.csv':
  for c in d.columns: print(c,d[c].nunique(),str(d[c].unique()[:20]))
 else:
  for c in ['Order_Date','Quantity','Order_Status','Return_Flag','Sales_Channel','Store_ID','Product_ID']:
   print(c,d[c].value_counts(dropna=False).to_dict() if d[c].nunique()<70 else [d[c].min(),d[c].max(),d[c].nunique()])
  print('transaction repeats',d.Transaction_ID.duplicated().sum()); print('product names',d.groupby('Product_ID').Product_Name.nunique().to_dict())
  print('monthly',d.groupby(d.Order_Date.str[:7]).agg(rows=('Quantity','size'),units=('Quantity','sum')).to_string())
  print('status-return',pd.crosstab(d.Order_Status,d.Return_Flag).to_string())
