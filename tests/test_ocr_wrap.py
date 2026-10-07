from __future__ import annotations

import unittest

from proba.ocr_wrap import reconstruct, stitch_lines


class OcrWrapTests(unittest.TestCase):
    def test_japanese_wrap_is_one_word(self):
        text = stitch_lines(["友達が学校", "に行きます。"])
        self.assertEqual(text, "友達が学校に行きます。")
        self.assertNotIn("\n", text)

    def test_sentence_break_stays_a_break(self):
        text = stitch_lines(["今日は休みです。", "明日行きます。"])
        self.assertEqual(text, "今日は休みです。\n\n明日行きます。")

    def test_latin_hyphen_wrap(self):
        text = stitch_lines(["inter-", "national"])
        self.assertEqual(text, "international")

    def test_long_vowel_mark_is_not_a_hyphen_wrap(self):
        text = stitch_lines(["ラーメン", "を食べる"])
        self.assertEqual(text, "ラーメンを食べる")

    def test_blank_line_is_a_paragraph(self):
        text = stitch_lines(["第一段。", "", "第二段。"])
        self.assertEqual(text, "第一段。\n\n第二段。")

    def test_three_line_wrap_is_one_phrase(self):
        text = stitch_lines(["友達が学", "校に行き", "ます。"])
        self.assertEqual(text, "友達が学校に行きます。")

    def test_mixed_script_keeps_a_space(self):
        text = stitch_lines(["これは", "test"])
        self.assertEqual(text, "これは test")

    def test_period_sits_on_the_same_line(self):
        words = [
            {"text": "ます", "left": 10, "top": 10, "width": 40, "height": 18},
            {"text": "。", "left": 52, "top": 20, "width": 8, "height": 8},
        ]
        self.assertEqual(reconstruct(words=words), "ます。")

    def test_words_on_two_rows_join(self):
        words = [
            {"text": "学校", "left": 10, "top": 10, "width": 40, "height": 18},
            {"text": "に", "left": 10, "top": 40, "width": 18, "height": 18},
            {"text": "行く", "left": 30, "top": 40, "width": 36, "height": 18},
        ]
        self.assertEqual(reconstruct(words=words), "学校に行く")

    def test_winrt_boxes_join_a_wrapped_sentence(self):
        words = [
            {"text": "友", "left": 53, "top": 55, "width": 102, "height": 99},
            {"text": "達", "left": 165, "top": 56, "width": 104, "height": 96},
            {"text": "が", "left": 283, "top": 56, "width": 97, "height": 93},
            {"text": "学", "left": 390, "top": 55, "width": 100, "height": 100},
            {"text": "校", "left": 53, "top": 287, "width": 102, "height": 102},
            {"text": "に", "left": 177, "top": 298, "width": 82, "height": 83},
            {"text": "行", "left": 279, "top": 288, "width": 101, "height": 101},
            {"text": "き", "left": 404, "top": 291, "width": 70, "height": 92},
            {"text": "ま", "left": 517, "top": 291, "width": 70, "height": 93},
            {"text": "す", "left": 617, "top": 291, "width": 94, "height": 96},
            {"text": "。", "left": 726, "top": 358, "width": 31, "height": 32},
        ]
        self.assertEqual(reconstruct(words=words), "友達が学校に行きます。")

