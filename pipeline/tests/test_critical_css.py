"""Critical CSS of the home (pipeline/critical_css.py): what inline() accepts and rejects, its size caps, and the
committed pages. The browser side (the first screen with only this CSS equals the full page) is checked by
_review/verify_site.py.

    python -m unittest discover -s pipeline/tests -v
"""
import gzip
import os
import random
import re
import string
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import critical_css as C  # noqa: E402
import regenerate as R  # noqa: E402

SHEETS = ('<link rel="stylesheet" href="/css/theme.css?v=1">\n'
          '<link rel="stylesheet" href="/css/shell.css?v=2">\n')
CSS = "a{color:red}"


def page(head_extra="", block='<style id="critical-css"></style>', body_sheets=SHEETS, after_main=True):
    sheets_before = "" if after_main else body_sheets
    sheets_after = body_sheets if after_main else ""
    return ("<!doctype html><html><head><title>t</title>%s%s</head><body>%s<main>m</main><footer>f</footer>%s"
            "</body></html>" % (block, head_extra, sheets_before, sheets_after))


def incompressible(n):
    rnd = random.Random(7)
    return "a{content:'%s'}" % "".join(rnd.choice(string.ascii_letters + string.digits) for _ in range(n - 14))


class InlineTest(unittest.TestCase):
    def test_fills_the_block_and_is_idempotent(self):
        once = C.inline(page(), CSS, "p")
        self.assertIn('<style id="critical-css">a{color:red}</style>', once)
        self.assertEqual(C.inline(once, CSS, "p"), once)

    def test_replaces_old_content(self):
        old = C.inline(page(), "b{color:blue}", "p")
        self.assertNotIn("blue", C.inline(old, CSS, "p"))

    def test_backslash_escapes_survive(self):
        css = 'a::before{content:"\\2192 \\\\ \\g<0> \\1"}'
        self.assertIn(css, C.inline(page(), css, "p"))

    def test_bad_css_stops_the_build(self):
        for label, css in {"empty": "", "blank": " \n\t ", "none": None, "not a string": 5,
                           "ends the style element": "a{}</style><script>x()</script>",
                           "any closing tag": "a{content:'</b>'}"}.items():
            with self.subTest(case=label), self.assertRaises(SystemExit):
                C.inline(page(), css, "p")

    def test_bad_layout_stops_the_build(self):
        # Each case names the message it must get: a head stylesheet is also "before </main>", so only the message
        # proves which guard caught it.
        cases = {
            "no block": (page(block=""), "exactly one"),
            "two blocks": (page(head_extra='<style id="critical-css"></style>'), "found 2"),
            "block outside head": (page(block="").replace("<main>", '<style id="critical-css"></style><main>'),
                                   "outside <head>"),
            "stylesheet still in head": (page(head_extra='<link rel="stylesheet" href="/css/home.css?v=3">'),
                                         "stylesheet in <head>"),
            "no stylesheet at all": (page(body_sheets=""), "no stylesheet after <head>"),
            "stylesheet before </main>": (page(after_main=False), "before </main>"),
            "no head": (page().replace("<head>", "").replace("</head>", ""), "no <head>"),
            "no main": (page().replace("<main>m</main>", ""), "no </main>"),
        }
        for label, (html, message) in cases.items():
            with self.subTest(case=label), self.assertRaisesRegex(SystemExit, re.escape(message)):
                C.inline(html, CSS, "p")

    def test_other_style_blocks_and_head_links_are_left_alone(self):
        html = page(head_extra='<style>b{}</style><link rel="preload" href="/fonts/x.woff2" as="font">')
        out = C.inline(html, CSS, "p")
        self.assertIn("<style>b{}</style>", out)
        self.assertIn('rel="preload"', out)


class SizeCapTest(unittest.TestCase):
    def test_raw_cap_boundaries(self):
        at = "a{}" * (C.MAX_BYTES // 3)
        at += " " * (C.MAX_BYTES - len(at))
        self.assertEqual(len(at.encode()), C.MAX_BYTES)
        C.check_css("at the cap", at)                         # compresses well: only the raw cap applies
        with self.assertRaises(SystemExit):
            C.check_css("one over", at + " ")

    def test_raw_cap_counts_bytes_not_characters(self):
        css = "a{content:'%s'}" % ("é" * ((C.MAX_BYTES // 2) - 5))
        self.assertLessEqual(len(css), C.MAX_BYTES)
        self.assertGreater(len(css.encode("utf-8")), C.MAX_BYTES)
        with self.assertRaises(SystemExit):
            C.check_css("multibyte", css)

    def test_compressed_cap(self):
        under = incompressible(C.MAX_GZIP - 2000)
        self.assertLess(len(gzip.compress(under.encode(), 9, mtime=0)), C.MAX_GZIP)
        C.check_css("under", under)
        # Random letters and digits still compress to about 75 %, so the input is 1.5x the cap; the premise is checked.
        over = incompressible(int(C.MAX_GZIP * 1.5))
        self.assertLessEqual(len(over.encode()), C.MAX_BYTES)
        self.assertGreater(len(gzip.compress(over.encode(), 9, mtime=0)), C.MAX_GZIP)
        with self.assertRaises(SystemExit):
            C.check_css("over", over)


class CommittedPagesTest(unittest.TestCase):
    def test_both_homes_carry_the_committed_css(self):
        css = C.css_path("home").read_text(encoding="utf-8").strip()
        raw, packed = C.check_css("home", css)
        self.assertGreater(raw, 1000)
        for rel in ("index.html", "es/index.html"):
            html = (C.ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                C.check_layout(html, rel)
                self.assertEqual(C.BLOCK.search(html).group(1), css)
                self.assertEqual(len(C.SHEET.findall(html)), 4)

    def test_the_committed_file_is_one_line(self):
        # build_critical_css writes one line so git line-ending conversion cannot change the inlined copy: on a Windows
        # checkout only the final newline may become CRLF, and inline_critical_css strips it.
        text = C.css_path("home").read_bytes()
        self.assertTrue(text.endswith(b"\n"))
        body = text.rstrip(b"\r\n")
        self.assertNotIn(b"\n", body)
        self.assertNotIn(b"\r", body)

    def test_it_keeps_the_first_screen_basics(self):
        css = C.css_path("home").read_text(encoding="utf-8")
        for needle in ("@font-face", "--signal", "data-theme", ".nb-hero-title", ".gh-header", "prefers-color-scheme"):
            with self.subTest(needle=needle):
                self.assertIn(needle, css)

    def test_regenerate_inlines_after_the_english_pages_and_before_the_spanish_copy(self):
        names = [s for s, _, _ in R.STEPS]
        i = names.index("inline_critical_css.py")
        for before in ("build_chrome.py", "build_home.py", "build_page_figures.py", "build_plugin_pages.py"):
            self.assertLess(names.index(before), i, before)
        self.assertLess(i, names.index("build_i18n.py"))
        self.assertIn("build_critical_css.py", R.EXCLUDED)


if __name__ == "__main__":
    unittest.main()
