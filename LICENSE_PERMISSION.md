# License Permission & Distribution Record — QGIS MCP Connector

## Decision

Distribution of the AiConnect QGIS connector (fork of `qgis-mcp`, upstream
v0.11.0, GPL-2.0) is **PERMITTED** under the following terms and reasoning,
by owner decision (Reza, 2026-08-23). This document records the legal
reasoning so it survives beyond verbal justification.

## 1. License identity

- Upstream: GPL-2.0-or-later (LICENSE preserved verbatim at ./LICENSE).
- This connector package (fork + AiConnect adapter layer) is therefore
  distributed under **GPL-2.0-or-later**, same as upstream.
- The adapter (`aioconnect.py`, `manifest.json`, Layer B modules) is
  derivative work of a GPL program's connector surface and is released
  under the same GPL — no permissive relicensing is claimed.

## 2. Why this does NOT infect the proprietary AiConnect core

**Process-isolation / arm's-length argument (FSF-consistent):**

1. The connector runs as a **separate OS process** with its own PID,
   spawned by the Process Manager via `tokio::process::Command`.
2. Communication with the gateway is **generic IPC**: MCP JSON-RPC over
   stdio pipes, and length-prefixed JSON over a localhost TCP socket to the
   in-QGIS plugin. No memory linking, no shared objects, no .so/.dll
   coupling.
3. The FSF's own guidance (GPL FAQ, "GP-Linking" / aggregate vs derivative)
   holds that communicating with a program over pipes/sockets does not make
   the parent a derivative work. Mere aggregation is not derivation.
4. Therefore: gateway, desktop app, cloud services, entitlement engine, and
   every other connector remain proprietary/closed-source, untouched by the
   GPL.

## 3. The socket-aggregation argument (specific to QGIS)

QGIS MCP is structurally TWO programs:

```
qgis_mcp server (Python, GPL)          ← the MCP tool surface
        ↕ TCP :9876, framed JSON, shared-secret token
qgis_mcp_plugin (PyQGIS, inside QGIS)  ← executes against QGIS API
```

The plugin half only ever runs **inside the user's own QGIS installation**
(installed to their QGIS profile directory). The AiConnect-distributed
artifact ships the Python server half; the plugin is installed into an
existing open-source host application the user already possesses. Aggregating
a GPL server that talks to a GPL plugin inside the user's GPL desktop app is
the weakest possible copyleft claim against any proprietary surrounding code.

## 4. Owner's own open-sourcing removes the practical dispute

The entire fork is **publicly developed at github.com/rezahanif/qgis-mcp**
under GPL-2.0. Every modification made by AiConnect (adapter, Layer B tools,
tests, docs) is already published under the same license.

Consequences:

- There is no hidden proprietary code inside the connector package to
  "leak" via copyleft.
- Anyone can rebuild the package from source; nothing is concealed.
- A copyleft violation claim would have no damaged party: the license's
  purpose (source availability for the connector) is satisfied by default.
- The only theoretically exposed surface would be claims about the *gateway*
  being derivative — rebutted by §2's process isolation.

## 5. Caveat — the entitlement gate

One integration detail deserves its own note:

`aioconnect.py` implements the AiConnect **license gate** (HS256
`MCP_LICENSE_TOKEN` validation at startup + per-call) and the response
**envelope wrap**. These run INSIDE the GPL'd process.

Implications:

- Because they ship inside a GPL process, their source is public (it is —
  see §4) and any recipient may reuse them under GPL terms.
- The gate must never be presented as DRM restricting the *upstream* code:
  upstream functionality remains fully usable standalone
  (`python -m qgis_mcp.server`, no token needed — the adapter is a no-op
  without `AICONNECT_ENABLE=1`). It gates only the AiConnect-managed spawn
  path, which is AiConnect's own service boundary.
- If a stricter reading were ever forced ("the gate makes the whole
  connector non-free"), the fallback is trivial and documented: strip
  `aioconnect.py` from the distributed archive; upstream behaviour is
  unchanged and the gateway spawns the plain upstream entry point instead.
  This fallback has been verified — the connector runs identically without
  the adapter (standalone mode).

## 6. Summary table

| Question | Answer |
|---|---|
| Can we distribute the QGIS connector? | **Yes** — under GPL-2.0-or-later, source-public |
| Does it force AiConnect core open? | **No** — separate process, generic IPC, FSF aggregate-vs-derivative position |
| Is the connector's source available? | **Yes, always** — public development repo, same license |
| Does the entitlement gate restrict upstream use? | **No** — standalone mode is untouched; gate applies only to managed spawns |
| Fallback if challenged? | Strip adapter from archive; ship pure upstream entry point (verified working) |

## 7. Related records

- Same reasoning family: ltspice-mcp (GPL-3.0, process isolation) —
  recorded in that repo's README.
- OfficeMCP permission record: `OfficeMCP/LICENSE_PERMISSION.md`
  (different situation — no-license-upstream, permitted by owner decision).
