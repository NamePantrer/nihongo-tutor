from __future__ import annotations

import hashlib
import math
import time

from proba import compute, db, schedule, seed
from proba.ids import new_id

TONIGHT_CAP = 7
QUEUE_PARK_DAYS = 1.0
PROVENANCE = ("teacher", "dictionary", "textbook", "model", "self")
KEY_SOURCES = PROVENANCE + ("auto",)
OUTCOMES = ("pass", "fail", "partial")
KINDS = ("production", "recognition", "transfer_zoom")
TRANSFER = ("used", "not_used", "no_chance")


def _id() -> str:
    return new_id()


def _claim_out(row) -> dict | None:
    d = db.row_dict(row)
    if not d:
        return None
    sch = db.row_dict(
        db.query_one("SELECT * FROM schedule WHERE claim_id = ?", (d["id"],))
    )
    last = db.row_dict(
        db.query_one(
            "SELECT * FROM probe_attempts WHERE claim_id = ? ORDER BY at DESC LIMIT 1",
            (d["id"],),
        )
    )
    d["schedule"] = sch
    d["last_attempt"] = last
    d["cue_leaks_key"] = cue_leaks_key(d.get("prompt_ja") or "", d.get("expected") or "")
    d["prompt_hint"] = scrub_hint(d.get("prompt_hint") or "", d.get("expected") or "")
    return d


def cue_leaks_key(prompt_ja: str, expected: str) -> bool:
    """True when the cue is the answer (copying, not production)."""
    p = (
        (prompt_ja or "")
        .replace("___", "")
        .replace("…", "")
        .replace("...", "")
        .strip()
    )
    e = (expected or "").strip()
    return bool(e) and p == e


def scrub_hint(hint: str, expected: str) -> str:
    """Hints must not contain the production key."""
    text = hint or ""
    key = (expected or "").strip()
    if not key:
        return text
    parts = [key]
    try:
        from proba.kana import to_reading

        reading = to_reading(key)
        if reading and reading != key:
            parts.append(reading)
    except Exception:
        pass
    for part in parts:
        if part:
            text = text.replace(part, "")
    cleaned = " ".join(text.replace("/", " ").replace("·", " ").split())
    if not cleaned:
        return "произведите форму, как на уроке"
    return cleaned


def diagnostic_pending() -> bool:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM source_events WHERE kind = 'diagnostic'"
    )
    return not row or row["n"] == 0


def ensure_diagnostic() -> None:
    if not diagnostic_pending():
        return
    t = schedule.now()
    eid = _id()
    db.execute(
        "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
        "VALUES (?, 'diagnostic', 'Срез: что уже умею', ?, ?, '')",
        (eid, t, t),
    )
    for item in seed.DIAGNOSTIC:
        cid = _id()
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                cid,
                eid,
                item["prompt_ja"],
                item["prompt_hint"],
                item["expected"],
                item["gloss_ru"],
                "self",
                "diagnostic",
                t,
            ),
        )
        db.execute(
            "INSERT INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
            "VALUES (?,?, 2.5, 0, NULL)",
            (cid, t),
        )


def diagnostic_items() -> list[dict]:
    ensure_diagnostic()
    rows = db.query(
        "SELECT c.* FROM claims c JOIN source_events e ON e.id = c.source_event_id "
        "WHERE e.kind = 'diagnostic' AND c.status = 'diagnostic' ORDER BY c.created_at"
    )
    return [dict(r) for r in rows]


def answer_diagnostic(claim_id: str, knows: bool) -> dict:
    claim = db.query_one("SELECT * FROM claims WHERE id = ?", (claim_id,))
    if claim is None:
        raise KeyError("claim")
    if claim["status"] != "diagnostic":
        raise ValueError("already answered")
    t = schedule.now()
    if knows:
        db.execute("UPDATE claims SET status = 'known' WHERE id = ?", (claim_id,))
        db.execute(
            "UPDATE schedule SET due_at = ?, interval_days = 7, last_outcome = 'pass' "
            "WHERE claim_id = ?",
            (schedule.due_at(t, 7), claim_id),
        )
    else:
        tonight = _tonight_count()
        status = "tonight" if tonight < TONIGHT_CAP else "queued"
        db.execute("UPDATE claims SET status = ? WHERE id = ?", (status, claim_id))
        db.execute(
            "UPDATE schedule SET due_at = ?, interval_days = 0, last_outcome = NULL "
            "WHERE claim_id = ?",
            (_due_for_status(status, t), claim_id),
        )
    return {"ok": True, "knows": knows, "remaining": len(diagnostic_items())}


