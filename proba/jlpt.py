from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from proba import db, paths

LEVELS = ("N5", "N4", "N3", "N2", "N1")
_KANJI_RE = re.compile(r"[\u4e00-\u9fff]")

# Grammar outline. Not inserted as claims.
TOPICS: dict[str, list[dict]] = {
    "N5": [
        {"id": "n5-desu", "title": "です / ます", "blurb": "Вежливое настоящее.", "tag": "polite"},
        {"id": "n5-wa-ga", "title": "は / が / を", "blurb": "Тема, новое подлежащее, дополнение.", "tag": "particle"},
        {"id": "n5-ni-de", "title": "に / で / へ", "blurb": "Место, средство, направление.", "tag": "particle"},
        {"id": "n5-kore", "title": "これ / それ / あれ", "blurb": "Указание по дистанции.", "tag": "deictic"},
        {"id": "n5-adj", "title": "い- и な-прилагательные", "blurb": "Склонение и связка.", "tag": "adj"},
        {"id": "n5-te", "title": "て-форма", "blurb": "Просьба, последовательность, соединение.", "tag": "te-form"},
        {"id": "n5-nai", "title": "ない-форма", "blurb": "Отрицание словарного глагола.", "tag": "nai"},
        {"id": "n5-ta", "title": "た-форма", "blurb": "Прошедшее простое.", "tag": "ta"},
        {"id": "n5-tai", "title": "たい", "blurb": "Хотение после глагола.", "tag": "tai"},
        {"id": "n5-teiru", "title": "ている", "blurb": "Процесс или результат.", "tag": "teiru"},
        {"id": "n5-aru", "title": "ある / いる", "blurb": "Бытие: вещи и люди.", "tag": "exist"},
        {"id": "n5-kara", "title": "から", "blurb": "Причина или исходная точка.", "tag": "reason"},
        {"id": "n5-mou", "title": "もう / まだ", "blurb": "Уже и ещё / ещё не.", "tag": "mou"},
        {"id": "n5-counter", "title": "Счётные суффиксы", "blurb": "本, 冊 и другие.", "tag": "counter"},
        {"id": "n5-kudasai", "title": "ください / ましょう", "blurb": "Просьба и предложение сделать вместе.", "tag": "request"},
    ],
    "N4": [
        {"id": "n4-pot", "title": "Потенциал", "blurb": "Мочь сделать. Не путать с словарным る.", "tag": "potential"},
        {"id": "n4-give", "title": "あげる / くれる / もらう", "blurb": "Направление давания.", "tag": "give"},
        {"id": "n4-tara", "title": "たら / と / ば", "blurb": "Условия: たら / と / ば.", "tag": "cond"},
        {"id": "n4-nagara", "title": "ながら", "blurb": "Два действия сразу.", "tag": "nagara"},
        {"id": "n4-te-aux", "title": "てしまう / ておく / てみる", "blurb": "Вспомогательные на て.", "tag": "te-aux"},
        {"id": "n4-nakereba", "title": "なければならない", "blurb": "Надо. Есть более короткие разговорные.", "tag": "must"},
        {"id": "n4-sou", "title": "そうだ", "blurb": "Вид vs пересказ — разные конструкции.", "tag": "sou"},
        {"id": "n4-you", "title": "ようだ / らしい", "blurb": "Впечатление и «слышно, что».", "tag": "you"},
        {"id": "n4-noni", "title": "のに", "blurb": "Вопреки ожиданию.", "tag": "noni"},
        {"id": "n4-tsumori", "title": "つもり / はず", "blurb": "Намерение и ожидание.", "tag": "intent"},
        {"id": "n4-naru", "title": "なる / する с прилагательными", "blurb": "Становиться и делать каким.", "tag": "naru"},
    ],
    "N3": [
        {"id": "n3-baai", "title": "場合 / とき", "blurb": "Случай и момент.", "tag": "baai"},
        {"id": "n3-tame", "title": "ために / ように", "blurb": "Цель. Глагол потенциала часто с ように.", "tag": "purpose"},
        {"id": "n3-koto", "title": "こと / もの / の", "blurb": "Номинализация. Не три синонима.", "tag": "nominal"},
        {"id": "n3-passive", "title": "Страдательный залог", "blurb": "Прямой и «пострадавший».", "tag": "passive"},
        {"id": "n3-caus", "title": "Каузатив", "blurb": "Заставить / позволить.", "tag": "causative"},
        {"id": "n3-tokoro", "title": "ところ / ばかり", "blurb": "Только что, как раз, сплошь.", "tag": "tokoro"},
        {"id": "n3-wake", "title": "わけ / はず / べき", "blurb": "Следствие, ожидание, долг.", "tag": "wake"},
        {"id": "n3-keigo-lite", "title": "Вежливость: お/ご, ください", "blurb": "お/ご и ください.", "tag": "keigo"},
    ],
    "N2": [
        {"id": "n2-keigo", "title": "尊敬語 / 謙譲語", "blurb": "尊敬語 и 謙譲語.", "tag": "keigo"},
        {"id": "n2-nuanced", "title": "ものだ / ことだ / わけだ", "blurb": "Нюансы номинализаторов.", "tag": "mono"},
        {"id": "n2-contra", "title": "つつ / ながらも / ものの", "blurb": "Уступка.", "tag": "concession"},
        {"id": "n2-aspect", "title": "かける / 切る / 出す", "blurb": "Аспектные глаголы.", "tag": "aspect"},
        {"id": "n2-written", "title": "Письменные связки", "blurb": "により, について, に関して.", "tag": "written"},
        {"id": "n2-hearsay", "title": "ということだ / そうだ", "blurb": "Пересказ.", "tag": "hearsay"},
    ],
    "N1": [
        {"id": "n1-formal", "title": "Формальная грамматика", "blurb": "にひきかえ, をもって и соседние.", "tag": "formal"},
        {"id": "n1-invert", "title": "Инверсия и эмфаза", "blurb": "からして, ですら, すら.", "tag": "emphasis"},
        {"id": "n1-written", "title": "Газетный стиль", "blurb": "Сжатые связки и канго.", "tag": "news"},
        {"id": "n1-nuance", "title": "Тонкие различия", "blurb": "Близкие формы, разные роли.", "tag": "nuance"},
    ],
}


