"""Typed error classes for QGIS MCP Server.

Provides structured error types that surface error codes to agents,
replacing bare RuntimeError with typed exceptions carrying hints.
"""
from typing import Any


class PluginError(Exception):
    """Base for all QGIS MCP plugin-related errors."""
    error_code: str = "PLUGIN_ERROR"

    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message)
        self.details = details


class ConnectionError_(PluginError):
    """Connection to QGIS instance failed."""
    error_code = "CONNECTION_ERROR"


class LayerNotFoundError(PluginError):
    """Requested layer does not exist."""
    error_code = "LAYER_NOT_FOUND"


class FieldNotFoundError(PluginError):
    """Requested attribute field does not exist."""
    error_code = "FIELD_NOT_FOUND"


class CRSError(PluginError):
    """CRS or projection related error."""
    error_code = "CRS_ERROR"


class TimeoutError_(PluginError):
    """Operation timed out."""
    error_code = "TIMEOUT"


class CommandError(PluginError):
    """Generic command processing error."""
    error_code = "COMMAND_ERROR"


# Map of error_code -> hint for agents
ERROR_HINTS: dict[str, str] = {
    "LAYER_NOT_FOUND": "Try calling 'get_layers' to see all valid layer IDs.",
    "FIELD_NOT_FOUND": "Check the layer schema using 'qgis://layers/{layer_id}/schema'.",
    "CRS_ERROR": "Verify CRS strings (e.g., 'EPSG:4326') or use 'transform_coordinates'.",
    "CONNECTION_ERROR": "Ensure the QGIS MCP plugin is started (Plugins > QGIS MCP > Start Server).",
    "TIMEOUT": "The operation took too long. For large renders or processing, this is expected.",
    "COMMAND_ERROR": "Check the command parameters and try again. Use 'diagnose' for connection status.",
}


def get_error_hint(error_code: str) -> str | None:
    """Return a helpful hint for the given error code."""
    return ERROR_HINTS.get(error_code)
