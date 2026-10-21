"""Measure the actual CLI subprocess including startup, preparation and CSV writing."""
import hashlib, json, platform, resource, subprocess, sys, time
from pathlib import Path
import numpy, pandas

command=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv','--planning-date','2025-11-30','--output-path','restocking.csv']
before=resource.getrusage(resource.RUSAGE_CHILDREN)
t=time.perf_counter(); result=subprocess.run(command,check=True,capture_output=True,text=True); elapsed=time.perf_counter()-t
after=resource.getrusage(resource.RUSAGE_CHILDREN)
expected=pandas.read_csv('restocking_expected.csv').fillna(''); actual=pandas.read_csv('restocking.csv').fillna('')
pandas.testing.assert_frame_equal(expected,actual)
hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['restock_routine.py','../released/input-1.csv','../released/input-2.csv','../released/input-3.csv','../released/input-4.csv','restocking.csv']}
m={'command':command,'planning_date':'2025-11-30','dependencies':{'python':platform.python_version(),'numpy':numpy.__version__,'pandas':pandas.__version__},'platform':platform.platform(),'machine':platform.machine(),'wall_seconds_including_startup_preparation_and_output':elapsed,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'peak_process_rss_bytes':after.ru_maxrss if sys.platform=='darwin' else after.ru_maxrss*1024,'measurement_limits':'Fresh measurement parent, one child. OS process peak includes interpreter, imports, input data and retained arrays through output. macOS RSS bytes/Linux KiB normalized. No hardware cap or 8GB-host assumption. Single observed warm/cold-cache-unspecified run, not a runtime guarantee.','routine_output':json.loads(result.stdout),'output_agreement':{'all_rows_headers_values_equal':True,'compared_to':'restocking_expected.csv from analysis selected calculation','independent_policy_checks':'see validation.json'},'sha256':hashes,'routine_numeric_cost_assessment':{'paid_model_api_calls':0,'paid_model_api_cost':0,'routine_uses_llm':False,'AI_assisted_build_cost':'not measured; distinct from local routine'},'eight_gb_assessment':'Measured process well below 1GB, leaving several GB for OS on a CPU-only 8GB computer at current 17,406 input rows and 336 keys. NumPy/pandas only; Croston state linear in keys, calendar preparation linear in dates times keys. Do not extrapolate unlimited growth. No sklearn/scipy required for selected routine; those are comparison-only dependencies.'}
Path('routine_measurements.json').write_text(json.dumps(m,indent=2)); print(json.dumps(m,indent=2))
