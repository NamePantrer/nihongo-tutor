from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, dictionary, gaps, importing, kernel, packs, plan
from proba.ids import new_id


class PlanFillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_fill_does_not_insert_claims(self):
        before = len(db.query("SELECT id FROM claims"))
        result = plan.fill("")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        self.assertLessEqual(result["count"], kernel.TONIGHT_CAP)
        self.assertGreater(result["count"], 0)
        self.assertEqual(result["used_course"], 0)
        self.assertNotIn("n5-desu", result["created"])
        pending = db.query("SELECT origin, topic_id FROM gap_proposals WHERE status = 'pending'")
        self.assertEqual(len(pending), result["count"])
        self.assertTrue(all(row["origin"] == "open" for row in pending))

    def test_analyze_does_not_write(self):
        before_c = len(db.query("SELECT id FROM claims"))
        before_g = len(db.query("SELECT id FROM gap_proposals"))
        data = plan.analyze("て-форма ポイント20 「こと」と「の」")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before_c)
        self.assertEqual(len(db.query("SELECT id FROM gap_proposals")), before_g)
        self.assertEqual(data["analyzer"], "lexicon")
        self.assertTrue(any(m["id"] == "p06" for m in data["matched"]))

    def test_paste_prefers_named_station_before_n5_walk(self):
        result = plan.fill("ポイント20 「こと」と「の」")
        self.assertIn("p06", result["created"])
        self.assertEqual(result["created"][0], "p06")

    def test_teacher_key_blocks_same_pack_item_not_the_whole_te_form(self):
        sid = new_id()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', 1, 1, '')",
            (sid,),
        )
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, '見る', 'て-форма', '見て', '', 'teacher', 'tonight', 1, 'te-form')",
            (new_id(), sid),
        )
        result = plan.fill("て-форма")
        self.assertNotIn("n5-kudasai", result["created"])
        self.assertIn("n5-te", result["created"])

    def test_known_surface_skips_that_key(self):
        sid = new_id()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'lesson', 't', 1, 1, '')",
            (sid,),
        )
        item = packs.pick_item("n5-te")
        db.execute(
            "INSERT INTO claims (id, source_event_id, prompt_ja, prompt_hint, expected, "
            "gloss_ru, provenance, status, created_at, tags) "
            "VALUES (?, ?, ?, '', ?, '', 'self', 'known', 1, 'te-form')",
            (new_id(), sid, item.prompt_ja, item.expected),
        )
        result = plan.fill("て-форма")
        self.assertNotIn("n5-te", result["created"])

    def test_last_paste_used_when_fill_text_empty(self):
        plan.save_paste("ポイント20 「こと」と「の」")
        result = plan.fill("")
        self.assertTrue(result["used_paste"])
        self.assertEqual(result["created"][0], "p06")

    def test_ingest_saves_paste_without_filling_path(self):
        importing.ingest_text("стр", "駅まで行ってください。")
        self.assertTrue(plan.last_paste())
        self.assertEqual(len(db.query("SELECT id FROM gap_proposals")), 0)
        self.assertTrue(db.query("SELECT id FROM claims WHERE status = 'proposed'"))

    def test_skip_kinds_never_become_gaps(self):
        result = plan.fill("擬音語 説明・意見・体験 会話上手")
        rows = db.query("SELECT topic_id FROM gap_proposals")
        ids = {row["topic_id"] for row in rows}
        self.assertNotIn("n4-giongo", ids)
        self.assertNotIn("n3-reading", ids)
        self.assertGreater(result["skipped_non_production"], 0)
        self.assertEqual(result["used_course"], 0)

    def test_accept_course_gap_is_textbook_not_teacher(self):
        plan.fill("n5-te")
        gid = db.query("SELECT id, origin FROM gap_proposals WHERE topic_id = 'n5-te'")[0]
        self.assertEqual(gid["origin"], "course")
        gaps.decide_gap(gid["id"], True)
        claim = db.query("SELECT provenance, status FROM claims")[0]
        self.assertEqual(claim["provenance"], "textbook")
        self.assertIn(claim["status"], ("tonight", "queued"))

    def test_station_page_does_not_insert(self):
        before_c = len(db.query("SELECT id FROM claims"))
        before_g = len(db.query("SELECT id FROM gap_proposals"))
        page = plan.station_page("n5-te")
        self.assertTrue(page["ok"])
        self.assertEqual(page["example"]["expected"], "行って")
        self.assertTrue(page["fillable"])
        self.assertEqual(len(db.query("SELECT id FROM claims")), before_c)
        self.assertEqual(len(db.query("SELECT id FROM gap_proposals")), before_g)

    def test_station_check_is_not_a_probe(self):
        before_a = len(db.query("SELECT id FROM probe_attempts"))
        before_c = len(db.query("SELECT id FROM claims"))
        miss = plan.station_check("n5-te", "wrong")
        self.assertEqual(miss["outcome"], "fail")
        self.assertFalse(miss["logged"])
        hit = plan.station_check("n5-te", "itte")
        self.assertEqual(hit["outcome"], "pass")
        self.assertEqual(hit["expected"], "行って")
        self.assertEqual(len(db.query("SELECT id FROM probe_attempts")), before_a)
        self.assertEqual(len(db.query("SELECT id FROM claims")), before_c)

    def test_station_unknown_is_none(self):
        self.assertIsNone(plan.station_page("n5-not-a-station"))

    def test_mimetic_station_has_no_drill(self):
        page = plan.station_page("n4-giongo")
        if page is None:
            self.skipTest("no n4-giongo topic")
        self.assertTrue(page["skip_kind"])
        self.assertFalse(page["fillable"])
        self.assertIsNone(page["example"])
        check = plan.station_check("n4-giongo", "anything")
        self.assertFalse(check["ok"])
        self.assertFalse(db.query("SELECT id FROM probe_attempts"))


