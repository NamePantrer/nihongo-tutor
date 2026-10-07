from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from proba import capture, dictionary, drills, gaps, giongo, importing, jlpt, kernel, paths, plan, shot, strokes, transcribe
from proba import db as database
from proba.flavor import app_name, chrome, current, is_atlas

APP_NAME = app_name()

WEB = paths.WEB_DIR

app = FastAPI(title=APP_NAME, version="0.2.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")


class DiagnosticIn(BaseModel):
    claim_id: str
    knows: bool


class LessonItemIn(BaseModel):
    prompt_ja: str
    expected: str
    prompt_hint: str = "произведите форму"
    gloss_ru: str = ""
    provenance: str = "teacher"
    tags: str = ""


class LessonIn(BaseModel):
    title: str = ""
    notes: str = ""
    items: list[LessonItemIn] = Field(min_length=1)


class ProbeIn(BaseModel):
    claim_id: str
    response: str = ""
    confidence: float | None = None
    outcome: str | None = None
    kind: str = "production"
    key_source: str | None = None


class TransferIn(BaseModel):
    claim_id: str
    used: str


class CaptureIn(BaseModel):
    action: str
    title: str = ""


class TextIn(BaseModel):
    title: str = ""
    text: str


class PlanFillIn(BaseModel):
    text: str = ""
    level: str = ""


class IdIn(BaseModel):
    id: str
    accept: bool = True


class DictIn(BaseModel):
    q: str = ""


class StationCheckIn(BaseModel):
    id: str
    response: str = ""


class DrillLevelIn(BaseModel):
    level: str
    confirm: bool = False


class DrillCheckIn(BaseModel):
    id: str
    pairs: dict[str, str] | None = None
    response: str = ""


@app.get("/api/health")
def health():
    return {"ok": True, "flavor": current(), "name": app_name()}


@app.get("/api/meta")
def meta():
    return chrome()


def _not_atlas():
    if is_atlas():
        raise HTTPException(404, "В справочнике этого нет")


@app.get("/api/snapshot")
def snapshot():
    return kernel.snapshot()


@app.get("/api/diagnostic")
def diagnostic():
    _not_atlas()
    return {"items": kernel.diagnostic_items()}


@app.post("/api/diagnostic")
def diagnostic_answer(body: DiagnosticIn):
    _not_atlas()
    try:
        return kernel.answer_diagnostic(body.claim_id, body.knows)
    except KeyError:
        raise HTTPException(404, "Нет такого утверждения") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/lessons")
