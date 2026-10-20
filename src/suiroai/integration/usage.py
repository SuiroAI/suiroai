"""Retain safe native usage counters and estimate API-equivalent build costs.

Only whitelisted nonnegative integers cross this boundary. Thread/turn-bound
cumulative totals replace snapshots; output already includes reasoning. Rates
are a dated external estimate, never a Codex subscription charge or invoice.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

FIELDS = {'inputTokens': 'input_units', 'cachedInputTokens': 'cached_input_units',
          'cacheWriteInputTokens': 'cache_write_input_units', 'outputTokens': 'output_units',
          'reasoningOutputTokens': 'reasoning_output_units', 'totalTokens': 'total_units'}
REQUIRED = set(FIELDS) - {'cacheWriteInputTokens'}
PRICING = {'model': 'gpt-6.1-sol', 'as_of': '2026-10-20', 'currency': 'USD',
    'source_url': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol',
    'per_million_units': {'input': '2.00', 'cached_input': '0.10', 'cache_write_input': '2.50', 'output': '10.00'},
    'fast_multiplier': '2', 'long_context_input_threshold': 272000,
    'long_context_input_and_cache_multiplier': '2', 'long_context_output_multiplier': '1.5'}


def _count(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def _breakdown(raw):
    if not isinstance(raw, dict) or not REQUIRED <= set(raw):
        return None
    if any(key in raw and not _count(raw[key]) for key in FIELDS):
        return None
    result = {dest: raw.get(src) for src, dest in FIELDS.items()}
    if (result['cached_input_units'] > result['input_units']
            or result['reasoning_output_units'] > result['output_units']
            or result['total_units'] != result['input_units'] + result['output_units']
            or (result['cache_write_input_units'] is not None
                and result['cached_input_units'] + result['cache_write_input_units'] > result['input_units'])):
        return None
    return result


class UsageAccumulator:
    """Keep final cumulative usage separately for each exposed thread/turn pair."""

    def __init__(self):
        self._snapshots = {}
        self._rejected = 0

    def observe(self, params):
        if not isinstance(params, dict):
            self._rejected += 1
            return
        thread, turn = params.get('threadId'), params.get('turnId')
        usage = params.get('tokenUsage')
        if not isinstance(thread, str) or not thread or not isinstance(turn, str) or not turn or not isinstance(usage, dict):
            self._rejected += 1
            return
        total, last = _breakdown(usage.get('total')), _breakdown(usage.get('last'))
        if total is None or last is None or any(last[k] is not None and total[k] is not None and last[k] > total[k] for k in total):
            self._rejected += 1
            return
        identity = thread, turn
        previous = self._snapshots.get(identity)
        if previous and any(previous['counts'][key] is not None and value is not None and value < previous['counts'][key]
                            for key, value in total.items()):
            self._rejected += 1
            return
        if identity not in self._snapshots and len(self._snapshots) >= 64:
            self._rejected += 1
            return
        capacity = usage.get('modelContextWindow')
        self._snapshots[identity] = {'counts': total, 'source': 'native_thread_usage_cumulative_total',
            'model_context_capacity_units': capacity if _count(capacity) else None,
            'max_observed_request_input_units': max(last['input_units'], previous['max_observed_request_input_units'] if previous else 0),
            'snapshot_count': previous['snapshot_count'] + 1 if previous else 1,
            'thread_id': thread, 'turn_id': turn}

    def receipt(self, thread_id, turn_id):
        result = deepcopy(self._snapshots.get((thread_id, turn_id)))
        if result is None:
            result = {'counts': {name: None for name in FIELDS.values()}, 'source': 'unavailable',
                'thread_id': thread_id, 'turn_id': turn_id, 'snapshot_count': 0,
                'max_observed_request_input_units': None, 'model_context_capacity_units': None}
        return {'format': 'dsc60-native-usage-v1', 'available': result['source'] != 'unavailable', **result,
            'rejected_update_count': self._rejected,
            'counting_note': 'Final cumulative total, not summed snapshots. Output includes reasoning; do not add reasoning again. Capacity is not actual request length. Missing counters remain unknown.'}


def estimate_api_cost(usage, *, model='gpt-6.1-sol', service_tier=None, context_pricing=None):
    """Estimate with explicit scenario assumptions, not an authenticated bill.

    Short-context/standard defaults are stated assumptions when tier/context
    pricing are unknown. Mixed request lengths cannot be priced exactly from
    thread totals; long mode is a whole-thread scenario, not a precise invoice.
    Cached reads and reported cache writes are subsets of total input.
    """
    result = {'format': 'dsc60-api-equivalent-estimate-v1', 'pricing': deepcopy(PRICING),
        'model': model, 'actual_charge': False, 'estimated_api_equivalent_usd': None,
        'assumptions': [], 'limits': ['API-equivalent estimate, not a Codex subscription bill, actual charge or routine-model cost.',
        'Thread totals do not establish per-request pricing tier, request-length mix, taxes, credits or contractual rates.']}
    counts = usage.get('counts', {}) if isinstance(usage, dict) else {}
    if model != PRICING['model'] or not isinstance(usage, dict) or not usage.get('available') or any(not _count(counts.get(k)) for k in ['input_units','cached_input_units','output_units']):
        result['status'] = 'usage_or_supported_model_unavailable'
        return result
    if service_tier not in (None, 'standard', 'default', 'fast') or context_pricing not in (None, 'short', 'long'):
        result['status'] = 'unsupported_pricing_scenario'
        return result
    tier = 'standard' if service_tier in (None, 'default') else service_tier
    context = context_pricing or 'short'
    if service_tier in (None, 'default'):
        result['assumptions'].append('Standard API rates assumed; Codex service tier/billing treatment is not established.')
    if context_pricing is None:
        result['assumptions'].append('Short-context API rates assumed; actual per-request long-context mix is unknown. Cumulative input is not request length.')
    writes = counts.get('cache_write_input_units')
    if writes is None:
        writes = 0
        result['assumptions'].append('Cache-write count unavailable: zero cache writes assumed only for this estimate, not asserted as observed usage.')
    if not _count(writes) or counts['cached_input_units'] + writes > counts['input_units']:
        result['status'] = 'inconsistent_usage'
        return result
    normal = counts['input_units'] - counts['cached_input_units'] - writes
    multiplier = Decimal(2) if tier == 'fast' else Decimal(1)
    im = Decimal(2) if context == 'long' else Decimal(1)
    om = Decimal('1.5') if context == 'long' else Decimal(1)
    rates = PRICING['per_million_units']
    parts = {'uncached_input': Decimal(normal)*Decimal(rates['input'])*im,
        'cached_input': Decimal(counts['cached_input_units'])*Decimal(rates['cached_input'])*im,
        'cache_write_input': Decimal(writes)*Decimal(rates['cache_write_input'])*im,
        'output_including_reasoning': Decimal(counts['output_units'])*Decimal(rates['output'])*om}
    costs = {key: value*multiplier/Decimal(1000000) for key,value in parts.items()}
    result.update(status='estimated', service_tier_scenario=tier, context_pricing_scenario=context,
        estimated_api_equivalent_usd=str(sum(costs.values()).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)),
        component_usd={key:str(value) for key,value in costs.items()},
        usage_counts=deepcopy(counts))
    if context == 'long':
        result['assumptions'].append('Long-context multipliers applied to entire thread as a scenario; mixed short/long requests may cost differently.')
    return result
