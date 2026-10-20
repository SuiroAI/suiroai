"""Archive bounded, reviewable Data workflow evidence without raw sales rows.

Copy exact prompts, trace receipts, producer code, plans and delivered outputs
from authorized development replays. Retain hashes and locations for all other
outputs/native logs instead of duplicating raw transaction previews, notebooks
or tool streams. This is artifact preservation, not numerical verification.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


OUTPUTS = {'analysis.py', 'analyze.py', 'task_refinement.json', 'evaluation_plan.json', 'evaluation_plan.md',
    'response.md', 'restocking.csv', 'result.json', 'selection.json',
    'model_evaluation.csv', 'model_scores.csv', 'horizon_scores.csv',
    'comparison_results.csv', 'origin_scores.csv', 'origin_results.csv',
    'coverage_results.csv', 'run_summary.json', 'measured_results.json',
    'audit_notes.md', 'validate_outputs.py', 'validation.json', 'validation_results.json',
    'selection_evidence.json', 'ordering_summary.json', 'runtime.json',
    'coverage_horizon_diagnostic.csv', 'origin_mae.csv', 'source_treatment.json'}


def preserve(source, target):
    """Copy exact bytes and return their identity, never run producer code."""
    data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {'source': str(source), 'retained': str(target), 'bytes': len(data),
        'sha256': sha256(data).hexdigest()}


def archive(output, native, trace, destination):
    records = []
    for directory, category in [(output, 'output'), (native, 'native'), (trace, 'trace')]:
        if directory is None:
            continue
        for path in sorted(directory.glob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            data = path.read_bytes()
            item = {'source': str(path), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}
            if ((category == 'output' and (path.name in OUTPUTS
                    or (path.name.startswith('presented-html-') and path.suffix == '.html')))
                    or (category == 'trace' and path.name in {'outbound-prompt.txt', 'call-trace.json'})):
                item = preserve(path, destination / category / path.name)
            records.append(item)
    run = native / 'native-run.json'
    if run.exists():
        record = json.loads(run.read_text())
        disposition = {k: record.get(k) for k in ['outcome', 'error_code', 'message', 'thread_id', 'turn_id', 'terminal_status']}
        (destination / 'outcome.json').write_text(json.dumps(disposition, indent=2) + '\n')
    (destination / 'artifact-index.json').write_text(json.dumps(records, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['paired', 'exact', 'service'], required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    if args.kind == 'paired':
        preserve(args.source / 'frozen-experiment.json', args.destination / 'frozen-experiment.json')
        for arm in ['historical', 'structured']:
            root = args.source / arm
            (args.destination / arm).mkdir(exist_ok=True)
            preserve(root / 'prompt.txt', args.destination / arm / 'prompt.txt')
            archive(root / 'output', root / 'native', None, args.destination / arm)
    elif args.kind == 'exact':
        preserve(args.source / 'frozen-replay.json', args.destination / 'frozen-replay.json')
        for call in json.loads((args.source / 'frozen-replay.json').read_text())['calls']:
            dest = args.destination / call['arm']
            dest.mkdir(exist_ok=True)
            archive(Path(call['output']), Path(call['native']),
                Path(call['trace']['receipt_path']).parent, dest)
    else:
        record = next(args.source.glob('*/engineering-workflow-replay.json'))
        preserve(record, args.destination / record.name)
        for attempt in record.parent.glob('runs/investigation-*'):
            archive(attempt / 'output', attempt / 'native', attempt / 'native-trace', args.destination)


if __name__ == '__main__':
    main()
