from __future__ import annotations

from pathlib import Path

from proba import extract, kernel
from proba.ids import new_id
from proba import db, schedule


def ingest_text(title: str, text: str, kind: str = "paste") -> dict:
    if kind not in ("paste", "pdf"):
        kind = "paste"
    t = schedule.now()
    eid = new_id()
    db.execute(
        "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes, transcript) "
        "VALUES (?, ?, ?, ?, ?, '', ?)",
        (eid, kind, title.strip() or "Текст", t, t, text),
    )
    props = extract.proposals_from_text(text)
    added = kernel.add_proposed(eid, props) if props else {"claim_ids": []}
    from proba import plan

    plan.save_paste(text)
    return {
        "source_event_id": eid,
        "proposed": added.get("claim_ids", []),
        "preview": props[:8],
    }


def ingest_pdf(path: Path, title: str = "") -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf не установлен") from exc
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages[:40]:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    return ingest_text(title or path.name, text, kind="pdf")
