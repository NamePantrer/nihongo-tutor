"""Pick CPU vs CUDA. CTranslate2 already runs GPU kernels; extra Python threads on CUDA hurt."""

from __future__ import annotations

import os


def cpu_threads() -> int:
    n = os.cpu_count() or 4
    return max(2, min(n, 16))


def cuda_device_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def whisper_plan() -> dict:
    env_model = (os.environ.get("PROBA_WHISPER_MODEL") or "").strip()
    n = cuda_device_count()
    if n > 0:
        return {
            "device": "cuda",
            "device_index": 0,
            "compute_type": "float16",
            "model": env_model or "medium",
            "cpu_threads": cpu_threads(),
            "num_workers": 1,
            "cuda_devices": n,
        }
    return {
        "device": "cpu",
        "device_index": 0,
        "compute_type": "int8",
        "model": env_model or "tiny",
        "cpu_threads": cpu_threads(),
        "num_workers": min(4, cpu_threads()),
        "cuda_devices": 0,
    }