def lessons(body: LessonIn):
    _not_atlas()
    try:
        return kernel.create_lesson(
            body.title,
            body.notes,
            [item.model_dump() for item in body.items],
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/api/claims")
def claims(status: str | None = None):
    _not_atlas()
    return {"claims": kernel.list_claims(status)}


@app.get("/api/probes/next")
def probes_next():
    _not_atlas()
    return {"next": kernel.next_probe()}


@app.post("/api/probes/pull-queued")
def probes_pull_queued():
    _not_atlas()
    try:
        nxt = kernel.pull_one_queued()
    except ValueError as exc:
        if str(exc) == "already":
            raise HTTPException(409, "На сегодня уже одну раньше срока") from None
        raise HTTPException(400, str(exc)) from None
    if nxt is None:
        raise HTTPException(404, "В очереди пусто")
    return {"next": nxt}


@app.post("/api/probes")
def probes_submit(body: ProbeIn):
    _not_atlas()
    try:
        return kernel.submit_probe(
            body.claim_id,
            body.response,
            body.confidence,
            body.outcome,
            body.kind,
            body.key_source,
        )
    except KeyError:
        raise HTTPException(404, "Нет такого утверждения") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/transfer")
def transfer(body: TransferIn):
    _not_atlas()
    try:
        return kernel.transfer_mark(body.claim_id, body.used)
    except KeyError:
        raise HTTPException(404, "Нет такого утверждения") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/api/growth")
def growth():
    _not_atlas()
    return kernel.growth_series()


@app.get("/api/conflicts")
def conflicts():
    _not_atlas()
    return {"conflicts": kernel.list_conflicts()}


@app.get("/api/pack")
def pack():
    _not_atlas()
    return kernel.teacher_pack()


def _due():
    if is_atlas():
        return None
    return kernel.due_expected()


@app.get("/api/dict")
def dict_search(q: str = ""):
    return {"hits": dictionary.redact_due(dictionary.search(q, packed=True), _due())}


@app.post("/api/dict")
def dict_search_post(body: DictIn):
    return {"hits": dictionary.redact_due(dictionary.search(body.q, packed=True), _due())}


@app.get("/api/kanji")
def kanji_lookup(c: str = ""):
    page = dictionary.kanji_page(c)
    if not page:
        raise HTTPException(404, "Нет знака")
    return dictionary.redact_due(page, _due())


@app.get("/api/radical")
def radical_lookup(r: str = ""):
    page = dictionary.radical_page(r)
    if not page:
        raise HTTPException(404, "Нет 部首")
    return dictionary.redact_due(page, _due())


@app.get("/api/word")
def word_lookup(q: str = ""):
    page = dictionary.word_page(q)
    if not page:
        raise HTTPException(404, "Нет слова")
    return dictionary.redact_due(page, _due())


@app.get("/api/giongo")
def giongo_index(mora: str = "", q: str = ""):
    if (q or "").strip():
        return {"hits": giongo.search(q, limit=40), "count": giongo.count()}
    if (mora or "").strip():
        return {"hits": giongo.by_mora(mora), "mora": mora.strip(), "count": giongo.count()}
    return giongo.index()


@app.get("/api/gaps")
def list_gap():
    _not_atlas()
    return {"gaps": gaps.list_gaps()}


@app.post("/api/gaps")
def decide_gap(body: IdIn):
    _not_atlas()
    try:
        return gaps.decide_gap(body.id, body.accept)
    except KeyError:
        raise HTTPException(404, "Нет предложения") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/proposed")
def decide_proposed(body: IdIn):
    _not_atlas()
    try:
        if body.accept:
            return kernel.accept_proposed(body.id)
        return kernel.reject_proposed(body.id)
    except KeyError:
        raise HTTPException(404, "Нет такого утверждения") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/proposed/accept-source")
def accept_source_proposed(body: IdIn):
    _not_atlas()
    try:
        return kernel.accept_source_proposed(body.id)
    except KeyError:
        raise HTTPException(404, "Нет занятия") from None


@app.get("/api/capture")
def capture_status():
    _not_atlas()
    return capture.controller.status()


@app.post("/api/capture")
def capture_action(body: CaptureIn):
    _not_atlas()
    if body.action == "start":
        return capture.controller.start(body.title)
    if body.action == "pause":
        return capture.controller.pause("manual")
    if body.action == "resume":
        return capture.controller.resume()
    if body.action == "stop":
        return capture.controller.stop()
    if body.action == "nudge-ack":
        capture.controller.clear_nudge()
        return capture.controller.status()
    raise HTTPException(400, "Неизвестное действие")


@app.post("/api/capture/transcribe")
def capture_transcribe(body: IdIn):
    _not_atlas()
    row = database.query_one("SELECT * FROM source_events WHERE id = ?", (body.id,))
    if row is None:
        raise HTTPException(404, "Нет занятия")
    path = Path(row["audio_path"] or "")
    result = transcribe.transcribe_wav(path)
    if result.get("text"):
        kernel.attach_transcript(
            body.id, result["text"], result.get("language") or ""
        )
        if result.get("language"):
            capture.controller.language_hint = str(result["language"])
    return result


@app.get("/api/jlpt")
def jlpt_catalog(level: str = "", book: str = ""):
    return jlpt.catalog(level=level or None, book=book or None)


@app.get("/api/drill")
def drill_status():
    """Unofficial notebook progress. Does not mint claims or log probes."""
    return drills.status()


@app.post("/api/drill/level")
def drill_level(body: DrillLevelIn):
    return drills.set_level(body.level, confirm=body.confirm)


@app.post("/api/drill/next")
def drill_next():
    return drills.next_task()


@app.post("/api/drill/check")
def drill_check(body: DrillCheckIn):
    return drills.submit(body.id, pairs=body.pairs, response=body.response or "")


@app.get("/api/strokes")
def stroke_paths(c: str = "", level: str = ""):
    """KanjiVG outlines."""
    if (c or "").strip():
        ch = (c or "").strip()[0]
        return {
            "char": ch,
            "paths": strokes.paths_for(ch),
            "parts": strokes.parts_for(ch),
            **strokes.credit(),
        }
    if (level or "").strip():
        lv = level.strip()
        return {"level": lv, "by_char": strokes.paths_for_level(lv), **strokes.credit()}
    raise HTTPException(400, "Нужен знак или уровень")


@app.get("/api/plan")
def plan_overview(level: str = ""):
    return plan.overview(level or None)


@app.post("/api/plan/fill")
def plan_fill(body: PlanFillIn = PlanFillIn()):
    _not_atlas()
    return plan.fill(body.text or "", body.level or None)


@app.post("/api/plan/analyze")
def plan_analyze(body: PlanFillIn = PlanFillIn()):
    _not_atlas()
    return plan.analyze(body.text or "")


@app.get("/api/station")
def station_get(id: str = ""):
    page = plan.station_page(id)
    if not page:
        raise HTTPException(404, "Нет такой стоянки")
    return page


@app.post("/api/station/check")
def station_post(body: StationCheckIn):
    """Sverka with a pack example. Does not log probes or insert claims."""
    if is_atlas():
        raise HTTPException(404, "В справочнике нет проверки")
    return plan.station_check(body.id, body.response or "")


@app.post("/api/shot")
async def shot_translate(file: UploadFile = File(...)):
    """OCR a screenshot, join wraps, then translate. Does not mint claims."""
    data = await file.read()
    try:
        return await asyncio.to_thread(shot.read_image, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/shot/clip")
async def shot_clipboard():
    """Same lookup from the Windows clipboard. Atlas and tutor."""
    try:
        return await asyncio.to_thread(shot.read_clipboard)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/import/text")
def import_text(body: TextIn):
    _not_atlas()
    if not body.text.strip():
        raise HTTPException(400, "Пустой текст")
    return importing.ingest_text(body.title, body.text, "paste")


@app.post("/api/import/pdf")
async def import_pdf(file: UploadFile = File(...)):
    _not_atlas()
    dest = database.DATA_DIR / "uploads"
    dest.mkdir(exist_ok=True)
    path = dest / (file.filename or "note.pdf")
    path.write_bytes(await file.read())
    try:
        return importing.ingest_pdf(path, file.filename or "")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    candidate = WEB / path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(WEB / "index.html")
