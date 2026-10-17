"""Engineering-only native permission-profile probe; never enables customer dispatch.

Uses experimental named-profile selection in installed Codex, not a new runtime.
Deterministic controls run first; at most one 90-second synthetic Data turn follows.
Scope is a tabular worker with native view_image, browser, apps and connectors off.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from suiroai.integration.native import DataPluginSpec, NativeHost, NativeRun, _Stop, _Transport, _matched_commands, _python_invocation, _safe

SPEC = DataPluginSpec(skill_sha256="a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e")
DATA_ROOT = Path("/Users/ceverson/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11")
def tiny_png():
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\xff")) + chunk(b"IEND", b""))

PNG = tiny_png()
DISABLED_FEATURES = ("apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use", "in_app_browser", "in_app_local_automation", "multi_agent", "code_mode_host", "memories", "view_image")


def retained_report(value):
    """Retain evidence identities, never raw reasoning or credential fields."""
    if isinstance(value, dict):
        if value.get("type") == "reasoning":
            return {"type": "reasoning", "id": value.get("id"), "content_omitted": True}
        return _safe({key: retained_report(item) for key, item in value.items()})
    if isinstance(value, list):
        return [retained_report(item) for item in value]
    return _safe(value)


def require(condition, reason):
    if not condition:
        raise _Stop("unsupported_integration", reason)


def toml(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        return "{" + ",".join(toml(str(key)) + "=" + toml(item) for key, item in value.items()) + "}"
    raise TypeError("Only strings, booleans and tables are used in probe overrides")


def filesystem_value(value):
    if isinstance(value, str) and value in ("read", "write", "deny"):
        return value
    return {"unexpected_value_type": type(value).__name__, "value_omitted": True}


def selected_profile_projection(config, profile):
    """Whitelist only this profile's permission metadata, never other config."""
    profiles = config.get("permissions")
    selected = profiles.get(profile) if isinstance(profiles, dict) else None
    if not isinstance(selected, dict):
        return {"profile": profile, "profile_shape_valid": False}
    filesystem, network = selected.get("filesystem"), selected.get("network")
    projected = {"profile": profile, "profile_shape_valid": True,
        "filesystem_shape_valid": isinstance(filesystem, dict), "network_shape_valid": isinstance(network, dict)}
    if isinstance(filesystem, dict):
        projected["filesystem"] = {key: (value if key == "glob_scan_max_depth"
            and (value is None or type(value) is int) else filesystem_value(value)) for key, value in filesystem.items()}
    if isinstance(network, dict):
        projected["network"] = {"enabled": network.get("enabled") if type(network.get("enabled")) is bool
            else {"unexpected_value_type": type(network.get("enabled")).__name__, "value_omitted": True},
            "other_present_field_names": sorted(key for key in network if key != "enabled"),
            "other_nonnull_field_names": sorted(key for key, value in network.items() if key != "enabled" and value is not None)}
    return projected


def normalized_filesystem(filesystem):
    if not isinstance(filesystem, dict): return None
    result = dict(filesystem)
    # rust-v0.163.0 config/src/permissions_toml.rs derives Serialize without
    # skip_serializing_if for Option<usize> glob_scan_max_depth; config/read
    # serializes typed ConfigToml (app-server/config_manager_service.rs137-149).
    # Only its absent/null representation is equivalent. Non-null stays unequal.
    if result.get("glob_scan_max_depth", object()) is None:
        del result["glob_scan_max_depth"]
    return result


