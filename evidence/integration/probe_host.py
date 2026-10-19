"""Bounded initialize/skills-list diagnostic; never starts a model turn.

Inspect host initialization and the available skill catalog under a bounded
timeout, retaining diagnostic results for integration troubleshooting.

Investigate whether the observed host supports the required integration,
retaining unresolved capability evidence without claiming analytical execution.

Linear: https://linear.app/gr3enarr0w/issue/DSC-26
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-home", type=Path)
    parser.add_argument("--plugins", action="store_true",
                        help="Also inspect the native CLI plugin catalog; does not install plugins.")
    args = parser.parse_args()
    executable = shutil.which("codex")
    if not executable:
        print("Codex CLI was not found on this Terminal's PATH.")
        return 2
    cwd = Path(__file__).resolve().parents[2]
    output_dir = Path(tempfile.mkdtemp(prefix="dsc26-host-check-"))
    command = [executable, "app-server", "--listen", "stdio://"]
    if args.sqlite_home:
        state = args.sqlite_home.resolve()
        state.mkdir(parents=True, exist_ok=True)
        command.extend(["-c", "sqlite_home=" + json.dumps(str(state))])
    report = {
        "record_kind": "engineering_host_diagnostic_not_stage_result",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cwd": str(cwd), "command": command,
        "customer_analysis": False, "model_turn_started": False,
        "handshake_completed": False, "skill_discovery_completed": False,
        "deadline_expired": False, "records": [],
    }
    if args.plugins:
        inventory_command = [executable, "plugin", "list", "--available", "--json"]
        inventory = {"command": inventory_command, "data_entries": []}
        try:
            result = subprocess.run(inventory_command, cwd=cwd, capture_output=True,
                                    text=True, timeout=25)
            inventory.update({"exit_code": result.returncode, "stderr": result.stderr})
            try:
                catalog = json.loads(result.stdout)
                inventory["native_result"] = catalog
                for category in ("installed", "available"):
                    for entry in catalog.get(category, []):
                        if entry.get("name") == "data-analytics":
                            inventory["data_entries"].append({"category": category, **entry})
            except (ValueError, AttributeError):
                inventory["unparsed_stdout"] = result.stdout
        except subprocess.TimeoutExpired:
            inventory["deadline_expired"] = True
        report["plugin_inventory"] = inventory
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selector = selectors.DefaultSelector()
    buffers = {"stdout": b"", "stderr": b""}
    for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
        selector.register(stream, selectors.EVENT_READ, name)

    def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()
        report["records"].append({"direction": "request", "message": message})

    def consume(name, line):
        message = line.decode(errors="replace")
        if name == "stdout":
            try:
                message = json.loads(message)
            except ValueError:
                pass
        report["records"].append({"direction": name, "message": message})
        if not isinstance(message, dict) or name != "stdout":
            return
        if message.get("id") == 1 and "result" in message:
            report["handshake_completed"] = True
            send({"method": "initialized", "params": {}})
            send({"id": 2, "method": "skills/list",
                  "params": {"cwds": [str(cwd)], "forceReload": True}})
        if message.get("id") == 2 and "result" in message:
            report["skill_discovery_completed"] = True

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {
            "name": "dsc26_engineering_probe", "title": "DSC-26 host diagnostic",
            "version": "0.1.0"}}})
        deadline = time.monotonic() + 20
        while selector.get_map() and not report["skill_discovery_completed"]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                report["deadline_expired"] = True
                break
            for key, _ in selector.select(min(0.25, remaining)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.data] += chunk
                while b"\n" in buffers[key.data]:
                    line, buffers[key.data] = buffers[key.data].split(b"\n", 1)
                    consume(key.data, line)
    except (OSError, BrokenPipeError) as exc:
        report["harness_error"] = str(exc)
    finally:
        for name, tail in buffers.items():
            if tail:
                report["records"].append({"direction": name, "message": tail.decode(errors="replace")})
        report["exit_before_cleanup"] = process.poll()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        report["exit_after_cleanup"] = process.returncode
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
    report_path = output_dir / "host-check.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    skills = []
    for record in report["records"]:
        message = record["message"]
        if record["direction"] == "stdout" and isinstance(message, dict) and message.get("id") == 2:
            for group in message.get("result", {}).get("data", []):
                for skill in group.get("skills", []):
                    if ("data-analytics" in skill.get("path", "")
                            or skill.get("name", "").startswith("data-analytics:")
                            or "data-analytics" in (skill.get("pluginId") or "")):
                        skills.append({k: skill.get(k) for k in ("name", "path", "enabled", "pluginId")})
    summary = {key: report[key] for key in ("handshake_completed", "skill_discovery_completed", "deadline_expired")}
    summary.update({"data_skills_observed": skills, "report": str(report_path),
                    "startup_stderr": [r["message"] for r in report["records"] if r["direction"] == "stderr"]})
    if args.plugins:
        summary["data_plugin_inventory"] = {k: v for k, v in report["plugin_inventory"].items()
                                            if k != "native_result"}
    print(json.dumps(summary, indent=2))
    return 0 if report["skill_discovery_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
