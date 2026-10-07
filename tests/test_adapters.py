from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from proba.capture import stitch_wavs
from proba.extract import proposals_from_text, sentences


def _tiny_wav(path: Path, frames: int = 800) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * frames)


class StitchTests(unittest.TestCase):
    def test_concat_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.wav"
            b = Path(tmp) / "b.wav"
            out = Path(tmp) / "o.wav"
            _tiny_wav(a, 100)
            _tiny_wav(b, 50)
            stitch_wavs([a, b], out)
            with wave.open(str(out), "rb") as w:
                self.assertEqual(w.getnframes(), 150)


class ExtractTests(unittest.TestCase):
    def test_japanese_sentence(self):
        text = "今日は行きます。Hello. 水を飲みたい。"
        sents = sentences(text)
        self.assertTrue(any("行き" in s for s in sents))
        props = proposals_from_text(text)
        self.assertTrue(props)
        self.assertTrue(all(p["prompt_ja"] for p in props))


if __name__ == "__main__":
    unittest.main()
