from __future__ import annotations

import re

from proba import curriculum, dictionary

_SENT = re.compile(r"[^。！？\n]+[。！？]?")
_JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]+")
_RU_CORR = re.compile(
    r"не\s*([ぁ-んァ-ン一-龯]{1,12})\s*[,，、]?\s*а\s*([ぁ-んァ-ン一-龯]{1,12})",
    re.I,
)
_JA_CORR = re.compile(
    r"([ぁ-んァ-ン一-龯]{1,12})\s*(?:じゃなくて|ではなくて|ではなく)\s*([ぁ-んァ-ン一-龯]{1,12})"
)

_HEADS = sorted((h for h, _, _ in dictionary.LEXICON), key=len, reverse=True)
_GLOSS = {h: g for h, _, g in dictionary.LEXICON}

FILL_CAP = 7

_SKIP_ALONE = {
    "です",
    "ます",
    "ました",
    "こんにちは",
    "こんばんは",
    "おはよう",
    "ありがとう",
    "すみません",
    "ください",
}

_ICHIDAN = frozenset(
    {
        "見る",
        "食べる",
        "始める",
        "教える",
        "降りる",
        "忘れる",
        "覚える",
        "出来る",
        "くれる",
        "あげる",
        "着る",
        "読める",
        "書ける",
    }
)
_SKIP_VERB = frozenset({"いる", "ある"})
_I_ADJ = (
    "寒い",
    "暑い",
    "忙しい",
    "難しい",
    "易しい",
    "早い",
    "遅い",
    "多い",
    "少ない",
)

_A_ROW = {
    "う": "わ",
    "く": "か",
    "ぐ": "が",
    "す": "さ",
    "つ": "た",
    "ぬ": "な",
    "ぶ": "ば",
    "む": "ま",
    "る": "ら",
}
_I_ROW = {
    "う": "い",
    "く": "き",
    "ぐ": "ぎ",
    "す": "し",
    "つ": "ち",
    "ぬ": "に",
    "ぶ": "び",
    "む": "み",
    "る": "り",
}
_E_ROW = {
    "う": "え",
    "く": "け",
    "ぐ": "げ",
    "す": "せ",
    "つ": "て",
    "ぬ": "ね",
    "ぶ": "べ",
    "む": "め",
    "る": "れ",
}
_TE = {
    "う": "って",
    "く": "いて",
    "ぐ": "いで",
    "す": "して",
    "つ": "って",
    "ぬ": "んで",
    "ぶ": "んで",
    "む": "んで",
    "る": "って",
}
_TA = {
    "う": "った",
    "く": "いた",
    "ぐ": "いだ",
    "す": "した",
    "つ": "った",
    "ぬ": "んだ",
    "ぶ": "んだ",
    "む": "んだ",
    "る": "った",
}

_TE_MAP = {
    "行って": "行く",
    "来て": "来る",
    "して": "する",
    "見て": "見る",
}
_WANT = {"飲みたい": "飲む"}
_NAI_MAP = {"食べない": "食べる"}
_POT_MAP = {"読める": "読む", "書ける": "書く"}

_HINT_FROM_GLOSS = (
    ("て-форма", "て-форма"),
    ("най-форма", "ない-форма"),
    ("хотеть", "たい"),
    ("мочь", "потенциал"),
    ("процесс", "ている"),
    ("давать (ко мне)", "направление: к вам"),
    ("давать (от меня)", "направление: от вас"),
    ("получать", "もらう"),
)


def _leaks(prompt_ja: str, expected: str) -> bool:
    p = (prompt_ja or "").replace("___", "").replace("…", "").replace("...", "").strip()
    e = (expected or "").strip()
    return bool(e) and p == e


def sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    found = [m.group(0).strip() for m in _SENT.finditer(raw)]
    return [s for s in found if _JP.search(s) and len(s) >= 2][:40]


def attested_tags(text: str) -> list[str]:
    raw = text or ""
    tags: list[str] = []
    if re.search(r"て(いる|る)?|って|んで", raw):
        tags.append("te-form")
    if "たい" in raw:
        tags.append("tai")
    if re.search(r"ない|ません", raw):
        tags.append("nai")
    if any(w in raw for w in ("くれる", "あげ", "もら")):
        tags.append("give")
    if "ので" in raw or "だから" in raw or any(adj + "から" in raw for adj in _I_ADJ):
        tags.append("reason")
    if any(w in raw for w in ("もう", "まだ")):
        tags.append("mou")
    if "てい" in raw or "てる" in raw:
        tags.append("teiru")
    if re.search(r"[えけげせぜてでねべめれ]る", raw) and re.search(
        r"読|書|話|聞", raw
    ):
        tags.append("potential")
    if "冊" in raw or re.search(r"[一二三四五六七八九十百千万0-9]+本", raw):
        tags.append("counter")
    return tags


