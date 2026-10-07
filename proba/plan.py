from __future__ import annotations

import re

from proba import db, extract, jlpt, kernel, packs, schedule
from proba.ids import new_id

FILL_CAP = kernel.TONIGHT_CAP
PATH_LEN = 7
_PASTE_KEY = "last_paste"


def last_paste() -> str:
    row = db.query_one("SELECT value FROM meta WHERE key = ?", (_PASTE_KEY,))
    return (row["value"] if row else "") or ""


def save_paste(text: str) -> None:
    db.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (_PASTE_KEY, (text or "")[:12000]),
    )


def _title_named(title: str, raw: str) -> bool:
    """True when the paste names this station, not when the kana merely occurs."""
    if not (title or "").strip() or not raw:
        return False
    jp = "".join(ch for ch in title if "\u3040" <= ch <= "\u9fff")
    has_gloss = any(
        not ("\u3040" <= ch <= "\u9fff") and (ch.isalnum() or ch in "/・")
        for ch in title
    )
    if has_gloss and len(title) >= 3:
        return title in raw
    if "/" in title or "・" in title:
        return title in raw
    needle = jp or title
    if not needle:
        return False
    return (
        re.search(
            rf"(?<![\u3040-\u9fff]){re.escape(needle)}(?![\u3040-\u9fff])",
            raw,
        )
        is not None
    )


def _id_in_text(tid: str, raw: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9-]){re.escape(tid)}(?![A-Za-z0-9-])", raw) is not None


def _priority_ids(pasted: str) -> list[str]:
    raw = pasted or ""
    if not raw.strip():
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for _lv, topic in jlpt.walk_topics():
        tid = topic["id"]
        title = topic.get("title") or ""
        book = topic.get("from_book") or ""
        hit = _id_in_text(tid, raw) or (book and book in raw) or _title_named(title, raw)
        if hit and tid not in seen:
            seen.add(tid)
            ordered.append(tid)
    return ordered


def _rotated_levels(start: str | None) -> list[str]:
    order = list(jlpt.LEVELS)
    lv = (start or "N5").upper()
    if lv not in order:
        lv = "N5"
    i = order.index(lv)
    return order[i:] + order[:i]


def _inventory() -> dict:
    attested: set[tuple[str, str]] = set()
    draft: set[tuple[str, str]] = set()
    blocking: set[tuple[str, str]] = set()
    pending_ids: set[str] = set()
    for row in db.query("SELECT prompt_ja, expected, status FROM claims"):
        pair = (row["prompt_ja"] or "", row["expected"] or "")
        if row["status"] in ("tonight", "queued", "known"):
            attested.add(pair)
            blocking.add(pair)
        elif row["status"] == "proposed":
            draft.add(pair)
            blocking.add(pair)
    for row in db.query(
        "SELECT prompt_ja, expected, status, topic_id FROM gap_proposals"
    ):
        pair = (row["prompt_ja"] or "", row["expected"] or "")
        if row["status"] == "pending":
            if row["topic_id"]:
                pending_ids.add(row["topic_id"])
            blocking.add(pair)
    return {
        "attested": attested,
        "draft": draft,
        "blocking": blocking,
        "pending_ids": pending_ids,
    }


def coverage_of(topic: dict, inv: dict | None = None) -> str:
    inv = inv or _inventory()
    tid = topic["id"]
    if tid in inv["pending_ids"]:
        return "pending"
    item = packs.pick_item(tid)
    if not item:
        return "empty"
    pair = (item.prompt_ja, item.expected)
    if pair in inv["attested"]:
        return "attested"
    if pair in inv["draft"]:
        return "draft"
    return "empty"


def stations(level: str | None = None) -> list[dict]:
    lv = (level or "N5").upper()
    if lv not in jlpt.LEVELS:
        lv = "N5"
    inv = _inventory()
    out = []
    for topic_lv, topic in jlpt.walk_topics():
        if topic_lv != lv:
            continue
        kind = topic.get("kind") or "grammar"
        item = packs.pick_item(topic["id"]) if kind in packs.FILL_KINDS else None
        out.append(
            {
                "id": topic["id"],
                "title": topic["title"],
                "blurb": topic.get("blurb") or "",
                "level": topic_lv,
                "kind": kind,
                "coverage": coverage_of(topic, inv),
                "fillable": bool(item) and kind in packs.FILL_KINDS,
                "pack": item.pack if item else "",
                "origin": item.origin if item else "",
            }
        )
    return out


def _station_from(topic_lv: str, topic: dict, item: packs.PackItem, inv: dict) -> dict:
    kind = topic.get("kind") or "grammar"
    return {
        "id": topic["id"],
        "title": topic["title"],
        "blurb": topic.get("blurb") or "",
        "level": topic_lv,
        "kind": kind,
        "coverage": coverage_of(topic, inv),
        "fillable": True,
        "pack": item.pack,
        "origin": item.origin,
    }


