"""The catalog index after the 2026-11-24 SEO and UX audit: structured data in the page's language, one Organization entity,
no internal notes in the served HTML, no dashes in what a reader or a crawler sees, and grids that are never hidden by the
scroll reveal.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build_i18n  # noqa: E402

SITE = "https://gaphunterlabs.com"
PAGES = {"en": "catalog/index.html", "es": "es/catalogo/index.html"}
MARKER = re.compile(r"^\s*/?(PRERENDER|CHROME|HREFLANG|LANG|STUBMETA|svc:|count:)")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def jsonld(text):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S)]


def collection(text):
    return next(b for b in jsonld(text) if b.get("@type") == "CollectionPage")


def organization(text):
    for b in jsonld(text):
        for node in b.get("@graph") or [b]:
            if node.get("@type") == "Organization":
                return node
    return None


class CatalogStructuredDataTest(unittest.TestCase):
    def test_the_spanish_collection_page_is_spanish(self):
        es = collection(read(PAGES["es"]))
        self.assertEqual(es["url"], SITE + "/es/catalogo/")
        self.assertEqual(es["inLanguage"], "es")
        self.assertNotEqual(es["name"], collection(read(PAGES["en"]))["name"])
        items = es["mainEntity"]["itemListElement"]
        english = [i["url"] for i in items if i["url"].startswith(SITE + "/catalog/")]
        self.assertEqual(english, [], "Spanish catalog lists English plugin pages")
        for item in items[:5]:
            path = item["url"][len(SITE):].strip("/")
            self.assertTrue((ROOT / path / "index.html").is_file(), item["url"])

    def test_the_english_collection_page_is_english(self):
        en = collection(read(PAGES["en"]))
        self.assertEqual((en["url"], en["inLanguage"]), (SITE + "/catalog/", "en"))
        self.assertTrue(all(i["url"].startswith(SITE + "/catalog/") for i in en["mainEntity"]["itemListElement"]))
        self.assertIn("VS Code", en["description"])
        self.assertEqual(en["isPartOf"], {"@id": SITE + "/#website"})

    def test_one_organization_entity_across_home_and_catalog(self):
        home = organization(read("index.html"))
        for rel in PAGES.values():
            org = organization(read(rel))
            self.assertEqual(org["@id"], home["@id"])
            self.assertEqual(org["description"], home["description"], rel)

    def test_translation_reaches_a_jsonld_block_with_attributes(self):
        src = ('<script type="application/ld+json" id="catalog-jsonld">{"@type":"CollectionPage","url":"%s/catalog/",'
               '"inLanguage":"en","mainEntity":{"itemListElement":[{"url":"%s/catalog/mermaid-companion/"}]}}</script>') % (SITE, SITE)
        out = build_i18n.translate_jsonld_text(src, {})
        self.assertIn('"url":"%s/es/catalogo/"' % SITE, out)
        self.assertIn('"inLanguage":"es"', out)
        self.assertIn("%s/es/catalogo/mermaid-companion/" % SITE, out)

    def test_untranslatable_and_unknown_blocks_stay_as_they_are(self):
        org = '<script type="application/ld+json">{"@type":"Organization","url":"%s/catalog/","inLanguage":"en"}</script>' % SITE
        self.assertEqual(build_i18n.translate_jsonld_text(org, {}), org)
        unknown = ('<script type="application/ld+json" id="x">{"@type":"CollectionPage","url":"%s/no-such-page/"}</script>' % SITE)
        self.assertIn("%s/no-such-page/" % SITE, build_i18n.translate_jsonld_text(unknown, {}))


class CatalogServedHtmlTest(unittest.TestCase):
    def test_no_internal_notes_in_the_html(self):
        for rel in PAGES.values():
            notes = [c.strip()[:60] for c in re.findall(r"<!--(.*?)-->", read(rel), re.S) if not MARKER.match(c)]
            self.assertEqual(notes, [], rel)

    def test_no_dashes_outside_scripts(self):
        for rel in PAGES.values():
            text = re.sub(r"<script\b.*?</script>", "", read(rel), flags=re.S)
            self.assertIsNone(re.search("[–—]", text), rel)

    def test_title_and_description_fit_the_results_page(self):
        for rel in PAGES.values():
            text = read(rel)
            title = re.search(r"<title>(.*?)</title>", text).group(1)
            desc = re.search(r'<meta name="description" content="([^"]*)"', text).group(1)
            self.assertLessEqual(len(title), 60, rel)
            self.assertTrue(120 <= len(desc) <= 160, "%s: %d" % (rel, len(desc)))

    def test_the_grids_are_never_hidden_by_the_scroll_reveal(self):
        for rel in PAGES.values():
            text = read(rel)
            for grid in ("catalogGrid", "vsxGrid", "atlassianGrid"):
                tag = re.search(r'<div [^>]*id="%s"[^>]*>' % grid, text).group(0)
                self.assertIn('data-reveal="none"', tag, "%s %s" % (rel, grid))
        self.assertIn("[data-reveal='none']", read("js/site-reveal.js"))


class CatalogExploreSectionTest(unittest.TestCase):
    """2026-11-24: one control per job. The hero no longer repeats the counts the tabs carry, the category board is
    the only category control (outside the grid view, so the table can use it too), the panels no longer repeat the
    tab's platform as an eyebrow, the pricing options carry their counts, and the grid can be sorted."""

    def test_no_duplicate_controls_or_labels(self):
        for rel in PAGES.values():
            text = read(rel)
            self.assertNotIn('id="categoryFilter"', text, rel)
            self.assertNotIn('class="ch-proof"', text, rel)
            self.assertIsNone(re.search(r'<p class="cv-eyebrow">[^<]*Marketplace</p>', text), rel)
            self.assertEqual(text.count('class="catalog-explore"'), 1, rel)
            self.assertLess(text.index('class="catalog-explore"'), text.index('id="fieldView"'), rel)
            self.assertGreater(text.index('class="catalog-explore"'), text.index('id="controls"'), rel)

    def test_pricing_options_carry_the_counts_of_the_data(self):
        data = json.loads(read("data/catalog-data.json"))["plugins"]
        by = {k: sum(1 for p in data if p.get("pricing") == k) for k in ("FREE", "FREEMIUM", "PAID")}
        text = read(PAGES["en"])
        options = dict(re.findall(r'<option value="([A-Z]+)">[^<(]*\((\d+)\)</option>', text))
        self.assertEqual(int(options["FREE"]), by["FREE"])
        self.assertEqual(int(options["PAIDANY"]), by["FREEMIUM"] + by["PAID"])
        self.assertIn("Gratis (%d)" % by["FREE"], read(PAGES["es"]))

    def test_the_grid_has_a_sort_control_in_both_languages(self):
        for rel, labels in ((PAGES["en"], ("Most downloaded", "Name, A to Z")), (PAGES["es"], ("Más descargados", "Nombre, de la A a la Z"))):
            text = read(rel)
            select = re.search(r'<select id="sortOrder"[^>]*>(.*?)</select>', text, re.S).group(1)
            self.assertEqual(re.findall(r'value="(\w+)"', select), ["downloads", "rating", "newest", "name"], rel)
            for label in labels:
                self.assertIn(label, select, rel)
        js = read("js/catalog.js")
        for key in ("downloads:", "rating:", "newest:", "name:"):
            self.assertIn(key, js)
        self.assertNotIn("categoryFilter", js)


