from __future__ import annotations

import json
from pathlib import Path

from proba import yarxi

_PACKED_PATH = Path(__file__).with_name("compounds.json")
_COMPOUND_SHOW = 24
_PACKED_ROWS: list[tuple[str, str, str]] | None = None
_PACKED_BY_CHAR: dict[str, list[tuple[str, str, str]]] | None = None
_PACKED_BY_HEAD: dict[str, tuple[str, str, str]] | None = None

# Compact JP–RU drawer.

LEXICON = [
    ("行く", "いく", "идти, ехать"),
    ("行って", "いって", "て-форма 行く"),
    ("来る", "くる", "приходить"),
    ("来て", "きて", "て-форма 来る"),
    ("する", "する", "делать"),
    ("して", "して", "て-форма する"),
    ("見る", "みる", "смотреть, видеть"),
    ("見て", "みて", "те-форма 見る"),
    ("食べる", "たべる", "есть"),
    ("食べない", "たべない", "най-форма 食べる"),
    ("飲む", "のむ", "пить"),
    ("飲みたい", "のみたい", "хотеть пить"),
    ("読む", "よむ", "читать"),
    ("読める", "よめる", "мочь читать"),
    ("書く", "かく", "писать"),
    ("書ける", "かける", "мочь писать"),
    ("は", "は", "частица темы"),
    ("が", "が", "частица подлежащего / нового"),
    ("を", "を", "частица дополнения"),
    ("に", "に", "направление, время, адресат"),
    ("で", "で", "место действия, средство"),
    ("から", "から", "потому что / от"),
    ("ので", "ので", "потому что (мягче)"),
    ("もう", "もう", "уже"),
    ("まだ", "まだ", "ещё, ещё не"),
    ("くれる", "くれる", "давать (ко мне)"),
    ("あげる", "あげる", "давать (от меня)"),
    ("もらう", "もらう", "получать"),
    ("本", "ほん", "книга; счётчик длинных предметов"),
    ("冊", "さつ", "счётчик книг"),
    ("学生", "がくせい", "студент"),
    ("友達", "ともだち", "друг"),
    ("宿題", "しゅくだい", "домашнее задание"),
    ("水", "みず", "вода"),
    ("今日", "きょう", "сегодня"),
    ("今", "いま", "сейчас"),
    ("先生", "せんせい", "преподаватель"),
    ("日本語", "にほんご", "японский язык"),
    ("勉強", "べんきょう", "учёба"),
    ("分かる", "わかる", "понимать"),
    ("聞く", "きく", "слушать, спрашивать"),
    ("話す", "はなす", "говорить"),
    ("言う", "いう", "сказать"),
    ("思う", "おもう", "думать"),
    ("知る", "しる", "знать (факт)"),
    ("出来る", "できる", "мочь, быть сделанным"),
    ("いる", "いる", "быть (одушевл.)"),
    ("ある", "ある", "быть (неодушевл.)"),
    ("たい", "たい", "хотеть (после глагола)"),
    ("ている", "ている", "процесс / состояние"),
    ("ました", "ました", "прошедшее вежливое"),
    ("です", "です", "связка вежливая"),
    ("ください", "ください", "пожалуйста, дайте"),
    ("すみません", "すみません", "извините"),
    ("ありがとう", "ありがとう", "спасибо"),
    ("おはよう", "おはよう", "доброе утро"),
    ("こんにちは", "こんにちは", "здравствуйте (день)"),
    ("こんばんは", "こんばんは", "добрый вечер"),
    ("人", "ひと", "человек"),
    ("日本", "にほん", "Япония"),
    ("時間", "じかん", "время, час"),
    ("毎日", "まいにち", "каждый день"),
    ("少し", "すこし", "немного"),
    ("とても", "とても", "очень"),
    ("でも", "でも", "но"),
    ("そして", "そして", "и затем"),
    ("だから", "だから", "поэтому"),
    ("どうして", "どうして", "почему"),
    ("何", "なに", "что"),
    ("誰", "だれ", "кто"),
    ("どこ", "どこ", "где"),
    ("いつ", "いつ", "когда"),
    ("どう", "どう", "как"),
    ("これ", "これ", "это (рядом)"),
    ("それ", "それ", "то (у собеседника)"),
    ("あれ", "あれ", "то (далеко)"),
    ("私", "わたし", "я"),
    ("あなた", "あなた", "вы"),
    ("彼", "かれ", "он"),
    ("彼女", "かのじょ", "она"),
    ("学校", "がっこう", "школа"),
    ("家", "いえ", "дом"),
    ("駅", "えき", "станция"),
    ("電車", "でんしゃ", "электричка"),
    ("買う", "かう", "покупать"),
    ("待つ", "まつ", "ждать"),
    ("会う", "あう", "встречаться"),
    ("終わる", "おわる", "заканчиваться"),
    ("始める", "はじめる", "начинать"),
    ("教える", "おしえる", "учить (кого-то)"),
    ("習う", "ならう", "учиться (у кого-то)"),
    ("覚える", "おぼえる", "запоминать"),
    ("忘れる", "わすれる", "забывать"),
    ("難しい", "むずかしい", "трудный"),
    ("易しい", "やさしい", "лёгкий"),
    ("早い", "はやい", "ранний, быстрый"),
    ("遅い", "おそい", "поздний, медленный"),
    ("多い", "おおい", "многочисленный"),
    ("少ない", "すくない", "малочисленный"),
    ("熱", "ねつ", "жар"),
    ("電話", "でんわ", "телефон"),
    ("払う", "はらう", "платить"),
    ("乗る", "のる", "садиться (на транспорт)"),
    ("降りる", "おりる", "выходить (из транспорта)"),
    ("履く", "はく", "надевать (обувь, штаны)"),
    ("着る", "きる", "надевать (одежду)"),
    ("降る", "ふる", "идти (об осадках)"),
    ("吹く", "ふく", "дуть"),
    ("安心", "あんしん", "спокойствие"),
    ("緊張", "きんちょう", "напряжение"),
    ("約束", "やくそく", "обещание, договорённость"),
    ("会議", "かいぎ", "совещание"),
    ("残業", "ざんぎょう", "переработка"),
    ("休む", "やすむ", "отдыхать"),
    ("休み", "やすみ", "выходной, перерыв"),
    ("休日", "きゅうじつ", "выходной день"),
    ("中国", "ちゅうごく", "Китай"),
    ("日本人", "にほんじん", "японец"),
    ("入学", "にゅうがく", "поступление"),
    ("出口", "でぐち", "выход"),
    ("入口", "いりぐち", "вход"),
    ("上手", "じょうず", "умелый"),
    ("下手", "へた", "неумелый"),
]


