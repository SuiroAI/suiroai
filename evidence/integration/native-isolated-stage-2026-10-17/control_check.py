import csv,json,errno,socket
from pathlib import Path
released=Path('/private/tmp/dsc26-native-isolation-zkaavghj/released/synthetic.csv')
rows=list(csv.DictReader(released.open()))
totals={}
for row in rows: totals[row['product']]=totals.get(row['product'],0)+int(row['units'])
positive={'row_count':len(rows),'group_totals':totals,'total_units':sum(totals.values())}
Path('/private/tmp/dsc26-native-isolation-zkaavghj/output/model-control-result.json').write_text(json.dumps(positive))
checks={}
for name,path,mode in [('sentinel_open', '/private/tmp/dsc26-native-isolation-zkaavghj/unreleased/sentinel.txt', 'rb'), ('symlink_open', '/private/tmp/dsc26-native-isolation-zkaavghj/output/denied-link', 'rb'), ('input_write', '/private/tmp/dsc26-native-isolation-zkaavghj/released/synthetic.csv', 'wb'), ('outside_write', '/private/tmp/dsc26-native-isolation-zkaavghj/unreleased/new-denied-file.txt', 'xb')]:
 try:
  with open(path,mode) as stream:
   if mode=='rb': stream.read(1)
  checks[name]={'denied':False}
 except PermissionError as exc:
  checks[name]={'denied':True,'type':type(exc).__name__,'errno':exc.errno}
try:
 with socket.create_connection(('127.0.0.1', 50424),timeout=2): pass
 checks['network']={'denied':False}
except PermissionError as exc:
 checks['network']={'denied':True,'type':type(exc).__name__,'errno':exc.errno}
print(json.dumps({'positive':positive,'checks':checks}))
raise SystemExit(0 if all(item.get('denied') for item in checks.values()) else 7)
