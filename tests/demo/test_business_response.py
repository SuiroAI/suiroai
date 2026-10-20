"""Verify isolated second writing turns, preserved outputs and consent checks.

Explicit fake hosts exercise wiring/integrity only, not real LLM accuracy.
Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from suiroai.demo.business_response import run_business_response
from suiroai.integration.artifacts import ArtifactStore


@pytest.fixture
def inputs(tmp_path):
    store = ArtifactStore(tmp_path / 'store')
    out = tmp_path / 'old-output'; out.mkdir()
    note = b'Order 12 units. Baseline comparison is small. Check synthetic stock.'
    csv = b'Product_ID,Store_ID,OrderQty,Quantity_Unit\nP,S,12,product_unit\nP,T,0,product_unit\n'
    response_ref = store.put_bytes('original-note', 1, 'derived', note)
    csv_ref = store.put_bytes('original-csv', 1, 'derived', csv)
    (out / 'response.md').write_bytes(note); (out / 'restocking.csv').write_bytes(csv)
    (out / 'routine_workload.json').write_text('{"seconds":0.4}')
    (out / 'measured_results.json').write_text('{"gain":0.02}')
    # Deliberately excluded; the writer must never get raw data or model bytes.
    (out / 'raw_sales.csv').write_text('forbidden')
    (out / 'selected_model.npz').write_bytes(b'forbidden')
    analysis = {'native_outcome': 'completed', 'unverified_investigation_text': note.decode(),
        'native_original_investigation_ref': response_ref, 'unverified_investigation_ref': response_ref,
        'unverified_report_ref': csv_ref, 'native_original_report_path': str(out / 'restocking.csv'),
        'thread_id': 'analysis-thread', 'turn_id': 'analysis-turn'}
    return store, out, analysis


class Writer:
    def __init__(self, *, corrupt=False, revoke=None):
        self.calls = []; self.corrupt = corrupt; self.revoke = revoke

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        released = kwargs['released_root']
        manifest = (released / 'source_manifest.json').read_bytes()
        text = b'Buy 12 units from the list. Check your real stock before purchasing.'
        (kwargs['cwd'] / 'business_response.md').write_bytes(text)
        result = {'format': 'dsc60-business-rewrite-v1', 'source_manifest_sha256': sha256(manifest).hexdigest(),
                  'response_file': 'business_response.md', 'response_sha256': 'wrong' if self.corrupt else sha256(text).hexdigest()}
        (kwargs['cwd'] / 'rewrite_result.json').write_text(json.dumps(result))
        if self.revoke: self.revoke()
        return SimpleNamespace(outcome='completed', error_code=None, message=None,
            thread_id='writer-thread', turn_id='writer-turn', evidence={})


def test_separate_writer_receives_only_bounded_evidence_and_keeps_originals(inputs, tmp_path):
    store, old, analysis = inputs
    before = {p.name: p.read_bytes() for p in old.iterdir()}
    host = Writer()
    result = run_business_response(store, analysis, tmp_path / 'new-runs', lambda: True, host=host)
    assert result['status'] == 'rewritten'
    call = host.calls[0]
    assert call['timeout_seconds'] is None
    assert call['cwd'].parent != old
    assert set(p.name for p in call['released_root'].iterdir()) == {'original_response.md', 'csv_facts.json',
        'source_manifest.json', 'measured_results.json', 'routine_workload.json'}
    facts = json.loads((call['released_root'] / 'csv_facts.json').read_text())
    assert (facts['row_count'], facts['positive_order_rows'], facts['total_order_units']) == (2, 1, 12)
    assert 'no mandatory 150' in call['prompt']
    assert 'Do not include prices, cost estimates' in call['prompt']
    assert 'what the selected method does' in call['prompt']
    assert 'controller appends' not in call['prompt']
    assert result['thread_id'] == 'writer-thread'
    assert store.read_bytes(result['response_ref']).decode() == result['text']
    assert result['source_manifest_ref'] and result['writer_result_ref'] and result['receipt_ref']
    assert {p.name: p.read_bytes() for p in old.iterdir()} == before
    assert Path(result['call_trace']['prompt_path']).read_text() == call['prompt']


def test_bad_writer_hash_falls_back_without_customer_warning(inputs, tmp_path):
    store, _, analysis = inputs
    result = run_business_response(store, analysis, tmp_path / 'runs', lambda: True, host=Writer(corrupt=True))
    assert result['status'] == 'original_retained'
    assert result['text'] == analysis['unverified_investigation_text']
    assert result['error']['message'].startswith('Writer response checksum')
    assert result['receipt_ref']


def test_revoked_consent_before_dispatch_and_after_completion_blocks_publication(inputs, tmp_path):
    store, _, analysis = inputs
    host = Writer()
    with pytest.raises(ValueError, match='revoked'):
        run_business_response(store, analysis, tmp_path / 'before', lambda: False, host=host)
    assert not host.calls
    state = {'approved': True}
    with pytest.raises(ValueError, match='revoked'):
        run_business_response(store, analysis, tmp_path / 'after', lambda: state['approved'],
            host=Writer(revoke=lambda: state.update(approved=False)))


def test_transport_failure_retains_original_and_exact_prompt_trace(inputs, tmp_path):
    store, _, analysis = inputs
    class Failed:
        def execute(self, **kwargs):
            raise RuntimeError('TEST transport failed')
    result = run_business_response(store, analysis, tmp_path / 'runs', lambda: True, host=Failed())
    assert result['status'] == 'original_retained'
    assert result['text'] == analysis['unverified_investigation_text']
    assert result['call_trace']['transport_exception']['message'] == 'TEST transport failed'


def test_released_source_tamper_cannot_adopt_rewrite(inputs, tmp_path):
    store, _, analysis = inputs
    class Tampered(Writer):
        def execute(self, **kwargs):
            result = super().execute(**kwargs)
            path = kwargs['released_root'] / 'original_response.md'
            path.chmod(0o600)
            path.write_text('changed')
            return result
    result = run_business_response(store, analysis, tmp_path / 'runs', lambda: True, host=Tampered())
    assert result['status'] == 'original_retained'
    assert result['text'] == analysis['unverified_investigation_text']
    assert result['source_manifest_ref'] and result['prompt_ref'] and result['call_trace_ref']


def test_progress_revocation_prevents_writer_dispatch(inputs, tmp_path):
    """Recheck trusted consent after callbacks that can change browser state."""
    store, _, analysis = inputs
    state = {"approved": True}
    host = Writer()

    def progress(_message):
        state["approved"] = False

    with pytest.raises(ValueError, match="revoked"):
        run_business_response(store, analysis, tmp_path / "runs", lambda: state["approved"],
            host=host, progress=progress)
    assert host.calls == []
    assert not list((tmp_path / "runs").glob("business-response-*/native-trace/outbound-prompt.txt"))


def test_internal_cost_includes_writer_without_changing_customer_bytes(inputs, tmp_path):
    from tests.demo.test_cost_summary import stage
    store, _, analysis = inputs
    analysis['prior_model_usage'] = [stage('current_process'), stage('analysis')]

    class MeteredWriter(Writer):
        def execute(self, **kwargs):
            result = super().execute(**kwargs)
            result.evidence['model_usage'] = stage('business_response')['model_usage']
            return result

    result = run_business_response(store, analysis, tmp_path / 'runs', lambda: True, host=MeteredWriter())
    assert result['text'] == 'Buy 12 units from the list. Check your real stock before purchasing.'
    assert 'US$' not in result['text']
    assert store.read_bytes(result['response_ref']).decode() == result['text']
    assert store.read_bytes(result['writer_prose_ref']) == b'Buy 12 units from the list. Check your real stock before purchasing.'
    assert result['writer_prose_ref'] == result['response_ref']
    receipt = json.loads(store.read_bytes(result['receipt_ref']))
    assert receipt['ai_cost_estimate']['estimated_api_equivalent_usd'] == '7.860000'
    assert receipt['ai_cost_estimate']['customer_sentence'] is None
    assert result['ai_cost_estimate']['status'] == 'estimated'