class CatalogItemListTest(unittest.TestCase):
    def test_the_item_list_has_the_three_platforms(self):
        vs = json.loads(read("data/vscode-catalog-data.json"))["extensions"]
        atl = json.loads(read("data/atlassian-catalog-data.json"))["apps"]
        jb = json.loads(read("data/catalog-data.json"))["plugins"]
        for lang, rel in PAGES.items():
            ld = collection(read(rel))["mainEntity"]
            items = ld["itemListElement"]
            self.assertEqual(ld["numberOfItems"], len(items))
            self.assertEqual(len(items), len(jb) + len(vs) + len(atl))
            self.assertEqual([i["position"] for i in items], list(range(1, len(items) + 1)))
            base = SITE + ("/es/catalogo/" if lang == "es" else "/catalog/")
            self.assertTrue(any(i["url"] == base + "vscode/%s/" % vs[0]["name"] for i in items), lang)
            self.assertTrue(any(i["url"] == base + "atlassian/%s/" % atl[0]["name"] for i in items), lang)
            for i in items:
                self.assertTrue((ROOT / i["url"][len(SITE):].strip("/") / "index.html").is_file(), i["url"])


import build_plugin_pages as bpp  # noqa: E402


class PluginPagesWithoutDashesTest(unittest.TestCase):
    """2026-11-24: the plugin pages had six dashes each (title, social titles, image alts) and more in the empty-value
    marks and in our own gap prose. Quotes of users and documentation stay verbatim."""

    def test_prose_without_dashes(self):
        f = bpp.prose_without_dashes
        self.assertEqual(f("A — an aside — ends."), "A (an aside) ends.")
        self.assertEqual(f("A — the leading one (430K) — has it."), "A, the leading one (430K), has it.")
        self.assertEqual(f("One — two."), "One: two.")
        self.assertEqual(f("Note: one — two."), "Note: one, two.")
        self.assertEqual(f("since 2009–2010"), "since 2009-2010")
        self.assertEqual(f("freezes —"), "freezes:")
        kept = 'they said "slow — broken" and `a — b`'
        self.assertEqual(f(kept), kept)
        self.assertEqual(f(None), "")
        self.assertEqual(f(""), "")

    def test_no_dash_in_titles_social_titles_or_alts(self):
        tags = re.compile(r'<title>[^<]*</title>|<meta (?:property|name)="(?:og:title|twitter:title|og:image:alt|twitter:image:alt)" content="[^"]*">')
        for page in list((ROOT / "catalog").glob("**/index.html")) + list((ROOT / "es" / "catalogo").glob("**/index.html")):
            for tag in tags.findall(page.read_text(encoding="utf-8")):
                self.assertIsNone(re.search("[–—]", tag), "%s: %s" % (page, tag))

    def test_dashes_left_in_the_pages_are_only_inside_quotes(self):
        for page in list((ROOT / "catalog").glob("*/index.html")) + list((ROOT / "es" / "catalogo").glob("*/index.html")):
            text = re.sub(r"<script\b.*?</script>", "", page.read_text(encoding="utf-8"), flags=re.S)
            text = re.sub(r"&quot;.*?&quot;|“.*?”|<code>.*?</code>|<em>&quot;.*?</em>", "", text, flags=re.S)
            self.assertIsNone(re.search("[–—]", text), str(page))


