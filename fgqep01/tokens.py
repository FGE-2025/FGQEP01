# -*- coding: utf-8 -*-
"""Token expansion helpers for preset paths."""

from __future__ import annotations

import getpass
import os
import re
import tempfile
from datetime import datetime

from qgis.core import QgsProject


def profile_name():
    try:
        from qgis.core import QgsApplication
        return QgsApplication.qgisSettingsDirPath().rstrip(os.sep).split(os.sep)[-1]
    except Exception:
        return "default"


def qgis_profile_name():
    return profile_name()


def qgz_folder():
    try:
        filename = QgsProject.instance().fileName()
        return os.path.normpath(os.path.dirname(filename)) if filename else ""
    except Exception:
        return ""


def project_file():
    try:
        filename = QgsProject.instance().fileName()
        return os.path.normpath(filename) if filename else ""
    except Exception:
        return ""


def project_file_name():
    filename = project_file()
    return os.path.basename(filename) if filename else ""


def project_file_base():
    name = project_file_name()
    return os.path.splitext(name)[0] if name else project_name()


def project_home():
    try:
        project = QgsProject.instance()
        home = project.homePath()
        if not home:
            home = qgz_folder()
        return os.path.normpath(home) if home else ""
    except Exception:
        return ""


def project_name():
    try:
        project = QgsProject.instance()
        filename = project.fileName()
        if filename:
            return os.path.splitext(os.path.basename(filename))[0]
        return project.title() or "project"
    except Exception:
        return "project"


def user_home():
    return os.path.expanduser("~")


def desktop_folder():
    return os.path.join(user_home(), "Desktop")


def documents_folder():
    return os.path.join(user_home(), "Documents")


def downloads_folder():
    return os.path.join(user_home(), "Downloads")


def fallback_current_file_folder():
    for path in (qgz_folder(), project_home()):
        if path:
            return path
    return user_home()


def expand_tokens_with_status(text, context=None):
    """Expand supported FGQEP01 path tokens and report missing values.

    Missing environment variables, QGIS project variables, or unavailable
    standard tokens are returned in the missing list rather than silently
    becoming empty strings. This lets the preset menu show unavailable items
    greyed out.
    """
    out = str(text or "")
    context = context or {}
    home = project_home()
    qgz = qgz_folder()
    current_file_folder = context.get("current_file_folder") or fallback_current_file_folder()
    replacements = {
        "{current_file_folder}": current_file_folder,
        "{project_home}": home,
        "{qgz_folder}": qgz,
        "{project_dirname}": os.path.basename((home or qgz).rstrip(os.sep)) if (home or qgz) else "",
        "{project_name}": project_name(),
        "{project_file}": project_file(),
        "{project_file_name}": project_file_name(),
        "{project_file_base}": project_file_base(),
        "{user}": getpass.getuser(),
        "{profile}": profile_name(),
        "{qgis_profile}": qgis_profile_name(),
        "{home}": user_home(),
        "{desktop}": desktop_folder(),
        "{documents}": documents_folder(),
        "{downloads}": downloads_folder(),
        "{temp}": tempfile.gettempdir(),
        # Friendly short tokens for users who prefer compact preset paths.
        "<home>": home,
        "<qgz>": qgz,
    }
    missing = []
    for token, value in replacements.items():
        if token in out:
            if value:
                out = out.replace(token, value)
            else:
                missing.append(token)
                out = out.replace(token, "")

    def repl_qgis_expr(match):
        name = match.group(1)
        value = ""
        try:
            from qgis.core import QgsExpressionContextUtils
            for scope in (
                QgsExpressionContextUtils.projectScope(QgsProject.instance()),
                QgsExpressionContextUtils.globalScope(),
            ):
                try:
                    if name in list(scope.variableNames()):
                        value = scope.variable(name)
                        break
                except Exception:
                    pass
        except Exception:
            value = ""
        if value in (None, ""):
            missing.append("{@%s}" % name)
            return ""
        return str(value)

    out = re.sub(r"\{\@([^}]+)\}", repl_qgis_expr, out)

    def repl_env(match):
        name = match.group(1)
        value = os.environ.get(name, "")
        if not value:
            missing.append("{env:%s}" % name)
        return value

    def repl_var(match):
        name = match.group(1)
        try:
            variables = QgsProject.instance().customVariables()
            value = variables.get(name, "")
        except Exception:
            value = ""
        if value in (None, ""):
            missing.append("{var:%s}" % name)
            return ""
        return str(value)

    def repl_date(match):
        fmt = match.group(1)
        fmt = fmt.replace("yyyy", "%Y").replace("yy", "%y")
        fmt = fmt.replace("MM", "%m").replace("dd", "%d")
        fmt = fmt.replace("HH", "%H").replace("mm", "%M").replace("ss", "%S")
        try:
            return datetime.now().strftime(fmt)
        except Exception:
            missing.append("{date:%s}" % match.group(1))
            return datetime.now().strftime("%Y%m%d")

    out = re.sub(r"\{env:([^}]+)\}", repl_env, out)
    out = re.sub(r"\{var:([^}]+)\}", repl_var, out)
    out = re.sub(r"\{date:([^}]+)\}", repl_date, out)
    return out, missing


