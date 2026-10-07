from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proba.brand import APP_NAME, ATLAS_EXE, ATLAS_NAME, EXE_FILE, OLD_EXE_FILES

EXE = ROOT / "dist" / EXE_FILE
ATLAS = ROOT / "dist" / ATLAS_EXE


def stop_frozen() -> None:
    import psutil

    names = {EXE_FILE, ATLAS_EXE, *OLD_EXE_FILES}
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        exe = (proc.info.get("exe") or "").replace("/", "\\")
        name = proc.info.get("name") or ""
        if name in names or any(exe.endswith("\\" + n) for n in names):
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    from proba.flavor import ATLAS_PORT, TUTOR_PORT

    ports = {ATLAS_PORT, TUTOR_PORT}
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception:
        conns = []
    for conn in conns:
        if not (conn.laddr and conn.laddr.port in ports and conn.status == "LISTEN" and conn.pid):
            continue
        try:
            proc = psutil.Process(conn.pid)
            cmd = " ".join(proc.cmdline()).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if "uvicorn" in cmd and "proba.main" in cmd:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    time.sleep(1.2)
    dist = ROOT / "dist"
    if dist.is_dir():
        for path in dist.glob("*.exe"):
            try:
                path.unlink()
                print("removed", path)
            except OSError as exc:
                print("locked", path, exc)
                prev = path.with_name(path.stem + ".prev.exe")
                try:
                    if prev.is_file() and prev != path:
                        prev.unlink()
                    path.replace(prev)
                except OSError:
                    pass
    delete_stale_exes()


def copy_atlas() -> None:
    if not EXE.is_file():
        raise SystemExit(f"missing exe: {EXE}")
    shutil.copy2(EXE, ATLAS)
    print("exe", ATLAS, ATLAS.stat().st_size)


KEEP_EXE = {EXE_FILE, ATLAS_EXE}


def delete_stale_exes(folder: Path | None = None) -> None:
    dist = folder or (ROOT / "dist")
    if not dist.is_dir():
        return
    for path in dist.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name in KEEP_EXE:
            continue
        if name.endswith(".exe") or name.endswith(".lnk"):
            try:
                path.unlink()
                print("removed", path)
            except OSError as exc:
                print("keep", path, exc)


def remove_shortcuts() -> None:
    start_dir = (
        Path(os.environ.get("APPDATA", str(Path.home())))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )
    names = [
        "Nihongo.lnk",
        "Benran.lnk",
        "Проба.lnk",
        f"{APP_NAME}.lnk",
        f"{ATLAS_NAME}.lnk",
    ]
    for folder in (Path.home() / "Desktop", start_dir):
        for name in names:
            path = folder / name
            if path.is_file():
                path.unlink()
                print("removed", path)


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "all"
    if cmd in ("stop", "all"):
        stop_frozen()
    if cmd in ("copy", "all"):
        copy_atlas()
        delete_stale_exes()
        remove_shortcuts()
    if cmd in ("tidy", "remove-shortcuts"):
        delete_stale_exes()
        remove_shortcuts()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
