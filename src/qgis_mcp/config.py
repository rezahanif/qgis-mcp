"""Configuration and path resolution for QGIS MCP Connector."""

import os
from pathlib import Path
from typing import Optional

def detect_qgis_port() -> int:
    """Detect configured QGIS MCP port from environment, QGIS3.ini, or default 9876."""
    if "QGIS_MCP_PORT" in os.environ:
        try:
            return int(os.environ["QGIS_MCP_PORT"])
        except ValueError:
            pass

    # Check QGIS user profile QGIS3.ini
    appdata = os.environ.get("APPDATA")
    if appdata:
        ini_path = Path(appdata) / "QGIS" / "QGIS3" / "profiles" / "default" / "QGIS" / "QGIS3.ini"
        if ini_path.exists():
            try:
                with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                    in_section = False
                    for line in f:
                        line = line.strip()
                        if line.lower() == "[qgis_mcp]":
                            in_section = True
                        elif in_section:
                            if line.startswith("["):
                                break
                            if line.startswith("port="):
                                return int(line.split("=")[1])
            except Exception:
                pass

    return 9876

DEFAULT_HOST: str = os.environ.get("QGIS_MCP_HOST", "127.0.0.1")
DEFAULT_PORT: int = detect_qgis_port()
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