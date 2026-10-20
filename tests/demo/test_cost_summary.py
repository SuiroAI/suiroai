"""Check complete-flow prices and immutable prose lineage without model calls.

Exercise known usage amounts, missing stages and duplicate native identities;
provider snapshots and pricing-component checks live in integration tests.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from suiroai.demo.cost_summary import summarize_model_cost


def stage(name):
    return {'stage': name, 'model_usage': {'available': True,
        'thread_id': name + '-thread', 'turn_id': name + '-turn',
        'counts': {'input_units': 1000000, 'cached_input_units': 200000,
                   'cache_write_input_units': 0, 'output_units': 100000,
                   'reasoning_output_units': 20000, 'total_units': 1100000}}}


def test_all_three_calls_including_writer_have_one_supported_price():
    result = summarize_model_cost([stage(n) for n in ('current_process', 'analysis', 'business_response')])
    # Each call: .8M*2 + .2M*.1 + .1M*10 = $2.62, including reasoning.
    assert result['estimated_api_equivalent_usd'] == '7.860000'
    assert result['customer_sentence'] is None
    assert result['actual_charge'] is False


def test_missing_usage_is_not_silently_priced_as_zero():
    entries = [stage(n) for n in ('current_process', 'analysis', 'business_response')]
    entries[0]['model_usage'] = None
    result = summarize_model_cost(entries)
    assert result['estimated_api_equivalent_usd'] is None
    assert result['customer_sentence'] is None


def test_reused_native_identity_cannot_count_twice():
    entries = [stage(n) for n in ('current_process', 'analysis', 'business_response')]
    entries[2]['model_usage'] = entries[1]['model_usage']
    assert summarize_model_cost(entries)['status'] == 'incomplete_usage'


def test_observed_long_request_produces_a_range_not_short_only_price():
    entries = [stage(n) for n in ('current_process', 'analysis', 'business_response')]
    entries[1]['model_usage']['max_observed_request_input_units'] = 300000
    result = summarize_model_cost(entries)
    assert result['estimated_standard_rate_range_usd'] == {'lower': '7.860000', 'upper': '9.980000'}
    assert result['customer_sentence'] is None
