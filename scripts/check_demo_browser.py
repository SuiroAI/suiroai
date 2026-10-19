"""Attempt the supplied retail example through the actual Streamlit browser UI.

Upload explicitly named source files, inspect the proposal, click approval once,
and record the visible terminal outcome plus source hashes and screenshots.
A blocked attempt exits with code 2 and never counts as successful end-to-end
acceptance. No fixture success or prewritten report is injected.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright, expect


FILES = {
    "sales": "supplied_sales/Sales_transactions_2022_2025.csv",
    "dictionary": "supplied_sales/sales_data_dictionary.csv",
    "inventory": "synthetic_inventory/inventory_position.csv",
    "receipts": "synthetic_inventory/inbound_deliveries.csv",
    "policy": "synthetic_ordering_rules/ordering_policy.csv",
}
QUESTION = "Using these files, produce an illustrative product/store restocking list as of November 30, 2025, with findings and limitations."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    record = {"format": "dsc59-real-browser-attempt-v1", "started_at": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION, "files": [], "success": False, "download_verified": False}
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
        inputs.set_input_files([str((args.data_root / relative).resolve()) for relative in FILES.values()])
        for i, (role, relative) in enumerate(FILES.items()):
            source = (args.data_root / relative).resolve()
            data = source.read_bytes()
            page.get_by_role("button", name="Remove " + source.name, exact=True).wait_for(timeout=15000)
            record["files"].append({"role": role, "name": source.name, "bytes": len(data), "sha256": sha256(data).hexdigest()})
        page.get_by_role("button", name="Review task", exact=True).click()
        page.get_by_role("heading", name="Review the proposed task").wait_for(timeout=30000)
        record["proposal_shown"] = True
        record["proposal_id"] = page.get_by_text("Proposal ID:", exact=False).inner_text()
        page.screenshot(path=str(args.output / "01-proposal.png"), full_page=True)
        assert page.get_by_role("button", name="Download verified HTML report").count() == 0
        page.get_by_role("button", name="Approve and run", exact=True).click()
        page.get_by_role("button", name="Approve and run", exact=True).wait_for(state="detached", timeout=90000)
        # The rerun removes the approval action only after the synchronous bounded attempt.
        body = page.locator("body").inner_text()
        record["approved_once"] = True
        record["terminal_page"] = body
        record["javascript_errors"] = errors
        page.screenshot(path=str(args.output / "02-outcome.png"), full_page=True)
        download = page.get_by_role("button", name="Download verified HTML report", exact=True)
        if download.count():
            with page.expect_download() as event:
                download.click()
            file = event.value
            file.save_as(args.output / file.suggested_filename)
            record["download_sha256"] = sha256((args.output / file.suggested_filename).read_bytes()).hexdigest()
            # A download alone is insufficient: compare it with the backend's retained verified artifact.
            record["outcome"] = "download_present_verification_pending"
        else:
            record["outcome"] = "blocked_no_verified_report"
        context.close()
        browser.close()
    record["source_files_unchanged"] = all(
        sha256((args.data_root / FILES[file["role"]]).read_bytes()).hexdigest() == file["sha256"]
        for file in record["files"])
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    (args.output / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ("outcome", "success", "download_verified", "proposal_shown", "approved_once")}))
    return 0 if record["success"] and record["download_verified"] else 2


if __name__ == "__main__":
    sys.exit(main())
