"""Tests for the download counts in pipeline/auto_update_catalog.py.

Run: python -m unittest discover -s pipeline/tests -v
"""
import copy
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("auto_update_catalog", str(PIPELINE / "auto_update_catalog.py"))
auc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auc)


def history_with(*snapshots):
    return {"snapshots": [{"date": d, "plugins": {k: {"downloads": v} for k, v in p.items()}} for d, p in snapshots]}


class MarketplaceDownloadsTest(unittest.TestCase):
    def test_value_is_published_unchanged(self):
        for raw in (0, 1, 2, 62, 13715):
            self.assertEqual(auc.marketplace_downloads(raw), raw)

    def test_missing_value_stays_missing(self):
        self.assertIsNone(auc.marketplace_downloads(None))

    def test_malformed_values_are_treated_as_missing(self):
        for raw in ("5", "", 2.0, 1.5, True, False, -1, -3, [], {}, [1]):
            with self.subTest(raw=raw):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertIsNone(auc.marketplace_downloads(raw))
                self.assertIn("[warn]", err.getvalue())

    def test_warning_does_not_echo_the_value(self):
        err = io.StringIO()
        with redirect_stderr(err):
            auc.marketplace_downloads("secret-looking-value")
        self.assertNotIn("secret-looking-value", err.getvalue())
        self.assertIn("str", err.getvalue())


class HistoryMigrationTest(unittest.TestCase):
    def test_adds_one_to_every_stored_count(self):
        h = history_with(("2026-08-18", {"a": 0, "b": 41}), ("2026-08-19", {"a": 1, "b": 45, "c": 0}))
        self.assertTrue(auc.migrate_history_to_marketplace_counts(h))
        self.assertEqual([s["plugins"]["a"]["downloads"] for s in h["snapshots"]], [1, 2])
        self.assertEqual(h["snapshots"][0]["plugins"]["b"]["downloads"], 42)
        self.assertEqual(h["snapshots"][1]["plugins"]["c"]["downloads"], 1)
        self.assertEqual(h[auc.HISTORY_BASIS_KEY], auc.HISTORY_BASIS)

    def test_runs_only_once(self):
        h = history_with(("2026-08-18", {"a": 5}))
        self.assertTrue(auc.migrate_history_to_marketplace_counts(h))
        self.assertFalse(auc.migrate_history_to_marketplace_counts(h))
        self.assertEqual(h["snapshots"][0]["plugins"]["a"]["downloads"], 6)

    def test_leaves_missing_and_non_int_values_alone(self):
        h = {"snapshots": [{"date": "2026-08-18", "plugins": {
            "none": {"downloads": None}, "absent": {}, "text": {"downloads": "7"}, "flag": {"downloads": True}}}]}
        before = copy.deepcopy(h["snapshots"])
        auc.migrate_history_to_marketplace_counts(h)
        self.assertEqual(h["snapshots"], before)

    def test_empty_and_partial_histories(self):
        for h in ({"snapshots": []}, {}, {"snapshots": [{"date": "2026-08-18"}]},
                  {"snapshots": [{"date": "2026-08-18", "plugins": None}]}):
            with self.subTest(h=h):
                self.assertTrue(auc.migrate_history_to_marketplace_counts(h))
                self.assertEqual(h[auc.HISTORY_BASIS_KEY], auc.HISTORY_BASIS)

    def test_unknown_basis_aborts_instead_of_guessing(self):
        for basis in ("adjusted", "", 0, "Marketplace"):
            with self.subTest(basis=basis):
                h = history_with(("2026-08-18", {"a": 5}))
                h[auc.HISTORY_BASIS_KEY] = basis
                with self.assertRaises(SystemExit) as ctx:
                    auc.migrate_history_to_marketplace_counts(h)
                self.assertIn(auc.HISTORY_BASIS_KEY, str(ctx.exception))
                self.assertEqual(h["snapshots"][0]["plugins"]["a"]["downloads"], 5)

    def test_trend_has_no_jump_at_the_switch(self):
        # Stored (old basis) snapshots plus one new raw snapshot: the only
        # change in the 7-day total must be the real new downloads.
        h = history_with(("2026-11-07", {"a": 100, "b": 0}), ("2026-11-08", {"a": 103, "b": 2}))
        auc.migrate_history_to_marketplace_counts(h)
        h["snapshots"].append({"date": "2026-11-09", "plugins": {"a": {"downloads": 105}, "b": {"downloads": 3}}})
        totals = [t["totalDownloads"] for t in auc.compute_trend7d(h)]
        self.assertEqual(totals, [102, 107, 108])

    def test_growth_baseline_uses_the_marketplace_basis(self):
        h = history_with(("2026-08-26", {"a": 0}), ("2026-11-08", {"a": 61}))
        auc.migrate_history_to_marketplace_counts(h)
        self.assertEqual(auc.earliest_datapoint(h, "a"), ("2026-08-26", 1))

    def test_save_and_load_keep_the_marker(self):
        h = history_with(("2026-08-18", {"a": 5}))
        auc.migrate_history_to_marketplace_counts(h)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history.json")
            old = auc.HISTORY_PATH
            auc.HISTORY_PATH = path
            try:
                auc.save_history(h)
                loaded = auc.load_history()
            finally:
                auc.HISTORY_PATH = old
        self.assertEqual(loaded, h)
        self.assertFalse(auc.migrate_history_to_marketplace_counts(loaded))

    def test_real_history_file_is_well_formed(self):
        # The committed history either still has the old basis (no marker,
        # every count an int >= 0) or is already marked; never anything else.
        with open(PIPELINE / "catalog_daily_history.json", encoding="utf-8") as f:
            h = json.load(f)
        self.assertIn(h.get(auc.HISTORY_BASIS_KEY), (None, auc.HISTORY_BASIS))
        for snap in h["snapshots"]:
            for entry in snap["plugins"].values():
                v = entry.get("downloads")
                self.assertTrue(v is None or (isinstance(v, int) and v >= 0), (snap["date"], v))


if __name__ == "__main__":
    unittest.main()
