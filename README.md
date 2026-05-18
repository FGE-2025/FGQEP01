# FGQEP01 Browse Enhancer v0.9.0

FGQEP01 Browse Enhancer enhances QGIS Save/Export browse workflows with extra mouse actions, folder presets, and path autofill.

It uses dialog-only and QgsFileWidget-focused detection while preserving native QGIS dialog behaviour. It also includes token expansion and a configurable startup delay before the event filter starts.

## Features

- Enhances QGIS Save/Export browse button workflows.
- Supports path-box workflow helpers for save-file, folder, and open-file contexts.
- Uses focused `QgsFileWidget` detection where possible.
- Keeps normal native QGIS browse behaviour available.
- Supports configurable mouse actions, including double-click and long-press behaviour.
- Provides folder presets and token expansion for reusable path locations.
- Supports path autofill helpers based on the selected/autofill content setting.
- Includes a configurable startup delay before the event filter starts. Default: `10000 ms`.
- Keeps the advanced mode area available for future custom widgets, diagnostics, and extended action mapping.

## Baseline architecture

- Dialog-first enhancement.
- Real `QgsFileWidget` detection where possible.
- No TOC processing.
- No broad heuristic scanning unless legacy/custom fallback is explicitly enabled.
- Direct `QgsFileWidget.setFilePath(...)` path binding where available.

## Settings tabs

1. General
2. Preset path menu
3. Save / Export buttons
4. Save-file path boxes
5. Folder path boxes
6. Open-file path boxes
7. Custom / Advanced Buttons
8. Preset folders
9. Debug / About

## Default preset folders

```text
Current file folder={current_file_folder}
Project home={project_home}
QGZ folder={qgz_folder}
```

## Icons

- `fgqep_brand_icon.png` is used for the QGIS Plugin Repository / Plugin Manager icon.
- `fgqep01_icon.png` is used for the plugin menu/tool action icon.
- `icon.png` is retained as a compatibility copy.

## Validation notes

Python syntax and AST parsing can be checked outside QGIS. Runtime testing should still be completed inside QGIS before public release.

## Disclaimer

This is a personal open-source project developed independently using public QGIS APIs and general programming methods.

This project is not affiliated with, endorsed by, or supported by any employer or client organisation.

No company confidential information, client data, project files, internal templates, or proprietary code are intentionally included.

Users are responsible for reviewing and testing the tool before use in any professional workflow.

## License

This project is released under the MIT License. See `LICENSE` for details.

FGQEP01 Browse Enhancer is part of FGQEP, a personal QGIS Enhancement Project — a collection of focused QGIS enhancement plugins designed to improve everyday GIS productivity, streamline repetitive workflows, and provide practical user-interface improvements for all QGIS users.
