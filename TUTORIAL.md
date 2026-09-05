# QGIS MCP Connector — AiConnect Gateway Setup & Usage Guide

The **QGIS MCP Connector** is an official connector for the **AiConnect Gateway**, enabling AI coding assistants and agentic LLMs (Claude, Gemini, Cursor, ChatGPT) to interactively inspect, analyze, style, and automate desktop GIS workflows in **QGIS Desktop 3.x** and headless PyQGIS environments.

---

## 1. Architecture Flow

```
┌────────────────────────────────────────────────────────┐
│               AI Agent (LLM Client)                    │
└───────────────────────────┬────────────────────────────┘
                            │ stdio / JSON-RPC 2.0
                            ▼
┌────────────────────────────────────────────────────────┐
│                 AiConnect Gateway                      │
│            (Loopback Gateway Port 8788)                │
└───────────────────────────┬────────────────────────────┘
                            │ Spawns connector process
                            ▼
┌────────────────────────────────────────────────────────┐
│            run_server.py (FastMCP Server)              │
│               13 Core MCP Tools Defined                │
└──────┬────────────────────┼────────────────────┬───────┘
       │                    │                    │
 (GUI Session)      (Offscreen Mode)     (Offline Test)
       ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐     ┌──────────────┐
│ QgisGUI      │    │ QgisHeadless │     │ QgisMock     │
│ Adapter      │    │ Adapter      │     │ Adapter      │
└──────┬───────┘    └──────────────┘     └──────────────┘
       │ Length-prefixed TCP Socket (127.0.0.1:9876)
       ▼
┌────────────────────────────────────────────────────────┐
│         QGIS Desktop (qgis-ltr-bin 3.x)                │
│    In-Process Python Bridge: qgis_mcp_plugin           │
└────────────────────────────────────────────────────────┘
```

The connector features a 3-tier fallback execution system:
1. **`QgisGUIAdapter` (Default)**: Connects via loopback TCP socket (`127.0.0.1:9876`) directly into your interactive QGIS Desktop session. Real-time canvas updates, dialogs, and styling appear on your screen immediately.
2. **`QgisHeadlessAdapter`**: Used on headless servers or CI runners where no GUI is running, driving offscreen PyQGIS processing.
3. **`QgisMockAdapter`**: Deterministic offline mock for testing environments where QGIS is not yet installed.

---

## 2. Quick Setup

### Step 1: Install the QGIS MCP Desktop Plugin
Copy the `qgis_mcp_plugin` folder into your QGIS 3 Python plugins directory:
```powershell
# Windows PowerShell
Copy-Item -Recurse -Force "qgis_mcp_plugin" "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\qgis_mcp_plugin"
```

### Step 2: Start QGIS Desktop
1. Open **QGIS Desktop**.
2. Go to **Plugins → Manage and Install Plugins → Installed**, and ensure **QGIS MCP** is checked.
3. The plugin will automatically start its non-blocking socket server listening on `127.0.0.1:9876` (indicated by a message bar alert).

### Step 3: Enable in AiConnect Gateway / Desktop
1. Open **AiConnect Desktop** (or run the AiConnect Gateway on port `8788`).
2. Navigate to **Connectors / MCP Collection**.
3. Enable **QGIS Connector** (`qgis-mcp`).
4. The connector status will display `● Connected`.

---

## 3. Core Tool Tiers (13 Tools)

The connector declares 13 core tools optimized for agent autonomy and low token consumption:

### A. Workspace & Viewport Navigation
* **`qgis_load_project`**: Opens `.qgz` or `.qgs` project files and automatically centers the map camera on the project's data layers (eliminating the $[-1.5 \times 10^{13}, +1.5 \times 10^{13}]$ coordinate camera bug).
* **`qgis_zoom_to`**: Re-centers canvas camera. Supports target `"full"` (all layers), `"layer"` (by layer ID or name), or `"bbox"` (`[xmin, ymin, xmax, ymax]`).
* **`qgis_quick_map`**: Bundled one-shot tool that centers the canvas, renders the map, and saves a PNG preview to disk.
* **`qgis_export_map_image`**: Exports high-resolution raster images (PNG, JPG) of the canvas at specified pixel dimensions.
* **`qgis_get_active_project`**: Returns active project path, title, CRS, layer count, and layer summaries.

