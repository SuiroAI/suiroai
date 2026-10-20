"""Attempt the supplied retail example through the actual Streamlit browser UI.

Upload explicitly named source files, inspect the proposal, click approval once,
and record the visible terminal outcome plus source hashes and screenshots.
File actions are opt-in with --download-csv and --open-preview; the recording
path leaves the main explanation visible without opening or downloading files. A blocked attempt exits with code 2. Checks remain
separate from full milestone acceptance. No prewritten result is injected.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from suiroai.integration.artifacts import ArtifactStore


FILES = {
    "sales": "supplied_sales/Sales_transactions_2022_2025.csv",
    "inventory": "synthetic_inventory/inventory_position.csv",
    "receipts": "synthetic_inventory/inbound_deliveries.csv",
    "policy": "synthetic_ordering_rules/ordering_policy.csv",
}
QUESTION = "Using these files, produce an illustrative product/store restocking list as of November 30, 2025, with findings and limitations."


def matching_artifact(artifact_root, expected_sources, data, ref_field):
    """Match downloaded bytes to an immutable receipt for the supplied files.

    This checks transport identity, not analytical quality or milestone approval.
    Linear: https://linear.app/gr3enarr0w/issue/DSC-59
    """
    checksum = sha256(data).hexdigest()
    for receipt_path in artifact_root.glob("*/runs/attempt-*.json"):
        receipt = json.loads(receipt_path.read_bytes())
        stage = receipt.get("stage_result") or {}
        ref = stage.get(ref_field)
        sources = {item["approved_source_ref"]["sha256"] for item in stage.get("released_files", [])}
        if ref and sources == expected_sources and ref["sha256"] == checksum:
            if ArtifactStore(receipt_path.parents[1] / "store").read_bytes(ref) == data:
                return str(receipt_path)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/demo"))
    parser.add_argument("--download-csv", action="store_true",
                        help="Explicitly click and verify the CSV download; omitted for recording.")
    parser.add_argument("--open-preview", action="store_true",
                        help="Explicitly open and verify the HTML in a new tab; omitted for recording.")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright, expect

    args.output.mkdir(parents=True, exist_ok=True)
    selected_files = FILES
    record = {"format": "dsc59-real-browser-attempt-v1", "started_at": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION, "files": [], "success": False,
        "download_matches_stored_artifact": False, "html_matches_stored_artifact": False,
        "full_milestone_accepted": False, "csv_download_requested": args.download_csv,
        "csv_download_clicked": False, "html_open_requested": args.open_preview,
        "html_opened_in_new_tab": False, "output_controls_available": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1200, "height": 1100})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.get_by_role("heading", name="SuiroAI local demo").wait_for(timeout=30000)
        record["question_label"] = "What are you trying to solve for?"
        record["upload_areas"] = page.locator('input[type="file"]').count()
        record["accepts_multiple_files"] = page.locator('input[type="file"]').get_attribute("multiple") is not None
        page.screenshot(path=str(args.output / "00-upload.png"), full_page=True)
        page.get_by_label("What are you trying to solve for?").fill(QUESTION)
        inputs = page.locator('input[type="file"]')
        expect(inputs).to_have_count(1)
        inputs.set_input_files([str((args.data_root / relative).resolve()) for relative in selected_files.values()])
        for role, relative in selected_files.items():
            source = (args.data_root / relative).resolve()
            data = source.read_bytes()
            page.get_by_role("button", name="Remove " + source.name, exact=True).wait_for(timeout=15000)
            record["files"].append({"role": role, "name": source.name, "bytes": len(data), "sha256": sha256(data).hexdigest()})
        page.get_by_role("button", name="Review task", exact=True).click()
        # Missing current-process context has an explicit user-owned continue path.
        continue_button = page.get_by_role("button", name="Continue without a current approach", exact=True)
        page.get_by_role("heading", name="Review the proposed task", exact=True).or_(continue_button).or_(
            page.get_by_text("We couldn't check your files for your current approach. Select Review task to try again.", exact=True)
        ).first.wait_for(timeout=0)
        if continue_button.count():
            continue_button.click()
        page.get_by_role("heading", name="Review the proposed task").wait_for(timeout=30000)
        record["proposal_shown"] = True
        page.screenshot(path=str(args.output / "01-proposal.png"), full_page=True)
        assert page.get_by_role("button", name="Download restocking list (CSV)", exact=True).count() == 0
        page.get_by_role("button", name="Approve and run", exact=True).click()
        page.get_by_role("button", name="Approve and run", exact=True).wait_for(state="detached", timeout=0)
        # Wait for completion/failure without an overall analytical time limit.
        body = page.locator("body").inner_text()
        record["approved_once"] = True
        record["terminal_page"] = body
        record["javascript_errors"] = errors
        page.screenshot(path=str(args.output / "02-outcome.png"), full_page=True)
        download = page.get_by_role("button", name="Download restocking list (CSV)", exact=True)
        record["output_controls_available"] = bool(download.count())
        if record["output_controls_available"]:
            expected_sources = {item["sha256"] for item in record["files"]}
            html = page.get_by_role("link", name="View restocking list", exact=True)
            if args.open_preview and html.count():
                with page.expect_popup() as event:
                    html.click()
                report_page = event.value
                report_page.wait_for_load_state()
                response = context.request.get(report_page.url)
                assert response.ok
                assert "attachment" not in response.headers.get("content-disposition", "")
                html_data = response.body()
                (args.output / "report.html").write_bytes(html_data)
                report_page.screenshot(path=str(args.output / "03-html-report.png"), full_page=True)
                record["html_opened_in_new_tab"] = True
                record["html_sha256"] = sha256(html_data).hexdigest()
                record["html_matching_receipt"] = matching_artifact(args.artifact_root, expected_sources, html_data, "html_report_ref")
                record["html_matches_stored_artifact"] = record["html_matching_receipt"] is not None
            if args.download_csv:
                with page.expect_download() as event:
                    record["csv_download_clicked"] = True
                    download.click()
                file = event.value
                destination = args.output / Path(file.suggested_filename).name
                file.save_as(destination)
                data = destination.read_bytes()
                record["download_sha256"] = sha256(data).hexdigest()
                record["matching_receipt"] = matching_artifact(args.artifact_root, expected_sources, data, "unverified_report_ref")
                record["download_matches_stored_artifact"] = record["matching_receipt"] is not None
                record["outcome"] = "preview_and_csv_checked" if args.open_preview else "csv_checked"
            else:
                record["outcome"] = "preview_checked_csv_not_requested" if args.open_preview else "analysis_ready_no_files_opened"
        else:
            record["outcome"] = "no_report_returned"
        context.close()
        browser.close()
    record["source_files_unchanged"] = all(
        sha256((args.data_root / FILES[file["role"]]).read_bytes()).hexdigest() == file["sha256"]
        for file in record["files"])
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["success"] = (record["output_controls_available"] and record["source_files_unchanged"]
        and not record["javascript_errors"]
        and (not args.open_preview or record["html_matches_stored_artifact"])
        and (not args.download_csv or record["download_matches_stored_artifact"]))
    (args.output / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ("outcome", "success", "download_matches_stored_artifact", "proposal_shown", "approved_once")}))
    return 0 if record["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