def profile_comparison(config, profile, expected_filesystem):
    profiles = config.get("permissions")
    selected = profiles.get(profile) if isinstance(profiles, dict) else None
    selected = selected if isinstance(selected, dict) else {}
    observed = selected_profile_projection(config, profile)
    raw_filesystem = selected.get("filesystem")
    filesystem = normalized_filesystem(raw_filesystem)
    network = selected.get("network")
    keys = set(filesystem or {}) | set(expected_filesystem)
    differences = {}
    for key in sorted(keys):
        if filesystem is None or key not in filesystem:
            differences[key] = {"expected": expected_filesystem.get(key), "observed": "[MISSING]"}
        elif key not in expected_filesystem:
            differences[key] = {"expected": "[ABSENT]", "observed": observed.get("filesystem", {}).get(key)}
        elif filesystem[key] != expected_filesystem[key]:
            differences[key] = {"expected": expected_filesystem[key], "observed": observed.get("filesystem", {}).get(key)}
    return {"expected": {"filesystem": expected_filesystem, "network": {"enabled": False}},
        "observed": observed, "filesystem_differences": differences,
        "normalization": ["glob_scan_max_depth:null equivalent to absent"] if isinstance(raw_filesystem, dict)
            and "glob_scan_max_depth" in raw_filesystem and raw_filesystem["glob_scan_max_depth"] is None else [],
        "filesystem_matches": filesystem == expected_filesystem,
        "network_matches": isinstance(network, dict) and network.get("enabled") is False}


class ProjectedTransport(_Transport):
    def __init__(self, *args, selected_profile=None, **kwargs):
        self.selected_profile = selected_profile
        super().__init__(*args, **kwargs)

    def record(self, direction, message, control=False):
        # Config responses may include credentials; project BEFORE logging.
        if (isinstance(message, dict) and isinstance(message.get("result"), dict)
                and "config" in message["result"]):
            config = message["result"]["config"]
            valid = isinstance(config, dict)
            config = config if valid else {}
            features = config.get("features") if isinstance(config.get("features"), dict) else {}
            projection = {"config_projection_only": True, "config_shape_valid": valid,
                "mcp_server_names": sorted(config["mcp_servers"]) if isinstance(config.get("mcp_servers"), dict) else None,
                "plugin_config_ids": sorted(config["plugins"]) if isinstance(config.get("plugins"), dict) else None,
                "default_permissions": config.get("default_permissions") if isinstance(config.get("default_permissions"), str) else None,
                "web_search": config.get("web_search") if isinstance(config.get("web_search"), str) else None,
                "feature_flags": {name: flag_enabled(features.get(name)) for name in (*DISABLED_FEATURES, "plugins")}}
            if getattr(self, "selected_profile", None) is not None:
                projection["selected_profile"] = selected_profile_projection(config, self.selected_profile)
            message = {"id": message.get("id"), "result": projection}
        elif (isinstance(message, dict) and isinstance(message.get("result"), dict)
                and isinstance(message["result"].get("contents"), str)):
            contents = message["result"]["contents"]
            message = {"id": message.get("id"), "result": {"contents_omitted": True,
                "contents_bytes": len(contents.encode()), "contents_sha256": sha256(contents.encode()).hexdigest()}}
        super().record(direction, retained_report(message), control=control)


def initialize(rpc, deadline):
    result = rpc.request("initialize", {"clientInfo": {"name": "dsc26_native_isolation_probe", "version": "0.1.0"},
        "capabilities": {"experimentalApi": True}}, deadline)
    rpc.send({"method": "initialized", "params": {}})
    return result


def flag_enabled(value):
    if isinstance(value, bool): return value
    if isinstance(value, dict) and isinstance(value.get("enabled"), bool): return value["enabled"]
    return None


def config_maps(response):
    config = response.get("config")
    require(isinstance(config, dict), "Native effective config response is missing or malformed")
    for key in ("mcp_servers", "plugins"):
        values = config.get(key, {})
        require(isinstance(values, dict) and all(isinstance(value, dict) for value in values.values()),
                "Native effective config table malformed: " + key)
    return config


def verify_effective_config(config, profile, filesystem):
    flags = config.get("features")
    require(isinstance(flags, dict), "Effective feature flags unavailable")
    require(all(flag_enabled(flags.get(name)) is False for name in DISABLED_FEATURES)
            and flag_enabled(flags.get("plugins")) is True, "Per-process model tool feature restrictions not effective")
    require(config.get("web_search") == "disabled", "Native web search not effectively disabled")
    require(config.get("default_permissions") == profile, "Effective default native permission profile differs")
    profiles = config.get("permissions")
    require(isinstance(profiles, dict) and isinstance(profiles.get(profile), dict), "Effective native profile unavailable")
    active = profiles[profile]
    require(normalized_filesystem(active.get("filesystem")) == filesystem and isinstance(active.get("network"), dict)
            and active["network"].get("enabled") is False,
            "Effective native filesystem/network profile differs")


