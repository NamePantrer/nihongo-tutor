from __future__ import annotations

from dataclasses import dataclass

# Production templates. origin=course: shelf key. origin=open: original example.


@dataclass(frozen=True)
class PackItem:
    topic_id: str
    prompt_ja: str
    prompt_hint: str
    expected: str
    gloss_ru: str
    tags: str
    pack: str
    origin: str  # course | open


def _c(
    topic_id: str,
    prompt_ja: str,
    prompt_hint: str,
    expected: str,
    gloss_ru: str,
    tags: str,
    pack: str,
) -> PackItem:
    return PackItem(
        topic_id, prompt_ja, prompt_hint, expected, gloss_ru, tags, pack, "course"
    )


def _o(
    topic_id: str,
    prompt_ja: str,
    prompt_hint: str,
    expected: str,
    gloss_ru: str,
    tags: str,
) -> PackItem:
    return PackItem(
        topic_id, prompt_ja, prompt_hint, expected, gloss_ru, tags, "open", "open"
    )


COURSE: tuple[PackItem, ...] = (
    _c("n5-desu", "学生", "на занятии представляетесь", "学生です", "Я / он студент.", "polite", "manabou"),
    _c("n5-te", "行く", "в кафе, уходите", "行って", "идти → 行って. Как на уроке 学ぼう.", "te-form", "manabou"),
    _c("n5-nai", "食べる", "в обед отказываетесь", "食べない", "не есть", "nai", "manabou"),
    _c("n5-ta", "行く", "вчера уже были там", "行った", "шёл / пошёл", "ta", "manabou"),
    _c("n5-tai", "飲む", "в жару хочется пить", "飲みたい", "хотеть пить", "tai", "manabou"),
    _c("n5-teiru", "食べる", "сейчас за столом", "食べている", "ест / в процессе", "teiru", "manabou"),
    _c("n5-aru", "本", "на полке, не про человека", "あります", "книга есть (здесь)", "exist", "manabou"),
    _c("n5-kara", "忙しい", "объясняете почему не придёте", "忙しいから", "потому что занят. На Zoom мог быть ので.", "reason", "manabou"),
    _c("n5-mou", "宿題", "уже сделал", "もう", "уже. Пара к まだ.", "mou", "manabou"),
    _c("n5-counter", "本", "считаете книги, не карандаши", "冊", "一冊. Не путать с 本.", "counter", "manabou"),
    _c("n5-kudasai", "見る", "просьба в магазине", "見てください", "посмотрите, пожалуйста", "request", "manabou"),
    _c(
        "n5-collocation",
        "かぜ",
        "連語: простудиться, не «ветер + тянуть»",
        "かぜをひく",
        "пара из ペアで覚えることば",
        "collocation",
        "pea",
    ),
    _c("n4-pot", "読む", "потенциал", "読める", "мочь читать", "potential", "manabou"),
    _c("n4-give", "プレゼント", "на уроке даёте вы, не くれる", "あげる", "от меня. Не くれる.", "give", "manabou"),
    _c("n4-tara", "行く", "условие たら", "行ったら", "если пойду / когда пошёл", "cond", "manabou"),
    _c("n4-nagara", "食べる", "ながら", "食べながら", "делая два сразу", "nagara", "manabou"),
    _c("n4-te-aux", "見る", "てみる", "見てみる", "попробовать посмотреть", "te-aux", "manabou"),
    _c("n4-nakereba", "行く", "надо (длинная форма)", "行かなければならない", "надо пойти", "must", "manabou"),
    _c("n4-tsumori", "行く", "намерение", "行くつもりです", "собираюсь пойти", "intent", "manabou"),
    _c("n4-naru", "静か", "стать каким (な)", "静かになる", "стать тихим", "naru", "manabou"),
    _c(
        "n3-tame",
        "勉強する",
        "цель ために",
        "勉強するために",
        "чтобы учиться. Не ように.",
        "purpose",
        "pointo",
    ),
    _c(
        "p06",
        "読む",
        "номинализация こと",
        "読むこと",
        "ポイント20: 「こと」と「の」. Не синонимы.",
        "nominal",
        "pointo",
    ),
    _c(
        "p10",
        "雨",
        "если (仮定)",
        "雨なら",
        "ポイント20: 仮定・逆接. На Zoom могла быть たら.",
        "cond",
        "pointo",
    ),
    _c(
        "p11",
        "寒い",
        "причина, мягче から",
        "寒いので",
        "ポイント20: 原因. Учитель мог дать から.",
        "reason",
        "pointo",
    ),
)

