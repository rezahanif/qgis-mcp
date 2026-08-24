"""Layer B tools validation — runs WITHOUT QGIS.

Validates the five Layer B guidance tools end-to-end against the real
doc_search + function_registry + templates modules:
  1. list_qgis_api_categories
  2. search_qgis_api
  3. qgis_function_registry_query (summary / detail / filter)
  4. register_verified_qgis
  5. list_templates / load_template
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name)


# ── doc_search ────────────────────────────────────────────────────────
import tempfile

from qgis_mcp import doc_search as ds

# Build a temp API dir with two known sections, and point DocIndex at it
# BEFORE any instance loads (the module reads ds.API_DIR lazily per call,
# but a fresh class instance is used so no stale singleton state applies).
tmp = tempfile.mkdtemp()
api_dir = Path(tmp) / "API"
api_dir.mkdir()
(api_dir / "Processing.md").write_text(
    "# processing.run\n\n## Syntax\nprocessing.run(algorithm, parameters)\n\n"
    "## Description\nExecutes a Processing algorithm and returns a dict of outputs.\n\n"
    "```python\nresult = processing.run('native:buffer', {'INPUT': lyr})\n```\n",
    encoding="utf-8",
)
(api_dir / "Vector.md").write_text(
    "# QgsSpatialIndex\n\n## Syntax\nQgsSpatialIndex(layer)\n\n"
    "## Description\nBulk loads a spatial index for fast nearest-neighbour queries.\n",
    encoding="utf-8",
)

ds.API_DIR = api_dir
idx2 = ds.DocIndex()
cats = idx2.list_categories()
check("doc_search: categories listed", any(c["category"] == "Processing Framework" for c in cats))
res = idx2.search("buffer algorithm")
check("doc_search: search finds processing.run", len(res) >= 1 and "processing.run" in res[0]["function_name"])
res2 = idx2.search("spatial index")
check("doc_search: category-scoped search", len(res2) >= 1 and res2[0]["category"] == "Vector Analysis")
check("doc_search: no-match returns empty", idx2.search("zzzznotfound") == [])

# ── function_registry ─────────────────────────────────────────────────
from qgis_mcp.function_registry import FunctionRegistry

reg_path = Path(tmp) / "scripts" / "registry.json"
reg = FunctionRegistry(registry_path=reg_path)

summary0 = reg.get_summary()
check("registry: starts empty", summary0["total_registered"] == 0)

r1 = reg.register_function(
    function_path="processing.run",
    category="Processing",
    description="Run a processing algorithm",
    signature='processing.run("native:buffer", {...}) -> {"OUTPUT": layer}',
)
check("registry: register new", r1["registered"] is True and r1["is_new"] is True)

v1 = reg.mark_verified("processing.run")
check("registry: mark verified", v1["verified"] is True)

r2 = reg.register_function(
    function_path="processing.run",
    category="Processing",
    notes="OUTPUT must be memory: for temp layers",
)
check("registry: re-register updates not new", r2["is_new"] is False)

fn = reg.get_function("processing.run")
check("registry: detail keeps fields", fn["verified"] is True and fn["notes"] != "")

matches = reg.list_functions(verified_only=True)
check("registry: verified_only filter", len(matches) == 1 and matches[0]["function_path"] == "processing.run")
check("registry: query miss returns empty", reg.list_functions(query="qqqq") == [])
cats_reg = reg.get_categories()
check("registry: categories counted", cats_reg["Processing"]["verified"] == 1)

# persistence round-trip
reg2 = FunctionRegistry(registry_path=reg_path)
check("registry: persists across instances", reg2.get_summary()["total_verified"] == 1)

# ── templates ─────────────────────────────────────────────────────────
tpl_path = Path(__file__).resolve().parent.parent / "templates" / "templates.json"
templates = json.loads(tpl_path.read_text(encoding="utf-8")).get("templates", {})
check("templates: file has entries", len(templates) >= 5)
check("templates: all have code+name+category", all(
    t.get("code") and t.get("name") and t.get("category") for t in templates.values()))

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} Layer B checks passed")
sys.exit(1 if failed else 0)
