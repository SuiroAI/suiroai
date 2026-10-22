"""One actual CLI invocation, measured end to end including imports/preparation/output."""
import hashlib, importlib.metadata, json, platform, resource, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
command=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv','--planning-date','2025-11-30','--output-path','restocking.csv']
start=time.perf_counter()
result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=True)
elapsed=time.perf_counter()-start
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
agreement=(ROOT/'restocking.csv').read_bytes()==(ROOT/'expected_output.csv').read_bytes()
assert agreement
measure={'command':command,'cwd_requirement':'Directory containing restock_routine.py; relative sources shown are this released demo layout','planning_date':'2025-11-30','selected_method':'sba','wall_seconds':elapsed,'cpu_user_seconds':usage.ru_utime,'cpu_system_seconds':usage.ru_stime,'peak_rss_mib':usage.ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),'measurement_scope':'One actual fresh CLI child process; includes Python/dependency imports, CSV reading, validation, preparation, fitting, inference, all order/timing calculations and output write. Not AI-assisted build duration. OS peak RSS includes resident native allocations and retained arrays; does not measure virtual memory, disk cache or other applications. Host is not assumed to have 8 GB.','dependency_versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas']},'python':platform.python_version(),'platform':platform.platform(),'source_sha256':{f'input-{i}.csv':sha(ROOT.parent/'released'/f'input-{i}.csv') for i in range(1,5)},'program_sha256':sha(ROOT/'restock_routine.py'),'output_sha256':sha(ROOT/'restocking.csv'),'output_agreement':{'byte_equal_to_prepared_selected_list':agreement,'reference_sha256':sha(ROOT/'expected_output.csv'),'reference_note':'Same selected implementation; separate independent policy arithmetic check in validate_outputs.py'},'stdout':result.stdout.strip(),'routine_external_model_or_api_calls':0,'routine_paid_calls':0,'routine_numeric_cost_assessment':'No model/API dependency or per-run API charge; no measured hardware/energy cost. AI-assisted analysis/build usage and cost not measured here.'}
(ROOT/'routine_measurements.json').write_text(json.dumps(measure,indent=2))
(ROOT/'result.json').write_text(json.dumps({'disposition':'analysis','output_file':'restocking.csv','output_sha256':measure['output_sha256']},indent=2))
print(json.dumps(measure,indent=2))
