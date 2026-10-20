"""Check recording evidence without blocking ordinary application results.

Reject missing or altered freezes, unsupported provenance, development-only
bundles and incompatible final origin claims. These fixtures test a bounded
evidence checklist, not a model-performance or parent-acceptance validator.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import hashlib
import json

from suiroai.demo.readiness import recording_readiness


def frozen(tmp_path):
    names = ['protocol.json', 'frozen_rule.json', 'frozen_predictions.csv']
    for name in names:
        (tmp_path / name).write_text('frozen content')
    (tmp_path / 'frozen_predictions.csv').write_text('target_start,target_end\n2025-12-01,2025-12-07\n2025-12-08,2025-12-14\n2025-12-15,2025-12-21\n2025-12-22,2025-12-28\n')
    manifest = {'schema_version': 1, 'phase': 'final_holdout_freeze', 'gate_approved': True, 'files': {n: hashlib.sha256((tmp_path / n).read_bytes()).hexdigest() for n in names},
                'source_sha256': {'input.csv': 'source hash'}, 'code_sha256': 'code hash',
                'cutoff': '2025-11-30', 'holdout_start': '2025-12-01', 'holdout_end': '2025-12-28'}
    path = tmp_path / 'freeze_manifest.json'
    path.write_text(json.dumps(manifest))
    return {'freeze_manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'untouched_provenance': {'independently_reviewed': True, 'outcomes_unseen_before_freeze': True,
                                     'reviewer': 'independent reviewer', 'evidence_reference': 'external receipt'},
            'engineering_gate_approved': True, 'independent_origin_count': 4, 'evaluation_count': 1, 'evaluated_after_freeze': True,
            'primary_metric': 'seven_day_aggregate_mae', 'baseline_mae': 1.0, 'candidate_mae': .94,
            'origin_block_gain_95_percent_lower': .01}


def test_missing_evidence_never_blocks_app(tmp_path):
    result = recording_readiness(tmp_path)
    assert result['recording_ready'] is False
    assert result['ordinary_app_results_blocked'] is False


def test_development_freeze_is_not_holdout_evidence(tmp_path):
    frozen(tmp_path)
    assert 'missing_independent_holdout_receipt' in recording_readiness(tmp_path)['reasons']


def test_complete_reviewed_receipt_can_pass(tmp_path):
    receipt = frozen(tmp_path)
    assert recording_readiness(tmp_path, receipt)['recording_ready'] is True


def test_changed_prediction_fails_closed(tmp_path):
    receipt = frozen(tmp_path)
    (tmp_path / 'frozen_predictions.csv').write_text('changed')
    assert 'frozen_file_changed:frozen_predictions.csv' in recording_readiness(tmp_path, receipt)['reasons']


def test_secondary_or_repeated_holdout_cannot_pass(tmp_path):
    receipt = frozen(tmp_path)
    receipt.update(primary_metric='rmse', evaluation_count=2)
    result = recording_readiness(tmp_path, receipt)
    assert result['recording_ready'] is False
    assert 'wrong_primary_metric' in result['reasons']
    assert 'holdout_not_one_shot_after_freeze' in result['reasons']


def test_small_or_nonrobust_gain_cannot_pass(tmp_path):
    receipt = frozen(tmp_path)
    receipt['candidate_mae'] = .96
    assert not recording_readiness(tmp_path, receipt)['recording_ready']
    receipt.update(candidate_mae=.90, origin_block_gain_95_percent_lower=-.01)
    assert not recording_readiness(tmp_path, receipt)['recording_ready']


def test_self_asserted_provenance_does_not_pass(tmp_path):
    receipt = frozen(tmp_path)
    receipt['untouched_provenance'] = {'outcomes_unseen_before_freeze': True}
    assert not recording_readiness(tmp_path, receipt)['recording_ready']


def test_one_origin_cannot_establish_temporal_robustness(tmp_path):
    receipt = frozen(tmp_path)
    receipt['independent_origin_count'] = 1
    assert 'insufficient_final_origins' in recording_readiness(tmp_path, receipt)['reasons']


def test_development_manifest_cannot_be_promoted_by_receipt(tmp_path):
    receipt = frozen(tmp_path)
    path = tmp_path / 'freeze_manifest.json'
    manifest = json.loads(path.read_text())
    manifest.update(phase='development_only', gate_approved=False)
    path.write_text(json.dumps(manifest))
    receipt['freeze_manifest_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert 'development_bundle_not_final_acceptance' in recording_readiness(tmp_path, receipt)['reasons']
