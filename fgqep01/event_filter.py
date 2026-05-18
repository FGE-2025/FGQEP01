# -*- coding: utf-8 -*-
"""Global event filter for FGQEP01 Browse Enhancer.

v0.8.1 performance notes:
- Custom/Advanced detection is pre-gated so UI131 does not scan every dialog button;

v0.6.5 mouse notes:
- no live QgsSettings reads in eventFilter() hot paths;
- normal left-click is always native QGIS browse, but is delayed when left double-click or hold is configured;
- left click-and-hold remains configurable and can swallow release after hold fires;
- normal left double-click remains configurable;
- Shift + left double-click opens the plugin folder as a diagnostic shortcut;
- right double-click is dropped/ignored.
"""

from __future__ import annotations

import os
import weakref

from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.gui import QgsFileWidget

from .path_resolver import project_home
from .tokens import qgz_folder, desktop_folder, documents_folder, downloads_folder
from .scope_rules import autofill_allowed, is_save_export_dialog, target_allowed
from .settings_model import (
    ACTION_AUTOFILL,
    ACTION_CLEAR_THEN_AUTOFILL,
    ACTION_CLEAR_PATH,
    ACTION_COPY_PATH,
    ACTION_DO_NOTHING,
    ACTION_LAST_USED,
    ACTION_NATIVE,
    ACTION_OPEN_FOLDER,
    ACTION_PROJECT_HOME,
    ACTION_SHOW_MENU,
    MOUSE_LEFT_DOUBLE,
    MOUSE_LEFT_HOLD,
    MOUSE_MIDDLE_CLICK,
    MOUSE_RIGHT_CLICK,
    TYPE_SAVE_EXPORT,
    TYPE_LEGACY,
)


TRACE_LIMIT = 12
DEFAULT_HOLD_DELAY_MS = 500
MIN_HOLD_DELAY_MS = 200
MAX_HOLD_DELAY_MS = 2000
DOUBLE_CLICK_EXTRA_MS = 30


class LegacyPathWidget(object):
    """Small adapter for allowlisted legacy/custom plugin Browse buttons.

    It exposes the minimal QgsFileWidget-like API used by FGQEP01 actions.
    The target can be a QLineEdit, QTextEdit or QPlainTextEdit.
    """

    def __init__(self, widget):
        self.widget = widget

    def hasTarget(self):
        return self.widget is not None

    def objectName(self):
        if self.widget is None:
            return "LegacyPathWidget(no target)"
        try:
            return self.widget.objectName()
        except Exception:
            return "LegacyPathWidget"

    def window(self):
        if self.widget is None:
            return None
        try:
            return self.widget.window()
        except Exception:
            return None

    def filePath(self):
        w = self.widget
        if w is None:
            return ""
        if isinstance(w, QtWidgets.QLineEdit):
            return w.text()
        if isinstance(w, QtWidgets.QPlainTextEdit):
            return w.toPlainText()
        if isinstance(w, QtWidgets.QTextEdit):
            return w.toPlainText()
        return ""

    def setFilePath(self, path):
        w = self.widget
        if w is None:
            return
        if isinstance(w, QtWidgets.QLineEdit):
            w.setText(path)
            return
        if isinstance(w, QtWidgets.QPlainTextEdit):
            w.setPlainText(path)
            return
        if isinstance(w, QtWidgets.QTextEdit):
            w.setPlainText(path)
            return


