from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from proba import jlpt, paths

# Stroke outlines from KanjiVG (CC BY-SA 3.0, Ulrich Apel).

_JSON = Path(__file__).resolve().parent / "kanjivg_paths.json"
_PARTS = Path(__file__).resolve().parent / "kanjivg_parts.json"

CREDIT = {
    "source": "kanjivg",
    "license": "CC BY-SA 3.0",
    "attribution": "KanjiVG © Ulrich Apel — http://kanjivg.tagaini.net",
}


@lru_cache(maxsize=1)
def _all() -> dict[str, list[str]]:
    if not _JSON.is_file():
        bundled = paths.bundle_root() / "proba" / "kanjivg_paths.json"
        path = bundled if bundled.is_file() else _JSON
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(_JSON.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _parts_blob() -> dict:
    path = _PARTS
    if not path.is_file():
        bundled = paths.bundle_root() / "proba" / "kanjivg_parts.json"
        path = bundled if bundled.is_file() else _PARTS
        if not path.is_file():
            return {}
    return json.loads(path.read_text(encoding="utf-8"))


def paths_for(char: str) -> list[str]:
    ch = (char or "").strip()
    if len(ch) != 1:
        return []
    return list(_all().get(ch) or [])


def packed_radical(char: str) -> str:
    ch = (char or "").strip()
    blob = _parts_blob().get(ch) or {}
    return blob.get("radical") or ""


def parts_for(char: str) -> list[dict]:
    ch = (char or "").strip()
    if len(ch) != 1:
        return []
    paths = paths_for(ch)
    blob = _parts_blob().get(ch) or {}
    out = []
    for part in blob.get("parts") or []:
        ix = [i for i in part.get("i") or [] if isinstance(i, int) and 0 <= i < len(paths)]
        if not ix:
            continue
        out.append(
            {
                "element": part.get("e") or "",
                "original": part.get("o") or "",
                "radical": part.get("r") or "",
                "i": ix,
                "paths": [paths[i] for i in ix],
            }
        )
    return out


def chars_with_radical(radical: str, limit: int = 24) -> list[str]:
    want = (radical or "").strip()
    if not want:
        return []
    hits = []
    for ch, blob in _parts_blob().items():
        if blob.get("radical") == want or any(
            (p.get("e") == want or p.get("o") == want) for p in (blob.get("parts") or [])
        ):
            hits.append(ch)
        if len(hits) >= limit:
            break
    return hits


def paths_for_level(level: str | None) -> dict[str, list[str]]:
    lv = (level or "N5").upper()
    if lv not in jlpt.LEVELS:
        lv = "N5"
    bank = jlpt._kanji_bank().get(lv) or []
    blob = _all()
    out: dict[str, list[str]] = {}
    for item in bank:
        ch = item.get("c") or ""
        paths = blob.get(ch)
        if ch and paths:
            out[ch] = paths
    return out


def credit() -> dict:
    return dict(CREDIT)
