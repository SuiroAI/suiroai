"""Summarize observed AI usage after all three demo stages have completed.

The controller adds one plain cost estimate after the writer returns, so its own
usage is included without an endless extra writing call. Keep original prose
and numeric receipts separate; estimates use published rates, never invoice data.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from decimal import Decimal, ROUND_HALF_UP

from suiroai.integration.usage import estimate_api_cost


STAGES = ('current_process', 'analysis', 'business_response')


def summarize_model_cost(entries):
    """Require distinct, available native receipts for the complete actual flow."""
    result = {'format': 'dsc60-demo-ai-cost-v1', 'status': 'incomplete_usage',
        'actual_charge': False, 'stages': [], 'estimated_api_equivalent_usd': None,
        'customer_sentence': None}
    if not isinstance(entries, list) or len(entries) != len(STAGES):
        return result
    names, identities = set(), set()
    total = upper = Decimal(0)
    for entry in entries:
        if not isinstance(entry, dict):
            return result
        stage, usage = entry.get('stage'), entry.get('model_usage')
        if stage not in STAGES or stage in names or not isinstance(usage, dict):
            return result
        identity = usage.get('thread_id'), usage.get('turn_id')
        if not all(isinstance(value, str) and value for value in identity) or identity in identities:
            return result
        estimate = estimate_api_cost(usage)
        result['stages'].append({'stage': stage, 'model_usage': usage, 'estimate': estimate})
        if estimate.get('status') != 'estimated':
            return result
        total += Decimal(estimate['estimated_api_equivalent_usd'])
        # A mixed thread cannot be priced exactly from cumulative counters. If
        # a long request was observed, bound it with whole-thread long pricing.
        maximum = usage.get('max_observed_request_input_units')
        long_request = type(maximum) is int and maximum > estimate['pricing']['long_context_input_threshold']
        ceiling = estimate_api_cost(usage, context_pricing='long') if long_request else estimate
        upper += Decimal(ceiling['estimated_api_equivalent_usd'])
        if long_request:
            result['stages'][-1]['long_context_upper_scenario'] = ceiling
        names.add(stage); identities.add(identity)
    if names != set(STAGES):
        return result
    display = ('less than US$0.01' if total < Decimal('0.01') else
               'about US$' + str(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    if upper > total:
        display = ('about US$' + str(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                   + '–US$' + str(upper.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    result.update(status='estimated', estimated_api_equivalent_usd=str(total),
        estimated_standard_rate_range_usd={'lower': str(total), 'upper': str(upper)},
        customer_sentence='Estimated AI processing cost for this analysis: ' + display
        + ', using OpenAI’s [published standard rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol).',
        scope='The observed intake, analysis and explanation calls for this task; not an invoice or a scheduled-run quote.')
    return result
