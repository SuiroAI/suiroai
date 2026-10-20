"""Check native numeric-only cumulative usage and bounded cost arithmetic.

No live calls or private message bodies are used; fixtures model CLI0.163's
locally generated ThreadTokenUsageUpdatedNotification JSON schema.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
import io
import json
from decimal import Decimal

from suiroai.integration.native import _Transport
from suiroai.integration.native_profile import sanitize
from suiroai.integration.usage import UsageAccumulator, estimate_api_cost


def breakdown(i=1000, cached=600, writes=100, out=200, reasoning=50):
    return {'inputTokens':i,'cachedInputTokens':cached,'cacheWriteInputTokens':writes,
            'outputTokens':out,'reasoningOutputTokens':reasoning,'totalTokens':i+out}


def event(total=None, last=None, thread='t', turn='u'):
    return {'threadId':thread,'turnId':turn,'tokenUsage':{'total':total or breakdown(),
        'last':last or breakdown(), 'modelContextWindow':475000}, 'apiKey':'PRIVATE'}


def test_snapshots_are_replaced_not_summed_and_binding_is_exact():
    usage=UsageAccumulator()
    usage.observe(event())
    usage.observe(event())
    usage.observe(event(breakdown(2000,1200,200,400,100)))
    receipt=usage.receipt('t','u')
    assert receipt['counts']['input_units']==2000
    assert receipt['counts']['output_units']==400
    assert receipt['snapshot_count']==3
    assert usage.receipt('t','other')['available'] is False
    assert 'PRIVATE' not in json.dumps(receipt)
    assert 'apiKey' not in json.dumps(receipt)
    assert sanitize({'model_usage':receipt})['model_usage']==receipt


def test_missing_cache_write_is_unknown_and_reasoning_not_double_counted():
    raw=breakdown(writes=0);del raw['cacheWriteInputTokens']
    usage=UsageAccumulator();usage.observe(event(raw,raw))
    receipt=usage.receipt('t','u')
    assert receipt['counts']['cache_write_input_units'] is None
    estimate=estimate_api_cost(receipt)
    assert estimate['estimated_api_equivalent_usd']=='0.002860'
    assert any('zero cache writes assumed' in a for a in estimate['assumptions'])
    assert Decimal(estimate['component_usd']['output_including_reasoning'])==Decimal('.002')


def test_cached_reads_and_writes_are_not_double_billed_as_normal_input():
    usage=UsageAccumulator();usage.observe(event())
    estimate=estimate_api_cost(usage.receipt('t','u'),service_tier='standard',context_pricing='short')
    assert estimate['estimated_api_equivalent_usd']=='0.002910'
    assert estimate['component_usd']=={'uncached_input':'0.0006','cached_input':'0.00006',
        'cache_write_input':'0.00025','output_including_reasoning':'0.002'}
    assert not estimate['actual_charge']


def test_fast_and_long_context_are_explicit_scenarios_not_capacity_inference():
    usage=UsageAccumulator();usage.observe(event())
    receipt=usage.receipt('t','u')
    standard=estimate_api_cost(receipt)
    assert standard['context_pricing_scenario']=='short'
    assert 'request length' in standard['assumptions'][1]
    cost=estimate_api_cost(receipt,service_tier='fast',context_pricing='long')
    assert cost['estimated_api_equivalent_usd']=='0.009640'
    assert any('entire thread' in a for a in cost['assumptions'])


def test_bad_negative_boolean_overcount_or_stale_updates_do_not_pollute_totals():
    usage=UsageAccumulator();usage.observe(event())
    for bad in [breakdown(i=-1),breakdown(i=True),breakdown(cached=999,writes=2),breakdown(reasoning=500)]:
        usage.observe(event(bad,bad))
    usage.observe(event(breakdown(i=500,cached=100,writes=0,out=100),breakdown(i=500,cached=100,writes=0,out=100)))
    assert usage.receipt('t','u')['counts']['input_units']==1000
    assert usage.receipt('t','u')['rejected_update_count']==5


def test_missing_usage_or_unsupported_model_does_not_invent_zero_cost():
    receipt=UsageAccumulator().receipt('t','u')
    assert receipt['counts']['input_units'] is None
    assert estimate_api_cost(receipt)['estimated_api_equivalent_usd'] is None
    assert estimate_api_cost(None)['estimated_api_equivalent_usd'] is None
    assert estimate_api_cost(receipt,model='unpriced')['estimated_api_equivalent_usd'] is None


def test_raw_transport_captures_only_safe_numbers_and_keeps_log_redaction():
    transport=_Transport.__new__(_Transport)
    transport.log=io.StringIO();transport.log_bytes=0;transport.recording_exhausted=False
    transport.responses={};transport.started=[];transport.events=[];transport.errors=[]
    transport.rejected_requests=[];transport.terminals={}
    message={'method':'thread/tokenUsage/updated','params':event()}
    transport.consume('stdout',json.dumps(message).encode())
    assert transport.usage.receipt('t','u')['counts']['input_units']==1000
    logged=transport.log.getvalue()
    assert 'PRIVATE' not in logged
    assert '[REDACTED]' in logged
    assert 'inputTokens' not in logged
