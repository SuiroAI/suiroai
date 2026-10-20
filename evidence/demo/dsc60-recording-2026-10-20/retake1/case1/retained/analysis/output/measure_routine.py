"""Invoke actual CLI in a fresh process; observe process-tree RSS using psutil."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import subprocess,sys,time,json,hashlib,platform,resource
from pathlib import Path
import numpy,pandas

def main():
    source=Path(sys.argv[1]).resolve()
    cmd=[sys.executable,'restock_routine.py','--sales-path',str(source/'input-4.csv'),'--stock-path',str(source/'input-3.csv'),'--deliveries-path',str(source/'input-2.csv'),'--policy-path',str(source/'input-1.csv'),'--planning-date','2025-11-30','--output-path','restocking.csv']
    start=time.perf_counter(); proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stdout,stderr=proc.communicate(); elapsed=time.perf_counter()-start
    if proc.returncode:raise RuntimeError(stderr)
    stats=json.loads(stdout)
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    out={'command_argv':cmd,'planning_date':'2025-11-30','returncode':proc.returncode,'local_calculation_wall_seconds':elapsed,'child_high_water_rss_bytes':int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*(1 if sys.platform=='darwin' else 1024)),'memory_measurement_limits':'OS process high-water RSS includes Python, imports, data preparation and retained arrays/models, but does not isolate fit and inference peaks or attribute swap. Routine spawns no child processes. Single warm-filesystem local run, not an 8 GB hardware benchmark. An initial attempted psutil process-tree observer was denied by the sandbox and was replaced by OS self/child resource counters.','routine_details':stats,'dependency_versions':{'python':platform.python_version(),'numpy':numpy.__version__,'pandas':pandas.__version__},'input_sha256':{str(p):digest(p) for p in sorted(source.glob('*.csv'))},'routine_sha256':digest('restock_routine.py'),'output_sha256':digest('restocking.csv'),'cpu_only':True,'paid_model_api_calls':0,'thread_settings':{x:os.environ[x] for x in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']},'cost_scope':'Measured weekly local calculation only, separate from AI-assisted analysis/build. No usage/pricing supplied for AI analysis cost; no electricity/hosting rate supplied.'}
    Path('routine_measurements.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__': main()