class PluginGapsInSpanishTest(unittest.TestCase):
    def test_every_gap_has_a_current_translation(self):
        build_i18n._GAPS = None
        by_path, stale = build_i18n._gap_tables()
        self.assertEqual(stale, [])
        self.assertEqual(len(by_path), len(json.loads(read("data/catalog-data.json"))["plugins"]))

    def test_the_spanish_pages_show_the_spanish_gap(self):
        for path, (en_html, es_html) in list(build_i18n._gap_tables()[0].items())[:20]:
            es_page = read("es/catalogo/%s/index.html" % path.strip("/").split("/")[-1])
            self.assertIn('<div class="pb-text">%s</div>' % es_html, es_page, path)
            if en_html != es_html:
                self.assertNotIn('<div class="pb-text">%s</div>' % en_html, es_page, path)

    def test_a_changed_english_gap_counts_as_missing(self):
        saved = build_i18n.GAPS_FILE
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            stored = json.loads(saved.read_text(encoding="utf-8"))
            key = sorted(stored)[0]
            stored[key]["en"] += " changed"
            fake = Path(d) / "gaps.json"
            fake.write_text(json.dumps(stored), encoding="utf-8")
            try:
                build_i18n.GAPS_FILE, build_i18n._GAPS = fake, None
                self.assertIn(key, build_i18n._gap_tables()[1])
            finally:
                build_i18n.GAPS_FILE, build_i18n._GAPS = saved, None

    def test_gap_texts_are_complete_and_free_of_internal_process_language(self):
        # 2026-11-24: 14 gap texts named internal process ("idea-validation discipline", "~10-day budget", "this session",
        # "Tier -3", a Spanish working phrase) and 17 were cut mid-sentence by a 600-character limit upstream.
        internal = re.compile(r"idea-validation discipline|10-day budget|this session|other 8 Gap Hunter|apuesta consciente|"
                              r"ancla de mercado|Tier -3|this workspace|disciplina de validación|presupuesto de ~10|esta sesión",
                              re.I)
        renderer = bpp.PluginRenderer(bpp.Sources())
        stored = json.loads(build_i18n.GAPS_FILE.read_text(encoding="utf-8"))
        for p in renderer.src.plugins:
            gap = renderer.gap_text(p).rstrip()
            es = stored["jetbrains:" + p["repo"]]["es"].rstrip()
            for text in (gap, es):
                self.assertIsNone(internal.search(text), p["repo"])
                self.assertRegex(text, r'[.!?)"”*`\]]$', "%s ends mid-sentence" % p["repo"])

    def test_a_social_title_is_kept_only_for_an_exact_plugin_name(self):
        name = sorted(build_i18n.NAMES)[0]
        self.assertEqual(build_i18n.lookup("%s | Gap Hunter Labs" % name, {}), "%s | Gap Hunter Labs" % name)
        self.assertIsNone(build_i18n.lookup("An English sentence nobody translated | Gap Hunter Labs", {}))


if __name__ == "__main__":
    unittest.main()
