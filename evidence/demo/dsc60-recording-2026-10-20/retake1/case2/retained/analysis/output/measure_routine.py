"""Measure the actual CLI invocation, including interpreter startup and file preparation."""
import subprocess, time, re, json, hashlib, sys, platform, os
from pathlib import Path
import pandas as pd
import numpy as np

command=[sys.executable,'restock_routine.py','--sales-path','../released/input-4.csv','--stock-path','../released/input-3.csv','--deliveries-path','../released/input-2.csv','--policy-path','../released/input-1.csv','--planning-date','2025-11-30','--output-path','restocking.csv']
start=time.perf_counter()
process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
_,status,usage=os.wait4(process.pid,0)
process.returncode=os.waitstatus_to_exitcode(status)
stdout=process.stdout.read(); stderr=process.stderr.read()
elapsed=time.perf_counter()-start
Path('routine_process_measurement.txt').write_text(stdout+stderr)
if process.returncode: raise RuntimeError(stderr)
rss=usage.ru_maxrss if sys.platform=='darwin' else usage.ru_maxrss*1024
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
agreement=Path('restocking.csv').read_bytes()==Path('expected_restocking.csv').read_bytes()
assert agreement
obj=dict(command=command,working_directory_requirement='Run from directory containing script; input paths may be any supplied current files',planning_date='2025-11-30',selected_method='pooled90',dependencies=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__),environment=platform.platform(),local_calculation_wall_seconds=elapsed,maximum_resident_set_bytes=rss,measurement_method='os.wait4 child process maximum RSS; wall clock includes interpreter startup, reads, validation, sales preparation, aggregation, inference, ordering, write and process shutdown',instrumentation_retry='An initial /usr/bin/time -l attempt produced the correct CSV but resource reporting failed on sandbox-denied sysctl. Repeated same command with wait4; no forecast or source changes.',output_agreement=dict(exact_bytes=agreement,comparison='Expected output constructed in comparison.py using frozen selected method'),hashes={p:sha(p) for p in ['restock_routine.py','restocking.csv','../released/input-1.csv','../released/input-2.csv','../released/input-3.csv','../released/input-4.csv']},routine_paid_model_calls=0,routine_network_calls=0,cost='No paid model service required; local computer, electricity or hosting costs remain. No dollar estimate without actual rates. AI-assisted analysis/build costs separate; usage and applicable pricing unavailable.',memory_limits='Single-process measured peak resident memory, not hardware RAM measurement or whole-system memory; includes fitting/aggregation and inference. Data and workload as supplied; future growth may increase usage.',fit_inference='Selected pooling method has no iterative learned-model fit. Trailing-90-day local/product/store sufficient statistics form the fitted rates, followed by 336 shrinkage predictions. Entire preparation, rate construction and inference bounded by observed process peak and total time; internal phase timings recorded in computational_profile.json.')
Path('routine_measurements.json').write_text(json.dumps(obj,indent=2))
Path('result.json').write_text(json.dumps(dict(disposition='analysis',output_file='restocking.csv',output_sha256=sha('restocking.csv')),indent=2))
print(stdout);print('seconds',elapsed,'RSS bytes',rss,'agreement',agreement)
