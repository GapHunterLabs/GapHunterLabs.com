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


if __name__ == "__main__":
    unittest.main()