def expand_tokens(text, context=None):
    """Expand supported FGQEP01 path tokens.

    Compatibility wrapper. New preset-menu code uses
    expand_tokens_with_status() so unresolved variables can be shown disabled.
    """
    return expand_tokens_with_status(text, context=context)[0]


TOKEN_HELPERS = [
    ("Common paths", [
        ("Current file folder", "{current_file_folder}"),
        ("Project home", "{project_home}"),
        ("QGZ folder", "{qgz_folder}"),
        ("Short token <home>", "<home>"),
        ("Short token <qgz>", "<qgz>"),
    ]),
    ("Project", [
        ("Project name", "{project_name}"),
        ("Project folder name", "{project_dirname}"),
        ("Project file", "{project_file}"),
        ("Project file name", "{project_file_name}"),
        ("Project file base", "{project_file_base}"),
    ]),
    ("System", [
        ("User name", "{user}"),
        ("User home", "{home}"),
        ("Desktop", "{desktop}"),
        ("Documents", "{documents}"),
        ("Downloads", "{downloads}"),
        ("Temp", "{temp}"),
    ]),
    ("QGIS", [
        ("QGIS profile", "{qgis_profile}"),
        ("Project code variable", "{var:project_code}"),
        ("Client code variable", "{var:client_code}"),
        ("Stage variable", "{var:stage}"),
    ]),
    ("Date/time", [
        ("Today yyyyMMdd", "{date:yyyyMMdd}"),
        ("Month yyyy-MM", "{date:yyyy-MM}"),
        ("Year yyyy", "{date:yyyy}"),
        ("Now yyyyMMdd_HHmmss", "{date:yyyyMMdd_HHmmss}"),
    ]),
    ("Relative path examples", [
        ("exports", "exports"),
        ("../exports", "../exports"),
        ("../../ClientExports", "../../ClientExports"),
        ("outputs/gpkg", "outputs/gpkg"),
        ("outputs/rasters", "outputs/rasters"),
        ("outputs/layouts", "outputs/layouts"),
        ("exports/date", "exports/{date:yyyyMMdd}"),
        ("project-code exports", "../{var:project_code}/exports"),
        ("normalised absolute", "C:/xyz/../abc"),
    ]),
]

# Grouped helper data for the Insert variable / path popup.
def qgis_expression_variable_items():
    """Return visible QGIS expression variables as helper rows.

    Rows are (label, token, value, description). This intentionally focuses on
    global and project scopes because they are stable and useful in preset paths.
    """
    rows = []
    try:
        from qgis.core import QgsExpressionContextUtils
        scopes = [
            ("Global", QgsExpressionContextUtils.globalScope()),
            ("Project", QgsExpressionContextUtils.projectScope(QgsProject.instance())),
        ]
        for scope_name, scope in scopes:
            try:
                names = list(scope.variableNames())
            except Exception:
                names = []
            for name in sorted(names):
                raw_name = str(name)
                clean_name = raw_name[1:] if raw_name.startswith("@") else raw_name
                try:
                    value = scope.variable(name)
                except Exception:
                    value = ""
                label = "@%s" % clean_name
                token = "{@%s}" % clean_name
                desc = "%s QGIS expression variable @%s." % (scope_name, clean_name)
                rows.append((label, token, str(value), desc))
    except Exception:
        pass
    if not rows:
        # Useful fallbacks when QGIS expression scopes are unavailable during tests.
        for name, value in [
            ("project_folder", qgz_folder()),
            ("project_path", project_file()),
            ("project_basename", project_file_base()),
            ("project_filename", project_file_name()),
            ("project_home", project_home()),
            ("user_account_name", getpass.getuser()),
            ("qgis_profile", qgis_profile_name()),
        ]:
            rows.append(("@" + name, "{@%s}" % name, str(value or ""), "QGIS expression variable @%s." % name))
    return rows


