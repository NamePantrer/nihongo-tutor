"""Screenshot → reconstructed Japanese → Russian. Lookup, not a probe.

Wraps are joined before translation so a line break is not a new word.
Does not insert claims or probe_attempts.
"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

from proba.ocr_wrap import jp_ratio, reconstruct

_MAX_BYTES = 12 * 1024 * 1024
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def _prepare(data: bytes) -> Image.Image:
    if len(data) > _MAX_BYTES:
        raise ValueError("Снимок слишком большой")
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as exc:
        raise ValueError("Это не картинка") from exc
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    w, h = im.size
    if min(w, h) < 720:
        scale = 720 / max(min(w, h), 1)
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    return im


def _await(coro):
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False
    if not running:
        return asyncio.run(coro)
    box: dict = {}
    err: list = []

    def runner() -> None:
        try:
            box["v"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001
            err.append(exc)

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()
    if err:
        raise err[0]
    if "v" not in box:
        raise RuntimeError("ocr")
    return box["v"]


def _ocr_winrt(path: Path) -> list[dict]:
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import (
        BitmapAlphaMode,
        BitmapDecoder,
        BitmapPixelFormat,
        SoftwareBitmap,
    )
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import StorageFile

    try:
        from winrt.windows.storage import FileAccessMode
    except ImportError:
        from winrt.windows.storage.streams import FileAccessMode

    async def run() -> list[dict]:
        file = await StorageFile.get_file_from_path_async(str(path))
        stream = await file.open_async(FileAccessMode.READ)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        fmt = bitmap.bitmap_pixel_format
        if fmt not in (BitmapPixelFormat.BGRA8, BitmapPixelFormat.GRAY8):
            bitmap = SoftwareBitmap.convert(
                bitmap, BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED
            )
        engine = OcrEngine.try_create_from_language(Language("ja"))
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("ocr")
        result = await engine.recognize_async(bitmap)
        words: list[dict] = []
        for line in result.lines or []:
            line_words = list(line.words) if line.words else []
            if line_words:
                for word in line_words:
                    box = word.bounding_rect
                    words.append(
                        {
                            "text": word.text or "",
                            "left": float(box.x),
                            "top": float(box.y),
                            "width": float(box.width),
                            "height": float(box.height),
                        }
                    )
            elif line.text:
                words.append(
                    {
                        "text": line.text,
                        "left": 0,
                        "top": len(words) * 20,
                        "width": 10,
                        "height": 18,
                    }
                )
        return words

    return _await(run())


def ocr_image(im: Image.Image) -> tuple[list[dict], str]:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    path = Path(tmp.name)
    tmp.close()
    try:
        im.save(path, format="PNG")
        try:
            words = _ocr_winrt(path)
            return words, "windows"
        except Exception:
            pass
        try:
            import pytesseract

            text = pytesseract.image_to_string(im, lang="jpn+eng") or ""
            words = [
                {"text": ln, "left": 0, "top": i * 24, "width": 40, "height": 20}
                for i, ln in enumerate(text.splitlines())
                if ln.strip()
            ]
            return words, "tesseract"
        except Exception:
            pass
        raise RuntimeError("ocr")
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _mt_get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise RuntimeError("translate") from exc


def _gtx(piece: str) -> str:
    q = urllib.parse.quote(piece[:4500])
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl=ja&tl=ru&dt=t&q={q}"
    )
    data = _mt_get(url)
    parts = []
    if data and data[0]:
        for chunk in data[0]:
            if chunk and chunk[0]:
                parts.append(chunk[0])
    return "".join(parts).strip()


def _mymemory(piece: str) -> str:
    q = urllib.parse.quote(piece[:500])
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=ja|ru"
    data = _mt_get(url)
    if not isinstance(data, dict):
        return ""
    block = data.get("responseData") or {}
    text = (block.get("translatedText") or "").strip()
    if not text or text.lower().startswith("query limits"):
        return ""
    return text


def translate_ru(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if jp_ratio(raw) < 0.08:
        return raw
    chunks: list[str] = []
    for para in raw.split("\n\n"):
        piece = para.strip()
        if not piece:
            continue
        ru = ""
        try:
            ru = _gtx(piece)
        except RuntimeError:
            ru = ""
        if not ru:
            try:
                ru = _mymemory(piece)
            except RuntimeError:
                ru = ""
        if not ru:
            raise RuntimeError("translate")
        chunks.append(ru)
    return "\n\n".join(chunks)


def read_image(data: bytes) -> dict:
    im = _prepare(data)
    try:
        words, engine = ocr_image(im)
    except RuntimeError as exc:
        raise ValueError(
            "Не прочитался текст. Для Windows OCR добавьте японский язык "
            "с распознаванием рукописного и экранного текста."
        ) from exc
    source = reconstruct(words=words)
    if not source.strip():
        raise ValueError("На снимке нет текста")
    err = ""
    ru = ""
    try:
        ru = translate_ru(source)
    except RuntimeError:
        err = "Текст собран, перевод сейчас не открылся."
    return {
        "source": source,
        "gloss_ru": ru,
        "engine": engine,
        "note": err,
        "kind": "shot",
    }


_CLIP_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def read_clipboard() -> dict:
    """Win32 clipboard image. WebView often hides CF_DIB from a focused text field."""
    from PIL import ImageGrab

    grabbed = ImageGrab.grabclipboard()
    if grabbed is None:
        raise ValueError("В буфере нет картинки")
    if isinstance(grabbed, list):
        for raw in grabbed:
            path = Path(str(raw))
            if path.is_file() and path.suffix.lower() in _CLIP_SUFFIX:
                return read_image(path.read_bytes())
        raise ValueError("В буфере нет картинки")
    buf = io.BytesIO()
    im = grabbed.convert("RGB") if grabbed.mode not in ("RGB", "L") else grabbed
    im.save(buf, format="PNG")
    return read_image(buf.getvalue())
