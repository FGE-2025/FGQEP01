# -*- coding: utf-8 -*-
"""Settings constants and helper model for FGQEP01 Browse Enhancer."""

from __future__ import annotations

from qgis.core import QgsSettings

PLUGIN_NAME = "FGQEP01 Browse Enhancer"
PLUGIN_VERSION = "0.9.0"
SETTINGS_NS = "FGQEP01/BrowseEnhancer"

# User-facing button/path-box types. These replace the old incremental scope tabs.
TYPE_SAVE_EXPORT = "save_export"
TYPE_SAVE_FILE = "save_file"
TYPE_FOLDER = "folder"
TYPE_OPEN_FILE = "open_file"
TYPE_LEGACY = "legacy"

TYPE_LABELS = {
    TYPE_SAVE_EXPORT: "Save / Export buttons",
    TYPE_SAVE_FILE: "Save-file path boxes",
    TYPE_FOLDER: "Folder path boxes",
    TYPE_OPEN_FILE: "Open-file path boxes",
    TYPE_LEGACY: "Custom / Advanced Buttons",
}

TYPE_PREFIX = {
    TYPE_SAVE_EXPORT: "save_export",
    TYPE_SAVE_FILE: "save_file",
    TYPE_FOLDER: "folder",
    TYPE_OPEN_FILE: "open_file",
    TYPE_LEGACY: "legacy",
}

# Backward-compatible old scope constants. Kept so older code/settings do not crash.
SCOPE_SAVE_ONLY = "save_only"
SCOPE_SAVE_FOLDER = "all_path_buttons"
SCOPE_ALL_WIDGETS = "all_qgsfilewidgets"
SCOPE_LEGACY = "legacy_heuristic"
SCOPE_LABELS = {
    SCOPE_SAVE_ONLY: "Save/Export dialogs only",
    SCOPE_SAVE_FOLDER: "Save and folder path boxes",
    SCOPE_ALL_WIDGETS: "All file path boxes",
    SCOPE_LEGACY: "Legacy fallback detection",
}
SCOPE_PREFIX = {
    SCOPE_SAVE_ONLY: TYPE_PREFIX[TYPE_SAVE_EXPORT],
    SCOPE_SAVE_FOLDER: TYPE_PREFIX[TYPE_SAVE_FILE],
    SCOPE_ALL_WIDGETS: TYPE_PREFIX[TYPE_OPEN_FILE],
    SCOPE_LEGACY: TYPE_PREFIX[TYPE_LEGACY],
}

ACTION_NATIVE = "native"
ACTION_SHOW_MENU = "show_menu"
ACTION_LAST_USED = "last_used"
ACTION_PROJECT_HOME = "project_home"
ACTION_AUTOFILL = "autofill"
ACTION_CLEAR_THEN_AUTOFILL = "clear_then_autofill"
ACTION_CLEAR_PATH = "clear_path"
ACTION_COPY_PATH = "copy_path"
ACTION_OPEN_FOLDER = "open_folder"
ACTION_DO_NOTHING = "do_nothing"

ACTION_LABELS = {
    ACTION_NATIVE: "Normal QGIS browse",
    ACTION_SHOW_MENU: "Show preset path menu",
    ACTION_LAST_USED: "Set path to last used folder",
    ACTION_PROJECT_HOME: "Set path to project home folder",
    ACTION_AUTOFILL: "Run autofill if empty",
    ACTION_CLEAR_THEN_AUTOFILL: "Clear then autofill",
    ACTION_CLEAR_PATH: "Clear path",
    ACTION_COPY_PATH: "Copy current path",
    ACTION_OPEN_FOLDER: "Open current folder",
    ACTION_DO_NOTHING: "Do nothing",
}

CLICK_NATIVE = ACTION_NATIVE
CLICK_LAST_USED = ACTION_LAST_USED
CLICK_PROJECT_HOME = ACTION_PROJECT_HOME
CLICK_SHOW_MENU = ACTION_SHOW_MENU
CLICK_PREFILL_ONLY = ACTION_AUTOFILL
CLICK_LABELS = ACTION_LABELS