class YarxiDrawerTests(unittest.TestCase):
    def test_radical_water_finds_kanji_cards(self):
        hits = dictionary.search("вода")
        kinds = {h.get("kind") for h in hits}
        self.assertIn("kanji", kinds)
        self.assertTrue(any(h.get("head") == "水" for h in hits if h.get("kind") == "kanji"))

    def test_lookup_does_not_need_db(self):
        card = dictionary.search("行")
        self.assertTrue(any(h.get("kind") == "kanji" and h.get("head") == "行" for h in card))

    def test_seven_is_russian(self):
        dictionary.reset_packed()
        page = dictionary.kanji_page("七")
        self.assertIn("семь", page["gloss_ru"])
        self.assertNotIn("Seven", page["gloss_ru"])

    def test_kanji_card_lists_several_russian_senses_after_readings(self):
        dictionary.reset_packed()
        page = dictionary.kanji_page("不")
        self.assertIsNotNone(page)
        parts = [p.strip() for p in page["gloss_ru"].split(" · ") if p.strip()]
        self.assertGreaterEqual(len(parts), 3)
        self.assertIn("не", parts)
        self.assertNotIn("Negative", page["gloss_ru"])
        rest = dictionary.kanji_page("休")
        self.assertIn("отдыхать", rest["gloss_ru"])
        go = dictionary.kanji_page("行")
        self.assertTrue("идти" in go["gloss_ru"] or "строка" in go["gloss_ru"])
        self.assertNotIn("Going", go["gloss_ru"])

    def test_seven_lists_compounds_from_packed_index(self):
        page = dictionary.kanji_page("七")
        self.assertGreaterEqual(len(page["compounds"]), 8)
        heads = {c["head"] for c in page["compounds"]}
        self.assertTrue(any("七" in h and h != "七" for h in heads))
        self.assertTrue(all(c.get("gloss_ru") for c in page["compounds"]))
        self.assertGreaterEqual(page["compounds_total"], len(page["compounds"]))
        self.assertEqual(page["compounds_more"], page["compounds_total"] - len(page["compounds"]))

    def test_packed_word_has_no_invented_paradigm(self):
        page = dictionary.word_page("七夕")
        self.assertIsNotNone(page)
        self.assertEqual(page["paradigm"], "pack")
        self.assertEqual(page["forms"], [])
        self.assertTrue(page["kana"])
        self.assertTrue(page["gloss_ru"])

    def test_mawaru_gloss_is_not_cut_mid_word(self):
        dictionary.reset_packed()
        page = dictionary.word_page("回る")
        self.assertIsNotNone(page)
        gloss = page["gloss_ru"]
        self.assertIn("кругу", gloss)
        self.assertNotIn("{", gloss)
        self.assertNotIn("связ", gloss)
        self.assertFalse(gloss.startswith("1)"))
        self.assertFalse(gloss.endswith("кру"))

    def test_packed_index_does_not_feed_extract(self):
        from proba import extract

        lex = {h for h, _k, _g in dictionary.LEXICON}
        self.assertEqual(set(extract._HEADS), lex)
        self.assertTrue(all(head in lex for _surface, head, _hint, _g in extract._VERB_FORMS))
        self.assertNotIn("七夕", lex)
        self.assertEqual(extract.inflections_of("七夕"), [])

    def test_rest_page_has_parts_compounds_and_siblings(self):
        page = dictionary.kanji_page("休")
        self.assertIsNotNone(page)
        self.assertGreaterEqual(len(page["parts"]), 2)
        heads = {c["head"] for c in page["compounds"]}
        self.assertTrue({"休む", "休み", "休日"} & heads)
        self.assertTrue(page["siblings"])
        self.assertTrue(all(s["head"] != "休" for s in page["siblings"]))
        rads = {s.get("radical") for s in page["siblings"]}
        self.assertTrue("人" in rads or any(s.get("radical") for s in page["siblings"]))

    def test_wood_component_lists_rest(self):
        page = dictionary.radical_page("木")
        self.assertIsNotNone(page)
        self.assertEqual(page["kind"], "radical")
        self.assertTrue(any(k["head"] == "休" for k in page["kanji"]))

    def test_iku_word_page_lists_te_form(self):
        page = dictionary.word_page("行く")
        self.assertEqual(page["kana"], "いく")
        surfaces = {f["surface"] for f in page["forms"]}
        self.assertIn("行って", surfaces)
        self.assertTrue(any("て-форма" in (f["gloss_ru"] or "") for f in page["forms"]))

    def test_pages_do_not_insert_claims(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db.use_path(Path(tmp.name) / "t.db")
        self.addCleanup(lambda: db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db"))
        before = len(db.query("SELECT id FROM claims"))
        dictionary.kanji_page("休")
        dictionary.radical_page("人")
        dictionary.word_page("行く")
        dictionary.word_page("七夕")
        self.assertEqual(len(db.query("SELECT id FROM claims")), before)
        self.assertFalse(db.query("SELECT id FROM probe_attempts"))