def _topic(tid: str, title: str, blurb: str, tag: str = "") -> dict:
    return {"id": tid, "title": title, "blurb": blurb, "tag": tag}


_KIKITORI = [
    "もしもし",
    "旗のデザイン",
    "海からの便り",
    "カラスのカー子ちゃん",
    "たためるピアノ",
    "日本人と果物",
    "待つ時間・待たせる時間",
    "震度３",
    "世界の人口",
    "牛丼の作り方",
    "ドライアイ",
    "日本の地方都市",
    "横断歩道",
    "弁当の日",
    "コンビニ図書館",
    "右回りの時計",
    "目にやさしい色",
    "上手に泣いて、ストレス解消",
    "阿波踊り",
    "富士山が見えるところ",
    "アニメ文化の輸出",
    "十二支の話",
    "東京を回る山手線",
    "どんな結婚披露宴がいい？",
    "通話をやめた若者",
    "いただきます",
    "川を渡る",
    "車は左、人は右？",
    "千羽鶴",
    "合格は誰のおかげ？",
    "時差ぼけ",
    "小判がこわい",
    "道路からメロディー",
    "カラオケ発明者にノーベル賞？",
    "砂糖の消費量",
    "盆栽",
    "駅伝",
    "波力発電",
    "河童",
    "「もったいない」を国際語に！",
    "思いがけない援助",
    "新幹線の顔",
    "ビルの地下の野菜畑",
    "イルカは頭がいい？",
    "留学生文学賞",
    "菜の花プロジェクト",
    "今日は何色のスーツですか",
    "缶コーヒーの値段",
    "あがらないためには",
    "国際宇宙ステーション",
]

