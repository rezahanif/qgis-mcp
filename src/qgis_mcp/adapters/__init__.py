"""Adapter factory for QGIS MCP."""

from qgis_mcp.adapters.base import QgisBaseAdapter
from qgis_mcp.adapters.gui import QgisGUIAdapter
from qgis_mcp.adapters.headless import QgisHeadlessAdapter, PYQGIS_AVAILABLE
from qgis_mcp.adapters.mock import QgisMockAdapter

_cached_adapter = None

def get_adapter() -> QgisBaseAdapter:
    global _cached_adapter
    if _cached_adapter is not None:
        return _cached_adapter

    gui_adapter = QgisGUIAdapter()
    if gui_adapter.is_available():
        _cached_adapter = gui_adapter
        return _cached_adapter

    if PYQGIS_AVAILABLE:
        try:
            headless = QgisHeadlessAdapter()
            _cached_adapter = headless
            return _cached_adapter
        except Exception:
            pass

    _cached_adapter = QgisMockAdapter()
    return _cached_adapter