from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, gaps, kernel
from proba.compute import whisper_plan
from proba.extract import inflections_of, neighbor_gap_items, proposals_from_text


class ExtractFormTests(unittest.TestCase):
    def test_tai_is_a_form_not_the_sentence(self):
        props = proposals_from_text("今日は水を飲みたいです。")
        self.assertTrue(props)
        self.assertTrue(all(p["provenance"] == "model" for p in props))
        hit = next(p for p in props if p["expected"] == "飲みたい")
        self.assertEqual(hit["prompt_ja"], "飲む")
        self.assertFalse(any(p["expected"].startswith("今日は水を") for p in props))

    def test_te_form_cue_is_dictionary_base(self):
        props = proposals_from_text("駅まで行ってください。")
        hit = next(p for p in props if p["expected"] == "行って")
        self.assertEqual(hit["prompt_ja"], "行く")

    def test_neighbors_are_not_the_whole_jlpt(self):
        items = neighbor_gap_items("駅まで行って。")
        self.assertTrue(items)
        self.assertLessEqual(len(items), 5)
        self.assertTrue(all(i.get("tags") == "te-form" for i in items))

    def test_attested_te_of_matsu_is_extracted(self):
        props = proposals_from_text("ここで待ってください。")
        hit = next(p for p in props if p["expected"] == "待って")
        self.assertEqual(hit["prompt_ja"], "待つ")
        self.assertEqual(hit["prompt_hint"], "て-форма")

    def test_kaite_is_extracted_from_kaku(self):
        props = proposals_from_text("名前を書いて。")
        hit = next(p for p in props if p["expected"] == "書いて")
        self.assertEqual(hit["prompt_ja"], "書く")

    def test_korekara_does_not_mint_kara(self):
        props = proposals_from_text("これから行きます。")
        self.assertFalse(any(p["expected"] in ("から", "これから") for p in props))
        hit = next(p for p in props if p["expected"] == "行きます")
        self.assertEqual(hit["prompt_ja"], "行く")

    def test_adj_kara_is_reason_not_incidental(self):
        props = proposals_from_text("寒いから、家にいます。")
        hit = next(p for p in props if p["expected"] == "寒いから")
        self.assertEqual(hit["prompt_ja"], "寒い")

    def test_teacher_correction_is_first(self):
        props = proposals_from_text("не から, а ので。忙しいので帰りません。")
        self.assertEqual(props[0]["expected"], "ので")
        self.assertEqual(props[0]["prompt_ja"], "から")
        self.assertIn("correction", props[0]["tags"])

    def test_cap_stays_seven(self):
        props = proposals_from_text(
            "待って。書いて。話して。買って。聞いて。乗って。終わって。習って。"
        )
        self.assertLessEqual(len(props), 7)


class DictParadigmTests(unittest.TestCase):
    def test_iku_lists_te(self):
        forms = inflections_of("行く")
        self.assertTrue(any(f["surface"] == "行って" for f in forms))

    def test_kiru_is_not_godan_te(self):
        forms = inflections_of("着る")
        surfaces = {f["surface"] for f in forms}
        self.assertIn("着て", surfaces)
        self.assertNotIn("着って", surfaces)

    def test_noun_has_no_paradigm(self):
        self.assertEqual(inflections_of("休日"), [])


class GapListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_get_style_list_does_not_dump_curriculum(self):
        self.assertEqual(gaps.list_gaps(), [])

    def test_neighbors_stay_proposed(self):
        gaps.propose_neighbors("行ってください")
        pending = gaps.list_gaps()
        self.assertTrue(pending)
        self.assertEqual(len(db.query("SELECT * FROM claims")), 0)


class ComputeTests(unittest.TestCase):
    def test_plan_has_device(self):
        plan = whisper_plan()
        self.assertIn(plan["device"], ("cpu", "cuda"))
        self.assertGreaterEqual(plan["cpu_threads"], 2)


class AcceptSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_one_tap_accepts_without_inserting_gaps(self):
        from proba.ids import new_id
        from proba import schedule

        sid = new_id()
        t = schedule.now()
        db.execute(
            "INSERT INTO source_events (id, kind, title, started_at, ended_at, notes) "
            "VALUES (?, 'zoom_audio', 't', ?, ?, '')",
            (sid, t, t),
        )
        kernel.attach_transcript(sid, "水を飲みたい。行って。")
        proposed = db.query(
            "SELECT * FROM claims WHERE source_event_id = ? AND status = 'proposed'",
            (sid,),
        )
        self.assertTrue(proposed)
        result = kernel.accept_source_proposed(sid)
        self.assertEqual(result["accepted"], len(proposed))
        still = db.query(
            "SELECT * FROM claims WHERE source_event_id = ? AND status = 'proposed'",
            (sid,),
        )
        self.assertEqual(len(still), 0)


if __name__ == "__main__":
    unittest.main()
