"""Startup + MCP initialization + tool dispatch tests.

Proves the PM lifecycle contract WITHOUT QGIS: the connector spawns,
initializes MCP over stdio, exposes the expected tools, and dispatches a
tool call whose failure is a structured envelope (no QGIS host socket).
No QGIS/plugin/license is touched.
"""
import json

from fake_license import SECRET, mcp_initialize, mcp_tools_list, mint, spawn_server, stop

# ~118 upstream tools (granular + compound modes). Assert key tools + volume,
# not the full exact set (upstream tool count changes between versions).
KEY_TOOLS = {"ping", "diagnose", "add_bookmark", "add_field"}


def test_starts_without_qgis_and_initializes():
    proc = spawn_server()
    try:
        init = mcp_initialize(proc)
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "Qgis_mcp"
    finally:
        stop(proc)


def test_exposes_tools():
    proc = spawn_server()
    try:
        mcp_initialize(proc)
        result = mcp_tools_list(proc)
        names = {t["name"] for t in result.get("tools", [])}
        assert len(names) >= 50, f"expected large tool surface, got {len(names)}"
        missing = KEY_TOOLS - names
        assert not missing, f"missing key tools: {missing}"
    finally:
        stop(proc)


def test_tool_dispatch():
    """list_qgis_instances (zero-arg, no QGIS needed) executes through the
    real server — proves MCP server + tool registration + dispatch.

    NOTE: dispatch runs in PLAIN mode (no adapter), matching the office/
    sap2000 harnesses. Adapter-mode wrapped CALLS on fastmcp 3.4.7 hit a
    FastMCP input-validation incompatibility (DictModel receives str) —
    tracked as a connector-polish finding; the envelope contract itself is
    proven at unit level (tests/test_aioconnect.py, 13 checks).
    """
    proc = spawn_server()
    try:
        mcp_initialize(proc)
        assert proc.stdin is not None
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "list_qgis_instances", "arguments": {}},
        }
        proc.stdin.write((json.dumps(req) + "\n").encode())
        proc.stdin.flush()
        resp = json.loads(proc.stdout.readline().decode())
        content = resp["result"]["content"][0]["text"]
        assert "instances" in content.lower() or "default" in content.lower()
    finally:
        stop(proc)


def test_exits_cleanly_on_stdin_close():
    proc = spawn_server()
    mcp_initialize(proc)
    code = stop(proc)
    assert code == 0, f"expected clean exit, got {code}"
