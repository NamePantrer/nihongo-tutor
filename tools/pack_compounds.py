"""Pack JP–RU compounds from JMdict (rus) for the unofficial N5–N1 bank.

Lookup only. Not LEXICON. Not Yarxi. Source: EDRDG JMdict via jmdict-simplified.
"""

from __future__ import annotations

import json
import re
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "proba" / "jlpt_kanji.json"
OUT = ROOT / "proba" / "compounds.json"
ZIP = ROOT / "assets" / "jmdict-rus.json.zip"
URL = (
    "https://github.com/scriptin/jmdict-simplified/releases/download/"
    "3.6.2%2B20260622163854/jmdict-rus-3.6.2+20260622163854.json.zip"
)

MAX_HEAD = 8
GLOSS_CAP = 400
GLOSS_SEP = " · "
GLOSS_MAX_PARTS = 6
_CYR = re.compile(r"[А-Яа-яЁё]")
_FRAME = re.compile(r"\{[^}]+\}")
_LEAD_COLON = re.compile(r"^[:：]\s*")
_NUM = re.compile(r"\s*\d+\)[:：]?\s*")
_TAG = re.compile(r"^\([^)]{1,24}\)$")


def _bank() -> set[str]:
    blob = json.loads(BANK.read_text(encoding="utf-8"))
    chars: set[str] = set()
    for items in blob.values():
        if not isinstance(items, list):
            continue
        for item in items:
            ch = (item.get("c") or "").strip()
            if len(ch) == 1:
                chars.add(ch)
    return chars


def _ensure_zip() -> Path:
    if ZIP.is_file() and ZIP.stat().st_size > 100_000:
        return ZIP
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    print("download", URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "Proba-pack/1"})
    with urllib.request.urlopen(req, timeout=180) as res, ZIP.open("wb") as f:
        while True:
            chunk = res.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return ZIP


def _cap(text: str) -> str:
    raw = (text or "").strip()
    if len(raw) <= GLOSS_CAP:
        return raw
    cut = raw[:GLOSS_CAP].rsplit(" ", 1)[0].rstrip(" ,;·")
    return cut or raw[:GLOSS_CAP]


def _parts_from_text(text: str) -> list[str]:
    t = _FRAME.sub(" ", text or "")
    t = t.strip()
    if not t or not _CYR.search(t):
        return []
    if t.startswith("(см.)") and len(t) < 40:
        return []
    if _TAG.match(t):
        return []
    out: list[str] = []
    for raw in _NUM.split(t):
        p = _LEAD_COLON.sub("", raw.strip())
        p = re.sub(r"\s+", " ", p).strip(" ,;·")
        if not p or p in out:
            continue
        if _TAG.match(p) or p.startswith("(см.") or p.startswith("(связ"):
            continue
        if not _CYR.search(p):
            continue
        out.append(p)
    return out


def _gloss(sense: list) -> str:
    texts: list[str] = []
    for s in sense or []:
        for g in s.get("gloss") or []:
            for part in _parts_from_text(g.get("text") or ""):
                if part not in texts:
                    texts.append(part)
                if len(texts) >= GLOSS_MAX_PARTS:
                    return _cap(GLOSS_SEP.join(texts))
    return _cap(GLOSS_SEP.join(texts))


def _kana_for(entry: dict, head: str) -> tuple[str, bool]:
    best = ""
    common = False
    for kn in entry.get("kana") or []:
        text = (kn.get("text") or "").strip()
        if not text:
            continue
        applies = kn.get("appliesToKanji") or ["*"]
        if applies != ["*"] and head not in applies:
            continue
        if kn.get("common"):
            return text, True
        if not best:
            best = text
            common = bool(kn.get("common"))
    return best, common


def _load_words(zpath: Path) -> list[dict]:
    with zipfile.ZipFile(zpath) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            return json.load(fh)["words"]


def _parse(words: list[dict], bank: set[str]) -> list[tuple[int, int, str, str, str]]:
    best: dict[str, tuple[int, int, str, str, str]] = {}
    for entry in words:
        gloss = _gloss(entry.get("sense") or [])
        if not gloss:
            continue
        for kj in entry.get("kanji") or []:
            head = (kj.get("text") or "").strip()
            if not head or len(head) > MAX_HEAD or len(head) < 2:
                continue
            chars = {c for c in head if c in bank}
            if not chars:
                continue
            kana, kn_common = _kana_for(entry, head)
            if not kana:
                continue
            k_common = 0 if kj.get("common") else 1
            n_common = 0 if kn_common else 1
            row = (k_common, n_common, head, kana, gloss)
            prev = best.get(head)
            if prev is None or row[:2] < prev[:2] or (row[:2] == prev[:2] and len(head) < len(prev[2])):
                best[head] = row
    return list(best.values())


def main() -> None:
    bank = _bank()
    zpath = _ensure_zip()
    rows = _parse(_load_words(zpath), bank)
    rows.sort(key=lambda r: (r[0], r[1], len(r[2]), r[2]))
    words = [[head, kana, gloss] for _kc, _nc, head, kana, gloss in rows]
    OUT.write_text(
        json.dumps({"source": "jmdict", "words": words}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    filled = {c for _kc, _nc, head, _kana, _g in rows for c in head if c in bank}
    print(f"wrote {OUT.name}: {len(words)} words, {len(filled)}/{len(bank)} kanji have compounds")


if __name__ == "__main__":
    main()
