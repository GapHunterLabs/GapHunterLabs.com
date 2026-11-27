"""Redesign of the Sponsors and Blog pages (2026-11-26): organization, boxes and metadata.

    python -m unittest discover -s pipeline/tests -v
"""
import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build_blog as B  # noqa: E402

SITE = "https://gaphunterlabs.com"
DASH = re.compile("[–—]|&mdash;|&ndash;")
DATA = json.loads((ROOT / "data" / "blog-cases.json").read_text(encoding="utf-8"))
CASES = DATA["cases"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def visible(text):
    """The page without scripts and styles: what a reader or a crawler reads."""
    return re.sub(r"<script\b.*?</script>|<style\b.*?</style>", "", text, flags=re.S)


class SponsorsTest(unittest.TestCase):
    PAGES = ("sponsors/index.html", "es/patrocinadores/index.html")

    def test_proof_comes_before_the_ask(self):
        for rel in self.PAGES:
            order = re.findall(r'aria-labelledby="(sec-[a-z]+)"', read(rel))
            with self.subTest(rel=rel):
                self.assertEqual(order[0], "sec-reach", "the figures of the work open the page")
                self.assertLess(order.index("sec-reach"), order.index("sec-levels"))
                self.assertLess(order.index("sec-independence"), order.index("sec-join"), "independence is read before paying")

    def test_audience_figures_and_questions_fold_away_but_stay_in_the_page(self):
        for rel in self.PAGES:
            text = read(rel)
            with self.subTest(rel=rel):
                self.assertRegex(text, r'<details class="sp-more"><summary>[^<]+</summary><div class="sp-audience">')
                self.assertEqual(text.count('<details class="sp-faq"><summary><h3>'), 6)
                self.assertEqual(text.count("sp-audience .tw-bg-bg"), 0)
                self.assertEqual(len(re.findall(r'class="tw-bg-bg tw-p-5"', text)), 8, "all eight figures are still there")

    def test_rail_is_an_index_of_the_page_not_a_repeat(self):
        for rel in self.PAGES:
            text = read(rel)
            rail = text[text.index('<aside class="page-insights"'):]
            rail = rail[:rail.index("</aside>")]
            anchors = re.findall(r'href="#(sec-[a-z]+)"', rail)
            with self.subTest(rel=rel):
                self.assertEqual(len(anchors), 5)
                for a in anchors:
                    self.assertIn('id="%s"' % a, text, "the rail links to a section that is not on the page")
                self.assertNotIn("USD", rail, "the rail no longer repeats the prices")

    def test_no_dash_anywhere_a_reader_sees(self):
        for rel in self.PAGES:
            self.assertIsNone(DASH.search(visible(read(rel))), rel)


class BlogTest(unittest.TestCase):
    PAGES = (("writing/index.html", "/writing/", "en"), ("es/escritos/index.html", "/es/escritos/", "es"))

    def test_head_without_dashes_and_within_the_results_page(self):
        for rel, _, lang in self.PAGES:
            text = read(rel)
            title = html.unescape(re.search(r"<title>(.*?)</title>", text).group(1))
            desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', text).group(1))
            with self.subTest(lang=lang):
                self.assertLessEqual(len(title), 60, title)
                self.assertTrue(120 <= len(desc) <= 160, (len(desc), desc))
                self.assertIsNone(DASH.search(visible(text)), "a dash on the %s Blog" % lang)

    def test_blog_jsonld_in_each_language(self):
        for rel, path, lang in self.PAGES:
            text = read(rel)
            blocks = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]
            blog = [b for b in blocks if b.get("@type") == "Blog"]
            with self.subTest(lang=lang):
                self.assertEqual(len(blog), 1)
                self.assertEqual(blog[0]["url"], SITE + path)
                self.assertEqual(blog[0]["inLanguage"], lang)
                self.assertEqual(len(blog[0]["blogPost"]), len(DATA["posts"]))
                for post in blog[0]["blogPost"]:
                    self.assertTrue(post["url"].startswith(SITE + path), post["url"])
                    self.assertIsNone(DASH.search(post["headline"]))

    def test_filters_carry_the_counts_of_the_cases_and_hide_until_javascript(self):
        f = B.filters_html(CASES)
        self.assertIn("data-blog-filters hidden", f, "without JavaScript the bar is hidden and every case shows")
        self.assertIn("<span>All areas</span> <b>%d</b>" % len(CASES), f)
        for k, label in B.CATS.items():
            n = sum(1 for c in CASES if c["cat"] == k)
            if n:
                self.assertIn('data-bf-cat="%s" aria-pressed="false"><span>%s</span> <b>%d</b>' % (k, label, n), f)
        for k, (label, _, _) in B.STATUS.items():
            n = sum(1 for c in CASES if c["status"] == k)
            if n:
                self.assertIn('data-bf-status="%s" aria-pressed="false"><span>%s</span> <b>%d</b>' % (k, label, n), f)

    def test_an_empty_bucket_gets_no_filter_button(self):
        only = [c for c in CASES if c["status"] == "fixed"]
        f = B.filters_html(only)
        self.assertNotIn('data-bf-status="open"', f)
        self.assertNotIn('data-bf-status="review"', f)
        self.assertNotIn("<b>0</b>", f)

    def test_case_card_shows_the_result_and_folds_the_problem_and_the_work(self):
        for c in CASES:
            card = B.case_html(c)
            with self.subTest(case=c["id"]):
                self.assertIn('data-cat="%s" data-status="%s"' % (c["cat"], c["status"]), card)
                self.assertIn('<p class="case-outcome">', card)
                self.assertIn(c["result"], card.split('<details')[0], "the result is visible without opening anything")
                fold = card[card.index("<details"):card.index("</details>")]
                self.assertIn(c["problem"], fold)
                self.assertIn(c["work"], fold)
                self.assertEqual(card.count("data-ev-date="), len(c["events"]), "the calendar still reads every date")

    def test_the_page_carries_every_case_and_the_post_as_a_feature(self):
        for rel, _, lang in self.PAGES:
            text = read(rel)
            with self.subTest(lang=lang):
                self.assertEqual(text.count('<article class="case blog-item"'), len(CASES))
                self.assertEqual(text.count('class="case case--post blog-item"'), len(DATA["posts"]))
                self.assertRegex(text, r'<main [^>]*data-reveal="none"')
                self.assertIn("data-blog-grid", text)

    def test_the_article_has_no_dash_in_either_language(self):
        for rel in ("writing/background-readaction-freeze/index.html", "es/escritos/background-readaction-freeze/index.html",
                    "pipeline/i18n/writing/background-readaction-freeze.es-main.html"):
            self.assertIsNone(DASH.search(read(rel)), rel)

    def test_hidden_cards_really_hide(self):
        css = read("css/blog.css")
        self.assertRegex(css, r"\.case\[hidden\][^{]*\{\s*display:\s*none")
        self.assertRegex(css, r"\.blog-filters\[hidden\][^{]*\{\s*display:\s*none|\.case\[hidden\], \.blog-filters\[hidden\]")


if __name__ == "__main__":
    unittest.main()
