"""JMdict on-mim lookup. Not LEXICON, not catalog stations, not a probe."""

from __future__ import annotations

import json
from pathlib import Path

_PACKED_PATH = Path(__file__).with_name("giongo.json")

# Dakuten/handakuten fold into the gojūon column.
_FOLD = str.maketrans(
    "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゔぁぃぅぇぉゃゅょっゎ",
    "かきくけこさしすせそたちつてとはひふへほはひふへほうあいうえおやゆよつわ",
)

MORA_ROWS = (
    tuple("あいうえお"),
    tuple("かきくけこ"),
    tuple("さしすせそ"),
    tuple("たちつてと"),
    tuple("なにぬねの"),
    tuple("はひふへほ"),
    tuple("まみむめも"),
    tuple("や ゆ よ"),
    tuple("らりるれろ"),
    tuple("わをん"),
)

CREDIT = {
    "source": "jmdict",
    "kind": "on-mim",
}

# Contrastive pairs from the unofficial N4 station — lookup overlay, not claims.
_STATION_KEYS = (
    "わくわく",
    "どきどき",
    "いらいら",
    "がっかり",
    "ぺらぺら",
    "すらすら",
    "がやがや",
    "ぐずぐず",
    "さっさと",
    "ぴったり",
    "にこにこ",
    "にやにや",
    "ほかほか",
    "ひんやり",
    "がんがん",
    "ずきずき",
    "どんどん",
    "きらきら",
    "ぴかぴか",
    "べとべと",
    "さらさら",
)

_ROWS: list[tuple[str, str, str, int, int]] | None = None
_BY_KEY: dict[str, tuple[str, str, str, int, int]] | None = None
_BY_MORA: dict[str, list[tuple[str, str, str, int, int]]] | None = None


def _kata_to_hira(text: str) -> str:
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def mora_of(kana: str) -> str:
    raw = _kata_to_hira((kana or "").strip())
    if not raw:
        return ""
    ch = raw[0].translate(_FOLD)
    if ch == "ー" and len(raw) > 1:
        ch = raw[1].translate(_FOLD)
    return ch


def reset() -> None:
    global _ROWS, _BY_KEY, _BY_MORA
    _ROWS = None
    _BY_KEY = None
    _BY_MORA = None


def _ensure() -> None:
    global _ROWS, _BY_KEY, _BY_MORA
    if _ROWS is not None:
        return
    rows: list[tuple[str, str, str, int, int]] = []
    by_key: dict[str, tuple[str, str, str, int, int]] = {}
    by_mora: dict[str, list[tuple[str, str, str, int, int]]] = {}
    if _PACKED_PATH.is_file():
        blob = json.loads(_PACKED_PATH.read_text(encoding="utf-8"))
        for item in blob.get("words") or []:
            if not isinstance(item, list) or len(item) < 3:
                continue
            kana = str(item[0] or "").strip()
            key = str(item[1] or "").strip() or _kata_to_hira(kana)
            gloss = str(item[2] or "").strip()
            vs = int(item[3]) if len(item) > 3 else 0
            lang = int(item[4]) if len(item) > 4 else 0
            if not kana or not gloss:
                continue
            row = (kana, key, gloss, vs, lang)
            rows.append(row)
            by_key.setdefault(key, row)
            by_key.setdefault(kana, row)
            by_key.setdefault(_kata_to_hira(kana), row)
            bucket = mora_of(key or kana)
            if bucket:
                by_mora.setdefault(bucket, []).append(row)
    _ROWS = rows
    _BY_KEY = by_key
    _BY_MORA = by_mora


def count() -> int:
    _ensure()
    return len(_ROWS or [])


def index() -> dict:
    _ensure()
    counts = {k: len(v) for k, v in (_BY_MORA or {}).items()}
    rows = []
    for line in MORA_ROWS:
        cells = []
        for ch in line:
            if ch == " ":
                cells.append({"kana": "", "n": 0})
            else:
                cells.append({"kana": ch, "n": counts.get(ch, 0)})
        rows.append(cells)
    return {
        "count": count(),
        "rus": sum(1 for _k, _q, _g, _v, lang in (_ROWS or []) if lang == 0),
        "rows": rows,
    }


def _card(row: tuple[str, str, str, int, int]) -> dict:
    kana, key, gloss, vs, lang = row
    return {
        "kind": "mimetic",
        "head": kana,
        "kana": key or kana,
        "gloss_ru": gloss if lang == 0 else "",
        "gloss": gloss,
        "lang": "ru" if lang == 0 else "en",
        "vs": bool(vs),
        "mora": mora_of(key or kana),
        "paradigm": "giongo",
    }


def by_mora(mora: str) -> list[dict]:
    _ensure()
    ch = mora_of(mora) or (mora or "").strip()[:1]
    return [_card(r) for r in (_BY_MORA or {}).get(ch) or []]


def lookup(query: str) -> dict | None:
    raw = (query or "").strip()
    if not raw:
        return None
    _ensure()
    hit = (_BY_KEY or {}).get(raw) or (_BY_KEY or {}).get(_kata_to_hira(raw))
    if hit:
        return _card(hit)
    return None


def search(query: str, limit: int = 20) -> list[dict]:
    from proba.kana import romaji_to_hiragana

    raw = (query or "").strip()
    if not raw:
        return []
    _ensure()
    variants = {raw, raw.lower(), _kata_to_hira(raw)}
    hira = romaji_to_hiragana(raw, commit=True)
    if hira:
        variants.add(hira)
        variants.add(_kata_to_hira(hira))
    hits: list[dict] = []
    seen: set[str] = set()
    for row in _ROWS or []:
        kana, key, gloss, _vs, _lang = row
        if kana in seen or key in seen:
            continue
        blob = f"{kana}{key}{gloss}".lower()
        if any(v and (v in blob or v == kana or v == key or v in gloss.lower()) for v in variants):
            seen.add(kana)
            seen.add(key)
            hits.append(_card(row))
        if len(hits) >= limit:
            break
    return hits


def page(query: str) -> dict | None:
    card = lookup(query)
    if not card:
        return None
    neighbors = [c for c in by_mora(card["mora"]) if c["head"] != card["head"]][:12]
    return {
        **card,
        "forms": [],
        "kanji": [],
        "neighbors": neighbors,
    }


def station_overlay() -> dict:
    _ensure()
    samples = []
    seen: set[str] = set()
    for key in _STATION_KEYS:
        card = lookup(key)
        if not card or card["head"] in seen:
            continue
        seen.add(card["head"])
        samples.append(card)
        if len(samples) >= 8:
            break
    return {
        "count": count(),
        "samples": samples,
    }