def _tonight_count() -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM claims WHERE status = 'tonight'"
    )
    return int(row["n"]) if row else 0


def _due_for_status(status: str, t: float) -> float:
    """Tonight is due now. Overflow queued is parked until the next day."""
    if status == "queued":
        return schedule.due_at(t, QUEUE_PARK_DAYS)
    return t


def create_lesson(
    title: str,
    notes: str,
    items: list[dict],
    kind: str = "lesson",
) -> dict:
    if not items:
        raise ValueError("empty")
    t = schedule.now()
    eid = _id()
    if kind not in ("lesson", "zoom_audio", "paste", "pdf", "gap"):
        kind = "lesson"
    db.execute(
        "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (eid, kind, title.strip() or "Занятие", t, t, notes.strip()),
    )
    created = []
    stamped = []
    tonight = _tonight_count()
    for raw in items:
        prompt_ja = (raw.get("prompt_ja") or "").strip()
        expected = (raw.get("expected") or "").strip()
        if not prompt_ja or not expected:
            continue
        if cue_leaks_key(prompt_ja, expected):
            continue
        provenance = raw.get("provenance") or "teacher"
        if provenance not in PROVENANCE:
            provenance = "teacher"
        twin_pair = db.query_one(
            "SELECT id FROM claims WHERE prompt_ja = ? AND expected = ? "
            "AND status NOT IN ('rejected', 'proposed')",
            (prompt_ja, expected),
        )
        if twin_pair:
            if provenance == "teacher":
                db.execute(
                    "UPDATE claims SET provenance = 'teacher' WHERE id = ?",
                    (twin_pair["id"],),
                )
                stamped.append(twin_pair["id"])
            continue
        cid = _id()
        status = raw.get("status") or None
        if status == "proposed":
            st = "proposed"
        elif tonight < TONIGHT_CAP:
            st = "tonight"
            tonight += 1
        else:
            st = "queued"
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                eid,
                prompt_ja,
                (raw.get("prompt_hint") or "произведите форму").strip(),
                expected,
                (raw.get("gloss_ru") or "").strip(),
                provenance,
                st,
                t,
                (raw.get("tags") or "").strip(),
            ),
        )
        if st != "proposed":
            db.execute(
                "INSERT INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
                "VALUES (?,?, 2.5, 0, NULL)",
                (cid, _due_for_status(st, t)),
            )
        _maybe_conflict(cid, prompt_ja, expected, provenance)
        created.append(cid)
    if not created and not stamped:
        raise ValueError("empty")
    return {
        "source_event_id": eid,
        "claim_ids": created or stamped,
        "tonight": _tonight_count(),
    }


def _maybe_conflict(claim_id: str, prompt_ja: str, expected: str, provenance: str) -> None:
    twin = db.query_one(
        "SELECT * FROM claims WHERE prompt_ja = ? AND id != ? "
        "AND expected != ? AND status NOT IN ('rejected', 'proposed')",
        (prompt_ja, claim_id, expected),
    )
    if twin is None:
        return
    if "teacher" in (twin["provenance"], provenance):
        winner = "teacher"
    else:
        winner = twin["provenance"] or provenance
    db.execute(
        "INSERT INTO conflicts (id, prompt_ja, claim_id_a, claim_id_b, expected_a, "
        "expected_b, winner, created_at) VALUES (?,?,?,?,?,?, ?, ?)",
        (
            _id(),
            prompt_ja,
            twin["id"],
            claim_id,
            twin["expected"],
            expected,
            winner,
            schedule.now(),
        ),
    )


def list_claims(status: str | None = None) -> list[dict]:
    if status:
        rows = db.query(
            "SELECT * FROM claims WHERE status = ? ORDER BY created_at", (status,)
        )
    else:
        rows = db.query("SELECT * FROM claims ORDER BY created_at")
    return [_claim_out(r) for r in rows]


def _local_day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _meta_get(key: str) -> str | None:
    row = db.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else None


def _meta_set(key: str, value: str) -> None:
    db.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def early_pull_used_today() -> bool:
    return _meta_get("early_pull_day") == _local_day(schedule.now())


