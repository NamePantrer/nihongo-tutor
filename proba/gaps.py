from __future__ import annotations

from proba import curriculum, db, kernel, schedule
from proba.ids import new_id


def refresh_gaps() -> list[dict]:
    existing = {
        row["prompt_ja"]
        for row in db.query("SELECT prompt_ja FROM claims")
    }
    already = {
        row["prompt_ja"]
        for row in db.query("SELECT prompt_ja FROM gap_proposals")
    }
    t = schedule.now()
    created = []
    for item in curriculum.GAPS:
        if item["prompt_ja"] in existing or item["prompt_ja"] in already:
            continue
        if kernel.cue_leaks_key(item["prompt_ja"], item["expected"]):
            continue
        gid = new_id()
        db.execute(
            "INSERT INTO gap_proposals (id, prompt_ja, prompt_hint, expected, gloss_ru, "
            "reason, status, created_at) VALUES (?,?,?,?,?,?, 'pending', ?)",
            (
                gid,
                item["prompt_ja"],
                item["prompt_hint"],
                item["expected"],
                item["gloss_ru"],
                item["reason"],
                t,
            ),
        )
        created.append(gid)
    return list_gaps()


def list_gaps(status: str = "pending") -> list[dict]:
    rows = db.query(
        "SELECT * FROM gap_proposals WHERE status = ? ORDER BY created_at",
        (status,),
    )
    return [dict(r) for r in rows]


def propose_neighbors(text: str) -> list[dict]:
    """Create pending gaps from this lesson's tags only. Does not insert claims."""
    from proba.extract import neighbor_gap_items

    existing = {row["prompt_ja"] for row in db.query("SELECT prompt_ja FROM claims")}
    already = {
        row["prompt_ja"] for row in db.query("SELECT prompt_ja FROM gap_proposals")
    }
    t = schedule.now()
    for item in neighbor_gap_items(text):
        if item["prompt_ja"] in existing or item["prompt_ja"] in already:
            continue
        gid = new_id()
        db.execute(
            "INSERT INTO gap_proposals (id, prompt_ja, prompt_hint, expected, gloss_ru, "
            "reason, status, created_at) VALUES (?,?,?,?,?,?, 'pending', ?)",
            (
                gid,
                item["prompt_ja"],
                item["prompt_hint"],
                item["expected"],
                item["gloss_ru"],
                "С этого занятия, не из полного JLPT. Пока не примете — не проба. "
                + item["reason"],
                t,
            ),
        )
    return list_gaps()


def decide_gap(gap_id: str, accept: bool) -> dict:
    row = db.query_one("SELECT * FROM gap_proposals WHERE id = ?", (gap_id,))
    if row is None:
        raise KeyError("gap")
    if row["status"] != "pending":
        raise ValueError("already decided")
    if not accept:
        db.execute(
            "UPDATE gap_proposals SET status = 'rejected' WHERE id = ?", (gap_id,)
        )
        return {"ok": True, "accepted": False}
    item = None
    topic_id = ""
    origin = ""
    try:
        topic_id = row["topic_id"] or ""
        origin = row["origin"] or ""
    except (KeyError, IndexError):
        pass
    from proba import packs

    item = packs.pick_item(topic_id) if topic_id else None
    tags = (item.tags if item else "") or topic_id or "gap"
    provenance = "textbook" if origin == "course" else "dictionary" if origin == "open" else "model"
    existing = db.query_one(
        "SELECT id FROM claims WHERE prompt_ja = ? AND expected = ? "
        "AND status NOT IN ('rejected', 'proposed')",
        (row["prompt_ja"], row["expected"]),
    )
    if existing:
        db.execute(
            "UPDATE gap_proposals SET status = 'accepted' WHERE id = ?", (gap_id,)
        )
        return {"ok": True, "accepted": True, "existing": existing["id"]}
    result = kernel.create_lesson(
        "Пробел (подтверждённый)",
        row["reason"],
        [
            {
                "prompt_ja": row["prompt_ja"],
                "prompt_hint": row["prompt_hint"],
                "expected": row["expected"],
                "gloss_ru": row["gloss_ru"],
                "provenance": provenance,
                "tags": tags,
            }
        ],
        kind="gap",
    )
    db.execute(
        "UPDATE gap_proposals SET status = 'accepted' WHERE id = ?", (gap_id,)
    )
    return {"ok": True, "accepted": True, "lesson": result}