def qgis_project_variable_items():
    rows = []
    try:
        variables = QgsProject.instance().customVariables()
    except Exception:
        variables = {}
    for name in sorted(list(variables.keys())):
        value = variables.get(name, "")
        rows.append((str(name), "{var:%s}" % name, str(value), "QGIS project custom variable %s." % name))
    if not rows:
        for name in ("project_code", "client_code", "stage"):
            rows.append((name, "{var:%s}" % name, "", "Example QGIS project variable %s. Greyed/unavailable if missing." % name))
    return rows


def environment_variable_items():
    preferred = ["USERPROFILE", "USERNAME", "OneDrive", "TEMP", "TMP", "HOMEDRIVE", "HOMEPATH"]
    rows = []
    for name in preferred:
        value = os.environ.get(name, "")
        rows.append((name, "{env:%s}" % name, value, "System environment variable %s." % name))
    return rows


def helper_items_for_group(group_name):
    """Return grouped helper rows as (label, token, value, description)."""
    if group_name == "Common folders":
        return [
            ("QGZ project folder", "<qgz>", qgz_folder(), "Folder containing the current .qgz/.qgs project file."),
            ("Project home", "<home>", project_home(), "QGIS project home folder."),
            ("Current file folder", "{current_file_folder}", "runtime", "Runtime token. Resolved when used from a detected source/export context."),
            ("Home folder", "{home}", user_home(), "Current user's home folder."),
            ("Desktop", "{desktop}", desktop_folder(), "Current user's Desktop folder."),
            ("Documents", "{documents}", documents_folder(), "Current user's Documents folder."),
            ("Downloads", "{downloads}", downloads_folder(), "Current user's Downloads folder."),
            ("Temp folder", "{temp}", tempfile.gettempdir(), "System temporary folder."),
        ]
    if group_name == "QGIS expression variables":
        return qgis_expression_variable_items()
    if group_name == "QGIS project variables":
        return qgis_project_variable_items()
    if group_name == "System / environment variables":
        return environment_variable_items()
    if group_name == "Date / time":
        return [
            ("Today yyyyMMdd", "{date:yyyyMMdd}", datetime.now().strftime("%Y%m%d"), "Current date in yyyyMMdd format."),
            ("Month yyyy-MM", "{date:yyyy-MM}", datetime.now().strftime("%Y-%m"), "Current month in yyyy-MM format."),
            ("Year yyyy", "{date:yyyy}", datetime.now().strftime("%Y"), "Current year."),
            ("Date/time yyyyMMdd_HHmm", "{date:yyyyMMdd_HHmm}", datetime.now().strftime("%Y%m%d_%H%M"), "Current date and time."),
        ]
    if group_name == "Relative path examples":
        return [
            ("Exports folder", "exports", "QGZ folder/exports", "Folder named exports beside the current QGZ/QGS project file."),
            ("Parent exports folder", "../exports", "QGZ parent/exports", "Folder named exports one level above the QGZ/QGS project folder."),
            ("Client exports folder", "../../ClientExports", "two levels above QGZ/ClientExports", "ClientExports folder two levels above the QGZ/QGS project folder."),
            ("Output GeoPackage folder", "outputs/gpkg", "QGZ folder/outputs/gpkg", "GeoPackage output folder under outputs."),
            ("Output rasters folder", "outputs/rasters", "QGZ folder/outputs/rasters", "Raster output folder under outputs."),
            ("Output layouts folder", "outputs/layouts", "QGZ folder/outputs/layouts", "Layout output folder under outputs."),
            ("Daily exports folder", "exports/{date:yyyyMMdd}", "QGZ folder/exports/today", "Daily export folder using a date token."),
            ("Project-code exports folder", "../{var:project_code}/exports", "requires project_code", "Relative folder using a QGIS project variable."),
            ("Normalised absolute path example", "C:/xyz/../abc", "C:/abc", "Absolute path example showing normal ../ path cleanup."),
        ]
    return []


def helper_group_names():
    return [
        "Common folders",
        "QGIS expression variables",
        "QGIS project variables",
        "System / environment variables",
        "Date / time",
        "Relative path examples",
    ]
