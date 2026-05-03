"""Application icon helpers."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

APP_ICON_RELATIVE_PATH = Path("assets/icons/measurer.ico")


def application_icon_path() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    candidates = []
    if bundle_root is not None:
        candidates.append(Path(bundle_root) / APP_ICON_RELATIVE_PATH)
    candidates.append(Path(__file__).resolve().parents[2] / APP_ICON_RELATIVE_PATH)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_application_icon() -> QIcon:
    icon_path = application_icon_path()
    if icon_path is None:
        return QIcon()
    return QIcon(str(icon_path))
