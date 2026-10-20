"""Replay retained visible native inputs and compare the revised Data handoff.

The original detector and investigation prompt bytes are sent unchanged, with
the original immutable released paths. Fresh output/native directories preserve
all earlier evidence. The revised investigation changes task construction only;
it receives the same retained detected context and same file manifest, with no
common control appendix. Replays can reveal observed workflow differences, not
hidden model context or deterministic causality from a single stochastic trial.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import uuid

from suiroai.demo.call_trace import begin_call_trace, finish_call_trace
from suiroai.demo.investigation import investigation_prompt
from suiroai.demo.task import task_context
from suiroai.integration.native import NativeHost


def prepare(repo, root):
    """Freeze exact prompts, release identities and code identity before calls."""
    index = json.loads((repo / 'evidence/demo/dsc60-debug-2026-10-20/trace/index.json').read_text())
    root.mkdir(parents=True, exist_ok=False)
    calls = []
    for arm, original_call in [('detector-exact', index['calls'][0]),
                               ('investigation-exact', index['calls'][1]),
                               ('investigation-revised', index['calls'][1])]:
        original_run = repo / original_call['native_run']['path']
        parent = original_run.parent.parent
        released = parent / 'released'
        # Reusing the original released path permits byte-exact original prompt
        # replay without weakening native restrictions or overwriting old output.
        suffix = uuid.uuid4().hex
        output, native = parent / ('replay-output-' + suffix), parent / ('replay-native-' + suffix)
        output.mkdir(mode=0o700)
        native.mkdir(mode=0o700)
        arm_root = root / arm
        arm_root.mkdir()
        manifest = [{k: v for k, v in item.items() if k != 'historical_released_file'}
                    for item in original_call['released_files']]
        for item in manifest:
            data = (released / item['relative_path']).read_bytes()
            if sha256(data).hexdigest() != item['released_byte_sha256']:
                raise ValueError('Historical released input changed')
        prompt = (repo / original_call['prompt']['path']).read_text()
        if sha256(prompt.encode()).hexdigest() != original_call['prompt']['sha256']:
            raise ValueError('Historical prompt identity mismatch')
        if arm.endswith('revised'):
            prompt = investigation_prompt(index['original_question'], released, manifest,
                context=task_context(index['original_question'], detected=index['detected_context']))
        trace = begin_call_trace(native, stage=arm, prompt=prompt, manifest=manifest,
            trace_dir=arm_root / 'trace')
        calls.append({'arm': arm, 'output': str(output), 'native': str(native),
            'released': str(released), 'trace': trace,
            'original_prompt_sha256': original_call['prompt']['sha256'],
            'byte_exact_original_prompt': arm.endswith('exact')})
    frozen = {'format': 'dsc60-exact-visible-call-replay-v1',
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'calls': calls,
        'code_sha256': {name: sha256((repo / name).read_bytes()).hexdigest() for name in
            ['src/suiroai/demo/task.py', 'src/suiroai/demo/investigation.py',
             'src/suiroai/demo/call_trace.py', 'scripts/dsc60_trace_replay.py']},
        'limits': 'Exact outbound text/file bytes; fresh runtime/profile identities. Hidden/system context unknown. One stochastic replay per arm. No performance acceptance or December outcomes.'}
    (root / 'frozen-replay.json').write_text(json.dumps(frozen, indent=2) + '\n')
    return calls


def execute(call):
    """Dispatch the frozen text to the existing restricted Codex/Data host."""
    trace = call['trace']
    try:
        native = NativeHost().execute(cwd=Path(call['output']),
            prompt=Path(trace['prompt_path']).read_text(), evidence_dir=Path(call['native']),
            released_root=Path(call['released']), timeout_seconds=None)
    except BaseException as exc:
        finish_call_trace(trace, error=exc)
        raise
    result = finish_call_trace(trace, native=native)
    print(json.dumps({'arm': call['arm'], **result['native_execution']}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    calls = prepare(Path(__file__).resolve().parents[1], args.root.resolve())
    if not args.prepare_only:
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(execute, calls))


if __name__ == '__main__':
    main()