_KAIWA = [
    ("k0-1", "予備 · 音や形の変化", "話しことば: 縮約."),
    ("k0-2", "予備 · 男ことばと女ことば", "男ことば и 女ことば."),
    ("k1-1", "あいさつのあとは…？", "Продолжить разговор после приветствия."),
    ("k1-2", "新しいものを紹介したいときは…？", "Рассказать то, чего собеседник не знает."),
    ("k1-3", "体験をおもしろく話すには…？", "Порядок в рассказе о случае."),
    ("k1-4", "頼んだり、誘ったりするときは…？", "Просьба и приглашение по шагам."),
    ("k1-5", "言いにくい話のときは…？", "Начать неудобный разговор."),
    ("k2-6", "相手に安心して話してもらうには…？", "あいづち — слушать, не перебивать ключом."),
    ("k2-7", "相手の話に共感するときは…？", "Реакция, не перевод реплики."),
    ("k2-8", "相手の話に共感できないときは…？", "Несогласие без ссоры."),
    ("k2-9", "相手の話を広げるには…？", "Вопрос, который держит тему."),
    ("k2-10", "話がわからないときは…？", "Переспросить."),
    ("k3-11", "次の話題に移るときは…？", "Смена темы."),
    ("k3-12", "相手がつまらなそうなときは…？", "Сменить тему по реакции."),
    ("k3-13", "相手の話に興味がないときは…？", "Честно уйти с темы."),
    ("k4-14", "話を途中で終わらせるには…？", "Оборвать разговор."),
    ("k4-15", "電話を切りたいときは…？", "Завершить звонок по шагам."),
]

_POINTO20 = [
    ("p01", "1. いろいろな働きをする助詞", "助詞 с разными ролями."),
    ("p02", "2. 話題の取り立て", "Выделение темы."),
    ("p03", "3. 助詞の働きをする言葉 1", "Слова, которые работают как частицы."),
    ("p04", "4. 助詞の働きをする言葉 2", "Продолжение."),
    ("p05", "5. 助詞の働きをする言葉 3", "Продолжение."),
    ("p06", "6. 「こと」と「の」", "Номинализация. Не два синонима."),
    ("p07", "7. 複文の「は」と「が」・時制", "Сложное предложение: тема и время."),
    ("p08", "8. 名詞修飾", "Определение перед существительным."),
    ("p09", "9. 複文 — 時間", "Время в сложном предложении."),
    ("p10", "10. 仮定・逆接", "Если и вопреки."),
    ("p11", "11. 原因・理由・相関", "Причина и основание."),
    ("p12", "12. 否定の言い方", "Отрицание не только ない."),
    ("p13", "13. 感覚・強い気持ち・不可能", "Как сказать своё состояние."),
    ("p14", "14. 推量・願望・感嘆・提案", "Догадка, хотение, предложение."),
    ("p15", "15. 決まった使い方の副詞", "Наречия в устойчивых парах."),
    ("p16", "16. 接続の言葉", "Связки между фразами."),
    ("p17", "17. 語彙を広げる", "Расширение словаря."),
    ("p18", "18. 硬い文章", "Письменный регистр."),
    ("p19", "19. ていねいな言い方", "Вежливые формулировки."),
    ("p20", "20. 会話・文章のまとまり", "Целый разговор или абзац, не пункт списка."),
]

_PEA = [
    ("pea-body", "体と健康", "かぜをひく, 熱がある — пара, не перевод по словам."),
    ("pea-phone", "電話", "電話をかける / 出る / 切る."),
    ("pea-money", "お金", "お金を払う, 貯金する."),
    ("pea-study", "学習", "宿題を出す, 試験を受ける."),
    ("pea-traffic", "交通", "電車に乗る, 乗り換え."),
    ("pea-food", "食事", "ご飯を炊く, 箸を使う."),
    ("pea-home", "家", "鍵をかける, ごみを出す."),
    ("pea-work", "仕事", "会議をする, 残業する."),
    ("pea-weather", "天気・自然", "雨が降る, 風が吹く."),
    ("pea-feel", "気持ち", "安心する, 緊張する."),
    ("pea-time", "時間", "約束を守る, 時間に間に合う."),
    ("pea-clothes", "衣類", "服を着る, 靴を履く."),
]

