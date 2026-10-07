from __future__ import annotations

import json
from pathlib import Path

from proba import jlpt

# Kanji card: radical, readings, RU glosses, compounds from the drawer.

_GLOSS_PATH = Path(__file__).with_name("kanji_ru.json")
_PACKED_GLOSS: dict[str, str] | None = None

_RADICAL_RU = {
    "一": ("一", "один"),
    "乙": ("乙", "крючок"),
    "人": ("人", "человек"),
    "亻": ("人", "человек"),
    "口": ("口", "рот"),
    "日": ("日", "солнце / день"),
    "月": ("月", "луна / мясо"),
    "木": ("木", "дерево"),
    "氵": ("水", "вода"),
    "水": ("水", "вода"),
    "火": ("火", "огонь"),
    "土": ("土", "земля"),
    "金": ("金", "металл"),
    "言": ("言", "речь"),
    "心": ("心", "сердце"),
    "忄": ("心", "сердце"),
    "手": ("手", "рука"),
    "扌": ("手", "рука"),
    "糸": ("糸", "нить"),
    "食": ("食", "еда"),
    "車": ("車", "повозка"),
    "門": ("門", "ворота"),
    "雨": ("雨", "дождь"),
    "女": ("女", "женщина"),
    "子": ("子", "ребёнок"),
    "山": ("山", "гора"),
    "川": ("川", "река"),
    "田": ("田", "поле"),
    "目": ("目", "глаз"),
    "耳": ("耳", "ухо"),
    "足": ("足", "нога"),
    "貝": ("貝", "раковина"),
    "鳥": ("鳥", "птица"),
    "魚": ("魚", "рыба"),
    "言": ("言", "речь"),
    "吾": ("吾", "я"),
    "辶": ("辶", "ходить"),
    "⻌": ("辶", "ходить"),
    "宀": ("宀", "крыша"),
    "广": ("广", "навес"),
    "⻏": ("邑", "селение"),
    "阝": ("阜", "холм / селение"),
    "犭": ("犬", "собака"),
    "忄": ("心", "сердце"),
    "扌": ("手", "рука"),
    "氵": ("水", "вода"),
    "亻": ("人", "человек"),
    "彳": ("彳", "шаг"),
    "⺮": ("竹", "бамбук"),
    "竹": ("竹", "бамбук"),
    "艹": ("艸", "трава"),
    "艸": ("艸", "трава"),
    "礻": ("示", "алтарь"),
    "衤": ("衣", "одежда"),
    "衣": ("衣", "одежда"),
    "示": ("示", "показывать"),
    "王": ("玉", "яшма"),
    "玉": ("玉", "яшма"),
    "石": ("石", "камень"),
    "田": ("田", "поле"),
    "力": ("力", "сила"),
    "又": ("又", "снова / рука"),
    "夕": ("夕", "вечер"),
    "土": ("土", "земля"),
    "大": ("大", "большой"),
    "小": ("小", "маленький"),
    "工": ("工", "мастерство"),
    "弓": ("弓", "лук"),
    "巾": ("巾", "полотно"),
    "山": ("山", "гора"),
    "干": ("干", "щит"),
    "幺": ("幺", "нить"),
    "广": ("广", "навес"),
    "廴": ("廴", "длинный шаг"),
    "廾": ("廾", "две руки"),
    "弋": ("弋", "копьё"),
    "弓": ("弓", "лук"),
    "彡": ("彡", "щетина"),
    "彳": ("彳", "шаг"),
    "心": ("心", "сердце"),
    "戈": ("戈", "алебарда"),
    "戸": ("戸", "дверь"),
    "手": ("手", "рука"),
    "支": ("支", "ветвь"),
    "文": ("文", "письмо"),
    "斗": ("斗", "мера"),
    "斤": ("斤", "топор"),
    "方": ("方", "сторона"),
    "无": ("无", "нет"),
    "日": ("日", "солнце / день"),
    "曰": ("曰", "сказать"),
    "月": ("月", "луна / мясо"),
    "木": ("木", "дерево"),
    "欠": ("欠", "нехватка"),
    "止": ("止", "остановка"),
    "歹": ("歹", "смерть"),
    "殳": ("殳", "алебарда"),
    "毋": ("毋", "не"),
    "比": ("比", "сравнение"),
    "毛": ("毛", "волос"),
    "氏": ("氏", "род"),
    "气": ("气", "пар"),
    "水": ("水", "вода"),
    "火": ("火", "огонь"),
    "爪": ("爪", "коготь"),
    "父": ("父", "отец"),
    "爻": ("爻", "черты"),
    "爿": ("爿", "доска"),
    "片": ("片", "кусок"),
    "牙": ("牙", "клык"),
    "牛": ("牛", "корова"),
    "犬": ("犬", "собака"),
    "玄": ("玄", "тёмный"),
    "玉": ("玉", "яшма"),
    "瓜": ("瓜", "тыква"),
    "瓦": ("瓦", "черепица"),
    "甘": ("甘", "сладкий"),
    "生": ("生", "жизнь"),
    "用": ("用", "применение"),
    "田": ("田", "поле"),
    "疋": ("疋", "рулон"),
    "疒": ("疒", "болезнь"),
    "癶": ("癶", "ноги врозь"),
    "白": ("白", "белый"),
    "皮": ("皮", "кожа"),
    "皿": ("皿", "посуда"),
    "目": ("目", "глаз"),
    "矛": ("矛", "копьё"),
    "矢": ("矢", "стрела"),
    "石": ("石", "камень"),
    "示": ("示", "алтарь"),
    "禸": ("禸", "след"),
    "禾": ("禾", "злак"),
    "穴": ("穴", "дыра"),
    "立": ("立", "стоять"),
    "竹": ("竹", "бамбук"),
    "米": ("米", "рис"),
    "糸": ("糸", "нить"),
    "缶": ("缶", "сосуд"),
    "网": ("网", "сеть"),
    "羊": ("羊", "овца"),
    "羽": ("羽", "перо"),
    "老": ("老", "старый"),
    "而": ("而", "и"),
    "耒": ("耒", "плуг"),
    "耳": ("耳", "ухо"),
    "聿": ("聿", "кисть"),
    "肉": ("肉", "мясо"),
    "臣": ("臣", "вассал"),
    "自": ("自", "сам"),
    "至": ("至", "достигать"),
    "臼": ("臼", "ступа"),
    "舌": ("舌", "язык"),
    "舛": ("舛", "ошибка"),
    "舟": ("舟", "лодка"),
    "艮": ("艮", "предел"),
    "色": ("色", "цвет"),
    "艸": ("艸", "трава"),
    "虍": ("虍", "тигр"),
    "虫": ("虫", "насекомое"),
    "血": ("血", "кровь"),
    "行": ("行", "идти"),
    "衣": ("衣", "одежда"),
    "襾": ("襾", "покрывать"),
    "見": ("見", "видеть"),
    "角": ("角", "угол / рог"),
    "言": ("言", "речь"),
    "谷": ("谷", "долина"),
    "豆": ("豆", "боб"),
    "豕": ("豕", "свинья"),
    "豸": ("豸", "зверь"),
    "貝": ("貝", "раковина"),
    "赤": ("赤", "красный"),
    "走": ("走", "бежать"),
    "足": ("足", "нога"),
    "身": ("身", "тело"),
    "車": ("車", "повозка"),
    "辛": ("辛", "острый"),
    "辰": ("辰", "дракон"),
    "辵": ("辵", "ходить"),
    "邑": ("邑", "селение"),
    "酉": ("酉", "вино"),
    "釆": ("釆", "различать"),
    "里": ("里", "деревня"),
    "金": ("金", "металл"),
    "長": ("長", "длинный"),
    "門": ("門", "ворота"),
    "阜": ("阜", "холм"),
    "隶": ("隶", "достигать"),
    "隹": ("隹", "птица"),
    "雨": ("雨", "дождь"),
    "青": ("青", "синий / зелёный"),
    "非": ("非", "не"),
    "面": ("面", "лицо"),
    "革": ("革", "кожа"),
    "韋": ("韋", "выделанная кожа"),
    "音": ("音", "звук"),
    "頁": ("頁", "страница / голова"),
    "風": ("風", "ветер"),
    "飛": ("飛", "лететь"),
    "食": ("食", "еда"),
    "首": ("首", "шея"),
    "香": ("香", "аромат"),
    "馬": ("馬", "лошадь"),
    "骨": ("骨", "кость"),
    "高": ("高", "высокий"),
    "髟": ("髟", "волосы"),
    "鬥": ("鬥", "бой"),
    "鬯": ("鬯", "жертвенное вино"),
    "鬲": ("鬲", "котёл"),
    "鬼": ("鬼", "дух"),
    "魚": ("魚", "рыба"),
    "鳥": ("鳥", "птица"),
    "鹵": ("鹵", "соль"),
    "鹿": ("鹿", "олень"),
    "麥": ("麥", "пшеница"),
    "麻": ("麻", "конопля"),
    "黃": ("黃", "жёлтый"),
    "黍": ("黍", "просо"),
    "黑": ("黑", "чёрный"),
    "黹": ("黹", "шитьё"),
    "黽": ("黽", "лягушка"),
    "鼎": ("鼎", "треножник"),
    "鼓": ("鼓", "барабан"),
    "鼠": ("鼠", "мышь"),
    "鼻": ("鼻", "нос"),
    "齊": ("齊", "ровный"),
    "齒": ("齒", "зуб"),
    "龍": ("龍", "дракон"),
    "龜": ("龜", "черепаха"),
    "龠": ("龠", "флейта"),
}

