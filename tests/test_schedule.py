from __future__ import annotations

import unittest

from proba import schedule


class ScheduleTests(unittest.TestCase):
    def test_delay_uses_created_when_never_probed(self):
        self.assertEqual(schedule.delay_hours(3600, None, 0), 1.0)

    def test_new_first_try_after_two_hours(self):
        self.assertEqual(schedule.attempt_index(10_000, 1000, 4), 1)
        self.assertEqual(schedule.attempt_index(1000, 900, 4), 5)

    def test_fail_shortens(self):
        ease, interval = schedule.review(2.5, 10, "fail")
        self.assertLess(ease, 2.5)
        self.assertEqual(interval, 0.25)

    def test_pass_from_zero_is_one_day(self):
        ease, interval = schedule.review(2.5, 0, "pass")
        self.assertEqual(interval, 1.0)
        self.assertGreaterEqual(ease, 2.5)


if __name__ == "__main__":
    unittest.main()
