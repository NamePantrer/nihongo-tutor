from __future__ import annotations

from pathlib import Path

from proba import compute

_model = None
_model_key = None


def _load(plan: dict):
    global _model, _model_key
    from faster_whisper import WhisperModel

    key = (plan["model"], plan["device"], plan["compute_type"])
    if _model is not None and _model_key == key:
        return _model
    _model = WhisperModel(
        plan["model"],
        device=plan["device"],
        device_index=plan["device_index"],
        compute_type=plan["compute_type"],
        cpu_threads=plan["cpu_threads"],
        num_workers=plan["num_workers"],
    )
    _model_key = key
    return _model


def device_info() -> dict:
    plan = compute.whisper_plan()
    return {
        "device": plan["device"],
        "model": plan["model"],
        "compute_type": plan["compute_type"],
        "cpu_threads": plan["cpu_threads"],
        "cuda_devices": plan["cuda_devices"],
    }


def transcribe_wav(path: Path) -> dict:
    if not path.exists() or path.stat().st_size < 1000:
        return {
            "ok": False,
            "text": "",
            "language": None,
            "error": "Нет звука в файле (короткий сегмент или заглушка без микрофона).",
            "device": None,
        }
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        return {
            "ok": False,
            "text": "",
            "language": None,
            "error": "faster-whisper нет в этой сборке. Запустите Пробу через run.ps1 — там расшифровка на видеокарте.",
            "device": None,
        }
    plan = compute.whisper_plan()
    tried = [plan]
    if plan["device"] == "cuda":
        tried.append({**plan, "model": "small", "compute_type": "float16"})
        tried.append(
            {
                **compute.whisper_plan(),
                "device": "cpu",
                "compute_type": "int8",
                "model": "tiny",
                "num_workers": min(4, compute.cpu_threads()),
                "cuda_devices": plan["cuda_devices"],
            }
        )
    last_err = ""
    for attempt in tried:
        try:
            model = _load(attempt)
            segments, info = model.transcribe(
                str(path),
                vad_filter=True,
                beam_size=5,
                language="ja",
            )
            text = "".join(seg.text for seg in segments).strip()
            return {
                "ok": True,
                "text": text,
                "language": getattr(info, "language", None),
                "language_probability": getattr(info, "language_probability", None),
                "error": "",
                "device": attempt["device"],
                "model": attempt["model"],
            }
        except Exception as exc:
            last_err = str(exc)
            continue
    return {
        "ok": False,
        "text": "",
        "language": None,
        "error": last_err or "Расшифровка не удалась.",
        "device": None,
    }
