"""Exercise genuine pre-consent context inspection, never analytical execution.

All input CSVs are explicitly synthetic literal examples authored below.
No real uploaded CSV is read or released. Native workspaces stay under
/private/tmp; this directory receives fixtures, hashes and redacted provenance.
Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from suiroai.demo.service import DemoSession, UploadedInput


def hashed_file(path):
    data = path.read_bytes()
    return {"name": path.name, "sha256": sha256(data).hexdigest(), "bytes": len(data)}


def main():
    destination = Path(__file__).resolve().parent
    private = Path(tempfile.mkdtemp(prefix="dsc59-autodetect-", dir="/private/tmp"))
    question = "Please provide a restocking list for December 2025 using the supplied retail data."
    fixture_dir = destination / "synthetic-inputs"
    fixture_dir.mkdir(exist_ok=True)
    fixtures = {
        "sales.csv": "Product_ID,Store_ID,Order_Date,Quantity,Order_Status,Return_Flag\nP_DEMO,S_DEMO,2025-11-29,2,Complete,False\n",
        "inventory.csv": "Product_ID,Store_ID,Snapshot_Date,Usable_On_Hand_Qty,On_Order_Qty\nP_DEMO,S_DEMO,2025-11-30,1,1\n",
        "receipts.csv": "Product_ID,Store_ID,Expected_Arrival_Date,Incoming_Qty\nP_DEMO,S_DEMO,2025-12-02,1\n",
        "policy.csv": "Product_ID,Store_ID,Supplier_Lead_Time_Days,Review_Period_Days,Safety_Stock_Qty,Minimum_Order_Qty,Order_Multiple_Qty\nP_DEMO,S_DEMO,1,7,1,1,1\n",
    }
    for name, text in fixtures.items():
        (fixture_dir / name).write_text(text)
    files = [fixture_dir / name for name in fixtures]
    uploads = [UploadedInput(name=path.name, data=path.read_bytes()) for path in files]
    note = b"Context,Description\nCurrent restocking process,We currently place replenishment orders every Monday using the average daily sales over the last 90 days to estimate demand until the next review plus supplier lead time.\n"
    (fixture_dir / "notes.csv").write_bytes(note)
    manifest = {"format": "dsc59-genuine-synthetic-context-checks-v1", "started_at": datetime.now(timezone.utc).isoformat(),
        "payload_scope": "Only nonsensitive synthetic CSV examples authored as literals by this script; no actual uploaded retail CSV was read or released.",
        "destination": "Existing authenticated native OpenAI Codex model gpt-6.1-sol, verified by NativeHost.",
        "actual_private_file_live_check_performed": False,
        "question": question, "question_sha256": sha256(question.encode()).hexdigest(),
        "input_files": [hashed_file(path) for path in files],
        "controlled_note": {"name": "notes.csv", "sha256": sha256(note).hexdigest(),
            "bytes": len(note), "text": note.decode(), "demo_only": True},
        "genuine_native": True, "injected_detector_or_host_or_backend": False,
        "analysis_approval_granted": False, "cases": []}

    def persist():
        (destination / "results.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    persist()
    for name, case_uploads in (("current_process_in_uploaded_note", uploads + [UploadedInput(name="notes.csv", data=note)]),
                               ("retail_parameters_without_process", uploads)):
        print("Starting genuine context inspection: " + name, flush=True)
        session = DemoSession(artifact_root=private / name)
        view = session.review(question, case_uploads)
        context = session.context_for(question, case_uploads)
        case = {"case": name, "review_status": view["status"], "context": context,
            "analysis_attempt_count": len(session._attempted), "approval_exists": session._approval is not None}
        if context:
            evidence_path = context.get("evidence_path")
            if evidence_path:
                provenance = json.loads(Path(evidence_path).read_text())
                case["native_provenance"] = {field: provenance.get(field) for field in
                    ("format", "question_sha256", "native_outcome", "error_code", "message", "thread_id", "turn_id")}
                case["native_provenance_sha256"] = sha256(Path(evidence_path).read_bytes()).hexdigest()
                # Keep raw native logs and sales outside public evidence.
                case["context"].pop("evidence_path", None)
        else:
            evidence_paths = list(private.glob(name + "/**/inspection.json"))
            case["failure_provenance"] = [{field: json.loads(path.read_text()).get(field)
                for field in ("native_outcome", "error_code", "message")} for path in evidence_paths]
        if name == "current_process_in_uploaded_note":
            case["passed"] = (view["status"] == "awaiting_approval" and context is not None
                and context["status"] == "found"
                and any(item["source"] == "input-5.csv" for item in context.get("evidence", [])))
        else:
            case["initial_expectation_met"] = view["status"] == "awaiting_current_process"
            continued = session.review(question, case_uploads, continue_without=True)
            case["continued_status"] = continued["status"]
            case["passed"] = case["initial_expectation_met"] and continued["status"] == "awaiting_approval"
        case["analysis_attempt_count_after"] = len(session._attempted)
        case["approval_exists_after"] = session._approval is not None
        case["passed"] = (case["passed"] and not case["analysis_attempt_count_after"]
            and not case["approval_exists_after"])
        manifest["cases"].append(case)
        persist()
        print(json.dumps({"case": name, "status": view["status"], "passed": case["passed"]}), flush=True)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["all_passed"] = all(case["passed"] for case in manifest["cases"])
    persist()
    print("Results: " + str(destination / "results.json"), flush=True)
    if not manifest["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
