"""Workbook drills from the unofficial N-level catalog.

Not a Probe. Not a Claim. Completing a notebook is not JLPT and not
teacher mastery. Catalog clicks still do not mint claims.
"""

from __future__ import annotations

import json
import random
import re
import time
from functools import lru_cache

from proba import db, dictionary, jlpt, kana, packs, schedule, yarxi
from proba.flavor import app_name
from proba.ids import new_id

LEVELS = jlpt.LEVELS
KINDS = ("match_word", "match_kanji", "read_word", "match_grammar")
PAIR_N = 4
DELAY_SEC = 18 * 3600
RECENT_SEC = 45 * 60
DAILY_TOAST_CAP = 4
PROMPT_MAX = 80
VOCAB_CAPS = {"N5": 48, "N4": 56, "N3": 64, "N2": 72, "N1": 80}

_KANJI = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]{3,}")
_SKIP_GLOSS = re.compile(r"форма|частица|связ", re.I)
_META_LEVEL = "drill_level"
_META_SESSION = "drill_session"
_META_TOAST_DAY = "drill_toast_day"
_META_TOAST_N = "drill_toast_n"
_META_KIND = "drill_kind_i"

_TOAST_BODY = {
    "match_word": "Закрепление {level}. Откройте тетрадь — соедините четыре слова.",
    "match_kanji": "Закрепление {level}. Откройте тетрадь — соедините четыре знака.",
    "read_word": "Закрепление {level}. Откройте тетрадь — напишите чтение.",
    "match_grammar": "Закрепление {level}. Откройте тетрадь — соедините четыре формы.",
}

_KIND_PROMPT = {
    "match_word": "Соедините слово и значение",
    "match_kanji": "Соедините знак и смысл",
    "match_grammar": "Соедините форму и смысл",
    "read_word": "Напишите чтение",
}


def _now() -> float:
    return schedule.now() if hasattr(schedule, "now") else time.time()


def _meta_get(key: str) -> str | None:
    row = db.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else None


def _meta_set(key: str, value: str) -> None:
    db.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _clip(text: str, n: int = 72) -> str:
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def _lead(text: str) -> str:
    raw = (text or "").replace("；", "·").replace(";", "·")
    bit = raw.split("·")[0].split(",")[0].strip()
    return _clip(bit, 48)


def _local_day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def level() -> str | None:
    raw = (_meta_get(_META_LEVEL) or "").strip().upper()
    return raw if raw in LEVELS else None


def next_level(lv: str) -> str | None:
    try:
        i = LEVELS.index(lv)
    except ValueError:
        return None
    if i + 1 >= len(LEVELS):
        return None
    return LEVELS[i + 1]


def _kanji_upto(lv: str) -> tuple[set[str], set[str]]:
    here: set[str] = set()
    upto: set[str] = set()
    hit = False
    for name in LEVELS:
        chars = {item.get("c") or "" for item in jlpt._kanji_bank().get(name, [])}
        chars.discard("")
        upto |= chars
        if name == lv:
            here = chars
            hit = True
            break
    if not hit:
        here = {item.get("c") or "" for item in jlpt._kanji_bank().get("N5", [])}
        here.discard("")
        upto = set(here)
    return here, upto


@lru_cache(maxsize=8)
def _kanji_items(lv: str) -> tuple[dict, ...]:
    rows = []
    seen_lead: set[str] = set()
    for item in jlpt._kanji_bank().get(lv, []):
        ch = (item.get("c") or "").strip()
        if not ch:
            continue
        gloss = yarxi._kanji_gloss(ch)
        lead = _lead(gloss)
        if not lead or _LATIN.search(lead):
            continue
        if lead in seen_lead:
            continue
        seen_lead.add(lead)
        rows.append({"key": f"k:{ch}", "head": ch, "left": ch, "right": lead, "kana": ""})
    return tuple(rows)