# First-guess radical for frequent N5 signs.
_CHAR_RADICAL = {
    "一": "一",
    "二": "一",
    "三": "一",
    "人": "人",
    "休": "人",
    "何": "人",
    "体": "人",
    "口": "口",
    "名": "口",
    "右": "口",
    "日": "日",
    "時": "日",
    "明": "日",
    "月": "月",
    "木": "木",
    "校": "木",
    "林": "木",
    "森": "木",
    "水": "水",
    "海": "水",
    "火": "火",
    "金": "金",
    "言": "言",
    "話": "言",
    "語": "言",
    "読": "言",
    "心": "心",
    "思": "心",
    "手": "手",
    "持": "手",
    "食": "食",
    "飲": "食",
    "車": "車",
    "駅": "車",
    "門": "門",
    "間": "門",
    "雨": "雨",
    "電": "雨",
    "女": "女",
    "子": "子",
    "学": "子",
    "山": "山",
    "川": "川",
    "田": "田",
    "男": "田",
    "目": "目",
    "見": "見",
    "耳": "耳",
    "聞": "耳",
    "足": "足",
    "走": "走",
    "行": "行",
    "来": "人",
    "本": "木",
    "東": "木",
    "書": "日",
    "生": "生",
    "先": "儿",
    "今": "人",
    "友": "又",
    "母": "毋",
    "父": "父",
    "国": "囗",
    "円": "冂",
    "出": "凵",
    "入": "入",
    "大": "大",
    "小": "小",
    "中": "｜",
    "上": "一",
    "下": "一",
    "左": "工",
    "年": "干",
    "午": "十",
}

