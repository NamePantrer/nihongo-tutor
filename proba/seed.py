from __future__ import annotations

# Diagnostic items.

DIAGNOSTIC = [
    {
        "prompt_ja": "行く",
        "prompt_hint": "て-форма",
        "expected": "行って",
        "gloss_ru": "идти → 行って",
    },
    {
        "prompt_ja": "私___学生です。",
        "prompt_hint": "は или が",
        "expected": "は",
        "gloss_ru": "Тема, не новое подлежащее: は",
    },
    {
        "prompt_ja": "友達が本を___。 (мне дали)",
        "prompt_hint": "направление давания",
        "expected": "くれた",
        "gloss_ru": "Ко мне: くれる. Прошедшее: くれた",
    },
    {
        "prompt_ja": "食べる",
        "prompt_hint": "ない-форма",
        "expected": "食べない",
        "gloss_ru": "ru-глагол: 食べない",
    },
    {
        "prompt_ja": "この本は___。 (могу прочитать)",
        "prompt_hint": "потенциал 読む",
        "expected": "読める",
        "gloss_ru": "読む → 読める",
    },
    {
        "prompt_ja": "水を飲み___。 (хочу)",
        "prompt_hint": "たい",
        "expected": "たい",
        "gloss_ru": "飲みたい",
    },
    {
        "prompt_ja": "今、宿題を___。 (делаю, процесс)",
        "prompt_hint": "て-форма + いる",
        "expected": "している",
        "gloss_ru": "している / やってる",
    },
    {
        "prompt_ja": "疲れた___、早く寝ます。",
        "prompt_hint": "から или ので — причина",
        "expected": "から",
        "gloss_ru": "Оба возможны. На уроке часто から. ので мягче.",
    },
    {
        "prompt_ja": "___食べましたか。 (уже)",
        "prompt_hint": "もう / まだ",
        "expected": "もう",
        "gloss_ru": "もう = уже, まだ = ещё",
    },
    {
        "prompt_ja": "ペンが三___あります。",
        "prompt_hint": "счётный суффикс для длинных предметов",
        "expected": "本",
        "gloss_ru": "一本、二本、三本",
    },
]