def _word_ok(head: str, kana_s: str, gloss: str, here: set[str], upto: set[str]) -> bool:
    if not head or not kana_s or not gloss:
        return False
    if _SKIP_GLOSS.search(gloss) or _LATIN.search(gloss):
        return False
    if not _KANJI.search(head):
        return False
    chars = set(_KANJI.findall(head))
    if not chars <= upto:
        return False
    if here and not (chars & here):
        return False
    if len(head) > 6 or len(head) < 1:
        return False
    lead = _lead(gloss)
    if not lead or len(lead) < 2:
        return False
    return True


@lru_cache(maxsize=8)
def _word_items(lv: str) -> tuple[dict, ...]:
    here, upto = _kanji_upto(lv)
    cap = VOCAB_CAPS.get(lv, 48)
    seen_head: set[str] = set()
    seen_lead: set[str] = set()
    rows: list[dict] = []

    def add(head: str, kana_s: str, gloss: str) -> None:
        if head in seen_head:
            return
        if not _word_ok(head, kana_s, gloss, here, upto):
            return
        lead = _lead(gloss)
        if lead in seen_lead:
            return
        seen_head.add(head)
        seen_lead.add(lead)
        rows.append(
            {
                "key": f"w:{head}",
                "read_key": f"r:{head}",
                "head": head,
                "left": head,
                "right": lead,
                "kana": kana_s,
            }
        )

    for head, kana_s, gloss in dictionary.LEXICON:
        add(head, kana_s, gloss)
        if len(rows) >= cap:
            return tuple(rows)
    for head, kana_s, gloss in dictionary.packed_words():
        add(head, kana_s, gloss)
        if len(rows) >= cap:
            break
    return tuple(rows)


@lru_cache(maxsize=8)
def _grammar_items(lv: str) -> tuple[dict, ...]:
    rows = []
    seen_lead: set[str] = set()
    for topic in jlpt._level_topics(lv):
        kind = topic.get("kind") or "grammar"
        if kind in packs.SKIP_KINDS:
            continue
        tid = topic.get("id") or ""
        title = (topic.get("title") or "").strip()
        blurb = (topic.get("blurb") or "").strip()
        if not tid or not title or not blurb:
            continue
        if blurb in {"Продолжение.", "Продолжение"}:
            continue
        pack = packs.pick_item(tid)
        if pack and pack.gloss_ru and kind == "vocab":
            left = pack.expected or pack.prompt_ja
            right = _lead(pack.gloss_ru)
        else:
            left = title
            right = _lead(blurb)
        if not right or right in seen_lead or _LATIN.search(right):
            continue
        seen_lead.add(right)
        rows.append({"key": f"g:{tid}", "head": tid, "left": left, "right": right, "kana": ""})
    return tuple(rows)


def _bank(lv: str, kind: str) -> tuple[dict, ...]:
    if kind == "match_kanji":
        return _kanji_items(lv)
    if kind in {"match_word", "read_word"}:
        return _word_items(lv)
    if kind == "match_grammar":
        return _grammar_items(lv)
    return ()


def reset_banks() -> None:
    _kanji_items.cache_clear()
    _word_items.cache_clear()
    _grammar_items.cache_clear()


def _attempts(item_key: str) -> list[dict]:
    rows = db.query(
        "SELECT at, outcome, first_try FROM drill_attempts "
        "WHERE item_key = ? ORDER BY at",
        (item_key,),
    )
    return [dict(r) for r in rows]


def is_excellent(item_key: str) -> bool:
    first = None
    excellent = False
    for row in _attempts(item_key):
        if row["outcome"] == "fail":
            first = None
            excellent = False
            continue
        if row["outcome"] != "pass" or not row["first_try"]:
            continue
        if first is None:
            first = float(row["at"])
        elif float(row["at"]) - first >= DELAY_SEC:
            excellent = True
            first = float(row["at"])
    return excellent


