"""Private policy for the exercised Codex0.163 macOS tabular Data worker.

No task, analytical, orchestration, or alternate execution runtime logic.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time

CLI_VERSION = "0.163.0"
MODEL = "gpt-6.1-sol"
DATA_ROOT = Path("/Users/ceverson/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11")
PYTHON_ROOT = Path("/opt/anaconda3")
SKILL_SHA256 = "a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e"
DISABLED_FEATURES = ("apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use", "in_app_browser", "in_app_local_automation", "multi_agent", "memories", "view_image")
ENABLED_FEATURES = ("plugins", "code_mode_host")
FALLBACK_WARNING_PREFIX = "Warning: failed to list remote marketplace plugins:"
LOG_LIMIT = 8 * 1024 * 1024
REPORT_LIMIT = 16 * 1024 * 1024

class NativePolicyError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def require(condition, reason):
    if not condition:
        raise NativePolicyError("unsupported_integration", reason)

def check(deadline, cancellation=None):
    if cancellation is not None and cancellation.is_set():
        raise NativePolicyError("cancelled", "Parent cancelled the native operation")
    if time.monotonic() >= deadline:
        raise NativePolicyError("timeout", "Native operation exceeded its finite deadline")

def toml(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        return "{" + ",".join(toml(str(key)) + "=" + toml(item) for key, item in value.items()) + "}"
    raise TypeError("Only strings, booleans and tables are used in probe overrides")

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
            and all(flag_enabled(flags.get(name)) is True for name in ENABLED_FEATURES), "Per-process model tool feature restrictions not effective")
    require(config.get("web_search") == "disabled", "Native web search not effectively disabled")
    require(config.get("default_permissions") == profile, "Effective default native permission profile differs")
    profiles = config.get("permissions")
    require(isinstance(profiles, dict) and isinstance(profiles.get(profile), dict), "Effective native profile unavailable")
    active = profiles[profile]
    require(normalized_filesystem(active.get("filesystem")) == filesystem and isinstance(active.get("network"), dict)
            and active["network"].get("enabled") is False
            and all(value is None for name, value in active["network"].items() if name != "enabled"),
            "Effective native filesystem/network profile differs")

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

def profile_overrides(profile, released, output, configured_servers, plugin_ids, plugin):
    filesystem = {":root": "deny", ":minimal": "read", str(released.resolve()): "read",
                  str(output.resolve()): "write", str(DATA_ROOT): "read",
                  str(PYTHON_ROOT): "read"}
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
    plugins[plugin.plugin_id] = {"enabled": True}
    return ["default_permissions=" + toml(profile),
        "permissions=" + toml({profile: {"filesystem": filesystem, "network": {"enabled": False}}}),
        "features=" + toml({**{name: False for name in DISABLED_FEATURES}, **{name: True for name in ENABLED_FEATURES}}),
        'web_search="disabled"',
        "mcp_servers=" + toml({name: {"enabled": False} for name in configured_servers}),
        "plugins=" + toml(plugins)]

def disabled_mcp_row_errors(row):
    fields = {"name", "runtimeStatus", "pluginId", "httpOrigin", "serverInfo", "serverCapabilities",
              "tools", "toolsError", "resources", "resourceTemplates", "authStatus"}
    if not isinstance(row, dict): return ["row is not an object"]
    errors = []
    if set(row) != fields: errors.append("missing/unknown inventory fields: " + repr(sorted(set(row) ^ fields)))
    if not isinstance(row.get("name"), str) or not row["name"]: errors.append("server name absent")
    if row.get("runtimeStatus") != "disabled": errors.append("runtimeStatus is not explicitly disabled")
    if type(row.get("tools")) is not dict or row["tools"]: errors.append("tools are not an explicit empty object")
    for field in ("resources", "resourceTemplates"):
        if type(row.get(field)) is not list or row[field]: errors.append(field + " is not an explicit empty list")
    for field in ("serverInfo", "serverCapabilities", "toolsError"):
        if field not in row or row[field] is not None: errors.append(field + " is not explicitly null")
    for field in ("pluginId", "httpOrigin"):
        if field not in row or (row[field] is not None and not isinstance(row[field], str)):
            errors.append(field + " has an invalid metadata type")
    if row.get("authStatus") not in ("unknown", "unsupported", "notLoggedIn", "bearerToken", "oAuth"):
        errors.append("authStatus metadata is missing or unknown")
    return errors

def inventory_diagnostics(stderr):
    # rust-v0.163.0 cli/src/plugin_cmd.rs895–897 emits this exact prefix before
    # returning an empty remote listing. Keep its identity, never the error body.
    fallback = any(line.startswith(FALLBACK_WARNING_PREFIX)
        for line in stderr.decode(errors="replace").splitlines())
    return {"fallback_observed": fallback, "raw_stderr_omitted": True,
        "source_warning": FALLBACK_WARNING_PREFIX if fallback else None,
        "source": "rust-v0.163.0/codex-rs/cli/src/plugin_cmd.rs:895"}

def bounded_plugin_inventory(executable, cwd, deadline, report, plugin, cancellation=None):
    """One actual CLI inventory, with finite capture and process-group cleanup."""
    command = [str(executable), "plugin", "list", "--json"]
    started = time.monotonic()
    receipt = {"phase": "plugin_inventory", "command": command, "status": "starting",
        "limit_seconds": max(0, deadline - started), "stdout_limit_bytes": 2 * 1024 * 1024,
        "stderr_limit_bytes": 64 * 1024, "exit_code": None}
    report["plugin_inventory_command"] = receipt
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    hashes = {name: sha256() for name in buffers}
    counts = {name: 0 for name in buffers}
    process = None
    selector = selectors.DefaultSelector()
    try:
        check(deadline, cancellation)
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        receipt["status"] = "running"
        for name in buffers:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            check(deadline, cancellation)
            for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                try: chunk = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError: continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                name = key.data
                counts[name] += len(chunk)
                hashes[name].update(chunk)
                limit = receipt[name + "_limit_bytes"]
                if counts[name] > limit:
                    raise NativePolicyError("budget_exhausted", "Native plugin inventory " + name + " exceeded its byte limit")
                buffers[name].extend(chunk)
        while process.poll() is None:
            check(deadline, cancellation)
            try: process.wait(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
            except subprocess.TimeoutExpired: pass
        receipt["exit_code"] = process.returncode
        receipt["diagnostics"] = inventory_diagnostics(buffers["stderr"])
        require(process.returncode == 0, "Native installed-plugin inventory exited unsuccessfully")
        require(not receipt["diagnostics"]["fallback_observed"],
            "Native CLI used remote-marketplace fallback; complete installed inventory is not established")
        try: inventory = json.loads(buffers["stdout"])
        except (ValueError, UnicodeDecodeError) as exc:
            raise NativePolicyError("integrity_error", "Native installed-plugin inventory was not JSON") from exc
        require(isinstance(inventory, dict) and isinstance(inventory.get("installed"), list),
                "Native installed-plugin inventory has no installed list")
        installed = inventory["installed"]
        require(all(isinstance(entry, dict) and isinstance(entry.get("pluginId"), str) and entry["pluginId"]
                    for entry in installed), "Native installed-plugin inventory entry is malformed")
        selected = [entry for entry in installed if entry["pluginId"] == plugin.plugin_id]
        receipt["installed_count"] = len(installed)
        receipt["selected_data_entry_count"] = len(selected)
        receipt["data_entries"] = [{key: entry.get(key) for key in ("pluginId", "enabled", "installed", "version")}
            | {"source_id": entry["source"].get("id") if isinstance(entry.get("source"), dict) else None}
            for entry in selected]
        require(len(selected) == 1 and selected[0].get("enabled") is True and selected[0].get("installed") is True
            and selected[0].get("version") == plugin.version and isinstance(selected[0].get("source"), dict)
            and selected[0]["source"].get("source") == "remote"
            and selected[0]["source"].get("id") == plugin.remote_plugin_id,
            "Exact installed Data inventory/version unavailable")
        entry = selected[0]
        receipt["data_entry"] = {key: entry[key] for key in ("pluginId", "enabled", "installed", "version")}
        receipt["data_entry"]["source_id"] = entry["source"]["id"]
        receipt["status"] = "verified"
        return {entry["pluginId"] for entry in installed}, receipt["data_entry"]
    except BaseException as exc:
        receipt["status"] = getattr(exc, "code", "interrupted" if isinstance(exc, KeyboardInterrupt) else "runtime_error")
        raise
    finally:
        cleanup = {"term_sent": False, "kill_sent": False, "direct_child_reaped": process is None}
        if process is not None:
            for signum, field in ((signal.SIGTERM, "term_sent"), (signal.SIGKILL, "kill_sent")):
                try:
                    os.killpg(process.pid, signum)
                    cleanup[field] = True
                except ProcessLookupError: pass
                except OSError as exc:
                    cleanup[field + "_error_errno"] = exc.errno
                try: process.wait(timeout=0.5)
                except subprocess.TimeoutExpired: pass
            cleanup["direct_child_reaped"] = process.poll() is not None
            receipt["exit_code"] = process.returncode
            for name in buffers:
                getattr(process, name).close()
        selector.close()
        receipt["cleanup"] = cleanup
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        for name in buffers:
            receipt[name + "_observed_bytes"] = counts[name]
            receipt[name + "_observed_sha256"] = hashes[name].hexdigest()
        # Plugin diagnostics may contain account details: retain measurements only.
        receipt["stderr_content_omitted"] = counts["stderr"] > 0
        receipt["diagnostics"] = inventory_diagnostics(buffers["stderr"])
        if not cleanup["direct_child_reaped"] or any(key.endswith("_error_errno") for key in cleanup):
            receipt["status_before_cleanup_failure"] = receipt["status"]
            receipt["status"] = "runtime_error"
            raise NativePolicyError("runtime_error", "Native plugin inventory process-group cleanup could not be completed within its limits")


def validate_roots(released, output, evidence):
    roots = [Path(value).absolute() for value in (released, output, evidence)]
    for path in roots:
        require(not any(parent.is_symlink() for parent in (path, *path.parents)),
                "Native stage roots cannot traverse symlinks")
    release, work, audit = roots
    require(release.is_dir() and work.is_dir(), "Native released/output directories must exist")
    require(release.parent == work.parent == audit.parent,
            "Native released/output/evidence directories must be physical siblings")
    require(len(set(roots)) == 3 and all(not a.is_relative_to(b) for a in roots for b in roots if a != b),
            "Native stage roots overlap")
    require(not audit.exists() or audit.is_dir(), "Native evidence root is not a directory")
    require(not audit.exists() or not any(audit.iterdir()), "Native evidence directory must be fresh and empty")
    for root in (release, work):
        count = 0
        for directory, children, files in os.walk(root, followlinks=False):
            for name in children + files:
                count += 1
                require(count <= 1024, "Native stage namespace metadata limit exceeded")
                candidate = Path(directory) / name
                require(not candidate.is_symlink(), "Native stage namespace contains a symlink")
                require(candidate.is_dir() or candidate.is_file(), "Native stage namespace contains a special file")
    return release.resolve(strict=True), work.resolve(strict=True), audit.resolve()


def validate_supported_plugin(plugin):
    require(plugin.plugin_id == "data-analytics@openai-curated-remote"
        and plugin.remote_plugin_id == "Plugin_fc9843a6fb34819195d6c7802398a8a7"
        and plugin.version == "1.0.11" and plugin.skill_name == "index"
        and plugin.skill_sha256 == SKILL_SHA256,
        "Customer native Data identity/hash differs from the exercised specification")
    require(sys.platform == "darwin" and DATA_ROOT.is_dir() and PYTHON_ROOT.is_dir(),
        "Exercised native runtime requires macOS and the pinned Data/Python resource roots")


def verify_host(host):
    require(host.get("platformOs") == "macos" and host.get("platformFamily") == "unix"
        and isinstance(host.get("userAgent"), str)
        and re.search(r"/0\.163\.0(?:\s|$)", host["userAgent"]),
        "Native CLI/platform differs from exercised Codex0.163 macOS host")


def verify_restrictions(config, profile, filesystem, servers, plugin_ids, plugin):
    verify_effective_config(config, profile, filesystem)
    actual_servers = config.get("mcp_servers", {})
    require(set(servers) <= set(actual_servers) and all(row.get("enabled") is False
        for row in actual_servers.values()), "Native MCP config is not explicitly disabled")
    actual_plugins = config.get("plugins", {})
    required = set(plugin_ids) | {"_default", plugin.plugin_id}
    require(required <= set(actual_plugins) and all(row.get("enabled") is (name == plugin.plugin_id)
        for name, row in actual_plugins.items()), "Native plugin config is not restricted to pinned Data")


def disabled_inventory(rpc, thread_id, deadline, cancellation, receipt):
    receipt.update(pages=[], validated_disabled_only=False)
    cursor, seen, server_names = None, set(), set()
    for _ in range(50):
        params = {"threadId": thread_id, "limit": 100, "detail": "full"}
        if cursor is not None:
            params["cursor"] = cursor
        page = rpc.request("mcpServerStatus/list", params, deadline, cancellation)
        rows = page.get("data")
        require(isinstance(rows, list) and len(rows) <= 100, "Native MCP inventory page malformed")
        errors = [error for row in rows for error in disabled_mcp_row_errors(row)]
        # No raw active tool descriptions, endpoint URLs or credentials retained.
        receipt["pages"].append({"rows": [{"name": row.get("name"), "runtimeStatus": row.get("runtimeStatus"),
            "disabled_and_empty": not disabled_mcp_row_errors(row)} if isinstance(row, dict)
            else {"malformed_row": True} for row in rows], "next_cursor_present": "nextCursor" in page,
            "complete": "nextCursor" in page and page["nextCursor"] is None})
        require(not errors, "Native MCP inventory is not completely disabled and empty")
        require("nextCursor" in page, "Native MCP inventory terminal cursor is missing")
        names = [row["name"] for row in rows]
        require(len(set(names)) == len(names) and not server_names.intersection(names),
                "Native MCP inventory contains duplicate server names")
        server_names.update(names)
        cursor = page["nextCursor"]
        if cursor is None:
            receipt["validated_disabled_only"] = True
            return
        require(isinstance(cursor, str) and cursor and cursor not in seen,
                "Native MCP inventory pagination incomplete")
        seen.add(cursor)
    raise NativePolicyError("budget_exhausted", "Native MCP inventory pagination limit exhausted")


def sanitize(value):
    if isinstance(value, dict):
        if value.get("method") == "item/commandExecution/outputDelta":
            params = value.get("params")
            identity = {key: params[key] for key in ("threadId", "turnId", "itemId")
                if isinstance(params, dict) and isinstance(params.get(key), str)}
            payload = {key: item for key, item in params.items() if key not in identity} if isinstance(params, dict) else params
            encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
            return {"method": value["method"], "params": {**identity, "output_payload_omitted": True,
                "payload_canonical_json_bytes": len(encoded), "payload_canonical_json_sha256": sha256(encoded).hexdigest()}}
        if str(value.get("method", "")).startswith("item/reasoning/"):
            return {"method": value["method"], "content_omitted": True}
        if value.get("type") == "reasoning":
            return {"type": "reasoning", "id": value.get("id"), "content_omitted": True}
        value = dict(value)
        if "config" in value:
            value["config"] = config_projection(value["config"])
        if isinstance(value.get("contents"), str):
            content = value.pop("contents").encode()
            value.update(contents_omitted=True, contents_bytes=len(content), contents_sha256=sha256(content).hexdigest())
        command = value.get("command")
        if value.get("type") == "commandExecution" and any(name in str(command)
                for name in ("SKILL.md", "shared-skill-instructions.md")):
            output = value.pop("aggregatedOutput", None)
            if isinstance(output, str):
                value.update(resource_output_omitted=True, resource_output_bytes=len(output.encode()),
                    resource_output_sha256=sha256(output.encode()).hexdigest())
        return {key: ("[REDACTED]" if re.search(r"token|secret|password|authorization|api.?key|cookie", key, re.I)
            else sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", value)
        return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
    return value


def config_projection(config):
    config = config if isinstance(config, dict) else {}
    features = config.get("features") if isinstance(config.get("features"), dict) else {}
    return {"config_projection_only": True,
        "mcp_server_names": sorted(config["mcp_servers"]) if isinstance(config.get("mcp_servers"), dict) else None,
        "plugin_ids": sorted(config["plugins"]) if isinstance(config.get("plugins"), dict) else None,
        "default_permissions": config.get("default_permissions"), "web_search": config.get("web_search"),
        "feature_flags": {key: flag_enabled(features.get(key)) for key in (*DISABLED_FEATURES, *ENABLED_FEATURES)}}


def project_message(message):
    if isinstance(message, dict) and str(message.get("method", "")).startswith("item/reasoning/"):
        return {"method": message["method"], "content_omitted": True}
    if isinstance(message, dict) and isinstance(message.get("result"), dict):
        result = message["result"]
        if "config" in result:
            message = {"id": message.get("id"), "result": config_projection(result["config"])}
        elif isinstance(result.get("data"), list) and any(isinstance(row, dict)
                and "runtimeStatus" in row for row in result["data"]):
            message = {"id": message.get("id"), "result": {"data": [{"name": row.get("name"),
                "runtimeStatus": row.get("runtimeStatus"), "disabled_and_empty": not disabled_mcp_row_errors(row)}
                if isinstance(row, dict) else {"malformed_row": True} for row in result["data"]],
                "nextCursor": result.get("nextCursor")}}
    return sanitize(message)
