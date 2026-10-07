from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from proba import paths

ROOT = paths.writable_root()
DATA_DIR = paths.DATA_DIR
CAPTURE_DIR = paths.CAPTURE_DIR
DB_PATH = paths.DB_PATH


def _export_paths() -> None:
    global ROOT, DATA_DIR, CAPTURE_DIR, DB_PATH
    ROOT = paths.writable_root()
    DATA_DIR = paths.DATA_DIR
    CAPTURE_DIR = paths.CAPTURE_DIR
    DB_PATH = paths.DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS source_events (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    notes TEXT NOT NULL DEFAULT '',
    audio_path TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    language_hint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    source_event_id TEXT NOT NULL REFERENCES source_events(id),
    prompt_ja TEXT NOT NULL,
    prompt_hint TEXT NOT NULL,
    expected TEXT NOT NULL,
    gloss_ru TEXT NOT NULL DEFAULT '',
    provenance TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    tags TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS probe_attempts (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(id),
    at REAL NOT NULL,
    attempt_index INTEGER NOT NULL,
    delay_hours REAL NOT NULL,
    outcome TEXT NOT NULL,
    confidence REAL,
    kind TEXT NOT NULL,
    key_source TEXT NOT NULL,
    response TEXT NOT NULL DEFAULT '',
    early INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schedule (
    claim_id TEXT PRIMARY KEY REFERENCES claims(id),
    due_at REAL NOT NULL,
    ease REAL NOT NULL,
    interval_days REAL NOT NULL,
    last_outcome TEXT,
    early_pull INTEGER NOT NULL DEFAULT 0,
    held_due_at REAL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capture_segments (
    id TEXT PRIMARY KEY,
    source_event_id TEXT NOT NULL REFERENCES source_events(id),
    path TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conflicts (
    id TEXT PRIMARY KEY,
    prompt_ja TEXT NOT NULL,
    claim_id_a TEXT NOT NULL REFERENCES claims(id),
    claim_id_b TEXT NOT NULL REFERENCES claims(id),
    expected_a TEXT NOT NULL,
    expected_b TEXT NOT NULL,
    winner TEXT NOT NULL DEFAULT 'teacher',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS gap_proposals (
    id TEXT PRIMARY KEY,
    prompt_ja TEXT NOT NULL,
    prompt_hint TEXT NOT NULL,
    expected TEXT NOT NULL,
    gloss_ru TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS drill_attempts (
    id TEXT PRIMARY KEY,
    item_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    level TEXT NOT NULL,
    at REAL NOT NULL,
    outcome TEXT NOT NULL,
    first_try INTEGER NOT NULL,
    delay_hours REAL NOT NULL,
    response TEXT NOT NULL DEFAULT ''
);
"""

_COLUMN_FIXES = (
    ("source_events", "audio_path", "TEXT NOT NULL DEFAULT ''"),
    ("source_events", "transcript", "TEXT NOT NULL DEFAULT ''"),
    ("source_events", "language_hint", "TEXT NOT NULL DEFAULT ''"),
    ("claims", "tags", "TEXT NOT NULL DEFAULT ''"),
    ("probe_attempts", "early", "INTEGER NOT NULL DEFAULT 0"),
    ("schedule", "early_pull", "INTEGER NOT NULL DEFAULT 0"),
    ("schedule", "held_due_at", "REAL"),
    ("gap_proposals", "topic_id", "TEXT NOT NULL DEFAULT ''"),
    ("gap_proposals", "level", "TEXT NOT NULL DEFAULT ''"),
    ("gap_proposals", "pack", "TEXT NOT NULL DEFAULT ''"),
    ("gap_proposals", "origin", "TEXT NOT NULL DEFAULT ''"),
)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, col, decl in _COLUMN_FIXES:
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {row[1] for row in info}
        if col not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _ensure_columns(_conn)
        _conn.commit()
    return _conn


def execute(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _lock:
        cur = connect().execute(sql, params)
        connect().commit()
        return cur


def query(sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
    with _lock:
        return list(connect().execute(sql, params).fetchall())


def query_one(sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
    with _lock:
        return connect().execute(sql, params).fetchone()


def use_path(path: Path) -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        paths.set_db_path(Path(path))
        _export_paths()
        DATA_DIR.mkdir(parents=True, exist_ok=True)


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
