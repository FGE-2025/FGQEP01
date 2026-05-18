# -*- coding: utf-8 -*-
"""Target classification and button-type rules for FGQEP01 Browse Enhancer."""

from __future__ import annotations

from qgis.PyQt import QtWidgets

from .settings_model import (
    TYPE_FOLDER,
    TYPE_LEGACY,
    TYPE_OPEN_FILE,
    TYPE_SAVE_EXPORT,
    TYPE_SAVE_FILE,
    TYPE_PREFIX,
    SCOPE_SAVE_ONLY,
    SCOPE_SAVE_FOLDER,
    SCOPE_ALL_WIDGETS,
    SCOPE_LEGACY,
)

KIND_SAVE_FILE = "save_file"
KIND_SELECT_FOLDER = "select_folder"
KIND_OPEN_FILE = "open_file"
KIND_UNKNOWN = "unknown"

SAVE_EXPORT_HINTS = (
    "save features as", "save vector layer as", "save raster layer as", "raster save as",
    "export", "save as", "save layer", "layout export", "print layout", "export map",
)


def widget_text(widget):
    parts = []
    for attr in ("objectName", "toolTip", "windowTitle"):
        try:
            value = getattr(widget, attr)()
            if value:
                parts.append(str(value))
        except Exception:
            pass
    try:
        parts.append(widget.metaObject().className())
    except Exception:
        pass
    return " ".join(parts).lower()


def is_save_export_dialog(dialog):
    if dialog is None:
        return False
    text = widget_text(dialog)
    return any(hint in text for hint in SAVE_EXPORT_HINTS)


def classify_file_widget(fw):
    """Best-effort QgsFileWidget type detection without broad GUI heuristics."""
    text = widget_text(fw)
    # Prefer explicit QgsFileWidget storage/mode methods if available.
    for method in ("storageMode", "fileWidgetButtonVisible", "dialogTitle"):
        try:
            value = getattr(fw, method)()
            text += " " + str(value).lower()
        except Exception:
            pass
    if "directory" in text or "folder" in text or "getexistingdirectory" in text:
        return KIND_SELECT_FOLDER
    if "open" in text or "input" in text or "existing" in text or "getopen" in text:
        return KIND_OPEN_FILE
    if "save" in text or "output" in text or "export" in text or "getsave" in text:
        return KIND_SAVE_FILE
    return KIND_UNKNOWN


def button_type_for_target(settings, fw, dialog=None):
    """Return the user-facing button/path-box type for a valid QgsFileWidget target."""
    if dialog is not None and is_save_export_dialog(dialog):
        return TYPE_SAVE_EXPORT
    kind = classify_file_widget(fw)
    if kind == KIND_SELECT_FOLDER:
        return TYPE_FOLDER
    if kind == KIND_OPEN_FILE:
        return TYPE_OPEN_FILE
    if kind == KIND_SAVE_FILE:
        return TYPE_SAVE_FILE
    # Unknown real QgsFileWidget path boxes are safest as save-file boxes, and only work if enabled.
    return TYPE_SAVE_FILE


def target_allowed(settings, fw, dialog=None):
    button_type = button_type_for_target(settings, fw, dialog)
    return settings.type_enabled(button_type), button_type


def autofill_allowed(settings, button_type):
    prefix = TYPE_PREFIX.get(button_type, "save_export")
    if button_type == TYPE_SAVE_EXPORT:
        return settings.type_enabled(TYPE_SAVE_EXPORT)
    if button_type in (TYPE_SAVE_FILE, TYPE_FOLDER, TYPE_OPEN_FILE):
        return settings.type_enabled(button_type) and settings.cached_bool(prefix + "/autofillEnabled", False)
    if button_type == TYPE_LEGACY:
        return False
    return False


def scope_key(scope_or_type):
    """Compatibility helper used by path_resolver."""
    if scope_or_type == SCOPE_SAVE_ONLY:
        return "save_export"
    if scope_or_type == SCOPE_SAVE_FOLDER:
        return "save_file"
    if scope_or_type == SCOPE_ALL_WIDGETS:
        return "open_file"
    if scope_or_type == SCOPE_LEGACY:
        return "legacy"
    return TYPE_PREFIX.get(scope_or_type, str(scope_or_type or "save_export"))

# Compatibility functions retained for older code references.
def dialog_allowed(scope, dialog):
    if not isinstance(dialog, QtWidgets.QDialog):
        return False
    if scope == SCOPE_SAVE_ONLY:
        return is_save_export_dialog(dialog)
    return True


def widget_allowed(scope, fw, dialog=None):
    return True
