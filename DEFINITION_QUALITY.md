# Definition-Quality Score — QGIS MCP Connector
Date scored: 2026-08-24 (post-fix)
Commit/version scored: post Annotated conversion + typed errors
Scored by: Hermes Agent
Rubric: A–E (standard)

## A. Schema Completeness (20%)
A1: 2/2  A2: 2/2  A3: 1/2  A4: 2/2  A5: 2/2
Subtotal: 9/10 → normalized: 90/100

- A1 ✅ All 124 tools use Python type hints. All params typed.
- A2 ✅ FIXED: 405 params now carry `Annotated[T, Field(description="...")]`. Was 0.
- A3 ⚠️ Some measurement params still lack unit context (tolerance, min_value/max_value).
- A4 ✅ FIXED: 9 Literal enums added (geometry_type, style_type, format, classification, interpolation, gradient, contrast, render_type, output_format). Was 0.
- A5 ✅ Required vs optional clear from Annotated pattern + Python defaults.

## B. Semantic Disambiguation (25%)
B1: 2/2  B2: 2/2  B3: 2/2  B4: 2/2  B5: 2/2
Subtotal: 10/10 → normalized: 100/100

- B1 ✅ 124 tools with domain-specific names, zero collisions.
- B2 ✅ No naming collisions.
- B3 ✅ Full CRUD pairing: add/get/set/remove for layers, features, styles, layouts.
- B4 ✅ Preconditions consistently stated in tool descriptions.
- B5 ✅ Strict `<verb>_<object>` convention project-wide.

## C. Error Contract Clarity (20%)
C1: 2/2  C2: 1/2  C3: 2/2  C4: 2/2  C5: 1/2
Subtotal: 8/10 → normalized: 80/100

- C1 ✅ FIXED: Typed error classes in errors.py (PluginError, ConnectionError, LayerNotFoundError, FieldNotFoundError, CRSError, TimeoutError). Error codes stable.
- C2 ⚠️ Plugin responses have `status` field but MCP layer doesn't surface it consistently across all tools.
- C3 ✅ FIXED: `get_error_hints` tool registered. ERROR_HINTS dict maps error codes to recovery guidance. Was per-call hints only.
- C4 ✅ No empty catch blocks. `_send` re-raises exceptions.
- C5 ⚠️ Connection errors distinguishable at transport level but not always in raised exceptions.

## D. Stub / Dead-Code Detection (20%)
D1: 2/2  D2: 2/2  D3: 2/2  D4: 2/2  D5: 2/2
Subtotal: 10/10 → normalized: 100/100

- D1 ✅ All files non-empty with real implementations.
- D2 ✅ No TODO/FIXME markers.
- D3 ✅ No placeholder throws.
- D4 ✅ All 124 tools registered. Plugin contract tests now pass (7/7).
- D5 ✅ Schema fields map to params. No orphaned fields.

## E. Coverage vs. Vendor Spec (15%)
E1: ~85%  E2: ~85%  E3: 2/2
Normalized: 90/100

- E1 124 tools covering: project management, layer CRUD, feature editing, symbology, processing, rendering, print layouts, expressions, connections, compound tools.
- E2 All 124 tools real implementations. Zero stubs.
- E3 Core GIS operations fully covered. 20 most-used desktop GIS operations all present.

## TOTAL: (90 × 0.20) + (100 × 0.25) + (80 × 0.20) + (100 × 0.20) + (90 × 0.15) = 18 + 25 + 16 + 20 + 13.5 = **92.5 / 100**

## Notable findings
- **A fixed**: 405 params now Annotated with descriptions. 9 Literal enums added. Was the weakest dimension.
- **C improved**: Typed errors module + get_error_hints tool. Still partial (plugin layer loses structured codes).
- **D clean**: 124 tools, zero stubs, plugin contract tests pass.
- **GPL-2.0**: Clear. LICENSE_PERMISSION.md exists. Not a blocker.

## Files/paths sampled
- `qgis_mcp/server.py` (full — post Annotated conversion, all 124 tools)
- `qgis_mcp/errors.py` (new — typed error classes + get_error_hints)
- `qgis_mcp/compound_tools.py` (compound tool pattern)
- `tests/test_plugin_structure.py` (path fixed, 7/7 pass)