def profile_overrides(profile, released, output, configured_servers, plugin_ids):
    filesystem = {":root": "deny", ":minimal": "read", str(released.resolve()): "read",
                  str(output.resolve()): "write", str(DATA_ROOT): "read",
                  str(Path(sys.base_prefix).resolve()): "read"}
    # Native macOS :minimal Process profiles add scratch access even with
    # :root=deny. Explicit physical-root denies constrain those implicit grants;
    # more-specific released/output grants remain separate allowed roots.
    # rust-v0.163.0 sandboxing/seatbelt.rs899-907, seatbelt_scratch.rs35-67;
    # protocol/permissions.rs100-102,1690-1691,1763-1791.
    scratch_roots = {Path("/private/tmp"), Path("/private/var/tmp")}
    tempdir = os.environ.get("TMPDIR")
    if tempdir:
        require(Path(tempdir).is_absolute(), "Native TMPDIR must be an absolute path")
        canonical_tempdir = Path(tempdir).resolve()
        require(canonical_tempdir != Path("/"), "Native TMPDIR cannot be filesystem root")
        scratch_roots.add(canonical_tempdir)
    for scratch_root in sorted(scratch_roots):
        require(str(scratch_root) not in filesystem, "Native scratch deny collides with a required positive grant")
        filesystem[str(scratch_root)] = "deny"
    plugins = {"_default": {"enabled": False}}
    plugins.update({name: {"enabled": False} for name in plugin_ids if name != "_default"})
    plugins[SPEC.plugin_id] = {"enabled": True}
    return ["default_permissions=" + toml(profile),
        "permissions=" + toml({profile: {"filesystem": filesystem, "network": {"enabled": False}}}),
        "features=" + toml({**{name: False for name in DISABLED_FEATURES}, "plugins": True}),
        'web_search="disabled"',
        "mcp_servers=" + toml({name: {"enabled": False} for name in configured_servers}),
        "plugins=" + toml(plugins)]


def exec_params(profile, output, argv):
    return {"command": argv, "cwd": str(output), "permissionProfile": profile,
            "timeoutMs": 10000, "outputBytesCap": 16384}


def control_code(released_file, sentinel, link, output_file, outside_file, network_address):
    # Harness-authored code: the model cannot supply a fake denial result.
    return ("import csv,json,errno,socket\nfrom pathlib import Path\n"
        + "released=Path(" + repr(str(released_file)) + ")\n"
        + "rows=list(csv.DictReader(released.open()))\n"
        + "totals={}\nfor row in rows: totals[row['product']]=totals.get(row['product'],0)+int(row['units'])\n"
        + "positive={'row_count':len(rows),'group_totals':totals,'total_units':sum(totals.values())}\n"
        + "Path(" + repr(str(output_file)) + ").write_text(json.dumps(positive))\nchecks={}\n"
        + "for name,path,mode in " + repr([
            ("sentinel_open", str(sentinel), "rb"), ("symlink_open", str(link), "rb"),
            ("input_write", str(released_file), "wb"), ("outside_write", str(outside_file), "xb")]) + ":\n"
        + " try:\n  with open(path,mode) as stream:\n   if mode=='rb': stream.read(1)\n"
        + "  checks[name]={'denied':False}\n"
        + " except PermissionError as exc:\n  checks[name]={'denied':True,'type':type(exc).__name__,'errno':exc.errno}\n"
        + "try:\n with socket.create_connection(" + repr(network_address) + ",timeout=2): pass\n checks['network']={'denied':False}\n"
        + "except PermissionError as exc:\n checks['network']={'denied':True,'type':type(exc).__name__,'errno':exc.errno}\n"
        + "print(json.dumps({'positive':positive,'checks':checks}))\n"
        + "raise SystemExit(0 if all(item.get('denied') for item in checks.values()) else 7)\n")


