"""Inspect exact replay call identities and workflow chronology, without analysis.

Only prompt/file hashes, native request/config metadata, tool action order and
output-file inventory are retained. Does not run generated scripts or evaluate
sales or forecast outcomes. Hidden provider context remains unknown.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from pathlib import Path
from hashlib import sha256
import json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
REPLAY=ROOT/'artifacts/dsc60-exact-replay-2026-10-20'
manifest=json.loads((REPLAY/'frozen-replay.json').read_text());rows=[]
for call in manifest['calls']:
 receipt=json.loads(Path(call['trace']['receipt_path']).read_text());prompt=Path(receipt['prompt_path']).read_bytes()
 sent=[];plans=[];executions=[];changes=[]
 for line in (Path(call['native'])/'native-rpc.jsonl').open():
  event=json.loads(line);msg=event.get('message',{});params=msg.get('params',{});item=params.get('item',{})
  if event.get('direction')=='sent' and msg.get('method')=='turn/start':
   text=next(p['text'] for p in params['input'] if p.get('type')=='text')
   sent.append({'effort':params.get('effort'),'text_sha256':sha256(text.encode()).hexdigest(),'matches_saved_prompt':text.encode()==prompt,'nontext_attachments':[p for p in params['input'] if p.get('type')!='text']})
  if msg.get('method')=='item/completed' and item.get('type')=='fileChange':
   paths=[c['path'] for c in item.get('changes',[])];changes.append({'monotonic':event['monotonic'],'paths':paths})
   if any('evaluation_plan.' in p for p in paths):plans.append(event['monotonic'])
  if msg.get('method')=='item/started' and item.get('type')=='commandExecution':
   # Retain action order, not command output/source samples.
   executions.append({'monotonic':event['monotonic'],'command_sha256':sha256(item['command'].encode()).hexdigest(),'analysis_program_execution':any(s in item['command'] for s in ['python analyze.py','python analysis.py','python3 analyze.py','python3 analysis.py']), 'cwd':item.get('cwd')})
 released={p['relative_path']:sha256((Path(call['released'])/p['relative_path']).read_bytes()).hexdigest()==p['released_byte_sha256'] for p in receipt['released_files']}
 row={'arm':call['arm'],'dispatch_status':receipt['dispatch_status'],'prompt_sha256':sha256(prompt).hexdigest(),'prompt_matches_frozen_intent':sha256(prompt).hexdigest()==call['trace']['prompt_sha256'],'original_exposed_prompt_exact':sha256(prompt).hexdigest()==call['original_prompt_sha256'] if call['byte_exact_original_prompt'] else None,'actual_sent_calls':sent,'released_hash_matches':released,'native_execution':receipt.get('native_execution'),'observed_configuration':receipt.get('observed_configuration'),'plan_completion_monotonic':plans,'file_change_events':changes,'command_events':executions,'output_files':[p.name for p in sorted(Path(call['output']).iterdir()) if p.is_file()]}
 rows.append(row)
(HERE/'exact_replay_trace_check.json').write_text(json.dumps({'scope':'Exposed outbound bytes, tool events and metadata only; no hidden/system-context equality, deterministic causality or analytical performance acceptance claimed. Analyses reuse retained detector context, not the parallel detector replay result.','calls':rows},indent=2)+'\n')
for r in rows:print(r['arm'],r['dispatch_status'],'actual_sent_match',all(c['matches_saved_prompt'] for c in r['actual_sent_calls']),'original_exact',r['original_exposed_prompt_exact'],'plans',len(r['plan_completion_monotonic']),'outputs',r['output_files'])
