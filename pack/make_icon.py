"""Convert the book PNG into a multi-size Windows .ico."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "proba-book-icon.png"
DST = ROOT / "assets" / "proba.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Нет исходной картинки: {SRC}")
    image = Image.open(SRC).convert("RGBA")
    image.save(DST, format="ICO", sizes=SIZES)
    print(f"Wrote {DST}")


if __name__ == "__main__":
    main()
