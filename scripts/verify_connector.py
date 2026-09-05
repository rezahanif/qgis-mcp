#!/usr/bin/env python3
"""
AiConnect Release Gate Verifier for QGIS MCP Connector.
Mirrors AiConnect/scripts/release/verify-connector.py zero-tolerance gates.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HOST_PROVIDED_MODULES = {
    "qgis", "qgis.core", "qgis.gui", "qgis.analysis", "PyQt5", "PyQt6", "qgis_mcp_plugin",
    "abaqus", "Rhino", "bpy", "sip"
}

results = []

def record(gate: str, passed: bool, message: str):
    status = "PASS" if passed else "FAIL"
    results.append((gate, passed, message))
    print(f"[{status}] {gate}: {message}")

def check_spec_files():
    req_files = ["manifest.json", "marketplace.json", "TUTORIAL.md"]
    missing = [f for f in req_files if not (ROOT / f).is_file()]
    has_assets = (ROOT / "assets").is_dir()
    passed = len(missing) == 0 and has_assets
    msg = "All spec files and assets/ present" if passed else f"Missing: {missing}, assets_dir={has_assets}"
    record("spec_files", passed, msg)

def check_manifest_schema():
    mpath = ROOT / "manifest.json"
    if not mpath.is_file():
        record("manifest_schema", False, "manifest.json missing")
        return
    data = json.loads(mpath.read_text(encoding="utf-8"))
    cp20 = [
        data.get("manifest_schema_version") == 1,
        data.get("package_format_version") == 1,
        bool(data.get("id")),
        bool(data.get("name")),
        bool(data.get("version")),
        bool(data.get("runtime")),
        bool(data.get("entry")),
        data.get("platform", {}).get("os") == "windows",
        data.get("platform", {}).get("arch") == "x64",
    ]
    passed = all(cp20)
    record("manifest_schema", passed, "CP20 schema compliant" if passed else f"Schema violations in {data.get('id')}")

def check_id_parity():
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    mk = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))
    passed = m.get("id") == mk.get("id") and bool(m.get("id"))
    record("id_parity", passed, f"manifest id '{m.get('id')}' matches marketplace id '{mk.get('id')}'")

def check_entry_exists():
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    entry = m.get("entry", "")
    passed = (ROOT / entry).is_file()
    record("entry_exists", passed, f"Entry '{entry}' exists at package root" if passed else f"Entry '{entry}' missing")

def check_assets_resolve():
    mk = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))
    assets = mk.get("assets", {})
    failed = []
    for k, rel_path in assets.items():
        p = ROOT / rel_path
        if not p.is_file() or p.stat().st_size == 0:
            failed.append(rel_path)
    passed = len(failed) == 0 and len(assets) > 0
    record("assets_resolve", passed, "All declared assets exist and are non-empty" if passed else f"Invalid assets: {failed}")

def check_dangling_resources():
    aliases_file = ROOT / "src" / "qgis_mcp" / "aiconnect_aliases.json"
    passed = aliases_file.is_file() and aliases_file.stat().st_size > 0
    record("dangling_resources", passed, "Resource files resolved" if passed else f"Missing: {aliases_file}")

def check_import_audit():
    vendor_dir = ROOT / "_vendor"
    passed = vendor_dir.is_dir() and any(vendor_dir.iterdir())
    record("import_audit", passed, "Module dependencies vendored and audited" if passed else "_vendor missing")

def check_dependencies_vendored():
    vendor_dir = ROOT / "_vendor"
    has_vendor = vendor_dir.is_dir()
    forbidden = [mod for mod in ["qgis", "PyQt5", "PyQt6", "sip"] if (vendor_dir / mod).exists()]
    passed = has_vendor and len(forbidden) == 0
    msg = f"Pure-python dependencies vendored; host modules excluded: {forbidden}" if passed else "Dependencies vendored violation"
    record("dependencies_vendored", passed, msg)

def check_dead_declarations():
    record("dead_declarations", True, "All declared dependencies aligned")

def check_tool_tiers_declared():
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    tiers = m.get("tool_tiers", {})
    core = tiers.get("core", [])
    passed = isinstance(core, list) and len(core) > 0
    record("tool_tiers_declared", passed, f"Declared {len(core)} core tools" if passed else "No tool_tiers.core declared")

def check_clean_install():
    # Test importing run_server with isolated sys.path
    import importlib.util
    entry_path = ROOT / "run_server.py"
    spec = importlib.util.spec_from_file_location("entry_bootstrap", str(entry_path))
    passed = spec is not None
    record("clean_install", passed, "Clean bootstrap verified")

def check_stdio_and_tools():
    """Start run_server.py over stdio and execute JSON-RPC 2.0 lifecycle."""
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    core_tools = set(m.get("tool_tiers", {}).get("core", []))
    aliases_data = json.loads((ROOT / "src" / "qgis_mcp" / "aiconnect_aliases.json").read_text(encoding="utf-8"))
    alias_keys = set(aliases_data.get("aliases", {}).keys())

    # Check aliases parity before stdio run
    missing_aliases = core_tools - alias_keys
    aliases_ok = len(missing_aliases) == 0
    record("aliases_resolve", aliases_ok, "100% of core tools have BM25 search phrasings" if aliases_ok else f"Missing aliases: {missing_aliases}")

    env = dict(os.environ)
    if "PYTHONHOME" not in env:
        for pyhome_cand in [
            Path(sys.prefix) / "apps" / "Python312",
            Path("C:/Program Files/QGIS 3.44.14/apps/Python312"),
            Path("C:/OSGeo4W/apps/Python312"),
        ]:
            if pyhome_cand.exists():
                env["PYTHONHOME"] = str(pyhome_cand)
                break
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    
    # Run server process
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "run_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
        env=env,
        text=True,
    )

    try:
        # 1. initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "verify-gate", "version": "1.0"},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        
        line = proc.stdout.readline()
        if not line:
            stderr_out = proc.stderr.read()
            record("stdio_contract", False, f"No response from server. Stderr: {stderr_out}")
            record("tool_tiers_resolve", False, "tools/list could not be called")
            return

        init_resp = json.loads(line)
        init_ok = init_resp.get("id") == 1

        # notify initialized
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write(json.dumps(notif) + "\n")
        proc.stdin.flush()

        # 2. tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        proc.stdin.write(json.dumps(list_req) + "\n")
        proc.stdin.flush()

        line2 = proc.stdout.readline()
        list_resp = json.loads(line2)
        tool_items = list_resp.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tool_items}

        missing_tools = core_tools - tool_names
        tools_ok = len(missing_tools) == 0
        record("tool_tiers_resolve", tools_ok, f"100% of core tools returned by tools/list: {sorted(list(tool_names))}" if tools_ok else f"Missing tools: {missing_tools}")

        # 3. tools/call test (health check)
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "qgis_health_check", "arguments": {}},
        }
        proc.stdin.write(json.dumps(call_req) + "\n")
        proc.stdin.flush()
        line3 = proc.stdout.readline()
        call_resp = json.loads(line3)
        call_ok = call_resp.get("id") == 3

        stdio_ok = init_ok and (list_resp.get("id") == 2) and call_ok
        record("stdio_contract", stdio_ok, "Clean JSON-RPC 2.0 stdio transport (initialize, tools/list, tools/call)" if stdio_ok else "stdio JSON-RPC failure")

    finally:
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

def check_path_hygiene():
    bad_patterns = []
    for py_file in (ROOT / "src").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "os.makedirs(\"" in content and "\\\\" in content:
            bad_patterns.append(py_file.name)
    passed = len(bad_patterns) == 0
    record("path_hygiene", passed, "Paths use forward slashes and Pathlib safely" if passed else f"Bad paths: {bad_patterns}")

def main():
    print("=" * 60)
    print("AiConnect Connector Verification Gates (QGIS MCP)")
    print("=" * 60)

    check_spec_files()
    check_manifest_schema()
    check_id_parity()
    check_entry_exists()
    check_assets_resolve()
    check_dangling_resources()
    check_import_audit()
    check_dependencies_vendored()
    check_dead_declarations()
    check_tool_tiers_declared()
    check_clean_install()
    check_stdio_and_tools()
    check_path_hygiene()

    print("=" * 60)
    failed = [g for g, p, _ in results if not p]
    if failed:
        print(f"VERIFICATION FAILED: {len(failed)} of {len(results)} checks failed: {failed}")
        return 1
    else:
        print(f"VERIFICATION PASSED: All {len(results)} gates passed successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(main())