def _last_at(item_key: str) -> float | None:
    row = db.query_one(
        "SELECT at FROM drill_attempts WHERE item_key = ? ORDER BY at DESC LIMIT 1",
        (item_key,),
    )
    return float(row["at"]) if row else None


def _last_outcome(item_key: str) -> str | None:
    row = db.query_one(
        "SELECT outcome FROM drill_attempts WHERE item_key = ? ORDER BY at DESC LIMIT 1",
        (item_key,),
    )
    return row["outcome"] if row else None


def _due(item_key: str, now: float) -> bool:
    if is_excellent(item_key):
        return False
    last = _last_at(item_key)
    if last is None:
        return True
    if now - last < RECENT_SEC:
        return False
    if _last_outcome(item_key) == "pass" and now - last < DELAY_SEC:
        return False
    return True


def _word_done(item: dict) -> bool:
    return is_excellent(item["key"]) and is_excellent(item.get("read_key") or item["key"])


def _progress(lv: str) -> dict:
    words = _word_items(lv)
    kanji = _kanji_items(lv)
    gram = _grammar_items(lv)
    w_done = sum(1 for it in words if _word_done(it))
    w_seen = sum(1 for it in words if _last_at(it["key"]) or _last_at(it.get("read_key") or ""))
    k_done = sum(1 for it in kanji if is_excellent(it["key"]))
    k_seen = sum(1 for it in kanji if _last_at(it["key"]))
    g_done = sum(1 for it in gram if is_excellent(it["key"]))
    g_seen = sum(1 for it in gram if _last_at(it["key"]))
    return {
        "words": {"done": w_done, "seen": w_seen, "total": len(words)},
        "kanji": {"done": k_done, "seen": k_seen, "total": len(kanji)},
        "grammar": {"done": g_done, "seen": g_seen, "total": len(gram)},
    }


def _complete(lv: str) -> bool:
    p = _progress(lv)
    if not p["words"]["total"] or not p["kanji"]["total"] or not p["grammar"]["total"]:
        return False
    return (
        p["words"]["done"] >= p["words"]["total"]
        and p["kanji"]["done"] >= p["kanji"]["total"]
        and p["grammar"]["done"] >= p["grammar"]["total"]
    )


def status() -> dict:
    lv = level()
    if not lv:
        return {
            "level": None,
            "levels": list(LEVELS),
            "locked": False,
            "unofficial": True,
            "complete": False,
            "offer": None,
            "progress": None,
        }
    prog = _progress(lv)
    done = _complete(lv)
    nxt = next_level(lv) if done else None
    return {
        "level": lv,
        "levels": list(LEVELS),
        "locked": True,
        "unofficial": True,
        "complete": done,
        "offer": nxt,
        "progress": prog,
        "lede": "Тетрадь справочника, не экзамен JLPT и не проба с урока.",
    }


def set_level(lv: str, *, confirm: bool = False) -> dict:
    want = (lv or "").strip().upper()
    if want not in LEVELS:
        return {"ok": False, "error": "Нет такого уровня"}
    cur = level()
    if cur and cur != want and not confirm:
        return {
            "ok": False,
            "need_confirm": True,
            "level": cur,
            "want": want,
            "message": f"Сейчас тетрадь {cur}. Сменить на {want}? Прогресс {cur} останется.",
        }
    _meta_set(_META_LEVEL, want)
    _meta_set(_META_SESSION, "")
    return {"ok": True, **status()}


def _kind_index() -> int:
    try:
        return int(_meta_get(_META_KIND) or "0")
    except ValueError:
        return 0


def _due_items(lv: str, kind: str, now: float) -> list[dict]:
    bank = _bank(lv, kind)
    if kind == "read_word":
        return [it for it in bank if _due(it["read_key"], now)]
    return [it for it in bank if _due(it["key"], now)]


def _has_work(lv: str, now: float) -> bool:
    if _complete(lv):
        return False
    return any(_due_items(lv, kind, now) for kind in KINDS)