_KANJI_RU = {
    "人": "человек",
    "日": "день, солнце",
    "月": "месяц, луна",
    "本": "книга; корень",
    "行": "идти, строка",
    "来": "приходить",
    "見": "видеть",
    "食": "есть",
    "飲": "пить",
    "読": "читать",
    "書": "писать",
    "話": "говорить",
    "語": "язык, слово",
    "学": "учёба",
    "校": "школа",
    "先": "впереди, преподаватель (先生)",
    "生": "жизнь, ученик",
    "時": "время, час",
    "間": "промежуток",
    "車": "машина",
    "駅": "станция",
    "電": "электричество",
    "水": "вода",
    "火": "огонь",
    "金": "золото, деньги, пятница",
    "土": "земля, суббота",
    "木": "дерево, четверг",
    "山": "гора",
    "川": "река",
    "口": "рот",
    "目": "глаз",
    "耳": "ухо",
    "手": "рука",
    "足": "нога",
    "友": "друг",
    "母": "мать",
    "父": "отец",
    "男": "мужчина",
    "女": "женщина",
    "子": "ребёнок",
    "国": "страна",
    "円": "иена, круг",
    "今": "сейчас",
    "何": "что",
    "名": "имя",
    "休": "отдых",
    "入": "входить",
    "出": "выходить",
    "上": "верх",
    "下": "низ",
    "中": "середина",
    "大": "большой",
    "小": "маленький",
    "年": "год",
    "一": "один",
    "乙": "крючок",
    "七": "семь",
    "万": "десять тысяч",
    "三": "три",
    "九": "девять",
    "二": "два",
    "五": "пять",
    "八": "восемь",
    "六": "шесть",
    "前": "перед",
    "北": "север",
    "十": "десять",
    "千": "тысяча",
    "午": "полдень",
    "半": "половина",
    "南": "юг",
    "右": "право",
    "四": "четыре",
    "外": "снаружи",
    "天": "небо",
    "左": "лево",
    "後": "после, сзади",
    "東": "восток",
    "毎": "каждый",
    "気": "дух, настроение",
    "白": "белый",
    "百": "сто",
    "聞": "слышать, спрашивать",
    "西": "запад",
    "長": "длинный",
    "雨": "дождь",
    "高": "высокий",
}


