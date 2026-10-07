from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil

from proba.brand import EXE_FILE

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / EXE_FILE


def main() -> int:
    if not EXE.is_file():
        print("missing", EXE)
        return 1
    for proc in psutil.process_iter(["name", "exe"]):
        exe = proc.info.get("exe") or ""
        if exe.replace("/", "\\").endswith("dist\\" + EXE_FILE):
            proc.kill()
    time.sleep(0.8)
    child = subprocess.Popen([str(EXE)])
    print("started", child.pid, flush=True)
    last = ""
    for i in range(40):
        time.sleep(0.4)
        if child.poll() is not None:
            print("exited", child.poll(), flush=True)
            log = ROOT / "dist" / "proba-debug.log"
            if log.is_file():
                print(log.read_text(encoding="utf-8"), flush=True)
            return 1
        try:
            sock = __import__("socket").socket()
            sock.settimeout(0.4)
            sock.connect(("127.0.0.1", 8765))
            sock.close()
            with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=2) as resp:
                print("health", resp.status, resp.read().decode(), "s", round((i + 1) * 0.4, 1), flush=True)
                break
        except Exception as exc:
            last = str(exc)
    else:
        print("no health", last, flush=True)
        log = ROOT / "dist" / "proba-debug.log"
        if log.is_file():
            print(log.read_text(encoding="utf-8"), flush=True)
        return 1
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == 8765 and conn.status == "LISTEN":
            owner = psutil.Process(conn.pid)
            print("listen", conn.pid, owner.name(), owner.exe(), flush=True)
    data = ROOT / "dist" / "data"
    print("data", data.exists(), [p.name for p in data.iterdir()] if data.exists() else None, flush=True)
    with urllib.request.urlopen("http://127.0.0.1:8765/", timeout=3) as resp:
        print("index", resp.status, len(resp.read()), flush=True)
    with urllib.request.urlopen("http://127.0.0.1:8765/api/strokes?c=%E6%B0%B4", timeout=5) as resp:
        blob = resp.read().decode("utf-8")
        print("strokes", resp.status, blob[:180], flush=True)
        data = json.loads(blob)
        if len(data.get("paths") or []) < 4 or data.get("source") != "kanjivg":
            print("strokes missing in exe bundle", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