def next_probe() -> dict | None:
    t = schedule.now()
    row = db.query_one(
        """
        SELECT c.* FROM claims c
        JOIN schedule s ON s.claim_id = c.id
        WHERE c.status IN ('tonight', 'queued', 'known')
          AND s.due_at <= ?
        ORDER BY
          CASE c.status WHEN 'tonight' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
          s.due_at ASC
        LIMIT 1
        """,
        (t,),
    )
    if row is None:
        row = db.query_one(
            """
            SELECT c.* FROM claims c
            JOIN schedule s ON s.claim_id = c.id
            WHERE c.status = 'tonight'
            ORDER BY s.due_at ASC
            LIMIT 1
            """
        )
    return _claim_out(row)


def due_expected() -> str:
    if diagnostic_items():
        return ""
    nxt = next_probe()
    return ((nxt or {}).get("expected") or "").strip()


def pull_one_queued() -> dict | None:
    """One parked form tonight, once. Does not dump the queue."""
    existing = next_probe()
    if existing:
        return existing
    if early_pull_used_today():
        raise ValueError("already")
    row = db.query_one(
        """
        SELECT c.* FROM claims c
        JOIN schedule s ON s.claim_id = c.id
        WHERE c.status = 'queued'
        ORDER BY s.due_at ASC
        LIMIT 1
        """
    )
    if row is None:
        return None
    sch = db.query_one("SELECT * FROM schedule WHERE claim_id = ?", (row["id"],))
    t = schedule.now()
    held = sch["due_at"] if sch else t
    db.execute(
        "UPDATE schedule SET due_at = ?, early_pull = 1, held_due_at = ? WHERE claim_id = ?",
        (t, held, row["id"]),
    )
    _meta_set("early_pull_day", _local_day(t))
    return next_probe()


def submit_probe(
    claim_id: str,
    response: str,
    confidence: float | None,
    outcome: str | None,
    kind: str,
    key_source: str | None = None,
) -> dict:
    from proba import kana

    if kind not in KINDS:
        raise ValueError("kind")
    claim = db.query_one("SELECT * FROM claims WHERE id = ?", (claim_id,))
    if claim is None:
        raise KeyError("claim")
    auto = kana.grade(response, claim["expected"])
    if outcome is None:
        outcome = auto["outcome"]
        src = "auto"
    else:
        if outcome not in OUTCOMES:
            raise ValueError("outcome")
        src = key_source or claim["provenance"]
    if src not in KEY_SOURCES:
        src = claim["provenance"]
    sch = db.query_one("SELECT * FROM schedule WHERE claim_id = ?", (claim_id,))
    last = db.query_one(
        "SELECT * FROM probe_attempts WHERE claim_id = ? ORDER BY at DESC LIMIT 1",
        (claim_id,),
    )
    t = schedule.now()
    last_at = last["at"] if last else None
    last_idx = last["attempt_index"] if last else None
    idx = schedule.attempt_index(t, last_at, last_idx)
    delay = schedule.delay_hours(t, last_at, claim["created_at"])
    early = bool(sch and sch["early_pull"])
    pid = _id()
    db.execute(
        "INSERT INTO probe_attempts (id, claim_id, at, attempt_index, delay_hours, "
        "outcome, confidence, kind, key_source, response, early) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            pid,
            claim_id,
            t,
            idx,
            delay,
            outcome,
            confidence,
            kind,
            src,
            (response or "").strip(),
            1 if early else 0,
        ),
    )
    if early and outcome == "pass":
        held = sch["held_due_at"] if sch and sch["held_due_at"] else None
        due = held if held and held > t else schedule.due_at(t, sch["interval_days"])
        ease, interval = sch["ease"], sch["interval_days"]
    else:
        ease, interval = schedule.review(sch["ease"], sch["interval_days"], outcome)
        due = schedule.due_at(t, interval)
    new_status = "queued" if claim["status"] == "tonight" else claim["status"]
    if claim["status"] == "diagnostic":
        new_status = "queued"
    db.execute(
        "UPDATE schedule SET due_at = ?, ease = ?, interval_days = ?, last_outcome = ?, "
        "early_pull = 0, held_due_at = NULL WHERE claim_id = ?",
        (due, ease, interval, outcome, claim_id),
    )
    db.execute("UPDATE claims SET status = ? WHERE id = ?", (new_status, claim_id))
    try:
        from proba.capture import controller

        controller.clear_nudge()
    except Exception:
        pass
    return {
        "attempt_id": pid,
        "next": next_probe(),
        "due_at": due,
        "outcome": outcome,
        "reading": auto["reading"],
        "expected_reading": auto["expected_reading"],
        "empty": auto["empty"],
        "key_source": src,
    }


