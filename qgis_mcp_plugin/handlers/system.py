"""Handlers for QGIS itself: health, versions, message log, plugins, settings."""

import contextlib
import io
import os
import sys
import traceback

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc  # noqa: UP017  (fallback path: datetime.UTC unavailable pre-3.11)

from typing import ClassVar

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsSettings,
    QgsVectorLayer,
)
from qgis.utils import active_plugins, available_plugins, pluginMetadata, reloadPlugin

from ..compat import MSG_INFO
from ..constants import plugin_version
from ..errors import CommandError
from ..registry import command


class SystemHandlers:
    """QGIS health, versions, message log, plugin list and settings."""

    @command
    def ping(self, **kwargs):
        return {"pong": True}

    @command
    def diagnose(self, **kwargs):
        """Run diagnostic checks and return health status."""
        checks = []
        overall = "healthy"

        # 1. QGIS info
        try:
            from qgis.PyQt.QtCore import QT_VERSION_STR as qt_ver

            info = {
                "qgis_version": Qgis.version(),
                "python_version": sys.version.split()[0],
                "qt_version": qt_ver,
            }
            checks.append({"name": "qgis", "status": "ok", "detail": info})
        except Exception as e:
            checks.append({"name": "qgis", "status": "error", "detail": str(e)})
            overall = "error"

        # 2. Plugin version
        try:
            checks.append({"name": "plugin_version", "status": "ok", "detail": plugin_version()})
        except Exception as e:
            checks.append({"name": "plugin_version", "status": "error", "detail": str(e)})
            overall = "degraded" if overall == "healthy" else overall

        # 3. Connected clients
        client_count = len(self.clients)
        checks.append({"name": "connected_clients", "status": "ok", "detail": client_count})

        # 3b. Which MCP server versions have talked to this plugin. The client
        # adds its own comparison (version_match), but reporting it from the
        # plugin's side covers several clients on one QGIS, where only some are
        # out of date - and it is empty against a server older than 0.10.
        seen = sorted(self.client_versions)
        drifted = [v for v in seen if v != plugin_version()]
        detail = {"seen": seen, "plugin": plugin_version(), "drifted": drifted}
        # The update command each drifted client announced for itself. Absent
        # against a client too old to send one.
        fixes = {v: self.client_fixes[v] for v in drifted if v in self.client_fixes}
        if fixes:
            detail["fixes"] = fixes
        checks.append(
            {
                "name": "client_versions",
                "status": "mismatch" if drifted else "ok",
                "detail": detail,
            }
        )

        # 4. Processing providers
        try:
            registry = QgsApplication.processingRegistry()
            providers = [p.id() for p in registry.providers() if p.isActive()]
            checks.append({"name": "processing_providers", "status": "ok", "detail": providers})
        except Exception as e:
            checks.append({"name": "processing_providers", "status": "degraded", "detail": str(e)})
            overall = "degraded" if overall == "healthy" else overall

        # 5. Project status
        try:
            project = QgsProject.instance()
            checks.append(
                {
                    "name": "project",
                    "status": "ok",
                    "detail": {
                        "loaded": bool(project.fileName()),
                        "path": project.fileName() or None,
                        "layer_count": len(project.mapLayers()),
                    },
                }
            )
        except Exception as e:
            checks.append({"name": "project", "status": "error", "detail": str(e)})
            overall = "degraded" if overall == "healthy" else overall

        return {"status": overall, "checks": checks}

    @command
    def get_qgis_info(self, **kwargs):
        info = {
            "qgis_version": Qgis.version(),
            "profile_folder": QgsApplication.qgisSettingsDirPath(),
            "plugins_count": len(active_plugins),
            # Identity, so a client driving several QGIS windows can tell which one
            # answered rather than inferring it from the port. The pid is unique and
            # stable; the window title is what the user reads in the taskbar and
            # already carries the project name.
            "pid": os.getpid(),
        }
        if self.iface is not None:
            with contextlib.suppress(Exception):
                info["window_title"] = self.iface.mainWindow().windowTitle()
        return info

    @command
    def execute_code(self, code, **kwargs):
        QgsMessageLog.logMessage(f"Executing code ({len(code)} chars)", self.LOG_TAG, MSG_INFO)
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            namespace = {
                "qgis": Qgis,
                "QgsProject": QgsProject,
                "iface": self.iface,
                "QgsApplication": QgsApplication,
                "QgsVectorLayer": QgsVectorLayer,
                "QgsRasterLayer": QgsRasterLayer,
                "QgsCoordinateReferenceSystem": QgsCoordinateReferenceSystem,
            }

            exec(code, namespace)  # nosec B102 - intentional: MCP execute_code tool

            return {
                "executed": True,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }
        except Exception as e:
            error_traceback = traceback.format_exc()
            return {
                "executed": False,
                "error": str(e),
                "traceback": error_traceback,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    _LEVEL_MAP: ClassVar[dict[int, str]] = {0: "info", 1: "warning", 2: "critical", 3: "success"}

    def _capture_message(self, message, tag, level, *_extra):
        """Capture a message log entry into the deque.

        QGIS 4.x messageReceivedWithFormat sends a 4th arg (StringFormat);
        *_extra absorbs it so the same handler works for both signals.
        """
        self._message_log.append(
            {
                "tag": tag,
                "message": message,
                "level": self._LEVEL_MAP.get(int(level), str(level)),
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
        )

    @command
    def get_message_log(self, level=None, tag=None, limit=100, **kwargs):
        entries = list(self._message_log)
        entries.reverse()  # newest first
        if level:
            entries = [e for e in entries if e["level"] == level]
        if tag:
            entries = [e for e in entries if e["tag"] == tag]
        entries = entries[:limit]
        return {"messages": entries, "count": len(entries)}

    @command
    def list_plugins(self, enabled_only=False, **kwargs):
        result = []
        names = list(active_plugins) if enabled_only else list(available_plugins)
        for name in sorted(names):
            result.append(
                {
                    "name": name,
                    "enabled": name in active_plugins,
                    "version": pluginMetadata(name, "version") or "",
                    "path": pluginMetadata(name, "path") or "",
                }
            )
        return {"plugins": result, "count": len(result)}

    @command
    def get_plugin_info(self, plugin_name, **kwargs):
        if plugin_name not in available_plugins and plugin_name not in active_plugins:
            raise CommandError(f"Plugin not found: {plugin_name}")
        return {
            "name": plugin_name,
            "enabled": plugin_name in active_plugins,
            "version": pluginMetadata(plugin_name, "version") or "",
            "description": pluginMetadata(plugin_name, "description") or "",
            "author": pluginMetadata(plugin_name, "author") or "",
            "path": pluginMetadata(plugin_name, "path") or "",
        }

    @command
    def reload_plugin(self, plugin_name, **kwargs):
        if plugin_name == "qgis_mcp_plugin":
            raise CommandError("Cannot reload MCP plugin (would break the connection)")
        if plugin_name not in active_plugins:
            raise CommandError(f"Plugin not active: {plugin_name}")
        reloadPlugin(plugin_name)
        return {"reloaded": plugin_name, "ok": True}

    @command
    def get_setting(self, key, **kwargs):
        settings = QgsSettings()
        value = settings.value(key)
        return {
            "key": key,
            "value": value,
            "exists": settings.contains(key),
        }

    @command
    def set_setting(self, key, value, **kwargs):
        settings = QgsSettings()
        settings.setValue(key, value)
        return {"ok": True, "key": key}

    @command
    def get_window_state(self, **kwargs):
        """Get structured metadata of active QGIS window, dialogs, and panels.
        
        Pure text/JSON, zero images - ideal for all agents, especially non-vision agents.
        """
        from qgis.PyQt.QtWidgets import QApplication, QDockWidget, QDialog

        main_win = self.iface.mainWindow() if self.iface else None
        active_win = QApplication.activeWindow()
        active_modal = QApplication.activeModalWidget()

        window_title = main_win.windowTitle() if main_win else (active_win.windowTitle() if active_win else "")

        modal_title = None
        if active_modal:
            modal_title = f"{active_modal.windowTitle()} ({type(active_modal).__name__})"

        open_dialogs = []
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w != main_win and w.windowTitle():
                open_dialogs.append(f"{w.windowTitle()} ({type(w).__name__})")

        visible_panels = []
        if main_win:
            for dock in main_win.findChildren(QDockWidget):
                if dock.isVisible() and dock.windowTitle():
                    visible_panels.append(dock.windowTitle())

        active_layer_name = None
        active_layer_id = None
        if self.iface and self.iface.activeLayer():
            al = self.iface.activeLayer()
            active_layer_name = al.name()
            active_layer_id = al.id()

        status_bar = {}
        canvas_extent = None
        if self.iface and self.iface.mapCanvas():
            canvas = self.iface.mapCanvas()
            ext = canvas.extent()
            status_bar["scale"] = f"1:{int(canvas.scale())}"
            status_bar["crs"] = canvas.mapSettings().destinationCrs().authid()
            status_bar["center"] = [canvas.center().x(), canvas.center().y()]
            canvas_extent = {
                "xmin": ext.xMinimum(),
                "ymin": ext.yMinimum(),
                "xmax": ext.xMaximum(),
                "ymax": ext.yMaximum(),
            }

        return {
            "window_title": window_title,
            "active_modal_dialog": modal_title,
            "open_dialogs": open_dialogs,
            "visible_panels": sorted(list(set(visible_panels))),
            "selected_layer": active_layer_name,
            "selected_layer_id": active_layer_id,
            "status_bar": status_bar,
            "canvas_extent": canvas_extent,
        }

    @command
    def get_ui_screenshot(self, target="active", output_path=None, format="png", **kwargs):
        """Capture a visual screenshot of the QGIS desktop window or dialog.
        
        Saves to an image file (PNG/JPG).
        Target options: 'active' (active modal/dialog or main window), 'main' (full QGIS window),
        'canvas' (map canvas only).
        Supported image file formats: png, jpg/jpeg.
        """
        import os
        from pathlib import Path
        from qgis.PyQt.QtWidgets import QApplication

        main_win = self.iface.mainWindow() if self.iface else None
        active_win = QApplication.activeWindow()
        active_modal = QApplication.activeModalWidget()

        if target == "canvas" and self.iface and self.iface.mapCanvas():
            widget = self.iface.mapCanvas()
            resolved_target = "canvas"
        elif target == "main" and main_win:
            widget = main_win
            resolved_target = "main_window"
        else:
            widget = active_modal or active_win or main_win
            resolved_target = type(widget).__name__ if widget else "unknown"

        if not widget:
            raise CommandError("No visible QGIS window or widget available to capture.")

        pixmap = widget.grab()

        if not output_path:
            import tempfile
            temp_dir = tempfile.gettempdir()
            clean_fmt = "jpg" if format.lower() in ["jpg", "jpeg"] else "png"
            output_path = os.path.join(temp_dir, f"qgis_ui_screenshot.{clean_fmt}")

        out_path_obj = Path(output_path)
        out_path_obj.parent.mkdir(parents=True, exist_ok=True)
        save_fmt = "JPEG" if out_path_obj.suffix.lower() in [".jpg", ".jpeg"] or format.lower() in ["jpg", "jpeg"] else "PNG"
        saved = pixmap.save(str(out_path_obj), save_fmt)
        if not saved:
            raise CommandError(f"Failed to save screenshot image to {output_path}")

        file_size = out_path_obj.stat().st_size if out_path_obj.exists() else 0

        return {
            "output_path": str(out_path_obj.as_posix()),
            "target": resolved_target,
            "widget_title": widget.windowTitle() if hasattr(widget, "windowTitle") else "",
            "width": pixmap.width(),
            "height": pixmap.height(),
            "file_size_bytes": file_size,
            "format": save_fmt.lower(),
        }
