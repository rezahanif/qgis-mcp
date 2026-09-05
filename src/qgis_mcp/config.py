"""Configuration and path resolution for QGIS MCP Connector."""

import os
from pathlib import Path
from typing import Optional

DEFAULT_HOST: str = os.environ.get("QGIS_MCP_HOST", "127.0.0.1")
DEFAULT_PORT: int = int(os.environ.get("QGIS_MCP_PORT", "9876"))
LOG_LEVEL: str = os.environ.get("QGIS_MCP_LOG_LEVEL", "WARNING").upper()

def detect_qgis_prefix() -> Optional[Path]:
    """Detect local QGIS installation on Windows or POSIX."""
    if "QGIS_PREFIX_PATH" in os.environ:
        p = Path(os.environ["QGIS_PREFIX_PATH"])
        if p.exists():
            return p

    # Standard Windows install locations
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    if program_files.exists():
        candidates = sorted(program_files.glob("QGIS*"), reverse=True)
        for c in candidates:
            if (c / "bin" / "qgis.exe").exists() or (c / "apps" / "qgis-ltr").exists():
                return c

    # OSGeo4W root
    for osgeo_dir in [Path("C:/OSGeo4W"), Path("C:/OSGeo4W64")]:
        if osgeo_dir.exists():
            return osgeo_dir

    return None

QGIS_PREFIX_PATH: Optional[Path] = detect_qgis_prefix()