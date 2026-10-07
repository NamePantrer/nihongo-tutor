from __future__ import annotations

import re
import unicodedata

# Longest first. Hepburn + common IME aliases (si/shi, tu/tsu).
_MORA: tuple[tuple[str, str], ...] = (
    ("kya", "きゃ"),
    ("kyu", "きゅ"),
    ("kyo", "きょ"),
    ("gya", "ぎゃ"),
    ("gyu", "ぎゅ"),
    ("gyo", "ぎょ"),
    ("sha", "しゃ"),
    ("shu", "しゅ"),
    ("sho", "しょ"),
    ("sya", "しゃ"),
    ("syu", "しゅ"),
    ("syo", "しょ"),
    ("ja", "じゃ"),
    ("ju", "じゅ"),
    ("jo", "じょ"),
    ("jya", "じゃ"),
    ("jyu", "じゅ"),
    ("jyo", "じょ"),
    ("zya", "じゃ"),
    ("zyu", "じゅ"),
    ("zyo", "じょ"),
    ("cha", "ちゃ"),
    ("chu", "ちゅ"),
    ("cho", "ちょ"),
    ("tya", "ちゃ"),
    ("tyu", "ちゅ"),
    ("tyo", "ちょ"),
    ("nya", "にゃ"),
    ("nyu", "にゅ"),
    ("nyo", "にょ"),
    ("hya", "ひゃ"),
    ("hyu", "ひゅ"),
    ("hyo", "ひょ"),
    ("bya", "びゃ"),
    ("byu", "びゅ"),
    ("byo", "びょ"),
    ("pya", "ぴゃ"),
    ("pyu", "ぴゅ"),
    ("pyo", "ぴょ"),
    ("mya", "みゃ"),
    ("myu", "みゅ"),
    ("myo", "みょ"),
    ("rya", "りゃ"),
    ("ryu", "りゅ"),
    ("ryo", "りょ"),
    ("shi", "し"),
    ("chi", "ち"),
    ("tsu", "つ"),
    ("xtu", "っ"),
    ("ltu", "っ"),
    ("xtsu", "っ"),
    ("ltsu", "っ"),
    ("xya", "ゃ"),
    ("xyu", "ゅ"),
    ("xyo", "ょ"),
    ("lya", "ゃ"),
    ("lyu", "ゅ"),
    ("lyo", "ょ"),
    ("xa", "ぁ"),
    ("xi", "ぃ"),
    ("xu", "ぅ"),
    ("xe", "ぇ"),
    ("xo", "ぉ"),
    ("la", "ぁ"),
    ("li", "ぃ"),
    ("lu", "ぅ"),
    ("le", "ぇ"),
    ("lo", "ぉ"),
    ("wu", "う"),
    ("wha", "うぁ"),
    ("whi", "うぃ"),
    ("whe", "うぇ"),
    ("who", "うぉ"),
    ("tsi", "つぃ"),
    ("tse", "つぇ"),
    ("tso", "つぉ"),
    ("thi", "てぃ"),
    ("dhi", "でぃ"),
    ("twu", "とぅ"),
    ("dwu", "どぅ"),
    ("fu", "ふ"),
    ("hu", "ふ"),
    ("ji", "じ"),
    ("zi", "じ"),
    ("di", "ぢ"),
    ("du", "づ"),
    ("dzu", "づ"),
    ("si", "し"),
    ("ti", "ち"),
    ("tu", "つ"),
    ("ka", "か"),
    ("ki", "き"),
    ("ku", "く"),
    ("ke", "け"),
    ("ko", "こ"),
    ("ga", "が"),
    ("gi", "ぎ"),
    ("gu", "ぐ"),
    ("ge", "げ"),
    ("go", "ご"),
    ("sa", "さ"),
    ("su", "す"),
    ("se", "せ"),
    ("so", "そ"),
    ("za", "ざ"),
    ("zu", "ず"),
    ("ze", "ぜ"),
    ("zo", "ぞ"),
    ("ta", "た"),
    ("te", "て"),
    ("to", "と"),
    ("da", "だ"),
    ("de", "で"),
    ("do", "ど"),
    ("na", "な"),
    ("ni", "に"),
    ("nu", "ぬ"),
    ("ne", "ね"),
    ("no", "の"),
    ("ha", "は"),
    ("hi", "ひ"),
    ("he", "へ"),
    ("ho", "ほ"),
    ("ba", "ば"),
    ("bi", "び"),
    ("bu", "ぶ"),
    ("be", "べ"),
    ("bo", "ぼ"),
    ("pa", "ぱ"),
    ("pi", "ぴ"),
    ("pu", "ぷ"),
    ("pe", "ぺ"),
    ("po", "ぽ"),
    ("ma", "ま"),
    ("mi", "み"),
    ("mu", "む"),
    ("me", "め"),
    ("mo", "も"),
    ("ya", "や"),
    ("yu", "ゆ"),
    ("yo", "よ"),
    ("ra", "ら"),
    ("ri", "り"),
    ("ru", "る"),
    ("re", "れ"),
    ("ro", "ろ"),
    ("wa", "わ"),
    ("wo", "を"),
    ("nn", "ん"),
    ("n'", "ん"),
    ("va", "ゔぁ"),
    ("vi", "ゔぃ"),
    ("vu", "ゔ"),
    ("ve", "ゔぇ"),
    ("vo", "ゔぉ"),
    ("fa", "ふぁ"),
    ("fi", "ふぃ"),
    ("fe", "ふぇ"),
    ("fo", "ふぉ"),
    ("a", "あ"),
    ("i", "い"),
    ("u", "う"),
    ("e", "え"),
    ("o", "お"),
    ("-", "ー"),
)