MOUSE_LEFT_CLICK = "left_click"
MOUSE_LEFT_DOUBLE = "left_double_click"
MOUSE_LEFT_HOLD = "left_hold"
MOUSE_RIGHT_CLICK = "right_click"
MOUSE_RIGHT_DOUBLE = "right_double_click"
MOUSE_MIDDLE_CLICK = "middle_click"

MOUSE_ACTIONS = [
    (MOUSE_LEFT_CLICK, "Left click"),
    (MOUSE_LEFT_DOUBLE, "Left double-click"),
    (MOUSE_LEFT_HOLD, "Left click and hold"),
    (MOUSE_RIGHT_CLICK, "Right click"),
    (MOUSE_RIGHT_DOUBLE, "Right double-click"),
    (MOUSE_MIDDLE_CLICK, "Middle click"),
]

AUTOFILL_CONTENT_NONE = "none"
AUTOFILL_CONTENT_LAYER_FOLDER = "layer_file_folder"
AUTOFILL_CONTENT_LAYER_PATH = "layer_file_path"
AUTOFILL_CONTENT_QGZ_FOLDER = "qgz_folder"
AUTOFILL_CONTENT_PROJECT_HOME = "project_home"
AUTOFILL_CONTENT_LAST_USED = "last_used"
AUTOFILL_CONTENT_PRESET = "preset_folder"
AUTOFILL_CONTENT_LABELS = {
    AUTOFILL_CONTENT_NONE: "Fill nothing",
    AUTOFILL_CONTENT_LAYER_FOLDER: "Current / selected layer file folder",
    AUTOFILL_CONTENT_LAYER_PATH: "Current / selected layer file path",
    AUTOFILL_CONTENT_QGZ_FOLDER: "QGZ project folder",
    AUTOFILL_CONTENT_PROJECT_HOME: "Project home folder",
    AUTOFILL_CONTENT_LAST_USED: "Last used folder",
    AUTOFILL_CONTENT_PRESET: "Preset folder...",
}

MISSING_LEAVE = "leave"
MISSING_ASK = "ask"
MISSING_AUTO_CREATE = "auto_create"
MISSING_FALLBACK = "fallback"
MISSING_LABELS = {
    MISSING_LEAVE: "Leave unchanged / let QGIS handle it",
    MISSING_ASK: "Ask before creating folder",
    MISSING_AUTO_CREATE: "Create missing folder automatically",
    MISSING_FALLBACK: "Use project home instead",
}

# Preset path menu configuration.
MENU_LAST_USED = "last_used"
MENU_CURRENT_FILE_FOLDER = "current_file_folder"
MENU_PROJECT_HOME = "project_home"
MENU_QGZ_FOLDER = "qgz_folder"
MENU_PRESET_FOLDERS = "preset_folders"
MENU_DESKTOP = "desktop"
MENU_DOCUMENTS = "documents"
MENU_DOWNLOADS = "downloads"
MENU_ITEMS = [
    (MENU_LAST_USED, "Last used folder"),
    (MENU_CURRENT_FILE_FOLDER, "Current file folder"),
    (MENU_PROJECT_HOME, "Project home"),
    (MENU_QGZ_FOLDER, "QGZ folder"),
    (MENU_PRESET_FOLDERS, "Preset folders"),
    (MENU_DESKTOP, "Desktop"),
    (MENU_DOCUMENTS, "Documents"),
    (MENU_DOWNLOADS, "Downloads"),
]
DEFAULT_MENU_ORDER = ",".join([MENU_LAST_USED, MENU_CURRENT_FILE_FOLDER, MENU_PROJECT_HOME, MENU_QGZ_FOLDER, MENU_PRESET_FOLDERS, MENU_DESKTOP, MENU_DOCUMENTS, MENU_DOWNLOADS])
UNRESOLVED_HIDE = "hide"
UNRESOLVED_DISABLE = "disable"
UNRESOLVED_LABELS = {
    UNRESOLVED_HIDE: "Hide unresolved menu items",
    UNRESOLVED_DISABLE: "Show unresolved menu items disabled",
}

DEFAULT_PRESETS = (
    "Preset1={current_file_folder}\n"
    "Preset2={project_home}\n"
    "Preset3={qgz_folder}"
)


def action_key(prefix, mouse_action):
    return "%s/action_%s" % (prefix, mouse_action)


