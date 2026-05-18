# -*- coding: utf-8 -*-
"""Path construction, last-used handling, and missing directory logic."""

from __future__ import annotations

import os
import re

from qgis.PyQt import QtWidgets
from qgis.core import Qgis

from .presets import norm_path, resolve_presets, resolve_preset_items
from .settings_model import (
    AUTOFILL_CONTENT_LAYER_FOLDER,
    AUTOFILL_CONTENT_LAYER_PATH,
    AUTOFILL_CONTENT_LAST_USED,
    AUTOFILL_CONTENT_NONE,
    AUTOFILL_CONTENT_PRESET,
    AUTOFILL_CONTENT_PROJECT_HOME,
    AUTOFILL_CONTENT_QGZ_FOLDER,
    MISSING_LEAVE,
    MISSING_ASK,
    MISSING_AUTO_CREATE,
    MISSING_FALLBACK,
    TYPE_SAVE_EXPORT,
)
from .scope_rules import scope_key
from .tokens import project_home, qgz_folder

RASTER_HINTS = ("raster", "tif", "tiff", "grid", "dem")
VECTOR_DEFAULT_EXT = ".gpkg"


def sanitize_filename(name, fallback="export"):
    text = str(name or "").strip()
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


class PathResolver(object):
    """Build and apply paths for valid QgsFileWidget targets."""

    def __init__(self, iface, settings, log_func=None):
        self.iface = iface
        self.settings = settings
        self.log_func = log_func

    def log(self, message, level=Qgis.Info):
        if self.log_func:
            self.log_func(message, level)

    def last_used_dir(self):
        value = str(self.settings.cached_value("lastUsedDir", "") or "")
        return norm_path(value) if value else ""

    def set_last_used_from_path(self, path):
        if not path:
            return
        directory = path if os.path.isdir(path) else os.path.dirname(path)
        if directory:
            self.settings.set_value("lastUsedDir", directory)

    def active_layer_file_path(self):
        """Return active layer local file path when the selected layer is file-backed."""
        try:
            layer = self.iface.activeLayer()
            if layer is not None:
                source = str(layer.source() or "")
                if "|" in source:
                    source = source.split("|", 1)[0]
                if os.path.isfile(source):
                    return source
        except Exception:
            pass
        return ""

    def active_layer_file_folder(self):
        path = self.active_layer_file_path()
        return os.path.dirname(path) if path else ""

    def current_file_folder(self, dialog=None):
        """Best-effort folder of the current source file/layer.

        Falls back to QGZ folder and project home when no file-backed layer is
        available. This supports the {current_file_folder} preset token.
        """
        try:
            layer = self.iface.activeLayer()
            if layer is not None:
                source = str(layer.source() or "")
                if "|" in source:
                    source = source.split("|", 1)[0]
                if os.path.isfile(source):
                    return os.path.dirname(source)
                if os.path.isdir(source):
                    return source
        except Exception:
            pass
        for path in (qgz_folder(), project_home()):
            if path:
                return path
        return os.path.expanduser("~")

    def token_context(self, dialog=None):
        return {"current_file_folder": self.current_file_folder(dialog)}

    def presets_resolved(self, dialog=None):
        return resolve_presets(self.settings.presets_text(), context=self.token_context(dialog))

    def presets_resolved_detailed(self, dialog=None):
        return resolve_preset_items(self.settings.presets_text(), context=self.token_context(dialog))

    def best_base_dir(self):
        for path in (self.last_used_dir(), project_home()):
            if path and os.path.isdir(path):
                return path
        presets = self.presets_resolved()
        if presets:
            return presets[0][1]
        return self.last_used_dir() or project_home() or os.path.expanduser("~")

    def missing_mode_for_scope(self, scope):
        key = scope_key(scope)
        return str(self.settings.cached_value(key + "/missingDir", MISSING_LEAVE))

    def autofill_content_for_scope(self, scope):
        key = scope_key(scope)
        return str(self.settings.cached_value(key + "/autofillContent", AUTOFILL_CONTENT_NONE) or AUTOFILL_CONTENT_NONE)

    def _first_resolved_preset_path(self, dialog=None):
        try:
            for item in self.presets_resolved_detailed(dialog):
                if len(item) >= 3 and item[2]:
                    return item[1]
        except Exception:
            pass
        try:
            presets = self.presets_resolved(dialog)
            if presets:
                return presets[0][1]
        except Exception:
            pass
        return ""

    def _content_path(self, content, dialog=None):
        if content == AUTOFILL_CONTENT_NONE:
            return ""
        if content == AUTOFILL_CONTENT_LAYER_FOLDER:
            return self.active_layer_file_folder()
        if content == AUTOFILL_CONTENT_LAYER_PATH:
            return self.active_layer_file_path()
        if content == AUTOFILL_CONTENT_QGZ_FOLDER:
            return qgz_folder()
        if content == AUTOFILL_CONTENT_PROJECT_HOME:
            return project_home()
        if content == AUTOFILL_CONTENT_LAST_USED:
            return self.last_used_dir()
        if content == AUTOFILL_CONTENT_PRESET:
            return self._first_resolved_preset_path(dialog)
        return ""

    def _folder_from_path(self, path):
        if not path:
            return ""
        if os.path.isdir(path):
            return path
        root, ext = os.path.splitext(path)
        if ext:
            return os.path.dirname(path)
        return path

    def build_autofill_path(self, fw, dialog, scope):
        """Return the selected autofill content directly.

        The older "autofill path style" setting generated a suggested file
        name from the active layer/dialog. That duplicated the newer
        per-tab Autofill content dropdown, so autofill now means: insert the
        selected content. For folder path boxes, file content is converted to
        its parent folder.
        """
        content = self.autofill_content_for_scope(scope)
        path = self._content_path(content, dialog)
        if not path:
            return ""

        # Folder path boxes should receive folders. If a file path is selected as
        # the autofill content, use its parent folder.
        if scope == "folder":
            return self._folder_from_path(path)

        return path

    def candidate_layer_name(self, dialog):
        try:
            layer = self.iface.activeLayer()
            if layer is not None:
                return layer.name()
        except Exception:
            pass
        if dialog is not None:
            return dialog.windowTitle() or "export"
        return "export"

    def looks_raster(self, dialog, fw):
        text = ""
        try:
            text += " " + str(fw.filePath())
        except Exception:
            pass
        if dialog is not None:
            text += " " + (dialog.windowTitle() or "")
            try:
                text += " " + dialog.metaObject().className()
            except Exception:
                pass
        return any(h in text.lower() for h in RASTER_HINTS)

    def extension_from_dialog(self, dialog):
        if dialog is None:
            return ""
        texts = [dialog.windowTitle() or ""]
        for combo in dialog.findChildren(QtWidgets.QComboBox):
            try:
                texts.append(combo.currentText())
            except Exception:
                pass
        joined = " ".join(texts).lower()
        for token, ext in (
            ("geopackage", ".gpkg"), ("gpkg", ".gpkg"),
            ("shapefile", ".shp"), ("esri shape", ".shp"),
            ("geojson", ".geojson"), ("tiff", ".tif"),
            ("geotiff", ".tif"), ("csv", ".csv"), ("dxf", ".dxf"),
        ):
            if token in joined:
                return ext
        return ""

    def prepare_missing_dir(self, path, scope):
        if not path:
            return ""
        directory = path if os.path.splitext(path)[1] == "" else os.path.dirname(path)
        if not directory:
            return path
        if os.path.isdir(directory):
            self.set_last_used_from_path(path)
            return path
        mode = self.missing_mode_for_scope(scope)
        if mode == MISSING_AUTO_CREATE:
            try:
                os.makedirs(directory, exist_ok=True)
                self.set_last_used_from_path(path)
                return path
            except Exception as exc:
                self.log("Could not create directory: {0}".format(exc), Qgis.Warning)
                return ""
        if mode == MISSING_FALLBACK:
            fallback = project_home() or os.path.expanduser("~")
            return fallback
        if mode == MISSING_LEAVE:
            # Match normal QGIS behaviour: do not create folders automatically.
            # Leave the target unchanged and let QGIS/the calling tool handle validation.
            return ""
        reply = QtWidgets.QMessageBox.question(
            self.iface.mainWindow(),
            "FGQEP01 Browse Enhancer",
            "Directory does not exist:\n{0}\n\nCreate it?".format(directory),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                os.makedirs(directory, exist_ok=True)
                self.set_last_used_from_path(path)
                return path
            except Exception as exc:
                self.log("Could not create directory: {0}".format(exc), Qgis.Warning)
        return ""

    def set_widget_path(self, fw, path, scope):
        if path == "":
            try:
                fw.setFilePath("")
                return True
            except Exception as exc:
                self.log("Clear path failed: {0}".format(exc), Qgis.Warning)
                return False
        path = self.prepare_missing_dir(path, scope)
        if not path:
            return False
        try:
            fw.setFilePath(path)
            self.set_last_used_from_path(path)
            return True
        except Exception as exc:
            self.log("Set path failed: {0}".format(exc), Qgis.Warning)
            return False