def candidate_queue(
    pasted: str = "", level: str | None = None
) -> tuple[list[tuple[str, dict, packs.PackItem]], int]:
    """Matched fillable packs first, then open examples from the open stamp.

    Course-shelf templates are not walked unless the pasted page named that station.
    """
    raw = (pasted or "").strip()
    skipped = 0
    queue: list[tuple[str, dict, packs.PackItem]] = []
    seen: set[str] = set()
    by_id = {t["id"]: (lv, t) for lv, t in jlpt.walk_topics()}

    for tid in _priority_ids(raw):
        pair = by_id.get(tid)
        if not pair:
            continue
        lv, topic = pair
        kind = topic.get("kind") or "grammar"
        if kind in packs.SKIP_KINDS:
            skipped += 1
            continue
        if kind not in packs.FILL_KINDS:
            continue
        item = packs.pick_item(tid)
        if item is None or tid in seen:
            continue
        seen.add(tid)
        queue.append((lv, topic, item))

    for lv in _rotated_levels(level):
        for topic_lv, topic in jlpt.walk_topics():
            if topic_lv != lv:
                continue
            tid = topic["id"]
            if tid in seen:
                continue
            kind = topic.get("kind") or "grammar"
            if kind in packs.SKIP_KINDS or kind not in packs.FILL_KINDS:
                continue
            item = packs.OPEN_BY_TOPIC.get(tid)
            if item is None:
                continue
            seen.add(tid)
            queue.append((lv, topic, item))
    return queue, skipped


def next_path(level: str | None = None) -> list[dict]:
    inv = _inventory()
    path = []
    queue, _skipped = candidate_queue(last_paste(), level)
    for lv, topic, item in queue:
        st = _station_from(lv, topic, item, inv)
        if st["coverage"] in ("attested", "draft", "pending"):
            continue
        path.append(st)
        if len(path) >= PATH_LEN:
            return path
    return path


def overview(level: str | None = None) -> dict:
    lv = (level or "N5").upper()
    pending_n = len(db.query("SELECT id FROM gap_proposals WHERE status = 'pending'"))
    return {
        "level": lv if lv in jlpt.LEVELS else "N5",
        "fill_cap": FILL_CAP,
        "path_len": PATH_LEN,
        "pending": pending_n,
        "stations": stations(lv),
        "path": next_path(lv),
        "unofficial": True,
    }


def analyze(text: str) -> dict:
    """Match a pasted page to stations. Remembers the page; does not write claims or gaps."""
    raw = text or ""
    save_paste(raw)
    matched = []
    by_id = {t["id"]: (lv, t) for lv, t in jlpt.walk_topics()}
    for tid in _priority_ids(raw):
        pair = by_id.get(tid)
        if not pair:
            continue
        lv, topic = pair
        item = packs.pick_item(tid)
        matched.append(
            {
                "id": tid,
                "level": lv,
                "title": topic["title"],
                "origin": item.origin if item else "",
                "fillable": bool(item)
                and (topic.get("kind") or "grammar") in packs.FILL_KINDS,
            }
        )
    preview = extract.proposals_from_text(raw)
    return {
        "matched": matched,
        "extract_preview": [
            {
                "prompt_ja": p["prompt_ja"],
                "expected": p["expected"],
                "provenance": p["provenance"],
            }
            for p in preview
        ],
        "claims": len(db.query("SELECT id FROM claims")),
        "pending": len(db.query("SELECT id FROM gap_proposals WHERE status = 'pending'")),
        "analyzer": "lexicon",
    }


def fill(pasted: str = "", level: str | None = None) -> dict:
    """Propose up to FILL_CAP production items. Never inserts claims.

    Named page → that station's pack (course if we have a shelf key). Remainder
    and empty/unmatched pages → original open examples, not the unofficial N5 dump.
    """
    inv = _inventory()
    blocking = set(inv["blocking"])
    pending = set(inv["pending_ids"])
    raw = (pasted or "").strip() or last_paste()
    if (pasted or "").strip():
        save_paste(pasted)
    queue, skipped_listen = candidate_queue(raw, level)
    pending_n = len(db.query("SELECT id FROM gap_proposals WHERE status = 'pending'"))
    room = FILL_CAP - pending_n
    created: list[str] = []
    used_open = 0
    used_course = 0

    if room > 0:
        for topic_lv, topic, item in queue:
            if len(created) >= room:
                break
            if topic["id"] in pending:
                continue
            pair = (item.prompt_ja, item.expected)
            if pair in blocking:
                continue
            if kernel.cue_leaks_key(item.prompt_ja, item.expected):
                continue
            _insert_gap(item, topic_lv)
            blocking.add(pair)
            pending.add(topic["id"])
            created.append(item.topic_id)
            if item.origin == "open":
                used_open += 1
            else:
                used_course += 1

    return {
        "created": created,
        "count": len(created),
        "claims": len(db.query("SELECT id FROM claims")),
        "used_course": used_course,
        "used_open": used_open,
        "skipped_non_production": skipped_listen,
        "fill_cap": FILL_CAP,
        "pending": len(db.query("SELECT id FROM gap_proposals WHERE status = 'pending'")),
        "used_paste": bool(raw.strip()),
        "level": (level or "N5").upper() if (level or "N5").upper() in jlpt.LEVELS else "N5",
    }


