from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, jlpt, strokes
from proba.ids import new_id


class StrokeLookupTests(unittest.TestCase):
    def test_water_has_kanjivg_strokes(self):
        paths = strokes.paths_for("水")
        self.assertGreaterEqual(len(paths), 4)
        self.assertTrue(all(p.startswith("M") for p in paths))
        self.assertEqual(strokes.credit()["source"], "kanjivg")

    def test_ichi_is_one_stroke(self):
        self.assertEqual(len(strokes.paths_for("一")), 1)

    def test_non_kanji_is_empty(self):
        self.assertEqual(strokes.paths_for("a"), [])
        self.assertEqual(strokes.paths_for(""), [])
        self.assertEqual(strokes.parts_for("a"), [])

    def test_rest_splits_into_two_parts(self):
        parts = strokes.parts_for("休")
        self.assertGreaterEqual(len(parts), 2)
        glyphs = {(p.get("element") or "") + (p.get("original") or "") for p in parts}
        blob = "".join(glyphs)
        self.assertTrue("人" in blob or "亻" in blob)
        self.assertIn("木", blob)

    def test_water_has_no_fake_split(self):
        self.assertEqual(strokes.parts_for("水"), [])

    def test_n5_level_includes_bank_chars(self):
        by = strokes.paths_for_level("N5")
        self.assertIn("日", by)
        self.assertIn("人", by)
        self.assertGreaterEqual(len(by), 70)

    def test_lookup_does_not_insert_claims(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db.use_path(Path(tmp.name) / "t.db")
        self.addCleanup(lambda: db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db"))
        before = len(db.query("SELECT id FROM claims"))
        strokes.paths_for("行")
        strokes.paths_for_level("N5")
        strokes.parts_for("休")
        jlpt.catalog("N5")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        sid = new_id()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', 1, 1, '')",
            (sid,),
        )
        self.assertFalse(db.query("SELECT id FROM probe_attempts"))


if __name__ == "__main__":
    unittest.main()
