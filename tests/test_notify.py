import unittest

from proba.notify import decide, toast_body


CLAIM = {
    "id": "c1",
    "prompt_ja": "行く",
    "prompt_hint": "て-форма",
    "expected": "行って",
    "last_attempt": None,
}


def snap(**kwargs):
    base = {
        "diagnostic_pending": False,
        "diagnostic_remaining": 0,
        "next": CLAIM,
        "capture": {"state": "idle", "source_event_id": None, "nudge": False},
    }
    base.update(kwargs)
    return base


class NotifyTests(unittest.TestCase):
    def test_key_never_in_body(self):
        body = toast_body(CLAIM, after_class=True, empty_after_class=False)
        self.assertNotIn("行って", body)
        self.assertIn("行く", body)

    def test_visible_skips(self):
        self.assertIsNone(
            decide(snap(), visible=True, hour=12, now=1000, last_toast=0, last_claim="")
        )

    def test_diagnostic_remaining_skips(self):
        self.assertIsNone(
            decide(
                snap(diagnostic_pending=True, diagnostic_remaining=3, next=None),
                visible=False,
                hour=12,
                now=1000,
                last_toast=0,
                last_claim="",
            )
        )

    def test_paused_class_skips(self):
        self.assertIsNone(
            decide(
                snap(
                    capture={
                        "state": "paused",
                        "source_event_id": "e1",
                        "nudge": False,
                    }
                ),
                visible=False,
                hour=12,
                now=1000,
                last_toast=0,
                last_claim="",
            )
        )

    def test_quiet_hours_skip_unless_after_class(self):
        self.assertIsNone(
            decide(snap(), visible=False, hour=23, now=1000, last_toast=0, last_claim="")
        )
        got = decide(
            snap(capture={"state": "idle", "source_event_id": None, "nudge": True}),
            visible=False,
            hour=23,
            now=1000,
            last_toast=0,
            last_claim="",
        )
        self.assertIsNotNone(got)
        self.assertIn("行く", got["body"])
        self.assertNotIn("行って", got["body"])
        self.assertNotIn("пора позаниматься", got["body"].lower())

    def test_after_class_without_probe_is_honest(self):
        got = decide(
            snap(
                next=None,
                capture={"state": "idle", "source_event_id": None, "nudge": True},
            ),
            visible=False,
            hour=21,
            now=1000,
            last_toast=0,
            last_claim="",
        )
        self.assertIsNotNone(got)
        self.assertIn("нечего", got["body"])

    def test_nudge_does_not_block_due_item(self):
        got = decide(
            snap(capture={"state": "idle", "source_event_id": None, "nudge": True}),
            visible=False,
            hour=21,
            now=1000,
            last_toast=0,
            last_claim="",
        )
        self.assertEqual(got["claim_id"], "c1")
        self.assertNotIn("не график и не конспект", got["body"])

    def test_delayed_copy(self):
        delayed = {**CLAIM, "last_attempt": {"outcome": "fail"}}
        body = toast_body(delayed, after_class=False, empty_after_class=False)
        self.assertIn("ждала паузу", body)

    def test_tonight_copy_does_not_claim_a_pause(self):
        body = toast_body(CLAIM, after_class=False, empty_after_class=False)
        self.assertNotIn("ждала паузу", body)
        self.assertIn("на этот вечер", body)

    def test_same_claim_cooldown(self):
        self.assertIsNone(
            decide(
                snap(),
                visible=False,
                hour=12,
                now=20_000,
                last_toast=20_000 - 51 * 60,
                last_claim="c1",
            )
        )


if __name__ == "__main__":
    unittest.main()