def transfer_mark(claim_id: str, used: str) -> dict:
    if used not in TRANSFER:
        raise ValueError("used")
    outcome = "pass" if used == "used" else "fail" if used == "not_used" else "partial"
    return submit_probe(
        claim_id,
        used,
        None,
        outcome,
        "transfer_zoom",
        None,
    )


def headline() -> dict:
    """First-try pass rate after ≥24h. Teacher keys are not averaged with textbook ones."""
    rows = db.query(
        """
        SELECT a.outcome, c.provenance FROM probe_attempts a
        JOIN claims c ON c.id = a.claim_id
        JOIN source_events e ON e.id = c.source_event_id
        WHERE a.attempt_index = 1
          AND a.delay_hours >= 24
          AND a.kind != 'transfer_zoom'
          AND IFNULL(a.early, 0) = 0
        ORDER BY a.at DESC
        LIMIT 200
        """
    )
    if not rows:
        return {
            "n": 0,
            "pass_rate": None,
            "note": "Пока нет отложенных первых попыток.",
        }
    teacher = [r for r in rows if r["provenance"] == "teacher"]
    use = teacher if teacher else list(rows)
    n = len(use)
    wins = sum(1 for r in use if r["outcome"] == "pass")
    note = (
        "Первая попытка после паузы ≥24 ч. Ключи учителя."
        if teacher
        else "Нет отложенных попыток по ключам учителя."
    )
    return {
        "n": n,
        "pass_rate": round(wins / n, 3),
        "note": note,
    }


def growth_series() -> dict:
    rows = db.query(
        """
        SELECT a.at, a.outcome, a.delay_hours, a.attempt_index, a.kind,
               IFNULL(a.early, 0) AS early, c.prompt_ja, c.provenance
        FROM probe_attempts a
        JOIN claims c ON c.id = a.claim_id
        ORDER BY a.at ASC
        """
    )
    delayed = [
        r
        for r in rows
        if r["attempt_index"] == 1
        and r["delay_hours"] >= 24
        and r["kind"] != "transfer_zoom"
        and not r["early"]
    ]
    teacher_delayed = [r for r in delayed if r["provenance"] == "teacher"]
    delayed = teacher_delayed if teacher_delayed else delayed
    points = []
    wins = 0
    for i, r in enumerate(delayed, start=1):
        if r["outcome"] == "pass":
            wins += 1
        points.append(
            {
                "at": r["at"],
                "prompt_ja": r["prompt_ja"],
                "outcome": r["outcome"],
                "rate": round(wins / i, 3),
            }
        )
    vanity = []
    greens = 0
    for i, r in enumerate(rows, start=1):
        if r["outcome"] == "pass":
            greens += 1
        vanity.append({"at": r["at"], "cumulative_pass": greens})
    return {
        "headline": headline(),
        "delayed_first": [dict(r) for r in delayed],
        "delayed_curve": points,
        "vanity_cumulative": vanity,
        "attempts": [dict(r) for r in rows],
        "graph": growth_graph(),
        "scatter": growth_scatter(),
        "stars": growth_starfield(),
    }


def snapshot() -> dict:
    from proba.flavor import is_atlas

    if is_atlas():
        return {
            "diagnostic_pending": False,
            "diagnostic_remaining": 0,
            "tonight": 0,
            "queued": 0,
            "proposed": 0,
            "next": None,
            "headline": {"pass_rate": None},
            "capture": {"state": "idle", "source_event_id": None, "nudge": False, "analysis": {}},
            "conflicts": 0,
            "zoom_proposed": None,
            "compute": {"device": "cpu"},
            "early_pull_used": False,
            "flavor": "atlas",
        }
    ensure_diagnostic()
    pending = diagnostic_items()
    nxt = None if pending else next_probe()
    from proba.capture import controller

    queued_row = db.query_one(
        "SELECT COUNT(*) AS n FROM claims WHERE status = 'queued'"
    )
    proposed_row = db.query_one(
        "SELECT COUNT(*) AS n FROM claims WHERE status = 'proposed'"
    )
    return {
        "diagnostic_pending": bool(pending),
        "diagnostic_remaining": len(pending),
        "tonight": _tonight_count(),
        "queued": int(queued_row["n"]) if queued_row else 0,
        "proposed": int(proposed_row["n"]) if proposed_row else 0,
        "next": nxt,
        "headline": headline(),
        "capture": controller.status(),
        "conflicts": int(
            db.query_one("SELECT COUNT(*) AS n FROM conflicts")["n"]
        ),
        "zoom_proposed": latest_zoom_proposed(),
        "compute": compute.whisper_plan(),
        "early_pull_used": early_pull_used_today(),
        "flavor": "tutor",
    }


