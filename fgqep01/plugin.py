# -*- coding: utf-8 -*-
"""FGQEP01 Browse Enhancer main plugin class."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt import QtCore
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis, QgsMessageLog

from .event_filter import FGQEP01EventFilter
from .path_resolver import PathResolver
from .settings_dialog import FGQEP01SettingsDialog
from .settings_model import PLUGIN_NAME, PLUGIN_VERSION, SettingsModel


class FGQEP01BrowseEnhancerPlugin(QtCore.QObject):
    """QGIS plugin lifecycle wrapper."""

    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.settings = SettingsModel()
        self.resolver = PathResolver(iface, self.settings, self.log)
        self.event_filter = FGQEP01EventFilter(self)
        self.action_settings = None
        self.settings_dialog = None
        self._startup_timer = None

    def initGui(self):
        icon_path = Path(__file__).with_name("fgqep01_icon.png")
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.action_settings = QAction(icon, PLUGIN_NAME + " Settings", self.iface.mainWindow())
        self.action_settings.triggered.connect(self.open_settings)
        self.iface.addPluginToMenu(PLUGIN_NAME, self.action_settings)

        self.apply_enabled_state(startup=True)

    def unload(self):
        self._cancel_startup_timer()
        self.event_filter.remove()
        if self.settings_dialog is not None:
            try:
                self.settings_dialog.close()
            except Exception:
                pass
            self.settings_dialog = None
        self._startup_timer = None
        if self.action_settings is not None:
            self.iface.removePluginMenu(PLUGIN_NAME, self.action_settings)

    def apply_enabled_state(self, startup=False):
        self.settings.reload_cache()
        self._cancel_startup_timer()
        if not self.settings.cached_bool("enabled", True):
            self.event_filter.remove()
            return

        if startup:
            try:
                delay_ms = int(self.settings.cached_value("startupDelayMs", 10000) or 0)
            except Exception:
                delay_ms = 10000
            delay_ms = max(0, min(60000, delay_ms))
            if delay_ms > 0:
                self._startup_timer = QtCore.QTimer(self)
                self._startup_timer.setSingleShot(True)
                self._startup_timer.timeout.connect(self._install_event_filter_after_startup_delay)
                self._startup_timer.start(delay_ms)
                self.log("Event filter startup delayed by {0} ms".format(delay_ms))
                return

        self.event_filter.install()

    def _install_event_filter_after_startup_delay(self):
        self._startup_timer = None
        self.settings.reload_cache()
        if self.settings.cached_bool("enabled", True):
            self.event_filter.install()
            self.log("Event filter installed after startup delay")

    def _cancel_startup_timer(self):
        if self._startup_timer is not None:
            try:
                self._startup_timer.stop()
                self._startup_timer.deleteLater()
            except Exception:
                pass
            self._startup_timer = None

    def open_settings(self):
        # Floating/modeless settings window. Keep exactly one instance.
        # If it is already open or minimized, bring it back instead of creating
        # another dialog. Do not use exec_() for this floating window.
        if self.settings_dialog is not None:
            try:
                self.settings_dialog.showNormal()
                self.settings_dialog.show()
                self.settings_dialog.raise_()
                self.settings_dialog.activateWindow()
                return
            except RuntimeError:
                self.settings_dialog = None
            except Exception:
                self.settings_dialog = None

        dialog = FGQEP01SettingsDialog(self.iface.mainWindow(), self)
        self.settings_dialog = dialog
        dialog.finished.connect(lambda _=None: self._settings_dialog_closed())
        dialog.destroyed.connect(lambda _=None: self._settings_dialog_destroyed())
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _settings_dialog_closed(self):
        # finished() is emitted by OK/Save, Close, and the window X button.
        # Keep the event filter in sync after settings may have changed.
        self.settings_dialog = None
        self.apply_enabled_state()

    def _settings_dialog_destroyed(self):
        self.settings_dialog = None

    def debug_summary(self):
        counts = self.event_filter.debug_counts
        lines = [
            "FGQEP01 Browse Enhancer v{0}".format(PLUGIN_VERSION),
            "Enabled: {0}".format(self.settings.cached_bool("enabled", True)),
            "Apply to: {0}".format(self.settings.enabled_types_summary()),
            "Last dialog: {0}".format(self.event_filter.last_dialog or "-"),
            "Last widget: {0}".format(self.event_filter.last_widget or "-"),
            "Last result: {0}".format(self.event_filter.last_result or "-"),
            "Dialogs seen: {0}".format(counts.get("dialogs", 0)),
            "Autofill count: {0}".format(counts.get("autofill", 0)),
            "Skipped count: {0}".format(counts.get("skipped", 0)),
            "Preset menus opened: {0}".format(counts.get("menus", 0)),
        ]
        return "\n".join(lines)


    def log(self, message, level=Qgis.Info):
        QgsMessageLog.logMessage(str(message), PLUGIN_NAME, level)