def reset_packed() -> None:
    global _PACKED_ROWS, _PACKED_BY_CHAR, _PACKED_BY_HEAD
    _PACKED_ROWS = None
    _PACKED_BY_CHAR = None
    _PACKED_BY_HEAD = None
    yarxi.reset_gloss()


def _ensure_packed() -> None:
    global _PACKED_ROWS, _PACKED_BY_CHAR, _PACKED_BY_HEAD
    if _PACKED_ROWS is not None:
        return
    rows: list[tuple[str, str, str]] = []
    by_char: dict[str, list[tuple[str, str, str]]] = {}
    by_head: dict[str, tuple[str, str, str]] = {}
    if _PACKED_PATH.is_file():
        blob = json.loads(_PACKED_PATH.read_text(encoding="utf-8"))
        for item in blob.get("words") or []:
            if not isinstance(item, list) or len(item) < 3:
                continue
            head, kana, gloss = str(item[0]), str(item[1]), str(item[2])
            if not head or not kana:
                continue
            row = (head, kana, gloss)
            rows.append(row)
            by_head.setdefault(head, row)
            for ch in set(head):
                by_char.setdefault(ch, []).append(row)
    _PACKED_ROWS = rows
    _PACKED_BY_CHAR = by_char
    _PACKED_BY_HEAD = by_head


def packed_words() -> list[tuple[str, str, str]]:
    _ensure_packed()
    return list(_PACKED_ROWS or [])


def packed_row(query: str) -> tuple[str, str, str] | None:
    raw = (query or "").strip()
    if not raw:
        return None
    _ensure_packed()
    hit = (_PACKED_BY_HEAD or {}).get(raw)
    if hit:
        return hit
    for head, kana, gloss in _PACKED_ROWS or []:
        if kana == raw:
            return head, kana, gloss
    return None


def _merge_compounds(ch: str, lexicon_hits: list[dict]) -> tuple[list[dict], int]:
    seen = {item.get("head") for item in lexicon_hits}
    out = list(lexicon_hits)
    _ensure_packed()
    for head, kana, gloss in (_PACKED_BY_CHAR or {}).get(ch) or []:
        if head in seen:
            continue
        seen.add(head)
        out.append({"head": head, "kana": kana, "gloss_ru": gloss})
    return out[:_COMPOUND_SHOW], len(out)


