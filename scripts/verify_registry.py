#!/usr/bin/env python3
"""Populate scripts/registry.json by EXECUTING PyQGIS calls against a real QGIS.

`qgis_function_registry_query` tells an agent "this call pattern is verified —
an earlier agent ran it successfully". That claim is the registry's entire
value, so nothing may be written here on the strength of documentation alone.
Every entry below is a probe that runs headlessly; an entry reaches the file
only if its probe returned without raising, and the probe's own assertion held.

Writes through the connector's own `FunctionRegistry`, not by hand, so the file
can never drift from the schema `qgis_function_registry_query` reads back.

Needs a PyQGIS install (headless is fine):
    QT_QPA_PLATFORM=offscreen <qgis-python> scripts/verify_registry.py
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _locate_pyqgis() -> Path | None:
    """PyQGIS is not always on sys.path.

    A conda-forge install puts the `qgis` package under
    <prefix>/share/qgis/python rather than in site-packages, and a Debian install
    uses /usr/share/qgis/python. Resolve it from the running interpreter's own
    prefix so this script works against whichever QGIS the caller points it at.
    """
    for prefix in (Path(sys.prefix), Path("/usr")):
        candidate = prefix / "share/qgis/python"
        if (candidate / "qgis").is_dir():
            sys.path.insert(0, str(candidate))
            return prefix
    return None


QGIS_PREFIX = _locate_pyqgis()

from qgis.core import QgsApplication  # noqa: E402

from qgis_mcp.function_registry import FunctionRegistry  # noqa: E402

PROBES: list[dict] = []


def probe(function_path, category, signature, description, parameter_notes="", notes=""):
    """Register a probe. The decorated callable must run the real API and assert."""
    def wrap(fn):
        PROBES.append({
            "function_path": function_path,
            "category": category,
            "signature": signature,
            "description": description,
            "parameter_notes": parameter_notes,
            "notes": notes,
            "run": fn,
        })
        return fn
    return wrap


def _memory_points(name="pts"):
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
    lyr = QgsVectorLayer("Point?crs=EPSG:4326&field=id:integer&field=name:string", name, "memory")
    feats = []
    for i, (x, y) in enumerate([(0.0, 0.0), (1.0, 1.0), (2.0, 0.5), (3.0, 2.0)]):
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        f.setAttributes([i, f"p{i}"])
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    return lyr


# ── Processing framework ──────────────────────────────────────────────
@probe("processing.run", "Processing Framework",
       "processing.run(algorithm_id: str, parameters: dict) -> dict",
       "Runs a Processing algorithm by id and returns a dict of its outputs.",
       "'OUTPUT': 'memory:name' keeps the result in RAM; a file path writes to disk. "
       "Layer inputs accept a QgsVectorLayer object or a source string.",
       "Returns a dict keyed by the algorithm's output names, not a layer. Read result['OUTPUT'].")
def _p_processing_run():
    import processing
    out = processing.run("native:buffer", {
        "INPUT": _memory_points(), "DISTANCE": 0.1, "SEGMENTS": 8,
        "DISSOLVE": False, "OUTPUT": "memory:buffered"})
    assert out["OUTPUT"].featureCount() == 4
    return True


@probe("QgsApplication.processingRegistry", "Processing Framework",
       "QgsApplication.processingRegistry() -> QgsProcessingRegistry",
       "Returns the processing registry, the entry point for enumerating every available algorithm.",
       "Static. Requires Processing.initialize() before providers are populated.",
       "len(registry.algorithms()) is 0 until the Processing framework is initialised.")
def _p_registry():
    from qgis.core import QgsApplication
    assert len(QgsApplication.processingRegistry().algorithms()) > 100
    return True


@probe("QgsProcessingRegistry.algorithmById", "Processing Framework",
       "QgsApplication.processingRegistry().algorithmById(id: str) -> QgsProcessingAlgorithm | None",
       "Looks up one algorithm by its fully qualified id, e.g. 'native:buffer'.",
       "The id is 'provider:name'. Returns None for an unknown id rather than raising.",
       "Pair with shortHelpString() to read an algorithm's parameters before calling processing.run.")
def _p_alg_by_id():
    from qgis.core import QgsApplication
    alg = QgsApplication.processingRegistry().algorithmById("native:buffer")
    assert alg is not None and QgsApplication.processingRegistry().algorithmById("no:such") is None
    return True


@probe("QgsProcessingAlgorithm.shortHelpString", "Processing Framework",
       "alg.shortHelpString() -> str",
       "Returns the HTML help text for an algorithm, including what each parameter means.",
       "Call on the object returned by algorithmById.",
       "The cheapest way to discover an unfamiliar algorithm's parameter names without leaving QGIS.")
def _p_help():
    from qgis.core import QgsApplication
    assert len(QgsApplication.processingRegistry().algorithmById("native:buffer").shortHelpString()) > 0
    return True


# ── Vector ────────────────────────────────────────────────────────────
@probe("QgsVectorLayer", "Vector Analysis",
       "QgsVectorLayer(path_or_uri: str, layer_name: str, provider: str) -> QgsVectorLayer",
       "Constructs a vector layer. The 'memory' provider builds a scratch layer from a URI string.",
       "A memory URI looks like 'Point?crs=EPSG:4326&field=id:integer'. Geometry type comes first.",
       "ALWAYS check layer.isValid() - an invalid layer is returned, not raised, and every later call fails silently.")
def _p_vector_layer():
    assert _memory_points().isValid()
    return True


@probe("QgsVectorLayer.getFeatures", "Vector Analysis",
       "layer.getFeatures(request: QgsFeatureRequest = ...) -> QgsFeatureIterator",
       "Iterates the layer's features, optionally filtered by a QgsFeatureRequest.",
       "Without a request it walks every feature. The iterator is single-pass.",
       "Do not call inside an open edit session without committing first, or you iterate stale state.")
def _p_get_features():
    assert len(list(_memory_points().getFeatures())) == 4
    return True


@probe("QgsFeatureRequest.setFilterExpression", "Vector Analysis",
       "QgsFeatureRequest().setFilterExpression(expression: str) -> QgsFeatureRequest",
       "Restricts a feature iteration to features matching a QGIS expression.",
       "The expression uses QGIS expression syntax, not SQL. Field names are bare or \"quoted\".",
       "Filtering in the request is far cheaper than iterating everything and testing in Python.")
def _p_feature_request():
    from qgis.core import QgsFeatureRequest
    req = QgsFeatureRequest().setFilterExpression('"id" >= 2')
    assert len(list(_memory_points().getFeatures(req))) == 2
    return True


@probe("QgsVectorLayer.selectByExpression", "Vector Analysis",
       "layer.selectByExpression(expression: str, behavior: int = SetSelection) -> None",
       "Selects features matching a QGIS expression, replacing the current selection by default.",
       "behavior: 0 SetSelection, 1 AddToSelection, 2 IntersectSelection, 3 RemoveFromSelection.",
       "Selection is canvas state, not a filter - getFeatures() still returns everything afterwards.")
def _p_select():
    lyr = _memory_points()
    lyr.selectByExpression('"id" < 2')
    assert lyr.selectedFeatureCount() == 2
    return True


@probe("QgsSpatialIndex.nearestNeighbor", "Vector Analysis",
       "QgsSpatialIndex(layer.getFeatures()).nearestNeighbor(point: QgsPointXY, neighbors: int) -> list[int]",
       "Returns the feature ids nearest to a point, using a bulk-loaded R-tree index.",
       "Build the index once from an iterator; querying it per point is what makes this fast.",
       "Returns feature IDs, not features. Look them up with getFeature(fid).")
def _p_spatial_index():
    from qgis.core import QgsPointXY, QgsSpatialIndex
    idx = QgsSpatialIndex(_memory_points().getFeatures())
    assert len(idx.nearestNeighbor(QgsPointXY(0.1, 0.1), 2)) == 2
    return True


@probe("QgsVectorFileWriter.writeAsVectorFormatV3", "Vector Analysis",
       "QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, transformContext, options) -> tuple",
       "Writes a vector layer to disk in any OGR format (GPKG, SHP, GeoJSON).",
       "options.driverName selects the format; 'GPKG' is the QGIS-native default.",
       "V1/V2 are deprecated. Returns (errorCode, message, ...) - errorCode 0 (NoError) means success.")
def _p_writer(tmp):
    from qgis.core import QgsProject, QgsVectorFileWriter
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    res = QgsVectorFileWriter.writeAsVectorFormatV3(
        _memory_points(), str(tmp / "out.gpkg"), QgsProject.instance().transformContext(), opts)
    assert res[0] == QgsVectorFileWriter.WriterError.NoError and (tmp / "out.gpkg").exists()
    return True


# ── Geometry ──────────────────────────────────────────────────────────
@probe("QgsGeometry.fromWkt", "Geometry Operations",
       "QgsGeometry.fromWkt(wkt: str) -> QgsGeometry",
       "Builds a geometry from Well-Known Text.",
       "Static. Invalid WKT yields a NULL geometry rather than raising.",
       "Check .isNull() after parsing; a silent NULL propagates through every later operation.")
def _p_from_wkt():
    from qgis.core import QgsGeometry
    assert not QgsGeometry.fromWkt("POLYGON((0 0,0 2,2 2,2 0,0 0))").isNull()
    return True


@probe("QgsGeometry.buffer", "Geometry Operations",
       "geometry.buffer(distance: float, segments: int) -> QgsGeometry",
       "Returns a buffer polygon around the geometry, approximating curves with `segments` per quadrant.",
       "distance is in the geometry's own CRS units - degrees in EPSG:4326, metres in a projected CRS.",
       "Buffering in a geographic CRS produces a distorted shape. Reproject before buffering by metres.")
def _p_buffer():
    from qgis.core import QgsGeometry
    assert QgsGeometry.fromWkt("POINT(0 0)").buffer(1.0, 8).area() > 3.0
    return True


@probe("QgsGeometry.intersection", "Geometry Operations",
       "geometry.intersection(other: QgsGeometry) -> QgsGeometry",
       "Returns the geometry shared by two geometries, empty when they do not overlap.",
       "Both geometries must already be in the same CRS - no transform is applied.",
       "Test .isEmpty() rather than comparing areas; a non-overlap returns an empty geometry, not None.")
def _p_intersection():
    from qgis.core import QgsGeometry
    a = QgsGeometry.fromWkt("POLYGON((0 0,0 2,2 2,2 0,0 0))")
    b = QgsGeometry.fromWkt("POLYGON((1 1,1 3,3 3,3 1,1 1))")
    assert abs(a.intersection(b).area() - 1.0) < 1e-9
    return True


@probe("QgsGeometry.makeValid", "Geometry Operations",
       "geometry.makeValid() -> QgsGeometry",
       "Repairs an invalid geometry (self-intersections, unclosed rings) and returns a valid one.",
       "Takes no arguments in the common form; returns a NEW geometry rather than repairing in place.",
       "Run before any overlay operation - GEOS raises on invalid input, which surfaces as a bare TopologyException.")
def _p_make_valid():
    from qgis.core import QgsGeometry
    bowtie = QgsGeometry.fromWkt("POLYGON((0 0,2 2,2 0,0 2,0 0))")
    assert not bowtie.isGeosValid() and bowtie.makeValid().isGeosValid()
    return True


@probe("QgsGeometry.centroid", "Geometry Operations",
       "geometry.centroid() -> QgsGeometry",
       "Returns the centre of mass of the geometry as a point geometry.",
       "Takes no arguments. The centroid of a concave polygon can fall outside it.",
       "Use pointOnSurface() instead when the result must lie inside the polygon.")
def _p_centroid():
    from qgis.core import QgsGeometry
    c = QgsGeometry.fromWkt("POLYGON((0 0,0 2,2 2,2 0,0 0))").centroid().asPoint()
    assert abs(c.x() - 1.0) < 1e-9 and abs(c.y() - 1.0) < 1e-9
    return True


# ── CRS ───────────────────────────────────────────────────────────────
@probe("QgsCoordinateReferenceSystem.fromEpsgId", "Coordinate Reference Systems",
       "QgsCoordinateReferenceSystem.fromEpsgId(epsg: int) -> QgsCoordinateReferenceSystem",
       "Builds a CRS from a numeric EPSG code.",
       "Static, takes the bare integer (4326), not the 'EPSG:4326' string form.",
       "An unknown code returns an INVALID crs object rather than raising - check .isValid().")
def _p_crs():
    from qgis.core import QgsCoordinateReferenceSystem
    assert QgsCoordinateReferenceSystem.fromEpsgId(4326).isValid()
    return True


@probe("QgsCoordinateTransform.transform", "Coordinate Reference Systems",
       "QgsCoordinateTransform(src, dest, QgsProject.instance()).transform(point: QgsPointXY) -> QgsPointXY",
       "Reprojects a point from the source CRS to the destination CRS.",
       "The third constructor argument supplies the datum-transform context; pass QgsProject.instance().",
       "Constructing the transform is the expensive part - build it once and reuse it across points.")
def _p_transform():
    from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                           QgsPointXY, QgsProject)
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                QgsCoordinateReferenceSystem("EPSG:3857"),
                                QgsProject.instance())
    assert abs(tr.transform(QgsPointXY(0.0, 0.0)).x()) < 1e-6
    return True


@probe("QgsDistanceArea.measureLength", "Coordinate Reference Systems",
       "da = QgsDistanceArea(); da.setEllipsoid('WGS84'); da.measureLength(geometry) -> float",
       "Measures true ellipsoidal length of a geometry rather than planar CRS-unit length.",
       "setEllipsoid() must be called or the measurement falls back to planar CRS units.",
       "This is how to get metres out of an EPSG:4326 layer without reprojecting it.")
def _p_distance_area():
    from qgis.core import QgsCoordinateReferenceSystem, QgsDistanceArea, QgsGeometry, QgsProject
    da = QgsDistanceArea()
    da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
    da.setEllipsoid("WGS84")
    assert da.measureLength(QgsGeometry.fromWkt("LINESTRING(0 0,1 0)")) > 100000
    return True


# ── Project ───────────────────────────────────────────────────────────
@probe("QgsProject.addMapLayer", "Project Management",
       "QgsProject.instance().addMapLayer(layer: QgsMapLayer, addToLegend: bool = True) -> QgsMapLayer",
       "Adds a layer to the current project so other tools and the canvas can see it.",
       "addToLegend=False registers the layer without showing it in the layer tree.",
       "A layer built in Python is invisible to every other tool until it is added to the project.")
def _p_add_layer():
    from qgis.core import QgsProject
    lyr = _memory_points("added")
    QgsProject.instance().addMapLayer(lyr)
    assert QgsProject.instance().mapLayer(lyr.id()) is not None
    QgsProject.instance().removeMapLayer(lyr.id())
    return True


@probe("QgsExpression.evaluate", "Expressions",
       "QgsExpression(text).evaluate(QgsExpressionContext) -> Any",
       "Evaluates a QGIS expression, optionally against a feature context.",
       "Without a context only context-free expressions work; field references need a feature scope.",
       "Check hasEvalError() - a failed evaluation returns None, which is indistinguishable from a NULL result.")
def _p_expression():
    from qgis.core import QgsExpression
    e = QgsExpression("1 + 2")
    assert e.evaluate() == 3 and not e.hasEvalError()
    return True


# ── Styling ───────────────────────────────────────────────────────────
@probe("QgsCategorizedSymbolRenderer", "Symbology and Styling",
       "QgsCategorizedSymbolRenderer(attrName: str, categories: list[QgsRendererCategory])",
       "Renders each distinct value of one field with its own symbol.",
       "attrName is a field name or an expression; categories pair a value with a symbol.",
       "layer.triggerRepaint() is required after setRenderer() or the canvas keeps the old symbology.")
def _p_categorized():
    from qgis.core import (QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol)
    lyr = _memory_points()
    cats = [QgsRendererCategory(f"p{i}", QgsSymbol.defaultSymbol(lyr.geometryType()), f"p{i}")
            for i in range(2)]
    lyr.setRenderer(QgsCategorizedSymbolRenderer("name", cats))
    assert lyr.renderer().classAttribute() == "name" and len(lyr.renderer().categories()) == 2
    return True


def main() -> int:
    if QGIS_PREFIX is not None:
        QgsApplication.setPrefixPath(str(QGIS_PREFIX), True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    roots = [Path(QgsApplication.prefixPath() or "")]
    if QGIS_PREFIX is not None:
        roots.append(QGIS_PREFIX)
    for root in roots:
        for candidate in (root / "share/qgis/python/plugins", root / "python/plugins"):
            if candidate.is_dir() and str(candidate) not in sys.path:
                sys.path.append(str(candidate))
    from processing.core.Processing import Processing
    Processing.initialize()

    import tempfile
    tmp = Path(tempfile.mkdtemp())

    reg_path = ROOT / "scripts" / "registry.json"
    if reg_path.exists():
        reg_path.unlink()               # rebuilt from probes every run, never appended to
    reg = FunctionRegistry(registry_path=reg_path)

    passed = failed = 0
    for spec in PROBES:
        fn = spec.pop("run")
        name = spec["function_path"]
        try:
            fn(tmp) if fn.__code__.co_argcount else fn()
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
            continue
        reg.register_function(**spec)
        reg.mark_verified(name)
        passed += 1
        print(f"ok   {name}")

    # `load_template` tells the agent "the code is verified against real QGIS".
    # The snippets are parameterised, so they cannot be executed as written - but
    # the algorithm ids they name CAN be resolved, and a template naming an
    # algorithm that does not exist is the failure that claim exists to exclude.
    import json
    import re

    from qgis.core import QgsApplication as _App

    registry_alg = _App.processingRegistry()
    templates = json.loads((ROOT / "templates" / "templates.json").read_text(
        encoding="utf-8"))["templates"]
    alg_bad = []
    alg_seen = 0
    for tid, tpl in sorted(templates.items()):
        for alg_id in re.findall(r"processing\.run\(\s*['\"]([a-z0-9_]+:[a-zA-Z0-9_]+)['\"]",
                                 tpl["code"]):
            alg_seen += 1
            if registry_alg.algorithmById(alg_id) is None:
                alg_bad.append(f"{tid}: unknown algorithm {alg_id!r}")
    for b in alg_bad:
        print(f"FAIL template {b}")
    print(f"{alg_seen - len(alg_bad)}/{alg_seen} template algorithm ids resolve "
          f"across {len(templates)} templates")

    from qgis.core import Qgis
    # applicationVersion() is the QGIS *app* version and is empty in a headless
    # QgsApplication; Qgis.QGIS_VERSION is the library version and is always set.
    print(f"\n{passed}/{passed + failed} probes verified against QGIS "
          f"{Qgis.QGIS_VERSION}")
    qgs.exitQgis()
    return 1 if (failed or alg_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
