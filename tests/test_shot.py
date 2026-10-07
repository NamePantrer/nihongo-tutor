from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from proba.shot import read_clipboard, read_image, translate_ru


class ShotLookupTests(unittest.TestCase):
    def test_garbage_bytes_are_not_a_picture(self):
        with self.assertRaises(ValueError) as ctx:
            read_image(b"not-an-image")
        self.assertIn("картинка", str(ctx.exception))

    def test_cyrillic_is_not_sent_to_mt(self):
        self.assertEqual(translate_ru("уже по-русски"), "уже по-русски")

    def test_empty_clipboard_is_honest(self):
        with patch("PIL.ImageGrab.grabclipboard", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                read_clipboard()
        self.assertIn("буфере", str(ctx.exception))

    def test_clipboard_file_list_reads_png(self):
        fd, name = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        tmp = Path(name)
        self.addCleanup(lambda: tmp.exists() and tmp.unlink())
        Image.new("RGB", (32, 32), (20, 20, 20)).save(tmp)
        with patch("PIL.ImageGrab.grabclipboard", return_value=[str(tmp)]):
            with patch("proba.shot.ocr_image", return_value=([], "windows")):
                with self.assertRaises(ValueError) as ctx:
                    read_clipboard()
        self.assertIn("нет текста", str(ctx.exception))
