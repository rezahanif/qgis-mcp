"""GUI adapter for interactive QGIS Desktop sessions via TCP plugin bridge."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from qgis_mcp.adapters.base import QgisBaseAdapter
from qgis_mcp.client import QgisMCPClient
from qgis_mcp.config import DEFAULT_HOST, DEFAULT_PORT
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

class QgisGUIAdapter(QgisBaseAdapter):
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.client = QgisMCPClient(host=host, port=port)

    @staticmethod
    def _unwrap(res: Any) -> Any:
        if isinstance(res, dict):
            if res.get("status") == "error":
                raise RuntimeError(res.get("message", "Error from QGIS plugin"))
            if "result" in res:
                return res["result"]
        return res

    def is_available(self) -> bool:
        # 1. Try configured port first
        try:
            connected = self.client.connect(timeout=0.2)
            if connected:
                self.client.disconnect()
                return True
        except Exception:
            pass

        # 2. Probe consecutive ports 9876..9885 if configured port failed
        for p in range(9876, 9886):
            if p == self.port:
                continue
            probe_client = QgisMCPClient(host=self.host, port=p)
            try:
                if probe_client.connect(timeout=0.05):
                    probe_client.disconnect()
                    self.port = p
                    self.client.port = p
                    return True
            except Exception:
                pass

        return False

    def get_capabilities(self) -> CapabilitiesResponse:
        self.client.connect()
        try:
            raw_info = self.client.send_command("get_qgis_info", {})
            info = self._unwrap(raw_info) if isinstance(raw_info, dict) else {}
            raw_prov = self.client.send_command("get_processing_providers", {})
            providers_resp = self._unwrap(raw_prov)
            providers = [p.get("id", "") for p in providers_resp] if isinstance(providers_resp, list) else []
            return CapabilitiesResponse(
                qgis_version=info.get("version", "3.x") if isinstance(info, dict) else "3.x",
                gdal_version=info.get("gdal_version") if isinstance(info, dict) else None,
                python_version=info.get("python_version", sys.version.split()[0]) if isinstance(info, dict) else sys.version.split()[0],
                available_providers=providers or ["native", "gdal", "qgis"],
                desktop_running=True,
                adapter_mode="gui",
            )
        finally:
            self.client.disconnect()

    def health_check(self) -> HealthCheckResponse:
        try:
            self.client.connect()
            ping_resp = self._unwrap(self.client.send_command("ping", {}))
            self.client.disconnect()
            return HealthCheckResponse(
                status="OK",
                pyqgis_installed=True,
                pyqgis_path=None,
                osgeo4w_detected=True,
                plugin_connected=True,
                details={"ping": ping_resp},
            )
        except Exception as exc:
            return HealthCheckResponse(
                status="OFFLINE",
                pyqgis_installed=False,
                pyqgis_path=None,
                osgeo4w_detected=False,
                plugin_connected=False,
                details={"error": str(exc)},
            )

    def inspect_layer(self, layer_id_or_name: str, source_path: Optional[str] = None) -> InspectLayerResponse:
        self.client.connect()
        try:
            raw_layer = self.client.send_command("get_layer_crs", {"layer_id": layer_id_or_name})
            layer_info = self._unwrap(raw_layer) if isinstance(raw_layer, dict) else {}
            crs_authid = layer_info.get("authid", "EPSG:4326") if isinstance(layer_info, dict) else "EPSG:4326"
            is_geo = "4326" in crs_authid
            raw_ext = self.client.send_command("get_layer_extent", {"layer_id": layer_id_or_name})
            extent_info = self._unwrap(raw_ext)
            
            extent = None
            if isinstance(extent_info, dict) and "xmin" in extent_info:
                extent = LayerExtent(
                    xmin=extent_info["xmin"],
                    ymin=extent_info["ymin"],
                    xmax=extent_info["xmax"],
                    ymax=extent_info["ymax"],
                )

            return InspectLayerResponse(
                layer_id=layer_id_or_name,
                name=layer_info.get("name", layer_id_or_name) if isinstance(layer_info, dict) else layer_id_or_name,
                type=layer_info.get("type", "vector") if isinstance(layer_info, dict) else "vector",
                crs_authid=crs_authid,
                crs_description=layer_info.get("description") if isinstance(layer_info, dict) else None,
                is_geographic=is_geo,
                unit_warning="WARNING: Geographic coordinates in degrees!" if is_geo else None,
                extent=extent,
                feature_count=layer_info.get("feature_count") if isinstance(layer_info, dict) else None,
            )
        finally:
            self.client.disconnect()

    def run_processing(
        self,
        algorithm_name: str,
        parameters: Dict[str, Any],
        distance_units: str = "meters"
    ) -> RunProcessingResponse:
        self.client.connect()
        try:
            res = self._unwrap(self.client.send_command("execute_processing", {
                "algorithm": algorithm_name,
                "parameters": parameters,
            }))

            messages = ["Processing executed via active QGIS GUI plugin."]

            # 1. In-Memory Layer Evaporation Warning
            out_val = str(parameters.get("OUTPUT", "") or parameters.get("output", "") or "")
            is_ephemeral = not out_val or out_val.startswith("memory:") or out_val == "TEMPORARY_OUTPUT"
            if is_ephemeral:
                messages.append(
                    "CRITICAL WARNING: Output was created as an in-memory layer (RAM only). "
                    "In-memory layers EVAPORATE (feature count becomes 0 or layer disappears) "
                    "when QGIS is closed or the project is reloaded! "
                    "To persist permanently, specify a persistent file path in parameters['OUTPUT'] (e.g. 'D:/output/result.gpkg')."
                )
            else:
                messages.append(f"Output saved permanently to: {out_val}")

            # 2. Geographic CRS Distance Warning
            input_val = str(parameters.get("INPUT", "") or parameters.get("input", "") or "")
            if input_val and ("meter" in distance_units.lower() or "degree" in distance_units.lower()):
                try:
                    raw_crs = self.client.send_command("get_layer_crs", {"layer_id": input_val})
                    layer_crs = self._unwrap(raw_crs) if isinstance(raw_crs, dict) else {}
                    if isinstance(layer_crs, dict) and "4326" in layer_crs.get("authid", ""):
                        messages.append(
                            "CRS NOTICE: Input layer is in EPSG:4326 (degrees). "
                            "Native distance operations in QGIS will interpret distance values as DEGREES (1 degree ~ 111 km), "
                            "NOT meters! If metric distance was intended, reproject the layer to a projected CRS (e.g. UTM) first."
                        )
                except Exception:
                    pass

            return RunProcessingResponse(
                success=True,
                algorithm=algorithm_name,
                results=res if isinstance(res, dict) else {"output": res},
                message=" ".join(messages),
            )
        finally:
            self.client.disconnect()

    def export_map_image(
        self,
        output_path: str,
        width: int = 1024,
        height: int = 768,
        image_format: str = "png"
    ) -> ExportMapImageResponse:
        self.client.connect()
        try:
            posix_path = str(Path(output_path).as_posix())
            self.client.send_command("render_map_base64", {
                "path": posix_path,
                "width": width,
                "height": height,
            })
            p = Path(output_path)
            size = p.stat().st_size if p.exists() else 0
            return ExportMapImageResponse(
                output_path=str(p.as_posix()),
                width=width,
                height=height,
                file_size_bytes=size,
            )
        finally:
            self.client.disconnect()

    def get_active_project(self) -> ActiveProjectResponse:
        self.client.connect()
        try:
            proj = self._unwrap(self.client.send_command("get_project_info", {}))
            if not isinstance(proj, dict):
                proj = {}
            layers_resp = self._unwrap(self.client.send_command("get_layers", {}))
            layers = []
            layers_list = layers_resp.get("layers", []) if isinstance(layers_resp, dict) else (layers_resp if isinstance(layers_resp, list) else [])
            for l in layers_list:
                layers.append(
                    LayerSummary(
                        id=l.get("id", ""),
                        name=l.get("name", ""),
                        type=l.get("type", ""),
                        crs=l.get("crs", proj.get("crs", "EPSG:4326")),
                    )
                )
            return ActiveProjectResponse(
                project_path=proj.get("filename"),
                title=proj.get("title"),
                crs_authid=proj.get("crs", "EPSG:4326"),
                layers_count=len(layers),
                layers=layers,
            )
        finally:
            self.client.disconnect()

    def load_project(self, project_path: str, zoom_to_extent: bool = True) -> LoadProjectResponse:
        self.client.connect()
        try:
            posix_path = str(Path(project_path).as_posix())
            res = self._unwrap(self.client.send_command("load_project", {"path": posix_path, "zoom_to_extent": zoom_to_extent}))
            if not isinstance(res, dict):
                res = {}
            ext_list = res.get("extent")
            ext = None
            if ext_list and len(ext_list) == 4:
                ext = LayerExtent(xmin=ext_list[0], ymin=ext_list[1], xmax=ext_list[2], ymax=ext_list[3])
            return LoadProjectResponse(
                loaded=res.get("loaded", posix_path),
                layer_count=res.get("layer_count", 0),
                extent=ext,
            )
        finally:
            self.client.disconnect()

    def zoom_to(self, target: str = "full", layer_id_or_name: str = "", bbox: Optional[Any] = None) -> ZoomToResponse:
        self.client.connect()
        try:
            if target == "layer" and layer_id_or_name:
                self.client.send_command("zoom_to_layer", {"layer_id": layer_id_or_name})
            elif target == "bbox" and bbox and len(bbox) == 4:
                self.client.send_command("set_canvas_extent", {"xmin": bbox[0], "ymin": bbox[1], "xmax": bbox[2], "ymax": bbox[3]})
            else:
                self.client.send_command("execute_code", {"code": "iface.mapCanvas().zoomToFullExtent(); iface.mapCanvas().refresh()"})
            cur_ext = self._unwrap(self.client.send_command("get_canvas_extent", {}))
            ext = None
            if isinstance(cur_ext, dict) and "xmin" in cur_ext:
                ext = LayerExtent(xmin=cur_ext["xmin"], ymin=cur_ext["ymin"], xmax=cur_ext["xmax"], ymax=cur_ext["ymax"])
            return ZoomToResponse(target=target, extent=ext, ok=True)
        finally:
            self.client.disconnect()

    def set_single_symbol(
        self,
        layer_id_or_name: str,
        color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Optional[str] = None,
        opacity: Optional[float] = None,
    ) -> SetSingleSymbolResponse:
        self.client.connect()
        try:
            cmd_args = {"layer_id": layer_id_or_name}
            if color: cmd_args["color"] = color
            if stroke_width is not None: cmd_args["stroke_width"] = stroke_width
            if stroke_color: cmd_args["stroke_color"] = stroke_color
            if opacity is not None: cmd_args["opacity"] = opacity
            res = self._unwrap(self.client.send_command("set_single_symbol", cmd_args))
            if not isinstance(res, dict):
                res = {}
            return SetSingleSymbolResponse(
                ok=res.get("ok", True),
                layer_id=res.get("layer_id", layer_id_or_name),
                color=res.get("color", color),
                stroke_width=res.get("stroke_width", stroke_width),
            )
        finally:
            self.client.disconnect()

    def get_algorithm_spec(self, algorithm_name: str) -> AlgorithmSpecResponse:
        self.client.connect()
        try:
            res = self._unwrap(self.client.send_command("get_algorithm_spec", {"algorithm": algorithm_name}))
            if not isinstance(res, dict):
                res = {}
            return AlgorithmSpecResponse(
                algorithm=res.get("algorithm", algorithm_name),
                display_name=res.get("display_name", algorithm_name),
                group=res.get("group", ""),
                parameters=res.get("parameters", []),
                outputs=res.get("outputs", []),
            )
        finally:
            self.client.disconnect()

    def quick_map(
        self,
        output_path: str = "",
        zoom_to_full: bool = True,
        width: int = 1024,
        height: int = 768,
    ) -> QuickMapResponse:
        if zoom_to_full:
            self.zoom_to("full")
        target_path = output_path if output_path else str((Path.cwd() / "quick_map.png").as_posix())
        exp = self.export_map_image(target_path, width, height, "png")
        return QuickMapResponse(
            output_path=exp.output_path,
            width=exp.width,
            height=exp.height,
            file_size_bytes=exp.file_size_bytes,
        )

    def get_window_state(self) -> WindowStateResponse:
        self.client.connect()
        try:
            res = self._unwrap(self.client.send_command("get_window_state", {}))
            if not isinstance(res, dict):
                res = {}
            ext_dict = res.get("canvas_extent")
            ext = None
            if isinstance(ext_dict, dict) and "xmin" in ext_dict:
                ext = LayerExtent(
                    xmin=ext_dict["xmin"],
                    ymin=ext_dict["ymin"],
                    xmax=ext_dict["xmax"],
                    ymax=ext_dict["ymax"],
                )
            return WindowStateResponse(
                window_title=res.get("window_title", ""),
                active_modal_dialog=res.get("active_modal_dialog"),
                open_dialogs=res.get("open_dialogs", []),
                visible_panels=res.get("visible_panels", []),
                selected_layer=res.get("selected_layer"),
                selected_layer_id=res.get("selected_layer_id"),
                status_bar=res.get("status_bar", {}),
                canvas_extent=ext,
            )
        finally:
            self.client.disconnect()

    def get_ui_screenshot(
        self,
        output_path: Optional[str] = None,
        target: str = "active",
        image_format: str = "png",
    ) -> UIScreenshotResponse:
        self.client.connect()
        try:
            args = {"target": target, "format": image_format}
            if output_path:
                args["output_path"] = str(Path(output_path).as_posix())
            res = self._unwrap(self.client.send_command("get_ui_screenshot", args))
            if not isinstance(res, dict):
                res = {}
            return UIScreenshotResponse(
                output_path=res.get("output_path", str(output_path or "")),
                target=res.get("target", target),
                widget_title=res.get("widget_title", ""),
                width=res.get("width", 0),
                height=res.get("height", 0),
                file_size_bytes=res.get("file_size_bytes", 0),
                format=res.get("format", image_format),
            )
        finally:
            self.client.disconnect()