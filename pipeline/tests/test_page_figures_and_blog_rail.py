"""The hand-made pages' figures (build_page_figures.py) and the Blog side rail (build_blog.py).

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))
import build_blog as B  # noqa: E402
import build_page_figures as PF  # noqa: E402
import regenerate as R  # noqa: E402

RAIL_RE = re.compile(re.escape(B.RAIL_START) + r"(.*?)" + re.escape(B.RAIL_END), re.S)


class PageFiguresTest(unittest.TestCase):
    def _tree(self, page_text):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for rel, _ in PF.PAGES:
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_bytes((ROOT / rel).read_bytes())
        return tmp

    def test_every_page_holds_its_markers_once_and_the_figure_inside(self):
        for rel, figure in PF.PAGES:
            html = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertEqual(html.count("<!-- PRERENDER:ISO:%s:START -->" % figure), 1)
                block = html.split("<!-- PRERENDER:ISO:%s:START -->" % figure)[1].split("<!-- PRERENDER:ISO:%s:END -->" % figure)[0]
                self.assertTrue(block.startswith('<svg class="iso-figure"'))
                self.assertIn('id="iso-%s-' % figure, block)
                self.assertIn('class="page-hero band-dark gh-page-header has-figure"', html)

    def test_the_build_is_idempotent_and_keeps_line_endings(self):
        tmp = self._tree(None)
        crlf = tmp / PF.PAGES[0][0]
        crlf.write_bytes(crlf.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        before = crlf.read_bytes()
        PF.build(tmp)
        self.assertEqual(crlf.read_bytes(), before)            # already up to date: nothing changes
        self.assertEqual(PF.build(tmp), [])

    def test_missing_or_duplicated_markers_stop_the_build(self):
        rel, figure = PF.PAGES[1]
        start = "<!-- PRERENDER:ISO:%s:START -->" % figure
        end = "<!-- PRERENDER:ISO:%s:END -->" % figure
        for label, change in (("missing", lambda h: re.sub(re.escape(start) + ".*?" + re.escape(end), "", h, flags=re.S)),
                              ("duplicated", lambda h: h.replace("</main>", start + end + "</main>", 1))):
            tmp = self._tree(None)
            page = tmp / rel
            page.write_text(change(page.read_text(encoding="utf-8")), encoding="utf-8")
            with self.subTest(case=label), self.assertRaises(SystemExit) as cm:
                PF.build(tmp)
            self.assertIn("PRERENDER:ISO:%s" % figure, str(cm.exception))

    def test_every_hand_made_page_with_a_figure_is_rebuilt_by_this_generator(self):
        # A page left out of PAGES keeps its old inlined SVG and silently goes stale when the figure changes.
        owned = {"index.html", "catalog/index.html", "sponsors/index.html", "engineering-evidence/index.html"}
        marker = re.compile(r"<!-- PRERENDER:ISO:([a-z0-9-]+):START -->")
        found = set()
        for page in ROOT.glob("**/index.html"):
            rel = page.relative_to(ROOT).as_posix()
            if rel.startswith(("es/", "node_modules/", "pipeline/")) or "/node_modules/" in rel or rel in owned:
                continue
            for figure in marker.findall(page.read_text(encoding="utf-8", errors="replace")):
                found.add((rel, figure))
        self.assertEqual(found, set(PF.PAGES))

    def test_it_runs_after_the_blog_and_before_the_spanish_copy(self):
        order = [s[0] for s in R.STEPS]
        self.assertLess(order.index("build_blog.py"), order.index("build_page_figures.py"))
        self.assertLess(order.index("build_page_figures.py"), order.index("build_i18n.py"))


class BlogRailTest(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT / "data" / "blog-cases.json").read_text(encoding="utf-8"))["cases"]

    def counts(self, html, eyebrow):
        card = html.split('<p class="pi-eyebrow">%s</p>' % eyebrow)[1].split("</ul>")[0]
        return [int(n) for n in re.findall(r"<b>(\d+)</b>", card)]

    def test_counts_come_from_the_cases(self):
        html = B.rail_html(self.cases)
        self.assertEqual(sum(self.counts(html, "Cases by status")), len(self.cases))
        self.assertEqual(sum(self.counts(html, "Cases by area")), len(self.cases))
        fixed = sum(1 for c in self.cases if c["status"] == "fixed")
        self.assertIn("<li><b>%d</b> Fixed</li>" % fixed, html)

    def test_an_empty_bucket_is_left_out_not_shown_as_zero(self):
        only_fixed = [c for c in self.cases if c["status"] == "fixed"]
        html = B.rail_html(only_fixed)
        self.assertNotIn("In review", html)
        self.assertNotIn("<b>0</b>", html)
        self.assertEqual(sum(self.counts(html, "Cases by area")), len(only_fixed))

    def test_the_built_pages_carry_the_same_rail(self):
        en = (ROOT / "writing" / "index.html").read_text(encoding="utf-8")
        es = (ROOT / "es" / "escritos" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(RAIL_RE.search(en).group(1), B.rail_html(self.cases))
        self.assertEqual(en.count(B.RAIL_START), 1)
        rail_es = RAIL_RE.search(es).group(1)
        self.assertIn("Casos por estado", rail_es)
        self.assertIn('href="/es/escritos/feed.xml"', rail_es)    # each language links its own feed
        self.assertNotIn("/writing/feed.xml", rail_es)
        for href in re.findall(r'href="([^"]+)"', rail_es + RAIL_RE.search(en).group(1)):
            self.assertTrue(href.startswith("/") or href.startswith("#"), href)


if __name__ == "__main__":
    unittest.main()
