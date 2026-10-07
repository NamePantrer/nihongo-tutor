from __future__ import annotations

import json
import os
import sys
import threading
import time

from proba import kernel, notify, paths
from proba.flavor import app_name, is_atlas, origin

URL = origin()

_visible = True
_window = None
_icon = None
_last_toast = 0.0
_last_claim = ""
_allow_quit = False
_stop = threading.Event()


def _log(msg: str) -> None:
    try:
        log = paths.writable_root() / "proba-debug.log"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(msg.rstrip() + "\n")
    except OSError:
        pass


def _dest_path():
    return paths.DATA_DIR / "open.dest"


def _write_dest(dest: str) -> None:
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _dest_path().write_text(dest or "/", encoding="utf-8")
    except OSError:
        pass


def _consume_dest() -> str:
    flag = _dest_path()
    try:
        if flag.is_file():
            val = flag.read_text(encoding="utf-8").strip()
            flag.unlink()
            return val
    except OSError:
        return ""
    return ""


def _request_show() -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths.show_signal_path().write_text("1", encoding="utf-8")


def _consume_show() -> bool:
    flag = paths.show_signal_path()
    try:
        if flag.is_file():
            flag.unlink()
            return True
    except OSError:
        return False
    return False


def _toast_app_id() -> str:
    return "Benran" if is_atlas() else "Proba"


def _register_toast_app() -> None:
    try:
        from winotify import Registry

        script = "" if getattr(sys, "frozen", False) else str(paths.writable_root() / "proba" / "launch.py")
        Registry(_toast_app_id(), executable=sys.executable, script_path=script)
    except Exception as exc:
        _log(f"toast registry: {exc}")


def _toast(title: str, body: str, claim_id: str = "") -> None:
    ico = paths.icon_png() or paths.icon_ico()
    launch = str(sys.executable) if getattr(sys, "frozen", False) else ""
    try:
        from winotify import Notification, audio

        kwargs = {
            "app_id": _toast_app_id(),
            "title": title,
            "msg": body,
            "icon": str(ico) if ico else "",
            "duration": "long",
        }
        if launch:
            kwargs["launch"] = launch
        note = Notification(**kwargs)
        note.set_audio(audio.Default, loop=False)
        note.show()
    except Exception as exc:
        _log(f"winotify: {exc}")
        if _icon is not None:
            try:
                _icon.notify(body, title)
            except Exception as tray_exc:
                _log(f"tray notify: {tray_exc}")
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (paths.DATA_DIR / "toast_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"at": time.time(), "claim_id": claim_id, "body": body},
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass


def _show_window(go_home: bool = True, dest: str = "") -> None:
    global _visible
    _visible = True
    if _window is None:
        return
    try:
        _window.show()
        _window.restore()
    except Exception as exc:
        _log(f"show: {exc}")
    route = dest or ("/" if go_home else "")
    if not route:
        return
    hash_dest = route if str(route).startswith("#") else "#" + str(route)
    try:
        _window.evaluate_js(
            f"if (window.probaOpen) window.probaOpen({hash_dest!r}); else location.hash={hash_dest!r};"
        )
    except Exception:
        pass


def _hide_window() -> None:
    global _visible
    _visible = False
    if _window is None:
        return
    try:
        _window.hide()
    except Exception as exc:
        _log(f"hide: {exc}")


def _quit() -> None:
    global _allow_quit
    _allow_quit = True
    _stop.set()
    if _icon is not None:
        try:
            _icon.stop()
        except Exception:
            pass
    if _window is not None:
        try:
            _window.destroy()
        except Exception:
            pass
    os._exit(0)


def _watch() -> None:
    global _last_toast, _last_claim
    last_due_check = 0.0
    while not _stop.wait(1.2):
        if _consume_show():
            _show_window(dest=_consume_dest() or "/")
        now = time.time()
        if now - last_due_check < 40:
            continue
        last_due_check = now
        try:
            from proba import drills

            snap = kernel.snapshot()
            hour = time.localtime(now).tm_hour
            cue = drills.toast_cue(now)
            decision = notify.decide(
                snap,
                visible=_visible,
                hour=hour,
                now=now,
                last_toast=_last_toast,
                last_claim=_last_claim,
                drill=cue,
            )
            if not decision:
                continue
            dest = decision.get("dest") or "/"
            _write_dest(dest)
            _toast(decision["title"], decision["body"], decision["claim_id"])
            _last_toast = now
            _last_claim = decision["claim_id"]
            if decision.get("kind") == "drill":
                drills.note_toast(now)
        except Exception as exc:
            _log(f"watch: {exc}")


def _tray_image():
    from PIL import Image

    png = paths.icon_png()
    if png is None:
        return Image.new("RGBA", (64, 64), (196, 92, 120, 255))
    return Image.open(png).convert("RGBA")


def _run_tray() -> None:
    global _icon
    import pystray

    items = [
        pystray.MenuItem("Открыть", lambda: _show_window(dest="/"), default=True),
        pystray.MenuItem("Тетрадь", lambda: _show_window(dest="/drill")),
    ]
    if not is_atlas():
        items.append(pystray.MenuItem("Произнести форму", lambda: _show_window(dest="/")))
    items.append(pystray.MenuItem("Выйти", lambda: _quit()))
    menu = pystray.Menu(*items)
    _icon = pystray.Icon("benran" if is_atlas() else "nihongo", _tray_image(), app_name(), menu)
    _icon.run()


def run_desktop(url: str = URL) -> None:
    global _window, _visible
    try:
        import webview
    except ImportError:
        _log("pywebview missing")
        raise

    _register_toast_app()
    _visible = True
    ico = paths.icon_ico()
    _window = webview.create_window(
        app_name(),
        url,
        width=1120,
        height=760,
        min_size=(760, 540),
        background_color="#161018",
        text_select=True,
    )
    if ico is not None:
        try:
            _window.set_icon(str(ico))  # type: ignore[attr-defined]
        except Exception:
            pass

    def on_closing() -> bool:
        if _allow_quit:
            return True
        _hide_window()
        return False

    def on_minimized() -> None:
        global _visible
        _visible = False

    def on_restored() -> None:
        global _visible
        _visible = True

    try:
        _window.events.closing += on_closing
    except Exception as exc:
        _log(f"closing hook: {exc}")
    try:
        _window.events.minimized += on_minimized
        _window.events.restored += on_restored
        _window.events.shown += on_restored
    except Exception as exc:
        _log(f"window events: {exc}")

    threading.Thread(target=_run_tray, name="proba-tray", daemon=True).start()
    threading.Thread(target=_watch, name="proba-watch", daemon=True).start()
    store = paths.DATA_DIR / "webview"
    store.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "gui": "edgechromium",
        "debug": False,
        "storage_path": str(store),
        "private_mode": True,
    }
    if ico is not None:
        kwargs["icon"] = str(ico)
    try:
        _log(f"webview start flavor={'atlas' if is_atlas() else 'tutor'} url={url}")
        try:
            webview.start(**kwargs)
        except TypeError:
            kwargs.pop("icon", None)
            webview.start(**kwargs)
        _log("webview returned")
    except Exception:
        import traceback

        _log(traceback.format_exc())
        raise
    _quit()
