# -*- coding: utf-8 -*-
"""Tabbed settings dialog for FGQEP01 Browse Enhancer."""

from __future__ import annotations

from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtCore import Qt

from .debug_index import tooltip
from .presets import resolve_presets, resolve_preset_items
from .tokens import helper_group_names, helper_items_for_group
from .settings_model import (
    ACTION_LABELS,
    AUTOFILL_CONTENT_LABELS,
    DEFAULT_PRESETS,
    MISSING_LABELS,
    MOUSE_ACTIONS,
    MOUSE_LEFT_CLICK,
    MOUSE_RIGHT_DOUBLE,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    MENU_ITEMS,
    UNRESOLVED_LABELS,
    action_key,
)


class FGQEP01SettingsDialog(QtWidgets.QDialog):
    """Settings dialog with button/path-box type tabs and stable UI index tooltips."""

    def __init__(self, parent, plugin):
        super().__init__(parent)
        self.plugin = plugin
        self.settings = plugin.settings
        self.action_combos = {}
        self.copy_target_checks = {}  # legacy; replaced by copy_target_combos in v0.4.3
        self.copy_target_combos = {}
        self.copy_extra_checks = {}
        self.copy_status_labels = {}
        self._test_browse_hold_timer = None
        self._test_browse_hold_fired = False
        self._test_browse_single_timer = None
        self._test_browse_suppress_next_release = False
        self.setWindowTitle(PLUGIN_NAME + " Settings")
        # Stable floating/modeless settings window. Use explicit top-level
        # window flags rather than mixing/removing Qt.Dialog flags, which can
        # behave inconsistently across QGIS/Qt builds on Windows.
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumWidth(920)
        self.setMinimumHeight(700)
        self._build_ui()
        self._load()

    def _combo(self, object_name, items, tip):
        combo = QtWidgets.QComboBox()
        combo.setObjectName(object_name)
        combo.setToolTip(tip)
        for value, label in items:
            combo.addItem(label, value)
        return combo

    def _checkbox(self, object_name, text, tip):
        check = QtWidgets.QCheckBox(text)
        check.setObjectName(object_name)
        check.setToolTip(tip)
        return check

    def _label(self, object_name, text, tip):
        label = QtWidgets.QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setToolTip(tip)
        return label

    def _compact_layout(self, layout, margins=(6, 4, 6, 4), spacing=4):
        try:
            layout.setContentsMargins(*margins)
            layout.setSpacing(spacing)
        except Exception:
            pass

    def _fit_list_widget_to_contents(self, widget, min_rows=2, max_rows=8):
        """Keep small list widgets close to their content height."""
        try:
            count = max(1, widget.count())
            rows = max(min_rows, min(count, max_rows))
            row_h = widget.sizeHintForRow(0) if widget.count() else widget.fontMetrics().lineSpacing() + 6
            if row_h <= 0:
                row_h = widget.fontMetrics().lineSpacing() + 6
            height = int(row_h * rows + 2 * widget.frameWidth() + 8)
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
            widget.updateGeometry()
        except Exception:
            pass

    def _fit_plain_text_to_contents(self, widget, min_lines=2, max_lines=8):
        """Keep text areas adaptive but capped so the settings dialog stays usable."""
        try:
            lines = max(1, widget.document().blockCount())
            lines = max(min_lines, min(lines, max_lines))
            line_h = widget.fontMetrics().lineSpacing()
            height = int(line_h * lines + 2 * widget.frameWidth() + 18)
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
            widget.updateGeometry()
        except Exception:
            pass

    def _set_combo(self, combo, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setAlignment(Qt.AlignTop)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("tabSettings")
        self.tabs.setToolTip(tooltip("UI#003", "QTabWidget", "tabSettings", "Settings tabs", "Settings are grouped by the type of QGIS browse button or path box being enhanced."))
        root.addWidget(self.tabs)

        self._build_general_tab()
        self._build_preset_menu_tab()
        self._build_save_export_tab()
        self._build_save_file_tab()
        self._build_folder_tab()
        self._build_open_file_tab()
        self._build_legacy_tab()
        self._build_presets_tab()
        self._build_debug_tab()

        btn_row = QtWidgets.QHBoxLayout()
        root.addLayout(btn_row)
        btn_row.addStretch(1)
        self.btn_restore = QtWidgets.QPushButton("Restore defaults")
        self.btn_restore.setObjectName("btnRestoreDefaults")
        self.btn_restore.setToolTip(tooltip("UI#011", "QPushButton", "btnRestoreDefaults", "Restore defaults", "Reset all settings to the recommended defaults, including enabled types and mouse actions."))
        self.btn_restore.clicked.connect(self._restore)
        btn_row.addWidget(self.btn_restore)
        self.btn_save = QtWidgets.QPushButton("Save settings")
        self.btn_save.setObjectName("btnSaveSettings")
        self.btn_save.setToolTip(tooltip("UI#190", "QPushButton", "btnSaveSettings", "Save settings", "Save all FGQEP01 Browse Enhancer settings and close this window."))
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        self.btn_apply = QtWidgets.QPushButton("Apply")
        self.btn_apply.setObjectName("btnApplySettings")
        self.btn_apply.setToolTip(tooltip("UI#193", "QPushButton", "btnApplySettings", "Apply", "Save all FGQEP01 Browse Enhancer settings, reload the in-memory cache, and keep this window open."))
        self.btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(self.btn_apply)
        self.btn_close = QtWidgets.QPushButton("Close")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setToolTip(tooltip("UI#191", "QPushButton", "btnClose", "Close", "Close this settings window without saving new changes."))
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

    def _build_general_tab(self):
        page = QtWidgets.QWidget()
        page.setObjectName("tabGeneral")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._label("lblGeneralDescription", "Turn Browse Enhancer on or off and choose which button/path-box types it is allowed to enhance.", tooltip("UI#001", "QLabel", "lblGeneralDescription", "General description", "General settings are intentionally simple. Detailed mouse actions are configured in each type tab.")))
        self.chk_enabled = self._checkbox("chkEnabled", "Enable Browse Enhancer", tooltip("UI#002", "QCheckBox", "chkEnabled", "Enable Browse Enhancer", "Turns FGQEP01 Browse Enhancer on or off."))
        layout.addWidget(self.chk_enabled)
        group = QtWidgets.QGroupBox("Apply to")
        group.setObjectName("grpApplyTo")
        group.setToolTip(tooltip("UI#004", "QGroupBox", "grpApplyTo", "Apply to", "Choose which button/path-box types Browse Enhancer is allowed to enhance. Save / Export buttons are recommended by default."))
        g = QtWidgets.QVBoxLayout(group)
        self.chk_apply_save_export = self._checkbox("chkApplySaveExport", "Save / Export buttons", tooltip("UI#005", "QCheckBox", "chkApplySaveExport", "Apply to Save / Export buttons", "Enhance normal QGIS Save As / Export dialogs, such as Save Features As, raster export, and layout export. Recommended."))
        self.chk_apply_save_file = self._checkbox("chkApplySaveFile", "Save-file path boxes", tooltip("UI#006", "QCheckBox", "chkApplySaveFile", "Apply to Save-file path boxes", "Enhance output file path boxes, such as Processing outputs or plugin file-save fields."))
        self.chk_apply_folder = self._checkbox("chkApplyFolder", "Folder path boxes", tooltip("UI#007", "QCheckBox", "chkApplyFolder", "Apply to Folder path boxes", "Enhance folder selection boxes, such as output folders or export directories."))
        self.chk_apply_open_file = self._checkbox("chkApplyOpenFile", "Open-file path boxes", tooltip("UI#008", "QCheckBox", "chkApplyOpenFile", "Apply to Open-file path boxes", "Enhance input file path boxes used to open existing files. Autofill is usually disabled for this type."))
        self.chk_apply_legacy = self._checkbox("chkApplyLegacy", "Custom / Advanced Buttons", tooltip("UI#009", "QCheckBox", "chkApplyLegacy", "Apply to Custom / Advanced Buttons", "Enable optional custom button detection. Normal QgsFileWidget tabs are not affected by these advanced button-type settings."))
        for w in (self.chk_apply_save_export, self.chk_apply_save_file, self.chk_apply_folder, self.chk_apply_open_file, self.chk_apply_legacy):
            g.addWidget(w)
        layout.addWidget(group)
        hold_form = QtWidgets.QFormLayout()
        self.spin_hold_delay = QtWidgets.QSpinBox()
        self.spin_hold_delay.setObjectName("spinHoldDelayMs")
        self.spin_hold_delay.setRange(200, 2000)
        self.spin_hold_delay.setSingleStep(50)
        self.spin_hold_delay.setSuffix(" ms")
        self.spin_hold_delay.setToolTip(tooltip("UI#020", "QSpinBox", "spinHoldDelayMs", "Hold action delay", "How long the mouse button must be held before a hold action runs. Default is 500 ms."))
        hold_form.addRow("Hold action delay", self.spin_hold_delay)

        self.spin_startup_delay = QtWidgets.QSpinBox()
        self.spin_startup_delay.setObjectName("spinStartupDelayMs")
        self.spin_startup_delay.setRange(0, 60000)
        self.spin_startup_delay.setSingleStep(1000)
        self.spin_startup_delay.setSuffix(" ms")
        self.spin_startup_delay.setToolTip(tooltip("UI#021", "QSpinBox", "spinStartupDelayMs", "Startup delay before event filter starts", "Delays the Browse Enhancer event filter after QGIS startup. This can reduce perceived startup load. The plugin menu and settings still load immediately. Default is 10000 ms. Set 0 to start immediately."))
        hold_form.addRow("Startup delay before event filter starts", self.spin_startup_delay)
        layout.addLayout(hold_form)

        self.tabs.addTab(page, "General")

    def _build_preset_menu_tab(self):
        page = QtWidgets.QWidget()
        page.setObjectName("tabPresetPathMenu")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._label(
            "lblPresetMenuDescription",
            "Configure what appears in the preset path menu when a browse button action is set to Show preset path menu.",
            tooltip("UI#012", "QLabel", "lblPresetMenuDescription", "Preset path menu description", "This menu is opened by mouse actions such as right-click or left-click-and-hold when their behaviour is set to Show preset path menu."),
        ))

        contents = QtWidgets.QGroupBox("Menu contents")
        contents.setObjectName("grpPresetMenuContents")
        contents.setToolTip(tooltip("UI#013", "QGroupBox", "grpPresetMenuContents", "Menu contents", "Choose which built-in path sources are shown in the preset path menu."))
        c_layout = QtWidgets.QGridLayout(contents)
        self._compact_layout(c_layout, margins=(6, 4, 6, 4), spacing=3)
        self.chk_menu_last_used = self._checkbox("chkMenuLastUsed", "Show Last used folder", tooltip("UI#014", "QCheckBox", "chkMenuLastUsed", "Show Last used folder", "Shows the most recent folder successfully used by FGQEP01."))
        self.chk_menu_current_file = self._checkbox("chkMenuCurrentFile", "Show Current file folder", tooltip("UI#015", "QCheckBox", "chkMenuCurrentFile", "Show Current file folder", "Shows the folder of the current source layer/file when available."))
        self.chk_menu_project_home = self._checkbox("chkMenuProjectHome", "Show Project home", tooltip("UI#016", "QCheckBox", "chkMenuProjectHome", "Show Project home", "Shows the QGIS project home folder."))
        self.chk_menu_qgz_folder = self._checkbox("chkMenuQgzFolder", "Show QGZ folder", tooltip("UI#017", "QCheckBox", "chkMenuQgzFolder", "Show QGZ folder", "Shows the folder containing the current .qgz/.qgs project file."))
        self.chk_menu_presets = self._checkbox("chkMenuPresets", "Show preset folders from Preset folders tab", tooltip("UI#018", "QCheckBox", "chkMenuPresets", "Show preset folders", "Shows custom named presets from the Preset folders tab."))
        self.chk_menu_desktop = self._checkbox("chkMenuDesktop", "Show Desktop", tooltip("UI#019", "QCheckBox", "chkMenuDesktop", "Show Desktop", "Shows the current user's Desktop folder."))
        self.chk_menu_documents = self._checkbox("chkMenuDocuments", "Show Documents", tooltip("UI#031", "QCheckBox", "chkMenuDocuments", "Show Documents", "Shows the current user's Documents folder."))
        self.chk_menu_downloads = self._checkbox("chkMenuDownloads", "Show Downloads", tooltip("UI#032", "QCheckBox", "chkMenuDownloads", "Show Downloads", "Shows the current user's Downloads folder."))
        for i, w in enumerate((self.chk_menu_last_used, self.chk_menu_current_file, self.chk_menu_project_home, self.chk_menu_qgz_folder, self.chk_menu_presets, self.chk_menu_desktop, self.chk_menu_documents, self.chk_menu_downloads)):
            c_layout.addWidget(w, i // 2, i % 2)
        layout.addWidget(contents)

        order_group = QtWidgets.QGroupBox("Menu item order")
        order_group.setObjectName("grpPresetMenuOrder")
        order_group.setToolTip(tooltip("UI#033", "QGroupBox", "grpPresetMenuOrder", "Menu item order", "Move items up or down to control the order of built-in sections in the preset path menu."))
        o_layout = QtWidgets.QVBoxLayout(order_group)
        self.lst_menu_order = QtWidgets.QListWidget()
        self.lst_menu_order.setObjectName("lstPresetMenuOrder")
        self.lst_menu_order.setToolTip(tooltip("UI#034", "QListWidget", "lstPresetMenuOrder", "Preset path menu order", "The enabled menu sources are shown in this order. Preset folders expand as individual items at the Preset folders position."))
        self.lst_menu_order.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        o_layout.addWidget(self.lst_menu_order)
        order_btns = QtWidgets.QHBoxLayout()
        self.btn_menu_move_up = QtWidgets.QPushButton("Move up")
        self.btn_menu_move_up.setObjectName("btnPresetMenuMoveUp")
        self.btn_menu_move_up.setToolTip(tooltip("UI#035", "QPushButton", "btnPresetMenuMoveUp", "Move up", "Move the selected menu source one row up."))
        self.btn_menu_move_up.clicked.connect(lambda: self._move_menu_order(-1))
        order_btns.addWidget(self.btn_menu_move_up)
        self.btn_menu_move_down = QtWidgets.QPushButton("Move down")
        self.btn_menu_move_down.setObjectName("btnPresetMenuMoveDown")
        self.btn_menu_move_down.setToolTip(tooltip("UI#036", "QPushButton", "btnPresetMenuMoveDown", "Move down", "Move the selected menu source one row down."))
        self.btn_menu_move_down.clicked.connect(lambda: self._move_menu_order(1))
        order_btns.addWidget(self.btn_menu_move_down)
        order_btns.addStretch(1)
        o_layout.addLayout(order_btns)
        layout.addWidget(order_group)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.chk_menu_create_missing = self._checkbox("chkMenuCreateMissing", "Create missing folders when selected from menu", tooltip("UI#037", "QCheckBox", "chkMenuCreateMissing", "Create missing folders when selected from menu", "Creates the target folder if it does not already exist when a menu item is chosen."))
        form.addRow("Missing folders", self.chk_menu_create_missing)
        self.chk_menu_remember_last = self._checkbox("chkMenuRememberLast", "Remember selected menu folder as Last used folder", tooltip("UI#038", "QCheckBox", "chkMenuRememberLast", "Remember selected menu folder", "When a folder is selected from the preset path menu, store it as the next Last used folder."))
        form.addRow("Last used folder", self.chk_menu_remember_last)
        self.cbo_menu_unresolved = self._combo("cboMenuUnresolved", list(UNRESOLVED_LABELS.items()), tooltip("UI#039", "QComboBox", "cboMenuUnresolved", "Unresolved menu items", "Choose whether unresolved menu items are hidden or shown disabled. Example: Current file folder when no source file can be detected."))
        form.addRow("Unresolved menu items", self.cbo_menu_unresolved)
        self.tabs.addTab(page, "Preset path menu")

    def _move_menu_order(self, direction):
        row = self.lst_menu_order.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.lst_menu_order.count():
            return
        item = self.lst_menu_order.takeItem(row)
        self.lst_menu_order.insertItem(new_row, item)
        self.lst_menu_order.setCurrentRow(new_row)

    def _set_menu_order(self, order_text):
        self.lst_menu_order.clear()
        labels = dict(MENU_ITEMS)
        valid = [k for k, _ in MENU_ITEMS]
        order = [x.strip() for x in str(order_text or "").split(",") if x.strip()]
        merged = []
        for key in order + valid:
            if key in valid and key not in merged:
                merged.append(key)
        for key in merged:
            item = QtWidgets.QListWidgetItem(labels.get(key, key))
            item.setData(Qt.UserRole, key)
            self.lst_menu_order.addItem(item)
        self._fit_list_widget_to_contents(self.lst_menu_order, min_rows=3, max_rows=7)

    def _menu_order_value(self):
        values = []
        for i in range(self.lst_menu_order.count()):
            item = self.lst_menu_order.item(i)
            values.append(str(item.data(Qt.UserRole)))
        return ",".join(values)

    def _build_action_group(self, parent_layout, prefix, title, ui_start):
        group = QtWidgets.QGroupBox("Browse button actions")
        group.setObjectName("grpActions_" + prefix)
        group.setToolTip(tooltip("UI#%03d" % ui_start, "QGroupBox", group.objectName(), title + " browse button actions", "Configure optional mouse actions for this button/path-box type. Normal left-click is always native QGIS browse and is not configurable."))
        form = QtWidgets.QFormLayout(group)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.action_combos[prefix] = {}
        idx = ui_start + 1
        for mouse_key, mouse_label in MOUSE_ACTIONS:
            # v0.6.0: normal left-click is always native QGIS browse and right double-click is dropped.
            # Keep existing settings keys for compatibility, but do not expose them in the UI.
            if mouse_key in (MOUSE_LEFT_CLICK, MOUSE_RIGHT_DOUBLE):
                continue
            object_name = "cbo_%s_%s" % (prefix, mouse_key)
            combo = self._combo(object_name, list(ACTION_LABELS.items()), tooltip("UI#%03d" % idx, "QComboBox", object_name, title + " - " + mouse_label, "Sets what happens on %s for this button/path-box type." % mouse_label.lower()))
            form.addRow(mouse_label, combo)
            self.action_combos[prefix][mouse_key] = combo
            idx += 1
        parent_layout.addWidget(group)
        return idx

    def _build_copy_group(self, parent_layout, source_prefix, source_title, ui_start):
        """Build compact copy-settings control.

        v0.8.3 replaces the previous large inline copy section with a
        single button that opens a small target-selection popup. This keeps
        each behaviour tab compact while preserving the same copy behaviour.
        """
        group = QtWidgets.QGroupBox("Copy settings")
        group.setObjectName("grpCopy_" + source_prefix)
        group.setToolTip(tooltip("UI#%03d" % ui_start, "QGroupBox", group.objectName(), source_title + " copy settings", "Copy settings from this tab directly to another button/path-box type tab, or to all other tabs."))
        layout = QtWidgets.QHBoxLayout(group)
        layout.setContentsMargins(8, 6, 8, 6)

        label = self._label("lblCopyDesc_" + source_prefix, "Copy settings:", tooltip("UI#%03d" % (ui_start + 1), "QLabel", "lblCopyDesc_" + source_prefix, source_title + " copy settings", "Use the button to choose target tabs in a compact popup."))
        label.setWordWrap(False)
        layout.addWidget(label)

        btn = QtWidgets.QToolButton()
        btn.setObjectName("btnCopySettingsTo_" + source_prefix)
        btn.setText("Copy settings to... ▼")
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        btn.setToolTip(tooltip("UI#%03d" % (ui_start + 2), "QToolButton", "btnCopySettingsTo_" + source_prefix, source_title + " copy settings to", "Open a popup to choose target tabs. Also copy autofill / missing-folder options is on by default."))
        btn.clicked.connect(lambda checked=False, p=source_prefix: self._show_copy_popup(p))
        layout.addWidget(btn)

        status = self._label("lblCopyStatus_" + source_prefix, "", tooltip("UI#%03d" % (ui_start + 3), "QLabel", "lblCopyStatus_" + source_prefix, source_title + " copy status", "Shows the result after copying settings."))
        status.setWordWrap(False)
        self.copy_status_labels[source_prefix] = status
        layout.addWidget(status, 1)
        parent_layout.addWidget(group)
        return ui_start + 4

    def _show_copy_popup(self, source_prefix):
        """Show compact target-selection popup for copying settings."""
        labels = dict(self._type_prefixes())
        source_title = labels.get(source_prefix, source_prefix)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Copy settings from " + source_title)
        dlg.setModal(True)
        dlg.setMinimumWidth(380)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.addWidget(self._label(
            "lblCopyPopupDesc_" + source_prefix,
            "Choose where to copy these settings.",
            "Copy mouse-action settings from the current tab. Extra options are copied where target tabs support them."
        ))

        chk_all = QtWidgets.QCheckBox("All other tabs")
        chk_all.setObjectName("chkCopyAll_" + source_prefix)
        layout.addWidget(chk_all)

        target_checks = []
        target_box = QtWidgets.QGroupBox("Target tabs")
        target_layout = QtWidgets.QVBoxLayout(target_box)
        for target_prefix, target_label in self._type_prefixes():
            if target_prefix == source_prefix:
                continue
            chk = QtWidgets.QCheckBox(target_label)
            chk.setObjectName("chkCopyTarget_%s_to_%s" % (source_prefix, target_prefix))
            target_layout.addWidget(chk)
            target_checks.append((target_prefix, chk))
        layout.addWidget(target_box)

        def on_all_changed(state):
            checked = chk_all.isChecked()
            for _, chk in target_checks:
                chk.setChecked(checked)
                chk.setEnabled(not checked)
        chk_all.stateChanged.connect(on_all_changed)

        chk_extra = QtWidgets.QCheckBox("Also copy autofill / missing-folder options where available")
        chk_extra.setObjectName("chkCopyExtrasPopup_" + source_prefix)
        chk_extra.setChecked(True)
        chk_extra.setToolTip("Also copies matching autofill and missing-folder settings to target tabs that support them.")
        layout.addWidget(chk_extra)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        btn_copy = QtWidgets.QPushButton("Copy to selected")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        row.addWidget(btn_copy)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def do_copy():
            if chk_all.isChecked():
                targets = [p for p, _ in self._type_prefixes() if p != source_prefix]
            else:
                targets = [p for p, chk in target_checks if chk.isChecked()]
            if not targets:
                self.copy_status_labels[source_prefix].setText("No copy target selected.")
                return
            self._copy_settings_to_targets(source_prefix, targets, chk_extra.isChecked())
            if chk_all.isChecked():
                self.copy_status_labels[source_prefix].setText("Copied settings to all other tabs.")
            else:
                target_names = ", ".join(labels.get(p, p) for p in targets)
                self.copy_status_labels[source_prefix].setText("Copied settings to: %s." % target_names)
            dlg.accept()

        btn_copy.clicked.connect(do_copy)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec_()

    def _type_prefixes(self):
        return [
            ("save_export", "Save / Export buttons"),
            ("save_file", "Save-file path boxes"),
            ("folder", "Folder path boxes"),
            ("open_file", "Open-file path boxes"),
            ("legacy", "Custom / Advanced Buttons"),
        ]

    def _type_page(self, object_name, tab_title, desc_obj, desc_text, ui_no):
        page = QtWidgets.QWidget()
        page.setObjectName(object_name)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._label(desc_obj, desc_text, tooltip(ui_no, "QLabel", desc_obj, tab_title + " description", desc_text)))
        return page, layout

    def _autofill_content_combo(self, object_name, ui_no, caption):
        return self._combo(
            object_name,
            list(AUTOFILL_CONTENT_LABELS.items()),
            tooltip(
                ui_no,
                "QComboBox",
                object_name,
                caption,
                "Choose what content is inserted when this tab runs 'Run autofill if empty' or 'Clear then autofill'. The same list is used across tabs, but each tab stores its own selected value.",
            ),
        )

    def _build_save_export_tab(self):
        page, layout = self._type_page("tabSaveExportButtons", "Save / Export buttons", "lblSaveExportDescription", "Use this tab for normal QGIS Save As / Export dialogs, such as Save Features As, raster export, layout export, and other export dialogs that write a new file.", "UI#050")
        next_ui = self._build_action_group(layout, "save_export", "Save / Export buttons", 51)
        form = QtWidgets.QFormLayout(); layout.addLayout(form)
        self.cbo_save_export_autofill_content = self._autofill_content_combo("cboSaveExportAutofillContent", "UI#057A", "Save / Export autofill content")
        form.addRow("Autofill content", self.cbo_save_export_autofill_content)
        self.chk_save_export_raster_no_ext = self._checkbox("chkSaveExportRasterNoExt", "Do not add extension for raster export autofill", tooltip("UI#059", "QCheckBox", "chkSaveExportRasterNoExt", "Raster export paths", "When a raster export path is suggested, leave off .tif or other extensions so the QGIS exporter can decide the final extension."))
        form.addRow("Raster export paths", self.chk_save_export_raster_no_ext)
        self.cbo_save_export_missing = self._combo("cboSaveExportMissing", list(MISSING_LABELS.items()), tooltip("UI#060", "QComboBox", "cboSaveExportMissing", "If Save / Export folder is missing", "Choose what happens if the selected preset/autofill folder does not exist. Default: leave unchanged and let QGIS handle it."))
        form.addRow("If folder is missing", self.cbo_save_export_missing)
        self._build_copy_group(layout, "save_export", "Save / Export buttons", 300)
        self.tabs.addTab(page, "Save / Export buttons")

    def _build_save_file_tab(self):
        page, layout = self._type_page("tabSaveFileBoxes", "Save-file path boxes", "lblSaveFileDescription", "Use this tab for path boxes that save a new file, usually in Processing tools or plugin dialogs. Example: an output .gpkg, .shp, .tif, .csv, or other file path. This is not for folder-only outputs and not for opening existing files.", "UI#070")
        self._build_action_group(layout, "save_file", "Save-file path boxes", 71)
        form = QtWidgets.QFormLayout(); layout.addLayout(form)
        self.chk_save_file_autofill = self._checkbox("chkSaveFileAutofill", "Enable autofill for save-file path boxes", tooltip("UI#078", "QCheckBox", "chkSaveFileAutofill", "Enable autofill for save-file path boxes", "Allow FGQEP01 to fill empty save-file path boxes. Default is off because Processing outputs can behave differently."))
        form.addRow("Autofill", self.chk_save_file_autofill)
        self.cbo_save_file_autofill_content = self._autofill_content_combo("cboSaveFileAutofillContent", "UI#078A", "Save-file autofill content")
        form.addRow("Autofill content", self.cbo_save_file_autofill_content)
        self.cbo_save_file_missing = self._combo("cboSaveFileMissing", list(MISSING_LABELS.items()), tooltip("UI#080", "QComboBox", "cboSaveFileMissing", "If save-file folder is missing", "Choose what happens if the selected/autofill folder does not exist. Default: leave unchanged and let QGIS handle it."))
        form.addRow("If folder is missing", self.cbo_save_file_missing)
        self._build_copy_group(layout, "save_file", "Save-file path boxes", 310)
        self.tabs.addTab(page, "Save-file path boxes")

    def _build_folder_tab(self):
        page, layout = self._type_page("tabFolderBoxes", "Folder path boxes", "lblFolderDescription", "Use this tab for path boxes that select or save to a folder rather than a file. Example: choosing an output folder, export directory, batch output folder, or destination folder.", "UI#090")
        self._build_action_group(layout, "folder", "Folder path boxes", 91)
        form = QtWidgets.QFormLayout(); layout.addLayout(form)
        self.chk_folder_autofill = self._checkbox("chkFolderAutofill", "Enable autofill for folder path boxes", tooltip("UI#098", "QCheckBox", "chkFolderAutofill", "Enable autofill for folder path boxes", "Allow FGQEP01 to fill empty folder path boxes with a folder location."))
        form.addRow("Autofill", self.chk_folder_autofill)
        self.cbo_folder_autofill_content = self._autofill_content_combo("cboFolderAutofillContent", "UI#098A", "Folder path-box autofill content")
        form.addRow("Autofill content", self.cbo_folder_autofill_content)
        self.cbo_folder_missing = self._combo("cboFolderMissing", list(MISSING_LABELS.items()), tooltip("UI#099", "QComboBox", "cboFolderMissing", "If folder path is missing", "Choose what happens if the selected/autofill folder does not exist. Default: leave unchanged and let QGIS handle it."))
        form.addRow("If folder is missing", self.cbo_folder_missing)
        self._build_copy_group(layout, "folder", "Folder path boxes", 320)
        self.tabs.addTab(page, "Folder path boxes")

    def _build_open_file_tab(self):
        page, layout = self._type_page("tabOpenFileBoxes", "Open-file path boxes", "lblOpenFileDescription", "Use this tab for path boxes that open or import an existing file. Example: selecting an input layer, CSV, raster, style file, or other existing file. Autofill is disabled by default because open-file boxes usually expect an existing input file, not a new export path.", "UI#110")
        self._build_action_group(layout, "open_file", "Open-file path boxes", 111)
        form = QtWidgets.QFormLayout(); layout.addLayout(form)
        self.chk_open_file_autofill = self._checkbox("chkOpenFileAutofill", "Allow autofill for open-file path boxes", tooltip("UI#118", "QCheckBox", "chkOpenFileAutofill", "Allow autofill for open-file path boxes", "Off by default. Enable only if you deliberately want empty open/import boxes to receive a suggested path."))
        form.addRow("Autofill", self.chk_open_file_autofill)
        self.cbo_open_file_autofill_content = self._autofill_content_combo("cboOpenFileAutofillContent", "UI#118A", "Open-file autofill content")
        form.addRow("Autofill content", self.cbo_open_file_autofill_content)
        self.cbo_open_file_missing = self._combo("cboOpenFileMissing", list(MISSING_LABELS.items()), tooltip("UI#120", "QComboBox", "cboOpenFileMissing", "If open-file folder is missing", "Choose what happens if the selected/autofill folder does not exist. Default: leave unchanged and let QGIS handle it."))
        form.addRow("If folder is missing", self.cbo_open_file_missing)
        self._build_copy_group(layout, "open_file", "Open-file path boxes", 330)
        self.tabs.addTab(page, "Open-file path boxes")

    def _build_legacy_tab(self):
        page = QtWidgets.QWidget(); page.setObjectName("tabLegacyFallback")
        layout = QtWidgets.QVBoxLayout(page); layout.setAlignment(Qt.AlignTop)

        warning = self._label(
            "lblLegacyWarning",
            "Advanced custom button support. Use this for third-party plugin dialogs that use ordinary buttons instead of QgsFileWidget. These options apply only to the Custom / Advanced Buttons tab and do not change normal QgsFileWidget handling.",
            tooltip("UI#130", "QLabel", "lblLegacyWarning", "Custom / Advanced warning", "Explains that this page is an advanced opt-in mode for ordinary plugin buttons."),
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("font-weight: bold;")
        layout.addWidget(warning)

        main_group = QtWidgets.QGroupBox("Main controls")
        main_group.setObjectName("grpLegacyMainControls")
        main_group.setToolTip("Enable Custom / Advanced detection, choose button classes, and optionally turn on the widget inspector.")
        main_layout = QtWidgets.QGridLayout(main_group)
        self._compact_layout(main_layout, margins=(6, 4, 6, 4), spacing=3)

        self.chk_legacy_enabled = self._checkbox("chkLegacyEnabled", "Enable custom / advanced button support", tooltip("UI#131", "QCheckBox", "chkLegacyEnabled", "Enable custom / advanced button support", "Enables support for allowlisted ordinary buttons in third-party plugin dialogs. These settings apply only to this tab."))
        main_layout.addWidget(self.chk_legacy_enabled, 0, 0, 1, 3)

        self.chk_legacy_qtoolbutton = self._checkbox("chkLegacyDetectQToolButton", "QToolButton", tooltip("UI#140", "QCheckBox", "chkLegacyDetectQToolButton", "Detect QToolButton", "Allow Custom / Advanced detection on QToolButton controls."))
        self.chk_legacy_qpushbutton = self._checkbox("chkLegacyDetectQPushButton", "QPushButton", tooltip("UI#141", "QCheckBox", "chkLegacyDetectQPushButton", "Detect QPushButton", "Allow Custom / Advanced detection on ordinary QPushButton controls, such as many third-party plugin Browse buttons."))
        self.chk_legacy_qcommandlinkbutton = self._checkbox("chkLegacyDetectQCommandLinkButton", "QCommandLinkButton", tooltip("UI#142A", "QCheckBox", "chkLegacyDetectQCommandLinkButton", "Detect QCommandLinkButton", "Advanced button type. Enable only when a specific plugin uses command-link buttons."))
        self.chk_legacy_qcheckbox = self._checkbox("chkLegacyDetectQCheckBox", "QCheckBox", tooltip("UI#142B", "QCheckBox", "chkLegacyDetectQCheckBox", "Detect QCheckBox", "Advanced button type. Checkboxes are button-like Qt controls and may cause unwanted detection if enabled."))
        self.chk_legacy_qradiobutton = self._checkbox("chkLegacyDetectQRadioButton", "QRadioButton", tooltip("UI#142C", "QCheckBox", "chkLegacyDetectQRadioButton", "Detect QRadioButton", "Advanced button type. Radio buttons are option controls and should usually stay off."))
        self.chk_legacy_other_button = self._checkbox("chkLegacyDetectOtherAbstractButton", "Other QAbstractButton", tooltip("UI#142D", "QCheckBox", "chkLegacyDetectOtherAbstractButton", "Detect other QAbstractButton types", "Broad fallback for custom or uncommon Qt button subclasses not listed above. Use only with narrow allowlists."))
        legacy_btn_label = self._label("lblLegacyButtonTypes", "Button types:", tooltip("UI#140A", "QLabel", "lblLegacyButtonTypes", "Button types", "Select which Qt button classes Custom / Advanced mode may detect. These options apply only to this tab."))
        legacy_btn_label.setWordWrap(False)
        main_layout.addWidget(legacy_btn_label, 1, 0)
        main_layout.addWidget(self.chk_legacy_qtoolbutton, 1, 1)
        main_layout.addWidget(self.chk_legacy_qpushbutton, 1, 2)
        main_layout.addWidget(self.chk_legacy_qcommandlinkbutton, 1, 3)
        main_layout.addWidget(self.chk_legacy_qcheckbox, 2, 1)
        main_layout.addWidget(self.chk_legacy_qradiobutton, 2, 2)
        main_layout.addWidget(self.chk_legacy_other_button, 2, 3)

        self.chk_legacy_middle_inspector = self._checkbox("chkLegacyMiddleInspector", "Middle-double-click widget inspector", tooltip("UI#132", "QCheckBox", "chkLegacyMiddleInspector", "Enable middle-double-click inspector", "When enabled, middle double-click any widget in a QGIS/plugin dialog to capture dialog title, item type, item text, and item objectName."))
        main_layout.addWidget(self.chk_legacy_middle_inspector, 3, 0, 1, 4)
        inspector_note = self._label("lblLegacyInspectorNote", "Inspector captures the clicked UI item and briefly highlights it.", tooltip("UI#132A", "QLabel", "lblLegacyInspectorNote", "Inspector note", "Describes the middle-double-click inspector."))
        inspector_note.setWordWrap(False)
        main_layout.addWidget(inspector_note, 4, 0, 1, 4)
        layout.addWidget(main_group)

        # Keep the working Custom / Advanced mouse-action controls from v0.7.7,
        # but place them directly after the compact main controls.
        self._build_action_group(layout, "legacy", "Custom / Advanced Buttons", 133)
        legacy_form = QtWidgets.QFormLayout(); layout.addLayout(legacy_form)
        self.cbo_legacy_autofill_content = self._autofill_content_combo("cboLegacyAutofillContent", "UI#139A", "Custom / Advanced autofill content")
        legacy_form.addRow("Autofill content", self.cbo_legacy_autofill_content)

        allow_group = QtWidgets.QGroupBox("Detection rules")
        allow_group.setObjectName("grpLegacyAllowlist")
        allow_group.setToolTip("Use narrow allowlists. If an allowlist is blank and its bypass is off, it matches nothing. Enable bypass to ignore that specific allowlist.")
        allow_layout = QtWidgets.QVBoxLayout(allow_group)
        note = self._label("lblLegacyAllowlistNote", "Blank allowlist + bypass off = match nothing. Enable a bypass to ignore that specific rule while keeping other safeguards active.", tooltip("UI#143", "QLabel", "lblLegacyAllowlistNote", "Allowlist note", "Explains blank allowlist and bypass behaviour."))
        note.setWordWrap(True)
        allow_layout.addWidget(note)

        self.chk_legacy_debug_bypass = self._checkbox("chkLegacyDebugBypass", "Bypass all allowlists", tooltip("UI#139B", "QCheckBox", "chkLegacyDebugBypass", "Bypass all allowlists", "Ignores all Custom / Advanced allowlists while still requiring Custom / Advanced support and enabled button types."))
        allow_layout.addWidget(self.chk_legacy_debug_bypass)

        rules_tabs = QtWidgets.QTabWidget(); rules_tabs.setObjectName("tabLegacyDetectionRules")
        allow_layout.addWidget(rules_tabs)

        def add_allow_tab(tab_title, checkbox_attr, checkbox_obj, textbox_attr, textbox_name, ui_num, tooltip_text, height=92):
            tab = QtWidgets.QWidget(); tab.setObjectName("tab" + textbox_name)
            tab_layout = QtWidgets.QVBoxLayout(tab); tab_layout.setContentsMargins(6, 6, 6, 6)
            tab_layout.addWidget(checkbox_obj)
            edit = QtWidgets.QPlainTextEdit(); edit.setObjectName(textbox_name); edit.setMaximumHeight(height)
            edit.setToolTip(tooltip_text)
            setattr(self, textbox_attr, edit)
            tab_layout.addWidget(edit)
            tab_layout.addWidget(self._label("lbl" + textbox_name, tooltip_text, tooltip(ui_num, "QLabel", "lbl" + textbox_name, tab_title + " help", tooltip_text)))
            rules_tabs.addTab(tab, tab_title)

        self.chk_legacy_bypass_dialog = self._checkbox("chkLegacyBypassDialogAllowlist", "Bypass dialog title allowlist", tooltip("UI#139C", "QCheckBox", "chkLegacyBypassDialogAllowlist", "Bypass dialog title allowlist", "When enabled, dialog title keywords are ignored. Other enabled allowlists and safeguards still apply."))
        add_allow_tab("Dialog title", "chk_legacy_bypass_dialog", self.chk_legacy_bypass_dialog, "txt_legacy_dialog_allow", "txtLegacyDialogAllowlist", "UI#144", "One dialog title keyword per line. Custom Browse buttons are only considered when the current QDialog title contains one of these keywords unless bypass is enabled.")

        self.chk_legacy_bypass_button_text = self._checkbox("chkLegacyBypassButtonTextAllowlist", "Bypass button text allowlist", tooltip("UI#139D", "QCheckBox", "chkLegacyBypassButtonTextAllowlist", "Bypass button text allowlist", "When enabled, button text such as Browse or Select is ignored. Other enabled allowlists and safeguards still apply."))
        add_allow_tab("Button text", "chk_legacy_bypass_button_text", self.chk_legacy_bypass_button_text, "txt_legacy_button_allow", "txtLegacyButtonAllowlist", "UI#145", "One button text keyword per line, for example Browse, ..., or Select. Matching is case-insensitive unless bypass is enabled.")

        self.chk_legacy_bypass_button_object = self._checkbox("chkLegacyBypassButtonObjectAllowlist", "Bypass button objectName allowlist", tooltip("UI#139E", "QCheckBox", "chkLegacyBypassButtonObjectAllowlist", "Bypass button objectName allowlist", "When enabled, button objectName matching is ignored. Other enabled allowlists and safeguards still apply."))
        add_allow_tab("Button objectName", "chk_legacy_bypass_button_object", self.chk_legacy_bypass_button_object, "txt_legacy_button_object_allow", "txtLegacyButtonObjectAllowlist", "UI#146", "One button objectName per line. Use this to target specific buttons such as browseZielPfadOrDatei unless bypass is enabled.")

        self.chk_legacy_bypass_target_object = self._checkbox("chkLegacyBypassTargetObjectAllowlist", "Bypass target textbox objectName allowlist", tooltip("UI#139F", "QCheckBox", "chkLegacyBypassTargetObjectAllowlist", "Bypass target textbox objectName allowlist", "When enabled, the target textbox objectName list is ignored and the selected search mode is used. Target detection is only required for actions that read/write a textbox."))
        add_allow_tab("Target textbox", "chk_legacy_bypass_target_object", self.chk_legacy_bypass_target_object, "txt_legacy_target_object_allow", "txtLegacyTargetObjectAllowlist", "UI#147", "One target textbox objectName per line. If set, only these QLineEdit/QTextEdit targets are accepted, such as txtZielPfad, unless bypass is enabled.")
        layout.addWidget(allow_group)

        search_group = QtWidgets.QGroupBox("Target path box search")
        search_group.setObjectName("grpLegacyTargetSearch")
        search_group.setToolTip("Target textbox detection is only required for actions that read or write the textbox. Menu-only actions can still run without a textbox.")
        search_layout = QtWidgets.QFormLayout(search_group)
        self.cbo_legacy_search_mode = QtWidgets.QComboBox(); self.cbo_legacy_search_mode.setObjectName("cboLegacyPathSearchMode")
        self.cbo_legacy_search_mode.addItem("Strict nearby search", "nearby")
        self.cbo_legacy_search_mode.addItem("Search within parent container", "parent")
        self.cbo_legacy_search_mode.addItem("Search whole dialog carefully", "dialog")
        self.cbo_legacy_search_mode.setToolTip("Controls how FGQEP01 finds the path text box for a custom Browse button when target objectName matching is bypassed or unavailable.")
        search_layout.addRow("Find target path box", self.cbo_legacy_search_mode)
        search_note = self._label("lblLegacyTargetSearchNote", "Target textbox detection does not block menu-only actions. Textbox actions are skipped if no target textbox is available.", tooltip("UI#148", "QLabel", "lblLegacyTargetSearchNote", "Target search note", "Explains when target textbox detection is required."))
        search_note.setWordWrap(True)
        search_layout.addRow(search_note)
        layout.addWidget(search_group)

        diag_group = QtWidgets.QGroupBox("Diagnostics")
        diag_group.setObjectName("grpLegacyDiagnostics")
        diag_layout = QtWidgets.QVBoxLayout(diag_group)
        diag_layout.addWidget(self._label("lblLegacyDiagnosticsNote", "Use Debug / About > Scan active dialog buttons, or enable the middle-double-click inspector above, to collect allowlist-ready information from any plugin dialog.", tooltip("UI#149", "QLabel", "lblLegacyDiagnosticsNote", "Diagnostics note", "Points users to the active-dialog scanner and middle-double-click inspector.")))
        layout.addWidget(diag_group)

        self._build_copy_group(layout, "legacy", "Custom / Advanced Buttons", 340)
        self.tabs.addTab(page, "Custom / Advanced Buttons")

    def _build_presets_tab(self):
        page = QtWidgets.QWidget(); page.setObjectName("tabPresets")
        layout = QtWidgets.QVBoxLayout(page); layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._label("lblPresetDescription", "Preset folders are named locations that can appear in the browse button menu. They can use common folder tokens, system variables, QGIS project variables, date tokens, and relative paths such as ../exports or ../../ClientExports.", tooltip("UI#160", "QLabel", "lblPresetDescription", "Preset folders description", "Explains what preset folders are and where they are used.")))
        self.txt_presets = QtWidgets.QPlainTextEdit(); self.txt_presets.setObjectName("txtPresets")
        self.txt_presets.setToolTip(tooltip("UI#161", "QPlainTextEdit", "txtPresets", "Preset folders", "Enter one preset per line as name=path. Relative paths such as exports, ../exports, or ../../ClientExports resolve from the folder containing the current QGZ/QGS project file. If the project is unsaved, relative presets are shown unavailable/disabled. Supported tokens include {project_home}, {qgz_folder}, {env:USERPROFILE}, {date:yyyyMMdd}, {user}, {qgis_profile}, and {var:project_code}."))
        self.txt_presets.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.txt_presets.textChanged.connect(self._preview_presets)
        self.txt_presets.textChanged.connect(lambda: self._fit_plain_text_to_contents(self.txt_presets, min_lines=3, max_lines=9))
        layout.addWidget(self.txt_presets)

        row = QtWidgets.QHBoxLayout(); layout.addLayout(row)
        self.btn_insert_variable_popup = QtWidgets.QPushButton("Insert variable / path...")
        self.btn_insert_variable_popup.setObjectName("btnInsertVariablePopup")
        self.btn_insert_variable_popup.setToolTip(tooltip("UI#230", "QPushButton", "btnInsertVariablePopup", "Insert variable / path", "Opens a helper popup for inserting common path, project, QGIS, system, and date tokens into the preset editor."))
        self.btn_insert_variable_popup.clicked.connect(self._show_insert_variable_popup)
        row.addWidget(self.btn_insert_variable_popup)
        self.btn_test_presets = QtWidgets.QPushButton("Preview selected preset")
        self.btn_test_presets.setObjectName("btnTestPresets")
        self.btn_test_presets.setToolTip(tooltip("UI#164", "QPushButton", "btnTestPresets", "Preview selected preset", "Refresh the resolved preset preview without changing QGIS paths or creating folders."))
        self.btn_test_presets.clicked.connect(self._preview_presets); row.addWidget(self.btn_test_presets)
        self.btn_preset_examples = QtWidgets.QPushButton("Reset default presets")
        self.btn_preset_examples.setObjectName("btnPresetExamples")
        self.btn_preset_examples.setToolTip(tooltip("UI#165", "QPushButton", "btnPresetExamples", "Reset default presets", "Replace the preset editor with the default presets: Current file folder, Project home, and QGZ folder. Save settings afterwards if you want to keep them."))
        self.btn_preset_examples.clicked.connect(lambda: self.txt_presets.setPlainText(DEFAULT_PRESETS)); row.addWidget(self.btn_preset_examples)
        row.addStretch(1)

        self.txt_preview = QtWidgets.QPlainTextEdit(); self.txt_preview.setObjectName("txtPresetPreview"); self.txt_preview.setReadOnly(True)
        self.txt_preview.setToolTip(tooltip("UI#166", "QPlainTextEdit", "txtPresetPreview", "Resolved preset preview", "Shows resolved folder paths after token expansion and relative-path resolution. Unavailable presets are shown with a reason."))
        self.txt_preview.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.txt_preview.textChanged.connect(lambda: self._fit_plain_text_to_contents(self.txt_preview, min_lines=2, max_lines=7))
        layout.addWidget(self.txt_preview)
        self.tabs.addTab(page, "Preset folders")

    def _insert_preset_text(self, text):
        cursor = self.txt_presets.textCursor()
        cursor.insertText(str(text))
        self.txt_presets.setTextCursor(cursor)
        self.txt_presets.setFocus()
        self._preview_presets()
        if hasattr(self, "lbl_insert_popup_status"):
            self.lbl_insert_popup_status.setText("Inserted: %s" % text)

    def _show_insert_variable_popup(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setObjectName("dlgInsertVariablePath")
        dlg.setWindowTitle("Insert variable / path")
        dlg.setMinimumWidth(860)
        dlg.setMinimumHeight(560)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setAlignment(Qt.AlignTop)
        desc = self._label(
            "lblInsertVariablePopupDescription",
            "Insert tokens, QGIS expression variables, project variables, system paths, date strings, or relative path examples into the preset editor.",
            tooltip("UI#231", "QLabel", "lblInsertVariablePopupDescription", "Insert variable popup description", "Select a group, filter the list, then insert the selected token/path into the preset editor."),
        )
        layout.addWidget(desc)

        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel("Group:"))
        self.cbo_insert_group = QtWidgets.QComboBox()
        self.cbo_insert_group.setObjectName("cboInsertVariableGroup")
        self.cbo_insert_group.setToolTip("Choose which type of token/path to browse.")
        for group_name in helper_group_names():
            self.cbo_insert_group.addItem(group_name)
        top_row.addWidget(self.cbo_insert_group, 1)
        top_row.addWidget(QtWidgets.QLabel("Filter:"))
        self.txt_insert_filter = QtWidgets.QLineEdit()
        self.txt_insert_filter.setObjectName("txtInsertVariableFilter")
        self.txt_insert_filter.setPlaceholderText("type to filter")
        self.txt_insert_filter.setToolTip("Filter helper rows by name, token, value, or description.")
        top_row.addWidget(self.txt_insert_filter, 1)
        layout.addLayout(top_row)

        self.tbl_insert_items = QtWidgets.QTableWidget(0, 3)
        self.tbl_insert_items.setObjectName("tblInsertVariableItems")
        self.tbl_insert_items.setHorizontalHeaderLabels(["Variable / item", "Token/path to insert", "Current value"])
        self.tbl_insert_items.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_insert_items.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_insert_items.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_insert_items.setToolTip("Select a row to preview and insert its token/path.")
        try:
            self.tbl_insert_items.horizontalHeader().setStretchLastSection(True)
            self.tbl_insert_items.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            self.tbl_insert_items.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        except Exception:
            pass
        layout.addWidget(self.tbl_insert_items, 1)

        form = QtWidgets.QFormLayout()
        self.txt_insert_token_preview = QtWidgets.QLineEdit()
        self.txt_insert_token_preview.setObjectName("txtInsertTokenPreview")
        self.txt_insert_token_preview.setReadOnly(True)
        form.addRow("Token/path to insert", self.txt_insert_token_preview)
        self.lbl_insert_description = self._label("lblInsertTokenDescription", "", "Description of the selected token/path.")
        form.addRow("Description", self.lbl_insert_description)
        layout.addLayout(form)

        custom = QtWidgets.QGroupBox("Custom inserts")
        custom.setObjectName("grpInsertCustomVariables")
        custom.setToolTip(tooltip("UI#260", "QGroupBox", "grpInsertCustomVariables", "Custom inserts", "Insert QGIS project variable, system environment variable, or custom date-format tokens."))
        custom_form = QtWidgets.QFormLayout(custom)
        self.txt_project_var_name = QtWidgets.QLineEdit(); self.txt_project_var_name.setObjectName("txtProjectVarName")
        self.txt_project_var_name.setPlaceholderText("project_code")
        self.btn_insert_project_var = QtWidgets.QPushButton("Insert {var:name}")
        self.btn_insert_project_var.setObjectName("btnInsertProjectVar")
        self.btn_insert_project_var.clicked.connect(self._insert_project_variable_token)
        r1 = QtWidgets.QHBoxLayout(); r1.addWidget(self.txt_project_var_name); r1.addWidget(self.btn_insert_project_var)
        custom_form.addRow("Project variable", r1)
        self.txt_env_var_name = QtWidgets.QLineEdit(); self.txt_env_var_name.setObjectName("txtEnvVarName")
        self.txt_env_var_name.setPlaceholderText("USERPROFILE")
        self.btn_insert_env_var = QtWidgets.QPushButton("Insert {env:NAME}")
        self.btn_insert_env_var.setObjectName("btnInsertEnvVar")
        self.btn_insert_env_var.clicked.connect(self._insert_env_variable_token)
        r2 = QtWidgets.QHBoxLayout(); r2.addWidget(self.txt_env_var_name); r2.addWidget(self.btn_insert_env_var)
        custom_form.addRow("Environment variable", r2)
        self.txt_date_format = QtWidgets.QLineEdit(); self.txt_date_format.setObjectName("txtDateFormat")
        self.txt_date_format.setPlaceholderText("yyyyMMdd_HHmm")
        self.btn_insert_date = QtWidgets.QPushButton("Insert {date:fmt}")
        self.btn_insert_date.setObjectName("btnInsertDateFormat")
        self.btn_insert_date.clicked.connect(self._insert_custom_date_token)
        r3 = QtWidgets.QHBoxLayout(); r3.addWidget(self.txt_date_format); r3.addWidget(self.btn_insert_date)
        custom_form.addRow("Date/time format", r3)
        layout.addWidget(custom)

        self.lbl_insert_popup_status = self._label("lblInsertPopupStatus", "", tooltip("UI#267", "QLabel", "lblInsertPopupStatus", "Insert status", "Shows the most recently inserted token."))
        layout.addWidget(self.lbl_insert_popup_status)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_insert_selected_helper = QtWidgets.QPushButton("Insert selected")
        self.btn_insert_selected_helper.setObjectName("btnInsertSelectedHelperItem")
        self.btn_insert_selected_helper.setToolTip("Insert the selected token/path into the preset editor at the cursor position.")
        self.btn_insert_selected_helper.clicked.connect(self._insert_selected_helper_item)
        btn_row.addWidget(self.btn_insert_selected_helper)
        self.btn_copy_selected_helper = QtWidgets.QPushButton("Copy token")
        self.btn_copy_selected_helper.setObjectName("btnCopySelectedHelperItem")
        self.btn_copy_selected_helper.setToolTip("Copy the selected token/path to the clipboard.")
        self.btn_copy_selected_helper.clicked.connect(self._copy_selected_helper_item)
        btn_row.addWidget(self.btn_copy_selected_helper)
        btn_row.addStretch(1)
        btn_close = QtWidgets.QPushButton("Close")
        btn_close.setObjectName("btnCloseInsertVariablePopup")
        btn_close.setToolTip(tooltip("UI#268", "QPushButton", "btnCloseInsertVariablePopup", "Close", "Close the insert variable / path popup."))
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self.cbo_insert_group.currentIndexChanged.connect(self._refresh_insert_helper_list)
        self.txt_insert_filter.textChanged.connect(self._refresh_insert_helper_list)
        self.tbl_insert_items.itemSelectionChanged.connect(self._update_insert_helper_preview)
        self.tbl_insert_items.itemDoubleClicked.connect(lambda item: self._insert_selected_helper_item())
        self._refresh_insert_helper_list()
        dlg.exec_()

    def _refresh_insert_helper_list(self):
        if not hasattr(self, "tbl_insert_items"):
            return
        group_name = str(self.cbo_insert_group.currentText() or "")
        filter_text = str(self.txt_insert_filter.text() or "").lower().strip()
        rows = helper_items_for_group(group_name)
        self.tbl_insert_items.setRowCount(0)
        for label, token_text, value, description in rows:
            haystack = " ".join([str(label), str(token_text), str(value), str(description)]).lower()
            if filter_text and filter_text not in haystack:
                continue
            row = self.tbl_insert_items.rowCount()
            self.tbl_insert_items.insertRow(row)
            values = [label, token_text, value]
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setToolTip(str(description))
                if col == 0:
                    item.setData(Qt.UserRole, str(token_text))
                    item.setData(Qt.UserRole + 1, str(description))
                self.tbl_insert_items.setItem(row, col, item)
        if self.tbl_insert_items.rowCount() > 0:
            self.tbl_insert_items.selectRow(0)
        else:
            self.txt_insert_token_preview.setText("")
            self.lbl_insert_description.setText("No matching helper item.")

    def _selected_helper_token(self):
        if not hasattr(self, "tbl_insert_items"):
            return ""
        items = self.tbl_insert_items.selectedItems()
        if not items:
            return ""
        row = items[0].row()
        item = self.tbl_insert_items.item(row, 0)
        return str(item.data(Qt.UserRole) or "") if item is not None else ""

    def _update_insert_helper_preview(self):
        token_text = self._selected_helper_token()
        desc = ""
        items = self.tbl_insert_items.selectedItems() if hasattr(self, "tbl_insert_items") else []
        if items:
            item = self.tbl_insert_items.item(items[0].row(), 0)
            if item is not None:
                desc = str(item.data(Qt.UserRole + 1) or "")
        self.txt_insert_token_preview.setText(token_text)
        self.lbl_insert_description.setText(desc)

    def _insert_selected_helper_item(self):
        token_text = self._selected_helper_token()
        if token_text:
            self._insert_preset_text(token_text)

    def _copy_selected_helper_item(self):
        token_text = self._selected_helper_token()
        if token_text:
            QtWidgets.QApplication.clipboard().setText(token_text)
            if hasattr(self, "lbl_insert_popup_status"):
                self.lbl_insert_popup_status.setText("Copied: %s" % token_text)

    def _insert_project_variable_token(self):
        name = str(self.txt_project_var_name.text() or "").strip() or "project_code"
        self._insert_preset_text("{var:%s}" % name)

    def _insert_env_variable_token(self):
        name = str(self.txt_env_var_name.text() or "").strip() or "USERPROFILE"
        self._insert_preset_text("{env:%s}" % name)

    def _insert_custom_date_token(self):
        fmt = str(self.txt_date_format.text() or "").strip() or "yyyyMMdd_HHmm"
        self._insert_preset_text("{date:%s}" % fmt)

    def _build_debug_tab(self):
        page = QtWidgets.QWidget(); page.setObjectName("tabDebugAbout")
        layout = QtWidgets.QVBoxLayout(page); layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._label("lblDebugDescription", "Use this tab to check whether the plugin is enabled, view the active button/path-box types, test debug output, and confirm the installed plugin version.", tooltip("UI#180", "QLabel", "lblDebugDescription", "Debug / About description", "Explains the purpose of the Debug / About tab.")))
        test_group = QtWidgets.QGroupBox("Manual debug tests")
        test_group.setObjectName("grpManualDebugTests")
        test_group.setToolTip(tooltip("UI#184", "QGroupBox", "grpManualDebugTests", "Manual debug tests", "Use these buttons to confirm the Debug / About tab and message logging are working before testing mouse events."))
        test_layout = QtWidgets.QVBoxLayout(test_group)
        test_row = QtWidgets.QHBoxLayout()
        self.btn_test_debug_log = QtWidgets.QPushButton("Run all debug tests")
        self.btn_test_debug_log.setObjectName("btnTestDebugLog")
        self.btn_test_debug_log.setToolTip(tooltip("UI#185", "QPushButton", "btnTestDebugLog", "Run all debug tests", "Runs internal FGQEP01 diagnostics and writes the result into the debug summary and QGIS message log."))
        self.btn_test_debug_log.clicked.connect(self._run_all_debug_tests)
        test_row.addWidget(self.btn_test_debug_log)
        self.btn_test_left_trace = QtWidgets.QPushButton("Start mouse event trace")
        self.btn_test_left_trace.setObjectName("btnTestLeftActionTrace")
        self.btn_test_left_trace.setToolTip(tooltip("UI#186", "QPushButton", "btnTestLeftActionTrace", "Start mouse event trace", "Starts recording QToolButton mouse events and QgsFileWidget detection in the recent trace."))
        self.btn_test_left_trace.clicked.connect(self._start_mouse_event_trace)
        test_row.addWidget(self.btn_test_left_trace)
        self.btn_stop_mouse_trace = QtWidgets.QPushButton("Stop mouse event trace")
        self.btn_stop_mouse_trace.setObjectName("btnStopMouseEventTrace")
        self.btn_stop_mouse_trace.setToolTip("Stops diagnostic mouse event tracing. UI index not rebuilt in v0.5.2 by request.")
        self.btn_stop_mouse_trace.clicked.connect(self._stop_mouse_event_trace)
        test_row.addWidget(self.btn_stop_mouse_trace)
        self.btn_clear_left_trace = QtWidgets.QPushButton("Clear trace")
        self.btn_clear_left_trace.setObjectName("btnClearLeftActionTrace")
        self.btn_clear_left_trace.setToolTip(tooltip("UI#187", "QPushButton", "btnClearLeftActionTrace", "Clear trace", "Clears the recent left-action trace."))
        self.btn_clear_left_trace.clicked.connect(self._clear_left_action_trace)
        test_row.addWidget(self.btn_clear_left_trace)
        self.btn_scan_active_dialog = QtWidgets.QPushButton("Scan active dialog buttons")
        self.btn_scan_active_dialog.setObjectName("btnScanActiveDialogButtons")
        self.btn_scan_active_dialog.setToolTip("Lists buttons and path/text widgets in the current active QDialog. Use this to diagnose third-party plugin Browse buttons.")
        self.btn_scan_active_dialog.clicked.connect(self._scan_active_dialog_buttons)
        test_row.addWidget(self.btn_scan_active_dialog)
        test_layout.addLayout(test_row)

        browse_test_row = QtWidgets.QHBoxLayout()
        browse_test_row.addWidget(self._label("lblTestBrowseButton", "Test browse button:", tooltip("UI#189", "QLabel", "lblTestBrowseButton", "Test browse button label", "Label for the fake browse button used to test mouse actions on the Debug / About page.")))
        self.btn_test_browse = QtWidgets.QToolButton()
        self.btn_test_browse.setObjectName("btnTestBrowseButton")
        self.btn_test_browse.setText("...")
        self.btn_test_browse.setToolTip(tooltip("UI#190", "QToolButton", "btnTestBrowseButton", "Fake browse test button", "Use this fake browse button to test left double-click, click-hold, right-click, and middle-click tracing without opening a QGIS file dialog. Normal left-click is native in real QGIS widgets."))
        self.btn_test_browse.installEventFilter(self)
        browse_test_row.addWidget(self.btn_test_browse)
        browse_test_row.addStretch(1)
        test_layout.addLayout(browse_test_row)
        test_layout.addWidget(self._label("lblTestBrowseButtonHelp", "Use the [...] test button to check mouse-event tracing without opening a QGIS file dialog.", tooltip("UI#191", "QLabel", "lblTestBrowseButtonHelp", "Fake browse test help", "Explains that the fake browse button is diagnostic only and does not open a file browser.")))

        self.lbl_last_debug_test = self._label("lblLastDebugTest", "Last debug test: never", tooltip("UI#188", "QLabel", "lblLastDebugTest", "Last debug test", "Shows when a manual debug test button was last clicked."))
        test_layout.addWidget(self.lbl_last_debug_test)
        layout.addWidget(test_group)

        self.txt_debug = QtWidgets.QPlainTextEdit(); self.txt_debug.setObjectName("txtDebugSummary"); self.txt_debug.setReadOnly(True)
        self.txt_debug.setToolTip(tooltip("UI#182", "QPlainTextEdit", "txtDebugSummary", "Current debug summary", "Shows enabled state, active button/path-box types, last detected dialog/widget, last result, and simple event counts."))
        self.txt_debug.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.txt_debug.textChanged.connect(lambda: self._fit_plain_text_to_contents(self.txt_debug, min_lines=4, max_lines=10))
        layout.addWidget(self.txt_debug)
        self.btn_about = QtWidgets.QPushButton("About"); self.btn_about.setObjectName("btnAbout")
        self.btn_about.setToolTip(tooltip("UI#183", "QPushButton", "btnAbout", "About", "Shows the plugin version and architecture baseline."))
        self.btn_about.clicked.connect(self._about); layout.addWidget(self.btn_about)
        self.tabs.addTab(page, "Debug / About")

    def eventFilter(self, obj, event):
        if getattr(self, "btn_test_browse", None) is not None and obj is self.btn_test_browse:
            return self._handle_test_browse_event(event)
        return super().eventFilter(obj, event)

    def _test_trace(self, message):
        try:
            self.plugin.event_filter._trace_left("TEST BUTTON: " + str(message))
        except Exception:
            pass
        try:
            self._refresh_debug_summary()
        except Exception:
            pass

    def _stop_test_browse_single_timer(self):
        if self._test_browse_single_timer is not None:
            try:
                self._test_browse_single_timer.stop()
                self._test_browse_single_timer.deleteLater()
            except Exception:
                pass
        self._test_browse_single_timer = None

    def _start_test_browse_single_timer(self):
        self._stop_test_browse_single_timer()
        self._test_browse_single_timer = QtCore.QTimer(self)
        self._test_browse_single_timer.setSingleShot(True)
        self._test_browse_single_timer.timeout.connect(self._fire_test_browse_single)
        try:
            interval = int(QtWidgets.QApplication.doubleClickInterval()) + 30
        except Exception:
            interval = 430
        self._test_trace("left release / pending single click: %d ms" % interval)
        self._test_browse_single_timer.start(interval)

    def _fire_test_browse_single(self):
        self._test_browse_single_timer = None
        self._test_trace("left single click fired")

    def _stop_test_browse_hold_timer(self):
        if self._test_browse_hold_timer is not None:
            try:
                self._test_browse_hold_timer.stop()
                self._test_browse_hold_timer.deleteLater()
            except Exception:
                pass
        self._test_browse_hold_timer = None

    def _start_test_browse_hold_timer(self):
        self._stop_test_browse_hold_timer()
        self._test_browse_hold_fired = False
        try:
            delay = int(self.spin_hold_delay.value())
        except Exception:
            delay = 500
        self._test_browse_hold_timer = QtCore.QTimer(self)
        self._test_browse_hold_timer.setSingleShot(True)
        self._test_browse_hold_timer.timeout.connect(self._fire_test_browse_hold)
        self._test_trace("left hold timer started: %d ms" % delay)
        self._test_browse_hold_timer.start(delay)

    def _fire_test_browse_hold(self):
        self._test_browse_hold_timer = None
        self._test_browse_hold_fired = True
        self._test_trace("left click-hold fired")

    def _handle_test_browse_event(self, event):
        etype = event.type()
        if etype == QtCore.QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self._test_browse_hold_fired = False
                self._test_browse_suppress_next_release = False
                self._test_trace("left press")
                self._start_test_browse_hold_timer()
                return True
            if event.button() == Qt.RightButton:
                self._test_trace("right press")
                return True
            if event.button() == Qt.MiddleButton:
                self._test_trace("middle press")
                return True
        if etype == QtCore.QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if self._test_browse_suppress_next_release:
                    self._test_browse_suppress_next_release = False
                    self._stop_test_browse_hold_timer()
                    self._test_browse_hold_fired = False
                    self._test_trace("left release suppressed after double-click")
                    return True
                self._stop_test_browse_hold_timer()
                if self._test_browse_hold_fired:
                    self._test_browse_hold_fired = False
                    self._stop_test_browse_single_timer()
                    self._test_trace("left release after hold")
                else:
                    self._start_test_browse_single_timer()
                return True
            if event.button() == Qt.RightButton:
                self._test_trace("right release / right click")
                return True
            if event.button() == Qt.MiddleButton:
                self._test_trace("middle release / middle click")
                return True
        if etype == QtCore.QEvent.MouseButtonDblClick:
            self._stop_test_browse_hold_timer()
            if event.button() == Qt.LeftButton:
                self._stop_test_browse_single_timer()
                self._test_browse_suppress_next_release = True
                self._test_browse_hold_fired = False
                self._test_trace("left double-click")
                return True
            if event.button() == Qt.RightButton:
                self._test_trace("right double-click")
                return True
        if etype == QtCore.QEvent.ContextMenu:
            self._test_trace("context menu event")
            return True
        return False

    def _set_combo_from_combo(self, target, source):
        value = source.currentData()
        idx = target.findData(value)
        if idx >= 0:
            target.setCurrentIndex(idx)

    def _copy_mouse_actions(self, source_prefix, target_prefix):
        for mouse_key, source_combo in self.action_combos.get(source_prefix, {}).items():
            target_combo = self.action_combos.get(target_prefix, {}).get(mouse_key)
            if target_combo is not None:
                self._set_combo_from_combo(target_combo, source_combo)

    def _extra_widget_map(self):
        return {
            "save_export": {
                "autofillContent": self.cbo_save_export_autofill_content,
                "missingDir": self.cbo_save_export_missing,
                "rasterNoExt": self.chk_save_export_raster_no_ext,
            },
            "save_file": {
                "autofillEnabled": self.chk_save_file_autofill,
                "autofillContent": self.cbo_save_file_autofill_content,
                "missingDir": self.cbo_save_file_missing,
            },
            "folder": {
                "autofillEnabled": self.chk_folder_autofill,
                "autofillContent": self.cbo_folder_autofill_content,
                "missingDir": self.cbo_folder_missing,
            },
            "open_file": {
                "autofillEnabled": self.chk_open_file_autofill,
                "autofillContent": self.cbo_open_file_autofill_content,
                "missingDir": self.cbo_open_file_missing,
            },
            "legacy": {
                "autofillContent": self.cbo_legacy_autofill_content,
            },
        }

    def _copy_extra_options(self, source_prefix, target_prefix):
        widget_map = self._extra_widget_map()
        source_widgets = widget_map.get(source_prefix, {})
        target_widgets = widget_map.get(target_prefix, {})
        for key, source_widget in source_widgets.items():
            target_widget = target_widgets.get(key)
            if target_widget is None:
                continue
            if isinstance(source_widget, QtWidgets.QComboBox) and isinstance(target_widget, QtWidgets.QComboBox):
                self._set_combo_from_combo(target_widget, source_widget)
            elif isinstance(source_widget, QtWidgets.QCheckBox) and isinstance(target_widget, QtWidgets.QCheckBox):
                target_widget.setChecked(source_widget.isChecked())

    def _copy_settings_to_targets(self, source_prefix, targets, copy_extras=True):
        """Copy settings from one behaviour tab to selected targets."""
        for target_prefix in targets:
            self._copy_mouse_actions(source_prefix, target_prefix)
            if copy_extras:
                self._copy_extra_options(source_prefix, target_prefix)

    def _copy_settings_from_tab(self, source_prefix):
        labels = dict(self._type_prefixes())
        combo = self.copy_target_combos.get(source_prefix)
        target_value = str(combo.currentData() or "") if combo is not None else ""
        if not target_value:
            self.copy_status_labels[source_prefix].setText("No copy target selected.")
            return
        if target_value == "__all__":
            targets = [p for p, _ in self._type_prefixes() if p != source_prefix]
        else:
            targets = [target_value] if target_value != source_prefix else []
        if not targets:
            self.copy_status_labels[source_prefix].setText("No valid target selected.")
            return
        copy_extras = self.copy_extra_checks[source_prefix].isChecked()
        for target_prefix in targets:
            self._copy_mouse_actions(source_prefix, target_prefix)
            if copy_extras:
                self._copy_extra_options(source_prefix, target_prefix)
        if combo is not None:
            combo.setCurrentIndex(0)
        if target_value == "__all__":
            self.copy_status_labels[source_prefix].setText("Copied settings to all other tabs.")
        else:
            self.copy_status_labels[source_prefix].setText("Copied settings to: %s." % labels.get(target_value, target_value))

    def _load_action_combos(self, prefix):
        for mouse_key, combo in self.action_combos.get(prefix, {}).items():
            self._set_combo(combo, self.settings.value(action_key(prefix, mouse_key)))

    def _save_action_combos(self, prefix):
        for mouse_key, combo in self.action_combos.get(prefix, {}).items():
            self.settings.set_value(action_key(prefix, mouse_key), combo.currentData())

    def _load(self):
        s = self.settings
        self.chk_enabled.setChecked(s.bool_value("enabled", True))
        self.chk_apply_save_export.setChecked(s.bool_value("apply/save_export", True))
        self.chk_apply_save_file.setChecked(s.bool_value("apply/save_file", False))
        self.chk_apply_folder.setChecked(s.bool_value("apply/folder", False))
        self.chk_apply_open_file.setChecked(s.bool_value("apply/open_file", False))
        self.chk_apply_legacy.setChecked(s.bool_value("apply/legacy", False))
        try:
            hold_delay = int(s.value("holdDelayMs", 500) or 500)
        except Exception:
            hold_delay = 500
        self.spin_hold_delay.setValue(max(200, min(2000, hold_delay)))
        try:
            startup_delay = int(s.value("startupDelayMs", 10000) or 0)
        except Exception:
            startup_delay = 10000
        self.spin_startup_delay.setValue(max(0, min(60000, startup_delay)))
        self.chk_menu_last_used.setChecked(s.bool_value("preset_menu/show_last_used", True))
        self.chk_menu_current_file.setChecked(s.bool_value("preset_menu/show_current_file_folder", True))
        self.chk_menu_project_home.setChecked(s.bool_value("preset_menu/show_project_home", True))
        self.chk_menu_qgz_folder.setChecked(s.bool_value("preset_menu/show_qgz_folder", True))
        self.chk_menu_presets.setChecked(s.bool_value("preset_menu/show_preset_folders", True))
        self.chk_menu_desktop.setChecked(s.bool_value("preset_menu/show_desktop", False))
        self.chk_menu_documents.setChecked(s.bool_value("preset_menu/show_documents", False))
        self.chk_menu_downloads.setChecked(s.bool_value("preset_menu/show_downloads", False))
        self.chk_menu_create_missing.setChecked(s.bool_value("preset_menu/create_missing_on_select", True))
        self.chk_menu_remember_last.setChecked(s.bool_value("preset_menu/remember_selected_as_last_used", True))
        self._set_combo(self.cbo_menu_unresolved, s.value("preset_menu/unresolvedMode"))
        self._set_menu_order(s.value("preset_menu/order"))
        for prefix in ("save_export", "save_file", "folder", "open_file", "legacy"):
            self._load_action_combos(prefix)
        self._set_combo(self.cbo_save_export_autofill_content, s.value("save_export/autofillContent"))
        self.chk_save_export_raster_no_ext.setChecked(s.bool_value("save_export/rasterNoExt", True))
        self._set_combo(self.cbo_save_export_missing, s.value("save_export/missingDir"))
        self.chk_save_file_autofill.setChecked(s.bool_value("save_file/autofillEnabled", False))
        self._set_combo(self.cbo_save_file_autofill_content, s.value("save_file/autofillContent"))
        self._set_combo(self.cbo_save_file_missing, s.value("save_file/missingDir"))
        self.chk_folder_autofill.setChecked(s.bool_value("folder/autofillEnabled", False))
        self._set_combo(self.cbo_folder_autofill_content, s.value("folder/autofillContent"))
        self._set_combo(self.cbo_folder_missing, s.value("folder/missingDir"))
        self.chk_open_file_autofill.setChecked(s.bool_value("open_file/autofillEnabled", False))
        self._set_combo(self.cbo_open_file_autofill_content, s.value("open_file/autofillContent"))
        self._set_combo(self.cbo_open_file_missing, s.value("open_file/missingDir"))
        self._set_combo(self.cbo_legacy_autofill_content, s.value("legacy/autofillContent"))
        self.chk_legacy_enabled.setChecked(s.bool_value("legacy/enabled", False))
        self.chk_legacy_debug_bypass.setChecked(s.bool_value("legacy/debugBypass", False))
        self.chk_legacy_middle_inspector.setChecked(s.bool_value("legacy/middleInspectEnabled", False))
        self.chk_legacy_bypass_dialog.setChecked(s.bool_value("legacy/bypassDialogAllowlist", False))
        self.chk_legacy_bypass_button_text.setChecked(s.bool_value("legacy/bypassButtonTextAllowlist", False))
        self.chk_legacy_bypass_button_object.setChecked(s.bool_value("legacy/bypassButtonObjectAllowlist", False))
        self.chk_legacy_bypass_target_object.setChecked(s.bool_value("legacy/bypassTargetObjectAllowlist", False))
        self.chk_legacy_qtoolbutton.setChecked(s.bool_value("legacy/detectQToolButton", True))
        self.chk_legacy_qpushbutton.setChecked(s.bool_value("legacy/detectQPushButton", True))
        self.chk_legacy_qcommandlinkbutton.setChecked(s.bool_value("legacy/detectQCommandLinkButton", False))
        self.chk_legacy_qcheckbox.setChecked(s.bool_value("legacy/detectQCheckBox", False))
        self.chk_legacy_qradiobutton.setChecked(s.bool_value("legacy/detectQRadioButton", False))
        self.chk_legacy_other_button.setChecked(s.bool_value("legacy/detectOtherAbstractButton", False))
        self.txt_legacy_dialog_allow.setPlainText(str(s.value("legacy/dialogAllowlist") or ""))
        self.txt_legacy_button_allow.setPlainText(str(s.value("legacy/buttonTextAllowlist") or ""))
        self.txt_legacy_button_object_allow.setPlainText(str(s.value("legacy/buttonObjectAllowlist") or ""))
        self.txt_legacy_target_object_allow.setPlainText(str(s.value("legacy/targetObjectAllowlist") or ""))
        self._set_combo(self.cbo_legacy_search_mode, s.value("legacy/pathSearchMode"))
        self.txt_presets.setPlainText(s.presets_text())
        self._preview_presets(); self._refresh_debug_summary()
        self._fit_plain_text_to_contents(self.txt_presets, min_lines=3, max_lines=9)
        self._fit_plain_text_to_contents(self.txt_preview, min_lines=2, max_lines=7)
        self._fit_plain_text_to_contents(self.txt_debug, min_lines=4, max_lines=10)

    def _write_settings(self):
        s = self.settings
        s.set_value("enabled", self.chk_enabled.isChecked())
        s.set_value("apply/save_export", self.chk_apply_save_export.isChecked())
        s.set_value("apply/save_file", self.chk_apply_save_file.isChecked())
        s.set_value("apply/folder", self.chk_apply_folder.isChecked())
        s.set_value("apply/open_file", self.chk_apply_open_file.isChecked())
        s.set_value("apply/legacy", self.chk_apply_legacy.isChecked())
        s.set_value("holdDelayMs", self.spin_hold_delay.value())
        s.set_value("startupDelayMs", self.spin_startup_delay.value())
        s.set_value("preset_menu/show_last_used", self.chk_menu_last_used.isChecked())
        s.set_value("preset_menu/show_current_file_folder", self.chk_menu_current_file.isChecked())
        s.set_value("preset_menu/show_project_home", self.chk_menu_project_home.isChecked())
        s.set_value("preset_menu/show_qgz_folder", self.chk_menu_qgz_folder.isChecked())
        s.set_value("preset_menu/show_preset_folders", self.chk_menu_presets.isChecked())
        s.set_value("preset_menu/show_desktop", self.chk_menu_desktop.isChecked())
        s.set_value("preset_menu/show_documents", self.chk_menu_documents.isChecked())
        s.set_value("preset_menu/show_downloads", self.chk_menu_downloads.isChecked())
        s.set_value("preset_menu/create_missing_on_select", self.chk_menu_create_missing.isChecked())
        s.set_value("preset_menu/remember_selected_as_last_used", self.chk_menu_remember_last.isChecked())
        s.set_value("preset_menu/unresolvedMode", self.cbo_menu_unresolved.currentData())
        s.set_value("preset_menu/order", self._menu_order_value())
        for prefix in ("save_export", "save_file", "folder", "open_file", "legacy"):
            self._save_action_combos(prefix)
        s.set_value("save_export/autofillContent", self.cbo_save_export_autofill_content.currentData())
        s.set_value("save_export/rasterNoExt", self.chk_save_export_raster_no_ext.isChecked())
        s.set_value("save_export/missingDir", self.cbo_save_export_missing.currentData())
        s.set_value("save_file/autofillEnabled", self.chk_save_file_autofill.isChecked())
        s.set_value("save_file/autofillContent", self.cbo_save_file_autofill_content.currentData())
        s.set_value("save_file/missingDir", self.cbo_save_file_missing.currentData())
        s.set_value("folder/autofillEnabled", self.chk_folder_autofill.isChecked())
        s.set_value("folder/autofillContent", self.cbo_folder_autofill_content.currentData())
        s.set_value("folder/missingDir", self.cbo_folder_missing.currentData())
        s.set_value("open_file/autofillEnabled", self.chk_open_file_autofill.isChecked())
        s.set_value("open_file/autofillContent", self.cbo_open_file_autofill_content.currentData())
        s.set_value("open_file/missingDir", self.cbo_open_file_missing.currentData())
        s.set_value("legacy/autofillContent", self.cbo_legacy_autofill_content.currentData())
        s.set_value("legacy/enabled", self.chk_legacy_enabled.isChecked())
        s.set_value("legacy/debugBypass", self.chk_legacy_debug_bypass.isChecked())
        s.set_value("legacy/middleInspectEnabled", self.chk_legacy_middle_inspector.isChecked())
        s.set_value("legacy/bypassDialogAllowlist", self.chk_legacy_bypass_dialog.isChecked())
        s.set_value("legacy/bypassButtonTextAllowlist", self.chk_legacy_bypass_button_text.isChecked())
        s.set_value("legacy/bypassButtonObjectAllowlist", self.chk_legacy_bypass_button_object.isChecked())
        s.set_value("legacy/bypassTargetObjectAllowlist", self.chk_legacy_bypass_target_object.isChecked())
        s.set_value("legacy/detectQToolButton", self.chk_legacy_qtoolbutton.isChecked())
        s.set_value("legacy/detectQPushButton", self.chk_legacy_qpushbutton.isChecked())
        s.set_value("legacy/detectQCommandLinkButton", self.chk_legacy_qcommandlinkbutton.isChecked())
        s.set_value("legacy/detectQCheckBox", self.chk_legacy_qcheckbox.isChecked())
        s.set_value("legacy/detectQRadioButton", self.chk_legacy_qradiobutton.isChecked())
        s.set_value("legacy/detectOtherAbstractButton", self.chk_legacy_other_button.isChecked())
        s.set_value("legacy/dialogAllowlist", self.txt_legacy_dialog_allow.toPlainText())
        s.set_value("legacy/buttonTextAllowlist", self.txt_legacy_button_allow.toPlainText())
        s.set_value("legacy/buttonObjectAllowlist", self.txt_legacy_button_object_allow.toPlainText())
        s.set_value("legacy/targetObjectAllowlist", self.txt_legacy_target_object_allow.toPlainText())
        s.set_value("legacy/pathSearchMode", self.cbo_legacy_search_mode.currentData())
        s.set_value("presets", self.txt_presets.toPlainText())
        try:
            s.reload_cache()
        except Exception:
            pass

    def _apply(self):
        self._write_settings()
        self._refresh_debug_summary()
        try:
            self.lbl_last_debug_test.setText("Last debug test: settings applied")
        except Exception:
            pass

    def _save(self):
        self._write_settings()
        self.accept()

    def _restore(self):
        self.settings.restore_defaults(); self._load()

    def _preview_presets(self):
        try:
            items = resolve_preset_items(self.txt_presets.toPlainText())
            lines = []
            for item in items:
                if item.get("ok"):
                    lines.append("%s = %s" % (item.get("name"), item.get("path")))
                else:
                    lines.append("%s = unavailable - %s" % (item.get("name"), item.get("reason", "unresolved")))
            self.txt_preview.setPlainText("\n".join(lines or ["No presets found."]))
            self._fit_plain_text_to_contents(self.txt_preview, min_lines=2, max_lines=7)
        except Exception as exc:
            self.txt_preview.setPlainText("Preset preview failed: %s" % exc)
            self._fit_plain_text_to_contents(self.txt_preview, min_lines=2, max_lines=7)

    def _refresh_debug_summary(self):
        f = getattr(self.plugin, "event_filter", None)
        if f is None:
            summary = "Event filter not available."
        else:
            left_trace = getattr(f, "left_trace", []) or []
            summary = "Enabled: %s\nApply to: %s\nMouse event trace: %s\nLast dialog: %s\nLast widget: %s\nLast result: %s\nCounts: %s\n\nRecent left-action trace:\n%s" % (
                self.settings.bool_value("enabled", True),
                self.settings.enabled_types_summary(),
                "on" if getattr(f, "mouse_trace_enabled", False) else "off",
                getattr(f, "last_dialog", ""), getattr(f, "last_widget", ""), getattr(f, "last_result", ""), getattr(f, "debug_counts", {}),
                "\n".join(left_trace[-12:]) if left_trace else "None")
        self.txt_debug.setPlainText(summary)
        self._fit_plain_text_to_contents(self.txt_debug, min_lines=4, max_lines=10)


    def _debug_timestamp(self):
        try:
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "now"

    def _set_last_debug_test(self, text):
        try:
            self.lbl_last_debug_test.setText("Last debug test: %s" % text)
        except Exception:
            pass

    def _run_all_debug_tests(self):
        stamp = self._debug_timestamp()
        results = []

        def add(name, ok, detail=""):
            status = "PASS" if ok else "FAIL"
            results.append("%s - %s%s" % (status, name, (": " + detail) if detail else ""))

        try:
            self.plugin.log("FGQEP01 run all debug tests clicked at %s" % stamp)
            add("debug log", True)
        except Exception as exc:
            add("debug log", False, str(exc))

        try:
            f = self.plugin.event_filter
            f._trace_left("Run all debug tests at %s" % stamp)
            add("trace system", True)
        except Exception as exc:
            add("trace system", False, str(exc))

        try:
            self.settings.reload_cache()
            add("settings cache", True, "enabled=%s" % self.settings.cached_bool("enabled", True))
        except Exception as exc:
            add("settings cache", False, str(exc))

        try:
            f = self.plugin.event_filter
            add("event filter object", f is not None)
            add("event filter installed", bool(getattr(f, "_installed", False)))
            add("mouse event trace", bool(getattr(f, "mouse_trace_enabled", False)), "on" if getattr(f, "mouse_trace_enabled", False) else "off")
        except Exception as exc:
            add("event filter status", False, str(exc))

        try:
            add("enabled button/path-box types", True, self.settings.enabled_types_summary())
        except Exception as exc:
            add("enabled button/path-box types", False, str(exc))

        try:
            action_lines = []
            for prefix, label in self._type_prefixes():
                vals = []
                for mouse_key, mouse_label in MOUSE_ACTIONS:
                    if mouse_key in (MOUSE_LEFT_CLICK, MOUSE_RIGHT_DOUBLE):
                        continue
                    vals.append("%s=%s" % (mouse_label, self.settings.cached_value(action_key(prefix, mouse_key))))
                action_lines.append("%s: %s" % (label, "; ".join(vals)))
            add("mouse-action settings", True)
            results.extend(["  " + line for line in action_lines])
        except Exception as exc:
            add("mouse-action settings", False, str(exc))

        try:
            add("hold delay", True, "%s ms" % self.settings.cached_value("holdDelayMs", 500))
            add("startup delay", True, "%s ms" % self.settings.cached_value("startupDelayMs", 10000))
        except Exception as exc:
            add("hold delay", False, str(exc))

        try:
            menu_bits = [
                "last_used=%s" % self.settings.cached_bool("preset_menu/show_last_used", True),
                "current_file=%s" % self.settings.cached_bool("preset_menu/show_current_file_folder", True),
                "project_home=%s" % self.settings.cached_bool("preset_menu/show_project_home", True),
                "qgz_folder=%s" % self.settings.cached_bool("preset_menu/show_qgz_folder", True),
                "presets=%s" % self.settings.cached_bool("preset_menu/show_preset_folders", True),
            ]
            add("preset menu settings", True, ", ".join(menu_bits))
        except Exception as exc:
            add("preset menu settings", False, str(exc))

        try:
            preset_count = len(resolve_presets(self.settings.presets_text()))
            add("preset parser", True, "%d preset(s)" % preset_count)
        except Exception as exc:
            add("preset parser", False, str(exc))

        summary = "Debug test result at %s:\n%s" % (stamp, "\n".join(results))
        try:
            self.plugin.log(summary)
        except Exception:
            pass
        try:
            self.plugin.iface.messageBar().pushInfo(PLUGIN_NAME, "FGQEP01 debug tests completed")
        except Exception:
            pass
        try:
            self.txt_debug.setPlainText(summary + "\n\n" + self.txt_debug.toPlainText())
        except Exception:
            pass
        self._set_last_debug_test(stamp + " (all tests)")

    def _start_mouse_event_trace(self):
        stamp = self._debug_timestamp()
        try:
            self.plugin.event_filter.set_mouse_trace_enabled(True)
        except Exception:
            pass
        self._set_last_debug_test(stamp + " (mouse trace started)")
        self._refresh_debug_summary()

    def _stop_mouse_event_trace(self):
        stamp = self._debug_timestamp()
        try:
            self.plugin.event_filter.set_mouse_trace_enabled(False)
        except Exception:
            pass
        self._set_last_debug_test(stamp + " (mouse trace stopped)")
        self._refresh_debug_summary()

    def _test_debug_log(self):
        self._run_all_debug_tests()

    def _test_left_action_trace(self):
        self._start_mouse_event_trace()


    def _scan_active_dialog_buttons(self):
        stamp = self._debug_timestamp()
        try:
            result = self.plugin.event_filter.scan_active_dialog_widgets()
        except Exception as exc:
            result = "Scan active dialog failed: %s" % exc
        try:
            self.plugin.log("FGQEP01 active dialog scan at %s:\n%s" % (stamp, result))
        except Exception:
            pass
        try:
            self.txt_debug.setPlainText("Active dialog scan at %s:\n%s\n\n%s" % (stamp, result, self.txt_debug.toPlainText()))
        except Exception:
            pass
        try:
            self.plugin.event_filter._trace_left("Active dialog scan run at %s" % stamp)
        except Exception:
            pass
        self._set_last_debug_test(stamp + " (active dialog scan)")

    def _clear_left_action_trace(self):
        stamp = self._debug_timestamp()
        try:
            self.plugin.event_filter.left_trace = []
            self.plugin.event_filter.last_result = "Left-action trace cleared manually"
        except Exception:
            pass
        self._set_last_debug_test(stamp + " (trace cleared)")
        self._refresh_debug_summary()

    def _about(self):
        about_text = (
            "%s v%s\n\n"
            "- Improves the QGIS Save/Export browse button and path boxes without replacing the normal QGIS dialogs.\n"
            "- Only works on real QGIS file/path widgets, so it avoids unrelated buttons.\n"
            "- Adds extra mouse actions, such as double-click, long-press, right-click, and middle-click shortcuts.\n"
            "- Provides folder presets, token-based paths, and automatic path filling.\n"
            "- Includes an advanced mode area for future custom widgets, diagnostics, and extended action mapping.\n"
            "- Can wait a short time after QGIS starts before turning on the event filter.\n"
            "- This is a personal open-source plugin, not an employer or client tool.\n"
            "- It does not intentionally include company files, client data, project files, internal templates, or private code.\n"
            "- Users should test it before using it in real work.\n\n"
            "FGQEP01 Browse Enhancer is part of FGQEP, a personal QGIS Enhancement Project — a collection of focused QGIS enhancement plugins designed to improve everyday GIS productivity, streamline repetitive workflows, and provide practical user-interface improvements for all QGIS users."
        ) % (PLUGIN_NAME, PLUGIN_VERSION)
        QtWidgets.QMessageBox.information(self, "About " + PLUGIN_NAME, about_text)
