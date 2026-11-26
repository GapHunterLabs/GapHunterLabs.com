"""SEO and UX audit of the sponsors page and the plugin pages (2026-11-26): what the fixes guarantee.

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
import build_i18n  # noqa: E402
import build_plugin_pages  # noqa: E402

SITE = "https://gaphunterlabs.com"
DASH = re.compile("[–—]|&mdash;|&ndash;")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def plugin_pages(lang):
    base = ROOT / ("catalog" if lang == "en" else "es/catalogo")
    pages = sorted(base.glob("*/index.html")) + sorted((base / "vscode").glob("*/index.html")) + sorted((base / "atlassian").glob("*/index.html"))
    return [p for p in pages if "plugin-hero" in p.read_text(encoding="utf-8")]


def head_value(text, pattern):
    m = re.search(pattern, text)
    return html.unescape(m.group(1)) if m else None


def jsonld_graph(text):
    out = []
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S):
        d = json.loads(m.group(1))
        out.extend(d.get("@graph", [d]))
    return out


class SponsorsPageTest(unittest.TestCase):
    PAGES = {"en": "sponsors/index.html", "es": "es/patrocinadores/index.html"}

    def test_head_has_no_dashes_and_fits_the_results_page(self):
        for lang, rel in self.PAGES.items():
            text = read(rel)
            head = text[: text.index("</head>")]
            head_wo_scripts = re.sub(r"<script\b.*?</script>", "", head, flags=re.S)
            with self.subTest(lang=lang):
                self.assertIsNone(DASH.search(head_wo_scripts), "a dash in the head of %s" % rel)
                title = head_value(text, r"<title>(.*?)</title>")
                desc = head_value(text, r'<meta name="description" content="([^"]*)"')
                self.assertLessEqual(len(title), 60, title)
                self.assertGreaterEqual(len(desc), 120, desc)
                self.assertLessEqual(len(desc), 160, desc)

    def test_jsonld_declares_the_language_of_each_page(self):
        for lang, rel in self.PAGES.items():
            page = next(n for n in jsonld_graph(read(rel)) if n.get("@type") == "WebPage")
            with self.subTest(lang=lang):
                self.assertEqual(page.get("inLanguage"), lang)
                self.assertTrue(page["url"].endswith("/sponsors/" if lang == "en" else "/es/patrocinadores/"))

    def test_how_to_join_comes_right_after_the_levels(self):
        for lang, rel in self.PAGES.items():
            text = read(rel)
            order = [m.group(1) for m in re.finditer(r'aria-labelledby="(sec-[a-z]+)"', text)]
            with self.subTest(lang=lang, order=order):
                self.assertEqual(order[order.index("sec-levels") + 1], "sec-join")
                self.assertEqual(order.count("sec-join"), 1)

    def test_nothing_waits_for_the_scroll_animation(self):
        for rel in self.PAGES.values():
            self.assertRegex(read(rel), r'<main [^>]*class="methodology-main sp-page"[^>]*data-reveal="none"')


class PluginPagesTest(unittest.TestCase):
    def test_titles_fit_the_results_page_in_both_languages(self):
        for lang in ("en", "es"):
            pages = plugin_pages(lang)
            self.assertGreater(len(pages), 170, "%s plugin pages not found" % lang)
            for page in pages:
                title = head_value(page.read_text(encoding="utf-8"), r"<title>(.*?)</title>")
                with self.subTest(page=str(page.relative_to(ROOT))):
                    self.assertLessEqual(len(title), 60, title)
                    self.assertNotIn("…", title, "a cut niche in the title")
                    self.assertIsNone(DASH.search(title))

    def test_title_budget_drops_the_niche_instead_of_cutting_it(self):
        r = build_plugin_pages.PluginRenderer.__new__(build_plugin_pages.PluginRenderer)
        long_niche = {"name": "XPath Injection Sink Companion", "niche": "XPath Injection Detection"}
        t = r.title(long_niche)
        self.assertEqual(t, "XPath Injection Sink Companion for IntelliJ")
        short = r.title({"name": "Ansible Companion", "niche": "Ansible / DevOps"})
        self.assertEqual(short, "Ansible Companion: Ansible / DevOps for IntelliJ")
        tiny = r.title({"name": "Cert", "niche": "TLS"})
        self.assertEqual(tiny, "Cert: TLS for IntelliJ | Gap Hunter Labs")
        # Boundary: a name so long that even name + " for IntelliJ" does not fit keeps the whole name.
        huge = r.title({"name": "A" * 58, "niche": "x"})
        self.assertLessEqual(len(huge), build_plugin_pages.TITLE_SOFT_MAX + 1)
        for p in ({"name": "N" * n, "niche": "Some niche"} for n in range(5, 60)):
            self.assertLessEqual(len(r.title(p)), 60, p)

    def test_spanish_pages_declare_the_spanish_page_and_breadcrumb(self):
        for page in plugin_pages("es"):
            nodes = jsonld_graph(page.read_text(encoding="utf-8"))
            app = next(n for n in nodes if n.get("@type") == "SoftwareApplication")
            crumbs = next(n for n in nodes if n.get("@type") == "BreadcrumbList")["itemListElement"]
            rel = "/" + page.parent.relative_to(ROOT).as_posix() + "/"
            with self.subTest(page=rel):
                self.assertEqual(app["url"], SITE + rel)
                self.assertTrue(app["@id"].startswith(SITE + "/catalog/"), "the app keeps one identity in both languages")
                self.assertEqual(crumbs[0]["name"], "Inicio")
                self.assertEqual(crumbs[0]["item"], SITE + "/es/")
                self.assertEqual(crumbs[1]["name"], "Catálogo")
                for c in crumbs:
                    if "item" in c:
                        self.assertTrue(c["item"].startswith(SITE + "/es/"), c)

    def test_english_pages_keep_the_english_jsonld(self):
        for page in plugin_pages("en")[:40]:
            nodes = jsonld_graph(page.read_text(encoding="utf-8"))
            crumbs = next(n for n in nodes if n.get("@type") == "BreadcrumbList")["itemListElement"]
            self.assertEqual(crumbs[0], {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"})

    def test_breadcrumb_item_translation_unit(self):
        src = ('<script type="application/ld+json">{"@graph":[{"@type":"BreadcrumbList","itemListElement":['
               '{"item":"%s/"},{"item":"%s/catalog/?platform=vscode"},{"item":"https://example.com/catalog/"},'
               '{"item":"%s/no-such-page/"}]}]}</script>') % (SITE, SITE, SITE)
        out = build_i18n.translate_jsonld_text(src, {})
        self.assertIn('"item":"%s/es/"' % SITE, out)
        self.assertIn('"item":"%s/es/catalogo/?platform=vscode"' % SITE, out)
        self.assertIn('"item":"https://example.com/catalog/"', out, "an external URL never changes")
        self.assertIn('"item":"%s/no-such-page/"' % SITE, out, "a page without a Spanish version stays as it is")

    def test_hero_has_no_zero_stars_and_no_third_price(self):
        for lang in ("en", "es"):
            for page in plugin_pages(lang):
                text = page.read_text(encoding="utf-8")
                m = re.search(r'<div class="hdr-stats ph-stats"[^>]*>(.*?)</div></div>', text, re.S)
                if not m:
                    continue
                stats = re.findall(r'<span class="hdr-stat-num">(.*?)</span><span class="hdr-stat-label">(.*?)</span>', m.group(0))
                labels = [lab for _, lab in stats]
                with self.subTest(page=str(page.relative_to(ROOT))):
                    self.assertNotIn("Pricing", labels)
                    self.assertNotIn("Precio", labels)
                    for num, lab in stats:
                        if lab in ("GitHub stars", "Estrellas en GitHub"):
                            self.assertNotEqual(num, "0")
                    # the grid has as many columns as figures; without --n it is the default of 4 (VS Code, Jira)
                    if "--n:" in m.group(0):
                        self.assertIn('style="--n:%d"' % len(stats), m.group(0))
                    else:
                        self.assertEqual(len(stats), 4)

    def test_plugin_pages_do_not_wait_for_the_scroll_animation(self):
        for lang in ("en", "es"):
            for page in plugin_pages(lang)[:30]:
                self.assertRegex(page.read_text(encoding="utf-8"), r'<main [^>]*class="wrap" data-reveal="none">')

    def test_copy_button_is_a_24px_target(self):
        css = read("css/plugin.css")
        block = re.search(r"\.copy-btn \{(.*?)\}", css, re.S).group(1)
        self.assertIn("width: 24px", block)
        self.assertIn("height: 24px", block)

    def test_corrected_niches_and_their_category(self):
        data = {p["repo"]: p for p in json.loads(read("data/catalog-data.json"))["plugins"]}
        self.assertEqual(data["php-composer-script-companion"]["niche"], "PHP / Composer Tooling")
        self.assertEqual(data["ruby-gemfile-group-companion"]["niche"], "Ruby / Bundler Tooling")
        shared = read("js/catalog-shared.js")
        for niche in ("PHP / Composer Tooling", "Ruby / Bundler Tooling"):
            self.assertIn("'%s': 'devops'" % niche, shared, "%s would fall into Other" % niche)
        self.assertNotIn("All Other plugins", read("catalog/php-composer-script-companion/index.html"))


if __name__ == "__main__":
    unittest.main()
