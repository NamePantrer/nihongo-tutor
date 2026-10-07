from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, jlpt
from proba.ids import new_id


class JlptCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_catalog_does_not_insert_claims(self):
        before = len(db.query("SELECT id FROM claims"))
        data = jlpt.catalog("N5")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        self.assertTrue(data["unofficial"])
        self.assertEqual(data["level"], "N5")
        self.assertEqual(data["levels"], ["N5", "N4", "N3", "N2", "N1"])
        self.assertGreaterEqual(len(data["kanji"]), 70)
        self.assertGreaterEqual(len(data["topics"]), 8)
        self.assertTrue(all("expected" not in hit for t in data["topics"] for hit in t["hits"]))
        self.assertNotIn("books", data)

    def test_unknown_level_falls_back_to_n5(self):
        data = jlpt.catalog("N9")
        self.assertEqual(data["level"], "N5")

    def test_n3_takes_pointo_not_listening_titles(self):
        before = len(db.query("SELECT id FROM claims"))
        data = jlpt.catalog("N3")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        titles = [t["title"] for t in data["topics"]]
        self.assertTrue(any("こと" in t and "の" in t for t in titles))
        self.assertFalse(any(t.startswith("1. もしもし") or t == "もしもし" for t in titles))
        self.assertLess(len(data["topics"]), 40)
        self.assertFalse(any("あいさつのあとは" in t for t in titles))

    def test_old_book_hash_maps_to_a_level(self):
        self.assertEqual(jlpt.catalog(book="manabou1")["level"], "N5")
        self.assertEqual(jlpt.catalog(book="kaiwa")["level"], "N3")
        n5 = jlpt.catalog(book="kanji", level="N4")
        self.assertEqual(n5["level"], "N4")

    def test_overlay_skips_proposed_and_known(self):
        sid = new_id()
        t = 1.0
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        for status, prompt in (("proposed", "行って"), ("known", "見て")):
            db.execute(
                "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
                "gloss_ru, provenance, status, created_at, tags) "
                "VALUES (?, ?, ?, 'て-форма', '', '', 'self', ?, ?, 'te-form')",
                (new_id(), sid, prompt, status, t),
            )
        data = jlpt.catalog("N5")
        te = next(row for row in data["topics"] if row["id"] == "n5-te")
        self.assertEqual(te["hits"], [])

    def test_marks_kanji_from_claims_not_as_insert(self):
        sid = new_id()
        t = 1.0
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        cid = new_id()
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, '行く', 'て-форма', '行って', '', 'teacher', 'tonight', ?, 'te-form')",
            (cid, sid, t),
        )
        data = jlpt.catalog("N5")
        self.assertEqual(len(db.query("SELECT id FROM claims")), 1)
        owned = {k["c"] for k in data["kanji"] if k["in_claims"]}
        self.assertIn("行", owned)
        te = next(row for row in data["topics"] if row["id"] == "n5-te")
        self.assertTrue(any(h["prompt_ja"] == "行く" for h in te["hits"]))
        self.assertTrue(all("expected" not in h for h in te["hits"]))
