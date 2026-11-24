"""The home check of _review/verify_seo.py (check 6) against the blocks build_home.py really pre-renders.

The home cut (#45) replaced the TOOLS block; verify_seo.py still required it, and since that script ran only in the
scheduled catalog update, the first sign was a red cron run. These tests keep the two lists together and pin what the
check rejects.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_review"))
import verify_seo as V  # noqa: E402


def block(name, body):
    return "<!-- PRERENDER:%s:START -->%s<!-- PRERENDER:%s:END -->" % (name, body, name)


FEATURED = '<a class="nb-feat" href="/catalog/openapi-companion/"><span class="nb-feat-name">OpenAPI</span></a>'


def home(**override):
    bodies = {name: "x" for name in V.HOME_PRERENDER_BLOCKS}
    bodies["CATFEATURED"] = FEATURED
    bodies.update(override)
    return "<html><body>%s</body></html>" % "".join(block(n, b) for n, b in bodies.items() if b is not None)


class HomeCheckTest(unittest.TestCase):

    def run_check(self, html):
        V.problems.clear()
        V.check_home(html)
        return list(V.problems)

    def test_the_blocks_checked_are_exactly_the_ones_build_home_injects_into_the_home(self):
        source = (ROOT / "pipeline" / "build_home.py").read_text(encoding="utf-8")
        injected = set(re.findall(r'inject\(html, "<!-- PRERENDER:([A-Z]+):START -->"', source))
        self.assertTrue(injected, "no inject(html, ...) calls found: the parser of this test needs updating")
        self.assertEqual(injected, set(V.HOME_PRERENDER_BLOCKS))

    def test_the_real_home_passes(self):
        self.assertEqual([], self.run_check((ROOT / "index.html").read_text(encoding="utf-8")))

    def test_a_complete_home_passes(self):
        self.assertEqual([], self.run_check(home()))

    def test_each_missing_or_empty_block_is_named(self):
        for name in V.HOME_PRERENDER_BLOCKS:
            for broken in (None, "", "   \n "):
                problems = self.run_check(home(**{name: broken}))
                self.assertTrue(any("el bloque %s " % name in p for p in problems), (name, broken, problems))

    def test_featured_cards_need_canonical_catalog_links(self):
        for href in ("/catalog/x", "https://example.com/catalog/x/", "/catalog/X/", "/catalog/a/b/", "catalog/x/"):
            card = FEATURED.replace("/catalog/openapi-companion/", href)
            problems = self.run_check(home(CATFEATURED=card))
            self.assertTrue(any("href no canonico" in p for p in problems), (href, problems))

    def test_a_featured_block_without_cards_fails(self):
        problems = self.run_check(home(CATFEATURED="<p>soon</p>"))
        self.assertTrue(any("ninguna herramienta destacada" in p for p in problems), problems)

    def test_the_old_tools_block_is_no_longer_required(self):
        self.assertNotIn("TOOLS", V.HOME_PRERENDER_BLOCKS)
        self.assertEqual([], self.run_check(home()))


if __name__ == "__main__":
    unittest.main()