def inventory_empty(rpc, thread_id, deadline):
    cursor, seen = None, set()
    for _ in range(20):
        params = {"threadId": thread_id, "detail": "full", "limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = rpc.request("mcpServerStatus/list", params, deadline)
        require(isinstance(page.get("data"), list), "MCP inventory response is malformed")
        # A nonempty server inventory is a scope blocker, including disabled or
        # unresolved rows. Never infer emptiness from missing/failed tool lists.
        require(not page["data"], "Thread MCP inventory is nonempty; model tool scope is not established")
        cursor = page.get("nextCursor")
        if cursor is None:
            return
        require(isinstance(cursor, str) and cursor and cursor not in seen, "MCP inventory pagination is incomplete")
        seen.add(cursor)
    raise _Stop("budget_exhausted", "MCP inventory pagination limit reached")


def retrieve(rpc, thread_id, turn_id, deadline):
    metadata = rpc.request("thread/read", {"threadId": thread_id, "includeTurns": False}, deadline)
    require((metadata.get("thread") or {}).get("id") == thread_id, "Retrieved thread identity differs")
    entries, cursor, seen = [], None, set()
    for _ in range(50):
        params = {"threadId": thread_id, "turnId": turn_id, "sortDirection": "asc", "limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = rpc.request("thread/items/list", params, deadline)
        require(isinstance(page.get("data"), list), "Native turn item page malformed")
        require(all(isinstance(entry, dict) and entry.get("turnId") == turn_id for entry in page["data"]),
                "Retrieved item turn binding differs")
        entries.extend(page["data"])
        cursor = page.get("nextCursor")
        if cursor is None:
            return entries
        require(isinstance(cursor, str) and cursor and cursor not in seen, "Item pagination is incomplete")
        seen.add(cursor)
    raise _Stop("budget_exhausted", "Item pagination limit reached")


def run_control(rpc, paths, profile, report, deadline):
    profiles = rpc.request("permissionProfile/list", {"cwd": str(paths["output"]), "limit": 100}, deadline)
    rows = [row for row in profiles.get("data", []) if row.get("id") == profile]
    require(len(rows) == 1 and rows[0].get("allowed") is True, "Native profile is absent or disallowed")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0)); listener.listen(2); listener.settimeout(2)
        address = listener.getsockname()
        with socket.create_connection(address, timeout=2):
            connection, _ = listener.accept(); connection.close()
        report["controlled_loopback_listener_positive"] = True
        code = control_code(paths["input"], paths["sentinel"], paths["link"], paths["control_result"], paths["outside_write"], address)
        report["control_code_sha256"] = sha256(code.encode()).hexdigest()
        positive = rpc.request("command/exec", exec_params(profile, paths["output"], [sys.executable, "-c", code]), deadline)
    report["native_control_response"] = positive
    try:
        require(isinstance(positive.get("stdout"), str) and len(positive["stdout"].encode()) <= 16384,
                "Native control stdout is missing or exceeds its bounded JSON receipt")
        parsed = json.loads(positive["stdout"])
    except (ValueError, KeyError) as exc:
        raise _Stop("integrity_error", "Native controls did not return inspectable JSON") from exc
    require(isinstance(parsed, dict) and isinstance(parsed.get("checks"), dict), "Native control JSON receipt is malformed")
    check_names = ("sentinel_open", "symlink_open", "input_write", "outside_write", "network")
    checks = {name: parsed["checks"].get(name) if isinstance(parsed["checks"].get(name), dict) else {} for name in check_names}
    report["native_control_checks"] = {name: {
        "denied": value.get("denied") if type(value.get("denied")) is bool else None,
        "error_type": value.get("type") if value.get("type") == "PermissionError" else None,
        "errno": value.get("errno") if type(value.get("errno")) is int else None} for name, value in checks.items()}
    report["allowed_when_denied"] = [name for name, value in checks.items() if value.get("denied") is False]
    require(positive.get("exitCode") == 0, "Deterministic native permission controls failed")
    expected = {"row_count": 3, "group_totals": {"A": 5, "B": 5}, "total_units": 10}
    require(parsed.get("positive") == expected, "Native positive input/output calculation differs")
    require(all(checks[name].get("denied") is True and checks[name].get("type") == "PermissionError"
                and checks[name].get("errno") in (1, 13) for name in check_names),
            "Actual OS read/symlink/write denial is not established")
    cat = rpc.request("command/exec", exec_params(profile, paths["output"], ["/bin/cat", str(paths["sentinel"])]), deadline)
    report["native_cat_response"] = cat
    require(cat.get("exitCode") != 0 and any(text in cat.get("stderr", "").lower()
        for text in ("permission denied", "operation not permitted")), "Native cat denial not established")
    require(paths["input"].read_bytes() == paths["input_bytes"], "Released synthetic input changed")
    require(not paths["outside_write"].exists(), "Native denied-directory write succeeded")
    require(json.loads(paths["control_result"].read_bytes()) == expected, "Fetched native control artifact differs")
    report["deterministic_native_controls_passed"] = True