def _hint_for(head: str, gloss: str) -> str:
    for needle, hint in _HINT_FROM_GLOSS:
        if needle in (gloss or ""):
            return hint
    return "произведите форму, как на уроке"


def _prompt_for(head: str) -> str:
    if head in _TE_MAP:
        return _TE_MAP[head]
    if head in _WANT:
        return _WANT[head]
    if head in _NAI_MAP:
        return _NAI_MAP[head]
    if head in _POT_MAP:
        return _POT_MAP[head]
    return head


def _kind(base: str) -> str | None:
    if base in _SKIP_VERB or base in _SKIP_ALONE:
        return None
    if base == "する":
        return "suru"
    if base == "来る":
        return "kuru"
    if base == "行く":
        return "iku"
    if base in _ICHIDAN:
        return "ichidan"
    if len(base) >= 2 and base[-1] in _A_ROW:
        return "godan"
    return None


def _forms(base: str, kind: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    def add(surface: str, hint: str, gloss: str) -> None:
        if surface and surface != base:
            out.append((surface, hint, gloss))

    if kind == "suru":
        add("して", "て-форма", "する → して")
        add("した", "た-форма", "する → した")
        add("しない", "ない-форма", "する → しない")
        add("したい", "たい", "する → したい")
        add("している", "ている", "する → している")
        add("してる", "ている", "する → してる")
        add("します", "ます", "する → します")
        return out
    if kind == "kuru":
        add("来て", "て-форма", "来る → 来て")
        add("来た", "た-форма", "来る → 来た")
        add("来ない", "ない-форма", "来る → 来ない")
        add("来たい", "たい", "来る → 来たい")
        add("来ている", "ている", "来る → 来ている")
        add("来てる", "ている", "来る → 来てる")
        add("来ます", "ます", "来る → 来ます")
        return out
    if kind == "iku":
        add("行って", "て-форма", "行く → 行って")
        add("行った", "た-форма", "行く → 行った")
        add("行かない", "ない-форма", "行く → 行かない")
        add("行きたい", "たい", "行く → 行きたい")
        add("行ける", "потенциал", "行く → 行ける")
        add("行っている", "ている", "行く → 行っている")
        add("行ってる", "ている", "行く → 行ってる")
        add("行きます", "ます", "行く → 行きます")
        return out
    if kind == "ichidan":
        stem = base[:-1]
        add(stem + "て", "て-форма", f"{base} → {stem}て")
        add(stem + "た", "た-форма", f"{base} → {stem}た")
        add(stem + "ない", "ない-форма", f"{base} → {stem}ない")
        add(stem + "たい", "たい", f"{base} → {stem}たい")
        add(stem + "ている", "ている", f"{base} → {stem}ている")
        add(stem + "てる", "ている", f"{base} → {stem}てる")
        add(stem + "ます", "ます", f"{base} → {stem}ます")
        add(stem + "られる", "потенциал", f"{base} → {stem}られる")
        return out
    end = base[-1]
    stem = base[:-1]
    add(stem + _TE[end], "て-форма", f"{base} → {stem}{_TE[end]}")
    add(stem + _TA[end], "た-форма", f"{base} → {stem}{_TA[end]}")
    add(stem + _A_ROW[end] + "ない", "ない-форма", f"{base} → {stem}{_A_ROW[end]}ない")
    add(stem + _I_ROW[end] + "たい", "たい", f"{base} → {stem}{_I_ROW[end]}たい")
    add(stem + _E_ROW[end] + "る", "потенциал", f"{base} → {stem}{_E_ROW[end]}る")
    te = stem + _TE[end]
    add(te + "いる", "ている", f"{base} → {te}いる")
    add(te + "る", "ている", f"{base} → {te}る")
    add(stem + _I_ROW[end] + "ます", "ます", f"{base} → {stem}{_I_ROW[end]}ます")
    return out


_HINT_RU = {
    "て-форма": "て-форма",
    "た-форма": "прошедшее",
    "ない-форма": "отрицание",
    "たい": "хотеть",
    "ている": "процесс / состояние",
    "ます": "вежливо",
    "потенциал": "мочь",
}


def inflections_of(base: str) -> list[dict]:
    """Generated dictionary paradigm. Not a teacher key and not a probe."""
    kind = _kind(base)
    if not kind:
        return []
    base_gloss = dictionary.gloss_for(base)
    kana_of = {h: k for h, k, _g in dictionary.LEXICON}
    out = []
    for surface, hint, _arrow in _forms(base, kind):
        form_ru = _HINT_RU.get(hint, hint)
        gloss = " · ".join(x for x in (form_ru, base_gloss) if x)
        out.append(
            {
                "surface": surface,
                "hint": hint,
                "kana": kana_of.get(surface, ""),
                "gloss_ru": gloss,
            }
        )
    return out


def _verb_catalog() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for head, _, gloss in dictionary.LEXICON:
        kind = _kind(head)
        if not kind:
            continue
        for surface, hint, g in _forms(head, kind):
            rows.append((surface, head, hint, g or gloss))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    return rows


_VERB_FORMS = _verb_catalog()


def _take_spans(text: str, needles: list[tuple[str, tuple]]) -> list[tuple[int, int, tuple]]:
    taken: list[tuple[int, int]] = []
    hits: list[tuple[int, int, tuple]] = []
    for needle, payload in needles:
        if not needle or needle in _SKIP_ALONE or len(needle) < 2:
            continue
        start = 0
        while True:
            i = text.find(needle, start)
            if i < 0:
                break
            j = i + len(needle)
            if any(i < b and j > a for a, b in taken):
                start = i + 1
                continue
            taken.append((i, j))
            hits.append((i, j, payload))
            start = j
    hits.sort(key=lambda h: h[0])
    return hits


def _corrections(text: str) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for rx in (_RU_CORR, _JA_CORR):
        for m in rx.finditer(text):
            wrong, right = m.group(1), m.group(2)
            if not right or right == wrong or _leaks(wrong, right):
                continue
            if right in seen:
                continue
            seen.add(right)
            items.append(
                {
                    "prompt_ja": wrong,
                    "prompt_hint": "как поправил учитель",
                    "expected": right,
                    "gloss_ru": f"не {wrong}",
                    "provenance": "model",
                    "tags": "transcript correction",
                    "_at": m.start(),
                }
            )
    return items


def _reason_hits(text: str) -> list[dict]:
    items: list[dict] = []
    for adj in _I_ADJ:
        for particle, hint in (("ので", "причина ので"), ("から", "причина から")):
            surface = adj + particle
            at = text.find(surface)
            if at < 0:
                continue
            items.append(
                {
                    "prompt_ja": adj,
                    "prompt_hint": hint,
                    "expected": surface,
                    "gloss_ru": f"{adj} → {surface}",
                    "provenance": "model",
                    "tags": "transcript reason",
                    "_at": at,
                }
            )
    return items


def proposals_from_text(text: str) -> list[dict]:
    """Forms attested in this text. Provenance is model. Not claims until accept."""
    raw = text or ""
    if not raw.strip():
        return []
    ranked: list[dict] = []
    ranked.extend(_corrections(raw))
    ranked.extend(_reason_hits(raw))

    needles = [
        (surface, (base, hint, gloss, surface))
        for surface, base, hint, gloss in _VERB_FORMS
    ]
    for start, _end, payload in _take_spans(raw, needles):
        base, hint, gloss, surface = payload
        if _leaks(base, surface):
            continue
        ranked.append(
            {
                "prompt_ja": base,
                "prompt_hint": hint,
                "expected": surface,
                "gloss_ru": gloss,
                "provenance": "model",
                "tags": "transcript",
                "_at": start,
            }
        )

    leftover = [
        (head, (_prompt_for(head), _hint_for(head, _GLOSS.get(head, "")), _GLOSS.get(head, ""), head))
        for head in _HEADS
        if head not in _SKIP_ALONE and len(head) >= 2 and _prompt_for(head) != head
    ]
    for start, _end, payload in _take_spans(raw, leftover):
        prompt_ja, hint, gloss, head = payload
        if _leaks(prompt_ja, head):
            continue
        ranked.append(
            {
                "prompt_ja": prompt_ja,
                "prompt_hint": hint,
                "expected": head,
                "gloss_ru": gloss,
                "provenance": "model",
                "tags": "transcript",
                "_at": start,
            }
        )

    ranked.sort(key=lambda r: (0 if "correction" in r["tags"] else 1, r.get("_at", 0)))
    items: list[dict] = []
    seen: set[str] = set()
    for row in ranked:
        key = row["expected"]
        if key in seen or any(key in prev or prev in key for prev in seen):
            continue
        seen.add(key)
        items.append({k: v for k, v in row.items() if not k.startswith("_")})
        if len(items) >= FILL_CAP:
            break
    return items


def neighbor_gap_items(text: str) -> list[dict]:
    """Neighbors of this lesson's tags. Still not claims until accept."""
    tags = set(attested_tags(text))
    if not tags:
        return []
    props = proposals_from_text(text)
    attested = {h for h in _HEADS if h in (text or "")}
    attested.update(p["expected"] for p in props)
    attested.update(p["prompt_ja"] for p in props)
    out = []
    for item in curriculum.GAPS:
        if item.get("tags") not in tags:
            continue
        if item["expected"] in attested or item["prompt_ja"] in attested:
            continue
        if _leaks(item["prompt_ja"], item["expected"]):
            continue
        out.append(item)
    return out[:5]