def _with_compounds(card: dict) -> dict:
    shown, total = _merge_compounds(card.get("head") or "", card.get("compounds") or [])
    card["compounds"] = shown
    card["compounds_total"] = total
    card["compounds_more"] = max(0, total - len(shown))
    return card


def search(query: str, limit: int = 20, packed: bool = False) -> list[dict]:
    from proba.kana import romaji_to_hiragana

    raw = (query or "").strip()
    if not raw:
        return [
            {"kind": "word", "head": h, "kana": k, "gloss_ru": g}
            for h, k, g in LEXICON[:12]
        ]
    variants = {raw.lower(), raw}
    hira = romaji_to_hiragana(raw, commit=True)
    if hira:
        variants.add(hira)
        variants.add(hira.lower())
    hits: list[dict] = []
    if len(raw) == 1:
        card = yarxi.kanji_card(raw, LEXICON)
        if card:
            hits.append(_with_compounds(card))
    hits.extend(h for h in yarxi.lookup_radical(raw, LEXICON) if h["head"] not in {x.get("head") for x in hits})
    for head, kana, gloss in LEXICON:
        blob = f"{head}{kana}{gloss}".lower()
        if any(v in blob or v in head or v in kana or v in gloss.lower() for v in variants):
            hits.append({"kind": "word", "head": head, "kana": kana, "gloss_ru": gloss})
        if len(hits) >= limit:
            return hits
    if packed:
        seen = {h.get("head") for h in hits}
        _ensure_packed()
        for head, kana, gloss in _PACKED_ROWS or []:
            if head in seen:
                continue
            blob = f"{head}{kana}{gloss}".lower()
            if any(v in blob or v in head or v in kana or v in gloss.lower() for v in variants):
                seen.add(head)
                hits.append({"kind": "word", "head": head, "kana": kana, "gloss_ru": gloss})
            if len(hits) >= limit:
                break
        if len(hits) < limit:
            from proba import giongo

            for item in giongo.search(raw, limit=limit):
                if item.get("head") in seen or item.get("kana") in seen:
                    continue
                seen.add(item.get("head") or "")
                hits.append(item)
                if len(hits) >= limit:
                    break
    return hits


def gloss_for(surface: str) -> str:
    for head, kana, gloss in LEXICON:
        if surface == head or surface == kana:
            return gloss
    return ""


def kanji_page(ch: str) -> dict | None:
    page = yarxi.kanji_page((ch or "").strip(), LEXICON)
    if not page:
        return None
    return _with_compounds(page)


def radical_page(query: str) -> dict | None:
    return yarxi.radical_page((query or "").strip(), LEXICON)


def word_page(head: str) -> dict | None:
    from proba import extract
    from proba import giongo

    raw = (head or "").strip()
    if not raw:
        return None
    row = next(((h, k, g) for h, k, g in LEXICON if h == raw or k == raw), None)
    in_lexicon = row is not None
    mimetic = None
    if not row:
        row = packed_row(raw)
    if not row:
        mimetic = giongo.page(raw)
        if mimetic:
            return mimetic
    if not row:
        return None
    h, kana, gloss = row
    kanji = []
    seen: set[str] = set()
    for ch in h:
        if ch in seen:
            continue
        card = yarxi._slim_card(ch, LEXICON)
        if card:
            seen.add(ch)
            kanji.append(card)
    return {
        "kind": "word",
        "head": h,
        "kana": kana,
        "gloss_ru": gloss,
        "forms": extract.inflections_of(h) if in_lexicon else [],
        "kanji": kanji,
        "paradigm": "dictionary" if in_lexicon else "pack",
    }


def _touches_due(item: dict, expected: str) -> bool:
    exp = (expected or "").strip()
    if not exp:
        return False
    return item.get("head") == exp or item.get("surface") == exp or item.get("kana") == exp


def redact_due(payload: dict | list | None, expected: str | None):
    """Drop the tonight key from lookup. Does not mint or grade."""
    exp = (expected or "").strip()
    if not exp or payload is None:
        return payload
    if isinstance(payload, list):
        return [x for x in payload if not _touches_due(x, exp)]
    out = dict(payload)
    for key in ("forms", "compounds", "kanji", "siblings", "hits"):
        if isinstance(out.get(key), list):
            out[key] = [x for x in out[key] if not _touches_due(x, exp)]
    return out
