"""Mock and diagnostic fallback adapter for offline / virgin environment testing."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from qgis_mcp.adapters.base import QgisBaseAdapter
from qgis_mcp.models import (
    CapabilitiesResponse,
    HealthCheckResponse,
    InspectLayerResponse,
    LayerExtent,
    RunProcessingResponse,
    ExportMapImageResponse,
    ActiveProjectResponse,
    LayerSummary,
    LoadProjectResponse,
    ZoomToResponse,
    SetSingleSymbolResponse,
    AlgorithmSpecResponse,
    QuickMapResponse,
    WindowStateResponse,
    UIScreenshotResponse,
)
from qgis_mcp.config import QGIS_PREFIX_PATH

class QgisMockAdapter(QgisBaseAdapter):
    def get_capabilities(self) -> CapabilitiesResponse:
        return CapabilitiesResponse(
            qgis_version="3.44.14-Solothurn (Mock/Offline)",
            gdal_version="3.13.3",
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            available_providers=["native", "gdal", "grass", "qgis"],
            desktop_running=False,
            adapter_mode="mock_fallback",
        )

    def health_check(self) -> HealthCheckResponse:
        return HealthCheckResponse(
            status="DEGRADED",
            pyqgis_installed=False,
            pyqgis_path=str(QGIS_PREFIX_PATH) if QGIS_PREFIX_PATH else None,
            osgeo4w_detected=QGIS_PREFIX_PATH is not None,
            plugin_connected=False,
            details={
                "message": "Running in mock/diagnostic mode. QGIS Desktop GUI is not active.",
                "python": sys.version,
            },
        )

    def inspect_layer(self, layer_id_or_name: str, source_path: Optional[str] = None) -> InspectLayerResponse:
        # Check CRS convention: geographic EPSG:4326 vs projected
        is_geo = True
        unit_warn = (
            "WARNING: CRS is geographic (EPSG:4326, degrees). Distances in meters will be interpreted as degrees!"
        )
        return InspectLayerResponse(
            layer_id=layer_id_or_name,
            name=layer_id_or_name,
            type="vector",
            crs_authid="EPSG:4326",
            crs_description="WGS 84 (Geographic Lat/Lon)",
            is_geographic=is_geo,
            unit_warning=unit_warn,
            extent=LayerExtent(xmin=-180.0, ymin=-90.0, xmax=180.0, ymax=90.0),
            feature_count=42,
            fields=[{"name": "id", "type": "Integer"}, {"name": "name", "type": "String"}],
        )

    def run_processing(
        self,
        algorithm_name: str,
        parameters: Dict[str, Any],
        distance_units: str = "meters"
    ) -> RunProcessingResponse:
        return RunProcessingResponse(
            success=True,
            algorithm=algorithm_name,
            results={
                "OUTPUT": f"memory:mock_result_{algorithm_name.replace(':', '_')}",
                "unit_used": distance_units,
                "parameters_echo": parameters,
            },
            message=f"Mock processed algorithm '{algorithm_name}' successfully.",
        )

    def export_map_image(
        self,
        output_path: str,
        width: int = 1024,
        height: int = 768,
        image_format: str = "png"
    ) -> ExportMapImageResponse:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # Create a tiny 1x1 or blank mock image if needed, or minimal valid PNG header
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        out_p.write_bytes(png_bytes)
        return ExportMapImageResponse(
            output_path=str(out_p.as_posix()),
            width=width,
            height=height,
            file_size_bytes=len(png_bytes),
        )

    def get_active_project(self) -> ActiveProjectResponse:
        return ActiveProjectResponse(
            project_path=None,
            title="Sample Mock Project",
            crs_authid="EPSG:4326",
            layers_count=2,
            layers=[
                LayerSummary(id="layer_001", name="osm_roads", type="vector", crs="EPSG:3857"),
                LayerSummary(id="layer_002", name="elevation_dem", type="raster", crs="EPSG:4326"),
            ],
        )

    def load_project(self, project_path: str, zoom_to_extent: bool = True) -> LoadProjectResponse:
        return LoadProjectResponse(
            loaded=str(Path(project_path).as_posix()),
            layer_count=2,
            extent=LayerExtent(xmin=-180.0, ymin=-90.0, xmax=180.0, ymax=90.0),
        )

    def zoom_to(self, target: str = "full", layer_id_or_name: str = "", bbox: Optional[Any] = None) -> ZoomToResponse:
        return ZoomToResponse(
            target=target,
            extent=LayerExtent(xmin=-180.0, ymin=-90.0, xmax=180.0, ymax=90.0),
            ok=True,
        )

    def set_single_symbol(
        self,
        layer_id_or_name: str,
        color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Optional[str] = None,
        opacity: Optional[float] = None,
    ) -> SetSingleSymbolResponse:
        return SetSingleSymbolResponse(
            ok=True,
            layer_id=layer_id_or_name,
            color=color,
            stroke_width=stroke_width,
        )

    def get_algorithm_spec(self, algorithm_name: str) -> AlgorithmSpecResponse:
        return AlgorithmSpecResponse(
            algorithm=algorithm_name,
            display_name=algorithm_name.replace("native:", "").replace("_", " ").title(),
            group="Vector geometry",
            parameters=[
                {"name": "INPUT", "description": "Input layer", "type": "source", "optional": False, "default": None},
                {"name": "DISTANCE", "description": "Distance in layer units", "type": "distance", "optional": False, "default": "10.0"},
                {"name": "OUTPUT", "description": "Buffered output", "type": "sink", "optional": True, "default": "memory:"},
            ],
            outputs=[
                {"name": "OUTPUT", "description": "Buffered layer", "type": "vector"},
            ],
        )

    def quick_map(
        self,
        output_path: str = "",
        zoom_to_full: bool = True,
        width: int = 1024,
        height: int = 768,
    ) -> QuickMapResponse:
        out_p = Path(output_path) if output_path else Path("quick_map.png")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        out_p.write_bytes(png_bytes)
        return QuickMapResponse(
            output_path=str(out_p.as_posix()),
            width=width,
            height=height,
            file_size_bytes=len(png_bytes),
        )

    def get_window_state(self) -> WindowStateResponse:
        return WindowStateResponse(
            window_title="*Untitled Project - QGIS (Mock)",
            active_modal_dialog=None,
            open_dialogs=[],
            visible_panels=["Layers", "Browser"],
            selected_layer="mock_layer",
            selected_layer_id="mock_layer_1",
            status_bar={"scale": "1:5000", "crs": "EPSG:32749", "center": [430000, 9140000]},
            canvas_extent=LayerExtent(xmin=420000, ymin=9130000, xmax=440000, ymax=9150000),
        )

    def get_ui_screenshot(
        self,
        output_path: Optional[str] = None,
        target: str = "active",
        image_format: str = "png",
    ) -> UIScreenshotResponse:
        out_p = Path(output_path) if output_path else Path("mock_ui_screenshot.png")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        out_p.write_bytes(png_bytes)
        return UIScreenshotResponse(
            output_path=str(out_p.as_posix()),
            target=target,
            widget_title="QGIS Desktop (Mock)",
            width=1024,
            height=768,
            file_size_bytes=len(png_bytes),
            format=image_format,
        )