### B. Desktop UI & Window State (Vision vs. Non-Vision)
* **`qgis_get_window_state`** *(Structured Text / Zero Images)*:
  - **Recommended for all agents**, especially text-only LLMs that cannot process image files.
  - Returns structured JSON: main window title, open non-main dialogs, active modal dialogs, visible dock panels (Layers, Browser, Processing), selected layer, and status bar coordinates/scale/CRS.
* **`qgis_get_ui_screenshot`** *(Visual Desktop Screenshot)*:
  - **Specifically designed for multimodal vision-capable models** (GPT-4o, Claude 3.5 Sonnet, Gemini).
  - Captures an image of the actual QGIS Desktop interface (toolbars, layers tree, dialogs, map view) and saves it to `.png` or `.jpg`.
  - Supports targets: `"active"` (focused modal/dialog), `"main"` (full application window), or `"canvas"` (map only).

### C. Inspection & Symbology
* **`qgis_inspect_layer`**: Returns layer geometry type, feature count, field attributes schema, bounding box extent, and CRS units (`is_geographic`, `unit_warning`).
* **`qgis_set_single_symbol`**: Styles vector layers directly using hex color codes (e.g. `#39FF14` neon green), stroke width in mm, stroke color, and opacity (0.0 to 1.0).

### D. Processing & Spatial Analysis
* **`qgis_run_processing`**: Runs any native QGIS or GDAL algorithm (`native:buffer`, `native:clip`, `gdal:contour`, etc.) with automatic case-insensitive parameter normalization (`input` -> `INPUT`).
* **`qgis_get_algorithm_spec`**: Introspects processing algorithm parameters, types, required/optional flags, and default values.

### E. Health & Diagnostics
* **`qgis_get_capabilities`**: Returns QGIS runtime version, GDAL version, Python runtime, and active adapter mode (`gui`, `headless`, `mock`).
* **`qgis_health_check`**: Probes TCP socket bridge connectivity and PyQGIS health.

---

## 4. Critical Spatial Agent Guidelines

When instructing an AI agent to perform spatial tasks, keep these three rules in mind:

### 1. The In-Memory Layer Evaporation Trap
* **The Trap**: In QGIS, if `OUTPUT` is omitted or set to `'memory:'`, features exist **only in temporary RAM**. When QGIS closes or the project reloads, all features evaporate.
* **The Fix**: The connector actively checks and alerts the agent if an ephemeral layer was created. Agents should always specify a persistent file path in `parameters['OUTPUT']` (e.g. `C:/data/output.gpkg`).

### 2. Coordinate Systems & Metric Distances
* **The Trap**: In Geographic CRS (`EPSG:4326` WGS 84), coordinates are in **degrees**, not meters. Running a 100-unit buffer on a geographic layer creates a buffer spanning the entire planet ($1^\circ \approx 111\text{ km}$).
* **The Fix**: `qgis_inspect_layer` returns `is_geographic: true` and a warning. `qgis_run_processing` actively checks CRS and alerts the agent if metric operations are executed on geographic layers without reprojection.

### 3. Identifier Precision
* **The Trap**: If multiple layers share the same display name (e.g. repeated buffers named `"Buffered"`), referring to them by display name creates ambiguity.
* **The Fix**: `qgis_inspect_layer` and `qgis_get_active_project` provide both `name` and the unique alphanumeric `layer_id`. Handlers prioritize exact `layer_id` lookups over display names.

---

## 5. Verification & Packaging

To verify connector health against the 15 AiConnect release gates:
```powershell
$env:PYTHONHOME = "C:\Program Files\QGIS 3.44.14\apps\Python312"
$env:PATH = "C:\Program Files\QGIS 3.44.14\bin;C:\Program Files\QGIS 3.44.14\apps\Python312;$env:PATH"
python scripts/verify_connector.py
```

To build the standalone `.acpkg` archive for the AiConnect Gateway:
```powershell
python pack_acpkg.py
```
This generates `dist/qgis-mcp-1.0.0-windows-x64.acpkg` and its corresponding `.sha256` checksum.
