"""Export inspectable synthetic calculations; never a customer acceptance run.

Run from project root: PYTHONPATH=src python3 tests/modeling/export_component_evidence.py

Requirement context for these component checks:
Retain inspectable synthetic baseline, comparison, and frozen-validation
calculations while distinguishing component evidence from real task execution.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
import json
from pathlib import Path
import sys
import unittest

from test_records import MeasuredRecordTests
from test_feature_records import FeatureRecordTests
from suiroai.contracts import digest, record_ref
from suiroai.modeling.frozen import finalize_validation


def main():
    model=MeasuredRecordTests('test_measured_initial_comparison_and_final_records_serialize')
    features=FeatureRecordTests('test_generated_and_materialized_features_serialize_with_immutable_evidence')
    try:
        model.setUp()
        features.setUp()
        proposal,feature_result=features.persist()
        passed=model.score(model.predicted+.5,identity='mock-export-pass')
        failed=model.score(model.predicted+20,identity='mock-export-fail')
        review=model.decision('final_validation','confirmed_failure',[failed['evidence_ref']],at='2026-10-17T09:05:00Z')
        terminal=finalize_validation(model.store,failed['evidence_ref'],parent_review=review)
        result={
            'evidence_mode':'mock', 'real_execution_accepted':False,
            'notice':'Actual calculations over explicit synthetic component fixtures. No customer data, approval, real LLM call, native stage run, genuine forecast, real final holdout score or restocking recommendation. Independent feature and model fixtures are not a coherent customer run.',
            'contract_version':'0.1.0-draft.3',
            'initial_nightly':'83f134fb7674de64d7f3a6b62f984bb6486ec81d',
            'source_nightly':'ee16115',
            'reproduce':'PYTHONPATH=src python3 tests/modeling/export_component_evidence.py',
            'initial_comparison':{'baseline_label':model.initial_measured['baseline_label'],
                'baseline_scores':model.initial_measured['baseline']['scores'],
                'candidate_scores':model.initial_measured['initial']['scores'],
                'comparison':model.initial_measured['comparison'],'parent_verified':False},
            'feature_specs':proposal['definitions'],
            'feature_materialization':features.context['materialized'],
            'feature_call':{'model_id':proposal['generation']['model_id'],'prompt_ref':proposal['generation']['prompt_ref'],'response_ref':proposal['generation']['response_ref'],'is_real_llm_call':False},
            'bounded_comparison':{'candidates':[{'candidate_id':c['candidate_id'],'feature_set_id':c['feature_set_id'],'scores':c['scores'],'rationale':c['rationale']} for c in model.measured['candidates']],
                'selected_candidate_id':model.measured['selected_candidate_id'],'tie_rule':model.measured['tie_rule'],'fit_count':model.measured['fit_count']},
            'frozen':model.frozen,
            'saved_forecast_payload':json.loads(model.store.read_bytes(model.frozen['frozen']['november_30_forecast_ref'])),
            'passing_validation':passed,'failing_validation':failed,'mock_parent_review_outcome':terminal,
            'limitations':['Every identity, source, approval, LLM response and parent decision here is mock.',
                'Temporary mock artifact stores are deleted; these content hashes describe test payloads and are not production retrieval references.',
                'Current genuine preparation does not establish complete demand horizons or historical outcome availability.',
                'Final gates in this implementation support absolute equal-series MAE/bias only; unsupported gates fail before freeze.',
                'Aggregate forecast fixture has no daily trajectory and cannot produce a recommendation.',
                'Feature fixture demonstrates materialization; its proposals did not earn inclusion in the separate numerical model fixture.',
                'Forecast accuracy alone does not prove stockout, profit or inventory-cost improvements.']}
        print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    finally:
        model.doCleanups()
        features.doCleanups()


if __name__=='__main__':main()