DEFAULTS = {
    "enabled": True,
    "apply/save_export": True,
    "apply/save_file": False,
    "apply/folder": False,
    "apply/open_file": False,
    "apply/legacy": False,
    "debugBorders": False,
    "holdDelayMs": 500,
    "startupDelayMs": 10000,
    "preset_menu/show_last_used": True,
    "preset_menu/show_current_file_folder": True,
    "preset_menu/show_project_home": True,
    "preset_menu/show_qgz_folder": True,
    "preset_menu/show_preset_folders": True,
    "preset_menu/show_desktop": False,
    "preset_menu/show_documents": False,
    "preset_menu/show_downloads": False,
    "preset_menu/create_missing_on_select": True,
    "preset_menu/remember_selected_as_last_used": True,
    "preset_menu/unresolvedMode": UNRESOLVED_DISABLE,
    "preset_menu/order": DEFAULT_MENU_ORDER,
    "presets": DEFAULT_PRESETS,
    "lastUsedDir": "",
    "save_export/autofillContent": AUTOFILL_CONTENT_LAYER_PATH,
    "save_export/rasterNoExt": True,
    "save_export/missingDir": MISSING_LEAVE,
    "save_file/autofillEnabled": False,
    "save_file/autofillContent": AUTOFILL_CONTENT_PRESET,
    "save_file/missingDir": MISSING_LEAVE,
    "folder/autofillEnabled": False,
    "folder/autofillContent": AUTOFILL_CONTENT_LAYER_FOLDER,
    "folder/missingDir": MISSING_LEAVE,
    "open_file/autofillEnabled": True,
    "open_file/autofillContent": AUTOFILL_CONTENT_LAYER_PATH,
    "open_file/missingDir": MISSING_LEAVE,
    "legacy/enabled": False,
    "legacy/debugBypass": False,
    "legacy/middleInspectEnabled": False,
    "legacy/bypassDialogAllowlist": False,
    "legacy/bypassButtonTextAllowlist": False,
    "legacy/bypassButtonObjectAllowlist": False,
    "legacy/bypassTargetObjectAllowlist": False,
    "legacy/textDetection": False,
    "legacy/tooltipDetection": False,
    "legacy/objectNameDetection": False,
    "legacy/dialogAllowlist": "Another DXF Import/Converter\n",
    "legacy/buttonTextAllowlist": "Browse\n",
    "legacy/buttonObjectAllowlist": "browseZielPfadOrDatei",
    "legacy/targetObjectAllowlist": "txtZielPfad",
    "legacy/detectQToolButton": True,
    "legacy/detectQPushButton": True,
    "legacy/detectQCommandLinkButton": False,
    "legacy/detectQCheckBox": False,
    "legacy/detectQRadioButton": False,
    "legacy/detectOtherAbstractButton": False,
    "legacy/pathSearchMode": "nearby",
    "legacy/missingDir": MISSING_LEAVE,
    "legacy/autofillContent": AUTOFILL_CONTENT_LAYER_PATH,
    # old setting kept as harmless compatibility value
    "activeScope": SCOPE_SAVE_ONLY,
    "save_export/autofillMode": "dir_and_name",
    "save_file/autofillMode": "dir_only",
    "folder/autofillMode": "dir_only",
    "open_file/autofillMode": "dir_only",
    "save_only/autofillMode": "dir_only",
}

for prefix in ("save_export", "save_file", "folder", "open_file", "legacy"):
    DEFAULTS[action_key(prefix, MOUSE_LEFT_CLICK)] = ACTION_NATIVE
    DEFAULTS[action_key(prefix, MOUSE_LEFT_DOUBLE)] = ACTION_DO_NOTHING
    DEFAULTS[action_key(prefix, MOUSE_LEFT_HOLD)] = ACTION_DO_NOTHING
    DEFAULTS[action_key(prefix, MOUSE_RIGHT_CLICK)] = ACTION_SHOW_MENU
    DEFAULTS[action_key(prefix, MOUSE_RIGHT_DOUBLE)] = ACTION_DO_NOTHING
    DEFAULTS[action_key(prefix, MOUSE_MIDDLE_CLICK)] = ACTION_DO_NOTHING

# v0.6.2: normal left-click is always native QGIS browse and is no longer configurable.
# Normal left double-click remains configurable. Shift+left double-click is a diagnostic
# shortcut that opens the plugin folder. Right double-click is dropped/ignored.

