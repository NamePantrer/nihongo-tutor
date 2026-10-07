from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PackSpecTests(unittest.TestCase):
    def test_spec_ships_kanjivg_and_web(self):
        spec = (ROOT / "pack" / "proba.spec").read_text(encoding="utf-8")
        self.assertIn("kanjivg_paths.json", spec)
        self.assertIn("kanjivg_parts.json", spec)
        self.assertIn("giongo.json", spec)
        self.assertIn("compounds.json", spec)
        self.assertIn("kanji_ru.json", spec)
        self.assertIn("proba.giongo", spec)
        self.assertIn("proba.flavor", spec)
        self.assertIn("jlpt_kanji.json", spec)
        self.assertIn("proba.drills", spec)
        self.assertIn('name="Nihongo"', spec)
        from proba.brand import APP_NAME, EXE_FILE

        self.assertEqual(APP_NAME, "日本語学習アシスタント")
        self.assertEqual(EXE_FILE, "Nihongo.exe")

    def test_kanjivg_file_exists_for_onefile(self):
        blob = ROOT / "proba" / "kanjivg_paths.json"
        self.assertTrue(blob.is_file(), "pack needs this json next to strokes.py")
        self.assertGreater(blob.stat().st_size, 100_000)
        parts = ROOT / "proba" / "kanjivg_parts.json"
        self.assertTrue(parts.is_file())
        self.assertGreater(parts.stat().st_size, 10_000)
        compounds = ROOT / "proba" / "compounds.json"
        self.assertTrue(compounds.is_file(), "pack needs compounds.json next to dictionary.py")
        self.assertGreater(compounds.stat().st_size, 100_000)
        giongo = ROOT / "proba" / "giongo.json"
        self.assertTrue(giongo.is_file(), "pack needs giongo.json next to giongo.py")
        self.assertGreater(giongo.stat().st_size, 10_000)
        kanji_ru = ROOT / "proba" / "kanji_ru.json"
        self.assertTrue(kanji_ru.is_file(), "pack needs kanji_ru.json for kanji cards")
        self.assertGreater(kanji_ru.stat().st_size, 10_000)
        fill = ROOT / "proba" / "giongo_en_ru.json"
        self.assertTrue(fill.is_file(), "packer fills English on-mim with Russian lookup")
        self.assertGreater(fill.stat().st_size, 10_000)

    def test_stale_exes_are_deleted(self):
        import importlib.util
        import tempfile

        spec = importlib.util.spec_from_file_location("win_pack", ROOT / "pack" / "win_pack.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dist = Path(tmp.name)
        (dist / "Nihongo.exe").write_bytes(b"keep")
        (dist / "Benran.exe").write_bytes(b"keep")
        (dist / "Nihongo.prev.exe").write_bytes(b"old")
        (dist / "Проба.exe").write_bytes(b"old")
        (dist / "Benran.prev.exe").write_bytes(b"old")
        mod.delete_stale_exes(dist)
        self.assertTrue((dist / "Nihongo.exe").is_file())
        self.assertTrue((dist / "Benran.exe").is_file())
        self.assertFalse((dist / "Nihongo.prev.exe").is_file())
        self.assertFalse((dist / "Benran.prev.exe").is_file())
        self.assertFalse((dist / "Проба.exe").is_file())

    def test_compound_gloss_keeps_whole_words(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("pack_compounds", ROOT / "tools" / "pack_compounds.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        gloss = mod._gloss(
            [
                {
                    "gloss": [
                        {
                            "text": "1) вертеться, кружиться, вращаться; поворачиваться, ворочаться; двигаться по кругу; обходить"
                        },
                        {"text": "6) (связ.:)"},
                    ]
                }
            ]
        )
        self.assertIn("кругу", gloss)
        self.assertNotIn("1)", gloss)
        self.assertNotIn("связ", gloss)
        self.assertGreater(len(gloss), 80)
        capped = mod._cap(("вертеться " * 80).strip())
        self.assertLessEqual(len(capped), 400)
        self.assertTrue(capped.endswith("вертеться"))