_GIONGO = [
    ("gi-waku", "わくわく / どきどき", "Ожидание и сердце. Скажите в реплике, не список."),
    ("gi-ira", "いらいら / がっかり", "Раздражение и спад."),
    ("gi-pera", "ぺらぺら / すらすら", "Беглость речи или чтения."),
    ("gi-gaya", "がやがや / しん", "Шум и тишина."),
    ("gi-guzu", "ぐずぐず / さっさと", "Медлить и сделать сразу."),
    ("gi-piti", "ぴったり", "Точно подходит."),
    ("gi-niko", "にこにこ / にやにや", "Улыбка: открытая и кривая."),
    ("gi-hoka", "ほかほか / ひんやり", "Тёплое и прохладное."),
    ("gi-gan", "がんがん / ずきずき", "Боль: стучит или ноет."),
    ("gi-don", "どんどん", "Одно за другим. Не путать с だんだん."),
    ("gi-kira", "きらきら / ぴかぴか", "Блеск."),
    ("gi-beto", "べとべと / さらさら", "Липкое и сыпучее."),
]

# Old hashes ?b= still open a level, not a book shelf.
_BOOK_TO_LEVEL = {
    "manabou1": "N5",
    "manabou2": "N4",
    "pea": "N5",
    "giongo": "N4",
    "kaiwa": "N3",
    "pointo": "N3",
    "kikitori": "N3",
    "teksty": "N3",
    "kanji": "N5",
}

_N3_KEEP = {"n3-baai", "n3-tame", "n3-passive", "n3-caus", "n3-tokoro", "n3-wake"}

LEVEL_LEDE = {
    "N5": "学ぼう！にほんご 初級1 · ペアで覚えることば",
    "N4": "学ぼう！にほんご 初級2 · 擬音",
    "N3": "中級日本語文法 要点整理 ポイント20",
    "N2": "Неофициальный конспект N2",
    "N1": "Неофициальный конспект N1",
}


def _with_meta(topic: dict, *, kind: str = "grammar", from_book: str = "") -> dict:
    row = {**topic, "kind": kind}
    if from_book:
        row["from_book"] = from_book
    return row


def _level_topics(level: str) -> list[dict]:
    if level == "N5":
        rows = [_with_meta(t) for t in TOPICS["N5"]]
        rows.append(
            _with_meta(
                _topic(
                    "n5-collocation",
                    "連語",
                    "かぜをひく, ご飯を炊く, 鍵をかける, 電車に乗る — пара, не перевод по словам.",
                ),
                kind="vocab",
                from_book="ペアで覚えることば",
            )
        )
        return rows
    if level == "N4":
        rows = [_with_meta(t) for t in TOPICS["N4"]]
        pairs = " · ".join(title for _, title, _ in _GIONGO[:6])
        rows.append(
            _with_meta(
                _topic(
                    "n4-giongo",
                    "擬音語・擬態語",
                    f"{pairs} — в реплике.",
                ),
                kind="mimetics",
                from_book="擬音",
            )
        )
        return rows
    if level == "N3":
        rows = [_with_meta(t) for t in TOPICS["N3"] if t["id"] in _N3_KEEP]
        rows.extend(
            _with_meta(_topic(pid, title, blurb), from_book="ポイント20")
            for pid, title, blurb in _POINTO20
        )
        rows.append(
            _with_meta(
                _topic(
                    "n3-reading",
                    "説明・意見・体験",
                    "Коротко объяснить, сказать позицию, рассказать случай.",
                ),
                kind="reading",
            )
        )
        return rows
    if level == "N2":
        return [_with_meta(t) for t in TOPICS["N2"]]
    return [_with_meta(t) for t in TOPICS["N1"]]


