from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from proba import db, dictionary, extract, flavor, giongo, kernel, plan

ROOT = Path(__file__).resolve().parent.parent


def _packer():
    path = ROOT / "tools" / "pack_giongo.py"
    spec = importlib.util.spec_from_file_location("pack_giongo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class GiongoLookupTests(unittest.TestCase):
    def test_pack_is_on_mim_not_lexicon(self):
        self.assertGreaterEqual(giongo.count(), 1000)
        self.assertEqual(giongo.CREDIT["source"], "jmdict")
        self.assertEqual(giongo.CREDIT["kind"], "on-mim")
        idx = giongo.index()
        self.assertNotIn("source", idx)
        self.assertNotIn("note", idx)
        lex = {h for h, _k, _g in dictionary.LEXICON}
        self.assertNotIn("わくわく", lex)
        self.assertNotIn("どきどき", extract._HEADS)

    def test_wakuwaku_is_lookup_not_a_probe(self):
        page = dictionary.word_page("わくわく")
        self.assertIsNotNone(page)
        self.assertEqual(page["kind"], "mimetic")
        self.assertEqual(page["paradigm"], "giongo")
        self.assertEqual(page["forms"], [])
        self.assertTrue(page.get("gloss_ru") or page.get("gloss"))

    def test_dokidoki_search_only_when_packed(self):
        packed = dictionary.search("どきどき", packed=True)
        self.assertTrue(any(h.get("kind") == "mimetic" and "どきどき" in (h.get("kana") or h.get("head") or "") for h in packed))
        slim = dictionary.search("どきどき", packed=False)
        self.assertFalse(any(h.get("kind") == "mimetic" for h in slim))

    def test_mora_folds_dakuten(self):
        self.assertEqual(giongo.mora_of("どきどき"), "と")
        row = giongo.by_mora("と")
        self.assertTrue(any("どきどき" in (c["head"] + c["kana"]) for c in row))

    def test_n4_station_is_still_not_a_probe(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db.use_path(Path(tmp.name) / "t.db")
        self.addCleanup(lambda: db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db"))
        page = plan.station_page("n4-giongo")
        self.assertIsNotNone(page)
        self.assertTrue(page["skip_kind"])
        self.assertFalse(page["fillable"])
        self.assertGreaterEqual(page["giongo"]["count"], 1000)
        self.assertTrue(page["giongo"]["samples"])
        before = len(db.query("SELECT id FROM probe_attempts"))
        plan.station_check("n4-giongo", "わくわく")
        dictionary.word_page("わくわく")
        self.assertEqual(len(db.query("SELECT id FROM probe_attempts")), before)
        self.assertFalse(db.query("SELECT id FROM claims"))

    def test_rus_numbered_senses_keep_hunger_and_skip_tag(self):
        pack = _packer()
        gloss = pack._sense_gloss(
            {
                "gloss": [
                    {"text": "(ономат.)"},
                    {"text": "1): {～する} низкопоклонничать, подхалимничать"},
                    {"text": "2): お腹がぺこぺこだ живот подвело"},
                    {"text": "3) (см.) ぺこんと"},
                ]
            }
        )
        self.assertIn("живот", gloss)
        self.assertIn("низкопоклонничать", gloss)
        self.assertNotIn("(ономат.)", gloss)
        self.assertNotIn("ぺこんと", gloss)
        self.assertNotIn("{", gloss)
        self.assertNotIn("1)", gloss)

    def test_dump_markup_is_stripped_from_the_sheet(self):
        pack = _packer()
        self.assertEqual(
            pack.clean_sheet_gloss(": {～する} нервничать, быть взволнованным"),
            "нервничать, быть взволнованным",
        )
        self.assertEqual(
            pack.clean_sheet_gloss("1): {～する} низкопоклонничать · 2): живот подвело"),
            "низкопоклонничать · живот подвело",
        )

    def test_wakuwaku_sheet_has_no_source_or_frames(self):
        giongo.reset()
        page = dictionary.word_page("わくわく")
        self.assertIsNotNone(page)
        gloss = page.get("gloss_ru") or page.get("gloss") or ""
        self.assertNotIn("{", gloss)
        self.assertNotIn("}", gloss)
        self.assertNotRegex(gloss, r"^\s*[:：]")
        self.assertNotIn("note", page)
        self.assertNotIn("source", page)
        overlay = giongo.station_overlay()
        self.assertNotIn("note", overlay)
        self.assertNotIn("source", overlay)

    def test_mixed_pos_does_not_stamp_suru_on_the_head(self):
        pack = _packer()
        self.assertEqual(
            pack._vs_flag(
                [
                    {"partOfSpeech": ["adj-na"]},
                    {"partOfSpeech": ["adv", "vs"]},
                ]
            ),
            0,
        )
        self.assertEqual(pack._vs_flag([{"partOfSpeech": ["vs"]}, {"partOfSpeech": ["vs-i"]}]), 1)

    def test_pekopeko_sheet_has_hunger_and_is_not_a_probe(self):
        giongo.reset()
        page = dictionary.word_page("ぺこぺこ")
        self.assertIsNotNone(page)
        gloss = (page.get("gloss_ru") or page.get("gloss") or "")
        self.assertIn("живот", gloss)
        self.assertIn("низкопоклонничать", gloss)
        self.assertFalse(page.get("vs"))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db.use_path(Path(tmp.name) / "t.db")
        self.addCleanup(lambda: db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db"))
        before = len(db.query("SELECT id FROM probe_attempts"))
        dictionary.word_page("ぺこぺこ")
        self.assertEqual(len(db.query("SELECT id FROM probe_attempts")), before)
        self.assertFalse(db.query("SELECT id FROM claims"))

    def test_hiikora_sheet_is_russian_lookup_not_english(self):
        giongo.reset()
        page = dictionary.word_page("ひいこら")
        self.assertIsNotNone(page)
        gloss = page.get("gloss_ru") or page.get("gloss") or ""
        self.assertRegex(gloss, r"[А-Яа-яЁё]")
        self.assertNotRegex(gloss, r"[A-Za-z]{3,}")
        self.assertEqual(page.get("lang"), "ru")
        self.assertEqual(page["kind"], "mimetic")
        self.assertEqual(page["forms"], [])

    def test_on_mim_pack_has_no_english_rows(self):
        giongo.reset()
        idx = giongo.index()
        self.assertEqual(idx["rus"], idx["count"])
        self.assertGreaterEqual(idx["count"], 1000)


class AtlasFlavorTests(unittest.TestCase):
    def tearDown(self):
        flavor.configure(flavor=flavor.TUTOR)

    def test_atlas_snapshot_has_no_probe_or_diagnostic(self):
        flavor.configure(flavor=flavor.ATLAS)
        snap = kernel.snapshot()
        self.assertEqual(snap["flavor"], "atlas")
        self.assertFalse(snap["diagnostic_pending"])
        self.assertIsNone(snap["next"])
        self.assertEqual(snap["tonight"], 0)

    def test_atlas_chrome_has_no_zoom(self):
        flavor.configure(flavor=flavor.ATLAS)
        chrome = flavor.chrome()
        labels = [r["label"] for r in chrome["rails"]]
        self.assertEqual(labels, ["Темы", "擬音", "Словарь"])
        self.assertNotIn("Zoom", labels)
        self.assertEqual(chrome["app_name"], "日本語便覧")
        flavor.configure(flavor=flavor.TUTOR)
        tutor = flavor.chrome()
        self.assertIn("Zoom", [r["label"] for r in tutor["rails"]])

    def test_atlas_from_argv_not_from_catalog_click(self):
        flavor.configure(argv=["launch.py", "--atlas"])
        self.assertTrue(flavor.is_atlas())
        self.assertEqual(flavor.port(), 8766)
        from proba.main import health

        self.assertEqual(health()["flavor"], "atlas")
        flavor.configure(flavor=flavor.TUTOR)
        self.assertEqual(health()["flavor"], "tutor")
