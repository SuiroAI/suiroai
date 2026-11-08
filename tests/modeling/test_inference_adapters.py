"""Synthetic integration calculations; no real data/execution acceptance."""
from datetime import date
from pathlib import Path
import json
import tempfile
import unittest

from suiroai.contracts import record_ref
from suiroai.integration.artifacts import ArtifactStore
from suiroai.modeling.core import canonical, Example, Window, ModelingError
from suiroai.modeling.inference import predict_november30
from suiroai.modeling.models import fit_model
from suiroai.modeling.frozen import freeze_bundle,score_frozen
from suiroai.modeling.prepared import materialize_reserved_targets,forecast_daily_rows

ROOT=Path(__file__).resolve().parents[2]
K=('mock-retail-restocking','P','S')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=ArtifactStore(Path(self.temp.name).resolve())
        packet=json.loads((ROOT/'examples/contracts/v0.1.0/successful_analysis.json').read_text())
        self.execution=next(r for r in packet['records'] if r['kind']=='execution_contract')
        self.execution['acceptance_rule']['metric_gates']=[{'metric_id':'mae','aggregation':'equal_series_mean','population_id':'mock-final','direction':'upper_bound','threshold':1,'unit':'product_unit'}]
        self.execution['acceptance_rule']['required_check_ids']=['frozen_coverage']
        self.execution['acceptance_rule']['minimum_observation_count']=1
        self.ref=self.store.put_bytes('mock-input',1,'mock',canonical({'MOCK':'development'}))
        training=[Example(Window(K,date(2024,1,d),2),(float(d),),2*d) for d in (1,2,3)]
        model=fit_model('mean',training)
        self.candidate={'candidate_id':'mock-initial','model_ref':self.store.put_bytes('mock-model',1,'mock',canonical({'format':'dsc28-fitted-model-v1','state':model.payload(),'candidate_id':'mock-initial','feature_names':['month']}))}
        self.feature_rows=[{'source_namespace':K[0],'Product_ID':'P','Store_ID':'S','origin':'2025-11-30','latest_information_available_date':'2025-11-30','month':11}]

    def test_saved_model_asof_inference_does_not_use_future_targets(self):
        predictions=predict_november30(self.store,candidate=self.candidate,feature_rows=self.feature_rows,feature_fields=['month'],horizons={K:2})
        self.assertEqual(predictions[0][1],4)
        with self.assertRaisesRegex(ModelingError,'ordered feature names'):
            predict_november30(self.store,candidate=self.candidate,feature_rows=self.feature_rows,feature_fields=['other'],horizons={K:2})
        self.feature_rows[0]['latest_information_available_date']='2025-12-01'
        with self.assertRaisesRegex(ModelingError,'availability'):
            predict_november30(self.store,candidate=self.candidate,feature_rows=self.feature_rows,feature_fields=['month'],horizons={K:2})

    def test_source_preserving_reserved_adapter_and_no_zero_fill(self):
        predictions=predict_november30(self.store,candidate=self.candidate,feature_rows=self.feature_rows,feature_fields=['month'],horizons={K:2})
        frozen=freeze_bundle(self.store,execution=self.execution,artifact_id='mock-freeze',selected_candidate_id='mock-initial',model_ref=self.candidate['model_ref'],feature_set_ref=self.ref,preprocessing_ref=self.ref,evaluation_plan_ref=self.ref,acceptance_rule=self.execution['acceptance_rule'],development_input_refs=[self.ref],forecast_input_refs=[self.ref],forecast=predictions,frozen_at='2026-10-17T12:00:00Z')
        source={'format':'dsc27-daily-v1','source_namespace':K[0],'rows':[{'Product_ID':'P','Store_ID':'S','Order_Date':f'2025-12-0{d}','target_quantity':2,'complete_daily_sales':True,'completeness_evidence_refs':[self.ref],'target_available_date':f'2025-12-0{d}'} for d in (1,2)]}
        source_ref=self.store.put_bytes('mock-reserved-original',1,'mock',canonical(source))
        stage={'kind':'stage_request','schema_version':'0.1.0-draft.3','artifact_id':'mock-stage','artifact_version':1,'provenance':'mock',
               'binding':self.execution['binding'],'run_id':self.execution['run_id'],
               'execution_contract_ref':record_ref(self.execution),'stage':'final_validation','attempt':1,
               'parent_authorization':{'checkpoint':'final_validation','decision':'proceed','actor':'mock-parent','decided_at':'2026-10-17T12:01:00Z','reason':'MOCK post-freeze release','evidence_refs':[self.ref]},
               'released_input_refs':[], 'remaining_limits':dict(self.execution['limits']),
               'issued_at':'2026-10-17T12:01:00Z','deadline':'2026-10-17T13:00:00Z','output_namespace':'mock-output'}
        stage['execution_contract_ref']=record_ref(self.execution)
        stage['released_input_refs'].append(source_ref)
        stage['issued_at']='2026-10-17T12:01:00Z'
        derived=materialize_reserved_targets(self.store,bundle_ref=frozen['bundle_ref'],reserved_unseen_data_ref=source_ref,stage_request=stage,artifact_id='mock-reserved-targets',observed_through=date(2025,12,31))
        self.assertEqual(next(iter(derived['actuals'].values())).actual,4)
        scored=score_frozen(self.store,frozen['bundle_ref'],derived['actuals'],reserved_targets_ref=derived['reserved_targets_ref'],reserved_unseen_data_ref=source_ref,holdout_accessed_at='2026-10-17T12:02:00Z',observed_through=date(2025,12,31),population_id='mock-final')
        self.assertEqual(scored['evidence']['outcome'],'pass')
        self.assertEqual(scored['evidence']['reserved_unseen_data_ref'],source_ref)
        self.assertEqual(scored['evidence']['scores'][0]['value'],0)
        source['rows'][0]['complete_daily_sales']=False
        sparse_ref=self.store.put_bytes('mock-incomplete-source',1,'mock',canonical(source))
        stage['released_input_refs'].append(sparse_ref)
        incomplete=materialize_reserved_targets(self.store,bundle_ref=frozen['bundle_ref'],reserved_unseen_data_ref=sparse_ref,stage_request=stage,artifact_id='mock-incomplete-targets',observed_through=date(2025,12,31))
        self.assertEqual(incomplete['actuals'],{})
        stage['issued_at']='2026-10-17T11:59:00Z'
        with self.assertRaisesRegex(ModelingError,'post-freeze'):
            materialize_reserved_targets(self.store,bundle_ref=frozen['bundle_ref'],reserved_unseen_data_ref=source_ref,stage_request=stage,artifact_id='mock-illegal',observed_through=date(2025,12,31))


if __name__=='__main__':unittest.main()
