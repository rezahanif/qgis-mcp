#!/usr/bin/env python3
"""Build qgis_mcp_plugin.zip — the host-plugin artifact named in manifest.json.

`manifest.host_plugin.artifact` is the file the gateway installs into the QGIS
profile. `process_manager.rs::install_host_plugin` resolves it as
`workdir.join(hp.artifact)` and does a plain `std::fs::copy` — so it must exist in
the shipped package as a FILE with exactly that name. The shared packager only
copies declared paths; it never builds anything. So this runs first, and
`manifest.package.include` names the result.

This exists because 0.12.0 shipped without it. 0.11.0's package contained
`qgis_mcp_plugin.zip`; when `package.include` was rewritten to declare the
`qgis_mcp_plugin/` source directory instead, the archive stopped being produced and
the connector shipped a manifest pointing at a file that was not there. Nothing on
Linux notices — installing a QGIS plugin is a Windows-side action — which is
exactly why it needs a build step and a gate check rather than vigilance.

Deterministic, like the shared packager: sorted entries, fixed 1980 timestamp, so
two builds of the same source give the same bytes and the package sha256 stays
reproducible.

Run: python3 scripts/build_plugin_zip.py
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "qgis_mcp_plugin"
OUT = ROOT / "qgis_mcp_plugin.zip"

PRUNE_DIRS = {"__pycache__", ".git", ".vscode", "tests"}
PRUNE_SUFFIX = (".pyc", ".pyo", ".pyd")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def main() -> int:
    if not SRC.is_dir():
        sys.exit(f"{SRC} does not exist — nothing to package")

    files = sorted(
        p for p in SRC.rglob("*")
        if p.is_file()
        and not p.name.endswith(PRUNE_SUFFIX)
        and not (set(p.relative_to(SRC).parts) & PRUNE_DIRS)
    )
    if not files:
        sys.exit(f"{SRC} contains no shippable files")

    # Entries are stored FLAT relative to the plugin directory, not under a
    # qgis_mcp_plugin/ prefix, matching what 0.11.0 shipped.
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            info = zipfile.ZipInfo(str(f.relative_to(SRC).as_posix()), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())

    import hashlib
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"{OUT.name}: {len(files)} files, {OUT.stat().st_size:,} bytes")
    print(f"  sha256 {digest}")
    if "metadata.txt" not in {f.relative_to(SRC).as_posix() for f in files}:
        print("  WARNING: no metadata.txt — QGIS will not recognise this as a plugin",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