def _pick_kind(lv: str, now: float) -> str | None:
    start = _kind_index() % len(KINDS)
    for i in range(len(KINDS)):
        kind = KINDS[(start + i) % len(KINDS)]
        if _due_items(lv, kind, now):
            _meta_set(_META_KIND, str((start + i + 1) % len(KINDS)))
            return kind
    return None


def _fill_pairs(lv: str, kind: str, now: float) -> list[dict]:
    due = list(_due_items(lv, kind, now))
    random.shuffle(due)
    picked = due[:PAIR_N]
    if len(picked) >= 2:
        bank = [it for it in _bank(lv, kind) if it not in picked]
        random.shuffle(bank)
        while len(picked) < min(PAIR_N, len(due) + len(bank)) and bank:
            picked.append(bank.pop())
        return picked[:PAIR_N]
    if len(picked) == 1:
        rest = [it for it in _bank(lv, kind) if it not in picked]
        random.shuffle(rest)
        picked.extend(rest[: PAIR_N - 1])
        return picked[:PAIR_N]
    prev_i = LEVELS.index(lv) - 1 if lv in LEVELS else -1
    if prev_i >= 0:
        easier = list(_due_items(LEVELS[prev_i], kind, now)) or list(_bank(LEVELS[prev_i], kind))
        random.shuffle(easier)
        picked.extend(easier[:PAIR_N])
    return picked[:PAIR_N]


def _opaque_match(kind: str, lv: str, items: list[dict]) -> dict:
    sid = new_id()
    left = []
    right = []
    map_l = {}
    map_r = {}
    rights = list(items)
    random.shuffle(rights)
    for i, it in enumerate(items):
        lid = f"L{i}"
        map_l[lid] = it["key"] if kind != "read_word" else it["read_key"]
        left.append({"id": lid, "text": it["left"]})
    for i, it in enumerate(rights):
        rid = f"R{i}"
        map_r[rid] = it["key"] if kind != "read_word" else it["read_key"]
        right.append({"id": rid, "text": it["right"]})
    texts = {it["key"]: {"left": it["left"], "right": it["right"]} for it in items}
    session = {
        "id": sid,
        "kind": kind,
        "level": lv,
        "map_l": map_l,
        "map_r": map_r,
        "texts": texts,
        "at": _now(),
    }
    _meta_set(_META_SESSION, json.dumps(session, ensure_ascii=False))
    return {
        "id": sid,
        "kind": kind,
        "level": lv,
        "prompt": _KIND_PROMPT[kind],
        "left": left,
        "right": right,
    }


def _open_read(lv: str, item: dict) -> dict:
    sid = new_id()
    session = {
        "id": sid,
        "kind": "read_word",
        "level": lv,
        "item_key": item["read_key"],
        "expected": item["kana"],
        "at": _now(),
    }
    _meta_set(_META_SESSION, json.dumps(session, ensure_ascii=False))
    return {
        "id": sid,
        "kind": "read_word",
        "level": lv,
        "prompt": _KIND_PROMPT["read_word"],
        "surface": item["head"],
    }


def next_task(now: float | None = None) -> dict:
    now = _now() if now is None else now
    st = status()
    if not st["level"]:
        return {"ok": False, "need_level": True, "status": st}
    if st["complete"]:
        return {"ok": True, "idle": True, "complete": True, "status": st}
    kind = _pick_kind(st["level"], now)
    if not kind:
        return {"ok": True, "idle": True, "status": st}
    if kind == "read_word":
        due = _due_items(st["level"], kind, now)
        random.shuffle(due)
        item = due[0]
        task = _open_read(st["level"], item)
        return {"ok": True, "task": task, "status": st}
    items = _fill_pairs(st["level"], kind, now)
    if len(items) < 2:
        return {"ok": True, "idle": True, "status": st}
    task = _opaque_match(kind, st["level"], items)
    return {"ok": True, "task": task, "status": st}


