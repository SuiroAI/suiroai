"""MOCK prepared artifacts; genuine daily completeness remains unverified.

Check prepared-payload parsing, forecast examples, daily coverage, and
reserved-target construction without inferring missing-date completeness.

Requirement context for these component checks:
Connect safe preparation to evaluation without deriving daily completeness
from sparse observations, and exclude development target horizons that cross
into the reserved December holdout.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from datetime import date
import json
import unittest

from suiroai.modeling.core import Window, ModelingError
from suiroai.modeling.prepared import DailyView,build_examples,forecast_daily_rows

K=('MOCK','P','S')

def payload():
    return {'format':'dsc27-daily-v1','source_namespace':'MOCK','rows':[
        {'Product_ID':'P','Store_ID':'S','Order_Date':f'2025-01-0{d}',
         'target_quantity':d,'complete_daily_sales':True,'observed_record_day':True,
         'completeness_evidence_refs':[{'MOCK':'evidence'}],'target_available_date':f'2025-01-0{d}'} for d in (2,3)]}


class PreparedTests(unittest.TestCase):
    def test_complete_supported_labels_and_feature_alignment(self):
        view=DailyView.from_payload(payload())
        rows=build_examples(view,[{'Product_ID':'P','Store_ID':'S','origin':'2025-01-01','month':1}],['month'],[Window(K,date(2025,1,1),2)])
        self.assertEqual(rows[0].actual,5)
        self.assertEqual(rows[0].label_available_on,date(2025,1,3))

    def test_missing_or_incomplete_dates_are_not_zero(self):
        p=payload();p['rows'].pop()
        with self.assertRaisesRegex(ModelingError,'not zero'):
            DailyView.from_payload(p).horizon_target(Window(K,date(2025,1,1),2))
        p=payload();p['rows'][0]['complete_daily_sales']=False
        with self.assertRaisesRegex(ModelingError,'completeness'):
            DailyView.from_payload(p).horizon_target(Window(K,date(2025,1,1),2))

    def test_outcome_timing_unknown_and_future_rows_rejected(self):
        p=payload();del p['rows'][0]['target_available_date']
        with self.assertRaisesRegex(ModelingError,'availability is unknown'):
            DailyView.from_payload(p).horizon_target(Window(K,date(2025,1,1),2))
        p=payload();p['rows'][0]['Order_Date']='2025-12-01'
        with self.assertRaisesRegex(ModelingError,'chronology'):DailyView.from_payload(p)

    def test_daily_forecast_reader_never_splits_aggregate(self):
        w=Window(K,date(2025,11,30),2)
        p={'binding':{'task_id':'MOCK'},'run_id':'mock-run','rows':[dict(w.payload(),predicted=5)],'recommendation_ready':True,
           'daily_forecast':[{'key':{'source_namespace':'MOCK','product_id':'P','store_id':'S'},
                             'date':f'2025-12-0{d}','quantity':q,'quantity_unit':'product_unit',
                             'as_of_date':'2025-11-30','latest_information_available_date':'2025-11-30'} for d,q in ((1,2),(2,3))]}
        self.assertEqual(len(forecast_daily_rows(json.dumps(p).encode())),2)
        p['daily_forecast'][0]['quantity']=99
        with self.assertRaisesRegex(ModelingError,'differs'):forecast_daily_rows(json.dumps(p).encode())
        p['daily_forecast']=[]
        with self.assertRaisesRegex(ModelingError,'no verified'):forecast_daily_rows(json.dumps(p).encode())


if __name__=='__main__':unittest.main()
