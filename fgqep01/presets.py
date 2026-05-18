# -*- coding: utf-8 -*-
"""Preset parsing and path resolution."""

from __future__ import annotations

import os

from .tokens import expand_tokens, expand_tokens_with_status, project_home


def norm_path(path):
    return os.path.normpath(os.path.expanduser(str(path or "")))


def parse_presets(text):
    """Parse multiline name=path presets."""
    items = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, path = line.split("=", 1)
        else:
            name, path = line, line
        name = name.strip() or path.strip()
        path = path.strip()
        if path:
            items.append((name, path))
    return items


def _qgz_relative_base():
    """Base folder for plain relative preset paths.

    Plain relative presets such as ../exports are resolved from the folder
    containing the current QGZ/QGS project file. If the project is unsaved,
    they are unresolved so the menu can show them disabled.
    """
    try:
        from .tokens import qgz_folder
        return qgz_folder()
    except Exception:
        return ""


def is_absolute_path(path):
    text = str(path or "")
    if os.path.isabs(text):
        return True
    # Windows drive or UNC path, useful for validation in non-Windows test envs.
    if len(text) >= 3 and text[1] == ":" and text[2] in ("/", "\\"):
        return True
    if text.startswith("\\\\") or text.startswith("//"):
        return True
    return False


def resolve_preset_items(text, context=None):
    """Resolve preset lines with status.

    Returns dictionaries with:
      name, raw_path, path, ok, reason
    Invalid/unresolved entries are kept so the preset menu can show them
    disabled instead of hiding them.
    """
    out = []
    seen = set()
    for name, raw_path in parse_presets(text):
        try:
            path, missing = expand_tokens_with_status(raw_path, context=context)
        except Exception as exc:
            out.append({"name": name, "raw_path": raw_path, "path": "", "ok": False, "reason": "token expansion failed: %s" % exc})
            continue
        reason = ""
        ok = True
        if missing:
            ok = False
            reason = "missing " + ", ".join(missing)
        if ok and not is_absolute_path(path):
            base = _qgz_relative_base()
            if base:
                path = os.path.join(base, path)
            else:
                ok = False
                reason = "relative path needs a saved QGZ/QGS project file"
        if ok:
            path = norm_path(path)
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
        out.append({"name": name, "raw_path": raw_path, "path": path if ok else "", "ok": ok, "reason": reason})
    return out


def resolve_presets(text, context=None):
    """Resolve tokens, relative paths, and duplicate paths.

    Compatibility helper returning only successfully resolved presets as
    (name, path). Use resolve_preset_items() when disabled/unresolved menu
    items are needed.
    """
    return [(item["name"], item["path"]) for item in resolve_preset_items(text, context=context) if item.get("ok")]