OPEN: tuple[PackItem, ...] = (
    _o("n5-wa-ga", "私", "в очереди говорите о себе, не о новом лице", "は", "тема высказывания", "particle"),
    _o("n5-ni-de", "学校", "направление к зданию, не «внутри»", "学校へ", "в школу (направление)", "particle"),
    _o("n5-kore", "近くのもの", "на столе рядом с вами", "これ", "не それ и не あれ", "deictic"),
    _o("n5-adj", "高い", "вчерашний ценник", "高かった", "был высоким / дорогим", "adj"),
    _o("n4-sou", "おいしい", "ещё не пробовали, только видите", "おいしそう", "выглядит вкусным", "sou"),
    _o("n4-you", "病気", "по лицу, не «слышно что»", "病気のようだ", "похоже, болен", "you"),
    _o("n4-noni", "勉強した", "ждали другое", "勉強したのに", "хотя учился", "noni"),
    _o("n3-passive", "食べる", "пирог исчез без вас", "食べられる", "быть съеденным / есть возможность — по уроку", "passive"),
    _o("n3-caus", "食べる", "ребёнку надо поесть", "食べさせる", "заставить / дать поесть", "causative"),
    _o("n3-tokoro", "出る", "как раз у двери", "出るところです", "как раз выходит", "tokoro"),
    _o("n3-wake", "行く", "отрицаете чужой вывод", "行くわけではない", "не то чтобы иду", "wake"),
    _o("n3-baai", "雨", "план B на улице", "雨の場合", "в случае дождя", "baai"),
    _o("n3-keigo-lite", "待つ", "в приёмной", "お待ちください", "вежливая просьба подождать.", "keigo"),
    _o("n2-keigo", "行く", "о преподавателе, не о себе", "いらっしゃる", "идти (уважит.).", "keigo"),
    _o("n2-nuanced", "子供", "так бывает, не приказ", "子供は泣くものだ", "дети плачут — общее место, не ключ て.", "mono"),
    _o("n2-contra", "思う", "делаете, хотя сомневаетесь", "思いつつ", "уступка つつ. Не ながら.", "concession"),
    _o("n2-aspect", "読む", "до конца, не «начать»", "読み切る", "аспект 切る.", "aspect"),
    _o("n2-written", "天気", "в объявлении, не в чате", "天気について", "письменная связка.", "written"),
    _o("n2-hearsay", "雨", "пересказ прогноза, не вид", "雨だそうだ", "слышно, что дождь.", "hearsay"),
    _o("n1-formal", "法律", "в приказе, не в кафе", "法律をもって", "письменный регистр.", "formal"),
    _o("n1-invert", "子供", "даже они, эмфаза", "子供ですら", "ですら.", "emphasis"),
    _o("n1-written", "会議", "газетная связка", "会議により", "により.", "news"),
    _o("n1-nuance", "失敗", "уже с этого видно", "失敗からして", "からして.", "nuance"),
)

COURSE_BY_TOPIC = {item.topic_id: item for item in COURSE}
OPEN_BY_TOPIC = {item.topic_id: item for item in OPEN}

FILL_KINDS = frozenset({"grammar", "vocab"})
SKIP_KINDS = frozenset({"listening", "conversation", "mimetics", "reading"})


def pick_item(topic_id: str) -> PackItem | None:
    return COURSE_BY_TOPIC.get(topic_id) or OPEN_BY_TOPIC.get(topic_id)
