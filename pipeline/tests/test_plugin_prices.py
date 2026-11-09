"""Tests for data/plugin-prices.json as read by build_plugin_pages.load_prices.

The file is optional. When it exists, a typo must stop the build with a message that names the file and the plugin,
never print a wrong price on a page.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_plugin_pages as bpp  # noqa: E402

PLUGINS = [
    {"repo": "paid-one", "pricing": "PAID"},
    {"repo": "freemium-one", "pricing": "FREEMIUM"},
    {"repo": "free-one", "pricing": "FREE"},
    {"repo": "no-pricing"},
]
PREFIX = "[build_plugin_pages] ERROR: plugin-prices.json: "


class LoadPricesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "plugin-prices.json"

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, content):
        if isinstance(content, bytes):
            self.path.write_bytes(content)
        elif isinstance(content, str):
            self.path.write_text(content, encoding="utf-8")
        else:
            self.path.write_text(json.dumps(content), encoding="utf-8")
        return bpp.load_prices(self.path, PLUGINS)

    def assertRejected(self, content, expected):
        with self.assertRaises(SystemExit) as caught:
            self.load(content)
        message = str(caught.exception.code)
        self.assertTrue(message.startswith(PREFIX), message)
        self.assertIn(expected, message)

    # ---------------------------------------------------------------- accepted
    def test_missing_file_means_no_prices(self):
        self.assertEqual(bpp.load_prices(self.path, PLUGINS), {})

    def test_empty_prices_object(self):
        self.assertEqual(self.load({"prices": {}}), {})

    def test_paid_and_freemium_entries(self):
        got = self.load({"prices": {"paid-one": {"yearUSD": 29}, "freemium-one": {"yearUSD": 1500}}})
        self.assertEqual(got, {"paid-one": 29, "freemium-one": 1500})

    def test_lowest_valid_price(self):
        self.assertEqual(self.load({"prices": {"paid-one": {"yearUSD": 1}}}), {"paid-one": 1})

    def test_bom_written_by_windows_tools(self):
        body = json.dumps({"prices": {"paid-one": {"yearUSD": 29}}}).encode("utf-8")
        self.assertEqual(self.load(b"\xef\xbb\xbf" + body), {"paid-one": 29})

    # ---------------------------------------------------------------- not JSON
    def test_unreadable_files_name_the_file(self):
        for label, content in [("empty", ""), ("bom only", b"\xef\xbb\xbf"), ("truncated", '{"prices": {'),
                               ("not utf-8", b"\xff\xfe{}")]:
            with self.subTest(label):
                self.assertRejected(content, "not valid UTF-8 JSON")

    # ---------------------------------------------------------------- wrong shape
    def test_wrong_shapes(self):
        for label, content in [("array", []), ("null", "null"), ("number", "29"), ("no prices key", {}),
                               ("prices is a list", {"prices": []}), ("prices is a string", {"prices": "29"}),
                               ("prices is null", {"prices": None})]:
            with self.subTest(label):
                self.assertRejected(content, 'expected an object with a "prices" object')

    # ---------------------------------------------------------------- wrong plugin
    def test_only_paid_or_freemium_plugins_of_the_catalog(self):
        for repo in ["free-one", "no-pricing", "not-in-catalog", "", "PAID-ONE"]:
            with self.subTest(repo=repo):
                self.assertRejected({"prices": {repo: {"yearUSD": 29}}}, '"%s" is not a paid or freemium plugin' % repo)

    def test_one_bad_entry_rejects_the_whole_file(self):
        self.assertRejected({"prices": {"paid-one": {"yearUSD": 29}, "free-one": {"yearUSD": 29}}},
                            '"free-one" is not a paid or freemium plugin')

    # ---------------------------------------------------------------- wrong price
    def test_price_must_be_a_positive_whole_number(self):
        for label, entry in [("0", {"yearUSD": 0}), ("-1", {"yearUSD": -1}), ("29.5", {"yearUSD": 29.5}),
                             ("29.0", {"yearUSD": 29.0}), ("string", {"yearUSD": "29"}), ("true", {"yearUSD": True}),
                             ("null", {"yearUSD": None}), ("missing", {}), ("bare number", 29),
                             ("list", [29])]:
            with self.subTest(label):
                self.assertRejected({"prices": {"paid-one": entry}}, '"paid-one".yearUSD must be a positive whole number')


if __name__ == "__main__":
    unittest.main()
