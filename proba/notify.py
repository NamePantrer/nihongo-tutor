"""When a Windows toast is allowed."""

from __future__ import annotations

from proba.flavor import app_name, is_atlas

TOAST_GAP_SEC = 50 * 60
SAME_CLAIM_GAP_SEC = 3 * 60 * 60
PROMPT_MAX = 80


def quiet_hours(hour: int) -> bool:
    return hour < 8 or hour >= 23


def class_in_progress(capture: dict | None) -> bool:
    cap = capture or {}
    return cap.get("state") in ("recording", "paused") and bool(cap.get("source_event_id"))


def _clip(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= PROMPT_MAX:
        return text
    return text[: PROMPT_MAX - 1] + "…"


def delayed_retrieval(claim: dict | None) -> bool:
    if not claim:
        return False
    return bool(claim.get("last_attempt"))


def toast_body(
    claim: dict | None,
    *,
    after_class: bool,
    empty_after_class: bool,
) -> str:
    if empty_after_class:
        return (
            "Занятие кончилось. Произносить нечего — внесите форму с урока в «Занятие»."
        )
    prompt = _clip((claim or {}).get("prompt_ja") or "форму")
    hint = _clip((claim or {}).get("prompt_hint") or "")
    cue = f"«{prompt}»" + (f" ({hint})" if hint else "")
    if delayed_retrieval(claim):
        return f"{cue} ждала паузу. Откройте Пробу из трея и произнесите, как учителю."
    if after_class:
        return f"{cue} — одна форма вслух, как учителю. Ключ не в уведомлении."
    return f"{cue} на этот вечер. Произнесите вслух — не график."


def decide(
    snap: dict,
    *,
    visible: bool,
    hour: int,
    now: float,
    last_toast: float,
    last_claim: str,
    drill: dict | None = None,
) -> dict | None:
    """Return {title, body, claim_id} or None. Never includes keys, glosses, or readings."""
    if visible:
        return None
    if not is_atlas():
        if int(snap.get("diagnostic_remaining") or 0) > 0 or snap.get("diagnostic_pending"):
            return None
        cap = snap.get("capture") or {}
        if class_in_progress(cap):
            return None
    else:
        cap = {}
    after_class = bool(cap.get("nudge")) and not is_atlas()
    if quiet_hours(hour) and not after_class:
        return None
    if last_toast > 0 and now - last_toast < TOAST_GAP_SEC:
        return None
    nxt = None if is_atlas() else snap.get("next")
    if after_class and not nxt:
        cid = "nudge-empty"
        if cid == last_claim and last_toast > 0 and now - last_toast < SAME_CLAIM_GAP_SEC:
            return None
        return {
            "title": app_name(),
            "body": toast_body(None, after_class=True, empty_after_class=True),
            "claim_id": cid,
            "kind": "nudge",
            "dest": "/",
        }
    if nxt:
        cid = str(nxt.get("id") or "")
        if not cid:
            return None
        if cid == last_claim and last_toast > 0 and now - last_toast < SAME_CLAIM_GAP_SEC:
            return None
        body = toast_body(nxt, after_class=after_class, empty_after_class=False)
        if nxt.get("expected") and nxt["expected"] in body:
            body = toast_body(
                {**nxt, "prompt_ja": "форма с занятия", "prompt_hint": nxt.get("prompt_hint") or ""},
                after_class=after_class,
                empty_after_class=False,
            )
            if nxt["expected"] in body:
                body = (
                    f"Форма ждала вас. Откройте {app_name()} из трея и произнесите, как учителю."
                )
        return {"title": app_name(), "body": body, "claim_id": cid, "kind": "probe", "dest": "/"}
    if not drill or not drill.get("id"):
        return None
    did = str(drill.get("id") or "")
    if did == last_claim and last_toast > 0 and now - last_toast < SAME_CLAIM_GAP_SEC:
        return None
    body = (drill.get("body") or "Закрепление. Откройте тетрадь.").strip()
    return {
        "title": drill.get("title") or app_name(),
        "body": body,
        "claim_id": did,
        "kind": "drill",
        "dest": drill.get("dest") or "/drill",
    }
