"""Tests for data/services.json (services_data.py) and the pages it drives (build_services.py).

    python -m unittest discover -s pipeline/tests -v
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_services as B  # noqa: E402
import services_data as S  # noqa: E402

GOOD = {
    "services": [
        {"key": "audit", "name": "Plugin performance audit", "shortName": "Performance audit",
         "path": "/audit-page/", "group": "jetbrains",
         "contactLabel": {"en": "Plugin performance audit", "es": "Auditoría"},
         "tiers": [{"id": "base", "usd": 10500, "days": 10}, {"id": "extended", "usd": 15000, "days": 15}]},
        {"key": "custom", "name": "Custom plugins", "shortName": "Custom", "path": "/custom-page/", "group": "any",
         "contactLabel": {"en": "Custom plugins", "es": "A medida"},
         "tiers": [{"id": "small", "usd": 7500, "days": 10}, {"id": "full", "usd": 15000, "days": None, "openEnded": True}],
         "addOns": [{"id": "cra", "usd": 1500, "days": 2}]},
    ]
}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for p in ("audit-page", "custom-page"):
            (self.root / p).mkdir()
            (self.root / p / "index.html").write_text("<html></html>", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def data(self, mutate=None):
        d = copy.deepcopy(GOOD)
        if mutate:
            mutate(d)
        return d

    def assertInvalid(self, mutate, expected):
        with self.assertRaises(S.ServicesError) as caught:
            S.validate(self.data(mutate), self.root)
        self.assertIn(expected, str(caught.exception))


class ValidateTest(Fixture):
    def test_good_file_passes(self):
        S.validate(self.data(), self.root)

    def test_top_level(self):
        for label, bad, expected in [("array", [], "must be an object"), ("no services", {}, "non-empty list"),
                                     ("empty", {"services": []}, "non-empty list"),
                                     ("typo", {"servics": [], "services": GOOD["services"]}, "unknown field")]:
            with self.subTest(label):
                with self.assertRaises(S.ServicesError) as caught:
                    S.validate(copy.deepcopy(bad), self.root)
                self.assertIn(expected, str(caught.exception))

    def test_service_fields(self):
        cases = [
            ("unknown field", lambda d: d["services"][0].update(teirs=[]), "unknown field(s) teirs"),
            ("key upper", lambda d: d["services"][0].update(key="Audit"), ".key must match"),
            ("key short", lambda d: d["services"][0].update(key="a"), ".key must match"),
            ("key reserved", lambda d: d["services"][0].update(key="other"), ".key must match"),
            ("key repeated", lambda d: d["services"][1].update(key="audit"), "is repeated"),
            ("name empty", lambda d: d["services"][0].update(name=""), ".name must be non-empty"),
            ("name spaces", lambda d: d["services"][0].update(name=" Audit"), "leading or trailing"),
            ("name markup", lambda d: d["services"][0].update(name="Audit <b>"), "must not contain"),
            ("name newline", lambda d: d["services"][0].update(name="Au\ndit"), "must not contain"),
            ("name type", lambda d: d["services"][0].update(name=5), ".name must be non-empty"),
            ("path relative", lambda d: d["services"][0].update(path="audit-page/"), ".path must look like"),
            ("path no slash", lambda d: d["services"][0].update(path="/audit-page"), ".path must look like"),
            ("path upper", lambda d: d["services"][0].update(path="/Audit/"), ".path must look like"),
            ("path missing page", lambda d: d["services"][0].update(path="/nowhere/"), "has no index.html"),
            ("path repeated", lambda d: d["services"][1].update(path="/audit-page/"), "is repeated"),
            ("group", lambda d: d["services"][0].update(group="all"), ".group must be one of"),
            ("label missing es", lambda d: d["services"][0].update(contactLabel={"en": "x"}), "exactly \"en\" and \"es\""),
            ("label extra", lambda d: d["services"][0]["contactLabel"].update(fr="x"), "exactly \"en\" and \"es\""),
            ("label apostrophe", lambda d: d["services"][0]["contactLabel"].update(es="Auditoría d'un"), "apostrophe"),
            ("label backslash", lambda d: d["services"][0]["contactLabel"].update(en="a\\b"), "must not contain"),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label):
                self.assertInvalid(mutate, expected)

    def test_levels(self):
        t0 = lambda **kw: (lambda d: d["services"][0]["tiers"][0].update(**kw))
        cases = [
            ("tiers empty", lambda d: d["services"][0].update(tiers=[]), "non-empty list"),
            ("tiers not list", lambda d: d["services"][0].update(tiers={}), "non-empty list"),
            ("tier not object", lambda d: d["services"][0]["tiers"].append(5), "must be an object"),
            ("tier unknown", t0(price=1), "unknown field(s) price"),
            ("id bad", t0(id="Base"), ".id must match"),
            ("id repeated", lambda d: d["services"][0]["tiers"][1].update(id="base"), "must be unique"),
            ("id repeated with add-on", lambda d: d["services"][1]["addOns"][0].update(id="small"), "must be unique"),
            ("usd zero", t0(usd=0), ".usd must be a whole number"),
            ("usd negative", t0(usd=-1), ".usd must be a whole number"),
            ("usd fraction", t0(usd=10.5), ".usd must be a whole number"),
            ("usd float whole", t0(usd=10500.0), ".usd must be a whole number"),
            ("usd string", t0(usd="10500"), ".usd must be a whole number"),
            ("usd bool", t0(usd=True), ".usd must be a whole number"),
            ("usd null", t0(usd=None), ".usd must be a whole number"),
            ("days zero", t0(days=0), ".days must be a whole number"),
            ("days null", t0(days=None), "days is required"),
            ("days string", t0(days="10"), ".days must be a whole number"),
            ("open-ended with days", lambda d: d["services"][1]["tiers"][1].update(days=20), "days must be null"),
            ("openEnded not bool", lambda d: d["services"][1]["tiers"][1].update(openEnded="yes"), "true or false"),
            ("add-on days null", lambda d: d["services"][1]["addOns"][0].update(days=None), "days is required"),
            ("add-on open-ended", lambda d: d["services"][1]["addOns"][0].update(openEnded=True), "unknown field(s) openEnded"),
            ("add-ons not list", lambda d: d["services"][1].update(addOns={}), "must be a list"),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label):
                self.assertInvalid(mutate, expected)

    def test_boundaries_that_pass(self):
        def edge(d):
            d["services"][0]["tiers"][0].update(usd=1, days=1)
            d["services"][0]["key"] = "ab"
            d["services"][1].pop("addOns")
        S.validate(self.data(edge), self.root)

    def test_load_reads_a_bom_and_names_bad_json(self):
        path = self.root / "services.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps(GOOD).encode("utf-8"))
        self.assertEqual(S.load(path, self.root)["services"][0]["key"], "audit")
        for content in (b"", b"{", b"\xff\xfe"):
            with self.subTest(content=content):
                path.write_bytes(content)
                with self.assertRaises(S.ServicesError) as caught:
                    S.load(path, self.root)
                self.assertIn("not valid JSON", str(caught.exception))
        with self.assertRaises(S.ServicesError):
            S.load(self.root / "missing.json", self.root)


class ValueTest(Fixture):
    def test_values_and_formats(self):
        d = S.validate(self.data(), self.root)
        self.assertEqual(S.value(d, "audit.base.usd"), 10500)
        self.assertEqual(S.value(d, "custom.cra.days"), 2)
        for ref, expected in [("audit.base", "must be"), ("audit.base.price", "must be"), ("nope.base.usd", "no service"),
                              ("audit.nope.usd", "no level"), ("custom.full.days", "has no value")]:
            with self.subTest(ref=ref):
                with self.assertRaises(S.ServicesError) as caught:
                    S.value(d, ref)
                self.assertIn(expected, str(caught.exception))
        for n, en, es in [(1, "1", "1"), (999, "999", "999"), (1000, "1,000", "1.000"), (10500, "10,500", "10.500"),
                          (1000000, "1,000,000", "1.000.000")]:
            self.assertEqual((S.usd(n), S.usd(n, "es")), (en, es))
        audit, custom = d["services"]
        self.assertEqual((S.min_usd(audit), S.max_usd(audit)), (10500, 15000))
        self.assertEqual((S.min_usd(custom), S.max_usd(custom)), (7500, None))
        no_open = self.data(lambda x: x["services"][1]["tiers"].pop())
        self.assertEqual(S.max_usd(S.validate(no_open, self.root)["services"][1]), 7500 + 1500)


class PageRulesTest(Fixture):
    def setUp(self):
        super().setUp()
        self.d = S.validate(self.data(), self.root)

    def test_bind_rewrites_the_figure_and_keeps_the_text(self):
        text = "<p>USD <!--svc:audit.base.usd-->9,999, fixed, in <!--svc:audit.base.days-->3 business days</p>"
        out, used = B.bind(text, self.d, "p.html")
        self.assertEqual(out, "<p>USD <!--svc:audit.base.usd-->10,500, fixed, in <!--svc:audit.base.days-->10 business days</p>")
        self.assertEqual(used, {"audit.base.usd", "audit.base.days"})
        self.assertEqual(B.bind(out, self.d, "p.html")[0], out)          # idempotent

    def test_bind_errors_name_file_and_line(self):
        for text, expected in [("a\n<!--svc:audit.nope.usd-->1", "p.html:2: service 'audit' has no level 'nope'"),
                               ("<!--svc:audit.base.usd--> USD", "is not followed by a figure"),
                               ("<!--svc:custom.full.days-->1", "has no value"),
                               ("<!--svc:audit.base-->1", "must be <key>.<level>.<usd|days>")]:
            with self.subTest(text=text):
                with self.assertRaises(B.BuildError) as caught:
                    B.bind(text, self.d, "p.html")
                self.assertIn(expected, str(caught.exception))

    def test_unbound_prices_are_reported_outside_head_and_scripts(self):
        text = ('<html><head><meta content="USD 1"></head><body>\n<p>USD <!--svc:a.b.usd-->5</p>\n<p>USD 7,500</p>'
                '<script>var p = "USD 9";</script></body></html>')
        self.assertEqual(B.unbound(text, "x.html"), ['x.html:3: "USD n" without a <!--svc:...--> binding'])
        self.assertEqual(B.unbound("<body>USD&nbsp;5 and 5 USD</body>", "x"), [])   # only the site's own form "USD 5"

    def test_head_prices(self):
        head = ('<head><meta property="og:image:alt" content="Audit, USD 1 fixed">'
                '<meta name="twitter:image:alt" content="Audit, from USD 2"></head><body></body>')
        out = B.head_prices(head, "a.html", self.d["services"][0])
        self.assertIn('content="Audit, USD 10,500 fixed"', out)
        self.assertIn('content="Audit, from USD 10,500"', out)
        bad = [(head.replace('name="twitter:image:alt"', 'name="twitter:image:x"'), "found 1"),
               (head.replace("USD 2", "no price"), "exactly one price, found 0"),
               (head.replace("USD 2", "USD 2 or USD 3"), "exactly one price, found 2"),
               (head.replace("</head>", '<meta name="description" content="USD 5"></head>'), "outside the image alt")]
        for text, expected in bad:
            with self.subTest(expected=expected):
                with self.assertRaises(B.BuildError) as caught:
                    B.head_prices(text, "a.html", self.d["services"][0])
                self.assertIn(expected, str(caught.exception))
        with self.assertRaises(B.BuildError):
            B.head_prices('<head><meta content="USD 5"></head>', "home.html", None)
        self.assertEqual(B.head_prices("<head></head>", "home.html", None), "<head></head>")

    def test_offer_catalog(self):
        text = '{\n  "x": 1,\n  "hasOfferCatalog": {"name": "Developer tooling services", "itemListElement": []}\n}'
        out = json.loads(B.offer_catalog(text, self.d, "i.html"))
        offers = out["hasOfferCatalog"]["itemListElement"]
        self.assertEqual(out["hasOfferCatalog"]["name"], "Developer tooling services")
        self.assertEqual([o["priceSpecification"].get("maxPrice") for o in offers], ["15000", None])
        self.assertEqual(offers[1]["priceSpecification"]["minPrice"], "7500")
        self.assertTrue(offers[0]["url"].endswith("/audit-page/"))
        for bad in ("{}", text.replace("}\n}", '}, "hasOfferCatalog": {}\n}'), '{"hasOfferCatalog": {}}'):
            with self.subTest(bad=bad[:30]):
                with self.assertRaises(B.BuildError):
                    B.offer_catalog(bad, self.d, "i.html")

    def test_contact_services(self):
        text = "a\n  // SERVICES:START x\n  var SERVICES = [];\n  // SERVICES:END\nb"
        out = B.contact_services(text, self.d, "c.js")
        self.assertIn("    ['audit', t('Plugin performance audit', 'Auditoría')],\n", out)
        self.assertIn("    ['other', t('Something else', 'Otra cosa')]\n  ];\n  // SERVICES:END\nb", out)
        self.assertEqual(B.contact_services(out, self.d, "c.js"), out)
        self.assertEqual(B.js_str("it's a\\b"), "'it\\'s a\\\\b'")
        for bad in ("no markers", text + text):
            with self.assertRaises(B.BuildError):
                B.contact_services(bad, self.d, "c.js")

    def test_coverage_names_each_missing_figure(self):
        refs = {"audit.base.usd", "audit.base.days", "audit.extended.usd", "audit.extended.days",
                "custom.small.usd", "custom.small.days", "custom.full.usd", "custom.cra.usd", "custom.cra.days"}
        full = {"/audit-page/": refs, "/custom-page/": refs, B.HUB: refs, B.HOME: refs}
        self.assertEqual(B.coverage(self.d, full), [])
        partial = dict(full, **{B.HUB: refs - {"custom.cra.days"}})
        self.assertEqual(B.coverage(self.d, partial), ["/services/: no page binding shows custom.cra.days (2)"])


class RepositoryTest(unittest.TestCase):
    """The real site: every page agrees with data/services.json, and so do the social images."""

    def test_pages_are_up_to_date(self):
        self.assertEqual(sorted(B.build()), [], "run python pipeline/build_services.py")

    def test_social_images_show_the_current_prices(self):
        self.assertEqual(B.og_stamp_problems(), [])

    def test_a_stale_missing_or_broken_stamp_is_reported(self):
        real = json.loads((S.ROOT / "data" / "og-prices.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIn("is missing", B.og_stamp_problems(root)[0])
            (root / "data").mkdir()
            stamp = root / "data" / "og-prices.json"
            stamp.write_text(json.dumps(real), encoding="utf-8")
            self.assertEqual(B.og_stamp_problems(root), [])
            stale = dict(real, texts=[t.replace("10,500", "9,000") for t in real["texts"]])
            stamp.write_text(json.dumps(stale), encoding="utf-8")
            self.assertIn("show old prices", B.og_stamp_problems(root)[0])
            stamp.write_text(json.dumps(dict(real, texts=real["texts"][1:])), encoding="utf-8")
            self.assertIn("show old prices", B.og_stamp_problems(root)[0])
            stamp.write_text("{", encoding="utf-8")
            self.assertIn("not valid JSON", B.og_stamp_problems(root)[0])

    def test_a_price_change_reaches_every_page(self):
        data = json.loads(S.SERVICES_FILE.read_text(encoding="utf-8"))
        data["services"][0]["tiers"][0]["usd"] += 1
        changes = B.build(data=data)
        self.assertGreaterEqual(set(changes), {"index.html", "services/index.html",
                                               data["services"][0]["path"].strip("/") + "/index.html"})
        self.assertTrue(any("10,501" in t for t in changes.values()))


if __name__ == "__main__":
    unittest.main()
