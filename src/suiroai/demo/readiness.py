"""Optional recording evidence check for DSC-60; never gates normal app results.

Purpose: verify local frozen evidence before a superiority-claim recording.
Tracking: https://linear.app/gr3enarr0w/issue/DSC-60
This bounded receipt checklist checks supplied evidence, not the truth of external
provenance assertions. It is not the DSC-9 final acceptance validator.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def recording_readiness(directory: Path, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fail closed on absent/tampered freeze, provenance or one-shot holdout result.

    `evidence` is a separately supplied post-freeze receipt, never inferred from
    development scores. The caller owns independent review of its attestations.
    It does not recompute scores, validate prediction populations or numeric values,
    parse protocol/rule semantics, authenticate chronology/approval, or rehash the
    external source/code files. No app results are modified; no outcomes are opened.
    """
    reasons: list[str] = []
    try:
        manifest_path = directory / 'freeze_manifest.json'
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        if manifest.get('phase') != 'final_holdout_freeze' or manifest.get('gate_approved') is not True:
            reasons.append('development_bundle_not_final_acceptance')
        if manifest.get('schema_version') != 1:
            reasons.append('unsupported_freeze_schema')
        required = {'protocol.json', 'frozen_rule.json', 'frozen_predictions.csv'}
        files = manifest.get('files', {})
        if not isinstance(files, dict) or set(files) != required:
            reasons.append('incomplete_frozen_files')
        else:
            for name in sorted(required):
                if hashlib.sha256((directory / name).read_bytes()).hexdigest() != files[name]:
                    reasons.append(f'frozen_file_changed:{name}')
        if not manifest.get('source_sha256') or not manifest.get('code_sha256'):
            reasons.append('missing_source_or_code_provenance')
        start, end = date.fromisoformat(manifest['holdout_start']), date.fromisoformat(manifest['holdout_end'])
        if not (manifest.get('cutoff') == '2025-11-30' and date(2025, 12, 1) <= start <= end <= date(2025, 12, 31)):
            reasons.append('unexpected_holdout_boundary')
        with (directory / 'frozen_predictions.csv').open(newline='') as handle:
            targets = {(r['target_start'], r['target_end']) for r in csv.DictReader(handle)}
        origins = sorted(date.fromisoformat(a) for a, b in targets)
        if len(origins) < 2 or any(b - a < timedelta(days=7) for a, b in zip(origins, origins[1:])):
            reasons.append('insufficient_frozen_independent_origins')
        if any(date.fromisoformat(b) != date.fromisoformat(a) + timedelta(days=6) or not (start <= date.fromisoformat(a) <= date.fromisoformat(b) <= end) for a, b in targets):
            reasons.append('invalid_frozen_weekly_targets')
        if evidence is None:
            reasons.append('missing_independent_holdout_receipt')
        else:
            frozen_digest = hashlib.sha256(manifest_bytes).hexdigest()
            if evidence.get('freeze_manifest_sha256') != frozen_digest:
                reasons.append('receipt_freeze_mismatch')
            provenance = evidence.get('untouched_provenance', {})
            if not (isinstance(provenance, dict) and provenance.get('independently_reviewed') is True
                    and provenance.get('outcomes_unseen_before_freeze') is True
                    and provenance.get('reviewer') and provenance.get('evidence_reference')):
                reasons.append('untouched_holdout_not_independently_evidenced')
            if evidence.get('engineering_gate_approved') is not True:
                reasons.append('engineering_gate_not_approved')
            if type(evidence.get('independent_origin_count')) is not int or evidence['independent_origin_count'] < 2 or evidence['independent_origin_count'] != len(origins):
                reasons.append('insufficient_final_origins')
            if type(evidence.get('evaluation_count')) is not int or evidence['evaluation_count'] != 1 or evidence.get('evaluated_after_freeze') is not True:
                reasons.append('holdout_not_one_shot_after_freeze')
            if evidence.get('primary_metric') != 'seven_day_aggregate_mae':
                reasons.append('wrong_primary_metric')
            baseline = evidence.get('baseline_mae')
            candidate = evidence.get('candidate_mae')
            lower = evidence.get('origin_block_gain_95_percent_lower')
            numeric = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            if not (numeric(baseline) and baseline > 0 and numeric(candidate) and candidate >= 0 and numeric(lower)):
                reasons.append('missing_valid_primary_result')
            elif 1 - candidate / baseline < .05 or lower <= 0:
                reasons.append('meaningful_robust_gain_not_demonstrated')
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        reasons.append('missing_or_invalid_freeze')
    return {'recording_ready': not reasons, 'scope': 'superiority_claim_recording_only',
            'ordinary_app_results_blocked': False, 'reasons': reasons,
            'criterion': 'Engineering proposal: >=5% relative seven-day MAE gain and positive origin-block 95% lower bound; no business ROI or service guarantee.'}