def direct_argv(command):
    try:
        outer = shlex.split(command)
        if len(outer) == 3 and Path(outer[0]).name in ("sh", "bash", "zsh") and outer[1] in ("-c", "-lc"):
            command = outer[2]
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>\n")
        lexer.whitespace, lexer.whitespace_split, lexer.commenters = " \t\r", True, ""
        tokens = list(lexer)
        return tokens if tokens and not any(token in (";", "&", "&&", "|", "||", ">", ">>", "<", "\n") for token in tokens) else []
    except (TypeError, ValueError):
        return []


def reads_data_resource(command):
    tokens = direct_argv(command)
    resources = {str(DATA_ROOT / "skills/index/SKILL.md"), str(DATA_ROOT / "shared/shared-skill-instructions.md")}
    if not tokens: return False
    program = Path(tokens[0]).name
    if program == "cat": return bool(tokens[1:]) and all(token in resources for token in tokens[1:])
    if program == "sed" and len(tokens) == 4 and tokens[1] == "-n":
        import re
        return bool(re.fullmatch(r"\d+(?:,\d+)?p", tokens[2]) and tokens[3] in resources)
    return False


def expected_resource_bytes(command):
    """Expected bytes of the narrow, actual read command, not model assertions."""
    if not reads_data_resource(command): return None
    tokens = direct_argv(command)
    if Path(tokens[0]).name == "cat":
        return b"".join(Path(path).read_bytes() for path in tokens[1:])
    bounds = tokens[2][:-1].split(",")
    start, end = int(bounds[0]), int(bounds[-1])
    if start < 1 or end < start: return None
    return b"".join(Path(tokens[3]).read_bytes().splitlines(keepends=True)[start-1:end])


def protected_hashes(paths):
    result = {}
    for key in ("input", "sentinel", "allowed_image", "denied_image"):
        require(paths[key].is_file() and not paths[key].is_symlink(), "Protected synthetic source missing or replaced: " + key)
        result[key] = sha256(paths[key].read_bytes()).hexdigest()
    for key, target in (("link", "sentinel"), ("image_link", "denied_image")):
        require(paths[key].is_symlink() and paths[key].readlink() == paths[target], "Synthetic symlink changed: " + key)
        result[key] = str(paths[key].readlink())
    return result


def resource_receipts(entries, events, thread_id, turn_id):
    """Pair actual successful reads without mistaking persisted truncation for failure."""
    receipts = []
    observed = {(event.get("threadId"), event.get("turnId"), (event.get("item") or {}).get("id")):
                event.get("item") or {} for event in events}
    for entry in entries:
        item = entry.get("item") or {}
        event = observed.get((thread_id, turn_id, item.get("id")))
        if (entry.get("turnId") != turn_id or item.get("type") != "commandExecution" or not event
                or item.get("status") != "completed" or event.get("status") != "completed"
                or type(item.get("exitCode")) is not int or item["exitCode"] != 0
                or event.get("exitCode") != 0 or event.get("command") != item.get("command")
                or event.get("cwd") != item.get("cwd") or not reads_data_resource(item.get("command", ""))):
            continue
        expected = expected_resource_bytes(item["command"])
        streamed, persisted = event.get("aggregatedOutput"), item.get("aggregatedOutput")
        if not expected or not isinstance(streamed, str) or streamed.encode() != expected or not isinstance(persisted, str):
            continue
        if streamed != persisted:
            marker = "\n... command output truncated for persistence ...\n"
            if persisted.count(marker) != 1: continue
            prefix, suffix = persisted.split(marker)
            if not prefix or not suffix or not streamed.startswith(prefix) or not streamed.endswith(suffix): continue
        values = {"command_id": item["id"], "command": item["command"], "cwd": item.get("cwd"),
                  "actual_resource_bytes_verified": True, "resource_output_sha256": sha256(expected).hexdigest(),
                  "stream_and_persisted_output_equal": event.get("aggregatedOutput") == item.get("aggregatedOutput")}
        for label, value in (("stream", event.get("aggregatedOutput")), ("persisted", item.get("aggregatedOutput"))):
            values[label + "_output_sha256"] = sha256(value.encode()).hexdigest() if isinstance(value, str) else None
            values[label + "_output_bytes"] = len(value.encode()) if isinstance(value, str) else None
        receipts.append(values)
    return receipts


