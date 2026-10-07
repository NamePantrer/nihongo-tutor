from __future__ import annotations

import unittest

from proba.launch import classify_listener


class ListenerClassifyTests(unittest.TestCase):
    def test_frozen_benran_is_desktop(self):
        self.assertEqual(
            classify_listener("Benran.exe", r"C:\dist\Benran.exe", []),
            "desktop",
        )

    def test_source_launch_is_desktop(self):
        self.assertEqual(
            classify_listener(
                "python.exe",
                r"C:\venv\Scripts\python.exe",
                ["python.exe", "-m", "proba.launch", "--atlas"],
            ),
            "desktop",
        )

    def test_bare_uvicorn_is_stray_not_a_window(self):
        self.assertEqual(
            classify_listener(
                "python.exe",
                r"C:\venv\Scripts\python.exe",
                ["python.exe", "-m", "uvicorn", "proba.main:app", "--port", "8766"],
            ),
            "stray",
        )

    def test_unrelated_is_other(self):
        self.assertEqual(
            classify_listener("chrome.exe", r"C:\Chrome\chrome.exe", ["chrome.exe"]),
            "other",
        )
