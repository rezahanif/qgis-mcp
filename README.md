# QGIS MCP Connector

Adaptation of [qgis-mcp](https://github.com/rezahanif/qgis-mcp) (commit
`d513500`, v0.11.0) into an AiConnect connector.

**License: GPL-2.0** (see `LICENSE` in this directory). Copyleft applies to
this connector package and any modification/redistribution of it; it runs as
a SEPARATE process spawned by the Process Manager (never linked into the
gateway), so the GPL boundary is the connector package itself. The AiConnect
gateway/SDK are not affected by this license. Full distribution reasoning —
process isolation, socket-aggregation argument, public-source position, and
the entitlement-gate caveat — is recorded in `LICENSE_PERMISSION.md`.

## Architecture (as upstream built it)

```
MCP client (agent)
    ↓  stdio (FastMCP, Python ≥3.12)
QGIS MCP server  (src/qgis_mcp/server.py — 118 tools, granular + compound modes)
    ↓  TCP socket, length-prefixed JSON (4-byte BE length header), port 9876, shared-secret token
QGIS plugin     (qgis_mcp_plugin/ — PyQGIS handlers: project/layers/features/
                 processing/canvas/style/layout/connections/system)
    ↓
QGIS API (in-process PyQGIS)
```

Two transports, deliberately distinct:
- **MCP transport**: stdio (env `QGIS_MCP_TRANSPORT`, default `stdio`).
- **QGIS communication transport**: TCP length-prefixed JSON to the in-process
  plugin — the plugin is a HOST_PLUGIN (same family as Revit's add-in, but
  Python/PyQGIS and a framed socket protocol instead of Node + raw JSON-RPC).

## AiConnect adaptation

- `manifest.json` — `stdio: true` (runs behind the generic `mcp-stdio-bridge`)
  + `host_plugin` block (qgis-plugin; install target is a QGIS profile dir,
  not a version dir — version detection stays Revit-specific per plan §7).
- `aioconnect.py` — adapter (integration layer, upstream untouched except one
  startup call in `server.py::main`): license gate (startup + per-call) via
  `mcp_license_sdk`, central response-envelope wrap of registered tools.

## Validation status

**PRE-RUNTIME COMPLETE** (2026-08-12): gateway launch/health/round-trip via
fixture; adapter unit checks; real QGIS runtime validation BLOCKED (no QGIS
available). See the phase report in the vault for the exact split.
