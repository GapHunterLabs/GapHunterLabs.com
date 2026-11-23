"""The Atlassian app icon from data/atlassian-catalog-data.json: only same-origin /media/*.png files that exist.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_plugin_pages import ROOT, atl_app_icon, atl_icon_html  # noqa: E402

MARK = "<svg>platform</svg>"
REAL = "/media/atlassian/workflow-gap-companion/icon.png"


class AtlAppIconTest(unittest.TestCase):
    def test_no_icon_falls_back_to_the_platform_mark(self):
        self.assertIsNone(atl_app_icon({"name": "x"}))
        html = atl_icon_html({"name": "x"}, MARK)
        self.assertIn("atl-mark", html)
        self.assertIn(MARK, html)
        self.assertNotIn("<img", html)

    def test_real_icon_is_used(self):
        self.assertEqual(atl_app_icon({"name": "w", "icon": REAL}), REAL)
        html = atl_icon_html({"name": "w", "icon": REAL}, MARK)
        self.assertIn('<img src="%s"' % REAL, html)
        self.assertIn('alt=""', html)
        self.assertNotIn(MARK, html)

    def test_rejected_values_stop_the_build(self):
        for bad in ("https://example.com/x.png", "//example.com/x.png", "/media/../index.html.png", "/media/a.svg",
                    "/media/A.PNG", "media/x.png", "/assets/x.png", '/media/x.png" onerror="alert(1)', "", 5, ["/media/x.png"]):
            with self.subTest(icon=bad), self.assertRaises(SystemExit):
                atl_app_icon({"name": "x", "icon": bad})

    def test_existing_files_outside_the_rule_are_rejected_too(self):
        # These files exist, so only the path rule (not the existence check) can stop them.
        for bad in ("/index.html", "/media/../index.html", "/assets/img/joel-diaz-96.jpg", "/css/theme.css"):
            self.assertTrue((ROOT / bad.lstrip("/")).resolve().is_file(), bad)
            with self.subTest(icon=bad), self.assertRaises(SystemExit) as cm:
                atl_app_icon({"name": "x", "icon": bad})
            self.assertIn("invalid icon", str(cm.exception))

    def test_missing_file_stops_the_build(self):
        with self.assertRaises(SystemExit) as cm:
            atl_app_icon({"name": "x", "icon": "/media/atlassian/no-such-app/icon.png"})
        self.assertIn("not found", str(cm.exception))

    def test_every_declared_icon_exists_and_is_a_square_png(self):
        apps = json.loads((ROOT / "data" / "atlassian-catalog-data.json").read_text(encoding="utf-8"))["apps"]
        for app in apps:
            if app.get("icon"):
                with self.subTest(app=app["name"]):
                    data = (ROOT / app["icon"].lstrip("/")).read_bytes()
                    self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                    w, h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
                    self.assertEqual(w, h)
                    self.assertGreaterEqual(w, 96)

    def test_browser_rule_matches_the_build_rule(self):
        js = (ROOT / "js" / "catalog-atlassian.js").read_text(encoding="utf-8")
        self.assertIn(r"/^\/media\/[a-z0-9\/._-]+\.png$/", js)
        self.assertIn("indexOf('..') === -1", js)


if __name__ == "__main__":
    unittest.main()
