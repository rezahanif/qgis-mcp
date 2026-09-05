"""Abstract Base Adapter for QGIS MCP."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from qgis_mcp.models import (
    CapabilitiesResponse,
    HealthCheckResponse,
    InspectLayerResponse,
    RunProcessingResponse,
    ExportMapImageResponse,
    ActiveProjectResponse,
    LoadProjectResponse,
    ZoomToResponse,
    SetSingleSymbolResponse,
    AlgorithmSpecResponse,
    QuickMapResponse,
    WindowStateResponse,
    UIScreenshotResponse,
)

class QgisBaseAdapter(ABC):
    @abstractmethod
    def get_capabilities(self) -> CapabilitiesResponse:
        """Return QGIS capabilities and environment details."""
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResponse:
        """Perform diagnostic health check."""
        pass

    @abstractmethod
    def inspect_layer(self, layer_id_or_name: str, source_path: Optional[str] = None) -> InspectLayerResponse:
        """Inspect a layer metadata, CRS, schema, and extent."""
        pass

    @abstractmethod
    def run_processing(
        self,
        algorithm_name: str,
        parameters: Dict[str, Any],
        distance_units: str = "meters"
    ) -> RunProcessingResponse:
        """Execute a QGIS processing algorithm."""
        pass

    @abstractmethod
    def export_map_image(
        self,
        output_path: str,
        width: int = 1024,
        height: int = 768,
        image_format: str = "png"
    ) -> ExportMapImageResponse:
        """Render map view to an image file."""
        pass

    @abstractmethod
    def get_active_project(self) -> ActiveProjectResponse:
        """Inspect currently active project and loaded layers."""
        pass

    @abstractmethod
    def load_project(self, project_path: str, zoom_to_extent: bool = True) -> LoadProjectResponse:
        """Load a project and auto-zoom to extent."""
        pass

    @abstractmethod
    def zoom_to(self, target: str = "full", layer_id_or_name: str = "", bbox: Optional[Any] = None) -> ZoomToResponse:
        """Control map canvas viewport camera."""
        pass

    @abstractmethod
    def set_single_symbol(
        self,
        layer_id_or_name: str,
        color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Optional[str] = None,
        opacity: Optional[float] = None,
    ) -> SetSingleSymbolResponse:
        """Apply uniform single-symbol styling with color hex, stroke width, and opacity."""
        pass

    @abstractmethod
    def get_algorithm_spec(self, algorithm_name: str) -> AlgorithmSpecResponse:
        """Introspect algorithm parameters, types, and defaults."""
        pass

    @abstractmethod
    def quick_map(
        self,
        output_path: str = "",
        zoom_to_full: bool = True,
        width: int = 1024,
        height: int = 768,
    ) -> QuickMapResponse:
        """Bundled workflow: focus canvas, render map view, and return file size."""
        pass

    @abstractmethod
    def get_window_state(self) -> WindowStateResponse:
        """Get structured metadata of active QGIS window, dialogs, and panels (text-only, zero images)."""
        pass

    @abstractmethod
    def get_ui_screenshot(
        self,
        output_path: Optional[str] = None,
        target: str = "active",
        image_format: str = "png",
    ) -> UIScreenshotResponse:
        """Capture visual screenshot of QGIS desktop window or dialog to an image file (PNG/JPG)."""
        pass