def list_conflicts() -> list[dict]:
    rows = db.query("SELECT * FROM conflicts ORDER BY created_at DESC")
    return [dict(r) for r in rows]


def accept_proposed(claim_id: str) -> dict:
    claim = db.query_one("SELECT * FROM claims WHERE id = ?", (claim_id,))
    if claim is None:
        raise KeyError("claim")
    if claim["status"] != "proposed":
        raise ValueError("not proposed")
    twin_pair = db.query_one(
        "SELECT id FROM claims WHERE prompt_ja = ? AND expected = ? AND id != ? "
        "AND status NOT IN ('rejected', 'proposed')",
        (claim["prompt_ja"], claim["expected"], claim_id),
    )
    if twin_pair:
        if claim["provenance"] == "teacher":
            db.execute(
                "UPDATE claims SET provenance = 'teacher' WHERE id = ?",
                (twin_pair["id"],),
            )
        db.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim_id,))
        return {"ok": True, "status": "duplicate", "existing": twin_pair["id"]}
    t = schedule.now()
    tonight = _tonight_count()
    status = "tonight" if tonight < TONIGHT_CAP else "queued"
    due = _due_for_status(status, t)
    db.execute("UPDATE claims SET status = ? WHERE id = ?", (status, claim_id))
    db.execute(
        "INSERT OR IGNORE INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
        "VALUES (?,?, 2.5, 0, NULL)",
        (claim_id, due),
    )
    db.execute(
        "UPDATE schedule SET due_at = ? WHERE claim_id = ?",
        (due, claim_id),
    )
    _maybe_conflict(
        claim_id,
        claim["prompt_ja"],
        claim["expected"],
        claim["provenance"],
    )
    return {"ok": True, "status": status}


def reject_proposed(claim_id: str) -> dict:
    claim = db.query_one("SELECT * FROM claims WHERE id = ?", (claim_id,))
    if claim is None:
        raise KeyError("claim")
    db.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim_id,))
    return {"ok": True}


def accept_source_proposed(source_event_id: str) -> dict:
    rows = db.query(
        "SELECT id FROM claims WHERE source_event_id = ? AND status = 'proposed' "
        "ORDER BY created_at",
        (source_event_id,),
    )
    statuses = []
    for row in rows:
        statuses.append(accept_proposed(row["id"])["status"])
    return {
        "ok": True,
        "accepted": len(statuses),
        "tonight": statuses.count("tonight"),
        "queued": statuses.count("queued"),
    }


def latest_zoom_proposed() -> dict | None:
    event = db.query_one(
        "SELECT * FROM source_events WHERE kind = 'zoom_audio' "
        "ORDER BY started_at DESC LIMIT 1"
    )
    if event is None:
        return None
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM claims WHERE source_event_id = ? AND status = 'proposed'",
        (event["id"],),
    )
    count = int(n["n"]) if n else 0
    if count <= 0:
        return None
    return {"source_event_id": event["id"], "proposed": count}


def add_proposed(source_event_id: str, items: list[dict]) -> dict:
    event = db.query_one("SELECT * FROM source_events WHERE id = ?", (source_event_id,))
    if event is None:
        raise KeyError("event")
    stamped = []
    for raw in items:
        raw = dict(raw)
        raw["status"] = "proposed"
        stamped.append(raw)
    if not stamped:
        return {"claim_ids": []}
    # Reuse create path but attach to existing event: insert claims only.
    t = schedule.now()
    ids = []
    for raw in stamped:
        prompt_ja = (raw.get("prompt_ja") or "").strip()
        expected = (raw.get("expected") or "").strip()
        if not prompt_ja or not expected:
            continue
        if cue_leaks_key(prompt_ja, expected):
            continue
        twin = db.query_one(
            "SELECT id FROM claims WHERE source_event_id = ? AND prompt_ja = ? AND expected = ?",
            (source_event_id, prompt_ja, expected),
        )
        if twin:
            continue
        cid = _id()
        provenance = raw.get("provenance") or "model"
        if provenance not in PROVENANCE:
            provenance = "model"
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                source_event_id,
                prompt_ja,
                (raw.get("prompt_hint") or "произведите форму").strip(),
                expected,
                (raw.get("gloss_ru") or "").strip(),
                provenance,
                "proposed",
                t,
                (raw.get("tags") or "").strip(),
            ),
        )
        ids.append(cid)
    return {"claim_ids": ids}


