"""Exercise the actual approved demo service with a fixed comparison contract.

Use the original four retail uploads and retained detector finding to isolate
analysis handoff behavior after exact detector replay has been checked. Review
and approval are performed by the authorized engineering caller, not claimed
as a new user-operated browser demonstration. All preparation/modeling/output
work is delegated to the existing genuine Codex/Data backend; this script does
not calculate forecasts, choose models, score results or open file actions.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from suiroai.demo.service import DemoSession, UploadedInput


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--contract', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    historical = json.loads((repo / 'evidence/demo/dsc60-debug-2026-10-20/trace/index.json').read_text())
    contract_bytes = args.contract.read_bytes()
    contract = json.loads(contract_bytes)
    uploads = [UploadedInput(name=name, data=(args.source / name).read_bytes()) for name in
        ['ordering_policy.csv', 'inbound_deliveries.csv', 'inventory_position.csv',
         'Sales_transactions_2022_2025.csv']]
    session = DemoSession(artifact_root=args.root.resolve(), comparison_contract=contract,
        context_detector=lambda *_: historical['detected_context'])
    review = session.review(historical['original_question'], uploads)
    if review['status'] != 'awaiting_approval':
        raise ValueError('Actual service did not reach review: ' + repr(review))
    record = {'format': 'dsc60-approved-service-replay-v1',
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'approval_actor': 'authorized engineering caller; no browser/customer click claimed',
        'detector_context': 'retained finding, isolated after separate exact detector replay',
        'contract_file_sha256': sha256(contract_bytes).hexdigest(),
        'code_sha256': {name: sha256((repo / name).read_bytes()).hexdigest() for name in
            ['src/suiroai/demo/task.py', 'src/suiroai/demo/service.py',
             'src/suiroai/demo/investigation.py', 'src/suiroai/demo/call_trace.py',
             'scripts/dsc60_workflow_replay.py']},
        'source_files': [{'name': item.name, 'sha256': sha256(item.data).hexdigest()} for item in uploads],
        'artifact_root': str(session._root), 'review': review,
        'limits': 'Development only; no untouched outcome evaluation, recording, automatic HTML/CSV action or performance acceptance.'}
    record_path = session._root / 'engineering-workflow-replay.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    print('Approved service/Data execution: ' + str(session._root), flush=True)
    session.approve_and_run(review['proposal_digest'])
    record['completed_at'] = datetime.now(timezone.utc).isoformat()
    record['result'] = session.view
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'status': session.view['status'], 'receipt': str(record_path)}), flush=True)


if __name__ == '__main__':
    main()
