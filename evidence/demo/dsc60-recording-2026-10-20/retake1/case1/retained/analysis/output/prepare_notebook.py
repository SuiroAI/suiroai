"""Save a small executed internal evidence notebook without starting a notebook server."""
from pathlib import Path
import contextlib,io,json,hashlib
import nbformat as nb

book=nb.v4.new_notebook()
book.metadata['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
book.metadata['execution_method']='Code cells executed top-to-bottom in a shared Python namespace by prepare_notebook.py, stdout captured; no external kernel/server needed.'
book.cells=[
nb.v4.new_markdown_cell('# Restocking development evidence\n\nInternal companion, November 30 scope. Primary reproducible calculations reside in profile_inputs.py, compare_candidates.py, restock_routine.py and audit_checks.py. This notebook reads their executed outputs; it does not claim to rerun model discovery.\n\n## Summary\nSelected Croston SBA yields only a small development MAE advantage. Orders total 875 units across 111 positive lines; 225 zeros. 66 potential pre-receipt shortages warrant review. No independent success gate is met.'),
nb.v4.new_markdown_cell('## Context and methods\n\nGross fulfilled/returned positive units, duplicates removed. No-row days mean zero recorded units conditional on ledger completeness. Eight development origins, all outcomes through November 30. Baseline is an analyst-defined 84-day mean, not the exact incumbent. Historical status knowledge and uncensored demand are unavailable. December outcomes excluded.'),
nb.v4.new_code_cell("import json\nfrom pathlib import Path\nimport pandas as pd\nquality=json.loads(Path('source_treatment.json').read_text())\nprint({k:quality[k] for k in ['rows','exact_duplicates_removed','remaining_duplicate_transaction_ids','invalid_quantity_rows','date_range','global_missing_dates','ledger_mismatches']})"),
nb.v4.new_markdown_cell('## Results\n\nIdentical populations and horizons. MAE units are product units per product at store per forecast period. Exact scores are internal diagnostics. Small pooled changes do not establish service or financial gains. These compact tables directly support the calculations; no additional chart is required for this table-only CSV handoff.'),
nb.v4.new_code_cell("scores=pd.read_csv('comparison_scores.csv')\nprint(scores[['method','kind','MAE','bias']].to_string(index=False))\nprint(pd.read_csv('target_sensitivity.csv').to_string(index=False))"),
nb.v4.new_code_cell("orders=pd.read_csv('restocking.csv')\nprint(orders.groupby('Store_ID').agg(Units=('OrderQty','sum'),Positive_orders=('OrderQty',lambda s:int(s.gt(0).sum()))).to_string())\nchecks=json.loads(Path('validation_results.json').read_text())\nassert checks['independent_full_order_agreement'] and checks['independent_shortage_agreement'] and checks['rerun_byte_agreement']\nprint({k:checks[k] for k in ['rows','order_rows','zero_rows','order_units','shortage_rows','no_recent_recorded_units_rows']})"),
nb.v4.new_code_cell("import hashlib\nrecord=json.loads(Path('routine_measurements.json').read_text())\nassert record['output_sha256']==hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()\nassert record['routine_sha256']==hashlib.sha256(Path('restock_routine.py').read_bytes()).hexdigest()\nprint({'local_calculation_seconds':record['local_calculation_wall_seconds'],'peak_RSS_bytes':record['routine_details']['process_high_water_rss_bytes'],'dependencies':record['dependency_versions']})"),
nb.v4.new_markdown_cell('## Takeaways\n\nWeekly non-LLM CLI replaces repeated aggregation and stock/policy arithmetic. Fixed stock rules, not an optimized availability/excess tradeoff. Peak RSS includes preparation and models; memory fits ordinary 8 GB CPU-only use at this supplied scale. No paid model calls in routine. AI analysis/build cost unknown because usage/pricing absent. Source bytes and internally synthetic operational classifications remain recorded. No reserved outcomes read. Standard numerical validation passed; no HTML report or chart rendering was part of the requested deliverable.')]
namespace={}
for number,cell in enumerate([c for c in book.cells if c.cell_type=='code'],1):
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):exec(compile(cell.source,'analysis_evidence.ipynb','exec'),namespace)
    cell.execution_count=number;cell.outputs=[nb.v4.new_output('stream',name='stdout',text=stream.getvalue())]
nb.validate(book);nb.write(book,'analysis_evidence.ipynb')
print('Notebook top-to-bottom execution and format validation passed.')
for c in book.cells:
    if c.cell_type=='code': print(c.outputs[0].text)
