from __future__ import annotations

import unittest

from proba.kana import grade, romaji_to_hiragana, to_reading


class RomajiTests(unittest.TestCase):
    def test_itte(self):
        self.assertEqual(romaji_to_hiragana("itte"), "いって")
        self.assertEqual(romaji_to_hiragana("ItTe"), "いって")

    def test_kureru_past(self):
        self.assertEqual(romaji_to_hiragana("kureta"), "くれた")

    def test_pending_n(self):
        self.assertEqual(romaji_to_hiragana("hon", commit=False), "ほn")
        self.assertEqual(romaji_to_hiragana("hon", commit=True), "ほん")

    def test_nn_and_nya(self):
        self.assertEqual(romaji_to_hiragana("nn"), "ん")
        self.assertEqual(romaji_to_hiragana("nya"), "にゃ")
        self.assertEqual(romaji_to_hiragana("minna"), "みんな")
        self.assertEqual(romaji_to_hiragana("honna"), "ほんな")

    def test_particles_are_not_swapped(self):
        self.assertEqual(romaji_to_hiragana("ha"), "は")
        self.assertEqual(romaji_to_hiragana("wa"), "わ")
        self.assertEqual(romaji_to_hiragana("wo"), "を")
        self.assertEqual(romaji_to_hiragana("he"), "へ")
        self.assertEqual(romaji_to_hiragana("e"), "え")


class GradeTests(unittest.TestCase):
    def test_empty_is_fail(self):
        self.assertEqual(grade("", "行って")["outcome"], "fail")
        self.assertTrue(grade("   ", "は")["empty"])

    def test_kana_matches_kanji_key(self):
        g = grade("itte", "行って")
        self.assertEqual(g["outcome"], "pass")
        self.assertEqual(g["reading"], "いって")

    def test_kureta(self):
        self.assertEqual(grade("くれた", "くれた")["outcome"], "pass")
        self.assertEqual(grade("kureta", "くれた")["outcome"], "pass")
        self.assertEqual(grade("kureru", "くれた")["outcome"], "fail")

    def test_ha_is_not_wa(self):
        self.assertEqual(grade("ha", "は")["outcome"], "pass")
        self.assertEqual(grade("wa", "は")["outcome"], "fail")
        self.assertEqual(grade("わ", "は")["outcome"], "fail")

    def test_ga_is_fail_for_ha(self):
        self.assertEqual(grade("ga", "は")["outcome"], "fail")

    def test_no_levenshtein_partial(self):
        self.assertEqual(grade("行った", "行って")["outcome"], "fail")

    def test_katakana_equals_hiragana(self):
        self.assertEqual(grade("イッテ", "いって")["outcome"], "pass")


if __name__ == "__main__":
    unittest.main()
