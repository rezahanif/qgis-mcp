# QGIS Connection Setup Guide

## 1. Prerequisites
- QGIS 3.x installed on your Windows machine.
- AiConnect Gateway running on loopback port `8788`.

## 2. Install the QGIS Plugin

The plugin ships inside the connector package. Install it automatically:

```bash
# The connector copies the plugin to your QGIS profile on first run.
# Or manually copy qgis_mcp_plugin/ to:
#   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\qgis_mcp_plugin\
```

## 3. Start the Plugin in QGIS

1. Open **QGIS Desktop**.
2. Go to **Plugins → QGIS MCP → Start Server**.
3. The plugin listens on `127.0.0.1:9876` (configurable via `QGIS_MCP_PORT`).

## 4. Connect in AiConnect Desktop

1. Open **AiConnect Desktop** → **MCP Collection**.
2. Find **QGIS GIS Connector** and click **Enable**.

## 5. Verify Connection

The connector status will show `● Connected` in AiConnect Desktop.

## 6. Start Mapping

Your AI agent can now:
- **Load layers** — vector (Shapefile, GeoPackage) and raster (GeoTIFF) data
- **Edit features** — create, modify, delete geometries and attributes
- **Run analysis** — buffer, clip, intersect, spatial joins via Processing toolbox
- **Render maps** — capture the canvas as an image
- **Export layouts** — generate print-ready maps with scale bars, legends, north arrows
- **Style layers** — apply symbology, color ramps, labels

### Example Agent Prompts

```
Load the shapefile at D:/data/roads.shp, style it by road class with
different colors, and take a screenshot of the map canvas.
```

```
Buffer all parcel features by 100 meters, clip the result to the
municipality boundary, and export the output as a new GeoPackage.
```

```
Create a print layout with a title, the current map view, a scale bar,
and a north arrow. Export it as PDF to D:/output/map.pdf.
```

## Multi-Instance

Connect to multiple QGIS windows simultaneously:

```bash
# Environment variable format:
QGIS_MCP_INSTANCES="default=9876,lab=9877,field=192.168.1.5:9876"
```

Each instance is an independent QGIS window with its own project.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QGIS_MCP_HOST` | `127.0.0.1` | TCP bridge host |
| `QGIS_MCP_PORT` | `9876` | TCP bridge port |
| `QGIS_MCP_INSTANCES` | (unset) | Multi-instance config: `name=port,name=host:port` |
| `QGIS_MCP_LOG_FILE` | `~/.local/share/qgis-mcp/server.log` | Log file path |
| `QGIS_MCP_LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `QGIS_MCP_AUTO_CONFIRM` | (unset) | Set to `0` to elicit confirmation for destructive operations |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection Refused` | QGIS plugin not running. Start it via **Plugins → QGIS MCP → Start Server**. |
| `Unknown QGIS instance` | Check `QGIS_MCP_INSTANCES` format. |
| `Layer not found` | Call `get_layers` to list valid layer IDs. |
| Slow render | Large canvases take time. Increase timeout or reduce canvas size. |
