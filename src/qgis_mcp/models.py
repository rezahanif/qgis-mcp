"""Pydantic schemas and models for QGIS MCP Connector."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class CapabilitiesResponse(BaseModel):
    qgis_version: str = Field(..., description="Installed or runtime QGIS version")
    gdal_version: Optional[str] = Field(None, description="GDAL library version")
    python_version: str = Field(..., description="Python interpreter version")
    available_providers: List[str] = Field(default_factory=list, description="Available processing providers")
    desktop_running: bool = Field(..., description="Whether active QGIS GUI bridge is connected")
    adapter_mode: str = Field(..., description="Active adapter execution mode (gui, headless, mock)")

class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health status (OK, DEGRADED, OFFLINE)")
    pyqgis_installed: bool = Field(..., description="Whether PyQGIS core is importable")
    pyqgis_path: Optional[str] = Field(None, description="Resolved PyQGIS library path")
    osgeo4w_detected: bool = Field(..., description="Whether OSGeo4W / QGIS installation was detected")
    plugin_connected: bool = Field(..., description="Whether QGIS GUI plugin TCP bridge is connected")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic details")

class InspectLayerRequest(BaseModel):
    layer_id_or_name: str = Field(..., description="Layer ID or layer name to inspect")
    source_path: Optional[str] = Field(None, description="Direct file path to inspect if not loaded")

class LayerExtent(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

class InspectLayerResponse(BaseModel):
    layer_id: str
    name: str
    type: str = Field(..., description="Layer type: 'vector' or 'raster'")
    crs_authid: str = Field(..., description="Coordinate Reference System (e.g. EPSG:4326, EPSG:3857)")
    crs_description: Optional[str] = None
    is_geographic: bool = Field(..., description="True if CRS is measured in degrees (e.g. WGS84)")
    unit_warning: Optional[str] = Field(None, description="Warning if spatial operations will use degrees instead of meters")
    extent: Optional[LayerExtent] = None
    feature_count: Optional[int] = None
    fields: Optional[List[Dict[str, str]]] = None
    raster_bands: Optional[int] = None

class RunProcessingRequest(BaseModel):
    algorithm_name: str = Field(..., description="QGIS or GDAL algorithm ID, e.g. 'native:buffer', 'native:clip'")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Algorithm input parameters")
    distance_units: Optional[str] = Field("meters", description="Units for spatial buffer/distance (meters or degrees)")

class RunProcessingResponse(BaseModel):
    success: bool
    algorithm: str
    results: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None

class ExportMapImageRequest(BaseModel):
    output_path: str = Field(..., description="Output image file path (e.g. D:/map.png)")
    width: int = Field(1024, description="Width in pixels")
    height: int = Field(768, description="Height in pixels")
    image_format: str = Field("png", description="Image format (png, jpg)")

class ExportMapImageResponse(BaseModel):
    output_path: str
    width: int
    height: int
    file_size_bytes: int

class LayerSummary(BaseModel):
    id: str
    name: str
    type: str
    crs: str

class ActiveProjectResponse(BaseModel):
    project_path: Optional[str] = None
    title: Optional[str] = None
    crs_authid: str
    layers_count: int
    layers: List[LayerSummary] = Field(default_factory=list)

class LoadProjectResponse(BaseModel):
    loaded: str
    layer_count: int
    extent: Optional[LayerExtent] = None

class ZoomToResponse(BaseModel):
    target: str
    extent: Optional[LayerExtent] = None
    ok: bool = True

class SetSingleSymbolResponse(BaseModel):
    ok: bool
    layer_id: str
    color: Optional[str] = None
    stroke_width: Optional[float] = None

class AlgorithmSpecResponse(BaseModel):
    algorithm: str
    display_name: str
    group: str
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)

class QuickMapResponse(BaseModel):
    output_path: str
    width: int
    height: int
    file_size_bytes: int

class WindowStateResponse(BaseModel):
    window_title: str = Field(..., description="Title of the main QGIS window")
    active_modal_dialog: Optional[str] = Field(None, description="Title of any blocking modal dialog, or None")
    open_dialogs: List[str] = Field(default_factory=list, description="List of currently visible non-main dialogs/windows")
    visible_panels: List[str] = Field(default_factory=list, description="Visible dock panels (e.g. Layers, Browser, Toolbox)")
    selected_layer: Optional[str] = Field(None, description="Currently selected layer in the layer tree")
    selected_layer_id: Optional[str] = Field(None, description="Layer ID of the currently selected layer")
    status_bar: Dict[str, Any] = Field(default_factory=dict, description="Status bar info (scale, CRS, center coordinate)")
    canvas_extent: Optional[LayerExtent] = Field(None, description="Current bounding box coordinates of the canvas")

class UIScreenshotResponse(BaseModel):
    output_path: str = Field(..., description="File path where screenshot was saved (supports .png, .jpg)")
    target: str = Field(..., description="Captured widget target (e.g. main_window, modal dialog, canvas)")
    widget_title: Optional[str] = Field("", description="Title of the captured window or dialog")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    file_size_bytes: int = Field(..., description="Saved image file size in bytes")
    format: str = Field("png", description="Image format (png, jpg)")