"""Join OCR lines so a wrap is not a new word.

Textbook Japanese splits compounds across lines with no hyphen.
Latin wraps may leave a trailing ASCII hyphen. Long vowel ー is not a wrap mark.
Lookup, not a probe: stitching happens before translation.
"""

from __future__ import annotations

import re

_JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\u3000-\u303f]")
_SENT_END = re.compile(r"[。．.！？!?…）」』】]$")
_HYPHEN_END = re.compile(r"[-\u00ad\u2010\u2011]$")


def jp_ratio(text: str) -> float:
    raw = text or ""
    if not raw:
        return 0.0
    return len(_JP.findall(raw)) / len(raw)


def _glue(prev: str, nxt: str) -> str:
    a = prev.rstrip()
    b = nxt.lstrip()
    if not a:
        return ""
    if not b:
        return "\n"
    if _HYPHEN_END.search(a) and jp_ratio(a) < 0.4:
        return "hyphen"
    if _SENT_END.search(a):
        return "\n"
    ja_a = jp_ratio(a) >= 0.25
    ja_b = jp_ratio(b) >= 0.25
    if ja_a and ja_b:
        return ""
    if ja_a != ja_b:
        return " "
    if a[-1] in "、,，:：;；":
        return "" if ja_b else " "
    if _JP.search(a[-1] or "") and _JP.search(b[0] or ""):
        return ""
    if a[-1].isalnum() and b[0].isalnum() and not ja_a:
        return " "
    return " " if not ja_a else ""


def stitch_lines(lines: list[str] | None) -> str:
    paras: list[str] = []
    buf = ""
    for raw in lines or []:
        line = (raw or "").replace("\u00a0", " ").strip()
        if not line:
            if buf:
                paras.append(buf)
                buf = ""
            continue
        if not buf:
            buf = line
            continue
        glue = _glue(buf, line)
        if glue == "hyphen":
            buf = _HYPHEN_END.sub("", buf) + line
        elif glue == "\n":
            paras.append(buf)
            buf = line
        else:
            buf = buf + glue + line
    if buf:
        paras.append(buf)
    return "\n\n".join(paras)


def _join_same_line(parts: list[str]) -> str:
    buf = ""
    for part in parts:
        bit = (part or "").strip()
        if not bit:
            continue
        if not buf:
            buf = bit
            continue
        glue = _glue(buf, bit)
        if glue == "hyphen":
            buf = _HYPHEN_END.sub("", buf) + bit
        elif glue == "\n":
            buf = buf + bit
        else:
            buf = buf + glue + bit
    return buf


def _vcenter(w: dict) -> float:
    return float(w.get("top") or 0) + max(float(w.get("height") or 1), 1.0) / 2


def _row_metrics(row: list[dict]) -> tuple[float, float]:
    hs = [max(float(w.get("height") or 1), 1.0) for w in row]
    return sum(_vcenter(w) for w in row) / len(row), max(hs)


def lines_from_words(words: list[dict] | None) -> list[str]:
    items = [w for w in (words or []) if (w.get("text") or "").strip()]
    if not items:
        return []
    items = sorted(items, key=lambda w: (_vcenter(w), float(w.get("left") or 0)))
    rows: list[list[dict]] = []
    for w in items:
        if not rows:
            rows.append([w])
            continue
        rc, rh = _row_metrics(rows[-1])
        wh = max(float(w.get("height") or 1), 1.0)
        if abs(_vcenter(w) - rc) <= max(rh, wh) * 0.55:
            rows[-1].append(w)
        else:
            rows.append([w])
    out: list[str] = []
    for row in rows:
        row.sort(key=lambda w: float(w.get("left") or 0))
        out.append(_join_same_line([str(w.get("text") or "") for w in row]))
    return [line for line in out if line]


def reconstruct(lines: list[str] | None = None, words: list[dict] | None = None) -> str:
    if words:
        return stitch_lines(lines_from_words(words))
    return stitch_lines(lines or [])
