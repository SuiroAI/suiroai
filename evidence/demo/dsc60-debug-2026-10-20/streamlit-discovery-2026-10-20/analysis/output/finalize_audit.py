from pathlib import Path
import json, hashlib, io, contextlib
import nbformat as nb
ROOT=Path(__file__).resolve().parent
# Retain the exact first-scored implementation, reconstructed only at the recorded repaired block.
current=(ROOT/'analysis.py').read_text()
fixed='''    product_mean=np.array([np.nanmean(hist[:,pi==j]) for j in range(len(products))]); store_mean=np.array([np.nanmean(hist[:,si==j]) for j in range(len(stores))])
    # Means use observed pair-weeks only; unknown store-weeks never contribute zeros.
    pooled=product_mean[pi]*store_mean[si]/max(np.nanmean(hist),1e-12)'''
initial='''    product_total=np.array([np.nansum(hist[:,pi==j]) for j in range(len(products))]); store_total=np.array([np.nansum(hist[:,si==j]) for j in range(len(stores))])
    # Each fully represented week contributes all pairs; early all-known panel verified.
    pooled=product_total[pi]*store_total[si]/max(np.nansum(hist),1)/len(hist)'''
assert fixed in current
(ROOT/'initial_implementation'/'analysis.py').write_text(current.replace(fixed,initial))
v2=json.loads((ROOT/'evaluation_plan.json').read_text())
v2.update(version=2,written_before_candidate_scores=False,status='Consolidated correction record, written after corrected development scoring; prospective repair is separately recorded in implementation_correction.json before corrected run.',previous_plan='evaluation_plan.json',implementation_correction=json.loads((ROOT/'implementation_correction.json').read_text()),changed_choices=['Observed-only denominators in pooled mean; all candidate specifications, comparison boundaries and selection rule unchanged.'],follow_on_results='exploratory development only')
(ROOT/'evaluation_plan_v2.json').write_text(json.dumps(v2,indent=2)+'\n')

book=nb.v4.new_notebook(metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'execution_method':'Code cells executed top-to-bottom in-process in one fresh Python namespace by finalize_audit.py, with captured standard output; no remote kernel or APIs.'})
book.cells=[
 nb.v4.new_markdown_cell('# Internal restocking evidence companion\n\n## Summary\nThe frozen pooled model orders 880 units across 112 of 336 current products at stores. This is an illustrative calculation using synthetic stock and policy, with a small development error improvement over an analytical baseline. December outcomes remain withheld. The customer explanation is in response.md.'),
 nb.v4.new_markdown_cell('## Context and methods\nSeven common forecast origins, next-week primary absolute-unit error, same recorded-unit target and populations. No true demand zeros are imputed on absent store-days. Missing whole store-weeks are excluded. The exact customer rule is unknown. See task_refinement.json, evaluation_plan.json, implementation_correction.json and internal_audit.md for assumptions and development-only limits. This companion uses compact tables to inspect the requested CSV calculation; no additional report or HTML is created.'),
 nb.v4.new_code_cell("from pathlib import Path\nimport json, hashlib\nimport pandas as pd\nroot = Path.cwd()\naudit = json.loads((root/'source_audit.json').read_text())\nprint(json.dumps({k:audit[k] for k in ['rows_raw','rows_deduplicated','exact_duplicates_removed','gross_target_units','population','stock_receipt_mismatches']}, indent=2))"),
 nb.v4.new_markdown_cell('## Source and code\nApproved inputs are ../released/input-1.csv through input-4.csv. prepare.py inspects sources and freezes the original plan; analysis.py contains comparison models; restock_model.py independently implements the selected routine; validate.py checks every purchase quantity and exported checksum. No notebook cell reruns candidate selection.'),
 nb.v4.new_code_cell("scores = pd.read_csv(root/'comparison_summary.csv')\nprint(scores[(scores.variant=='gross') & (scores.horizon.astype(str)=='7')][['model','n','mae','bias']].to_string(index=False))\nprint('Exploratory target sensitivities:')\nprint(scores[(scores.variant!='gross') & (scores.horizon.astype(str)=='7')][['variant','model','mae']].to_string(index=False))"),
 nb.v4.new_markdown_cell('## Results and checks\nThe selected model has a small absolute-error advantage; its more negative bias and the weak complete-coverage subset advantage do not establish improved availability. The following checks show the final CSV totals, checksum and local runtime workload.'),
 nb.v4.new_code_cell("orders = pd.read_csv(root/'restocking.csv')\nresult = json.loads((root/'result.json').read_text())\nassert hashlib.sha256((root/'restocking.csv').read_bytes()).hexdigest() == result['output_sha256']\nassert len(orders)==336 and orders.OrderQty.ge(0).all()\nprint(orders.groupby('Store_ID').agg(order_units=('OrderQty','sum'), positive_orders=('OrderQty',lambda x:int((x>0).sum()))).to_string())\nprint(json.dumps(json.loads((root/'validation.json').read_text()), indent=2))\nwork = json.loads((root/'routine_workload.json').read_text())\nprint(json.dumps({k:work[k] for k in ['end_to_end_including_imports_seconds','process_peak_rss_bytes_including_imports_and_preparation','retained_model_bytes','training_array_bytes']}, indent=2))"),
 nb.v4.new_markdown_cell('## Takeaways\nApply the list only after replacing synthetic stock/policy with checked real inputs. Treat the 52 pre-arrival flags and zero orders as review priorities where missing records or shortages may hide demand. Routine calculations are CPU-only with pandas and NumPy and no paid model calls. This development investigation cannot close the independent performance-success gate. The same-rate missing-day scenario is exploratory, not a confidence interval. The notebook is table-based and its saved source and text outputs were inspected; no graphical or HTML preview is required for these outputs.')]
scope={}
number=0
for cell in book.cells:
 if cell.cell_type=='code':
  number+=1; stream=io.StringIO()
  with contextlib.redirect_stdout(stream): exec(compile(cell.source,f'analysis.ipynb:cell{number}','exec'),scope)
  cell.execution_count=number; cell.outputs=[nb.v4.new_output('stream',name='stdout',text=stream.getvalue())]
nb.validate(book); nb.write(book,ROOT/'analysis.ipynb')
assert all(c.execution_count is not None and c.outputs for c in book.cells if c.cell_type=='code')
word_count=len((ROOT/'response.md').read_text().split()); assert 150<=word_count<=250,word_count
files=['prepare.py','analysis.py','restock_model.py','validate.py','evaluation_plan.json','evaluation_plan_v2.json','implementation_correction.json','task_refinement.json','source_audit.json','selected_model.npz','restocking.csv','response.md','result.json','comparison_summary.csv','comparison_predictions.csv','scores_by_origin.csv','diagnostics.json','workload.json','routine_workload.json','sensitivity_plan.json','missing_day_sensitivity.csv','validation.json','internal_audit.md','analysis.ipynb']
manifest={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
(ROOT/'artifact_manifest.json').write_text(json.dumps({'purpose':'Reproducibility hashes for development artifacts, not an independent performance-success gate.','artifacts':manifest},indent=2)+'\n')
print('Response words:',word_count,'; executed notebook cells:',number,'; final CSV SHA-256:',manifest['restocking.csv'])
print('Notebook outputs:')
for cell in book.cells:
 if cell.cell_type=='code': print(cell.outputs[0].text)
