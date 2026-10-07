from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proba import db, gaps


class GapGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.use_path(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        db.use_path(Path(__file__).resolve().parent.parent / "data" / "proba.db")
        self.tmp.cleanup()

    def test_refresh_does_not_create_claims(self):
        pending = gaps.refresh_gaps()
        self.assertTrue(pending)
        claims = db.query("SELECT * FROM claims")
        self.assertEqual(len(claims), 0)

    def test_accept_creates_claim(self):
        pending = gaps.refresh_gaps()
        gid = pending[0]["id"]
        gaps.decide_gap(gid, True)
        claims = db.query("SELECT * FROM claims")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["provenance"], "model")


if __name__ == "__main__":
    unittest.main()
