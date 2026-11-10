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


if __name__ == "__main__":
    unittest.main()
