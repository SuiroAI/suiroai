from pathlib import Path
import json, shutil
root=Path(__file__).resolve().parent; dest=root/'initial_implementation'; dest.mkdir(exist_ok=True)
for name in ['comparison_summary.csv','scores_by_origin.csv','comparison_predictions.csv','diagnostics.json','measured_results.json','workload.json','order_sensitivity.csv','complete_week_diagnostics.csv','sparsity_diagnostics.csv','restocking.csv','result.json']:
 shutil.copy2(root/name,dest/name)
note={'status':'Prospective implementation correction before corrected scores','reason':'During code review, pooled product/store totals used a fixed calendar-week denominator. Correct pooled means to use observed pair-weeks only, so entirely unobserved store-weeks never implicitly count as zero. Candidate set, baseline, training windows, horizons, metric and selection rule unchanged. Original scores retained in initial_implementation; final corrected outputs supersede them. This is a missingness implementation repair, not adaptive candidate discovery.','changes':'pooled = observed product mean * observed store mean / observed global mean; shrink prior remains 13 weeks.','previous_evidence_used':'Source coverage check identified 14 entirely unobserved store-weeks across history; code review, not a search for gain.','results_label':'All scores remain exploratory development evidence; no untouched outcomes.'}
(root/'implementation_correction.json').write_text(json.dumps(note,indent=2)+'\n')
print('Initial scores retained; correction recorded before recomparison.')
