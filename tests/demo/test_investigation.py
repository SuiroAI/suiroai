"""Test approved exploratory Data handoff with explicit native transport doubles.

Check that pending policies and absent dictionaries can reach a real-host API
boundary while December outcomes and revoked consent cannot. These tests do
not establish a live Data run or independently verified analytical output.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from suiroai.contracts import proposal_digest, record_ref
from suiroai.demo.investigation import present_data_output, run_investigation
from suiroai.demo.service import DemoSession, UploadedInput
from suiroai.integration.native import NativeRun


@pytest.fixture
def approved(tmp_path, request):
    """Build measured fixture records and an explicit test consent authority."""
    files = {
        "sales.csv": b"Product_ID,Store_ID,Order_Date,Quantity,Order_Status,Return_Flag\nP,S,2025-11-29,2,Completed,No\nP,S,2025-11-29,2,Completed,No\nP,S,2025-12-01,987654321,Completed,No\n",
        "inventory.csv": b"Product_ID,Store_ID,Snapshot_Date,Usable_On_Hand_Qty,On_Order_Qty\nP,S,2025-11-30,1,2\n",
        "receipts.csv": b"Product_ID,Store_ID,Expected_Arrival_Date,Incoming_Qty\nP,S,2025-12-03,2\n",
        "policy.csv": b"Product_ID,Store_ID,Supplier_Lead_Time_Days,Review_Period_Days,Safety_Stock_Qty,Minimum_Order_Qty,Order_Multiple_Qty\nP,S,3,7,1,1,1\n",
    }
    files.update(getattr(request, "param", {}))
    calls = []

    def backend(*args):
        calls.append(args)
        return SimpleNamespace(status="blocked", message="TEST capture", evidence_path=None)

    session = DemoSession(artifact_root=tmp_path / "session", backend=backend)
    view = session.review("Please restock with findings and limitations.",
        [UploadedInput(name=name, data=data) for name, data in files.items()])
    session.approve_and_run(view["proposal_digest"])
    store, submission, proposal, approval = calls[0][:4]
    proposal, approval = deepcopy(proposal), deepcopy(approval)
    proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
    approval["binding"] = deepcopy(proposal["binding"])
    approval["proposal_ref"] = record_ref(proposal)
    # Explicit fixture authority authenticates exact current approval/proposal.
    validator = lambda a, p: a == approval and p == proposal
    return store, submission, proposal, approval, tmp_path / "runs", validator


def test_pending_policies_and_no_dictionary_reach_native_data_boundary(approved):
    """Release development records and supplied operations without model policy."""
    calls = []

    class Host:
        def execute(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["timeout_seconds"] is None
            release = kwargs["released_root"]
            contents = [p.read_bytes() for p in release.iterdir()]
            assert len(contents) == 4
            assert not any(b"987654321" in data for data in contents)
            assert sum(data.count(b"2025-11-29") for data in contents) == 2
            assert any(b"2025-12-03" in data for data in contents)  # known inbound due date
            assert "dictionary" not in kwargs["prompt"].lower()
            assert "Do not ask the user any clarification questions" in kwargs["prompt"]
            assert "Own the analytical decisions" in kwargs["prompt"]
            assert "independent verification has not been completed" not in kwargs["prompt"]
            assert "analytical deliverable" in kwargs["prompt"]
            assert "substantive scientific limitations" in kwargs["prompt"]
            assert "Please restock with findings and limitations." in kwargs["prompt"]
            assert "fit and compare models using development data" in kwargs["prompt"]
            (kwargs["cwd"] / "investigation.md").write_text("TEST unverified investigation")
            _write_result(kwargs["cwd"])
            return NativeRun(outcome="completed", thread_id="TEST-thread", turn_id="TEST-turn")

    assert approved[2]["target_policy"]["status"] == "pending"
    assert approved[2]["acceptance_rule"]["status"] == "pending"
    result = run_investigation(*approved, host=Host())
    assert len(calls) == 1
    assert result["native_outcome"] == "completed"
    assert result["thread_id"] == "TEST-thread"
    assert result["unverified_investigation_text"] == "TEST unverified investigation"
    assert approved[0].read_bytes(result["unverified_investigation_ref"]) == b"TEST unverified investigation"
    assert result["analytical_model_turn_requested"] is True
    assert result["verified_report_available"] is False
    assert result["final_policy_frozen"] is False
    assert result["disposition"] == "analysis"
    assert approved[0].read_bytes(result["unverified_report_ref"]) == b"<html><body>TEST analysis</body></html>"
    sales = next(file for file in result["released_files"] if file["source_role"] == "transactions")
    lineage = json.loads(approved[0].read_bytes(sales["controller_lineage_ref"]))
    assert lineage["included_source_records"] == [1, 2]
    assert lineage["released_byte_sha256"] == sales["released_byte_sha256"]
    assert lineage["duplicates_preserved"] is True


def test_inventory_only_approval_cannot_start_data(approved):
    """Require exploratory permission in the exact approved proposal."""
    args = list(approved)
    args[2] = deepcopy(args[2])
    args[2]["assumptions"] = [a for a in args[2]["assumptions"]
        if a["assumption_id"] != "development_investigation"]
    args[5] = lambda *_: True  # test authority; scope remains mandatory
    with pytest.raises(ValueError, match="does not authorize"):
        run_investigation(*args)
    assert not Path(args[4]).exists()


def test_revocation_before_source_read_starts_no_host(approved):
    """Reject revoked consent before accessing any approved source bytes."""
    args = list(approved)
    args[5] = lambda *_: False
    with pytest.raises(ValueError, match="revoked"):
        run_investigation(*args)
    assert not Path(args[4]).exists()


def test_revocation_during_native_run_prevents_result_adoption(approved):
    """Recheck the browser ledger after a potentially long native turn."""
    args = list(approved)
    current = [True]
    args[5] = lambda *_: current[0]

    class Host:
        def execute(self, **kwargs):
            current[0] = False
            return NativeRun(outcome="completed", thread_id="TEST-stale")

    with pytest.raises(ValueError, match="revoked"):
        run_investigation(*args, host=Host())


def _write_result(output, *, disposition="analysis", report=b"<html><body>TEST analysis</body></html>"):
    """Write explicit mocked artifacts with exact byte identity for transport tests."""
    (output / "report.html").write_bytes(report)
    result = {"disposition": disposition,
        "report_file": "report.html", "report_sha256": sha256(report).hexdigest()}
    if disposition == "needs_clarification":
        result.update(customer_questions=["Should returned units reduce replenishment quantities?"],
            report_file=None, report_sha256=None)
    (output / "result.json").write_text(json.dumps(result))


def test_legacy_clarification_is_rejected_without_exposing_questions(approved):
    """Data must own choices and produce supported findings instead of questions."""
    class Host:
        def execute(self, **kwargs):
            _write_result(kwargs["cwd"], disposition="needs_clarification")
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert result["disposition"] == "incomplete"
    assert result["customer_questions"] == []
    assert result["output_error"]
    assert result["unverified_report_ref"] is None


@pytest.mark.parametrize("corrupt", ["hash", "symlink", "traversal"])
def test_report_identity_and_containment_are_enforced(approved, corrupt):
    """A model manifest cannot publish forged bytes or an outside artifact."""
    class Host:
        def execute(self, **kwargs):
            output = kwargs["cwd"]
            _write_result(output)
            result = json.loads((output / "result.json").read_text())
            if corrupt == "hash":
                (output / "report.html").write_bytes(b"<html>CHANGED</html>")
            elif corrupt == "symlink":
                (output / "report.html").unlink()
                (output / "report.html").symlink_to(output.parent / "released" / "input-1.csv")
            else:
                result["report_file"] = "../released/input-1.csv"
                (output / "result.json").write_text(json.dumps(result))
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert result["output_error"]
    assert result["error_code"] == "output_contract_error"
    assert result["native_outcome"] == "completed"
    assert result["unverified_report_ref"] is None


@pytest.mark.parametrize("payload", [
    b"<script>alert(1)</script>", b"<p onclick='alert(1)'>X</p>",
    b"<a href='java&#x73;cript:alert(1)'>X</a>",
    b"<style>body{background:url(https://example.com/x)}</style>",
    b"<meta http-equiv='refresh' content='0;url=https://example.com'>",
    b"<iframe src='https://example.com'></iframe>",
])
def test_generated_html_rejects_active_or_external_content(approved, payload):
    """Exact byte publication is distinct from passive downloaded HTML safety."""
    class Host:
        def execute(self, **kwargs):
            _write_result(kwargs["cwd"], report=b"<html><body>" + payload + b"</body></html>")
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert result["output_error"]
    assert result["error_code"] == "output_contract_error"
    assert result["native_outcome"] == "completed"
    assert result["unverified_report_ref"] is None


@pytest.mark.parametrize("approved", [{
    "sales-part2.csv": b"Order_Date,Quantity\n2025-10-01,5\n2025-12-10,987654321\n",
    "context-one.csv": b"Unfamiliar_Field\nA\n",
    "context-two.csv": b"Another_Field\nB\n",
}], indirect=True)
def test_multiple_transaction_and_unfamiliar_sources_are_all_released_safely(approved):
    """Partition each dated file while preserving all unfamiliar approved inputs."""
    class Host:
        def execute(self, **kwargs):
            contents = [file.read_bytes() for file in kwargs["released_root"].iterdir()]
            assert len(contents) == 7
            assert not any(b"987654321" in data for data in contents)
            assert any(b"2025-10-01" in data for data in contents)
            assert any(b"Unfamiliar_Field" in data for data in contents)
            assert any(b"Another_Field" in data for data in contents)
            _write_result(kwargs["cwd"])
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert len(result["released_files"]) == 7
    assert sum(file["development_partition"] for file in result["released_files"]) == 2


def test_progress_callback_cannot_revoke_consent_then_start_host(approved):
    """Authenticate current consent immediately after potentially reentrant UI work."""
    args = list(approved)
    current = [True]
    args[5] = lambda *_: current[0]

    def progress(message):
        current[0] = False

    class Host:
        def execute(self, **kwargs):
            pytest.fail("Revoked consent must prevent native dispatch")

    with pytest.raises(ValueError, match="revoked"):
        run_investigation(*args, host=Host(), progress=progress)


def test_invalid_generated_output_keeps_native_turn_and_immutable_evidence_linked(approved):
    """Output rejection preserves genuine transport evidence for diagnosis."""
    class Host:
        def execute(self, **kwargs):
            data = b'TEST native transport receipt'
            (kwargs['evidence_dir'] / 'native-test.json').write_bytes(data)
            _write_result(kwargs['cwd'], report=b'<html><script>unsafe()</script></html>')
            return NativeRun(outcome='completed', thread_id='TEST-real-turn-link',
                turn_id='TEST-turn', evidence={'artifact_receipts': [{
                    'relative_path': 'native-test.json', 'bytes': len(data),
                    'sha256': sha256(data).hexdigest()}]})
    result = run_investigation(*approved, host=Host())
    assert result['output_error']
    assert result['thread_id'] == 'TEST-real-turn-link'
    assert result['turn_id'] == 'TEST-turn'
    assert result['native_outcome'] == 'completed'
    assert approved[0].read_bytes(result['immutable_native_evidence_refs'][0]) == b'TEST native transport receipt'
    assert result['unverified_report_ref'] is None


def test_explicit_finite_native_budget_is_still_forwarded(approved):
    """Preserve a finite caller budget while the default has no overall deadline."""
    class Host:
        def execute(self, **kwargs):
            assert kwargs["timeout_seconds"] == 120
            _write_result(kwargs["cwd"])
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host(), timeout_seconds=120)
    assert result["disposition"] == "analysis"


def test_presentation_retains_native_digest_and_every_analytical_value(approved):
    """Known house-copy removal creates lineage without rewriting scientific content."""
    analytical = "<h1>Restocking</h1><p>Missing dates remain unknown; proxy uses 28 days.</p><table><tr><td>336 pairs</td><td>927 inbound units</td><td>42 duplicates</td></tr></table>"
    notice = "Data-generated analysis; independent verification has not been completed."
    check_notice = "These checks share the analysis inputs and do not establish independent numerical or claim verification."
    original = ("<html><body><p>" + notice + "</p>" + analytical + "<p>" + check_notice + "</p></body></html>").encode()
    expected = ("<html><body><p>Data-generated analysis.</p>" + analytical + "<p></p></body></html>").encode()

    class Host:
        def execute(self, **kwargs):
            _write_result(kwargs["cwd"], report=original)
            (kwargs["cwd"] / "investigation.md").write_text(notice + "\n" + analytical)
            return NativeRun(outcome="completed")

    result = run_investigation(*approved, host=Host())
    store = approved[0]
    assert store.read_bytes(result["native_original_report_ref"]) == original
    assert result["native_original_report_sha256"] == sha256(original).hexdigest()
    assert store.read_bytes(result["unverified_report_ref"]) == expected
    assert result["presented_report_sha256"] == sha256(expected).hexdigest()
    assert Path(result["native_original_report_path"]).read_bytes() == original
    assert Path(result["unverified_report_path"]).read_bytes() == expected
    native_manifest = json.loads(store.read_bytes(result["unverified_result_ref"]))
    assert native_manifest["report_sha256"] == sha256(original).hexdigest()
    lineage = json.loads(store.read_bytes(result["presentation_lineage_ref"]))
    assert lineage["native_original_ref"] == result["native_original_report_ref"]
    assert lineage["presented_ref"] == result["unverified_report_ref"]
    assert analytical in result["unverified_investigation_text"]
    assert notice not in result["unverified_investigation_text"]
    assert notice in store.read_bytes(result["native_original_investigation_ref"]).decode()
    assert result["verified_report_available"] is False


def test_presentation_is_exact_literal_only_and_idempotent():
    """Scientific statements and unfamiliar notices are left exactly unchanged."""
    text = ("Return sensitivity is 14.2%; demand remains uncertain. "
        "Successful execution and self-checks do not establish independent numerical or claim verification. "
        "Unfamiliar verification wording stays unchanged.")
    presented = present_data_output(text)
    assert presented == "Return sensitivity is 14.2%; demand remains uncertain.  Unfamiliar verification wording stays unchanged."
    assert present_data_output(presented) == presented


def test_csv_deliverable_is_separate_from_plain_app_response_and_preserves_all_bytes(approved):
    """Deliver the source-format restocking list without editing product text or values."""
    csv = (b'Product_ID,Product_Name,Store_ID,OrderQty,Quantity_Unit\n'
        b'P1,Data-generated analysis; independent verification has not been completed.,S1,10,product_unit\n'
        b'P2,Ordinary product,S1,0,product_unit\n')

    class Host:
        def execute(self, **kwargs):
            output = kwargs['cwd']
            assert 'restocking.csv' in kwargs['prompt']
            assert 'Write response.md' in kwargs['prompt']
            assert 'Always write a standalone UTF-8 report.html' not in kwargs['prompt']
            (output / 'restocking.csv').write_bytes(csv)
            (output / 'response.md').write_text('Order 10 units of P1; P2 needs no order. The method uses supported recorded units.')
            (output / 'result.json').write_text(json.dumps({'disposition': 'analysis',
                'output_file': 'restocking.csv', 'output_sha256': sha256(csv).hexdigest()}))
            return NativeRun(outcome='completed')

    result = run_investigation(*approved, host=Host())
    assert result['unverified_report_name'] == 'restocking.csv'
    assert result['unverified_report_mime'] == 'text/csv'
    assert result['restocking_ref'] == result['unverified_report_ref']
    assert approved[0].read_bytes(result['unverified_report_ref']) == csv
    assert approved[0].read_bytes(result['native_original_report_ref']) == csv
    assert result['native_original_report_sha256'] == result['presented_report_sha256'] == sha256(csv).hexdigest()
    assert result['unverified_investigation_text'].startswith('Order 10 units')
    lineage = json.loads(approved[0].read_bytes(result['presentation_lineage_ref']))
    assert lineage['transformation'] == 'identity-csv-v1'
    assert lineage['replacements'] == []


@pytest.mark.parametrize('quantity', ['-1', 'NaN', '', '2.5'])
def test_csv_does_not_adopt_invalid_order_quantities(approved, quantity):
    """Reject malformed executable recommendations without silently replacing values."""
    class Host:
        def execute(self, **kwargs):
            output = kwargs['cwd']
            csv = ('Product_ID,Store_ID,OrderQty,Quantity_Unit\nP,S,' + quantity + ',product_unit\n').encode()
            (output / 'restocking.csv').write_bytes(csv)
            (output / 'result.json').write_text(json.dumps({'disposition': 'analysis',
                'output_file': 'restocking.csv', 'output_sha256': sha256(csv).hexdigest()}))
            return NativeRun(outcome='completed')
    result = run_investigation(*approved, host=Host())
    assert result['output_error']
    assert result['unverified_report_ref'] is None



def test_csv_and_demo_html_have_separate_exact_originals_and_presented_outputs(approved):
    """Deliver both views while retaining distinct native hashes and presentation lineage."""
    csv = b"Product_ID,Store_ID,OrderQty,Quantity_Unit\nP,S,10,product_unit\n"
    html = b"<html><body><p>Data-generated analysis; independent verification has not been completed.</p><table><tr><td>P</td><td>S</td><td>10</td></tr></table></body></html>"
    class Host:
        def execute(self, **kwargs):
            output = kwargs["cwd"]
            assert "Also write report.html" in kwargs["prompt"]
            (output / "restocking.csv").write_bytes(csv)
            (output / "report.html").write_bytes(html)
            (output / "response.md").write_text("Order 10 product units.")
            (output / "result.json").write_text(json.dumps({"disposition": "analysis",
                "output_file": "restocking.csv", "output_sha256": sha256(csv).hexdigest(),
                "html_file": "report.html", "html_sha256": sha256(html).hexdigest()}))
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert result["output_error"] is None
    store = approved[0]
    assert store.read_bytes(result["unverified_report_ref"]) == csv
    assert result["unverified_report_mime"] == "text/csv"
    assert store.read_bytes(result["native_original_html_report_ref"]) == html
    assert result["native_original_html_report_sha256"] == sha256(html).hexdigest()
    presented_html = present_data_output(html.decode()).encode()
    assert store.read_bytes(result["html_report_ref"]) == presented_html
    assert result["html_report_name"] == "report.html"
    assert result["html_report_mime"] == "text/html"
    assert Path(result["html_report_path"]).read_bytes() == presented_html
    assert b"<td>10</td>" in presented_html
    assert result["html_presentation_lineage_ref"] != result["presentation_lineage_ref"]


@pytest.mark.parametrize("corrupt", ["hash", "active"])
def test_html_companion_requires_exact_hash_and_passive_content(approved, corrupt):
    """A valid CSV cannot silently endorse a malformed HTML demo artifact."""
    class Host:
        def execute(self, **kwargs):
            output = kwargs["cwd"]
            csv = b"Product_ID,Store_ID,OrderQty\nP,S,10\n"
            html = b"<html><body>10</body></html>" if corrupt == "hash" else b"<html><script>unsafe()</script></html>"
            (output / "restocking.csv").write_bytes(csv)
            (output / "report.html").write_bytes(html)
            (output / "result.json").write_text(json.dumps({"disposition": "analysis",
                "output_file": "restocking.csv", "output_sha256": sha256(csv).hexdigest(),
                "html_file": "report.html", "html_sha256": "0" * 64 if corrupt == "hash" else sha256(html).hexdigest()}))
            return NativeRun(outcome="completed")
    result = run_investigation(*approved, host=Host())
    assert result["output_error"]
    assert result["unverified_report_ref"] is None
    assert not result.get("html_report_ref")
