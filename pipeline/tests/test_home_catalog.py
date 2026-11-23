"""The home catalog section and the bound plugin counts: every number comes from the data, so the twice-daily
rebuild (update-catalog.yml runs regenerate.py, which runs build_home.py) keeps them current.

    python -m unittest discover -s pipeline/tests -v
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))
import build_home as H  # noqa: E402

DATA = json.loads((ROOT / "data" / "catalog-data.json").read_text(encoding="utf-8"))
VSCODE = json.loads((ROOT / "data" / "vscode-catalog-data.json").read_text(encoding="utf-8"))["totalExtensions"]
TOTAL = DATA["totalPlugins"] + VSCODE


def strip_comments(s):
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)


class HomeCatalogTest(unittest.TestCase):
    def setUp(self):
        self.en = strip_comments((ROOT / "index.html").read_text(encoding="utf-8"))
        self.es = strip_comments((ROOT / "es" / "index.html").read_text(encoding="utf-8"))

    def test_title_and_link_carry_the_current_total(self):
        self.assertIn('id="catalogTitle">%d engineering tools,<br>one place</h2>' % TOTAL, self.en)
        self.assertIn('All %d tools &rarr;' % TOTAL, self.en)
        self.assertIn('id="catalogTitle">%d herramientas' % TOTAL, self.es)
        self.assertIn('Ver las %d herramientas' % TOTAL, self.es)

    def test_no_other_tool_count_is_typed_by_hand(self):
        section = self.en.split('id="catalog"')[1].split("</section>")[0]
        numbers = {int(n.replace(",", "")) for n in re.findall(r">\s*(\d[\d,]*)\s*(?:engineering tools|tools)", section)}
        self.assertEqual(numbers, {TOTAL})
        self.assertNotIn("nb-cat-counter", section)

    def test_featured_cards_follow_the_data(self):
        by_repo = {p["repo"]: p for p in DATA["plugins"]}
        cards = re.findall(r'<a class="nb-feat" href="/catalog/([^/]+)/"><span class="nb-feat-name">([^<]+)</span>'
                           r'<span class="nb-feat-meta">([\d,]+) downloads</span><span class="badge badge-status ([a-z-]+)">', self.en)
        self.assertEqual([c[0] for c in cards], list(H.FEATURED))
        for repo, name, downloads, cls in cards:
            p = by_repo[repo]
            with self.subTest(repo=repo):
                self.assertEqual(name, p["name"])
                self.assertEqual(int(downloads.replace(",", "")), p["downloads"])
                self.assertEqual(cls, H.PRICE_LABEL[p["pricing"]][1])

    def test_a_bad_featured_plugin_stops_the_build(self):
        cases = {"missing": lambda d: d["plugins"].pop(next(i for i, p in enumerate(d["plugins"]) if p["repo"] == H.FEATURED[0])),
                 "unknown price": lambda d: next(p for p in d["plugins"] if p["repo"] == H.FEATURED[1]).update(pricing="PENDING"),
                 "no downloads": lambda d: next(p for p in d["plugins"] if p["repo"] == H.FEATURED[2]).update(downloads=None)}
        for label, change in cases.items():
            d = copy.deepcopy(DATA)
            change(d)
            with self.subTest(case=label), self.assertRaises(SystemExit):
                H.featured_html(d)

    def test_names_are_escaped(self):
        d = copy.deepcopy(DATA)
        next(p for p in d["plugins"] if p["repo"] == H.FEATURED[0])["name"] = "<script>x</script>"
        self.assertNotIn("<script>", H.featured_html(d))


class BoundCountsTest(unittest.TestCase):
    VALUES = {"jetbrains": "147", "vscode": "33", "tools": "180"}

    def test_bindings_are_rewritten_from_the_data(self):
        self.assertEqual(H.bind_counts("a <!--count:jetbrains-->146 b <!--count:tools-->1,000", self.VALUES, "t"),
                         "a <!--count:jetbrains-->147 b <!--count:tools-->180")

    def test_unknown_or_missing_bindings_stop_the_build(self):
        with self.assertRaises(SystemExit):
            H.bind_counts("<!--count:plugins-->146", self.VALUES, "t")
        with self.assertRaises(SystemExit):
            H.bind_counts("146 plugins in my catalog", self.VALUES, "t")

    def test_every_bound_page_shows_the_current_count_in_both_languages(self):
        es_paths = {"custom-plugins-inspections/index.html": "es/plugins-e-inspecciones-a-medida/index.html",
                    "plugin-performance-audit/index.html": "es/auditoria-de-rendimiento/index.html",
                    "plugin-updates/index.html": "es/actualizacion-de-plugins/index.html"}
        self.assertEqual(set(es_paths), set(H.COUNT_PAGES))
        for rel in H.COUNT_PAGES:
            en = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                bound = re.findall(r"<!--count:jetbrains-->(\d+) plugins", en)
                self.assertTrue(bound)
                self.assertEqual(set(bound), {str(DATA["totalPlugins"])})
                # no plugin count left unbound in the page text
                self.assertEqual(len(re.findall(r"(?<![\d>])\d{3} plugins", strip_comments(en))), len(bound))
                es = (ROOT / es_paths[rel]).read_text(encoding="utf-8")
                self.assertIn("%d plugins" % DATA["totalPlugins"], es)


class CronTest(unittest.TestCase):
    def test_the_twice_daily_update_runs_the_home_generator(self):
        wf = (ROOT / ".github" / "workflows" / "update-catalog.yml").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'cron: "[^"]+"', wf)), 2)
        self.assertIn("pipeline/regenerate.py", wf)
        import regenerate as R
        self.assertIn("build_home.py", [s[0] for s in R.STEPS])


if __name__ == "__main__":
    unittest.main()
