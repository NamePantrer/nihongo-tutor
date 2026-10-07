"""Attacks from adversarial review. Each test is the failure the product must not allow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, extract, gaps, importing, kernel, packs, plan, schedule
from proba.ids import new_id


def _lesson_claim(prompt_ja: str, expected: str, *, status="tonight", tags="", provenance="teacher"):
    sid = new_id()
    db.execute(
        "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
        "VALUES (?, 'lesson', 't', 1, 1, '')",
        (sid,),
    )
    db.execute(
        "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
        "gloss_ru, provenance, status, created_at, tags) "
        "VALUES (?, ?, ?, '', ?, '', ?, ?, 1, ?)",
        (new_id(), sid, prompt_ja, expected, provenance, status, tags),
    )


class SharedSurfaceAttestedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_iku_te_form_does_not_attest_ta_form(self):
        te = packs.pick_item("n5-te")
        self.assertEqual((te.prompt_ja, te.expected), ("行く", "行って"))
        _lesson_claim("行く", "行って", tags="te-form")
        by_id = {s["id"]: s for s in plan.stations("N5")}
        self.assertEqual(by_id["n5-te"]["coverage"], "attested")
        self.assertEqual(by_id["n5-ta"]["coverage"], "empty")
        result = plan.fill("た-форма")
        self.assertIn("n5-ta", result["created"])
        self.assertNotIn("n5-te", result["created"])

    def test_taberu_nai_does_not_attest_teiru(self):
        _lesson_claim("食べる", "食べない", tags="nai")
        by_id = {s["id"]: s for s in plan.stations("N5")}
        self.assertEqual(by_id["n5-nai"]["coverage"], "attested")
        self.assertEqual(by_id["n5-teiru"]["coverage"], "empty")
        result = plan.fill("ている")
        self.assertIn("n5-teiru", result["created"])

    def test_diagnostic_hon_does_not_attest_satsu(self):
        kernel.ensure_diagnostic()
        row = db.query_one("SELECT id FROM claims WHERE expected = '本' AND status = 'diagnostic'")
        self.assertIsNotNone(row)
        kernel.answer_diagnostic(row["id"], True)
        by_id = {s["id"]: s for s in plan.stations("N5")}
        self.assertEqual(by_id["n5-counter"]["coverage"], "empty")
        self.assertEqual(by_id["n5-aru"]["coverage"], "empty")
        result = plan.fill("Счётные суффиксы")
        self.assertIn("n5-counter", result["created"])


class FillNotCurriculumDumpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_empty_fill_does_not_insert_course_shelf(self):
        result = plan.fill("")
        self.assertEqual(result["used_course"], 0)
        self.assertGreater(result["used_open"], 0)
        self.assertNotIn("n5-desu", result["created"])
        origins = {row["origin"] for row in db.query("SELECT origin FROM gap_proposals")}
        self.assertEqual(origins, {"open"})

    def test_unmatched_fill_does_not_dump_n5_course(self):
        analyzed = plan.analyze("hello world zzzz")
        self.assertEqual(analyzed["matched"], [])
        result = plan.fill("hello world zzzz")
        self.assertEqual(result["used_course"], 0)
        self.assertNotIn("n5-desu", result["created"])

    def test_listening_paste_does_not_create_n5_course(self):
        result = plan.fill("擬音語 説明・意見・体験 会話上手")
        self.assertGreater(result["skipped_non_production"], 0)
        self.assertEqual(result["used_course"], 0)
        self.assertNotIn("n5-desu", result["created"])

    def test_n3_path_and_fill_agree_on_first_station(self):
        path = plan.overview("N3")["path"]
        created = plan.fill("", "N3")["created"]
        self.assertTrue(path)
        self.assertTrue(created)
        self.assertEqual(created[0], path[0]["id"])

    def test_analyze_seeds_last_paste_for_empty_fill(self):
        plan.analyze("ポイント20 「こと」と「の」")
        self.assertIn("こと", plan.last_paste())
        result = plan.fill("")
        self.assertEqual(result["created"][0], "p06")

    def test_priority_n5_tai_is_not_n5_ta(self):
        matched = plan.analyze("n5-tai")["matched"]
        ids = [m["id"] for m in matched]
        self.assertIn("n5-tai", ids)
        self.assertNotIn("n5-ta", ids)
        result = plan.fill("n5-tai")
        self.assertEqual(result["created"][0], "n5-tai")
        self.assertNotIn("n5-ta", result["created"])

    def test_incidental_kara_is_not_a_named_station(self):
        ids = [m["id"] for m in plan.analyze("これから行きます。")["matched"]]
        self.assertNotIn("n5-kara", ids)
        self.assertNotIn("n5-kara", plan.fill("これから行きます。")["created"])
        self.assertEqual(plan.fill("待っているところです")["used_course"], 0)

    def test_second_fill_does_not_dump_another_cap(self):
        first = plan.fill("")
        self.assertGreater(first["count"], 0)
        self.assertEqual(plan.fill("")["count"], 0)

    def test_pending_station_leaves_the_path(self):
        plan.fill("て-форма")
        self.assertNotIn("n5-te", [s["id"] for s in plan.next_path("N5")])

    def test_pointo_book_match_skips_unfillable_p01(self):
        result = plan.fill("ポイント20")
        self.assertNotIn("p01", result["created"])
        self.assertEqual(result["created"][0], "p06")


class DraftPathConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_proposed_extract_is_draft_not_empty_station(self):
        importing.ingest_text("t", "駅まで行ってください。")
        by_id = {s["id"]: s for s in plan.stations("N5")}
        self.assertEqual(by_id["n5-te"]["coverage"], "draft")
        path_ids = [s["id"] for s in plan.next_path("N5")]
        self.assertNotIn("n5-te", path_ids)
        result = plan.fill("て-форма")
        self.assertNotIn("n5-te", result["created"])

    def test_rejected_gap_can_be_filled_again(self):
        first = plan.fill("て-форма")
        self.assertIn("n5-te", first["created"])
        gid = db.query_one("SELECT id FROM gap_proposals WHERE topic_id = 'n5-te'")["id"]
        gaps.decide_gap(gid, False)
        by_id = {s["id"]: s for s in plan.stations("N5")}
        self.assertEqual(by_id["n5-te"]["coverage"], "empty")
        second = plan.fill("て-форма")
        self.assertIn("n5-te", second["created"])


class OverlayIsNotMasteryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_te_overlay_hit_is_not_pack_coverage(self):
        from proba import jlpt

        _lesson_claim("見る", "見て", tags="te-form")
        cat = next(t for t in jlpt.catalog("N5")["topics"] if t["id"] == "n5-te")
        st = next(s for s in plan.stations("N5") if s["id"] == "n5-te")
        self.assertTrue(cat["hits"])
        self.assertEqual(st["coverage"], "empty")


class ExtractAndNeighborTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_fallback_does_not_propose_cue_equals_key(self):
        props = extract.proposals_from_text("猫だ。")
        self.assertFalse(any(p["prompt_ja"] == p["expected"] for p in props))
        self.assertFalse(any(kernel.cue_leaks_key(p["prompt_ja"], p["expected"]) for p in props))

    def test_hontou_is_not_a_counter_neighbor(self):
        gaps.propose_neighbors("本当に。")
        pending = gaps.list_gaps()
        self.assertFalse(any(row["expected"] == "冊" for row in pending))

    def test_give_neighbor_does_not_leak_cue(self):
        items = extract.neighbor_gap_items("プレゼントをくれる。")
        self.assertTrue(items)
        for item in items:
            self.assertFalse(kernel.cue_leaks_key(item["prompt_ja"], item["expected"]))


class ConflictAndHeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_two_textbook_keys_do_not_mint_teacher_winner(self):
        kernel.create_lesson(
            "a",
            "",
            [{"prompt_ja": "寒い", "expected": "寒いから", "provenance": "textbook"}],
        )
        kernel.create_lesson(
            "b",
            "",
            [{"prompt_ja": "寒い", "expected": "寒いので", "provenance": "textbook"}],
        )
        row = db.query_one("SELECT winner FROM conflicts")
        self.assertIsNotNone(row)
        self.assertNotEqual(row["winner"], "teacher")

    def test_headline_teacher_rate_is_not_mixed_with_textbook(self):
        t = 1.0
        sid = new_id()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', ?, ?, '')",
            (sid, t, t),
        )
        teacher = new_id()
        book = new_id()
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, '行く', '', '行って', '', 'teacher', 'queued', ?, '')",
            (teacher, sid, t),
        )
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, '読む', '', '読むこと', '', 'textbook', 'queued', ?, '')",
            (book, sid, t),
        )
        at = t + 25 * 3600
        db.execute(
            "INSERT INTO probe_attempts (id, claim_id, at, attempt_index, delay_hours, "
            "outcome, confidence, kind, key_source, response, early) "
            "VALUES (?, ?, ?, 1, 25, 'fail', 0.5, 'production', 'teacher', '', 0)",
            (new_id(), teacher, at),
        )
        db.execute(
            "INSERT INTO probe_attempts (id, claim_id, at, attempt_index, delay_hours, "
            "outcome, confidence, kind, key_source, response, early) "
            "VALUES (?, ?, ?, 1, 25, 'pass', 0.5, 'production', 'textbook', '', 0)",
            (new_id(), book, at),
        )
        h = kernel.headline()
        self.assertEqual(h["n"], 1)
        self.assertEqual(h["pass_rate"], 0.0)
        g = kernel.growth_series()
        self.assertEqual(len(g["delayed_first"]), h["n"])
        self.assertEqual(g["delayed_curve"][-1]["rate"], h["pass_rate"])
        self.assertNotIn("усредн", (h.get("note") or "").lower())


    def test_accept_proposed_records_conflict_with_teacher(self):
        kernel.create_lesson(
            "t",
            "",
            [{"prompt_ja": "寒い", "expected": "寒いから", "provenance": "teacher"}],
        )
        sid = db.query("SELECT id FROM source_events")[0]["id"]
        kernel.add_proposed(
            sid,
            [{"prompt_ja": "寒い", "expected": "寒いので", "provenance": "model"}],
        )
        pid = db.query_one("SELECT id FROM claims WHERE status = 'proposed'")["id"]
        kernel.accept_proposed(pid)
        self.assertIsNotNone(db.query_one("SELECT winner FROM conflicts"))
        self.assertEqual(db.query_one("SELECT winner FROM conflicts")["winner"], "teacher")

    def test_same_pack_pair_is_not_two_claims(self):
        plan.fill("て-форма")
        importing.ingest_text("t", "駅まで行ってください。")
        gid = db.query_one("SELECT id FROM gap_proposals WHERE topic_id = 'n5-te'")["id"]
        gaps.decide_gap(gid, True)
        proposed = db.query_one("SELECT id FROM claims WHERE status = 'proposed'")
        if proposed:
            kernel.accept_proposed(proposed["id"])
        n = len(
            db.query(
                "SELECT id FROM claims WHERE prompt_ja = '行く' AND expected = '行って' "
                "AND status NOT IN ('rejected', 'proposed')"
            )
        )
        self.assertEqual(n, 1)
    def test_probe_submit_sends_numeric_confidence(self):
        src = (Path(__file__).resolve().parent.parent / "web" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("confidence: null", src)
        self.assertIn("data-conf", src)
        self.assertIn('kind: "production"', src)
        self.assertIn("/api/drill/check", src)
        self.assertNotIn('kind: "recognition"', src)
        self.assertNotIn("runCheck(0.5)", src)


class CreateLessonLeakTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_teacher_lesson_stamps_known_same_pair(self):
        kernel.ensure_diagnostic()
        row = db.query_one(
            "SELECT id FROM claims WHERE prompt_ja = '行く' AND expected = '行って' "
            "AND status = 'diagnostic'"
        )
        kernel.answer_diagnostic(row["id"], True)
        kernel.create_lesson(
            "zoom",
            "",
            [{"prompt_ja": "行く", "expected": "行って", "provenance": "teacher"}],
        )
        live = db.query(
            "SELECT provenance, status FROM claims WHERE prompt_ja = '行く' AND expected = '行って' "
            "AND status NOT IN ('rejected', 'proposed')"
        )
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["provenance"], "teacher")

    def test_create_lesson_refuses_cue_equals_key(self):
        with self.assertRaises(ValueError):
            kernel.create_lesson(
                "x",
                "",
                [{"prompt_ja": "あげる", "expected": "あげる", "provenance": "model"}],
            )


class QueueParkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_eighth_lesson_item_is_not_due_tonight(self):
        items = [
            {
                "prompt_ja": f"動{i}",
                "expected": f"形{i}",
                "prompt_hint": "форма",
                "provenance": "teacher",
            }
            for i in range(8)
        ]
        kernel.create_lesson("zoom", "", items)
        tonight = db.query("SELECT id FROM claims WHERE status = 'tonight'")
        parked = db.query(
            "SELECT c.id, s.due_at FROM claims c "
            "JOIN schedule s ON s.claim_id = c.id WHERE c.status = 'queued'"
        )
        self.assertEqual(len(tonight), 7)
        self.assertEqual(len(parked), 1)
        self.assertGreater(parked[0]["due_at"], schedule.now() + 3600)
        nxt = kernel.next_probe()
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt["status"], "tonight")
        self.assertNotEqual(nxt["id"], parked[0]["id"])

    def test_accept_overflow_stays_off_the_evening_stage(self):
        from proba.ids import new_id as nid

        sid = nid()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'zoom_audio', 't', ?, ?, '')",
            (sid, t, t),
        )
        for i in range(8):
            cid = nid()
            db.execute(
                "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
                "gloss_ru, provenance, status, created_at, tags) "
                "VALUES (?, ?, ?, 'hint', ?, '', 'model', 'proposed', ?, '')",
                (cid, sid, f"動{i}", f"形{i}", t),
            )
        result = kernel.accept_source_proposed(sid)
        self.assertEqual(result["tonight"], 7)
        self.assertEqual(result["queued"], 1)
        nxt = kernel.next_probe()
        self.assertEqual(nxt["status"], "tonight")
        parked = db.query_one(
            "SELECT s.due_at FROM claims c JOIN schedule s ON s.claim_id = c.id "
            "WHERE c.status = 'queued'"
        )
        self.assertGreater(parked["due_at"], schedule.now() + 3600)


if __name__ == "__main__":
    unittest.main()