def run_model(rpc, paths, profile, report):
    deadline = time.monotonic() + 90
    thread = rpc.request("thread/start", {"cwd": str(paths["output"]), "runtimeWorkspaceRoots": [str(paths["output"])],
        "approvalPolicy": "never", "permissions": profile}, deadline)
    report["thread_start"] = thread
    require((thread.get("activePermissionProfile") or {}).get("id") == profile, "Native active profile acknowledgement differs")
    require(thread.get("runtimeWorkspaceRoots") == [str(paths["output"])], "Native runtime workspace roots differ")
    require(thread.get("cwd") == str(paths["output"]) and thread.get("approvalPolicy") == "never", "Native cwd/approval differs")
    require((thread.get("sandbox") or {}).get("networkAccess") is False, "Native command networking is not acknowledged off")
    thread_id = (thread.get("thread") or {}).get("id")
    require(isinstance(thread_id, str) and thread_id, "Native thread identity absent")
    report["thread_id"] = thread_id
    inventory_empty(rpc, thread_id, deadline)
    skill = rpc.request("plugin/skill/read", {"remoteMarketplaceName": "openai-curated-remote",
        "remotePluginId": SPEC.remote_plugin_id, "skillName": "index"}, deadline)
    markdown = skill.get("contents")
    require(isinstance(markdown, str) and sha256(markdown.encode()).hexdigest() == SPEC.skill_sha256, "Native Data skill version/hash differs")
    prompt = ("Use the attached native Data plugin for one synthetic engineering isolation probe. No customer task, "
        "approval or data is involved. Follow installed Data resources. Do not use network, connectors, other agents "
        "or install anything. This is a tabular worker; native image tools are disabled. Read " + str(paths["input"]) + ". Generate isolation_calculation.py "
        "to compute CSV row_count, group_totals by product, total_units. Execute exactly `python3 isolation_calculation.py` "
        "as a separate command in the current output directory, without chaining, cd, flags or other commands. Save exactly those fields "
        "in isolation_result.json in the current output directory. Derive values from the released CSV. "
        "Keep input unchanged. Do not evade restrictions, request permission or repair policy. "
        "Stop after artifact paths and actual outcomes.")
    require(paths["sentinel"].read_bytes() not in prompt.encode(), "Unreleased sentinel value leaked into model prompt")
    report["sentinel_value_absent_from_prompt"] = True
    report["model_turn_requested"] = True
    run = NativeRun(thread_id=thread_id, mode="engineering")
    try:
        started = rpc.request("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": prompt},
            {"type": "mention", "name": "Data", "path": "plugin://" + SPEC.plugin_id}]}, deadline)
        run.turn_id = (started.get("turn") or {}).get("id")
        require(isinstance(run.turn_id, str) and run.turn_id, "Native turn identity absent")
        report["turn_id"] = run.turn_id
        terminal = rpc.wait_terminal(thread_id, run.turn_id, deadline)
        run.terminal_status = terminal.get("status")
        report["terminal"] = terminal
        require(run.terminal_status == "completed" and not terminal.get("error"), "Native engineering Data turn did not complete")
        entries = retrieve(rpc, thread_id, run.turn_id, deadline)
        report["retrieved_items"] = entries
        allowed_items = {"userMessage", "agentMessage", "reasoning", "commandExecution", "fileChange", "plan"}
        observed_types = {(entry.get("item") or {}).get("type") for entry in entries}
        observed_types.update((event.get("item") or {}).get("type") for event in rpc.events
            if event.get("threadId") == thread_id and event.get("turnId") == run.turn_id)
        require(observed_types <= allowed_items, "Unexpected native tool/item outside declared tabular scope: "
                + repr(sorted(observed_types - allowed_items, key=str)))
        commands = _matched_commands(entries, rpc.events, thread_id, run.turn_id)
        require(any(item.get("exitCode") == 0 and Path(item.get("cwd", "")).resolve() == paths["output"].resolve()
            and (argv := _python_invocation(item.get("command", ""))) and len(argv) == 2
            and (paths["output"] / argv[1]).resolve() == (paths["output"] / "isolation_calculation.py").resolve()
            for item in commands), "Actual Data calculation execution not retrieved")
        report["data_resource_receipts"] = resource_receipts(entries, rpc.events, thread_id, run.turn_id)
        require(report["data_resource_receipts"], "Actual installed Data resource read not retrieved")
        result = paths["output"] / "isolation_result.json"
        code = paths["output"] / "isolation_calculation.py"
        require(result.is_file() and not result.is_symlink() and code.is_file() and not code.is_symlink(), "Data artifacts unavailable")
        require(bool(code.read_bytes().strip()), "Generated calculation code is empty")
        require(json.loads(result.read_bytes()) == {"row_count": 3, "group_totals": {"A": 5, "B": 5}, "total_units": 10},
                "Independent Data result check differs")
        require(paths["input"].read_bytes() == paths["input_bytes"], "Released input changed during Data turn")
        report["data_artifacts"] = [{"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()} for path in (result, code)]
        report["data_turn_artifacts_verified"] = True
        require(not rpc.rejected_requests, "Unexpected native server requests were rejected")
    except BaseException:
        if run.terminal_status not in ("completed", "failed", "interrupted"):
            NativeHost._interrupt(rpc, run)
            report["interrupt_evidence"] = run.evidence
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="dsc26-native-isolation-", dir="/private/tmp"))
    released, output, evidence, denied = (root / name for name in ("released", "output", "evidence", "unreleased"))
    for directory in (released, output, evidence, denied): directory.mkdir()
    paths = {"released": released, "output": output, "input": released / "synthetic.csv",
        "input_bytes": b"product,units\nA,2\nA,3\nB,5\n", "sentinel": denied / "sentinel.txt",
        "link": output / "denied-link", "control_result": output / "control-result.json",
        "outside_write": denied / "new-denied-file.txt",
        "allowed_image": released / "allowed.png", "denied_image": denied / "denied.png",
        "image_link": output / "denied-image-link"}
    paths["input"].write_bytes(paths["input_bytes"])
    paths["sentinel"].write_text(secrets.token_hex(32))
    paths["link"].symlink_to(paths["sentinel"])
    paths["allowed_image"].write_bytes(PNG); paths["denied_image"].write_bytes(PNG)
    paths["image_link"].symlink_to(paths["denied_image"])
    protected_before = protected_hashes(paths)
    profile = "dsc26-synthetic-" + secrets.token_hex(8)
    report = {"record_kind": "native_isolation_engineering_probe", "customer_analysis": False,
        "model_turn_requested": False, "manual_review_required": True, "automatic_acceptance": False,
        "customer_gate_unchanged": True, "experimental_fields": ["thread/start.permissions", "command/exec.permissionProfile",
        "thread/start.runtimeWorkspaceRoots", "thread/start.activePermissionProfile"], "profile": profile,
        "deterministic_native_controls_passed": False, "data_turn_artifacts_verified": False,
        "protected_sources_before": protected_before,
        "declared_scope": "Tabular Data worker; view_image, browser, web, apps, external MCP and other plugins disabled",
        "unexercised": ["Native image helper denial (tool disabled)", "Customer analytical execution", "Upstream quota exhaustion"],
        "status": "blocked_or_incomplete", "remaining_limits": "One Data turn <=90s; control phase <=120s; RPC <=20s"}
    deadline = time.monotonic() + 120
    try:
        executable = shutil.which("codex")
        require(executable, "Codex CLI unavailable")
        with (evidence / "bootstrap.jsonl").open("w") as log:
            rpc = ProjectedTransport(executable, output, log)
            try:
                initialize(rpc, deadline)
                config = config_maps(rpc.request("config/read", {"cwd": str(output), "includeLayers": False}, deadline))
                servers = list(config.get("mcp_servers") or {})
                configured_plugins = set(config.get("plugins") or {})
            finally: rpc.close()
        inventory = subprocess.run([executable, "plugin", "list", "--json"], cwd=output,
            capture_output=True, timeout=min(20, max(0.01, deadline - time.monotonic())), check=True)
        installed = json.loads(inventory.stdout).get("installed", [])
        selected = [entry for entry in installed if entry.get("pluginId") == SPEC.plugin_id]
        require(len(selected) == 1 and selected[0].get("enabled") is True and selected[0].get("installed") is True
            and selected[0].get("version") == SPEC.version and (selected[0].get("source") or {}).get("id") == SPEC.remote_plugin_id,
            "Exact installed Data inventory/version unavailable")
        plugin_ids = configured_plugins | {entry["pluginId"] for entry in installed}
        overrides = profile_overrides(profile, released, output, servers, plugin_ids)
        report["config_overrides"] = overrides
        with (evidence / "native-rpc.jsonl").open("w") as log:
            rpc = ProjectedTransport(executable, output, log, config_overrides=overrides, selected_profile=profile)
            try:
                report["host"] = initialize(rpc, deadline)
                effective = config_maps(rpc.request("config/read", {"cwd": str(output), "includeLayers": False}, deadline))
                expected_filesystem = tomllib.loads(overrides[1])["permissions"][profile]["filesystem"]
                report["effective_profile_comparison"] = profile_comparison(effective, profile, expected_filesystem)
                verify_effective_config(effective, profile, expected_filesystem)
                report["per_process_restrictions_acknowledged"] = True
                run_control(rpc, paths, profile, report, deadline)
                require(protected_hashes(paths) == protected_before, "Protected source changed during native controls")
                run_model(rpc, paths, profile, report)
                require(protected_hashes(paths) == protected_before, "Protected source changed during Data turn")
                report["status"] = "engineering_checks_observed_pending_manual_review"
            finally:
                report["item_completed_events"] = rpc.events
                report["rejected_server_requests"] = rpc.rejected_requests
                rpc.close()
    except (_Stop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report["blocker"] = str(exc)
        report["error_code"] = getattr(exc, "code", "runtime_error")
    except KeyboardInterrupt:
        report["blocker"] = "Operator interrupted engineering probe"
    try:
        report["protected_sources_after"] = protected_hashes(paths)
        report["protected_sources_unchanged"] = report["protected_sources_after"] == protected_before
    except _Stop as exc:
        report["protected_sources_unchanged"] = False
        report["protected_source_error"] = str(exc)
    if not report["protected_sources_unchanged"]:
        report["status"] = "blocked_or_incomplete"
        report["blocker"] = "Protected synthetic sources changed or disappeared"
    destination = evidence / "isolation-evidence.json"
    destination.write_text(json.dumps(retained_report(report), indent=2) + "\n")
    print(json.dumps({key: report.get(key) for key in ("status", "blocker", "model_turn_requested",
        "deterministic_native_controls_passed", "data_turn_artifacts_verified", "manual_review_required",
        "native_control_checks", "allowed_when_denied")}
        | ({"effective_profile_comparison": retained_report(report["effective_profile_comparison"])}
            if report.get("error_code") and "effective_profile_comparison" in report
            and not (report["effective_profile_comparison"]["filesystem_matches"]
                and report["effective_profile_comparison"]["network_matches"]) else {})
        | {"evidence": str(destination)}, indent=2))
    return 0 if report["status"] == "engineering_checks_observed_pending_manual_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
