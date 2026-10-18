import csv
import json
from pathlib import Path


source = Path('/private/tmp/dsc26-native-isolation-zkaavghj/released/synthetic.csv')
row_count = 0
group_totals = {}
total_units = 0

with source.open(newline='', encoding='utf-8') as handle:
    for row in csv.DictReader(handle):
        units = int(row['units'])
        product = row['product']
        row_count += 1
        group_totals[product] = group_totals.get(product, 0) + units
        total_units += units

result = {
    'row_count': row_count,
    'group_totals': group_totals,
    'total_units': total_units,
}
Path('isolation_result.json').write_text(
    json.dumps(result, indent=2) + '\n', encoding='utf-8'
)
print(json.dumps(result))