class FGQEP01EventFilter(QtCore.QObject):
    """Lean event filter for QgsFileWidget plus allowlisted legacy buttons."""

    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.settings = plugin.settings
        self.resolver = plugin.resolver
        self._installed = False
        self._handled_dialogs = set()
        self._hold_timer = None
        self._hold_fired = False
        self._hold_payload = None
        self._left_click_timer = None
        self._left_click_payload = None
        self._left_stream_controlled = False
        self._ignore_next_left_release = False
        self._suppress_left_release_button = None
        self._last_left_payload = None
        self._replaying_native_click = False
        self._active_menu = None
        self._logged_event_error = False
        self.debug_counts = {"dialogs": 0, "autofill": 0, "skipped": 0, "menus": 0, "actions": 0}
        self.left_trace = []
        self.mouse_trace_enabled = False
        self.last_dialog = ""
        self.last_widget = ""
        self.last_result = ""

    def install(self):
        if self._installed:
            return
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._installed = True

    def remove(self):
        self._stop_hold_timer()
        self._stop_left_click_timer(reason="plugin removed")
        if not self._installed:
            return
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._installed = False

    def eventFilter(self, obj, event):
        try:
            return self._event_filter(obj, event)
        except Exception as exc:
            # Never let a global event filter bring QGIS down. Log once only and
            # return False so native QGIS behaviour continues.
            self.last_result = "Event filter skipped after error: %s" % exc
            if not self._logged_event_error:
                self._logged_event_error = True
                try:
                    self.plugin.log(self.last_result)
                except Exception:
                    pass
            return False

    def _event_filter(self, obj, event):
        if self._replaying_native_click:
            return False
        if not self.settings.cached_bool("enabled", True):
            return False
        etype = event.type()

        # Read-only widget inspector: middle double-click any widget to capture
        # allowlist/mapping information. It runs before browse actions and does
        # not modify the clicked control.
        if self.settings.cached_bool("legacy/middleInspectEnabled", False):
            try:
                if etype == QtCore.QEvent.MouseButtonDblClick and hasattr(event, "button") and event.button() == Qt.MiddleButton:
                    if self._inspect_clicked_widget(obj):
                        return True
            except Exception as exc:
                self._trace_left("inspector failed: %s" % exc)
                return False

        # Stop pending actions only when the relevant watched widget/dialog is
        # closing. v0.6.3 cancelled delayed native single-click on unrelated
        # Hide/Close events, which made single-click browse unreliable.
        if etype in (QtCore.QEvent.Hide, QtCore.QEvent.Close, QtCore.QEvent.DeferredDelete):
            self._cancel_pending_for_object(obj, self._event_type_name(etype))
            return False

        # Dialog-show autofill is restricted to Save/Export only. Broader path-box
        # types are handled only when the actual QgsFileWidget button is clicked.
        if etype == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QDialog):
            if self.settings.type_enabled(TYPE_SAVE_EXPORT) and is_save_export_dialog(obj):
                self._on_dialog_show(obj)
            return False

        # Fast exit: do not inspect arbitrary widgets. Custom/legacy support is
        # still button-only and allowlist-gated. When diagnostic mouse tracing is
        # enabled, also record non-button mouse targets inside QDialogs so custom
        # plugin buttons that deliver events through child widgets can be seen.
        if not isinstance(obj, QtWidgets.QAbstractButton):
            self._trace_non_button_mouse_event(obj, event)
            return False

        self._trace_mouse_event(obj, event)

        if etype == QtCore.QEvent.ContextMenu:
            return self._on_context_menu(obj, event)
        if etype == QtCore.QEvent.MouseButtonDblClick:
            return self._on_mouse_double_click(obj, event)
        if etype == QtCore.QEvent.MouseButtonPress:
            return self._on_mouse_press(obj, event)
        if etype == QtCore.QEvent.MouseButtonRelease:
            return self._on_mouse_release(obj, event)
        return False

    def _button_from_widget(self, widget):
        """Return nearest parent QAbstractButton for a clicked child widget."""
        current = widget
        while current is not None:
            if isinstance(current, QtWidgets.QAbstractButton):
                return current
            current = current.parentWidget() if hasattr(current, "parentWidget") else None
        return None

    def _highlight_widget(self, widget):
        """Simple temporary red outline around a widget."""
        if widget is None:
            return
        try:
            old_style = widget.styleSheet()
        except Exception:
            old_style = ""
        try:
            widget.setStyleSheet((old_style or "") + "\noutline: 2px solid red; border: 2px solid red;")
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)
            def restore():
                try:
                    widget.setStyleSheet(old_style)
                except Exception:
                    pass
                try:
                    timer.deleteLater()
                except Exception:
                    pass
            timer.timeout.connect(restore)
            timer.start(2000)
        except Exception:
            pass

    def _candidate_target_widgets(self, dialog):
        out = []
        if not isinstance(dialog, QtWidgets.QDialog):
            return out
        for cls in (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit):
            try:
                for w in dialog.findChildren(cls):
                    try:
                        out.append((w.__class__.__name__, w.objectName() or "", self._widget_text_value(w)))
                    except Exception:
                        pass
            except Exception:
                pass
        return out

    def _widget_text_value(self, widget):
        """Return the most useful visible text/value for common Qt widgets."""
        try:
            if isinstance(widget, QtWidgets.QLineEdit):
                return widget.text()
            if isinstance(widget, QtWidgets.QPlainTextEdit):
                return widget.toPlainText()
            if isinstance(widget, QtWidgets.QTextEdit):
                return widget.toPlainText()
            if isinstance(widget, QtWidgets.QAbstractButton):
                return widget.text()
            if isinstance(widget, QtWidgets.QLabel):
                return widget.text()
            if isinstance(widget, QtWidgets.QGroupBox):
                return widget.title()
            if isinstance(widget, QtWidgets.QComboBox):
                return widget.currentText()
            if isinstance(widget, QtWidgets.QTabWidget):
                idx = widget.currentIndex()
                return widget.tabText(idx) if idx >= 0 else ""
            if isinstance(widget, QtWidgets.QListWidget):
                item = widget.currentItem()
                return item.text() if item is not None else ""
            if isinstance(widget, QtWidgets.QTreeWidget):
                item = widget.currentItem()
                return item.text(0) if item is not None else ""
            # Last-resort support for widgets exposing text() or title().
            if hasattr(widget, "text"):
                value = widget.text()
                if isinstance(value, str):
                    return value
            if hasattr(widget, "title"):
                value = widget.title()
                if isinstance(value, str):
                    return value
        except Exception:
            pass
        return ""

    def _show_widget_info_popup(self, text):
        """Show a small copyable widget-inspector result popup."""
        try:
            dlg = QtWidgets.QDialog(self.plugin.iface.mainWindow())
        except Exception:
            dlg = QtWidgets.QDialog()
        dlg.setWindowTitle("FGQEP01 Widget info")
        dlg.setModal(False)
        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel("Clicked widget information")
        label.setWordWrap(True)
        layout.addWidget(label)
        edit = QtWidgets.QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(text)
        edit.setMinimumWidth(520)
        edit.setMinimumHeight(150)
        layout.addWidget(edit)
        buttons = QtWidgets.QHBoxLayout()
        copy_btn = QtWidgets.QPushButton("Copy to clipboard")
        close_btn = QtWidgets.QPushButton("Close")
        buttons.addStretch(1)
        buttons.addWidget(copy_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        def copy_text():
            try:
                QtWidgets.QApplication.clipboard().setText(text)
            except Exception:
                pass

        copy_btn.clicked.connect(copy_text)
        close_btn.clicked.connect(dlg.close)
        dlg.show()
        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass
        # Keep a reference so the modeless popup is not garbage collected.
        self._last_widget_info_popup = dlg

    def _inspect_clicked_widget(self, clicked):
        """Capture compact information for any clicked UI widget.

        This inspector is intentionally read-only. It reports the exact widget
        that received the middle double-click, not only parent buttons.
        """
        dialog = clicked.window() if hasattr(clicked, "window") else None
        if not isinstance(dialog, QtWidgets.QDialog):
            self._trace_left("inspector: clicked widget is not inside a QDialog")
            return False

        item_name = clicked.objectName() or ""
        item_text = self._widget_text_value(clicked) or ""
        item_type = clicked.__class__.__name__
        title = dialog.windowTitle() or ""

        lines = [
            "Dialog title: %s" % (title or "<empty>"),
            "Item type: %s" % item_type,
            "Item text: %s" % (item_text or "<empty>"),
            "Item objectName: %s" % (item_name or "<empty>"),
        ]
        result = "\n".join(lines)
        self.last_result = result
        self._trace_left("inspector captured: %s | %s | %s" % (item_type, item_name or "<empty>", item_text or "<empty>"))
        try:
            self.plugin.log(result)
        except Exception:
            pass
        self._highlight_widget(clicked)
        self._show_widget_info_popup(result)
        return True

    def qgsfilewidget_of(self, widget):
        current = widget
        while current is not None:
            if isinstance(current, QgsFileWidget):
                return current
            current = current.parentWidget() if hasattr(current, "parentWidget") else None
        return None

    def _list_setting(self, name):
        text = str(self.settings.cached_value(name, "") or "")
        return [line.strip().lower() for line in text.splitlines() if line.strip()]

    def _legacy_debug_bypass(self):
        return self.settings.cached_bool("legacy/debugBypass", False)

    def _legacy_bypass_dialog_allowlist(self):
        return self._legacy_debug_bypass() or self.settings.cached_bool("legacy/bypassDialogAllowlist", False)

    def _legacy_bypass_button_text_allowlist(self):
        return self._legacy_debug_bypass() or self.settings.cached_bool("legacy/bypassButtonTextAllowlist", False)

    def _legacy_bypass_button_object_allowlist(self):
        return self._legacy_debug_bypass() or self.settings.cached_bool("legacy/bypassButtonObjectAllowlist", False)

    def _legacy_bypass_target_object_allowlist(self):
        return self._legacy_debug_bypass() or self.settings.cached_bool("legacy/bypassTargetObjectAllowlist", False)

    def _legacy_enabled(self):
        # Normal custom/advanced support requires both the General apply checkbox
        # and the Custom/Advanced tab enable checkbox. Debug bypass intentionally
        # relaxes the General apply checkbox so users can diagnose why a third-
        # party Browse button is not being detected, but the Custom/Advanced
        # feature must still be explicitly enabled.
        return self.settings.cached_bool("legacy/enabled", False) and (self.settings.type_enabled(TYPE_LEGACY) or self._legacy_debug_bypass())

    def _legacy_dialog_allowed(self, dialog):
        title = (dialog.windowTitle() or "").lower()
        allow = self._list_setting("legacy/dialogAllowlist")
        bypass = self._legacy_bypass_dialog_allowlist()
        self._trace_left('custom bypass state: dialogTitle=%s' % bypass)
        if bypass:
            self._trace_left('custom bypass: dialog title allowlist bypassed for "%s"' % (dialog.windowTitle() or dialog.__class__.__name__))
            return True
        if not allow:
            self._trace_left('custom rejected: dialog title allowlist blank and bypass off')
            return False
        matched = any(item in title for item in allow)
        if not matched:
            self._trace_left('custom rejected: dialog title "%s" not allowlisted' % (dialog.windowTitle() or "<empty>"))
        else:
            self._trace_left('custom matched: dialog title allowlist')
        return matched

    def _legacy_button_type_allowed(self, button):
        # These button type toggles apply only to Custom / Advanced mode.
        # Normal FGQEP01 QgsFileWidget detection is handled separately.
        qcommand = getattr(QtWidgets, "QCommandLinkButton", None)
        if qcommand is not None and isinstance(button, qcommand):
            return self.settings.cached_bool("legacy/detectQCommandLinkButton", False)
        if isinstance(button, QtWidgets.QToolButton):
            return self.settings.cached_bool("legacy/detectQToolButton", True)
        if isinstance(button, QtWidgets.QPushButton):
            return self.settings.cached_bool("legacy/detectQPushButton", True)
        if isinstance(button, QtWidgets.QCheckBox):
            return self.settings.cached_bool("legacy/detectQCheckBox", False)
        if isinstance(button, QtWidgets.QRadioButton):
            return self.settings.cached_bool("legacy/detectQRadioButton", False)
        return self.settings.cached_bool("legacy/detectOtherAbstractButton", False)

    def _legacy_button_allowed(self, button):
        """Return True when the custom/advanced button passes all active button allowlists.

        v0.7.7 tightened the semantics after testing showed blank allowlists
        could still pass when another allowlist was bypassed. Formal rule:
        every non-bypassed allowlist is mandatory; if it is blank it matches
        nothing. A bypass skips only its own allowlist.
        """
        if not self._legacy_button_type_allowed(button):
            self._trace_left('custom trace: button type %s not enabled' % button.__class__.__name__)
            return False

        text = (button.text() or "").strip().lower()
        name = (button.objectName() or "").strip().lower()

        self._trace_left('custom candidate: type=%s objectName=%s text="%s"' % (button.__class__.__name__, button.objectName() or "", button.text() or ""))

        name_allow = self._list_setting("legacy/buttonObjectAllowlist")
        text_allow = self._list_setting("legacy/buttonTextAllowlist")
        bypass_name = self._legacy_bypass_button_object_allowlist()
        bypass_text = self._legacy_bypass_button_text_allowlist()

        self._trace_left('custom bypass state: buttonText=%s buttonObject=%s' % (bypass_text, bypass_name))

        if bypass_name:
            self._trace_left('custom bypass: button objectName allowlist bypassed')
        else:
            if not name_allow:
                self._trace_left('custom rejected: button objectName allowlist blank and bypass off')
                return False
            if not name or not any(item == name or item in name for item in name_allow):
                self._trace_left('custom rejected: button objectName "%s" not allowlisted' % (name or "<empty>"))
                return False
            self._trace_left('custom matched: button objectName allowlist')

        if bypass_text:
            self._trace_left('custom bypass: button text allowlist bypassed')
        else:
            if not text_allow:
                self._trace_left('custom rejected: button text allowlist blank and bypass off')
                return False
            if not text or not any(item == text or item in text for item in text_allow):
                self._trace_left('custom rejected: button text "%s" not allowlisted' % (text or "<empty>"))
                return False
            self._trace_left('custom matched: button text allowlist')

        return True

    def _legacy_text_widgets(self, root):
        widgets = []
        for cls in (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit):
            try:
                widgets.extend(root.findChildren(cls))
            except Exception:
                pass
        out = []
        for w in widgets:
            try:
                if w.isEnabled() and w.isVisible():
                    out.append(w)
            except Exception:
                pass
        return out

    def _widget_center_global(self, widget):
        rect = widget.rect()
        return widget.mapToGlobal(rect.center())

    def _legacy_find_path_widget(self, button, dialog):
        target_allow = self._list_setting("legacy/targetObjectAllowlist")
        bypass_target = self._legacy_bypass_target_object_allowlist()
        self._trace_left('custom bypass state: targetTextbox=%s' % bypass_target)
        if target_allow and not bypass_target:
            for w in self._legacy_text_widgets(dialog):
                try:
                    name = (w.objectName() or "").strip().lower()
                    if name and any(item == name or item in name for item in target_allow):
                        self._trace_left('custom matched: target textbox objectName "%s"' % (w.objectName() or ""))
                        return w
                except Exception:
                    continue
            self._trace_left('custom rejected target: no textbox matched objectName allowlist')
            return None
        if not target_allow and not bypass_target:
            self._trace_left('custom target unresolved: target textbox allowlist blank and bypass off; menu-only actions may still run')
            return None
        if bypass_target:
            self._trace_left('custom bypass: target textbox objectName allowlist bypassed; using safe target search')

        mode = str(self.settings.cached_value("legacy/pathSearchMode", "nearby") or "nearby")
        candidates = []
        roots = []
        if mode in ("nearby", "parent"):
            parent = button.parentWidget()
            if parent is not None:
                roots.append(parent)
        if mode == "dialog" or not roots:
            roots.append(dialog)
        seen = set()
        btn_center = self._widget_center_global(button)
        btn_x = btn_center.x(); btn_y = btn_center.y()
        for root in roots:
            for w in self._legacy_text_widgets(root):
                if w is button or id(w) in seen:
                    continue
                seen.add(id(w))
                try:
                    g = w.mapToGlobal(w.rect().topLeft())
                    rect = QtCore.QRect(g, w.size())
                    # For the safest mode, only accept fields near the same row
                    # or fields whose vertical span contains the browse button.
                    if mode == "nearby":
                        vertical_match = rect.top() - 12 <= btn_y <= rect.bottom() + 12
                        same_row = abs(rect.center().y() - btn_y) <= max(40, rect.height())
                        if not (vertical_match or same_row):
                            continue
                    # Prefer text fields to the left of the button and close to it.
                    dx = max(0, btn_x - rect.right())
                    dy = abs(rect.center().y() - btn_y)
                    same_parent_bonus = 0 if w.parentWidget() is button.parentWidget() else 500
                    score = same_parent_bonus + dy * 4 + dx
                    candidates.append((score, w))
                except Exception:
                    continue
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _legacy_button_target(self, button):
        if not self._legacy_enabled():
            return None, None, None
        dialog = button.window()
        if not isinstance(dialog, QtWidgets.QDialog):
            return None, None, None
        if not self._legacy_dialog_allowed(dialog):
            return None, None, None
        if not self._legacy_button_allowed(button):
            return None, None, None
        path_widget = self._legacy_find_path_widget(button, dialog)
        self.last_dialog = dialog.windowTitle() or dialog.__class__.__name__
        btn_label = button.text() or button.objectName() or button.__class__.__name__
        if path_widget is None:
            self.last_widget = "No target path box"
            self._trace_left('custom trace: dialog="%s" matched, button="%s" matched, target path box not found; non-target actions may still run' % (self.last_dialog, button.text() or button.__class__.__name__))
            return LegacyPathWidget(None), dialog, TYPE_LEGACY
        self.last_widget = path_widget.objectName() or path_widget.__class__.__name__
        self._trace_left('custom trace: button type=%s objectName=%s text="%s" target=%s allowed=True' % (button.__class__.__name__, button.objectName() or "", button.text() or "", self.last_widget))
        self._trace_left('custom trace: dialog="%s" button="%s" target=%s allowed=True' % (self.last_dialog, btn_label, self.last_widget))
        return LegacyPathWidget(path_widget), dialog, TYPE_LEGACY

    def _dialog_id(self, dialog):
        try:
            if dialog.testAttribute(Qt.WA_WState_Created):
                return int(dialog.winId())
        except Exception:
            pass
        return id(dialog)

    def _cancel_pending_for_object(self, obj, event_name):
        """Cancel delayed single-click only if the pending target is closing.

        Global Qt Hide/Close events are noisy in QGIS and Windows dialogs. Do
        not cancel a pending native browse just because an unrelated widget hid.
        """
        try:
            payload = self._left_click_payload
            if payload:
                _action, fw, dialog, button, _button_type = payload
                if obj is fw or obj is dialog or obj is button:
                    self._stop_left_click_timer(reason="target %s" % event_name)
            # Keep hold cancellation conservative as well. If the exact target
            # is closing, the hold should not fire.
            hp = self._hold_payload
            if hp:
                _action, fw_ref, dialog_ref, button_ref, _button_type = hp
                if obj is fw_ref() or obj is dialog_ref() or obj is button_ref():
                    self._stop_hold_timer()
                    self._trace_left("Pending hold cancelled: target %s" % event_name)
        except Exception as exc:
            self._trace_left("Pending cancel check skipped: %s" % exc)

    def _on_dialog_show(self, dialog):
        did = self._dialog_id(dialog)
        if did in self._handled_dialogs:
            return
        self._handled_dialogs.add(did)
        self.debug_counts["dialogs"] += 1
        self.last_dialog = dialog.windowTitle() or dialog.__class__.__name__
        QtCore.QTimer.singleShot(0, lambda d=dialog: self._safe_enhance_dialog(d))

    def _safe_enhance_dialog(self, dialog):
        try:
            self._enhance_dialog(dialog)
        except Exception as exc:
            self.last_result = "Skipped dialog autofill after error: %s" % exc

    def _enhance_dialog(self, dialog):
        if dialog is None or not isinstance(dialog, QtWidgets.QDialog):
            return
        if not self.settings.type_enabled(TYPE_SAVE_EXPORT):
            return
        if not is_save_export_dialog(dialog):
            return
        for fw in dialog.findChildren(QgsFileWidget):
            allowed, button_type = target_allowed(self.settings, fw, dialog)
            if not allowed or button_type != TYPE_SAVE_EXPORT:
                self.debug_counts["skipped"] += 1
                continue
            self.last_widget = fw.objectName() or fw.__class__.__name__
            if autofill_allowed(self.settings, button_type):
                self._autofill_widget(fw, dialog, button_type)

    def _valid_button_target(self, button):
        fw = self.qgsfilewidget_of(button)
        if fw is not None:
            dialog = button.window()
            if not isinstance(dialog, QtWidgets.QDialog):
                return None, None, None
            allowed, button_type = target_allowed(self.settings, fw, dialog)
            if not allowed:
                return None, None, None
            self.last_dialog = dialog.windowTitle() or dialog.__class__.__name__
            self.last_widget = fw.objectName() or fw.__class__.__name__
            return fw, dialog, button_type
        return self._legacy_button_target(button)

    def _action_for(self, button_type, mouse_action):
        return self.settings.cached_mouse_action(button_type, mouse_action)

    def _action_needs_path_target(self, action):
        return action in (
            ACTION_AUTOFILL,
            ACTION_CLEAR_THEN_AUTOFILL,
            ACTION_LAST_USED,
            ACTION_PROJECT_HOME,
            ACTION_CLEAR_PATH,
            ACTION_COPY_PATH,
            ACTION_OPEN_FOLDER,
        )

    def _action_is_plugin_controlled(self, action):
        """Return True when an action needs FGQEP01 to handle the event.

        ACTION_NATIVE and ACTION_DO_NOTHING should stay as fast pass-through
        cases. This helper is used to avoid running Custom/Advanced detection on
        ordinary left clicks when that button type has no relevant action.
        """
        return action not in (ACTION_NATIVE, ACTION_DO_NOTHING)

    def _legacy_mouse_event_needs_detection(self, event):
        """Cheap pre-gate for Custom/Advanced button detection.

        UI131 enables support for ordinary third-party plugin buttons. Without
        this gate, every QPushButton/QToolButton press in every dialog can run
        dialog/title/button allowlist checks and possibly target-field search.
        Only run those checks when the current mouse event could actually fire
        a configured Custom/Advanced action.
        """
        if not self._legacy_enabled():
            return False
        try:
            etype = event.type()
            button = event.button() if hasattr(event, "button") else None
        except Exception:
            return False

        if etype == QtCore.QEvent.ContextMenu:
            return self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_RIGHT_CLICK))

        if etype == QtCore.QEvent.MouseButtonPress:
            if button == Qt.LeftButton:
                return (
                    self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_LEFT_DOUBLE))
                    or self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_LEFT_HOLD))
                )
            if button == Qt.RightButton:
                return self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_RIGHT_CLICK))
            if button == Qt.MiddleButton:
                return self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_MIDDLE_CLICK))
            return False

        if etype == QtCore.QEvent.MouseButtonDblClick:
            if button == Qt.LeftButton:
                # Shift + left double-click is a diagnostic action, but
                # still only applies after a button is accepted. Keep detection
                # enabled for Shift double-click on Custom/Advanced buttons.
                try:
                    mods = event.modifiers() if hasattr(event, "modifiers") else QtWidgets.QApplication.keyboardModifiers()
                except Exception:
                    mods = Qt.NoModifier
                return bool(mods & Qt.ShiftModifier) or self._action_is_plugin_controlled(self._action_for(TYPE_LEGACY, MOUSE_LEFT_DOUBLE))
            # Right double-click is intentionally ignored; middle double-click is
            # reserved for the inspector and is handled before button detection.
            return False

        # Release handling only matters after a left stream was already
        # controlled by a previous accepted press. Do not start Custom/Advanced
        # candidate detection from a plain release.
        if etype == QtCore.QEvent.MouseButtonRelease:
            return bool(self._left_stream_controlled or self._ignore_next_left_release)

        return False

    def _has_path_target(self, fw):
        if hasattr(fw, "hasTarget"):
            try:
                return bool(fw.hasTarget())
            except Exception:
                return False
        return fw is not None

    def _on_context_menu(self, button, event):
        if self.qgsfilewidget_of(button) is None and not self._legacy_mouse_event_needs_detection(event):
            return False
        fw, dialog, button_type = self._valid_button_target(button)
        if fw is None:
            return False
        action = self._action_for(button_type, MOUSE_RIGHT_CLICK)
        if action == ACTION_NATIVE:
            return False
        return self._perform_action(action, fw, dialog, button, button_type)

    def _trace_left(self, message):
        """Keep a small in-memory trace of left-button dispatcher decisions."""
        try:
            self.left_trace.append(str(message))
            self.left_trace = self.left_trace[-TRACE_LIMIT:]
            self.last_result = str(message)
        except Exception:
            pass

    def _event_type_name(self, event_type):
        names = {
            QtCore.QEvent.MouseButtonPress: "MouseButtonPress",
            QtCore.QEvent.MouseButtonRelease: "MouseButtonRelease",
            QtCore.QEvent.MouseButtonDblClick: "MouseButtonDblClick",
            QtCore.QEvent.ContextMenu: "ContextMenu",
            QtCore.QEvent.Show: "Show",
            QtCore.QEvent.Hide: "Hide",
            QtCore.QEvent.Close: "Close",
            QtCore.QEvent.DeferredDelete: "DeferredDelete",
        }
        return names.get(event_type, str(int(event_type)))


    def _trace_non_button_mouse_event(self, obj, event):
        if not self.mouse_trace_enabled:
            return
        etype = event.type()
        if etype not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.ContextMenu):
            return
        try:
            dialog = obj.window() if hasattr(obj, "window") else None
            if not isinstance(dialog, QtWidgets.QDialog):
                return
            # Only add this noisy diagnostic when custom/advanced debugging is in
            # play. Normal QgsFileWidget tracing stays button-only.
            if not (self._legacy_enabled() or self._legacy_debug_bypass()):
                return
            name = obj.objectName() if hasattr(obj, "objectName") else ""
            text = ""
            if hasattr(obj, "text"):
                try:
                    text = obj.text()
                except Exception:
                    text = ""
            self._trace_left('mouse trace non-button: %s | widget=%s objectName=%s text="%s" | dialog=%s' % (
                self._event_type_name(etype), obj.__class__.__name__, name or "", text or "", dialog.windowTitle() or dialog.__class__.__name__))
        except Exception as exc:
            self._trace_left("mouse trace non-button failed: %s" % exc)

    def scan_active_dialog_widgets(self):
        """Debug helper: list buttons and path-like widgets in the active dialog.

        Used for custom/advanced third-party plugin support. This is only called
        from the Debug / About tab, never from the event-filter hot path.
        """
        try:
            app = QtWidgets.QApplication.instance()
            dialog = None
            if app is not None:
                w = app.activeWindow()
                if isinstance(w, QtWidgets.QDialog):
                    dialog = w
                elif w is not None and hasattr(w, "window") and isinstance(w.window(), QtWidgets.QDialog):
                    dialog = w.window()
            if dialog is None:
                # Fall back to the first visible QDialog that is not our own
                # settings dialog. This helps when QGIS focus is odd.
                for w in QtWidgets.QApplication.topLevelWidgets():
                    if isinstance(w, QtWidgets.QDialog) and w.isVisible():
                        title = w.windowTitle() or w.__class__.__name__
                        if "Browse Enhancer" not in title:
                            dialog = w
                            break
            if dialog is None:
                self._trace_left("scan active dialog: no active visible QDialog found")
                return "No active visible QDialog found."

            lines = []
            title = dialog.windowTitle() or dialog.__class__.__name__
            lines.append('Dialog: %s | class=%s | objectName=%s' % (title, dialog.__class__.__name__, dialog.objectName() or ""))
            lines.append("Buttons:")
            buttons = dialog.findChildren(QtWidgets.QAbstractButton)
            if not buttons:
                lines.append("  (none)")
            for b in buttons:
                try:
                    lines.append('  %s | objectName=%s | text="%s" | enabled=%s | visible=%s' % (
                        b.__class__.__name__, b.objectName() or "", b.text() or "", b.isEnabled(), b.isVisible()))
                except Exception as exc:
                    lines.append('  <button read error: %s>' % exc)
            lines.append("Path/text widgets:")
            widgets = []
            for cls in (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit, QtWidgets.QListWidget):
                try:
                    widgets.extend(dialog.findChildren(cls))
                except Exception:
                    pass
            if not widgets:
                lines.append("  (none)")
            for w in widgets:
                try:
                    val = ""
                    if hasattr(w, "text"):
                        val = w.text()
                    elif hasattr(w, "toPlainText"):
                        val = w.toPlainText()
                    elif isinstance(w, QtWidgets.QListWidget):
                        val = "%d item(s)" % w.count()
                    if len(val) > 120:
                        val = val[:117] + "..."
                    lines.append('  %s | objectName=%s | value="%s" | enabled=%s | visible=%s' % (
                        w.__class__.__name__, w.objectName() or "", val or "", w.isEnabled(), w.isVisible()))
                except Exception as exc:
                    lines.append('  <widget read error: %s>' % exc)
            result = "\n".join(lines)
            self._trace_left("scan active dialog completed: %s" % title)
            return result
        except Exception as exc:
            msg = "scan active dialog failed: %s" % exc
            self._trace_left(msg)
            return msg

    def _trace_mouse_event(self, button, event):
        """Diagnostic-only trace for real QToolButton mouse events.

        This is intentionally controlled by a Debug / About button so normal
        runtime paths stay quiet. It records what QGIS is actually sending to
        FGQEP01 and whether the button resolves to a QgsFileWidget target.
        """
        if not self.mouse_trace_enabled:
            return
        etype = event.type()
        if etype not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.ContextMenu):
            return
        try:
            fw = self.qgsfilewidget_of(button)
            dialog = button.window()
            allowed = False
            button_type = "-"
            if fw is not None and isinstance(dialog, QtWidgets.QDialog):
                try:
                    allowed, button_type = target_allowed(self.settings, fw, dialog)
                except Exception:
                    allowed, button_type = False, "target-error"
            elif isinstance(dialog, QtWidgets.QDialog):
                try:
                    legacy_fw, _legacy_dialog, legacy_type = self._legacy_button_target(button)
                    if legacy_fw is not None:
                        fw = legacy_fw
                        allowed, button_type = True, legacy_type
                except Exception:
                    allowed, button_type = False, "legacy-target-error"
            btn_name = button.objectName() or button.__class__.__name__
            fw_name = "None" if fw is None else (fw.objectName() or fw.__class__.__name__)
            dlg_name = "None" if not isinstance(dialog, QtWidgets.QDialog) else (dialog.windowTitle() or dialog.__class__.__name__)
            extra = ""
            if hasattr(event, "button"):
                try:
                    extra = " button=%s" % int(event.button())
                except Exception:
                    extra = ""
            self._trace_left("mouse trace: %s%s | btn=%s | fw=%s | dialog=%s | allowed=%s | type=%s" % (self._event_type_name(etype), extra, btn_name, fw_name, dlg_name, allowed, button_type))
        except Exception as exc:
            self._trace_left("mouse trace failed: %s" % exc)

    def set_mouse_trace_enabled(self, enabled):
        self.mouse_trace_enabled = bool(enabled)
        self._trace_left("Mouse event trace %s" % ("started" if enabled else "stopped"))

    def _on_mouse_press(self, button, event):
        is_qgs_button = self.qgsfilewidget_of(button) is not None
        if not is_qgs_button and not self._legacy_mouse_event_needs_detection(event):
            return False
        fw, dialog, button_type = self._valid_button_target(button)
        if fw is None:
            return False

        if event.button() == Qt.LeftButton:
            # v0.6.4: if a left double-click or left hold action is configured,
            # FGQEP01 owns the left stream and delays native browse until a
            # single-click is confirmed. If neither is configured, native QGIS
            # receives the click immediately.
            self._hold_fired = False
            self._ignore_next_left_release = False
            self._stop_left_click_timer()

            double_action = self._action_for(button_type, MOUSE_LEFT_DOUBLE)
            hold_action = self._action_for(button_type, MOUSE_LEFT_HOLD)
            plugin_double = double_action not in (ACTION_DO_NOTHING, ACTION_NATIVE)
            plugin_hold = hold_action not in (ACTION_DO_NOTHING, ACTION_NATIVE)
            try:
                modifiers = event.modifiers() if hasattr(event, "modifiers") else QtWidgets.QApplication.keyboardModifiers()
            except Exception:
                modifiers = Qt.NoModifier
            shift_diagnostic_double = bool(modifiers & Qt.ShiftModifier)

            if not plugin_double and not plugin_hold and not shift_diagnostic_double:
                self._left_stream_controlled = False
                self._trace_left("Left press passed to native QGIS: no double/hold action")
                return False

            self._left_stream_controlled = True
            self._last_left_payload = (fw, dialog, button, button_type)
            if shift_diagnostic_double and not plugin_double and not plugin_hold:
                self._trace_left("Left press intercepted for Shift + left double-click diagnostic action")
            else:
                self._trace_left("Left press intercepted: single=native double=%s hold=%s shift_diagnostic=%s" % (double_action, hold_action, shift_diagnostic_double))
            if plugin_hold:
                self._start_hold_timer(hold_action, fw, dialog, button, button_type)
            return True

        if event.button() == Qt.RightButton:
            action = self._action_for(button_type, MOUSE_RIGHT_CLICK)
            if action in (ACTION_NATIVE, ACTION_DO_NOTHING):
                return action == ACTION_DO_NOTHING
            return self._perform_action(action, fw, dialog, button, button_type)

        if event.button() == Qt.MiddleButton:
            action = self._action_for(button_type, MOUSE_MIDDLE_CLICK)
            if action == ACTION_NATIVE:
                return False
            return self._perform_action(action, fw, dialog, button, button_type)

        return False

    def _on_mouse_release(self, button, event):
        if event.button() != Qt.LeftButton:
            return False

        if self._ignore_next_left_release:
            # Suppress only the release belonging to the same button that
            # produced the hold/double-click. This avoids swallowing unrelated
            # QGIS or plugin mouse releases.
            suppress_btn = self._suppress_left_release_button
            if suppress_btn is None or suppress_btn is button:
                self._ignore_next_left_release = False
                self._suppress_left_release_button = None
                self._stop_hold_timer()
                self._left_stream_controlled = False
                self._trace_left("Left release suppressed after double-click/hold")
                return True

        if self._left_stream_controlled:
            # We intercepted the press because double-click and/or hold is
            # configured. If hold did not fire, treat this as a pending native
            # single-click and trigger native browse after the double-click
            # window has passed.
            self._stop_hold_timer()
            if self._hold_fired:
                self._hold_fired = False
                self._left_stream_controlled = False
                self._stop_left_click_timer()
                self._trace_left("Left release after hold")
                return True
            self._trace_left("Left release: delayed native single-click waiting for double-click window")
            self._start_left_click_timer(ACTION_NATIVE, *self._last_left_payload)
            return True

        # No configured left double/hold action: native QGIS receives release.
        self._stop_hold_timer()
        self._hold_fired = False
        self._trace_left("Left release passed to native QGIS")
        return False

    def _on_mouse_double_click(self, button, event):
        is_qgs_button = self.qgsfilewidget_of(button) is not None
        if not is_qgs_button and not self._legacy_mouse_event_needs_detection(event):
            return False
        fw, dialog, button_type = self._valid_button_target(button)
        if fw is None:
            return False

        if event.button() == Qt.LeftButton:
            self._stop_hold_timer()
            self._stop_left_click_timer(reason="double-click")
            # Always suppress the release that follows a left double-click on
            # the same detected QgsFileWidget button. Otherwise that final
            # release starts a new delayed single-click/native browse action.
            self._ignore_next_left_release = True
            self._suppress_left_release_button = button
            self._left_stream_controlled = False
            modifiers = event.modifiers() if hasattr(event, "modifiers") else QtWidgets.QApplication.keyboardModifiers()
            if modifiers & Qt.ShiftModifier:
                self._trace_left("Shift + left double-click: opening plugin folder")
                return self._open_plugin_folder()

            action = self._action_for(button_type, MOUSE_LEFT_DOUBLE)
            if action in (ACTION_DO_NOTHING, ACTION_NATIVE):
                self._trace_left("Left double-click: no plugin action configured; next release suppressed")
                return True
            self._trace_left("Left double-click: running action %s" % action)
            return self._perform_action(action, fw, dialog, button, button_type)

        # v0.6.0: right double-click is dropped/ignored.
        if event.button() == Qt.RightButton:
            self._trace_left("Right double-click ignored")
            return False

        return False

    def _open_plugin_folder(self):
        try:
            folder = os.path.dirname(os.path.abspath(__file__))
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            self.last_result = "Opened plugin folder: " + folder
            self._trace_left(self.last_result)
            return True
        except Exception as exc:
            self._trace_left("Open plugin folder failed: %s" % exc)
            return True

    def _perform_left_single_action(self, action, fw, dialog, button, button_type):
        if action == ACTION_NATIVE:
            return self._trigger_native_browse(fw, button)
        return self._perform_action(action, fw, dialog, button, button_type)

    def _trigger_native_browse(self, fw, button):
        """Trigger the native QgsFileWidget browse behaviour after delayed click.

        Real QGIS browse buttons cannot be handled by pass-through when hold or
        double-click is also configured. This method first tries QgsFileWidget
        browse-like slots if exported, then falls back to clicking the actual
        QToolButton on the next event-loop turn.
        """
        try:
            self._trace_left("Native browse requested")
            if fw is not None:
                for name in ("openFileDialog", "openFileDialog_", "showFileDialog"):
                    method = getattr(fw, name, None)
                    if callable(method):
                        self._trace_left("Native browse method: QgsFileWidget.%s" % name)
                        method()
                        return True

            if button is None or (hasattr(button, "isVisible") and not button.isVisible()):
                self._trace_left("Native browse skipped: button not visible")
                return True

            def do_click(btn=button):
                try:
                    self._replaying_native_click = True
                    self._trace_left("Native browse method: QToolButton.click queued")
                    btn.click()
                except Exception as exc:
                    self._trace_left("Native browse queued click failed: %s" % exc)
                finally:
                    self._replaying_native_click = False

            QtCore.QTimer.singleShot(0, do_click)
            return True
        except Exception as exc:
            self._replaying_native_click = False
            self._trace_left("Native browse trigger failed: %s" % exc)
            return True

    def _weak(self, obj):
        try:
            return weakref.ref(obj)
        except Exception:
            return lambda: obj


    def _single_click_delay_ms(self):
        try:
            return int(QtWidgets.QApplication.doubleClickInterval()) + DOUBLE_CLICK_EXTRA_MS
        except Exception:
            return 430

    def _hold_delay_ms(self):
        try:
            delay = int(self.settings.cached_value("holdDelayMs", DEFAULT_HOLD_DELAY_MS))
        except Exception:
            delay = DEFAULT_HOLD_DELAY_MS
        return max(MIN_HOLD_DELAY_MS, min(MAX_HOLD_DELAY_MS, delay))

    def _start_left_click_timer(self, action, fw, dialog, button, button_type):
        """Start the delayed single-click action.

        v0.6.4 keeps strong references to the real QgsFileWidget, dialog and
        button until the timer fires. Weak references were too easy to lose in
        QGIS/Qt wrapper lifecycles, which made native single-click browse
        intermittent while hold/double-click worked.
        """
        if self._left_click_timer is not None or self._left_click_payload is not None:
            self._trace_left("Pending single-click replaced before firing")
        self._stop_left_click_timer(log_cancel=False)
        self._left_click_timer = QtCore.QTimer(self)
        self._left_click_timer.setSingleShot(True)
        self._left_click_payload = (action, fw, dialog, button, button_type)
        self._left_click_timer.timeout.connect(self._fire_left_click)
        interval = self._single_click_delay_ms()
        self._trace_left("Left single-click timer started: %d ms" % interval)
        self._left_click_timer.start(interval)

    def _stop_left_click_timer(self, log_cancel=True, reason="unspecified"):
        had_timer = self._left_click_timer is not None or self._left_click_payload is not None
        if self._left_click_timer is not None:
            try:
                self._left_click_timer.stop()
                self._left_click_timer.deleteLater()
            except Exception:
                pass
        self._left_click_timer = None
        self._left_click_payload = None
        if log_cancel and had_timer:
            self._trace_left("Pending single-click cancelled: %s" % reason)

    def _fire_left_click(self):
        payload = self._left_click_payload
        timer = self._left_click_timer
        self._left_click_timer = None
        self._left_click_payload = None
        if timer is not None:
            try:
                timer.deleteLater()
            except Exception:
                pass
        if not payload:
            self._trace_left("Left single-click timer fired with no payload")
            return
        action, fw, dialog, button, button_type = payload
        try:
            self._left_stream_controlled = False
            if fw is None or dialog is None or button is None:
                self._trace_left("Left single-click skipped: missing target")
                return
            if hasattr(button, "isVisible") and not button.isVisible():
                self._trace_left("Left single-click target button not visible; trying native browse anyway")
            if hasattr(dialog, "isVisible") and not dialog.isVisible():
                self._trace_left("Left single-click dialog not visible; trying native browse anyway")
            self._trace_left("Left single-click timer fired: %s" % action)
            self._perform_left_single_action(action, fw, dialog, button, button_type)
        except Exception as exc:
            self._left_stream_controlled = False
            self._trace_left("Skipped delayed left-click after error: %s" % exc)

    def _start_hold_timer(self, action, fw, dialog, button, button_type):
        self._stop_hold_timer()
        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_payload = (action, self._weak(fw), self._weak(dialog), self._weak(button), button_type)
        self._hold_timer.timeout.connect(self._fire_hold)
        delay = self._hold_delay_ms()
        self._trace_left("Left hold timer started: %d ms" % delay)
        self._hold_timer.start(delay)

    def _stop_hold_timer(self):
        if self._hold_timer is not None:
            try:
                self._hold_timer.stop()
                self._hold_timer.deleteLater()
            except Exception:
                pass
        self._hold_timer = None
        self._hold_payload = None

    def _fire_hold(self):
        payload = self._hold_payload
        self._hold_timer = None
        self._hold_payload = None
        if not payload:
            return
        action, fw_ref, dialog_ref, button_ref, button_type = payload
        try:
            fw = fw_ref(); dialog = dialog_ref(); button = button_ref()
            if fw is None or dialog is None or button is None:
                return
            if hasattr(button, "isVisible") and not button.isVisible():
                return
            if hasattr(dialog, "isVisible") and not dialog.isVisible():
                return
            self._hold_fired = True
            self._ignore_next_left_release = True
            self._suppress_left_release_button = button
            self._left_stream_controlled = False
            self._stop_left_click_timer(reason="hold fired")
            self._trace_left("Left hold fired: %s" % action)
            self._perform_action(action, fw, dialog, button, button_type)
        except Exception as exc:
            self._trace_left("Skipped hold action after error: %s" % exc)

    def _perform_action(self, action, fw, dialog, anchor, button_type):
        self.debug_counts["actions"] += 1
        if self._action_needs_path_target(action) and not self._has_path_target(fw):
            self.last_result = "Skipped action: no target path box for %s" % action
            self._trace_left(self.last_result)
            return True
        if action == ACTION_DO_NOTHING:
            self.last_result = "Mouse action: do nothing"
            return True
        if action == ACTION_SHOW_MENU:
            self._show_preset_menu(anchor, fw, button_type)
            return True
        if action == ACTION_AUTOFILL:
            self._autofill_widget(fw, dialog, button_type, clear_first=False)
            return True
        if action == ACTION_CLEAR_THEN_AUTOFILL:
            self._trace_left("Clear then autofill requested")
            self._autofill_widget(fw, dialog, button_type, clear_first=True)
            return True
        if action == ACTION_LAST_USED:
            path = self.resolver.last_used_dir()
            if path:
                self.resolver.set_widget_path(fw, path, button_type)
                self.last_result = "Set path to last used folder: " + path
            else:
                self.last_result = "No last used folder available"
            return True
        if action == ACTION_PROJECT_HOME:
            path = project_home()
            if path:
                self.resolver.set_widget_path(fw, path, button_type)
                self.last_result = "Set path to project home: " + path
            else:
                self.last_result = "No project home folder available"
            return True
        if action == ACTION_CLEAR_PATH:
            self.resolver.set_widget_path(fw, "", button_type)
            self.last_result = "Cleared path"
            return True
        if action == ACTION_COPY_PATH:
            try:
                path = str(fw.filePath() or "")
                QtWidgets.QApplication.clipboard().setText(path)
                self.last_result = "Copied current path"
            except Exception as exc:
                self.last_result = "Copy path failed: %s" % exc
            return True
        if action == ACTION_OPEN_FOLDER:
            self._open_current_folder(fw)
            return True
        if action == ACTION_NATIVE:
            return False
        self.last_result = "Unknown mouse action: " + str(action)
        return False

    def _autofill_widget(self, fw, dialog, button_type, clear_first=False):
        try:
            current = str(fw.filePath() or "").strip()
        except Exception:
            current = ""
        if current and not clear_first:
            self.last_result = "Skipped autofill: path already has text"
            self._trace_left(self.last_result)
            return False
        if current and clear_first:
            try:
                fw.setFilePath("")
                self._trace_left("Clear then autofill: existing path cleared")
            except Exception as exc:
                self.last_result = "Clear before autofill failed: %s" % exc
                self._trace_left(self.last_result)
                return False
        path = self.resolver.build_autofill_path(fw, dialog, button_type)
        if not path:
            self.last_result = "Skipped autofill: no path could be built"
            self._trace_left(self.last_result)
            return False
        ok = self.resolver.set_widget_path(fw, path, button_type)
        if ok:
            self.debug_counts["autofill"] += 1
            self.last_result = ("Clear then autofilled: " if clear_first else "Autofilled: ") + path
            self._trace_left(self.last_result)
        else:
            self.last_result = "Autofill failed"
            self._trace_left(self.last_result)
        return ok

    def _open_current_folder(self, fw):
        try:
            path = str(fw.filePath() or "")
        except Exception:
            path = ""
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            self.last_result = "Opened current folder: " + folder
        else:
            self.last_result = "Current folder does not exist"

    def _menu_set_path(self, fw, path, button_type):
        if path and self.settings.cached_bool("preset_menu/create_missing_on_select", True):
            try:
                target_dir = path if os.path.splitext(path)[1] == "" else os.path.dirname(path)
                if target_dir and not os.path.isdir(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
            except Exception:
                pass
        ok = self.resolver.set_widget_path(fw, path, button_type)
        if ok and self.settings.cached_bool("preset_menu/remember_selected_as_last_used", True):
            self.resolver.set_last_used_from_path(path)
        return ok

    def _add_menu_path(self, menu, label, path, fw, button_type, unresolved_mode, reason=""):
        if path:
            menu.addAction(label + ": " + path, lambda p=path: self._menu_set_path(fw, p, button_type))
            return True
        if unresolved_mode == "disable":
            suffix = "unavailable" if not reason else "unavailable - " + str(reason)
            action = menu.addAction(label + ": " + suffix)
            action.setEnabled(False)
            try:
                action.setToolTip(str(reason or "Unavailable"))
            except Exception:
                pass
            return True
        return False

    def _show_preset_menu(self, anchor, fw, button_type):
        menu = QtWidgets.QMenu(anchor)
        self._active_menu = menu
        menu.aboutToHide.connect(lambda: setattr(self, "_active_menu", None))
        unresolved_mode = str(self.settings.cached_value("preset_menu/unresolvedMode", "hide") or "hide")
        order_text = str(self.settings.cached_value("preset_menu/order", "last_used,current_file_folder,project_home,qgz_folder,preset_folders") or "")
        order = [x.strip() for x in order_text.split(",") if x.strip()]
        all_keys = ["last_used", "current_file_folder", "project_home", "qgz_folder", "preset_folders", "desktop", "documents", "downloads"]
        for key in all_keys:
            if key not in order:
                order.append(key)
        added_any = False
        dialog = getattr(fw, "window", lambda: None)()
        for key in order:
            if key == "last_used":
                if self.settings.cached_bool("preset_menu/show_last_used", True):
                    added_any = self._add_menu_path(menu, "Last used folder", self.resolver.last_used_dir(), fw, button_type, unresolved_mode) or added_any
            elif key == "current_file_folder":
                if self.settings.cached_bool("preset_menu/show_current_file_folder", True):
                    added_any = self._add_menu_path(menu, "Current file folder", self.resolver.current_file_folder(dialog), fw, button_type, unresolved_mode) or added_any
            elif key == "project_home":
                if self.settings.cached_bool("preset_menu/show_project_home", True):
                    added_any = self._add_menu_path(menu, "Project home", project_home(), fw, button_type, unresolved_mode) or added_any
            elif key == "qgz_folder":
                if self.settings.cached_bool("preset_menu/show_qgz_folder", True):
                    added_any = self._add_menu_path(menu, "QGZ folder", qgz_folder(), fw, button_type, unresolved_mode) or added_any
            elif key == "preset_folders":
                if self.settings.cached_bool("preset_menu/show_preset_folders", True):
                    if added_any and menu.actions() and not menu.actions()[-1].isSeparator():
                        menu.addSeparator()
                    preset_count = 0
                    for item in self.resolver.presets_resolved_detailed(dialog):
                        name = item.get("name", "Preset")
                        path = item.get("path", "")
                        if item.get("ok") and path:
                            menu.addAction(name + ": " + path, lambda p=path: self._menu_set_path(fw, p, button_type))
                            preset_count += 1
                        elif unresolved_mode == "disable":
                            reason = item.get("reason", "unavailable")
                            action = menu.addAction(name + ": unavailable - " + reason)
                            action.setEnabled(False)
                            try:
                                action.setToolTip(reason)
                            except Exception:
                                pass
                            preset_count += 1
                    added_any = added_any or preset_count > 0
                    if preset_count and menu.actions() and not menu.actions()[-1].isSeparator():
                        menu.addSeparator()
            elif key == "desktop":
                if self.settings.cached_bool("preset_menu/show_desktop", False):
                    added_any = self._add_menu_path(menu, "Desktop", desktop_folder(), fw, button_type, unresolved_mode) or added_any
            elif key == "documents":
                if self.settings.cached_bool("preset_menu/show_documents", False):
                    added_any = self._add_menu_path(menu, "Documents", documents_folder(), fw, button_type, unresolved_mode) or added_any
            elif key == "downloads":
                if self.settings.cached_bool("preset_menu/show_downloads", False):
                    added_any = self._add_menu_path(menu, "Downloads", downloads_folder(), fw, button_type, unresolved_mode) or added_any
        acts = menu.actions()
        if acts and acts[-1].isSeparator():
            menu.removeAction(acts[-1])
        if not menu.actions():
            action = menu.addAction("No folders available")
            action.setEnabled(False)
        self.debug_counts["menus"] += 1
        self.last_result = "Opened preset path menu"
        menu.popup(anchor.mapToGlobal(anchor.rect().bottomLeft()))
