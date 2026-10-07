"""Pack KanjiVG stroke paths and component groups for the N5–N1 bank."""

from __future__ import annotations

import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XML_GZ = ROOT / "assets" / "kanjivg-20250816.xml.gz"
BANK = ROOT / "proba" / "jlpt_kanji.json"
OUT = ROOT / "proba" / "kanjivg_paths.json"
OUT_PARTS = ROOT / "proba" / "kanjivg_parts.json"

_BLOCK = re.compile(r'<kanji id="kvg:kanji_([0-9a-f]+)">(\s*.*?)</kanji>', re.S)
_EL = re.compile(r'kvg:element="([^"]+)"')
_PATH = re.compile(r'<path[^>]*id="kvg:[^"]*-s(\d+)"[^>]*d="([^"]+)"')
KVG = "{http://kanjivg.tagaini.net}"


def _parts(body: str, paths: list[str]) -> dict:
    try:
        root = ET.fromstring(f'<kanji xmlns:kvg="http://kanjivg.tagaini.net">{body}</kanji>')
    except ET.ParseError:
        return {"radical": "", "parts": []}
    top = next((c for c in list(root) if c.tag == "g"), None)
    if top is None:
        return {"radical": "", "parts": []}
    index = {d: i for i, d in enumerate(paths)}
    groups = [c for c in list(top) if c.tag == "g"]
    parts = []
    radical = ""
    for g in groups:
        el = g.get(KVG + "element") or ""
        orig = g.get(KVG + "original") or ""
        rad = g.get(KVG + "radical") or ""
        ds = [p.get("d") or "" for p in g.iter("path") if p.get("d")]
        ix = [index[d] for d in ds if d in index]
        if not el or not ix:
            continue
        parts.append({"e": el, "o": orig, "r": rad, "i": ix})
        if rad == "general" and not radical:
            radical = orig or el
    if not radical:
        radical = top.get(KVG + "element") or ""
    if len(parts) < 2:
        parts = []
    return {"radical": radical, "parts": parts}


def pack() -> dict:
    need = {
        item["c"]
        for items in json.loads(BANK.read_text(encoding="utf-8")).values()
        for item in items
        if item.get("c")
    }
    xml = gzip.open(XML_GZ, "rt", encoding="utf-8").read()
    out: dict[str, list[str]] = {}
    parts_out: dict[str, dict] = {}
    for hexid, body in _BLOCK.findall(xml):
        els = _EL.findall(body)
        ch = els[0] if els else chr(int(hexid, 16))
        if ch not in need:
            continue
        strokes = [(int(n), d) for n, d in _PATH.findall(body)]
        strokes.sort()
        if not strokes:
            continue
        paths = [d for _, d in strokes]
        out[ch] = paths
        blob = _parts(body, paths)
        if blob["radical"] or blob["parts"]:
            parts_out[ch] = blob
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUT_PARTS.write_text(
        json.dumps(parts_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    missing = sorted(need - set(out))
    print(
        f"packed {len(out)} / {len(need)}  parts {len(parts_out)}  "
        f"bytes {OUT.stat().st_size}+{OUT_PARTS.stat().st_size}"
    )
    if missing:
        print("missing", "".join(missing[:40]))
    return out


if __name__ == "__main__":
    pack()
