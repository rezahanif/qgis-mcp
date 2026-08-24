# Changelog

## 1.0.0 (2026-08-24)

### Fixed
- Converted 405 `= Field(...)` to `Annotated[...]` pattern (Fix 124 failing tests → 9)
- Fixed stale `src/` path in test_plugin_structure.py (7/7 tests pass)
- Added 9 Literal enums for fixed-value params (geometry_type, format, style_type, etc.)
- Created typed error module (PluginError, ConnectionError, LayerNotFoundError, etc.)
- Registered `get_error_hints` tool for agent self-healing

### Changed
- GPL-2.0 license confirmed clear (LICENSE_PERMISSION.md exists)
