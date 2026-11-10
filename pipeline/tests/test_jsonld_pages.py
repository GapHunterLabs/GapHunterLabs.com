"""JSON-LD of the commercial pages (2026-11-09): present, valid, in the page's language, pointing to the page itself.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://gaphunterlabs.com"
PAIRS = {"/services/": "/es/servicios/", "/sponsors/": "/es/patrocinadores/", "/contact/": "/es/contacto/",
         "/engineering-evidence/": "/es/ingenieria-y-evidencia/"}


def blocks(path):
    text = (ROOT / path.strip("/") / "index.html").read_text(encoding="utf-8")
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', text).group(1)
    return canonical, [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]


class CommercialPagesTest(unittest.TestCase):
    def test_each_page_has_one_valid_block_about_itself(self):
        for en, es in PAIRS.items():
            for path in (en, es):
                with self.subTest(page=path):
                    canonical, found = blocks(path)
                    self.assertEqual(len(found), 1)
                    d = found[0]
                    self.assertEqual(d["url"], canonical)
                    self.assertEqual(d["@id"], canonical + "#webpage")
                    self.assertEqual(d["isPartOf"], {"@id": SITE + "/#website"})

    def test_spanish_blocks_are_translated(self):
        for en, es in PAIRS.items():
            with self.subTest(page=es):
                e, s = blocks(en)[1][0], blocks(es)[1][0]
                self.assertNotEqual(e["name"], s["name"])
                self.assertNotEqual(e["description"], s["description"])

    def test_services_catalog_follows_services_json(self):
        services = json.loads((ROOT / "data" / "services.json").read_text(encoding="utf-8"))["services"]
        for path in ("/services/", "/es/servicios/"):
            with self.subTest(page=path):
                org = blocks(path)[1][0]["mainEntity"]
                self.assertEqual(org["@id"], SITE + "/#org")   # the identity never moves to the Spanish URL
                offers = org["hasOfferCatalog"]["itemListElement"]
                self.assertEqual(len(offers), len(services))
                for offer in offers:
                    self.assertEqual(offer["priceSpecification"]["priceCurrency"], "USD")
                    self.assertTrue(offer["url"].startswith(SITE + ("/es/" if path.startswith("/es/") else "/")))
                    if path.startswith("/es/"):
                        self.assertTrue(offer["url"].startswith(SITE + "/es/"), offer["url"])


class BlogTest(unittest.TestCase):
    def test_every_english_page_with_a_spanish_pair_is_in_the_sitemap(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipeline"))
        from build_chrome import ES_PATHS
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        missing = [p for p in ES_PATHS if "<loc>%s%s</loc>" % (SITE, p) not in sitemap]
        self.assertEqual(missing, [])

    def test_spanish_article_card_is_spanish_and_the_blog_has_its_own_image(self):
        meta = lambda path, prop: re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % prop,
                                            (ROOT / path / "index.html").read_text(encoding="utf-8")).group(1)
        en, es = "writing/background-readaction-freeze", "es/escritos/background-readaction-freeze"
        self.assertNotEqual(meta(en, "og:title"), meta(es, "og:title"))
        self.assertTrue(meta(es, "og:title").startswith("Una acción de lectura"))
        for path, image in (("writing", "og-blog.png"), ("es/escritos", "og-blog.es.png"), (en, "og-blog.png")):
            self.assertIn("/" + image + "?v=", meta(path, "og:image"))
            png = (ROOT / image).read_bytes()
            self.assertEqual((int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")), (1200, 630))


if __name__ == "__main__":
    unittest.main()