_Y_GLIDE = frozenset("ya yu yo".split())
_CONSONANT = frozenset("bcdfghjklmpqrstvwxyz")
_SOKUON_C = frozenset("bcdfghjklmpqrstvwxyz") - frozenset("n")
_KATA = str.maketrans(
    "ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ",
    "ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをんゔゕゖ",
)
_PUNCT = re.compile(r"[\s\u3000、。・「」『』（）()\[\].,!?！？〜~…'’\"“”]+")


def _fold_latin(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKC", text):
        if "A" <= ch <= "Z" or "a" <= ch <= "z" or ch in "-'":
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _match_mora(chunk: str) -> tuple[str, int] | None:
    low = chunk.lower()
    for roman, kana in _MORA:
        if low.startswith(roman):
            return kana, len(roman)
    return None


def romaji_to_hiragana(text: str, *, commit: bool = False) -> str:
    """Convert roman letters to hiragana; leave unfinished latin if commit is False."""
    s = _fold_latin(text)
    i = 0
    out: list[str] = []
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "n":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "n":
                rest = s[i + 1 :]
                if _match_mora(rest):
                    out.append("ん")
                    i += 1
                    continue
                out.append("ん")
                i += 2
                continue
            if nxt == "'":
                out.append("ん")
                i += 2
                continue
            if nxt == "y" and i + 2 < n and s[i + 2] in "auo":
                hit = _match_mora(s[i:])
                if hit:
                    kana, consumed = hit
                    out.append(kana)
                    i += consumed
                    continue
            if nxt == "":
                out.append("ん" if commit else "n")
                i += 1
                continue
            if nxt not in "aiueoy":
                out.append("ん")
                i += 1
                continue
            hit = _match_mora(s[i:])
            if hit:
                kana, consumed = hit
                out.append(kana)
                i += consumed
                continue
        if (
            i + 1 < n
            and ch in _SOKUON_C
            and s[i + 1] == ch
            and _match_mora(s[i + 1 :])
        ):
            out.append("っ")
            i += 1
            continue
        hit = _match_mora(s[i:])
        if hit:
            kana, consumed = hit
            out.append(kana)
            i += consumed
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _kanji_to_hira(text: str) -> str:
    try:
        import pykakasi
    except ImportError:
        return text
    conv = getattr(_kanji_to_hira, "_conv", None)
    if conv is None:
        conv = pykakasi.kakasi()
        _kanji_to_hira._conv = conv  # type: ignore[attr-defined]
    parts = conv.convert(text)
    return "".join(p.get("hira") or p.get("orig", "") for p in parts)


def to_reading(text: str) -> str:
    """Hiragana reading used for auto-grade. Kanji folded to sound, not to a second teacher key in the UI."""
    raw = romaji_to_hiragana(text or "", commit=True)
    raw = raw.translate(_KATA)
    raw = _kanji_to_hira(raw)
    return _PUNCT.sub("", raw)


def grade(response: str, expected: str) -> dict:
    """pass or fail only. No Levenshtein partial (は/が would become 'close')."""
    empty = not (response or "").strip()
    got = to_reading(response or "")
    want = to_reading(expected or "")
    if empty or not want:
        outcome = "fail"
    elif got == want:
        outcome = "pass"
    else:
        outcome = "fail"
    return {
        "outcome": outcome,
        "reading": got,
        "expected_reading": want,
        "empty": empty,
    }