def _session() -> dict | None:
    raw = _meta_get(_META_SESSION) or ""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _first_try(item_key: str, now: float) -> bool:
    last = _last_at(item_key)
    if last is None:
        return True
    return (now - last) >= 2 * 3600


def _write_attempt(
    item_key: str,
    kind: str,
    level: str,
    now: float,
    outcome: str,
    first_try: bool,
    response: str,
) -> None:
    last = _last_at(item_key)
    delay = schedule.delay_hours(now, last, now if last is None else last)
    db.execute(
        "INSERT INTO drill_attempts (id, item_key, kind, level, at, outcome, first_try, delay_hours, response) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            new_id(),
            item_key,
            kind,
            level,
            now,
            outcome,
            1 if first_try else 0,
            delay,
            response[:200],
        ),
    )


def submit(session_id: str, *, pairs: dict | None = None, response: str = "", now: float | None = None) -> dict:
    now = _now() if now is None else now
    sess = _session()
    if not sess or sess.get("id") != session_id:
        return {"ok": False, "error": "Это задание уже закрыто"}
    kind = sess.get("kind") or ""
    lv = sess.get("level") or level() or "N5"
    results = []
    if kind == "read_word":
        key = sess.get("item_key") or ""
        expected = sess.get("expected") or ""
        graded = kana.grade(response, expected)
        ft = _first_try(key, now)
        _write_attempt(key, kind, lv, now, graded["outcome"], ft, response)
        results.append(
            {
                "key": key,
                "outcome": graded["outcome"],
                "reading": graded["reading"],
                "expected": expected,
            }
        )
    else:
        map_l = sess.get("map_l") or {}
        map_r = sess.get("map_r") or {}
        given = pairs or {}
        texts = sess.get("texts") or {}
        for lid, key in map_l.items():
            rid = given.get(lid) or ""
            want_r = next((r for r, k in map_r.items() if k == key), "")
            got = map_r.get(rid) if rid else None
            outcome = "pass" if got == key else "fail"
            ft = _first_try(key, now)
            _write_attempt(key, kind, lv, now, outcome, ft, rid)
            results.append(
                {
                    "left": lid,
                    "right": want_r,
                    "got": rid,
                    "outcome": outcome,
                    "key": key,
                    "answer": (texts.get(key) or {}).get("right") or "",
                }
            )
    _meta_set(_META_SESSION, "")
    passed = sum(1 for r in results if r["outcome"] == "pass")
    return {
        "ok": True,
        "kind": kind,
        "passed": passed,
        "total": len(results),
        "results": results,
        "status": status(),
        "logged": False,
    }


def toast_cue(now: float | None = None) -> dict | None:
    now = _now() if now is None else now
    lv = level()
    if not lv:
        return None
    if _complete(lv):
        return None
    day = _local_day(now)
    if _meta_get(_META_TOAST_DAY) == day:
        try:
            n = int(_meta_get(_META_TOAST_N) or "0")
        except ValueError:
            n = 0
        if n >= DAILY_TOAST_CAP:
            return None
    if not _has_work(lv, now):
        return None
    kind = KINDS[_kind_index() % len(KINDS)]
    if not _due_items(lv, kind, now):
        kind = _pick_kind(lv, now) or kind
    body = _TOAST_BODY.get(kind, _TOAST_BODY["match_word"]).format(level=lv)
    return {
        "id": f"drill:{lv}:{kind}",
        "kind": kind,
        "level": lv,
        "title": app_name(),
        "body": body[:PROMPT_MAX],
        "dest": "/drill",
    }


def note_toast(now: float | None = None) -> None:
    now = _now() if now is None else now
    day = _local_day(now)
    if _meta_get(_META_TOAST_DAY) != day:
        _meta_set(_META_TOAST_DAY, day)
        _meta_set(_META_TOAST_N, "1")
        return
    try:
        n = int(_meta_get(_META_TOAST_N) or "0")
    except ValueError:
        n = 0
    _meta_set(_META_TOAST_N, str(n + 1))
