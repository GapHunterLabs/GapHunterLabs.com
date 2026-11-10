"""data/reach.json: the audience figures printed on /sponsors/. A wrong figure is a public error, so the loader fails fast."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_home as H  # noqa: E402

REAL = json.loads(H.REACH_DATA.read_text(encoding="utf-8"))


class ReachTest(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reach.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.object(H, "REACH_DATA", path):
                return H.load_reach()

    def assertRejected(self, mutate, message):
        data = copy.deepcopy(REAL)
        mutate(data)
        with self.assertRaises(SystemExit) as ctx:
            self.load(data)
        self.assertIn(message, str(ctx.exception))

    def test_the_real_file_loads_and_prints_every_figure(self):
        reach = self.load(copy.deepcopy(REAL))
        html = H.reach_html(reach)
        recent = REAL["linkedin"]["recent"]
        for value in (REAL["linkedin"]["followers"], recent["postImpressions7d"], recent["profileViewers90d"],
                      recent["connections"], recent["searchAppearances"]):
            self.assertIn('tw-text-ink">%s</p>' % format(value, ","), html)
        self.assertIn('<time datetime="%s">' % recent["searchFrom"], html)
        self.assertIn('<time datetime="%s">' % recent["searchTo"], html)

    def test_recent_block_is_required(self):
        self.assertRejected(lambda d: d["linkedin"].pop("recent"), "linkedin.recent")
        self.assertRejected(lambda d: d["linkedin"].__setitem__("recent", []), "linkedin.recent")

    def test_each_recent_count_must_be_a_positive_int(self):
        for field in H.REACH_RECENT_COUNTS:
            for bad in (None, 0, -1, "12", 1.5, True):
                with self.subTest(field=field, bad=bad):
                    self.assertRejected(lambda d: d["linkedin"]["recent"].__setitem__(field, bad), field)
            with self.subTest(field=field, missing=True):
                self.assertRejected(lambda d: d["linkedin"]["recent"].pop(field), field)

    def test_change_pct_is_an_int_from_minus_100(self):
        for bad in (None, "201", 2.5, True, -101):
            with self.subTest(bad=bad):
                self.assertRejected(lambda d: d["linkedin"]["recent"].__setitem__("postImpressions7dChangePct", bad),
                                    "postImpressions7dChangePct")

    def test_change_pct_boundaries_and_sign(self):
        for value, shown in ((-100, "<b>-100%</b>"), (0, "<b>0%</b>"), (201, "<b>+201%</b>")):
            with self.subTest(value=value):
                data = copy.deepcopy(REAL)
                data["linkedin"]["recent"]["postImpressions7dChangePct"] = value
                self.assertIn(shown, H.reach_html(self.load(data)))

    def test_search_window_dates(self):
        as_of = REAL["asOf"]
        self.assertRejected(lambda d: d["linkedin"]["recent"].__setitem__("searchFrom", "27/10/2026"), "searchFrom")
        self.assertRejected(lambda d: d["linkedin"]["recent"].pop("searchTo"), "searchTo")
        # inverted, and ending after asOf
        self.assertRejected(lambda d: d["linkedin"]["recent"].update(searchFrom="2026-11-02", searchTo="2026-10-27"),
                            "searchFrom <= searchTo <= asOf")
        self.assertRejected(lambda d: d["linkedin"]["recent"].update(searchTo="2099-01-01"),
                            "searchFrom <= searchTo <= asOf")
        # a one-day window that ends exactly on asOf is valid
        data = copy.deepcopy(REAL)
        data["linkedin"]["recent"].update(searchFrom=as_of, searchTo=as_of)
        self.load(data)


if __name__ == "__main__":
    unittest.main()
