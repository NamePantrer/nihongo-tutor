from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def writable_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _flavor_dir() -> str:
    from proba.flavor import data_dirname

    return data_dirname()


WEB_DIR = bundle_root() / "web"
DATA_DIR = writable_root() / _flavor_dir()
CAPTURE_DIR = DATA_DIR / "capture"
DB_PATH = DATA_DIR / "proba.db"
ASSETS_DIR = bundle_root() / "assets"


def refresh() -> None:
    global DATA_DIR, CAPTURE_DIR, DB_PATH
    DATA_DIR = writable_root() / _flavor_dir()
    CAPTURE_DIR = DATA_DIR / "capture"
    DB_PATH = DATA_DIR / "proba.db"


def set_db_path(path: Path) -> None:
    global DATA_DIR, CAPTURE_DIR, DB_PATH
    DB_PATH = Path(path)
    DATA_DIR = DB_PATH.parent
    CAPTURE_DIR = DATA_DIR / "capture"


def icon_ico() -> Path | None:
    candidate = ASSETS_DIR / "proba.ico"
    return candidate if candidate.is_file() else None


def icon_png() -> Path | None:
    for name in ("proba-book-icon.png", "proba.ico"):
        candidate = ASSETS_DIR / name
        if candidate.is_file():
            return candidate
    return None


def show_signal_path() -> Path:
    return DATA_DIR / "show.signal"
