from __future__ import annotations

import threading
import wave
from pathlib import Path

from proba import db, schedule
from proba.ids import new_id

SAMPLE_RATE = 16000
RECONNECT_LIMIT = 25 * 60
ZOOM_GONE_GRACE = 8


def zoom_running() -> bool:
    try:
        import psutil
    except ImportError:
        return False
    names = {"zoom.exe", "cpthost.exe", "zoom"}
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name in names:
            return True
    return False


def stitch_wavs(paths: list[Path], out: Path) -> Path:
    if not paths:
        raise ValueError("no segments")
    params = None
    chunks: list[bytes] = []
    for path in paths:
        with wave.open(str(path), "rb") as src:
            cur = src.getparams()
            if params is None:
                params = cur
            elif (cur.nchannels, cur.sampwidth, cur.framerate) != (
                params.nchannels,
                params.sampwidth,
                params.framerate,
            ):
                raise ValueError("segment format mismatch")
            chunks.append(src.readframes(src.getnframes()))
    out.parent.mkdir(parents=True, exist_ok=True)
    assert params is not None
    with wave.open(str(out), "wb") as dst:
        dst.setparams(params)
        for chunk in chunks:
            dst.writeframes(chunk)
    return out


class CaptureController:
    def __init__(self) -> None:
        self.state = "idle"
        self.source_event_id: str | None = None
        self.zoom_seen = False
        self.paused_at: float | None = None
        self.nudge = False
        self.last_error = ""
        self.language_hint = ""
        self.last_event_id: str | None = None
        self.analysis: dict = {
            "state": "idle",
            "device": "",
            "model": "",
            "proposed": 0,
            "error": "",
        }
        self._stop = threading.Event()
        self._writer_stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._watch: threading.Thread | None = None
        self._wave: wave.Wave_write | None = None
        self._current_path: Path | None = None
        self._lock = threading.Lock()

    def status(self) -> dict:
        return {
            "state": self.state,
            "source_event_id": self.source_event_id,
            "zoom_running": zoom_running(),
            "nudge": self.nudge,
            "last_error": self.last_error,
            "language_hint": self.language_hint,
            "reconnect_limit_s": RECONNECT_LIMIT,
            "analysis": dict(self.analysis),
            "last_event_id": self.last_event_id,
        }

    def start(self, title: str = "") -> dict:
        with self._lock:
            if self.state == "recording":
                return self.status()
            paused = self.state == "paused" and bool(self.source_event_id)
        if paused:
            return self.resume()
        with self._lock:
            t = schedule.now()
            eid = new_id()
            db.execute(
                "INSERT INTO source_events (id, kind, title, started_at, notes) "
                "VALUES (?, 'zoom_audio', ?, ?, '')",
                (eid, title.strip() or "Zoom-занятие", t),
            )
            self.source_event_id = eid
            self.nudge = False
            self.last_error = ""
            self._open_segment("start")
            self.state = "recording"
            self._stop.clear()
            self._watch = threading.Thread(target=self._watch_zoom, daemon=True)
            self._watch.start()
            return self.status()

    def pause(self, reason: str = "manual") -> dict:
        with self._lock:
            if self.state != "recording":
                return self.status()
            self._close_segment(reason)
            self.state = "paused"
            self.paused_at = schedule.now()
            return self.status()

    def resume(self) -> dict:
        with self._lock:
            if self.state != "paused" or not self.source_event_id:
                return self.status()
            self._open_segment("resume")
            self.state = "recording"
            self.paused_at = None
            return self.status()

    def stop(self) -> dict:
        with self._lock:
            if self.state == "recording":
                self._close_segment("end")
            self._stop.set()
            eid = self.source_event_id
            self.state = "idle"
            self.paused_at = None
        if eid:
            self._stitch_and_attach(eid)
            self.nudge = True
            self.last_event_id = eid
            threading.Thread(
                target=self._analyze_event, args=(eid,), daemon=True, name="proba-analyze"
            ).start()
        self.source_event_id = None
        return self.status()

    def clear_nudge(self) -> None:
        self.nudge = False

    def _open_segment(self, reason: str) -> None:
        assert self.source_event_id
        t = schedule.now()
        sid = new_id()
        path = db.CAPTURE_DIR / f"{self.source_event_id}_{sid}.wav"
        self._current_path = path
        self._writer_stop.clear()
        self._wave = wave.open(str(path), "wb")
        self._wave.setnchannels(1)
        self._wave.setsampwidth(2)
        self._wave.setframerate(SAMPLE_RATE)
        db.execute(
            "INSERT INTO capture_segments (id, source_event_id, path, started_at, reason) "
            "VALUES (?,?,?,?,?)",
            (sid, self.source_event_id, str(path), t, reason),
        )
        self._thread = threading.Thread(target=self._write_loop, daemon=True)
        self._thread.start()

    def _close_segment(self, reason: str) -> None:
        self._writer_stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._wave:
            self._wave.close()
            self._wave = None
        if self._current_path and self.source_event_id:
            db.execute(
                "UPDATE capture_segments SET ended_at = ?, reason = reason || ? "
                "WHERE path = ?",
                (schedule.now(), f"|{reason}", str(self._current_path)),
            )
        self._current_path = None

    def _write_loop(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError:
            self.last_error = "Нет sounddevice/numpy. Запись — тишина-заглушка, вставьте файл вручную."
            self._write_silence()
            return
        try:
            extra = None
            try:
                extra = sd.WasapiSettings(loopback=True)
            except Exception:
                extra = None
            device = None
            try:
                device = sd.default.device[1]
            except Exception:
                device = None

            def callback(indata, frames, time_info, status):  # noqa: ARG001
                if self._wave and not self._writer_stop.is_set():
                    pcm = np.clip(indata[:, 0 if indata.ndim > 1 else ...], -1, 1)
                    if getattr(pcm, "ndim", 1) > 1:
                        pcm = pcm.mean(axis=1)
                    self._wave.writeframes((pcm * 32767).astype(np.int16).tobytes())

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=callback,
                device=device,
                extra_settings=extra,
            ):
                while not self._writer_stop.is_set():
                    self._writer_stop.wait(0.2)
        except Exception as exc:
            self.last_error = str(exc)
            self._write_silence()

    def _write_silence(self) -> None:
        while not self._writer_stop.is_set():
            if self._wave:
                self._wave.writeframes(b"\x00\x00" * 1600)
            self._writer_stop.wait(0.1)

    def _watch_zoom(self) -> None:
        gone_since: float | None = None
        while not self._stop.is_set():
            self._stop.wait(2)
            if self.state == "idle":
                break
            running = zoom_running()
            if running:
                self.zoom_seen = True
                gone_since = None
                if self.state == "paused" and self.paused_at:
                    if schedule.now() - self.paused_at <= RECONNECT_LIMIT:
                        self.resume()
                continue
            if self.state == "recording":
                if gone_since is None:
                    gone_since = schedule.now()
                elif schedule.now() - gone_since >= ZOOM_GONE_GRACE:
                    self.pause("zoom_gone")
                    gone_since = None

    def _stitch_and_attach(self, eid: str) -> None:
        rows = db.query(
            "SELECT path FROM capture_segments WHERE source_event_id = ? "
            "ORDER BY started_at",
            (eid,),
        )
        paths = [Path(r["path"]) for r in rows if Path(r["path"]).exists()]
        if not paths:
            return
        out = db.CAPTURE_DIR / f"{eid}_full.wav"
        try:
            stitch_wavs(paths, out)
            db.execute(
                "UPDATE source_events SET ended_at = ?, audio_path = ? WHERE id = ?",
                (schedule.now(), str(out), eid),
            )
        except Exception as exc:
            self.last_error = str(exc)

    def _analyze_event(self, eid: str) -> None:
        from proba import kernel, transcribe
        from proba.compute import whisper_plan

        plan = whisper_plan()
        self.analysis = {
            "state": "running",
            "device": plan["device"],
            "model": plan["model"],
            "proposed": 0,
            "error": "",
        }
        row = db.query_one("SELECT audio_path FROM source_events WHERE id = ?", (eid,))
        path = Path((row["audio_path"] if row else "") or "")
        result = transcribe.transcribe_wav(path)
        if not result.get("ok"):
            err = result.get("error") or "анализ не удался"
            self.analysis = {
                "state": "error",
                "device": result.get("device") or plan["device"],
                "model": result.get("model") or plan["model"],
                "proposed": 0,
                "error": err,
            }
            self.last_error = err
            return
        attached = kernel.attach_transcript(
            eid, result.get("text") or "", result.get("language") or ""
        )
        if result.get("language"):
            self.language_hint = str(result["language"])
        self.analysis = {
            "state": "done",
            "device": result.get("device") or plan["device"],
            "model": result.get("model") or plan["model"],
            "proposed": len(attached.get("proposed") or []),
            "error": "",
        }


controller = CaptureController()