def _insert_gap(item: packs.PackItem, level: str) -> None:
    t = schedule.now()
    reason = (
        f"Тропа {level}: {item.topic_id}. "
        + (
            "Шаблон с полки курса."
            if item.origin == "course"
            else "Открытый пример: на странице не было ключа."
        )
    )
    db.execute(
        "INSERT INTO gap_proposals (id, prompt_ja, prompt_hint, expected, gloss_ru, "
        "reason, status, created_at, topic_id, level, pack, origin) "
        "VALUES (?,?,?,?,?,?, 'pending', ?,?,?,?,?)",
        (
            new_id(),
            item.prompt_ja,
            item.prompt_hint,
            item.expected,
            item.gloss_ru,
            reason,
            t,
            item.topic_id,
            level,
            item.pack,
            item.origin,
        ),
    )


def _find_topic(topic_id: str) -> tuple[str, dict] | None:
    tid = (topic_id or "").strip()
    if not tid:
        return None
    for lv, topic in jlpt.walk_topics():
        if topic["id"] == tid:
            return lv, topic
    return None


def _lexicon_for(item: packs.PackItem) -> list[dict]:
    from proba import dictionary

    seen: set[tuple] = set()
    out: list[dict] = []
    for q in (item.prompt_ja, item.expected):
        for hit in dictionary.search(q, limit=8, packed=False):
            key = (hit.get("kind"), hit.get("head"))
            if key in seen:
                continue
            seen.add(key)
            out.append(hit)
            if len(out) >= 8:
                return out
    return out


def station_page(topic_id: str) -> dict | None:
    """Reference sheet. Does not insert claims or drafts."""
    found = _find_topic(topic_id)
    if not found:
        return None
    lv, topic = found
    tid = topic["id"]
    kind = topic.get("kind") or "grammar"
    item = packs.pick_item(tid) if kind in packs.FILL_KINDS else None
    yours: list[dict] = []
    if item:
        for row in db.query(
            "SELECT status, provenance FROM claims "
            "WHERE prompt_ja = ? AND expected = ? AND status NOT IN ('rejected', 'proposed')",
            (item.prompt_ja, item.expected),
        ):
            yours.append({"status": row["status"], "provenance": row["provenance"]})
    hits = []
    if kind not in packs.SKIP_KINDS:
        hits = [
            {"prompt_ja": h["prompt_ja"], "status": h["status"]}
            for h in (jlpt.topic_hits(topic.get("tag") or "") or [])
        ]
    example = None
    if item:
        example = {
            "prompt_ja": item.prompt_ja,
            "prompt_hint": item.prompt_hint,
            "expected": item.expected,
            "gloss_ru": item.gloss_ru,
            "pack": item.pack,
            "origin": item.origin,
        }
    overlay = None
    if kind == "mimetics":
        from proba import giongo

        overlay = giongo.station_overlay()
    return {
        "ok": True,
        "id": tid,
        "level": lv,
        "title": topic["title"],
        "blurb": topic.get("blurb") or "",
        "kind": kind,
        "from_book": topic.get("from_book") or "",
        "fillable": bool(item) and kind in packs.FILL_KINDS,
        "skip_kind": kind in packs.SKIP_KINDS,
        "example": example,
        "lexicon": _lexicon_for(item) if item else [],
        "your_pairs": yours,
        "hits": hits,
        "unofficial": True,
        "giongo": overlay,
    }


def station_check(topic_id: str, response: str) -> dict:
    """Grade a pack example. Does not write probe_attempts."""
    from proba import kana

    page = station_page(topic_id)
    if not page or not page.get("example"):
        return {"ok": False, "logged": False, "outcome": "fail"}
    graded = kana.grade(response, page["example"]["expected"])
    return {
        "ok": True,
        "logged": False,
        "outcome": graded["outcome"],
        "expected": page["example"]["expected"],
        "reading": graded["reading"],
        "expected_reading": graded["expected_reading"],
        "empty": graded["empty"],
    }
