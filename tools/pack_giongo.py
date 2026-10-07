"""Pack JMdict on-mim (擬音語・擬態語) for lookup.

Not LEXICON. Not catalog stations. Not a probe.
The rus dump has empty misc tags, so on-mim ids come from jmdict-eng;
Russian glosses come from jmdict-rus, joined by entry id.
Not the 擬音 textbook pairs (those stay one N4 skip-kind station).
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "proba" / "giongo.json"
FILL = ROOT / "proba" / "giongo_en_ru.json"
RUS_ZIP = ROOT / "assets" / "jmdict-rus.json.zip"
ENG_ZIP = ROOT / "assets" / "jmdict-eng.json.zip"
RELEASE = "3.6.2%2B20260622163854"
VER = "3.6.2+20260622163854"

_CYR = re.compile(r"[А-Яа-яЁё]")
_HIRA = re.compile(r"[\u3040-\u309F]")
_KATA = re.compile(r"[\u30A0-\u30FF]")
_TAG = re.compile(r"^\([^)]{1,24}\)$")
_FRAME = re.compile(r"\{[^}]+\}")
_LEAD_COLON = re.compile(r"^[:：]\s*")
_LEAD_NUM = re.compile(r"^\d+\)[:：]?\s*")
GLOSS_SEP = " · "
GLOSS_CAP = 400
GLOSS_MAX_PARTS = 8


def _ensure(path: Path, name: str) -> Path:
    if path.is_file() and path.stat().st_size > 100_000:
        return path
    url = (
        "https://github.com/scriptin/jmdict-simplified/releases/download/"
        f"{RELEASE}/{name}-{VER}.json.zip"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    print("download", url)
    req = Request(url, headers={"User-Agent": "Proba-pack/1"})
    with urlopen(req, timeout=180) as res, path.open("wb") as f:
        while True:
            chunk = res.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return path


def _load_words(zpath: Path) -> list[dict]:
    with zipfile.ZipFile(zpath) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            return json.load(fh)["words"]


def _kata_to_hira(text: str) -> str:
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def _is_mim(sense: dict) -> bool:
    return "on-mim" in (sense.get("misc") or []) or "on-mim" in (sense.get("partOfSpeech") or [])


def _skip_gloss(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if "(см.)" in t:
        return True
    if _TAG.match(t):
        return True
    return False


def _cap(text: str) -> str:
    raw = text.strip()
    if len(raw) <= GLOSS_CAP:
        return raw
    return raw[:GLOSS_CAP].rsplit(" ", 1)[0].rstrip(" ·,;")


def _strip_dump_markup(text: str) -> str:
    t = _FRAME.sub(" ", text or "")
    t = _LEAD_COLON.sub("", t.strip())
    t = _LEAD_NUM.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" ,;·")
    return t


def clean_sheet_gloss(text: str) -> str:
    chunks: list[str] = []
    for raw in (text or "").split(GLOSS_SEP):
        t = _strip_dump_markup(raw)
        if t:
            chunks.append(t)
    return GLOSS_SEP.join(chunks)


def _has_vs(sense: dict) -> bool:
    return any(p in {"vs", "vs-i", "vs-s"} for p in (sense.get("partOfSpeech") or []))


def _vs_flag(senses: list[dict]) -> int:
    if not senses:
        return 0
    return int(all(_has_vs(s) for s in senses))


def _sense_gloss(sense: dict) -> str:
    texts: list[str] = []
    for g in sense.get("gloss") or []:
        t = (g.get("text") or "").strip()
        if _skip_gloss(t) or not _CYR.search(t):
            continue
        t = _strip_dump_markup(t)
        if not t or t in texts:
            continue
        texts.append(t)
        if len(texts) >= GLOSS_MAX_PARTS:
            break
    return _cap(GLOSS_SEP.join(texts))


def _eng_gloss(sense: dict) -> str:
    texts: list[str] = []
    for g in sense.get("gloss") or []:
        t = (g.get("text") or "").strip()
        if not t or _skip_gloss(t):
            continue
        texts.append(t)
        if len(texts) >= 3:
            break
    return GLOSS_SEP.join(texts)


def _kana_rows(entry: dict) -> list[tuple[str, bool]]:
    rows: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for kn in entry.get("kana") or []:
        text = (kn.get("text") or "").strip()
        if not text or text in seen:
            continue
        if "sk" in (kn.get("tags") or []):
            continue
        if not (_HIRA.search(text) or _KATA.search(text)):
            continue
        seen.add(text)
        rows.append((text, bool(kn.get("common"))))
    return rows


def _mim_ids(eng_words: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in eng_words:
        senses = [s for s in (entry.get("sense") or []) if _is_mim(s)]
        if not senses:
            continue
        out[str(entry.get("id") or "")] = {
            "entry": entry,
            "senses": senses,
            "vs": _vs_flag(senses),
            "eng": _cap(GLOSS_SEP.join(g for s in senses if (g := _eng_gloss(s)))),
        }
    return out


def _parse(rus_words: list[dict], mim: dict[str, dict]) -> tuple[list[list], dict]:
    rus_by_id = {str(w.get("id") or ""): w for w in rus_words}
    stats = {
        "eng_mim": len(mim),
        "with_rus": 0,
        "with_eng_only": 0,
        "skipped_no_kana": 0,
        "skipped_no_gloss": 0,
    }
    best: dict[str, tuple[int, int, int, str, str, str, int, int]] = {}
    for eid, meta in mim.items():
        rus = rus_by_id.get(eid)
        entry = rus or meta["entry"]
        gloss_parts: list[str] = []
        vs = meta["vs"]
        lang = 1
        if rus:
            for s in rus.get("sense") or []:
                g = _sense_gloss(s)
                if g and g not in gloss_parts:
                    gloss_parts.append(g)
        if gloss_parts:
            gloss = _cap(GLOSS_SEP.join(gloss_parts))
            lang = 0
            stats["with_rus"] += 1
        else:
            gloss = _cap(meta.get("eng") or "")
            if not gloss:
                stats["skipped_no_gloss"] += 1
                continue
            stats["with_eng_only"] += 1
        kana_rows = _kana_rows(entry)
        if not kana_rows:
            stats["skipped_no_kana"] += 1
            continue
        kana_rows.sort(key=lambda r: (0 if _HIRA.search(r[0]) else 1, 0 if r[1] else 1, len(r[0]), r[0]))
        kana = kana_rows[0][0]
        key = _kata_to_hira(kana)
        hira_pref = 0 if _HIRA.search(kana) else 1
        common = 0 if kana_rows[0][1] else 1
        # Prefer Russian over English, then common hiragana.
        row = (lang, hira_pref, common, kana, key, gloss, vs, lang)
        prev = best.get(key)
        if prev is None or row[:3] < prev[:3]:
            best[key] = row
    words_out = [
        [kana, key, gloss, vs, lang]
        for _lg, _hp, _cm, kana, key, gloss, vs, lang in sorted(best.values(), key=lambda r: r[4])
    ]
    return words_out, stats


def apply_ru_fill(words: list[list]) -> tuple[list[list], int]:
    """Russian lookup fill for JMdict-eng-only heads. Not a probe, not LEXICON."""
    if not FILL.is_file():
        return words, sum(1 for row in words if int(row[4]) == 1)
    fill = json.loads(FILL.read_text(encoding="utf-8"))
    out: list[list] = []
    missing = 0
    for kana, key, gloss, vs, lang in words:
        if int(lang) == 1:
            ru = (fill.get(gloss) or "").strip()
            if ru and _CYR.search(ru):
                gloss = _cap(ru)
                lang = 0
            else:
                missing += 1
        out.append([kana, key, clean_sheet_gloss(gloss), vs, lang])
    return out, missing


def main() -> None:
    rus = _load_words(_ensure(RUS_ZIP, "jmdict-rus"))
    eng = _load_words(_ensure(ENG_ZIP, "jmdict-eng"))
    words, stats = _parse(rus, _mim_ids(eng))
    words, missing = apply_ru_fill(words)
    words = [[kana, key, clean_sheet_gloss(gloss), vs, lang] for kana, key, gloss, vs, lang in words]
    stats["ru_fill_missing"] = missing
    OUT.write_text(
        json.dumps(
            {"source": "jmdict", "kind": "on-mim", "words": words},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT.name}: {len(words)} heads")
    print("stats", stats)


def rewrite_packed() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    data["words"] = [
        [kana, key, clean_sheet_gloss(gloss), vs, lang]
        for kana, key, gloss, vs, lang in data["words"]
    ]
    OUT.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"rewrote {OUT.name}: {len(data['words'])} heads")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rewrite":
        rewrite_packed()
    else:
        main()