def teacher_pack() -> dict:
    """1–3 forms for the next Zoom."""
    rows = db.query(
        """
        SELECT c.* FROM claims c
        JOIN schedule s ON s.claim_id = c.id
        WHERE c.status IN ('tonight', 'queued')
        ORDER BY
          CASE s.last_outcome WHEN 'fail' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,
          s.due_at ASC
        LIMIT 3
        """
    )
    items = [_claim_out(r) for r in rows]
    questions = [
        f"Почему «{it['prompt_ja']}» так, а не иначе?"
        for it in items
        if it
    ]
    return {"items": items, "questions": questions}


def growth_graph() -> dict:
    claims = db.query(
        "SELECT * FROM claims WHERE status NOT IN ('rejected', 'proposed', 'diagnostic')"
    )
    nodes = []
    for c in claims:
        delayed = db.query(
            "SELECT outcome FROM probe_attempts WHERE claim_id = ? AND attempt_index = 1 "
            "AND delay_hours >= 24 AND kind != 'transfer_zoom'",
            (c["id"],),
        )
        rate = None
        if delayed:
            rate = sum(1 for r in delayed if r["outcome"] == "pass") / len(delayed)
        probed = db.query_one(
            "SELECT COUNT(*) AS n FROM probe_attempts WHERE claim_id = ?",
            (c["id"],),
        )
        nodes.append(
            {
                "id": c["id"],
                "label": c["prompt_ja"][:18],
                "source_event_id": c["source_event_id"],
                "provenance": c["provenance"],
                "delayed_rate": rate,
                "probed": int(probed["n"]) if probed else 0,
            }
        )
    edges = []
    by_event: dict[str, list[str]] = {}
    for n in nodes:
        by_event.setdefault(n["source_event_id"], []).append(n["id"])
    for ids in by_event.values():
        for a, b in zip(ids, ids[1:]):
            edges.append({"from": a, "to": b})
    return {"nodes": nodes, "edges": edges}


def star_need(
    *,
    due: bool,
    tonight: bool,
    last_outcome: str | None,
    probed: int,
    in_pack: bool,
    conflict: bool,
    delayed_fail: bool = False,
) -> tuple[int, list[str]]:
    """Brightness is NEED, not mastery. A delayed fail must outshine an idle pass."""
    need = 0
    reasons: list[str] = []
    slipped = last_outcome in ("fail", "partial")
    if slipped:
        need += 3
        reasons.append("срыв после паузы" if delayed_fail else "срыв")
    if due:
        need += 3
        reasons.append("срок")
    if tonight:
        need += 2
        reasons.append("этот вечер")
    if probed <= 0 and not tonight:
        need += 2
        reasons.append("ещё не произносили")
    if in_pack and not slipped:
        need += 2
        reasons.append("к учителю")
    if conflict:
        need += 2
        reasons.append("два ключа — в пробе ключ учителя")
    if last_outcome == "pass" and not due and not tonight:
        need = max(0, need - 1)
        if not reasons:
            reasons.append("совпало и сейчас не ждёт")
    return need, reasons


def _hash01(text: str) -> float:
    n = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    return n / 0xFFFFFFFF


def _star_xyz(event_id: str, claim_id: str) -> tuple[float, float, float]:
    u = _hash01(event_id + ":u")
    v = _hash01(event_id + ":v")
    theta = u * math.tau
    phi = (v * 2 - 1) * 1.05
    cx = math.cos(phi) * math.cos(theta)
    cy = math.sin(phi)
    cz = math.cos(phi) * math.sin(theta)
    ox = (_hash01(claim_id + ":x") - 0.5) * 0.38
    oy = (_hash01(claim_id + ":y") - 0.5) * 0.38
    oz = (_hash01(claim_id + ":z") - 0.5) * 0.38
    return (cx + ox, cy + oy, cz + oz)


