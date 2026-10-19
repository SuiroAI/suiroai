"""Synthetic numerical counterexamples, not real DSC-28 acceptance.

Check metric aggregation and candidate comparisons against known numerical
answers, including persisted training-only preprocessing and model loading.
"""
from datetime import date
import unittest

from suiroai.modeling.core import Example, Prediction, Window, ModelingError
from suiroai.modeling.metrics import score, compare_values
from suiroai.modeling.models import fit_model, load_model

K=('MOCK','P1','S1')

def ex(x,y,day=1):
    return Example(Window(K,date(2024,1,day),1),(x,),y)


class CommonMathTests(unittest.TestCase):
    def test_equal_series_metrics_do_not_let_busy_store_hide_bad_series(self):
        rows=[Prediction(Window(K,date(2025,1,d),1),0,0) for d in range(1,11)]
        rows.append(Prediction(Window(('MOCK','P1','S2'),date(2025,1,1),1),0,10))
        actual=score(rows,'mock-population')
        self.assertEqual(actual['scores'][0]['value'],5)
        self.assertEqual(actual['scores'][1]['value'],5)
        with self.assertRaises(ModelingError):score(rows,'mock',include_wape=True)

    def test_pooled_wape_positive_single_sku_only(self):
        rows=[Prediction(Window(K,date(2025,1,1),2),10,8),
              Prediction(Window(('MOCK','P1','S2'),date(2025,1,1),2),30,36)]
        self.assertAlmostEqual(score(rows,'mock',include_wape=True)['scores'][2]['value'],.2)
        rows[1]=Prediction(Window(('MOCK','P2','S2'),date(2025,1,1),2),30,36)
        with self.assertRaisesRegex(ModelingError,'same namespace'):score(rows,'mock',include_wape=True)

    def test_metric_direction_and_tolerance(self):
        self.assertEqual(compare_values(10,9),'better')
        self.assertEqual(compare_values(10,11,'higher_is_better'),'better')
        self.assertEqual(compare_values(10,9,tolerance=1),'equal')
        with self.assertRaises(ModelingError):compare_values(0,float('nan'))

    def test_immutable_fitted_training_preprocessing_does_not_see_inference(self):
        model=fit_model('ridge',[ex(None,2),ex(2,4,2),ex(4,8,3)],{'alpha':1})
        before=model.state
        self.assertEqual(model.payload()['medians'],[3])
        model.predict(ex(100000,0,4))
        self.assertEqual(model.state,before)
        detached=model.payload();detached['medians'][0]=999
        self.assertEqual(model.payload()['medians'],[3])
        self.assertEqual(load_model(model.payload()).predict(ex(None,0,4)),model.predict(ex(None,0,4)))

    def test_ridge_known_solution_and_past_baseline(self):
        model=fit_model('ridge',[ex(1,2),ex(2,4,2),ex(3,6,3)],{'alpha':1})
        self.assertAlmostEqual(model.predict(ex(3,0,4)),5.5)
        baseline=fit_model('past_mean',[ex(1,2),ex(2,4,2)])
        self.assertEqual(baseline.predict(ex(99,0,4)),3)
        unknown=Example(Window(('MOCK','P1','new'),date(2025,1,1),1),(1,),0)
        with self.assertRaisesRegex(ModelingError,'past-only'):baseline.predict(unknown)

    def test_nonfinite_negative_or_misaligned_vectors_rejected(self):
        with self.assertRaises(ModelingError):ex(float('inf'),1)
        with self.assertRaises(ModelingError):ex(1,-1)
        model=fit_model('ridge',[ex(1,2),ex(2,4,2)])
        with self.assertRaises(ModelingError):model.predict(Example(Window(K,date(2025,1,1),1),(1,2),0))


if __name__=='__main__':unittest.main()