def _resolve_level(level: str | None, book: str | None) -> str:
    raw_lv = (level or "").strip().upper()
    raw_book = (book or "").strip()
    if raw_lv in LEVELS:
        return raw_lv
    if raw_book in _BOOK_TO_LEVEL:
        mapped = _BOOK_TO_LEVEL[raw_book]
        return mapped if mapped in LEVELS else "N5"
    return "N5"


@lru_cache(maxsize=1)
def _kanji_bank() -> dict[str, list[dict]]:
    path = Path(__file__).resolve().parent / "jlpt_kanji.json"
    if not path.is_file():
        bundled = paths.bundle_root() / "proba" / "jlpt_kanji.json"
        path = bundled if bundled.is_file() else path
    if not path.is_file():
        return {level: [] for level in LEVELS}
    return json.loads(path.read_text(encoding="utf-8"))


def _chars_in_claims() -> set[str]:
    found: set[str] = set()
    rows = db.query(
        "SELECT prompt_ja, expected FROM claims WHERE status NOT IN ('rejected', 'proposed', 'diagnostic')"
    )
    for row in rows:
        blob = f"{row['prompt_ja'] or ''}{row['expected'] or ''}"
        found.update(_KANJI_RE.findall(blob))
    return found


_HINT = {
    "te-form": ("て-форма", "te-form"),
    "nai": ("ない", "най"),
    "tai": ("たい",),
    "teiru": ("ている", "процесс"),
    "give": ("くれる", "あげる", "もらう", "направление"),
    "reason": ("から", "ので", "причина"),
    "mou": ("もう", "まだ"),
    "potential": ("потенциал", "мочь"),
    "counter": ("счёт", "冊"),
}

# One shared tag on every slip would paint the whole book as “covered”.
_NO_OVERLAY_TAGS = frozenset({"mimetic", "kaiwa", "pointo", "kikitori", "collocation"})


def walk_topics():
    for lv in LEVELS:
        for topic in _level_topics(lv):
            yield lv, topic


def topic_hits(tag: str) -> list[dict]:
    return _topic_hits(tag)


def _topic_hits(tag: str) -> list[dict]:
    if not tag or tag in _NO_OVERLAY_TAGS:
        return []
    aliases = _HINT.get(tag, (tag,))
    rows = db.query(
        "SELECT id, prompt_ja, prompt_hint, status, tags FROM claims "
        "WHERE status NOT IN ('rejected', 'diagnostic', 'proposed', 'known') "
        "ORDER BY created_at"
    )
    hits = []
    for row in rows:
        tags = (row["tags"] or "").split()
        hint = row["prompt_hint"] or ""
        if tag not in tags and not any(a in hint for a in aliases):
            continue
        hits.append(
            {
                "id": row["id"],
                "prompt_ja": row["prompt_ja"],
                "prompt_hint": row["prompt_hint"],
                "status": row["status"],
            }
        )
        if len(hits) >= 8:
            break
    return hits


def catalog(level: str | None = None, book: str | None = None) -> dict:
    """Catalog for one JLPT level."""
    lv = _resolve_level(level, book)
    owned = _chars_in_claims()
    kanji = []
    for item in _kanji_bank().get(lv, []):
        ch = item.get("c") or ""
        kanji.append(
            {
                "c": ch,
                "m": item.get("m") or "",
                "on": item.get("on") or "",
                "kun": item.get("kun") or "",
                "in_claims": ch in owned,
            }
        )
    topics = []
    for topic in _level_topics(lv):
        topics.append({**topic, "hits": _topic_hits(topic.get("tag") or "")})
    return {
        "level": lv,
        "levels": list(LEVELS),
        "unofficial": True,
        "lede": LEVEL_LEDE[lv],
        "topics": topics,
        "kanji": kanji,
        "kanji_in_claims": sum(1 for k in kanji if k["in_claims"]),
    }
