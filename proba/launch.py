from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from multiprocessing import freeze_support
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def _bind() -> str:
    global PORT, URL
    from proba import paths
    from proba.flavor import app_name, configure, origin, port

    configure(sys.argv)
    paths.refresh()
    PORT = port()
    URL = origin()
    return app_name()


def _log_path():
    from pathlib import Path

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "proba-debug.log"
    return Path(__file__).resolve().parent.parent / "proba-debug.log"


def _log(message: str) -> None:
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except OSError:
        pass


def _health_info() -> dict | None:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=0.6) as resp:
            if resp.status != 200:
                return None
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {"ok": True}
            if isinstance(data, dict):
                data.setdefault("ok", True)
                return data
            return {"ok": True}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _health() -> bool:
    info = _health_info()
    return bool(info and info.get("ok", True))


def _port_busy() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((HOST, PORT)) == 0


def classify_listener(name: str, exe: str, cmdline: list[str] | tuple[str, ...] | str) -> str:
    """desktop = our window; stray = uvicorn without chrome; other = leave it."""
    stem = Path(exe or name or "").stem.lower()
    if stem in ("benran", "nihongo"):
        return "desktop"
    blob = cmdline.lower() if isinstance(cmdline, str) else " ".join(cmdline or []).lower()
    if "proba.launch" in blob or "launch.py" in blob:
        return "desktop"
    if "uvicorn" in blob and "proba.main" in blob:
        return "stray"
    return "other"


def _occupant() -> dict | None:
    try:
        import psutil
    except ImportError:
        return None
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception as exc:
        _log(f"net_connections: {exc}")
        return None
    for conn in conns:
        if not conn.laddr or conn.laddr.port != PORT or conn.status != "LISTEN" or not conn.pid:
            continue
        try:
            proc = psutil.Process(conn.pid)
            name = proc.name()
            try:
                exe = proc.exe() or ""
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                exe = ""
            try:
                cmd = proc.cmdline()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                cmd = []
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            _log(f"occupant: {exc}")
            return {"kind": "other", "pid": conn.pid, "label": str(conn.pid)}
        kind = classify_listener(name, exe, cmd)
        return {
            "kind": kind,
            "pid": proc.pid,
            "label": exe or name or str(proc.pid),
            "name": name,
        }
    return None


def _kill_pid(pid: int) -> None:
    import psutil

    proc = psutil.Process(pid)
    proc.terminate()
    try:
        proc.wait(3)
    except psutil.TimeoutExpired:
        proc.kill()


def _run_server() -> None:
    try:
        import uvicorn

        from proba.main import app

        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = False
        _log("uvicorn starting")
        server.run()
        _log("uvicorn stopped")
    except Exception:
        import traceback

        _log(traceback.format_exc())
        raise


def _wait_ready(seconds: float | None = None) -> bool:
    if seconds is None:
        seconds = 60.0 if getattr(sys, "frozen", False) else 12.0
    deadline = time.time() + seconds
    last = 0.0
    while time.time() < deadline:
        if _health():
            return True
        now = time.time()
        if now - last >= 5:
            _log(f"waiting health {URL}")
            last = now
        time.sleep(0.2)
    return False


def _die(text: str) -> None:
    _log("die: " + text.replace("\n", " | "))
    title = "Error"
    try:
        from proba.flavor import app_name

        title = app_name()
    except Exception:
        pass
    shown = False
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x00000010)
            shown = True
        except Exception as exc:
            _log(f"messagebox: {exc}")
    if not shown:
        try:
            import tkinter as tk
            from tkinter import messagebox

            tk.Tk().withdraw()
            messagebox.showerror(title, text)
        except Exception:
            pass
    sys.exit(1)


def _start_ui() -> None:
    try:
        from proba.shell import run_desktop

        run_desktop(URL)
    except Exception:
        import traceback

        _log(traceback.format_exc())
        _die("Окно не открылось. В трее у часов: меню → Выйти, затем запустите снова.")


def main() -> None:
    freeze_support()
    name = _bind()
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    from proba.flavor import current

    mine = current()
    _log(
        f"start flavor={mine} port={PORT} exe={sys.executable} "
        f"argv={sys.argv!r} frozen={bool(getattr(sys, 'frozen', False))}"
    )

    occ = _occupant()
    if occ:
        _log(f"occupant kind={occ['kind']} pid={occ['pid']} {occ.get('label')}")
    busy = _port_busy()
    info = _health_info() if busy else None

    if occ and occ["kind"] == "desktop" and info:
        _log("already: request_show")
        from proba.shell import _request_show

        _request_show()
        return

    if occ and occ["kind"] == "stray":
        _log(f"killing stray pid={occ['pid']}")
        try:
            _kill_pid(occ["pid"])
        except Exception as exc:
            _log(f"kill stray: {exc}")
            _die(
                f"{name}: порт {PORT} занят {occ.get('label')}. "
                "Закройте python.exe в диспетчере задач и запустите снова."
            )
        time.sleep(0.6)
        if _port_busy():
            _die(
                f"{name}: порт {PORT} всё ещё занят. "
                "Диспетчер задач → снимите python.exe, затем dist\\Benran.exe."
            )
    elif busy and info and info.get("flavor") == mine:
        _log("already: request_show (no occupant)")
        from proba.shell import _request_show

        _request_show()
        return
    elif busy:
        label = (occ or {}).get("label") or f"порт {PORT}"
        _die(
            f"{name} не отвечает. Занят {label}. "
            "В трее (у часов): меню → Выйти, или диспетчер задач."
        )

    worker = threading.Thread(target=_run_server, name="proba-uvicorn", daemon=True)
    worker.start()
    if not _wait_ready():
        err = ""
        log = _log_path()
        if log.is_file():
            err = log.read_text(encoding="utf-8")[-800:]
        _die(f"Не удалось запустить {name}.\n\n" + (err or f"Лог: {log}"))
    _start_ui()


if __name__ == "__main__":
    main()
