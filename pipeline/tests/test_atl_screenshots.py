"""Atlassian app screenshots from data/atlassian-catalog-data.json: same-origin /media/...-1840.webp files with a
920 px twin and a real text alternative; anything else stops the build.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_plugin_pages import ROOT, atl_screenshots, atl_shot_img  # noqa: E402

OK = "/media/atlassian/workflow-gap-companion/screenshot-1-report-1840.webp"


class AtlScreenshotsTest(unittest.TestCase):
    def test_no_screenshots_is_an_empty_list(self):
        self.assertEqual(atl_screenshots({"name": "x"}), [])

    def test_a_valid_screenshot_gets_its_small_twin(self):
        shots = atl_screenshots({"name": "w", "screenshots": [{"src": OK, "alt": "  The report  "}]})
        self.assertEqual(shots, [{"src": OK, "small": OK.replace("-1840.webp", "-920.webp"), "alt": "The report"}])

    def test_bad_entries_stop_the_build(self):
        cases = {
            "not a list": "x",
            "entry not an object": [OK],
            "foreign url": [{"src": "https://example.com/a-1840.webp", "alt": "a"}],
            "png instead of webp": [{"src": "/media/a-1840.png", "alt": "a"}],
            "missing size suffix": [{"src": "/media/atlassian/workflow-gap-companion/screenshot-1-report.webp", "alt": "a"}],
            "traversal": [{"src": "/media/../media/atlassian/workflow-gap-companion/screenshot-1-report-1840.webp", "alt": "a"}],
            "missing file": [{"src": "/media/atlassian/no-such/shot-1840.webp", "alt": "a"}],
            "empty alt": [{"src": OK, "alt": "   "}],
            "alt not a string": [{"src": OK, "alt": 5}],
            "alt too long": [{"src": OK, "alt": "a" * 201}],
            "quote in src": [{"src": '/media/x" onerror="alert(1)-1840.webp', "alt": "a"}],
        }
        for label, value in cases.items():
            with self.subTest(case=label), self.assertRaises(SystemExit):
                atl_screenshots({"name": "x", "screenshots": value})

    def test_alt_text_is_escaped_in_the_markup(self):
        html = atl_shot_img({"src": OK, "small": OK, "alt": 'a "b" <c>'}, eager=False)
        self.assertIn('alt="a &quot;b&quot; &lt;c&gt;"', html)
        self.assertIn('loading="lazy"', html)
        self.assertNotIn("fetchpriority", html)

    def test_every_declared_screenshot_is_a_real_webp_pair(self):
        apps = json.loads((ROOT / "data" / "atlassian-catalog-data.json").read_text(encoding="utf-8"))["apps"]
        for app in apps:
            for shot in atl_screenshots(app):
                for path, width in ((shot["src"], 1840), (shot["small"], 920)):
                    with self.subTest(path=path):
                        data = (ROOT / path.lstrip("/")).read_bytes()
                        self.assertEqual(data[:4], b"RIFF")
                        self.assertEqual(data[8:12], b"WEBP")

    def test_the_built_page_shows_them_in_both_languages(self):
        for rel in ("catalog/atlassian/workflow-gap-companion/index.html", "es/catalogo/atlassian/workflow-gap-companion/index.html"):
            html = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertEqual(len(re.findall(r'<div class="ph-media"><img [^>]*fetchpriority="high"', html)), 1)
                self.assertEqual(html.count('class="atl-shot"'), 1)
                self.assertNotIn("no-media", re.search(r'<header class="plugin-hero[^"]*"', html).group(0))


    def test_the_generated_stylesheet_keeps_the_images_inside_their_card(self):
        # css/plugin.css is written by build_plugin_pages.py: a rule added by hand there is lost on the next build, and
        # without it a 1840 px screenshot overflows the page.
        css = (ROOT / "css" / "plugin.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.atl-shot img \{[^}]*width: 100%")
        self.assertRegex(css, r"\.ph-media img[^{]*\{[^}]*width: 100%")


if __name__ == "__main__":
    unittest.main()
