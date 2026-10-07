from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, drills, flavor, kernel, notify
from proba.ids import new_id
from proba.notify import decide


class DrillNotebookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")
        flavor.configure(flavor=flavor.TUTOR)
        drills.reset_banks()

    def tearDown(self):
        flavor.configure(flavor=flavor.TUTOR)
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_set_level_does_not_insert_claims(self):
        before = len(db.query("SELECT id FROM claims"))
        drills.set_level("N5")
        self.assertEqual(drills.level(), "N5")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        st = drills.status()
        self.assertTrue(st["unofficial"])
        self.assertGreater(st["progress"]["kanji"]["total"], 20)
        self.assertGreater(st["progress"]["words"]["total"], 10)
        self.assertGreater(st["progress"]["grammar"]["total"], 5)

    def test_change_level_needs_confirm(self):
        drills.set_level("N5")
        r = drills.set_level("N4")
        self.assertTrue(r.get("need_confirm"))
        self.assertEqual(drills.level(), "N5")
        r = drills.set_level("N4", confirm=True)
        self.assertTrue(r.get("ok"))
        self.assertEqual(drills.level(), "N4")

    def test_n5_banks_are_russian(self):
        drills.set_level("N5")
        words = drills._word_items("N5")
        heads = {w["head"] for w in words}
        self.assertIn("行く", heads)
        blob = " ".join(w["right"] for w in words)
        self.assertNotRegex(blob, r"[A-Za-z]{3,}")
        kanji = drills._kanji_items("N5")
        seven = next(k for k in kanji if k["head"] == "七")
        self.assertIn("семь", seven["right"])
        self.assertNotIn("Seven", seven["right"])

    def test_read_task_does_not_leak_kana(self):
        drills.set_level("N5")
        drills._meta_set(drills._META_KIND, "2")
        nxt = drills.next_task()
        self.assertTrue(nxt.get("ok"))
        if nxt.get("task") and nxt["task"]["kind"] == "read_word":
            self.assertNotIn("expected", nxt["task"])
            self.assertNotIn("kana", nxt["task"])
            self.assertTrue(nxt["task"].get("surface"))

    def test_matching_grades_without_probes(self):
        drills.set_level("N5")
        drills._meta_set(drills._META_KIND, "0")
        nxt = drills.next_task()
        task = nxt["task"]
        self.assertIn(task["kind"], ("match_word", "match_kanji", "match_grammar"))
        sess = drills._session()
        pairs = {}
        for lid, key in sess["map_l"].items():
            rid = next(r for r, k in sess["map_r"].items() if k == key)
            pairs[lid] = rid
        r = drills.submit(task["id"], pairs=pairs)
        self.assertEqual(r["passed"], r["total"])
        self.assertFalse(r["logged"])
        self.assertEqual(len(db.query("SELECT id FROM probe_attempts")), 0)
        self.assertEqual(len(db.query("SELECT id FROM claims")), 0)

    def test_excellent_needs_delay_and_can_fall(self):
        key = "k:七"
        t0 = 1_000_000.0
        db.execute(
            "INSERT INTO drill_attempts (id, item_key, kind, level, at, outcome, first_try, delay_hours, response) "
            "VALUES (?, ?, 'match_kanji', 'N5', ?, 'pass', 1, 0, '')",
            (new_id(), key, t0),
        )
        self.assertFalse(drills.is_excellent(key))
        db.execute(
            "INSERT INTO drill_attempts (id, item_key, kind, level, at, outcome, first_try, delay_hours, response) "
            "VALUES (?, ?, 'match_kanji', 'N5', ?, 'pass', 1, 18, '')",
            (new_id(), key, t0 + 19 * 3600),
        )
        self.assertTrue(drills.is_excellent(key))
        db.execute(
            "INSERT INTO drill_attempts (id, item_key, kind, level, at, outcome, first_try, delay_hours, response) "
            "VALUES (?, ?, 'match_kanji', 'N5', ?, 'fail', 1, 0, '')",
            (new_id(), key, t0 + 40 * 3600),
        )
        self.assertFalse(drills.is_excellent(key))

    def test_toast_has_no_gloss_or_reading(self):
        drills.set_level("N5")
        cue = drills.toast_cue()
        self.assertIsNotNone(cue)
        body = cue["body"]
        self.assertIn("N5", body)
        self.assertNotIn("行って", body)
        self.assertNotIn("семь", body)
        self.assertNotIn("いく", body)
        self.assertNotIn("идти", body)

    def test_offer_does_not_auto_advance(self):
        self.assertEqual(drills.next_level("N5"), "N4")
        self.assertIsNone(drills.next_level("N1"))
        drills.set_level("N5")
        self.assertFalse(drills.status()["complete"])
        self.assertIsNone(drills.status()["offer"])


class DrillNotifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")
        flavor.configure(flavor=flavor.TUTOR)

    def tearDown(self):
        flavor.configure(flavor=flavor.TUTOR)
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_probe_wins_over_drill(self):
        drill = {
            "id": "drill:N5:match_word",
            "body": "Закрепление N5. Откройте тетрадь — соедините четыре слова.",
            "title": "x",
            "dest": "/drill",
        }
        got = decide(
            {
                "diagnostic_pending": False,
                "diagnostic_remaining": 0,
                "next": {
                    "id": "c1",
                    "prompt_ja": "行く",
                    "prompt_hint": "て-форма",
                    "expected": "行って",
                    "last_attempt": None,
                },
                "capture": {"state": "idle", "source_event_id": None, "nudge": False},
            },
            visible=False,
            hour=12,
            now=1000,
            last_toast=0,
            last_claim="",
            drill=drill,
        )
        self.assertEqual(got["claim_id"], "c1")
        self.assertEqual(got["kind"], "probe")
        self.assertNotIn("тетрадь", got["body"])
        self.assertNotIn("行って", got["body"])

    def test_atlas_may_toast_drill(self):
        flavor.configure(flavor=flavor.ATLAS)
        drill = {
            "id": "drill:N5:read_word",
            "body": "Закрепление N5. Откройте тетрадь — напишите чтение.",
            "title": "日本語便覧",
            "dest": "/drill",
        }
        got = decide(
            kernel.snapshot(),
            visible=False,
            hour=12,
            now=1000,
            last_toast=0,
            last_claim="",
            drill=drill,
        )
        self.assertIsNotNone(got)
        self.assertEqual(got["kind"], "drill")
        self.assertEqual(got["dest"], "/drill")
        self.assertNotIn("いく", got["body"])

    def test_after_class_empty_still_beats_drill(self):
        drill = {
            "id": "drill:N5:match_word",
            "body": "Закрепление N5. Откройте тетрадь.",
            "title": "x",
            "dest": "/drill",
        }
        got = decide(
            {
                "diagnostic_pending": False,
                "diagnostic_remaining": 0,
                "next": None,
                "capture": {"state": "idle", "source_event_id": None, "nudge": True},
            },
            visible=False,
            hour=21,
            now=1000,
            last_toast=0,
            last_claim="",
            drill=drill,
        )
        self.assertIn("нечего", got["body"])
        self.assertNotEqual(got["kind"], "drill")


if __name__ == "__main__":
    unittest.main()