def growth_starfield() -> dict:
    now = schedule.now()
    pack_ids = {it["id"] for it in teacher_pack()["items"] if it}
    conflict_ids: set[str] = set()
    for row in db.query("SELECT claim_id_a, claim_id_b FROM conflicts"):
        conflict_ids.add(row["claim_id_a"])
        conflict_ids.add(row["claim_id_b"])
    claims = db.query(
        "SELECT * FROM claims WHERE status NOT IN "
        "('rejected', 'proposed', 'diagnostic', 'known')"
    )
    stars = []
    for c in claims:
        sch = db.query_one("SELECT * FROM schedule WHERE claim_id = ?", (c["id"],))
        last = db.query_one(
            "SELECT outcome FROM probe_attempts WHERE claim_id = ? AND kind != 'transfer_zoom' "
            "ORDER BY at DESC LIMIT 1",
            (c["id"],),
        )
        delayed = db.query_one(
            "SELECT outcome FROM probe_attempts WHERE claim_id = ? AND attempt_index = 1 "
            "AND delay_hours >= 24 AND kind != 'transfer_zoom' ORDER BY at DESC LIMIT 1",
            (c["id"],),
        )
        probed_row = db.query_one(
            "SELECT COUNT(*) AS n FROM probe_attempts WHERE claim_id = ? AND kind != 'transfer_zoom'",
            (c["id"],),
        )
        probed = int(probed_row["n"]) if probed_row else 0
        due = bool(sch and sch["due_at"] <= now)
        last_out = last["outcome"] if last else None
        delayed_fail = bool(delayed and delayed["outcome"] in ("fail", "partial"))
        need, reasons = star_need(
            due=due,
            tonight=c["status"] == "tonight",
            last_outcome=last_out,
            probed=probed,
            in_pack=c["id"] in pack_ids,
            conflict=c["id"] in conflict_ids and c["provenance"] == "teacher",
            delayed_fail=delayed_fail,
        )
        x, y, z = _star_xyz(c["source_event_id"], c["id"])
        stars.append(
            {
                "id": c["id"],
                "label": c["prompt_ja"][:18],
                "hint": c["prompt_hint"],
                "source_event_id": c["source_event_id"],
                "provenance": c["provenance"],
                "status": c["status"],
                "need": need,
                "reasons": reasons,
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z, 4),
            }
        )
    edges = []
    by_event: dict[str, list[str]] = {}
    for s in stars:
        by_event.setdefault(s["source_event_id"], []).append(s["id"])
    for ids in by_event.values():
        for a, b in zip(ids, ids[1:]):
            edges.append({"from": a, "to": b})
    return {"stars": stars, "edges": edges}


def growth_scatter() -> list[dict]:
    claims = db.query(
        "SELECT * FROM claims WHERE status NOT IN ('rejected', 'proposed')"
    )
    points = []
    for c in claims:
        firsts = db.query(
            "SELECT delay_hours, outcome, kind FROM probe_attempts "
            "WHERE claim_id = ? AND attempt_index = 1 ORDER BY at",
            (c["id"],),
        )
        if not firsts:
            continue
        last = firsts[-1]
        all_att = db.query(
            "SELECT kind FROM probe_attempts WHERE claim_id = ?", (c["id"],)
        )
        prod = sum(1 for r in all_att if r["kind"] == "production")
        share = prod / len(all_att) if all_att else 0
        y = 1 if last["outcome"] == "pass" else 0.5 if last["outcome"] == "partial" else 0
        points.append(
            {
                "id": c["id"],
                "label": c["prompt_ja"][:24],
                "delay_hours": last["delay_hours"],
                "first_try": y,
                "production_share": share,
                "provenance": c["provenance"],
            }
        )
    return points


def attach_transcript(source_event_id: str, text: str, language: str = "") -> dict:
    db.execute(
        "UPDATE source_events SET transcript = ?, language_hint = ? WHERE id = ?",
        (text, language or "", source_event_id),
    )
    from proba.extract import proposals_from_text
    from proba import gaps

    props = proposals_from_text(text)
    added = add_proposed(source_event_id, props) if props else {"claim_ids": []}
    gaps.propose_neighbors(text)
    return {"ok": True, "proposed": added["claim_ids"], "language": language}

