#!/usr/bin/env python3
"""AiConnect QGIS MCP Server implementation."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Logging isolation: ALWAYS use stderr to preserve stdout for JSON-RPC
logger = logging.getLogger("qgis_mcp")
logger.handlers.clear()
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.addHandler(stderr_handler)
logger.setLevel(logging.WARNING)

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

from qgis_mcp.adapters import get_adapter
from qgis_mcp.models import (
    CapabilitiesResponse,
    HealthCheckResponse,
    InspectLayerResponse,
    RunProcessingResponse,
    ExportMapImageResponse,
    ActiveProjectResponse,
)

mcp = FastMCP("qgis-mcp", instructions="Automate QGIS Desktop GIS modeling, vector/raster spatial analysis, CRS transformations, and map rendering via MCP.") if FastMCP else None

if mcp:
    @mcp.tool(name="qgis_get_capabilities")
    def qgis_get_capabilities() -> Dict[str, Any]:
        """Get QGIS installation version, GDAL support, available processing providers, and active connection status."""
        adapter = get_adapter()
        return adapter.get_capabilities().model_dump()

    @mcp.tool(name="qgis_health_check")
    def qgis_health_check() -> Dict[str, Any]:
        """Verify PyQGIS paths, OSGeo4W environment, Python dependencies, and QGIS GUI plugin connectivity."""
        adapter = get_adapter()
        return adapter.health_check().model_dump()

    @mcp.tool(name="qgis_inspect_layer")
    def qgis_inspect_layer(layer_id_or_name: str, source_path: str = "") -> Dict[str, Any]:
        """Inspect spatial layer metadata: attributes schema, feature count, CRS, and bounding box extent.
        
        IDENTIFIER PRECISION: Accepts either unique alphanumeric layer ID (e.g. 'road_sleman_83f3f7d5...') or display name ('road_sleman').
        When multiple layers share the same name (e.g. duplicate buffer runs), use the exact layer_id to avoid ambiguity.
        COORDINATE UNITS & CRS: Returns 'is_geographic' and 'unit_warning'. If true, CRS is in degrees (EPSG:4326), meaning
        spatial buffer/distance operations will measure in degrees (1 degree ~ 111 km) unless reprojected to a projected CRS (e.g. UTM)."""
        adapter = get_adapter()
        return adapter.inspect_layer(layer_id_or_name, source_path if source_path else None).model_dump()

    @mcp.tool(name="qgis_run_processing")
    def qgis_run_processing(
        algorithm_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        distance_units: str = "meters"
    ) -> Dict[str, Any]:
        """Execute a QGIS or GDAL processing algorithm (e.g. buffer, clip, dissolve, reproject).
        
        CRITICAL USAGE GUIDELINES FOR AGENTS:
        1. IN-MEMORY EVAPORATION WARNING: Omitting parameters['OUTPUT'] or setting it to 'memory:' creates a temporary RAM layer.
           In-memory layers EVAPORATE completely (feature count becomes 0 or layer disappears) upon closing QGIS or reloading the project!
           ALWAYS specify a persistent GeoPackage or Shapefile path (e.g. 'D:/analysis/result.gpkg') to persist results permanently.
        2. COORDINATE SYSTEMS & DISTANCE UNITS: Spatial distance algorithms (e.g. native:buffer) use layer CRS units.
           - Projected CRS (e.g. EPSG:32749 UTM): Units are METERS. Passing DISTANCE=100 creates a 100-meter buffer.
           - Geographic CRS (e.g. EPSG:4326 WGS84): Units are DEGREES. Passing DISTANCE=100 creates a buffer spanning the globe! (1 degree ~ 111 km)
           Specify distance_units explicitly and check 'is_geographic' via qgis_inspect_layer.
        3. PARAMETER NORMALIZATION: Keys are automatically case-normalized (e.g. 'input' -> 'INPUT').
        4. IDENTIFIER PRECISION: Use exact unique 'layer_id' when layers share identical display names."""
        adapter = get_adapter()
        params = parameters if parameters is not None else {}
        return adapter.run_processing(algorithm_name, params, distance_units).model_dump()

    @mcp.tool(name="qgis_export_map_image")
    def qgis_export_map_image(
        output_path: str,
        width: int = 1024,
        height: int = 768,
        image_format: str = "png"
    ) -> Dict[str, Any]:
        """Render map canvas or project layers to an image file (PNG, JPG) at specified pixel resolution."""
        adapter = get_adapter()
        return adapter.export_map_image(output_path, width, height, image_format).model_dump()

    @mcp.tool(name="qgis_get_active_project")
    def qgis_get_active_project() -> Dict[str, Any]:
        """Inspect open QGIS project file, CRS, and list layers currently loaded in the desktop session."""
        adapter = get_adapter()
        return adapter.get_active_project().model_dump()

    @mcp.tool(name="qgis_load_project")
    def qgis_load_project(project_path: str, zoom_to_extent: bool = True) -> Dict[str, Any]:
        """Load a QGIS project file (.qgz or .qgs) into the active session and automatically center the map viewport camera on the study area extent."""
        adapter = get_adapter()
        return adapter.load_project(project_path, zoom_to_extent).model_dump()

    @mcp.tool(name="qgis_zoom_to")
    def qgis_zoom_to(
        target: str = "full",
        layer_id_or_name: str = "",
        bbox: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Navigate and center the map canvas camera. Target can be 'full' (all layers), 'layer' (specific layer by name/id), or 'bbox' ([xmin, ymin, xmax, ymax])."""
        adapter = get_adapter()
        return adapter.zoom_to(target, layer_id_or_name, bbox).model_dump()

    @mcp.tool(name="qgis_set_single_symbol")
    def qgis_set_single_symbol(
        layer_id_or_name: str,
        color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Optional[str] = None,
        opacity: Optional[float] = None
    ) -> Dict[str, Any]:
        """Apply uniform single-symbol styling on a vector layer. Accepts direct hex colors (e.g. '#39FF14' neon green), stroke width in mm, and opacity (0.0 to 1.0)."""
        adapter = get_adapter()
        return adapter.set_single_symbol(layer_id_or_name, color, stroke_width, stroke_color, opacity).model_dump()

    @mcp.tool(name="qgis_get_algorithm_spec")
    def qgis_get_algorithm_spec(algorithm_name: str) -> Dict[str, Any]:
        """Introspect a QGIS or GDAL processing algorithm to inspect its parameter names, descriptions, data types, required/optional flags, and default values."""
        adapter = get_adapter()
        return adapter.get_algorithm_spec(algorithm_name).model_dump()

    @mcp.tool(name="qgis_quick_map")
    def qgis_quick_map(
        output_path: str = "",
        zoom_to_full: bool = True,
        width: int = 1024,
        height: int = 768
    ) -> Dict[str, Any]:
        """Bundled workflow: Centers the viewport on all active layers, renders the map canvas to disk, and returns the file path and byte size."""
        adapter = get_adapter()
        return adapter.quick_map(output_path, zoom_to_full, width, height).model_dump()

    @mcp.tool(name="qgis_get_window_state")
    def qgis_get_window_state() -> Dict[str, Any]:
        """Get structured metadata of active QGIS window, modal dialogs, visible panels, and status bar.
        
        OUTPUT FORMAT: Pure structured text/JSON (zero image files).
        RECOMMENDED FOR: All LLM agents, especially text-only models that cannot process image files.
        Returns:
        - window_title: Title of main QGIS window
        - active_modal_dialog: Any blocking modal dialog title (or null)
        - open_dialogs: List of open non-main dialogs/windows
        - visible_panels: List of visible dock panels (e.g. Layers, Browser, Processing)
        - selected_layer: Currently selected layer name in layer tree
        - status_bar: Current scale, CRS, and center coordinate
        - canvas_extent: Current bounding box coordinates
        """
        adapter = get_adapter()
        return adapter.get_window_state().model_dump()

    @mcp.tool(name="qgis_get_ui_screenshot")
    def qgis_get_ui_screenshot(
        output_path: str = "",
        target: str = "active",
        image_format: str = "png"
    ) -> Dict[str, Any]:
        """Capture a visual desktop screenshot of the QGIS user interface (toolbars, layers panel, open dialogs, and canvas).
        
        OUTPUT FORMAT: Saves an image file to disk (.png or .jpg) and returns file path, dimensions, and file size.
        SUPPORTED FILE FORMATS: '.png' (default, lossless) and '.jpg' / '.jpeg' (compressed).
        TARGET OPTIONS:
        - 'active' (default): Captures currently focused window or modal dialog if one is open, else main window.
        - 'main': Captures full QGIS application window (including dock panels, menu, and status bar).
        - 'canvas': Captures only the map canvas area.
        NOTE FOR AGENTS: Only multimodal vision-capable agents should call this tool. Text-only agents that cannot interpret image files MUST use 'qgis_get_window_state' instead.
        """
        adapter = get_adapter()
        return adapter.get_ui_screenshot(output_path, target, image_format).model_dump()



async def main():
    """Run the MCP server asynchronously over stdio."""
    if not mcp:
        logger.error("FastMCP library not found.")
        sys.exit(1)
    if hasattr(mcp, "run_stdio_async"):
        await mcp.run_stdio_async()
    else:
        mcp.run()

if __name__ == "__main__":
    asyncio.run(main())