# Migration aliases from v0.3.x.
DEFAULTS["save_only/rasterNoExt"] = DEFAULTS["save_export/rasterNoExt"]
DEFAULTS["save_only/missingDir"] = DEFAULTS["save_export/missingDir"]
DEFAULTS["save_folder/autofillEnabled"] = DEFAULTS["save_file/autofillEnabled"]
DEFAULTS["save_folder/missingDir"] = DEFAULTS["save_file/missingDir"]
DEFAULTS["all_widgets/autofillSaveEnabled"] = False
DEFAULTS["all_widgets/autofillFolderEnabled"] = False
DEFAULTS["all_widgets/autofillOpenEnabled"] = False


def safe_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


class SettingsModel(object):
    """QgsSettings wrapper with a safe in-memory cache for event-filter use.

    QGIS/Qt global event filters can run during native dialog and Windows shell
    activity. Reading QgsSettings/QSettings repeatedly from those hot paths can
    be unstable and slow, so runtime event code must use cached_* helpers only.
    """

    def __init__(self):
        self._settings = QgsSettings()
        self._cache = {}
        self.reload_cache()

    def key(self, name):
        return SETTINGS_NS + "/" + name

    def reload_cache(self):
        """Refresh the in-memory settings cache from QgsSettings.

        This is intended for plugin startup and after the settings dialog saves.
        It should not be called from eventFilter().
        """
        cache = {}
        for name, default in DEFAULTS.items():
            try:
                cache[name] = self._settings.value(self.key(name), default)
            except Exception:
                cache[name] = default
        self._cache = cache
        return cache

    def value(self, name, default=None):
        """Live QgsSettings read. Do not call this from event-filter paths."""
        if default is None:
            default = DEFAULTS.get(name)
        return self._settings.value(self.key(name), default)

    def cached_value(self, name, default=None):
        if default is None:
            default = DEFAULTS.get(name)
        return self._cache.get(name, default)

    def set_value(self, name, value):
        self._settings.setValue(self.key(name), value)
        self._cache[name] = value

    def bool_value(self, name, default=None):
        if default is None:
            default = bool(DEFAULTS.get(name, False))
        return safe_bool(self.value(name, default), default)

    def cached_bool(self, name, default=None):
        if default is None:
            default = bool(DEFAULTS.get(name, False))
        return safe_bool(self.cached_value(name, default), default)

    def type_prefix(self, button_type):
        return TYPE_PREFIX.get(button_type, TYPE_PREFIX[TYPE_SAVE_EXPORT])

    def type_enabled(self, button_type):
        prefix = self.type_prefix(button_type)
        return self.cached_bool("apply/" + prefix, DEFAULTS.get("apply/" + prefix, False))

    def mouse_action_value(self, button_type, mouse_action):
        return self.cached_mouse_action(button_type, mouse_action)

    def cached_mouse_action(self, button_type, mouse_action):
        prefix = self.type_prefix(button_type)
        key = action_key(prefix, mouse_action)
        value = self.cached_value(key, DEFAULTS.get(key, ACTION_DO_NOTHING))
        if value is not None:
            return str(value)
        return str(DEFAULTS.get(key, ACTION_DO_NOTHING))

    # Compatibility helpers for older code paths.
    def active_scope(self):
        return str(self.cached_value("activeScope", SCOPE_SAVE_ONLY))

    def scope_prefix(self, scope=None):
        if scope in SCOPE_PREFIX:
            return SCOPE_PREFIX[scope]
        if scope in TYPE_PREFIX:
            return TYPE_PREFIX[scope]
        return TYPE_PREFIX[TYPE_SAVE_EXPORT]

    def restore_defaults(self):
        for key, value in DEFAULTS.items():
            self.set_value(key, value)
        self.reload_cache()

    def presets_text(self):
        return str(self.cached_value("presets", DEFAULT_PRESETS) or "")

    def enabled_types_summary(self):
        names = []
        for t in (TYPE_SAVE_EXPORT, TYPE_SAVE_FILE, TYPE_FOLDER, TYPE_OPEN_FILE, TYPE_LEGACY):
            if self.type_enabled(t):
                names.append(TYPE_LABELS[t])
        return ", ".join(names) if names else "None"