def reset_gloss() -> None:
    global _PACKED_GLOSS
    _PACKED_GLOSS = None


def _split_ru(text: str) -> list[str]:
    out: list[str] = []
    for chunk in (text or "").replace(";", "·").replace("；", "·").split("·"):
        for bit in chunk.split(","):
            p = bit.strip()
            if p and p not in out:
                out.append(p)
    return out


def _packed_gloss(ch: str) -> str:
    global _PACKED_GLOSS
    if _PACKED_GLOSS is None:
        blob: dict = {}
        if _GLOSS_PATH.is_file():
            raw = json.loads(_GLOSS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                blob = raw.get("kanji") if isinstance(raw.get("kanji"), dict) else raw
        _PACKED_GLOSS = {str(k): str(v) for k, v in (blob or {}).items() if v}
    return (_PACKED_GLOSS.get(ch) or "").strip()


def _kanji_gloss(ch: str) -> str:
    parts = _split_ru(_packed_gloss(ch))
    fallback = _KANJI_RU.get(ch) or ""
    if not fallback and ch in _RADICAL_RU:
        fallback = _RADICAL_RU[ch][1]
    for p in _split_ru(fallback):
        if p not in parts:
            parts.append(p)
    return " · ".join(parts[:6])


def _bank_entry(ch: str) -> dict | None:
    for _lv, items in jlpt._kanji_bank().items():
        for item in items:
            if item.get("c") == ch:
                return item
    return None


def radical_of(ch: str) -> tuple[str, str]:
    from proba import strokes

    packed = strokes.packed_radical(ch)
    rad = packed or _CHAR_RADICAL.get(ch) or ch
    name = _RADICAL_RU.get(rad) or _RADICAL_RU.get(ch)
    if name:
        return name
    return rad, _KANJI_RU.get(rad) or ""


def element_label(element: str, original: str = "") -> tuple[str, str]:
    key = (original or element or "").strip()
    el = (element or "").strip()
    if el in _RADICAL_RU:
        return _RADICAL_RU[el]
    if key in _RADICAL_RU:
        return _RADICAL_RU[key]
    ru = _KANJI_RU.get(key) or _KANJI_RU.get(el) or ""
    return key or el, ru


def compounds_for(ch: str, lexicon: list[tuple[str, str, str]], limit: int = 16) -> list[dict]:
    hits = []
    for head, kana, gloss in lexicon:
        if ch in head and head != ch:
            hits.append({"head": head, "kana": kana, "gloss_ru": gloss})
        if len(hits) >= limit:
            break
    return hits


def lookup_radical(query: str, lexicon: list[tuple[str, str, str]], limit: int = 12) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    want = set()
    for rad, (canon, ru) in _RADICAL_RU.items():
        if q == rad or q == canon or q in ru:
            want.add(rad)
            want.add(canon)
    if not want:
        return []
    hits = []
    seen: set[str] = set()
    for ch, rad in _CHAR_RADICAL.items():
        if rad not in want and ch not in want:
            continue
        if ch in seen:
            continue
        seen.add(ch)
        card = kanji_card(ch, lexicon)
        if card:
            hits.append(card)
        if len(hits) >= limit:
            break
    return hits


def kanji_card(ch: str, lexicon: list[tuple[str, str, str]]) -> dict | None:
    if len(ch) != 1:
        return None
    from proba import strokes

    entry = _bank_entry(ch)
    if (
        not entry
        and ch not in _KANJI_RU
        and ch not in _CHAR_RADICAL
        and ch not in _RADICAL_RU
        and not strokes.paths_for(ch)
        and not strokes.packed_radical(ch)
    ):
        return None
    rad, rad_ru = radical_of(ch)
    gloss = _kanji_gloss(ch)
    return {
        "kind": "kanji",
        "head": ch,
        "kana": (entry or {}).get("kun") or "",
        "on": (entry or {}).get("on") or "",
        "kun": (entry or {}).get("kun") or "",
        "gloss_ru": gloss,
        "gloss_en": (entry or {}).get("m") or "",
        "radical": rad,
        "radical_ru": rad_ru,
        "compounds": compounds_for(ch, lexicon),
        "in_bank": bool(entry),
    }


def _slim_card(ch: str, lexicon: list[tuple[str, str, str]]) -> dict | None:
    card = kanji_card(ch, lexicon)
    if not card:
        return None
    return {
        "kind": "kanji",
        "head": card["head"],
        "on": card["on"],
        "kun": card["kun"],
        "gloss_ru": card["gloss_ru"],
        "gloss_en": card["gloss_en"],
        "radical": card["radical"],
        "radical_ru": card["radical_ru"],
    }


def _key_want(query: str) -> set[str]:
    q = (query or "").strip()
    if not q:
        return set()
    glyph, _ru = element_label(q, "")
    want = {q, glyph}
    for key in list(want):
        if key in _RADICAL_RU:
            want.add(_RADICAL_RU[key][0])
            want.add(key)
    return {x for x in want if x}


def uses_key(ch: str, want: set[str]) -> bool:
    from proba import strokes

    if not ch or not want:
        return False
    packed = strokes.packed_radical(ch) or _CHAR_RADICAL.get(ch) or ""
    if packed in want or ch in want:
        return True
    for part in strokes.parts_for(ch):
        if (part.get("element") or "") in want or (part.get("original") or "") in want:
            return True
    return False


def siblings_for(ch: str, lexicon: list[tuple[str, str, str]], limit: int = 16) -> list[dict]:
    from proba import strokes

    rad, _ru = radical_of(ch)
    want = _key_want(rad) | {ch}
    packed = strokes.packed_radical(ch)
    if packed:
        want |= _key_want(packed)
    hits: list[dict] = []
    seen: set[str] = set()
    for lv in jlpt.LEVELS:
        for item in jlpt._kanji_bank().get(lv) or []:
            other = item.get("c") or ""
            if not other or other == ch or other in seen:
                continue
            other_rad = strokes.packed_radical(other) or _CHAR_RADICAL.get(other) or ""
            if other_rad not in want and other not in want:
                continue
            slim = _slim_card(other, lexicon)
            if not slim:
                continue
            seen.add(other)
            hits.append(slim)
            if len(hits) >= limit:
                return hits
    return hits


def kanji_page(ch: str, lexicon: list[tuple[str, str, str]]) -> dict | None:
    from proba import strokes

    raw = (ch or "").strip()
    ch = raw[0] if raw else ""
    card = kanji_card(ch, lexicon)
    if not card:
        return None
    parts = []
    for part in strokes.parts_for(ch):
        show, ru = element_label(part.get("element") or "", part.get("original") or "")
        parts.append(
            {
                "element": part.get("element") or "",
                "original": part.get("original") or "",
                "glyph": show,
                "ru": ru,
                "i": part.get("i") or [],
                "paths": part.get("paths") or [],
            }
        )
    return {
        **card,
        "parts": parts,
        "siblings": siblings_for(ch, lexicon),
        "paths": strokes.paths_for(ch),
    }


def radical_page(query: str, lexicon: list[tuple[str, str, str]], limit: int = 24) -> dict | None:
    from proba import strokes

    q = (query or "").strip()
    if not q:
        return None
    glyph, ru = element_label(q, "")
    if q in _RADICAL_RU:
        glyph, ru = _RADICAL_RU[q]
    want = _key_want(q)
    kanji = []
    seen: set[str] = set()
    for lv in jlpt.LEVELS:
        for item in jlpt._kanji_bank().get(lv) or []:
            other = item.get("c") or ""
            if not other or other in seen:
                continue
            if not uses_key(other, want):
                continue
            slim = _slim_card(other, lexicon)
            if not slim:
                continue
            seen.add(other)
            kanji.append(slim)
            if len(kanji) >= limit:
                break
        if len(kanji) >= limit:
            break
    if not kanji and not ru:
        return None
    return {
        "kind": "radical",
        "head": glyph,
        "query": q,
        "gloss_ru": ru,
        "kanji": kanji,
        "paths": strokes.paths_for(glyph) or strokes.paths_for(q),
    }
