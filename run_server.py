#!/usr/bin/env python3
"""AiConnect entrypoint for QGIS MCP Server."""

import sys
from pathlib import Path

# 1. Bootstrap vendored libraries and source directory
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "_vendor"))

# 2. Critical stdio isolation: NEVER print debugging output to stdout!
# FastMCP and MCP stdio use stdout exclusively for JSON-RPC messages.
# All logging must go to stderr or file.

import asyncio
from qgis_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())