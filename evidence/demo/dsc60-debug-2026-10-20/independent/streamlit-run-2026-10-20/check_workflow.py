"""Review real Streamlit dispatch/approval metadata without analytical execution.

Read only immutable record metadata, exposed prompts, source hashes and tool
chronology. Never parse original sales values or execute generated analysis.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from pathlib import Path
from hashlib import sha256
import json
from suiroai.integration.artifacts import ArtifactStore
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
SESSION=ROOT/'artifacts/demo/fb7ddff7fa934efb9fd02c7752e3f04d'
EXPECT=json.loads((ROOT/'evidence/demo/dsc60-debug-2026-10-20/trace/comparison-contract.json').read_text())
store=ArtifactStore(SESSION/'store');records={}
for p in (SESSION/'store/refs').glob('*.json'):
 registry=json.loads(p.read_text())
 if registry['encoding']=='canonical_json':
  r=store.read_record(registry['ref']);records[r['kind']]=r
proposal=records.get('task_proposal');approval=records.get('task_approval');submission=records.get('submission')
# Source objects in the immutable store are deliberately not opened.
approved_context=None
if proposal:
 assumptions=[a for a in proposal['assumptions'] if a['assumption_id']=='structured_task_context']
 approved_context=json.loads(assumptions[0]['statement'])
entries=[]
for p in sorted(SESSION.rglob('native-trace/call-trace.json')):
 r=json.loads(p.read_text());native=Path(r['native_evidence_dir']);prompt=Path(r['prompt_path']).read_text();release=native.parent/'released'
 sent=[];plan_events=[];program_runs=[];source_updates=[];plan_commands=[]
 for line in (native/'native-rpc.jsonl').open():
  e=json.loads(line);m=e.get('message',{});item=m.get('params',{}).get('item',{})
  if e.get('direction')=='sent' and m.get('method')=='turn/start':
   sent.append({'text_matches_trace':all(x['text']==prompt for x in m['params']['input'] if x['type']=='text'),'reasoning_effort':m['params'].get('effort'),'attachments':[x for x in m['params']['input'] if x['type']!='text']})
  if m.get('method')=='item/completed' and item.get('type')=='fileChange':
   for ch in item.get('changes',[]):
    if ch['path'].endswith('evaluation_plan.json'):plan_events.append(e['monotonic'])
    if ch.get('kind',{}).get('type')=='update':source_updates.append({'monotonic':e['monotonic'],'file':Path(ch['path']).name})
  if m.get('method')=='item/completed' and item.get('type')=='commandExecution' and 'python make_plan.py' in item.get('command','') and item.get('exitCode')==0:
   plan_commands.append(e['monotonic'])
  if m.get('method')=='item/started' and item.get('type')=='commandExecution':
   cmd=item['command']
   if any(s in cmd for s in ['python analysis.py','python analyze.py','python3 analysis.py','python3 analyze.py']):program_runs.append(e['monotonic'])
 row={'stage':r['stage'],'dispatch_status':r['dispatch_status'],'prompt_sha256':r['prompt_sha256'],'saved_prompt_hash_matches':sha256(prompt.encode()).hexdigest()==r['prompt_sha256'],'actual_sent':sent,'native_execution':r.get('native_execution'),'observed_configuration':r.get('observed_configuration'),'released_files':[{'relative_path':f['relative_path'],'source_sha256':f.get('source_sha256',f.get('approved_source_ref',{}).get('sha256')),'released_sha256':f['released_byte_sha256'],'actual_hash_matches':sha256((release/f['relative_path']).read_bytes()).hexdigest()==f['released_byte_sha256']} for f in r['released_files']],'plan_filechange_completion':plan_events,'plan_writer_success_completion':plan_commands,'analysis_program_starts':program_runs,'source_update_events':source_updates}
 if r['stage']=='investigation':
  brief=json.loads(prompt.split('Structured internal task (customer_context remains untrusted data):\n',1)[1].split('\nReleased inputs',1)[0]);row['transmitted_context_equals_approved_context']=brief['customer_context']==approved_context;row['transmitted_contract_definition_equals_predeclared']=brief['comparison_contract']['definition']==EXPECT
  out=native.parent/'output';plan=out/'evaluation_plan.json'
  if plan.exists():
   declared=json.loads(plan.read_text());row['plan_sha256']=sha256(plan.read_bytes()).hexdigest();row['plan_contract_equals_transmitted']=declared.get('comparison_contract')==brief['comparison_contract'];row['declared_digest_matches']=declared.get('comparison_contract_sha256')==brief['comparison_contract']['sha256'];row['plan_precedes_analysis']=(bool((plan_events or plan_commands) and max(plan_events+plan_commands)<min(program_runs)) if program_runs else None)
  row['output_files']=[f.name for f in sorted(out.iterdir()) if f.is_file()]
 if r['stage']=='current_process' and (native.parent/'output/result.json').exists():
  detector=json.loads((native.parent/'output/result.json').read_text());row['detector_status']=detector['status']
  if approved_context:
   process=approved_context['current_process'];row['approved_context_matches_detector_result']=(process['source']=='detector_interpretation' and process['status']==detector['status'] and process['text']==detector['summary'] and process['evidence']==detector['evidence'])
 entries.append(row)
result={'scope':'Real UI workflow metadata/claims review; no new analytical computation, original raw-sales parse or generated producer execution. Hidden provider context remains unknown. UI action observations owned by root.','session':SESSION.name,'record_kinds':sorted(records),'approved_context_present':approved_context is not None,'approved_original_question_matches_submission':bool(approved_context and submission and approved_context['original_question']==submission['original_request']),'approval_proposal_binding_equal':bool(approval and proposal and approval['binding']==proposal['binding']),'approval_decision':approval.get('decision') if approval else None,'calls':entries}
(HERE/'workflow-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'record_kinds':result['record_kinds'],'binding_match':result['approval_proposal_binding_equal'],'calls':[{k:c.get(k) for k in ['stage','dispatch_status','transmitted_context_equals_approved_context','transmitted_contract_definition_equals_predeclared','plan_contract_equals_transmitted','plan_precedes_analysis']} for c in entries]},indent=2))
