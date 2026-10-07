from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, kernel, schedule
from proba.ids import new_id


class StarNeedTests(unittest.TestCase):
    def test_delayed_fail_outshines_idle_pass(self):
        fail, _ = kernel.star_need(
            due=False,
            tonight=False,
            last_outcome="fail",
            probed=3,
            in_pack=False,
            conflict=False,
        )
        idle, _ = kernel.star_need(
            due=False,
            tonight=False,
            last_outcome="pass",
            probed=3,
            in_pack=False,
            conflict=False,
        )
        self.assertGreater(fail, idle)
        self.assertEqual(idle, 0)

    def test_due_fail_beats_due_pass(self):
        fail, why = kernel.star_need(
            due=True,
            tonight=False,
            last_outcome="fail",
            probed=2,
            in_pack=False,
            conflict=False,
        )
        passed, _ = kernel.star_need(
            due=True,
            tonight=False,
            last_outcome="pass",
            probed=2,
            in_pack=False,
            conflict=False,
        )
        self.assertGreater(fail, passed)
        self.assertIn("срыв", " ".join(why))
        self.assertNotIn("после паузы", " ".join(why))

    def test_pause_word_only_when_delayed(self):
        _, why = kernel.star_need(
            due=False,
            tonight=False,
            last_outcome="fail",
            probed=2,
            in_pack=False,
            conflict=False,
            delayed_fail=True,
        )
        self.assertTrue(any("после паузы" in r for r in why))

    def test_tonight_unprobed_does_not_double_count(self):
        a, _ = kernel.star_need(
            due=False,
            tonight=True,
            last_outcome=None,
            probed=0,
            in_pack=False,
            conflict=False,
        )
        b, why = kernel.star_need(
            due=False,
            tonight=False,
            last_outcome=None,
            probed=0,
            in_pack=False,
            conflict=False,
        )
        self.assertEqual(a, 2)
        self.assertGreater(b, 0)
        self.assertIn("ещё не произносили", why)

    def test_unprobed_is_not_mastery_glow(self):
        need, why = kernel.star_need(
            due=False,
            tonight=False,
            last_outcome=None,
            probed=0,
            in_pack=False,
            conflict=False,
        )
        self.assertGreater(need, 0)
        self.assertIn("ещё не произносили", why)


class StarfieldPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def _event(self) -> str:
        sid = new_id()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'zoom_audio', 't', ?, ?, '')",
            (sid, t, t),
        )
        return sid

    def _claim(self, sid: str, status: str, expected: str, prompt: str) -> str:
        cid = new_id()
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, ?, 'hint', ?, '', 'teacher', ?, ?, '')",
            (cid, sid, prompt, expected, status, schedule.now()),
        )
        return cid

    def test_key_never_in_stars(self):
        sid = self._event()
        self._claim(sid, "queued", "行って", "行く")
        field = kernel.growth_starfield()
        blob = str(field)
        self.assertNotIn("行って", blob)
        self.assertNotIn("expected", field["stars"][0])
        star = field["stars"][0]
        self.assertIn("need", star)
        self.assertIn("x", star)
        self.assertIn("y", star)
        self.assertIn("z", star)

    def test_proposed_and_diagnostic_stay_off_the_sky(self):
        sid = self._event()
        self._claim(sid, "proposed", "SECRETKEY", "飲む")
        self._claim(sid, "diagnostic", "OTHERKEY", "来る")
        self._claim(sid, "known", "もうできる", "知る")
        live = self._claim(sid, "tonight", "見たい", "見る")
        field = kernel.growth_starfield()
        ids = {s["id"] for s in field["stars"]}
        self.assertEqual(ids, {live})
        self.assertNotIn("SECRETKEY", str(field))
        self.assertNotIn("OTHERKEY", str(field))
