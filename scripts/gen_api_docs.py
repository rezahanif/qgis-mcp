#!/usr/bin/env python3
"""Generate API/*.md — the tier-2 PyQGIS reference qgis_mcp/doc_search.py indexes.

Signatures are SCRAPED from the official PyQGIS documentation
(https://qgis.org/pyqgis/master/), never recalled from memory. Every name is
resolved through the Sphinx inventory (objects.inv) first, so a name that has
been renamed or removed upstream is a hard error rather than a plausible-looking
section that documents a call which does not exist.

Output format is exactly what `DocIndex._parse_file` reads:

    # <ShortName>
    ## Syntax
    <real signature>
    ## Description
    <first paragraph from the upstream docs>
    ```python
    <call template, derived mechanically from the signature>
    ```

The filename stem selects the category label via doc_search.CATEGORIES, so a new
file must be added there too or it falls back to the bare stem.

These entries are DOCUMENTED, not verified — nothing here has been executed
against a real QGIS. That distinction is the whole point of the split with
scripts/registry.json, which holds only what actually ran. See
aiconnector/docs/audit/QGIS-API-BENCHMARK.md.

Run: python3 scripts/gen_api_docs.py [--out API] [--cache .doccache]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://qgis.org/pyqgis/master/"
UA = {"User-Agent": "qgis-mcp-doc-generator/0.12 (+https://github.com/rezahanif/qgis-mcp)"}

# file stem -> qualified names. The stem must exist in doc_search.CATEGORIES.
SECTIONS: dict[str, list[str]] = {
    "Processing": [
        "qgis.core.QgsApplication.processingRegistry",
        "qgis.core.QgsProcessingRegistry.algorithmById",
        "qgis.core.QgsProcessingRegistry.algorithms",
        "qgis.core.QgsProcessingAlgorithm.run",
        "qgis.core.QgsProcessingUtils.mapLayerFromString",
        "qgis.core.QgsProcessingParameters.parameterAsLayer",
    ],
    "Geometry": [
        "qgis.core.QgsGeometry.buffer",
        "qgis.core.QgsGeometry.intersection",
        "qgis.core.QgsGeometry.difference",
        "qgis.core.QgsGeometry.simplify",
        "qgis.core.QgsGeometry.centroid",
        "qgis.core.QgsGeometry.fromWkt",
        "qgis.core.QgsGeometry.makeValid",
    ],
    "Vector": [
        "qgis.core.QgsSpatialIndex",
        "qgis.core.QgsSpatialIndex.nearestNeighbor",
        "qgis.core.QgsFeatureRequest.setFilterExpression",
        "qgis.core.QgsVectorLayer.getFeatures",
        "qgis.core.QgsVectorLayerUtils.createFeature",
        "qgis.core.QgsVectorFileWriter.writeAsVectorFormatV3",
    ],
    "Raster": [
        "qgis.analysis.QgsRasterCalculator",
        "qgis.analysis.QgsZonalStatistics",
        "qgis.core.QgsRasterDataProvider.sample",
        "qgis.core.QgsRasterInterface.block",
        "qgis.core.QgsRasterFileWriter.writeRaster",
    ],
    "Styling": [
        "qgis.core.QgsCategorizedSymbolRenderer",
        "qgis.core.QgsGraduatedSymbolRenderer.createRenderer",
        "qgis.core.QgsRendererCategory.setValue",
        "qgis.core.QgsSymbol.defaultSymbol",
        "qgis.core.QgsPalLayerSettings.setFormat",
        "qgis.core.QgsVectorLayerSimpleLabeling",
    ],
    "CRS": [
        "qgis.core.QgsCoordinateReferenceSystem.fromEpsgId",
        "qgis.core.QgsCoordinateTransform.transform",
        "qgis.core.QgsProject.transformContext",
        "qgis.core.QgsDistanceArea.measureLength",
    ],
    "Layouts": [
        "qgis.core.QgsLayoutExporter.exportToImage",
        "qgis.core.QgsLayoutExporter.exportToPdf",
        "qgis.core.QgsLayoutItemMap.setExtent",
        "qgis.core.QgsLayoutItemLegend.setLinkedMap",
        "qgis.core.QgsLayoutAtlas.setFilterFeatures",
    ],
}


def fetch(url: str, cache: Path) -> str:
    key = cache / re.sub(r"[^A-Za-z0-9_.-]", "_", url.replace(BASE, ""))
    if key.exists():
        return key.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8", "replace")
    cache.mkdir(parents=True, exist_ok=True)
    key.write_text(body, encoding="utf-8")
    return body


def load_inventory(cache: Path) -> dict[str, str]:
    """Parse Sphinx objects.inv -> {qualified name: page path}."""
    raw_path = cache / "objects.inv"
    if not raw_path.exists():
        req = urllib.request.Request(BASE + "objects.inv", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        cache.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
    raw = raw_path.read_bytes()
    # four plain-text header lines, then zlib
    off = 0
    for _ in range(4):
        off = raw.index(b"\n", off) + 1
    body = zlib.decompress(raw[off:]).decode("utf-8")
    inv: dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+(-?\d+)\s+(\S+)\s+(.*)$", line)
        if m:
            name, _typ, _prio, loc, _disp = m.groups()
            inv[name] = loc.replace("$", name)
    return inv


TAGS = re.compile(r"<[^>]+>")


def text_of(fragment: str) -> str:
    return html.unescape(TAGS.sub("", fragment)).replace("¶", "").strip()


def extract(page: str, qualified: str) -> tuple[str, str]:
    """Return (signature, description) for one anchored definition.

    For a CLASS the useful content is not on the class anchor. PyQGIS renders
    that as a bare `class qgis.core.QgsFoo` whose block often holds nothing but
    `Bases: ...` before diving into nested methods - both the constructor
    arguments and the prose live on the class's `__init__` entry instead. So a
    class falls back to `__init__` for whichever of the two it is missing.
    """
    anchor = f'id="{qualified}"'
    i = page.find(anchor)
    if i < 0:
        raise KeyError(qualified)
    # rewind to the start of the enclosing <dt ...> or the id= attribute leaks
    # into the signature text ('id="qgis.core.QgsGeometry.buffer"> buffer(...)')
    dt_start = page.rindex("<dt", 0, i)
    dt_end = page.index("</dt>", i)
    sig = text_of(page[dt_start:dt_end])
    sig = re.sub(r"\[source\]$", "", sig).strip()
    sig = re.sub(r"\s+", " ", sig).replace("→", "->")

    # Take the first few substantive paragraphs, not just one. On a CLASS page the
    # opening paragraphs are boilerplate ("Bases: ...", "Constructor for X.") and the
    # sentence that actually describes the class - the text BM25 has to match on -
    # is the third or fourth.
    drop = re.compile(r"^Bases:")
    # "Constructor for QgsSpatialIndex. Creates an empty R-tree index." - the lead
    # sentence is boilerplate but what follows it is the only description the page
    # carries, so strip the prefix instead of discarding the paragraph.
    lead = re.compile(r"^(?:Copy c|C)onstructor for [^.]*\.\s*")
    paras: list[str] = []
    dd = page.find("<dd>", dt_end)
    if dd >= 0:
        # Bound the scan to THIS entry. A fixed character window runs past the
        # closing </dd> into the next method's block, and the description then
        # ends with sentences describing a different call entirely.
        nxt = page.find('<dl class="py ', dd)
        end = nxt if nxt > 0 else min(len(page), dd + 20000)
        for m in re.finditer(r"<p>(.*?)</p>", page[dd:end], re.DOTALL):
            candidate = re.sub(r"\s+", " ", text_of(m.group(1))).strip()
            if drop.match(candidate):
                continue
            candidate = lead.sub("", candidate).strip()
            if len(candidate) < 25:
                continue
            if re.match(r"^\w+\s*\(.*\)$", candidate):      # a parameter row, not prose
                continue
            paras.append(candidate)
            if len(" ".join(paras)) > 320:
                break
    desc = " ".join(paras)[:480]

    if sig.startswith("class ") and f'id="{qualified}.__init__"' in page:
        ctor_sig, ctor_desc = extract(page, f"{qualified}.__init__")
        short = qualified.split(".")[-1]
        args = re.search(r"\((.*)\)", ctor_sig)
        if args:
            sig = f"{short}({args.group(1)})"
        desc = desc or ctor_desc
    return sig, desc


def call_template(qualified: str, sig: str) -> str:
    """A call skeleton derived from the real signature. Mechanical, not invented."""
    short = qualified.split(".")[-1]
    params = ""
    m = re.search(r"\((.*)\)", sig)
    if m:
        parts = [p.strip() for p in re.split(r",(?![^\[\]()]*[\])])", m.group(1)) if p.strip()]
        names = [p.split(":")[0].split("=")[0].strip() for p in parts]
        names = [n for n in names if n and n != "self"]
        params = ", ".join(names)
    owner = qualified.split(".")[-2]
    if short[0].isupper():                       # a class: constructor
        return f"from {qualified.rsplit('.', 1)[0]} import {short}\nobj = {short}({params})"
    return f"from {'.'.join(qualified.split('.')[:2])} import {owner}\nresult = {owner}.{short}({params})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "API"))
    ap.add_argument("--cache", default=str(ROOT / ".doccache"))
    args = ap.parse_args()

    cache = Path(args.cache)
    out = Path(args.out)
    inv = load_inventory(cache)

    missing = [n for names in SECTIONS.values() for n in names if n not in inv]
    if missing:
        print("names absent from the upstream PyQGIS inventory:", file=sys.stderr)
        for n in missing:
            print("  " + n, file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for stem, names in SECTIONS.items():
        blocks = []
        for qualified in names:
            loc = inv[qualified]
            page = fetch(BASE + loc.split("#")[0], cache)
            try:
                sig, desc = extract(page, qualified)
            except KeyError:
                print(f"anchor not found on page: {qualified}", file=sys.stderr)
                return 1
            if not desc:
                print(f"no description paragraph: {qualified}", file=sys.stderr)
                return 1
            tail = qualified.split(".")[-1]
            # a class stands alone; a method is qualified by its owning class
            short = tail if tail[0].isupper() else ".".join(qualified.split(".")[-2:])
            blocks.append(
                f"# {short}\n\n"
                f"## Syntax\n{sig}\n\n"
                f"## Description\n{desc}\n\n"
                f"```python\n{call_template(qualified, sig)}\n```\n"
            )
            total += 1
        header = (
            f"<!-- generated by scripts/gen_api_docs.py from {BASE} — do not edit by hand -->\n\n"
        )
        (out / f"{stem}.md").write_text(header + "\n".join(blocks), encoding="utf-8")
        print(f"  {stem}.md  {len(names)} sections")
    print(f"{total} sections across {len(SECTIONS)} categories -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
