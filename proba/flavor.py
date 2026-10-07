"""Tutor vs handbook. Not a kernel type.

Atlas is a second product: catalog + dictionary + 擬音 lookup + the same
level notebook (закрепление). It does not hide Zoom copy over the same
probe loop.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TUTOR = "tutor"
ATLAS = "atlas"

TUTOR_APP_NAME = "日本語学習アシスタント"
ATLAS_APP_NAME = "日本語便覧"
TUTOR_EXE_FILE = "Nihongo.exe"
ATLAS_EXE_FILE = "Benran.exe"
TUTOR_PORT = 8765
ATLAS_PORT = 8766

_FLAVOR: str | None = None
_ATLAS_STEMS = frozenset({"benran", "nihongobenran"})


def _stems() -> list[str]:
    out: list[str] = []
    if getattr(sys, "frozen", False):
        out.append(Path(sys.executable).stem.lower())
    if sys.argv:
        out.append(Path(sys.argv[0]).stem.lower())
    return out


def _from_argv(argv: list[str]) -> str | None:
    lowered = [a.lower() for a in argv]
    if "--atlas" in lowered or "-atlas" in lowered:
        return ATLAS
    if "--tutor" in lowered:
        return TUTOR
    return None


def _from_env() -> str | None:
    raw = (os.environ.get("PROBA_FLAVOR") or "").strip().lower()
    if raw in (ATLAS, "benran", "handbook", "reference"):
        return ATLAS
    if raw in (TUTOR, "assistant"):
        return TUTOR
    return None


def configure(argv: list[str] | None = None, flavor: str | None = None) -> str:
    global _FLAVOR
    if flavor in (TUTOR, ATLAS):
        _FLAVOR = flavor
        return _FLAVOR
    found = _from_argv(argv if argv is not None else sys.argv) or _from_env()
    if found:
        _FLAVOR = found
        return _FLAVOR
    if any(s in _ATLAS_STEMS for s in _stems()):
        _FLAVOR = ATLAS
        return _FLAVOR
    _FLAVOR = TUTOR
    return _FLAVOR


def current() -> str:
    if _FLAVOR is None:
        configure()
    return _FLAVOR or TUTOR


def is_atlas() -> bool:
    return current() == ATLAS


def app_name() -> str:
    return ATLAS_APP_NAME if is_atlas() else TUTOR_APP_NAME


def exe_file() -> str:
    return ATLAS_EXE_FILE if is_atlas() else TUTOR_EXE_FILE


def port() -> int:
    return ATLAS_PORT if is_atlas() else TUTOR_PORT


def origin() -> str:
    return f"http://127.0.0.1:{port()}"


def data_dirname() -> str:
    return "data-benran" if is_atlas() else "data"


def brand_sub() -> str:
    if is_atlas():
        return "справочник и тетрадь закрепления"
    return "после занятия — форма вслух"


def rails() -> list[dict]:
    if is_atlas():
        return [
            {"href": "/", "route": "/", "label": "Темы", "title": "N5–N1 и тетрадь закрепления"},
            {"href": "/giongo", "route": "/giongo", "label": "擬音", "title": "擬音語・擬態語"},
            {"href": "/dict", "route": "/dict", "label": "Словарь", "title": "поиск"},
        ]
    return [
        {"href": "/", "route": "/", "label": "Темы", "title": "N5–N1. Если есть форма — сначала она"},
        {"href": "/zoom", "route": "/zoom", "label": "Zoom", "title": "Звук 40+40+10"},
        {"href": "/settings", "route": "/settings", "label": "Настройки", "title": "Срез, текст, очередь"},
    ]


def chrome() -> dict:
    return {
        "flavor": current(),
        "atlas": is_atlas(),
        "app_name": app_name(),
        "brand_sub": brand_sub(),
        "rails": rails(),
    }
