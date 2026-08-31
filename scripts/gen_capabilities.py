#!/usr/bin/env python3
"""Generate the tier-2 capability index the gateway shadow-indexes.

A shadow capability is something this connector can DO but does not advertise as
a typed tool: it never enters `tools/list`, so it costs zero tool-surface tokens
in every session, and it is reached through the exec hatch declared in
manifest.json (`execute_code`). See aiconnector/docs/audit/QGIS-API-BENCHMARK.md.

Two sources, deliberately kept distinct by `verification_status`:

  verified    scripts/registry.json - PyQGIS calls this connector has actually
              executed successfully against a real QGIS, written by
              scripts/verify_registry.py. THIS IS THE DEFAULT.
  documented  API/*.md, behind --include-docs. Parsed with the connector's OWN
              doc_search parser, so the index cannot drift from what
              `search_qgis_api` returns.

Whether the doc half helps or hurts is a measured question, not a matter of
taste: on sap2000 the 1,657 extra documented entries bought ~9 tier-2 tasks and
cost half the negative controls. Sweep it for this connector before enabling it.

Registry wins on collision, and any name that collides with a real typed tool is
dropped - the callable one must win.

Run: python3 scripts/gen_capabilities.py [--include-docs]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "qgis_mcp" / "aiconnect-capabilities.json"
REGISTRY = ROOT / "scripts" / "registry.json"
EXEC_TOOL = "execute_code"

# --- connector-shipped alias phrasings -------------------------------------
# Authored intent phrasings live in ONE file next to the generated index, and
# this generator is the only thing that copies them. The gateway folds them into
# its BM25 haystack only (ToolDoc::add_search_text) - never into the summary the
# model is shown, and never into the embedding.
#
# They are emitted as alias-only entries naming LISTED tools. shadow_docs skips a
# capability whose name collides with a real tool (the callable one wins), but
# merge_capability_aliases harvests its phrasings onto that tool first, so this is
# exactly where aliases pay. An older gateway simply skips them: backward compatible.
ALIAS_FILE = OUT.parent / "aiconnect_aliases.json"


def alias_entries(taken: set) -> list:
    """Alias-only entries for tools that ARE listed. No description - the real
    one arrives over tools/list."""
    if not ALIAS_FILE.is_file():
        return []
    aliases = json.loads(ALIAS_FILE.read_text(encoding="utf-8")).get("aliases", {})
    return [{"name": n, "aliases": aliases[n]}
            for n in sorted(aliases) if n not in taken and aliases[n]]

MAX_DESC = 200


def typed_tool_names() -> set[str]:
    """Names the connector really lists. A shadow entry may never shadow one."""
    import ast

    src = (ROOT / "qgis_mcp" / "server.py").read_text(encoding="utf-8")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for dec in node.decorator_list:
                fn = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(fn, ast.Attribute) and fn.attr == "tool":
                    names.add(node.name)
    return names


def from_registry() -> list[dict]:
    if not REGISTRY.is_file():
        sys.exit(f"{REGISTRY} does not exist — run scripts/verify_registry.py "
                 f"against a real QGIS first. An empty tier-2 index is exactly the "
                 f"failure this file exists to prevent.")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = []
    for path, entry in sorted(data.get("functions", {}).items()):
        if not entry.get("verified"):
            continue
        desc = entry.get("description", "") or ""
        sig = entry.get("signature", "") or ""
        notes = entry.get("notes", "") or ""
        blurb = " ".join(x for x in (desc, sig, notes) if x)[:MAX_DESC]
        out.append({
            "name": path,
            "description": blurb,
            "category": entry.get("category", "Uncategorized"),
            "verification_status": "verified",
        })
    return out


def from_docs() -> list[dict]:
    """Parse API/*.md with the connector's own indexer, not a second parser."""
    from qgis_mcp.doc_search import DocIndex

    idx = DocIndex()
    idx._load()
    out = []
    for section in idx._sections:
        blurb = " ".join(x for x in (section.get("description", ""),
                                     section.get("syntax", "")) if x)[:MAX_DESC]
        out.append({
            "name": section["function_name"],
            "description": blurb,
            "category": section["category"],
            "verification_status": "documented",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-docs", action="store_true",
                    help="add the API/*.md half (measure it before shipping it)")
    ap.add_argument("--docs-only", action="store_true",
                    help="API/*.md ONLY, no verified half. This is a benchmark arm, "
                         "not a shipping configuration: every entry is documented, so "
                         "the index asserts existence and says nothing about correctness.")
    args = ap.parse_args()
    if args.docs_only and args.include_docs:
        ap.error("--docs-only already implies the docs half")

    typed = typed_tool_names()
    merged: dict[str, dict] = {}

    if args.include_docs or args.docs_only:
        for cap in from_docs():
            merged[cap["name"]] = cap
    if not args.docs_only:
        for cap in from_registry():      # registry wins on collision
            merged[cap["name"]] = cap

    shadowed = sorted(n for n in merged if n in typed)
    for n in shadowed:
        del merged[n]

    caps = [merged[k] for k in sorted(merged)]
    # `caps` stays the capability list, so every count below is unchanged by
    # aliases; the alias-only entries exist purely as a search channel.
    enriched = alias_entries({c["name"] for c in caps})
    OUT.write_text(json.dumps({"exec_tool": EXEC_TOOL, "capabilities": caps + enriched},
                              indent=2) + "\n", encoding="utf-8")
    print(f"  alias-only entries for listed tools: {len(enriched)}")

    verified = sum(1 for c in caps if c["verification_status"] == "verified")
    print(f"{len(caps)} capabilities -> {OUT.relative_to(ROOT)}")
    print(f"  verified   {verified}")
    print(f"  documented {len(caps) - verified}")
    if shadowed:
        print(f"  dropped (collide with a listed tool): {', '.join(shadowed)}")
    if args.docs_only:
        print("  WARNING: --docs-only. Nothing in this index has been executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
