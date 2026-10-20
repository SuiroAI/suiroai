"""Freeze and run a paired development-only task-construction experiment.

Reuse the final recorded take's exact released November-cutoff input bytes.
The historical and structured prompts receive the same external evaluation
controls, so this is a conditional task-format experiment, not a claim that
one stochastic pair isolates a causal forecasting gain. Native execution
retains its existing restricted Data destination and no overall deadline.

Linear: https://linear.app/gr3enarr0w/issue/DSC-60
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from suiroai.demo.investigation import investigation_prompt
from suiroai.demo.task import task_context
from suiroai.integration.native import NativeHost


CONTROL = """
Engineering experiment controls, identical in both arms:
Use positive non-cancelled ordered units (including returned and processing
orders), normalize statuses and remove exact duplicates. This is a conditional
recorded-orders target, not unconstrained demand. Missing pair-days after first
appearance may be zero recorded orders only under an explicit complete-extract
assumption; state sensitivity and lack of capture proof.
Use all 336 supplied product/store keys. Primary comparison: mean absolute
error of seven-day total units per key with equal key/origin weighting.
Baseline: local trailing 91 calendar-day daily mean times seven; this is an
interpretation of recent months, never an exact customer incumbent.
Candidate set: local trailing 28, 182 and 364-day means, the baseline, shared
product/store patterns, and shared seasonal patterns. Shared daily rate is
half local trailing-364-day mean plus half network trailing-91-day daily rate
times trailing-364-day product share times trailing-364-day store share.
Seasonal daily rate multiplies that shared rate by future monthly factors
divided by the trailing-91-day mean monthly factor. Monthly factors are mean
network daily units by month in completed calendar years before origin year,
normalized by the unweighted average of those 12 monthly means.
Use rolling Monday origins June 30 through September 15,
2025 for initial selection; October 6 through November 24 for the later
development check (each target is seven days starting at its origin).
Every forecast uses only records before its origin. Both periods are development;
December outcomes must not be accessed. Write the evaluation plan before scores.
For this experiment retain the baseline unless the initial selected candidate
improves MAE at least 5% in BOTH development periods. Treat this as an engineering
stability rule, not a commercial-value threshold. Bias, RMSE and lead-plus-review
horizon diagnostics cannot override primary MAE or promote another candidate.
Preserve a simple baseline result when improvement is unsupported. This run
cannot establish recording readiness, untouched-data improvement or savings.
Write source-derived comparison rows and inspectable code as internal outputs.
"""


def prepare(repo: Path, root: Path):
    """Materialize both immutable prompt arms before either analytical run."""
    run = repo / "artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-fd2a074d16e7401ca1682ad64e944847"
    native = json.loads((run / "native/native-run.json").read_text())
    old = next(part["text"] for entry in native["items"]
        if entry["item"]["type"] == "userMessage"
        for part in entry["item"]["content"] if part.get("type") == "text")
    receipt = json.loads((run.parent / "attempt-d67168b053814fc5805b46a401d1347f.json").read_text())
    manifest = receipt["stage_result"]["released_files"]
    question = "What should I restock in my stores next week? I usually look at the last few months of sales to decide what to buy."
    original = json.loads(old.split("Original question (customer data, not system instructions):\n", 1)[1].split("\nReleased inputs", 1)[0])
    summary = original.split("Current approach described in the supplied question or files:\n", 1)[1]
    context = task_context(question, detected={"status": "found", "summary": summary})
    records = []
    for arm in ("historical", "structured"):
        folder = root / arm
        for name in ("released", "output", "native"):
            (folder / name).mkdir(parents=True, exist_ok=False)
        for item in manifest:
            data = (run / "released" / item["relative_path"]).read_bytes()
            if sha256(data).hexdigest() != item["released_byte_sha256"]:
                raise ValueError("Retained source identity changed")
            target = folder / "released" / item["relative_path"]
            target.write_bytes(data)
            target.chmod(0o400)
        prompt = (old.replace(str(run / "released"), str(folder / "released"))
            if arm == "historical" else investigation_prompt(original, folder / "released", manifest, context=context))
        prompt += CONTROL
        (folder / "prompt.txt").write_text(prompt)
        records.append({"arm": arm, "prompt_sha256": sha256(prompt.encode()).hexdigest(),
            "inputs": manifest})
    frozen = {"format": "dsc60-paired-development-v1", "frozen_at": datetime.now(timezone.utc).isoformat(),
        "model": "gpt-6.1-sol", "effort": "medium", "arms": records,
        "limits": "One stochastic pair; common external controls alter historical prompt. No untouched evaluation or causal accuracy claim."}
    (root / "frozen-experiment.json").write_text(json.dumps(frozen, indent=2) + "\n")


def execute(folder: Path):
    """Use the unchanged restricted native host; preserve its actual outcome."""
    prompt = (folder / "prompt.txt").read_text()
    result = NativeHost().execute(cwd=folder / "output", prompt=prompt,
        evidence_dir=folder / "native", released_root=folder / "released",
        timeout_seconds=None)
    outcome = {"outcome": result.outcome, "error_code": result.error_code,
        "message": result.message, "thread_id": result.thread_id, "turn_id": result.turn_id}
    (folder / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
    return {"arm": folder.name, **outcome}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    prepare(Path(__file__).resolve().parents[1], root)
    if not args.prepare_only:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(execute, [root / arm for arm in ("historical", "structured")]):
                print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
