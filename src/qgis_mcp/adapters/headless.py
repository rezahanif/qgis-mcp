"""Headless PyQGIS adapter for offscreen/batch GIS operations without GUI."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from qgis_mcp.adapters.base import QgisBaseAdapter
from qgis_mcp.config import QGIS_PREFIX_PATH
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

# Safe conditional PyQGIS import
try:
    from qgis.core import (
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
        QgsVectorLayer,
    )
    PYQGIS_AVAILABLE = True
except ImportError:
    PYQGIS_AVAILABLE = False


class QgisHeadlessAdapter(QgisBaseAdapter):
    def __init__(self):
        self._app = None
        if PYQGIS_AVAILABLE:
            self._init_qgis()

    def _init_qgis(self):
        if QgsApplication.instance() is None:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            self._app = QgsApplication([], False)
            if QGIS_PREFIX_PATH:
                self._app.setPrefixPath(str(QGIS_PREFIX_PATH.as_posix()), True)
            self._app.initQgis()

    def is_available(self) -> bool:
        return PYQGIS_AVAILABLE

    def get_capabilities(self) -> CapabilitiesResponse:
        from qgis.core import Qgis
        return CapabilitiesResponse(
            qgis_version=Qgis.version(),
            gdal_version=getattr(Qgis, "gdalVersion", lambda: "3.x")(),
            python_version=sys.version.split()[0],
            available_providers=["native", "gdal", "qgis"],
            desktop_running=False,
            adapter_mode="headless",
        )

    def health_check(self) -> HealthCheckResponse:
        return HealthCheckResponse(
            status="OK" if PYQGIS_AVAILABLE else "DEGRADED",
            pyqgis_installed=PYQGIS_AVAILABLE,
            pyqgis_path=str(QGIS_PREFIX_PATH.as_posix()) if QGIS_PREFIX_PATH else None,
            osgeo4w_detected=QGIS_PREFIX_PATH is not None,
            plugin_connected=False,
            details={
                "mode": "headless",
                "qt_platform": os.environ.get("QT_QPA_PLATFORM", "default"),
            },
        )

    def inspect_layer(self, layer_id_or_name: str, source_path: Optional[str] = None) -> InspectLayerResponse:
        path = source_path or layer_id_or_name
        vlayer = QgsVectorLayer(path, "inspect_layer", "ogr")
        if vlayer.isValid():
            crs = vlayer.crs()
            is_geo = crs.isGeographic()
            rect = vlayer.extent()
            extent = LayerExtent(
                xmin=rect.xMinimum(),
                ymin=rect.yMinimum(),
                xmax=rect.xMaximum(),
                ymax=rect.yMaximum(),
            )
            fields = [{"name": f.name(), "type": f.typeName()} for f in vlayer.fields()]
            return InspectLayerResponse(
                layer_id=vlayer.id(),
                name=vlayer.name(),
                type="vector",
                crs_authid=crs.authid(),
                crs_description=crs.description(),
                is_geographic=is_geo,
                unit_warning="WARNING: Geographic coordinates (degrees). Buffer/distance calculations expect meters!" if is_geo else None,
                extent=extent,
                feature_count=vlayer.featureCount(),
                fields=fields,
            )

        rlayer = QgsRasterLayer(path, "inspect_layer")
        if rlayer.isValid():
            crs = rlayer.crs()
            is_geo = crs.isGeographic()
            rect = rlayer.extent()
            extent = LayerExtent(
                xmin=rect.xMinimum(),
                ymin=rect.yMinimum(),
                xmax=rect.xMaximum(),
                ymax=rect.yMaximum(),
            )
            return InspectLayerResponse(
                layer_id=rlayer.id(),
                name=rlayer.name(),
                type="raster",
                crs_authid=crs.authid(),
                crs_description=crs.description(),
                is_geographic=is_geo,
                unit_warning="WARNING: Geographic coordinates (degrees)!" if is_geo else None,
                extent=extent,
                raster_bands=rlayer.bandCount(),
            )

        raise ValueError(f"Could not load layer from path/id: {path}")

    def run_processing(
        self,
        algorithm_name: str,
        parameters: Dict[str, Any],
        distance_units: str = "meters"
    ) -> RunProcessingResponse:
        # Import processing in headless PyQGIS
        import processing
        res = processing.run(algorithm_name, parameters)

        messages = ["Algorithm executed via headless PyQGIS processing."]
        out_val = str(parameters.get("OUTPUT", "") or parameters.get("output", "") or "")
        if not out_val or out_val.startswith("memory:") or out_val == "TEMPORARY_OUTPUT":
            messages.append(
                "CRITICAL WARNING: Output was created as an in-memory layer (RAM only). "
                "In-memory layers EVAPORATE upon project reload or process restart! "
                "To persist permanently, specify a persistent file path in parameters['OUTPUT'] (e.g. 'D:/output/result.gpkg')."
            )
        else:
            messages.append(f"Output saved permanently to: {out_val}")

        return RunProcessingResponse(
            success=True,
            algorithm=algorithm_name,
            results=res,
            message=" ".join(messages),
        )

    def export_map_image(
        self,
        output_path: str,
        width: int = 1024,
        height: int = 768,
        image_format: str = "png"
    ) -> ExportMapImageResponse:
        from qgis.core import QgsMapSettings, QgsMapRendererParallelJob
        from PyQt5.QtGui import QImage, QColor
        from PyQt5.QtCore import QSize

        settings = QgsMapSettings()
        settings.setOutputSize(QSize(width, height))
        settings.setBackgroundColor(QColor(255, 255, 255))
        settings.setLayers(QgsProject.instance().mapLayers().values())
        settings.setExtent(QgsProject.instance().viewExtent())

        job = QgsMapRendererParallelJob(settings)
        job.start()
        job.waitForFinished()
        image = job.renderedImage()
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(out_p.as_posix()), image_format.upper())
        size = out_p.stat().st_size if out_p.exists() else 0

        return ExportMapImageResponse(
            output_path=str(out_p.as_posix()),
            width=width,
            height=height,
            file_size_bytes=size,
        )

    def get_active_project(self) -> ActiveProjectResponse:
        proj = QgsProject.instance()
        layers = []
        for l in proj.mapLayers().values():
            layers.append(
                LayerSummary(
                    id=l.id(),
                    name=l.name(),
                    type="vector" if isinstance(l, QgsVectorLayer) else "raster",
                    crs=l.crs().authid(),
                )
            )
        return ActiveProjectResponse(
            project_path=proj.fileName() or None,
            title=proj.title() or None,
            crs_authid=proj.crs().authid(),
            layers_count=len(layers),
            layers=layers,
        )

    def load_project(self, project_path: str, zoom_to_extent: bool = True) -> LoadProjectResponse:
        proj = QgsProject.instance()
        posix_path = str(Path(project_path).as_posix())
        ok = proj.read(posix_path)
        ext = None
        if ok and zoom_to_extent:
            full_box = None
            for lyr in proj.mapLayers().values():
                if lyr.isValid():
                    full_box = lyr.extent() if full_box is None else full_box.combineExtentWith(lyr.extent())
            if full_box:
                ext = LayerExtent(xmin=full_box.xMinimum(), ymin=full_box.yMinimum(), xmax=full_box.xMaximum(), ymax=full_box.yMaximum())
        return LoadProjectResponse(
            loaded=posix_path if ok else "",
            layer_count=len(proj.mapLayers()) if ok else 0,
            extent=ext,
        )

    def zoom_to(self, target: str = "full", layer_id_or_name: str = "", bbox: Optional[Any] = None) -> ZoomToResponse:
        proj = QgsProject.instance()
        ext = None
        if target == "layer" and layer_id_or_name:
            lyr = proj.mapLayer(layer_id_or_name)
            if not lyr:
                for l in proj.mapLayers().values():
                    if l.name() == layer_id_or_name:
                        lyr = l
                        break
            if lyr and lyr.isValid():
                e = lyr.extent()
                ext = LayerExtent(xmin=e.xMinimum(), ymin=e.yMinimum(), xmax=e.xMaximum(), ymax=e.yMaximum())
        elif target == "bbox" and bbox and len(bbox) == 4:
            ext = LayerExtent(xmin=bbox[0], ymin=bbox[1], xmax=bbox[2], ymax=bbox[3])
        else:
            full_box = None
            for lyr in proj.mapLayers().values():
                if lyr.isValid():
                    full_box = lyr.extent() if full_box is None else full_box.combineExtentWith(lyr.extent())
            if full_box:
                ext = LayerExtent(xmin=full_box.xMinimum(), ymin=full_box.yMinimum(), xmax=full_box.xMaximum(), ymax=full_box.yMaximum())
        return ZoomToResponse(target=target, extent=ext, ok=True)

    def set_single_symbol(
        self,
        layer_id_or_name: str,
        color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        stroke_color: Optional[str] = None,
        opacity: Optional[float] = None,
    ) -> SetSingleSymbolResponse:
        from qgis.core import QgsSymbol, QgsSingleSymbolRenderer
        from qgis.PyQt.QtGui import QColor
        proj = QgsProject.instance()
        lyr = proj.mapLayer(layer_id_or_name)
        if not lyr:
            for l in proj.mapLayers().values():
                if l.name() == layer_id_or_name:
                    lyr = l
                    break
        if lyr and isinstance(lyr, QgsVectorLayer):
            sym = QgsSymbol.defaultSymbol(lyr.geometryType())
            target_color = color
            if target_color:
                sym.setColor(QColor(target_color))
            if opacity is not None:
                sym.setOpacity(float(opacity))
            if stroke_width is not None and hasattr(sym, "setWidth"):
                sym.setWidth(float(stroke_width))
            lyr.setRenderer(QgsSingleSymbolRenderer(sym))
            lyr.triggerRepaint()
            return SetSingleSymbolResponse(ok=True, layer_id=lyr.id(), color=color, stroke_width=stroke_width)
        return SetSingleSymbolResponse(ok=False, layer_id=layer_id_or_name, color=color, stroke_width=stroke_width)

    def get_algorithm_spec(self, algorithm_name: str) -> AlgorithmSpecResponse:
        from qgis.core import QgsProcessingParameterDefinition
        algo = QgsApplication.processingRegistry().algorithmById(algorithm_name)
        if not algo:
            return AlgorithmSpecResponse(algorithm=algorithm_name, display_name=algorithm_name, group="", parameters=[], outputs=[])
        params = []
        for p in algo.parameterDefinitions():
            params.append({
                "name": p.name(),
                "description": p.description(),
                "type": p.type(),
                "optional": bool(p.flags() & QgsProcessingParameterDefinition.FlagOptional),
                "default": str(p.defaultValue()) if p.defaultValue() is not None else None,
            })
        outputs = []
        for out in algo.outputDefinitions():
            outputs.append({
                "name": out.name(),
                "description": out.description(),
                "type": out.type(),
            })
        return AlgorithmSpecResponse(
            algorithm=algorithm_name,
            display_name=algo.displayName(),
            group=algo.group(),
            parameters=params,
            outputs=outputs,
        )

    def quick_map(
        self,
        output_path: str = "",
        zoom_to_full: bool = True,
        width: int = 1024,
        height: int = 768,
    ) -> QuickMapResponse:
        target_path = output_path if output_path else str((Path.cwd() / "quick_map.png").as_posix())
        exp = self.export_map_image(target_path, width, height, "png")
        return QuickMapResponse(
            output_path=exp.output_path,
            width=exp.width,
            height=exp.height,
            file_size_bytes=exp.file_size_bytes,
        )

    def get_window_state(self) -> WindowStateResponse:
        prj = QgsProject.instance() if PYQGIS_AVAILABLE else None
        return WindowStateResponse(
            window_title="QGIS Headless (Offscreen)",
            active_modal_dialog=None,
            open_dialogs=[],
            visible_panels=[],
            selected_layer=None,
            selected_layer_id=None,
            status_bar={"mode": "headless", "crs": prj.crs().authid() if prj else "EPSG:4326"},
            canvas_extent=None,
        )

    def get_ui_screenshot(
        self,
        output_path: Optional[str] = None,
        target: str = "active",
        image_format: str = "png",
    ) -> UIScreenshotResponse:
        target_path = output_path if output_path else str((Path.cwd() / f"qgis_ui_screenshot.{image_format}").as_posix())
        exp = self.export_map_image(target_path, 1024, 768, image_format)
        return UIScreenshotResponse(
            output_path=exp.output_path,
            target="offscreen_canvas",
            widget_title="Headless Canvas",
            width=exp.width,
            height=exp.height,
            file_size_bytes=exp.file_size_bytes,
            format=image_format,
        )