"""Pack several Russian senses per unofficial N5–N1 kanji.

Lookup for the kanji card, not LEXICON and not a probe.
Prefer JMdict-rus (the character, then a kun-word). Remaining characters
use KANJIDIC English filled into Russian. The sheet never shows English.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "proba" / "jlpt_kanji.json"
OUT = ROOT / "proba" / "kanji_ru.json"
FILL = ROOT / "proba" / "kanji_en_ru.json"
RUS_ZIP = ROOT / "assets" / "jmdict-rus.json.zip"
RUS_URL = (
    "https://github.com/scriptin/jmdict-simplified/releases/download/"
    "3.6.2%2B20260622163854/jmdict-rus-3.6.2+20260622163854.json.zip"
)
KANJIDIC = ROOT / "assets" / "kanjidic2.xml"
KANJIDIC_URL = "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz"

GLOSS_SEP = " · "
GLOSS_MAX = 5
PART_CAP = 48
_CYR = re.compile(r"[А-Яа-яЁё]")
_LAT = re.compile(r"[A-Za-z]")
_FRAME = re.compile(r"\{[^}]+\}")
_LEAD_COLON = re.compile(r"^[:：]\s*")
_LEAD_NUM = re.compile(r"^(?:\d+[.)]|[1-9]\.)[:：]?\s*")
_LEAD_NOTE = re.compile(r"^\([^)]{1,28}\)\s*")
_TAG = re.compile(r"^\([^)]{1,32}\)$")
_POS_LINE = re.compile(r"^\d+\.\s*\([^)]+\)\s*$")
_SPLIT = re.compile(r"[;；]")
_SKIP_HINT = re.compile(r"фил\.|буд\.|санскр|англ\.|уст\.|прост\. см|зодиак|тж\.|\([а-яё]\)")
_KANA = re.compile(r"[\u3040-\u30ff]")
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SEED: dict[str, list[str]] = {
    "不": ["не", "нет", "без-", "отрицание"],
    "無": ["нет", "без-", "небытие"],
    "非": ["не", "ложь"],
    "未": ["ещё не", "будущее"],
    "可": ["можно", "возможный"],
    "第": ["номер", "порядок"],
    "援": ["помогать", "спасать"],
    "皇": ["император"],
    "菖": ["ирис"],
    "丞": ["помогать"],
    "迅": ["быстрый", "скорый"],
    "般": ["общий", "род", "вид"],
    "祐": ["помогать"],
    "蓉": ["лотос"],
    "迪": ["путь", "наставлять"],
    "博": ["доктор", "ярмарка"],
    "柊": ["остролист"],
    "柚": ["юдзу", "цитрон"],
    "桐": ["павловния"],
    "桑": ["шелковица"],
    "楠": ["камфорное дерево"],
    "竣": ["завершать"],
    "葵": ["мальва"],
    "蓮": ["лотос"],
    "鯛": ["спар"],
    "鶴": ["журавль"],
}


def _bank() -> dict[str, dict]:
    blob = json.loads(BANK.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for items in blob.values():
        if not isinstance(items, list):
            continue
        for item in items:
            ch = (item.get("c") or "").strip()
            if len(ch) == 1:
                out[ch] = item
    return out


def _ensure_zip() -> Path:
    if RUS_ZIP.is_file() and RUS_ZIP.stat().st_size > 100_000:
        return RUS_ZIP
    RUS_ZIP.parent.mkdir(parents=True, exist_ok=True)
    print("download", RUS_URL)
    req = urllib.request.Request(RUS_URL, headers={"User-Agent": "Proba-pack/1"})
    with urllib.request.urlopen(req, timeout=180) as res:
        RUS_ZIP.write_bytes(res.read())
    return RUS_ZIP


def _ensure_kanjidic() -> Path:
    if KANJIDIC.is_file() and KANJIDIC.stat().st_size > 100_000:
        return KANJIDIC
    import gzip

    KANJIDIC.parent.mkdir(parents=True, exist_ok=True)
    print("download", KANJIDIC_URL)
    req = urllib.request.Request(KANJIDIC_URL, headers={"User-Agent": "Proba-pack/1"})
    with urllib.request.urlopen(req, timeout=180) as res:
        KANJIDIC.write_bytes(gzip.decompress(res.read()))
    return KANJIDIC


def _load_words(zpath: Path) -> list[dict]:
    import zipfile

    with zipfile.ZipFile(zpath) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            return json.load(fh)["words"]


def _strip(text: str, cap: bool = False) -> str:
    t = _FRAME.sub(" ", text or "")
    t = _LEAD_NUM.sub("", t.strip())
    t = _LEAD_COLON.sub("", t)
    t = _LEAD_NOTE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" ,;·")
    t = re.sub(r"^\[([^\[\]]+)\]\s*", r"\1 ", t).strip()
    if cap and len(t) > PART_CAP:
        t = t[:PART_CAP].rsplit(" ", 1)[0].rstrip(" ,;·")
    return t


def _keep(text: str) -> bool:
    t = (text or "").strip()
    if not t or not _CYR.search(t):
        return False
    if _KANA.search(t) or _LAT.search(t):
        return False
    if t.count("(") != t.count(")"):
        return False
    if t.startswith(")") or t.endswith("("):
        return False
    if _TAG.match(t) or _POS_LINE.match(t):
        return False
    if _SKIP_HINT.search(t):
        return False
    if t.startswith("(см.") or t.startswith("(связ") or t.startswith("(диал"):
        return False
    if t in {"неперех.", "перех.", "быть"}:
        return False
    if t.startswith("по "):
        return False
    return True


def _comma_bits(text: str) -> list[str]:
    if "," not in text and "，" not in text:
        return [text]
    bits = [b.strip() for b in re.split(r"[,，]", text) if b.strip()]
    if any(b.count("(") != b.count(")") for b in bits):
        return [text]
    if bits and all(len(b) <= 22 and _keep(b) for b in bits):
        return bits
    return [text]


def _parts_from_text(text: str) -> list[str]:
    raw = _strip(text, cap=False)
    if not raw:
        return []
    out: list[str] = []
    for bit in _SPLIT.split(raw):
        p = _strip(bit, cap=True)
        for piece in _comma_bits(p):
            if _keep(piece) and piece not in out:
                out.append(piece)
    return out


def _sense_parts(entry: dict) -> list[str]:
    out: list[str] = []
    for sense in entry.get("sense") or []:
        for g in sense.get("gloss") or []:
            for part in _parts_from_text(g.get("text") or ""):
                if part not in out:
                    out.append(part)
                if len(out) >= GLOSS_MAX:
                    return out
    return out


def _prefer(parts: list[str]) -> list[str]:
    good = [p for p in parts if not p.startswith("(")]
    rest = [p for p in parts if p.startswith("(")]
    return good + rest


def _join(parts: list[str]) -> str:
    uniq: list[str] = []
    for p in _prefer(parts):
        if p and p not in uniq:
            uniq.append(p)
        if len(uniq) >= GLOSS_MAX:
            break
    return GLOSS_SEP.join(uniq)


def _kanjidic_en(bank: set[str]) -> dict[str, list[str]]:
    text = _ensure_kanjidic().read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    for block in text.split("<character>")[1:]:
        lit = re.search(r"<literal>([^<]+)</literal>", block)
        if not lit or lit.group(1) not in bank:
            continue
        meanings: list[str] = []
        for m in re.finditer(r'<meaning(?: m_lang="([^"]+)")?>([^<]+)</meaning>', block):
            lang = m.group(1) or "en"
            if lang != "en":
                continue
            t = (m.group(2) or "").strip()
            if t and t not in meanings:
                meanings.append(t)
            if len(meanings) >= GLOSS_MAX:
                break
        if meanings:
            out[lit.group(1)] = meanings
    return out


def _load_fill() -> dict[str, str]:
    if FILL.is_file():
        blob = json.loads(FILL.read_text(encoding="utf-8"))
        if isinstance(blob, dict):
            return {str(k): str(v) for k, v in blob.items() if v}
    return {}


def _save_fill(fill: dict[str, str]) -> None:
    FILL.write_text(json.dumps(fill, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def _mt_en(text: str) -> str:
    q = urllib.parse.quote((text or "")[:180])
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|ru"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ru = ((data.get("responseData") or {}).get("translatedText") or "").strip()
    if not ru or not _CYR.search(ru) or ru.lower() == text.lower():
        return ""
    return _strip(ru)


def _fill_missing(ch: str, english: list[str], fill: dict[str, str]) -> list[str]:
    blob = "; ".join(english[:GLOSS_MAX])
    if not blob:
        return []
    if blob in fill:
        ru = fill[blob]
    else:
        try:
            ru = _mt_en(blob)
        except Exception:
            ru = ""
        if ru:
            fill[blob] = ru
            _save_fill(fill)
    if not ru:
        return []
    parts: list[str] = []
    for bit in re.split(r"[;；,]", ru):
        p = _strip(bit, cap=True)
        if _keep(p) and p not in parts:
            parts.append(p)
    return parts


def main() -> None:
    bank = _bank()
    words = _load_words(_ensure_zip())
    one: dict[str, list[tuple[int, list[str]]]] = {ch: [] for ch in bank}
    kun: dict[tuple[str, str], list[str]] = {}
    for entry in words:
        parts = _sense_parts(entry)
        if not parts:
            continue
        common_k = 0
        for kj in entry.get("kanji") or []:
            if kj.get("common"):
                common_k = 1
                break
        rank = 0 if common_k else 1
        for kj in entry.get("kanji") or []:
            head = (kj.get("text") or "").strip()
            if not head:
                continue
            if len(head) == 1 and head in one:
                one[head].append((rank, parts))
            ch0 = head[0]
            if ch0 in bank:
                for kn in entry.get("kana") or []:
                    kana = (kn.get("text") or "").strip()
                    if not kana:
                        continue
                    applies = kn.get("appliesToKanji") or ["*"]
                    if applies != ["*"] and head not in applies:
                        continue
                    key = (ch0, kana)
                    prev = kun.get(key)
                    if prev is None or (rank == 0 and len(parts) >= len(prev)):
                        kun[key] = parts

    english = _kanjidic_en(set(bank))
    fill = _load_fill()
    gloss: dict[str, str] = {}
    used_jm = used_kun = used_seed = used_en = 0
    for ch, item in bank.items():
        parts: list[str] = []
        if ch in SEED:
            parts.extend(SEED[ch])
            used_seed += 1
        kun_txt = item.get("kun") or ""
        for reading in kun_txt.split("・"):
            reading = reading.strip()
            extra = kun.get((ch, reading)) if reading else None
            if not extra:
                continue
            used_kun += 1
            for p in extra:
                if p not in parts:
                    parts.append(p)
                if len(parts) >= 3:
                    break
            if len(parts) >= 3:
                break
        if len(parts) < GLOSS_MAX:
            rows = sorted(one.get(ch) or [], key=lambda r: r[0])
            if rows:
                used_jm += 1
                for _rank, chunk in rows:
                    for p in chunk:
                        if p not in parts:
                            parts.append(p)
                        if len(parts) >= GLOSS_MAX:
                            break
                    if len(parts) >= GLOSS_MAX:
                        break
        if len(parts) < 2:
            extra = _fill_missing(ch, english.get(ch) or [], fill)
            if extra:
                used_en += 1
                for p in extra:
                    if p not in parts:
                        parts.append(p)
                    if len(parts) >= GLOSS_MAX:
                        break
        text = _join(parts)
        if text:
            gloss[ch] = text

    OUT.write_text(
        json.dumps({"source": "jmdict", "kanji": gloss}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"wrote {OUT.name}: {len(gloss)}/{len(bank)} kanji, "
        f"jmdict {used_jm}, kun {used_kun}, seed {used_seed}, kanjidic-fill {used_en}"
    )


if __name__ == "__main__":
    main()
