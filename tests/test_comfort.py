from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, dictionary, kernel, schedule
from proba.ids import new_id


class CueLeakTests(unittest.TestCase):
    def test_same_surface_is_a_leak(self):
        self.assertTrue(kernel.cue_leaks_key("あげる", "あげる"))

    def test_hint_must_not_contain_the_key(self):
        self.assertNotIn("あげる", kernel.scrub_hint("あげる / от меня", "あげる"))
        self.assertEqual(
            kernel.scrub_hint("て-форма", "行って"),
            "て-форма",
        )

    def test_extract_give_hint_has_no_surface(self):
        from proba.extract import _hint_for

        self.assertNotIn("あげる", _hint_for("あげる", "давать (от меня)"))


class DueDictRedactTests(unittest.TestCase):
    def test_te_form_is_dropped_from_iku_page(self):
        page = dictionary.word_page("行く")
        self.assertTrue(any(f["surface"] == "行って" for f in page["forms"]))
        red = dictionary.redact_due(page, "行って")
        self.assertFalse(any(f["surface"] == "行って" for f in red["forms"]))
        self.assertTrue(any(f["surface"] == "行った" for f in red["forms"]))

    def test_compound_is_dropped_from_kanji_page(self):
        page = dictionary.kanji_page("行")
        self.assertTrue(any(c["head"] == "行って" for c in page["compounds"]))
        red = dictionary.redact_due(page, "行って")
        self.assertFalse(any(c["head"] == "行って" for c in red["compounds"]))

    def test_search_itte_is_redacted_while_due(self):
        hits = dictionary.search("itte")
        self.assertTrue(any(h.get("kana") == "いって" or h.get("head") == "行って" for h in hits))
        red = dictionary.redact_due(hits, "行って")
        self.assertFalse(any(h.get("head") == "行って" or h.get("kana") == "いって" for h in red))

    def test_nothing_due_keeps_the_form(self):
        page = dictionary.word_page("行く")
        red = dictionary.redact_due(page, "")
        self.assertTrue(any(f["surface"] == "行って" for f in red["forms"]))


class DictRomajiTests(unittest.TestCase):
    def test_itte_finds_te_form(self):
        hits = dictionary.search("itte")
        self.assertTrue(any(h["kana"] == "いって" for h in hits))


class PullQueuedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_pull_makes_one_due_not_the_whole_queue(self):
        sid = new_id()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        ids = []
        for prompt in ("行く", "来る"):
            cid = new_id()
            ids.append(cid)
            db.execute(
                "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
                "gloss_ru, provenance, status, created_at, tags) "
                "VALUES (?, ?, ?, 'hint', 'x', '', 'teacher', 'queued', ?, '')",
                (cid, sid, prompt, t),
            )
            db.execute(
                "INSERT INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
                "VALUES (?, ?, 2.5, 1, 'pass')",
                (cid, t + 86400 + len(ids)),
            )
        self.assertIsNone(kernel.next_probe())
        pulled = kernel.pull_one_queued()
        self.assertIsNotNone(pulled)
        self.assertEqual(pulled["id"], ids[0])
        self.assertIsNotNone(kernel.next_probe())
        still = db.query("SELECT status FROM claims WHERE status = 'queued'")
        self.assertEqual(len(still), 2)

    def test_second_pull_same_day_is_refused(self):
        sid = new_id()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        for i, prompt in enumerate(("行く", "来る")):
            cid = new_id()
            db.execute(
                "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
                "gloss_ru, provenance, status, created_at, tags) "
                "VALUES (?, ?, ?, 'hint', 'x', '', 'teacher', 'queued', ?, '')",
                (cid, sid, prompt, t),
            )
            db.execute(
                "INSERT INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
                "VALUES (?, ?, 2.5, 3, 'pass')",
                (cid, t + 86400 * (i + 2)),
            )
        first = kernel.pull_one_queued()
        self.assertIsNotNone(first)
        kernel.submit_probe(first["id"], "x", None, "pass", "production", None)
        self.assertIsNone(kernel.next_probe())
        with self.assertRaises(ValueError) as ctx:
            kernel.pull_one_queued()
        self.assertEqual(str(ctx.exception), "already")

    def test_early_pass_does_not_lengthen_interval(self):
        sid = new_id()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        cid = new_id()
        held = t + 3 * 86400
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, '行く', 'hint', '行って', '', 'teacher', 'queued', ?, '')",
            (cid, sid, t),
        )
        db.execute(
            "INSERT INTO schedule (claim_id, due_at, ease, interval_days, last_outcome) "
            "VALUES (?, ?, 2.5, 3, 'pass')",
            (cid, held),
        )
        kernel.pull_one_queued()
        kernel.submit_probe(cid, "行って", None, None, "production", None)
        sch = db.query_one("SELECT * FROM schedule WHERE claim_id = ?", (cid,))
        self.assertAlmostEqual(sch["due_at"], held, delta=2)
        self.assertEqual(sch["interval_days"], 3)
        self.assertEqual(sch["early_pull"], 0)
        att = db.query_one(
            "SELECT early FROM probe_attempts WHERE claim_id = ?", (cid,)
        )
        self.assertEqual(att["early"], 1)
