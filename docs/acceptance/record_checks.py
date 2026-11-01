#!/usr/bin/env python3
"""Record fixed DSC-56 mock engineering checks; never grant final acceptance."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NOTICE = ("Blocked: actual DSC-31 real-run artifacts and recording, plus current "
          "DSC-24 contract and DSC-10 guardrail evidence, must be reviewed manually. "
          "Mock engineering checks cannot establish successful restocking acceptance.")


def fingerprint():
    files = {}
    # Acceptance seams import existing component helpers and shared examples.
    # Bind their bytes too: test-only provenance changes invalidate evidence.
    for area in ("src", "tests", "examples/contracts/v0.1.0", "docs"):
        for path in sorted((ROOT / area).rglob("*")):
            if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_symlink():
                raise ValueError(f"Source binding cannot follow symlink: {path}")
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"algorithm": "sha256", "source_fingerprint": digest, "files": files}


def run(command):
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def test_key(node):
    parts = node.split("::")
    return (".".join([parts[0][:-3].replace("/", ".")] + parts[1:-1]), parts[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", required=True, help="Named person/agent recording these checks")
    parser.add_argument("--output", default="evidence/acceptance/check-results.json")
    parser.add_argument("--only", action="append", default=[], metavar="NODE_OR_PATH",
                        help="Repeat to recheck affected acceptance paths/node selectors only")
    args = parser.parse_args()
    if not args.reviewer.strip():
        parser.error("--reviewer must name a reviewer")
    output = Path(args.output)
    output = (ROOT / output).resolve() if not output.is_absolute() else output.resolve()
    evidence_root = (ROOT / "evidence/acceptance").resolve()
    if not evidence_root.is_relative_to(ROOT) or not output.is_relative_to(evidence_root):
        parser.error("--output must remain within evidence/acceptance/")
    report = {"format": "dsc56-engineering-checks-v1", "evidence_mode": "mock",
              "reviewer": args.reviewer.strip(), "recorded_at": datetime.now(timezone.utc).isoformat(),
              "final_audit": {"decision": "blocked", "reason": NOTICE},
              "tests": [], "reporter_errors": [], "commands": []}
    returncode = 1
    try:
        requirements = json.loads((ROOT / "docs/acceptance/requirements.json").read_text())
        ids = [ac["requirement_id"] for issue in requirements["issues"] for ac in issue["criteria"]]
        if len(ids) != 58 or len(set(ids)) != 58:
            raise ValueError("Expected the fixed 58 unique acceptance criteria; review a changed requirement set")
        report["requirement_count"] = len(ids)
        commit = run(["git", "rev-parse", "HEAD"])
        if commit.returncode:
            raise ValueError("Cannot bind code commit: " + commit.stderr.strip())
        report["code_commit"] = commit.stdout.strip()
        report["versions"] = {"python": sys.version, "pytest": importlib.metadata.version("pytest"),
                              "jsonschema": importlib.metadata.version("jsonschema")}
        report["source_bindings"] = fingerprint()
        collect_command = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/acceptance"]
        report["commands"].append(collect_command)
        collected = run(collect_command)
        if collected.returncode:
            raise ValueError("Acceptance collection failed: " + collected.stdout + collected.stderr)
        nodes = [line.strip() for line in collected.stdout.splitlines()
                 if line.startswith("tests/acceptance/") and "::" in line]
        if not nodes or len(nodes) != len(set(nodes)):
            raise ValueError("Acceptance inventory is empty or contains duplicate node IDs")
        selected = set(nodes) if not args.only else set()
        for selector in args.only:
            if selector.startswith("-") or "\\" in selector:
                raise ValueError("Invalid acceptance selector: " + selector)
            path = selector.split("::", 1)[0].rstrip("/")
            resolved = (ROOT / path).resolve()
            if not resolved.is_relative_to((ROOT / "tests/acceptance").resolve()):
                raise ValueError("Selector must remain within tests/acceptance: " + selector)
            matches = {node for node in nodes if node == selector or node.startswith(selector + "::")
                       or node.startswith(selector + "[")
                       or ("::" not in selector and node.split("::", 1)[0].startswith(path + "/"))}
            if not matches:
                raise ValueError("Selector matches no collected acceptance check: " + selector)
            selected.update(matches)
        outcomes = {node: {"test_id": node, "expected": "pass", "actual": "not_run",
                            "decision": "needs_evidence", "evidence_mode": "mock"} for node in nodes}
        report["tests"] = list(outcomes.values())
        with tempfile.TemporaryDirectory(prefix="dsc56-junit-") as temporary:
            junit = Path(temporary) / "results.xml"
            command = [sys.executable, "-m", "pytest", "-q", *sorted(selected), "--junitxml=" + str(junit)]
            report["commands"].append(command)
            result = run(command)
            report["pytest_exit_code"] = result.returncode
            report["pytest_output"] = result.stdout + result.stderr
            if not junit.is_file():
                raise ValueError("Pytest did not produce JUnit evidence")
            lookup = {test_key(node): node for node in selected}
            observed = set()
            for case in ET.parse(junit).iter("testcase"):
                node = lookup.get((case.get("classname"), case.get("name")))
                if node is None or node in observed:
                    raise ValueError("Unmatched or duplicate JUnit test: " + str(case.attrib))
                observed.add(node)
                failure = case.find("failure")
                error = case.find("error")
                skipped = case.find("skipped")
                actual = "fail" if failure is not None or error is not None else "blocked" if skipped is not None else "pass"
                decision = {"pass": "accepted_for_mock_check_only", "fail": "rejected", "blocked": "needs_evidence"}[actual]
                outcomes[node].update(actual=actual, decision=decision)
                detail = failure if failure is not None else error if error is not None else skipped
                if detail is not None:
                    outcomes[node]["detail"] = detail.get("message") or detail.text or detail.tag
            for node in selected - observed:
                outcomes[node].update(actual="blocked", detail="No JUnit outcome returned")
            if selected != observed:
                raise ValueError("Not every selected check returned JUnit evidence")
            if fingerprint() != report["source_bindings"]:
                raise ValueError("Source bytes changed during verification; recheck affected dependencies")
            returncode = 0 if result.returncode == 0 and all(outcomes[n]["actual"] == "pass" for n in selected) else 1
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, importlib.metadata.PackageNotFoundError) as error:
        report["reporter_errors"].append(str(error))
        for check in report["tests"]:
            if check["actual"] == "not_run" and check["test_id"] in selected:
                check.update(actual="blocked", detail="Reporter could not establish a test outcome")
    report["recorder_outcome"] = "recorded" if not report["reporter_errors"] else "blocked"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False, suffix=".tmp") as saved:
        json.dump(report, saved, indent=2, sort_keys=True)
        saved.write("\n")
    os.replace(saved.name, output)
    print(f"Recorded {len(report['tests'])} mock check outcomes: {output}")
    return returncode


if __name__ == "__main__":
    sys.exit(main())
