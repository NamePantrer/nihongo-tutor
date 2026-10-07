# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPEC).resolve().parent.parent

datas = [
    (str(ROOT / "web"), "web"),
    (str(ROOT / "assets" / "proba.ico"), "assets"),
    (str(ROOT / "assets" / "proba-book-icon.png"), "assets"),
    (str(ROOT / "proba" / "jlpt_kanji.json"), "proba"),
    (str(ROOT / "proba" / "kanjivg_paths.json"), "proba"),
    (str(ROOT / "proba" / "kanjivg_parts.json"), "proba"),
    (str(ROOT / "proba" / "compounds.json"), "proba"),
    (str(ROOT / "proba" / "giongo.json"), "proba"),
    (str(ROOT / "proba" / "kanji_ru.json"), "proba"),
]
datas += collect_data_files("_sounddevice_data")
datas += collect_data_files("pykakasi")
binaries = []
hidden_extra = []

try:
    from PyInstaller.utils.hooks import collect_all

    for pkg in (
        "webview",
        "pythonnet",
        "pystray",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.globalization",
        "winrt.windows.graphics.imaging",
        "winrt.windows.media.ocr",
        "winrt.windows.storage",
        "winrt.windows.storage.streams",
    ):
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden_extra += h
except Exception:
    pass

hiddenimports = (
    collect_submodules("uvicorn")
    + [
        "fastapi",
        "starlette",
        "starlette.routing",
        "pydantic",
        "multipart",
        "sounddevice",
        "numpy",
        "psutil",
        "pypdf",
        "pykakasi",
        "jaconv",
        "webview",
        "webview.platforms.edgechromium",
        "pythonnet",
        "clr_loader",
        "clr",
        "pystray",
        "pystray._win32",
        "winotify",
        "PIL",
        "proba.launch",
        "proba.brand",
        "proba.flavor",
        "proba.giongo",
        "proba.main",
        "proba.paths",
        "proba.kana",
        "proba.jlpt",
        "proba.shell",
        "proba.notify",
        "proba.strokes",
        "proba.drills",
        "proba.plan",
        "proba.packs",
        "proba.curriculum",
        "proba.extract",
        "proba.gaps",
        "proba.yarxi",
        "proba.dictionary",
        "proba.kernel",
        "proba.schedule",
        "proba.capture",
        "proba.db",
        "proba.ocr_wrap",
        "proba.shot",
        "winrt",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.globalization",
        "winrt.windows.graphics.imaging",
        "winrt.windows.media.ocr",
        "winrt.windows.storage",
        "winrt.windows.storage.streams",
    ]
    + hidden_extra
)

excludes = [
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "av",
    "huggingface_hub",
    "tokenizers",
    "torch",
    "torchaudio",
    "tensorflow",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "notebook",
    "pytest",
]

a = Analysis(
    [str(ROOT / "proba" / "launch.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Nihongo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "proba.ico"),
)
