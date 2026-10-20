"""Additional target interpretation sensitivity and a small executed evidence notebook."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import nbformat
import pandas as pd
from restock_routine import load_inputs,daily_sales,fit_forecaster,predict_days,order_table,SELECTED_MODEL

def main():
    sales,stock,inbound,policy,date,pairs=load_inputs('../released/input-4.csv','../released/input-3.csv','../released/input-2.csv','../released/input-1.csv','2025-11-30')
    alternate=sales.copy()
    alternate.loc[alternate.status.eq('returned'),'status']='completed'
    daily=daily_sales(alternate,pairs,date)
    pred=predict_days(fit_forecaster(daily,date,SELECTED_MODEL),date,14,len(pairs))
    table=order_table(sales,stock,inbound,policy,date,pairs,pred)
    output=pd.read_csv('restocking.csv')
    extra={'label':'Interpretation sensitivity only, not a revised model selection or scored comparison','alternate_target':'Include positive returned-only status as original fulfilled units, retaining selected mean182 and all operational rules','order_units':int(table.OrderQty.sum()),'changed_order_rows':int(table.OrderQty.ne(output.OrderQty).sum()),'positive_order_rows':int(table.OrderQty.gt(0).sum()),'timing_flags':int(table.Review_Before_Arrival.sum()),'consequence':'Target interpretation uncertainty does not justify crediting returns into usable stock; compare small order changes against frozen main recommendation.'}
    Path('additional_sensitivities.json').write_text(json.dumps(extra,indent=2))
    notebook=nbformat.v4.new_notebook()
    notebook.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    notebook.cells=[
      nbformat.v4.new_markdown_cell('# Restocking development evidence\n\n## tl;dr\nThe predeclared comparison selected mean182. This companion inspects retained evidence; `analysis.py` contains the reproducible original comparison and `measure_and_validate.py` contains the measured CLI invocation and independent arithmetic checks. No untouched evaluation claim is made.'),
      nbformat.v4.new_markdown_cell('## Context & Methods\nAs of 2025-11-30, four released CSVs only. Primary: seven-day equal-weight cumulative product-unit MAE. Candidate and target decisions are in `evaluation_plan.json`.\n\n### Key Assumptions\nMissing pair events mean no recorded transactions conditional on capture, not zero latent demand. Final supplied statuses are frozen labels. Current policy defines coverage; no historical stock simulation is claimed. See `internal_notes.md` for operational and source limitations.'),
      nbformat.v4.new_code_cell("import json\nfrom pathlib import Path\nimport pandas as pd\nprofile=json.loads(Path('source_treatment.json').read_text())\nresults=json.loads(Path('comparison_results.json').read_text())\nvalidation=json.loads(Path('order_validation.json').read_text())\nmeasurement=json.loads(Path('routine_measurements.json').read_text())"),
      nbformat.v4.new_markdown_cell('## Data\nReleased source hashes, population and preparation are retained without personal customer fields.'),
      nbformat.v4.new_code_cell("print(json.dumps({k:profile[k] for k in ['source_files','raw_rows','exact_duplicates_removed','pairs','target_rows','target_units','global_missing_calendar_days','positive_pair_day_fraction','weekly_zero_fraction']},indent=2))"),
      nbformat.v4.new_markdown_cell('## Results\nThree prespecified models; tables retain exact values for review. These are development comparisons. Full per-origin predictions remain in `comparison_predictions.csv`.'),
      nbformat.v4.new_code_cell("print(pd.read_csv('comparison_scores.csv').to_string(index=False))\nprint('Selected:',results['selected_model'])\nprint(pd.read_csv('scores_by_origin.csv').to_string(index=False))"),
      nbformat.v4.new_markdown_cell('## Takeaways\nInspect the order and workload evidence below. Scenario quantities are not confidence bounds. Buffers and pack rules largely determine current orders; timing flags are expected small gaps. Business-facing recommendations are in `response.md`.'),
      nbformat.v4.new_code_cell("print(json.dumps(validation,indent=2))\nprint(json.dumps(json.loads(Path('additional_sensitivities.json').read_text()),indent=2))\nprint('Local calculation seconds:',measurement['local_calculation_wall_seconds_including_python_startup_imports_read_fit_infer_write'])\nprint('Peak process RSS bytes:',measurement['process_peak_rss_bytes'])\nprint('Output agreement:',measurement['output_agreement'])")
    ]
    # Plain Python cells execute sequentially in one namespace; no kernel/temp files needed.
    namespace={};count=0
    for cell in notebook.cells:
        if cell.cell_type=='code':
            count+=1
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):exec(compile(cell.source,'evidence_review.ipynb','exec'),namespace)
            cell.execution_count=count
            cell.outputs=[nbformat.v4.new_output('stream',name='stdout',text=stream.getvalue())]
    nbformat.validate(notebook)
    nbformat.write(notebook,'evidence_review.ipynb')
    # Verify saved notebook text/output and required delivery integrity.
    saved=nbformat.read('evidence_review.ipynb',as_version=4)
    assert all(c.execution_count and c.outputs for c in saved.cells if c.cell_type=='code')
    result=json.loads(Path('result.json').read_text())
    measurement=json.loads(Path('routine_measurements.json').read_text())
    assert set(result)=={'disposition','output_file','output_sha256'}
    assert hashlib.sha256(Path('restocking.csv').read_bytes()).hexdigest()==result['output_sha256']
    assert hashlib.sha256(Path('restock_routine.py').read_bytes()).hexdigest()==measurement['routine_sha256']
    assert 150<=len(Path('response.md').read_text().split())<=250
    assert all(c not in output for c in ['Provenance','Synthetic','Illustrative_Synthetic_Stock'])
    Path('final_checks.json').write_text(json.dumps({'csv_hash_correct':True,'routine_hash_matches_measured_run':True,'result_exact_three_keys':True,'response_word_count':len(Path('response.md').read_text().split()),'notebook_execution':'Sequential plain Python execution, saved stream outputs; nbformat validation passed; saved plain text outputs inspected; no kernel or chart rendering required','required_files_present':all(Path(x).is_file() for x in ['restocking.csv','response.md','result.json','task_refinement.json','evaluation_plan.json','restock_routine.py','routine_usage.md','routine_measurements.json'])},indent=2))
    print(json.dumps(extra,indent=2));print(Path('final_checks.json').read_text())

if __name__=='__main__':main()
