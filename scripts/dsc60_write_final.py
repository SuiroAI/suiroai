"""Invoke a genuine final business-writing turn from completed measured findings.

Snapshot final Data findings and allowlisted aggregate context into an immutable
store, retaining the original 336-row/880-unit restocking CSV by its prior hash.
Use the existing writer API and native trace without fitting, scoring or
regenerating a model/table. Authorization records the current explicit user
request as an engineering action, never a forged browser/customer approval.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from suiroai.demo.business_response import run_business_response
from suiroai.integration.artifacts import ArtifactStore, read_stage_file


REPO = Path(__file__).resolve().parents[1]
RETAINED = REPO / 'evidence/demo/dsc60-debug-2026-10-20/streamlit-discovery-2026-10-20/analysis/output'
CSV_SHA256 = 'c2a20f1446677825b738129f5c350547b32ca7ac21fce722e05c885644ebcb74'
OPTIONAL_CONTEXT = ('comparison_summary.csv', 'evaluation_plan.json', 'evaluation_plan_v2.json', 'routine_workload.json', 'task_refinement.json')


def _read(path, limit):
    path = Path(path).absolute()
    return read_stage_file(path.parent, path.name, max_bytes=limit)


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o400)


def write_final(analysis_output, root, *, authorization_context, restocking_csv=None,
                analysis_native_receipt=None, routine_workload=None):
    """Run one explicitly authorized writing stage; root must be a new directory.

    Final findings and native completion must exist before any run is created.
    A REVOKED file in root revokes the engineering request at subsequent writer
    consent checks. The function never creates a customer task_approval record.
    """
    if not isinstance(authorization_context, str) or not authorization_context.strip():
        raise ValueError('Record the existing explicit user authorization context')
    analysis_output = Path(analysis_output).absolute()
    root = Path(root).absolute()
    csv_path = Path(restocking_csv or RETAINED / 'restocking.csv').absolute()
    native_path = Path(analysis_native_receipt or analysis_output.parent / 'native/native-run.json').absolute()
    response = read_stage_file(analysis_output, 'response.md', max_bytes=96 * 1024)
    measured = read_stage_file(analysis_output, 'measured_results.json', max_bytes=256 * 1024)
    if not response.strip() or not isinstance(json.loads(measured), dict):
        raise ValueError('Completed final response and measured-results object are required')
    native_bytes = _read(native_path, 64 * 1024 * 1024)
    native = json.loads(native_bytes)
    if native.get('outcome') != 'completed' or not native.get('thread_id') or not native.get('turn_id'):
        raise ValueError('Final analytical native receipt must report completed thread/turn identities')
    csv_bytes = _read(csv_path, 16 * 1024 * 1024)
    if sha256(csv_bytes).hexdigest() != CSV_SHA256:
        raise ValueError('Restocking CSV differs from the immutable original 880-unit deliverable')
    inputs = {'response.md': response, 'measured_results.json': measured, 'restocking.csv': csv_bytes}
    for name in OPTIONAL_CONTEXT:
        candidate = analysis_output / name
        if candidate.exists() or candidate.is_symlink():
            raw = read_stage_file(analysis_output, name, max_bytes=256 * 1024)
            if name.endswith('.json'):
                json.loads(raw)
            inputs[name] = raw
    if 'routine_workload.json' not in inputs:
        workload_path = Path(routine_workload or RETAINED / 'routine_workload.json')
        workload = _read(workload_path, 256 * 1024)
        json.loads(workload)
        inputs['routine_workload.json'] = workload
    if 'task_refinement.json' not in inputs:
        # Exact original Data-authored model rationale, not a new controller analysis.
        refinement = _read(RETAINED / 'task_refinement.json', 256 * 1024)
        json.loads(refinement)
        inputs['task_refinement.json'] = refinement
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    snapshot = root / 'source-output'
    snapshot.mkdir(mode=0o700)
    store = ArtifactStore(root / 'store')
    refs = {}
    for name, raw in inputs.items():
        refs[name] = store.put_bytes('final-writing-input-' + name, 1, 'derived', raw)
        _write_new(snapshot / name, raw)
    authorization = {'format': 'dsc60-engineering-writing-authorization-v1',
        'actor': 'engineering-controller', 'basis': 'existing-explicit-user-request',
        'context': authorization_context.strip(), 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'One genuine business-writing turn from completed final findings; original restocking CSV unchanged.',
        'customer_ui_approval_claimed': False, 'inputs': refs,
        'analysis_native_receipt': {'path': str(native_path), 'sha256': sha256(native_bytes).hexdigest(),
            'thread_id': native['thread_id'], 'turn_id': native['turn_id']}}
    auth_bytes = _json(authorization)
    authorization_path = root / 'engineering-authorization.json'
    _write_new(authorization_path, auth_bytes)

    def currently_authorized():
        return (not (root / 'REVOKED').exists()
            and _read(authorization_path, 256 * 1024) == auth_bytes)

    analysis = {'native_outcome': native['outcome'], 'output_error': None,
        'unverified_investigation_text': response.decode('utf-8'),
        'native_original_investigation_ref': refs['response.md'],
        'unverified_investigation_ref': refs['response.md'],
        'unverified_report_ref': refs['restocking.csv'],
        'native_original_report_path': str(snapshot / 'restocking.csv'),
        'thread_id': native['thread_id'], 'turn_id': native['turn_id']}
    writing = run_business_response(store, analysis, root / 'runs', currently_authorized)
    if not currently_authorized():
        raise ValueError('Engineering writing authorization was revoked before publication')
    if _read(csv_path, 16 * 1024 * 1024) != csv_bytes:
        raise ValueError('Original CSV changed during business writing')
    result_bytes = store.read_bytes(writing['response_ref'])
    if result_bytes.decode('utf-8') != writing['text']:
        raise ValueError('Business response differs from its immutable receipt')
    _write_new(root / 'business_response.md', result_bytes)
    receipt = {**writing, 'authorization': authorization, 'input_refs': refs,
        'original_csv_sha256': CSV_SHA256, 'analytical_or_parent_acceptance_granted': False}
    _write_new(root / 'business-writing-result.json', _json(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-output', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--authorization-context', required=True)
    parser.add_argument('--restocking-csv', type=Path)
    parser.add_argument('--analysis-native-receipt', type=Path)
    parser.add_argument('--routine-workload', type=Path)
    args = parser.parse_args()
    result = write_final(args.analysis_output, args.root, authorization_context=args.authorization_context,
        restocking_csv=args.restocking_csv, analysis_native_receipt=args.analysis_native_receipt,
        routine_workload=args.routine_workload)
    print(json.dumps({'status': result['status'], 'thread_id': result['thread_id'],
        'turn_id': result['turn_id'], 'output': str(args.root / 'business_response.md'),
        'receipt': str(args.root / 'business-writing-result.json')}, indent=2))


if __name__ == '__main__':
    main()
