"""Tests for the evidence hub generator (build_evidence.py) and the data-driven home hero (build_home.py).

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
import build_evidence as E  # noqa: E402
import build_home as H  # noqa: E402

CASES = json.loads((ROOT / "data" / "blog-cases.json").read_text(encoding="utf-8"))["cases"]
SERVICES = json.loads((ROOT / "data" / "services.json").read_text(encoding="utf-8"))["services"]
HUB = (ROOT / "engineering-evidence" / "index.html").read_text(encoding="utf-8")


def case(**over):
    c = {"id": "x-1", "cat": "performance", "status": "fixed", "title": "A title", "problem": "A problem.",
         "work": "Work.", "result": "Result.", "events": [{"t": "filed", "d": "2026-10-01"}, {"t": "fixed", "d": "2026-10-09"}],
         "refs": [["IJPL-1", "https://youtrack.jetbrains.com/issue/IJPL-1"]]}
    c.update(over)
    return c


def block(html, name):
    return re.search(r"<!-- PRERENDER:%s:START -->(.*?)<!-- PRERENDER:%s:END -->" % (name, name), html, re.S).group(1)


class CompleteCaseTest(unittest.TestCase):
    def test_a_full_case_is_shown(self):
        self.assertTrue(E.complete(case()))

    def test_a_case_without_real_data_is_left_out(self):
        bad = [case(title=""), case(title=None), case(problem=""), case(refs=[]), case(events=[]),
               case(status="done"), case(cat="other"), case(events=[{"t": "filed", "d": "2026-13"}]),
               case(events=[{"t": "launched", "d": "2026-10-01"}]), case(events=["2026-10-01"]),
               case(refs=[["Report", "http://example.com/plain-http"]]), case(refs=[["Report", "javascript:alert(1)"]]),
               case(refs=[["only label"]])]
        for c in bad:
            with self.subTest(case={k: c.get(k) for k in ("title", "status", "cat", "events", "refs")}):
                self.assertFalse(E.complete(c))
        missing_id = case()
        del missing_id["id"]
        self.assertFalse(E.complete(missing_id))

    def test_group_drops_incomplete_cases_and_sorts_newest_first(self):
        cases = [case(id="a", events=[{"t": "filed", "d": "2026-09-01"}]), case(id="b"), case(id="c", title="")]
        by_area = E.group(cases)
        self.assertEqual([c["id"] for c in by_area["tickets"]], ["b", "a"])
        self.assertEqual(sum(len(v) for v in by_area.values()), 2)

    def test_an_area_without_cases_has_no_card_and_no_section(self):
        by_area = E.group([case()])
        featured, sections = E.featured_html(by_area), E.sections_html(by_area)
        self.assertEqual(featured.count('class="ee-case"'), 1)
        self.assertNotIn("thumb-security", featured)
        self.assertNotIn('id="ee-security"', sections)
        self.assertEqual(E.featured_html(E.group([])), "")


class AreaAndIdentifierTest(unittest.TestCase):
    def test_area_of_every_kind(self):
        self.assertEqual(E.area_of(case(cat="security", refs=[["r", "https://github.com/o/r/issues/5"]])), "security")
        self.assertEqual(E.area_of(case(cat="custom")), "analysis")
        self.assertEqual(E.area_of(case(cat="platform")), "tickets")
        self.assertEqual(E.area_of(case(refs=[["i", "https://github.com/redhat-developer/lsp4ij/issues/1540"]])), "audits")

    def test_identifiers(self):
        self.assertEqual(E.ident("https://youtrack.jetbrains.com/issue/IJPL-257909"), "IJPL-257909")
        self.assertEqual(E.ident("https://youtrack.jetbrains.com/issue/IDEA-1#focus=Comments-1"), "IDEA-1")
        self.assertEqual(E.ident("https://github.com/bancolombia/data-mask/issues/86"), "data-mask#86")
        self.assertEqual(E.ident("https://github.com/JetBrains/intellij-community/pull/3701"), "intellij-community#3701")
        self.assertEqual(E.ident("https://github.com/JetBrains/intellij-community/commit/4a88fdfa"), "intellij-community")
        self.assertEqual(E.ident("https://nvd.nist.gov/vuln/detail/CVE-2022-22963"), "nvd.nist.gov")

    def test_markup_in_a_source_url_is_escaped(self):
        html = E.featured_html(E.group([case(refs=[["r", 'https://youtrack.jetbrains.com/issue/X-1"><script>x()</script>']])]))
        self.assertNotIn("<script>", html)
        self.assertEqual(html.count("&lt;script&gt;"), 2)   # the identifier chip and the link, both escaped
        rows = E.sections_html(E.group([case(refs=[["r", 'https://youtrack.jetbrains.com/issue/X-1"><script>x()</script>']])]))
        self.assertNotIn("<script>", rows)


class HubPageTest(unittest.TestCase):
    def test_every_complete_case_is_listed_once_and_links_its_first_source(self):
        shown = [c for c in CASES if E.complete(c)]
        rows = re.findall(r'<li class="ee-row" data-date="([^"]+)">.*?<a href="([^"]+)"', block(HUB, "EESECTIONS"), re.S)
        self.assertEqual(len(rows), len(shown))
        self.assertEqual(sorted(href for _, href in rows), sorted(E.source(c) for c in shown))
        for _, href in rows:
            self.assertTrue(href.startswith("https://"), href)

    def test_one_featured_card_per_area_and_it_is_the_newest(self):
        by_area = E.group(CASES)
        cards = re.findall(r'<article class="ee-case" aria-labelledby="ee-f-([^"]+)"', block(HUB, "EEFEATURED"))
        self.assertEqual(cards, [by_area[k][0]["id"] for k, *_ in E.AREAS if by_area[k]])

    def test_the_counts_come_from_the_area_pages(self):
        n = E.counts()
        shown = re.findall(r"<b>(\d+)</b>", block(HUB, "EECOUNTS"))
        self.assertEqual([int(x) for x in shown], [v for k, v in n.items() if v > 0])
        research = json.loads((ROOT / "data" / "research.json").read_text(encoding="utf-8"))
        self.assertEqual(n["prs"], research["upstreamPullRequests"]["total"],
                         "the tickets page and research.json disagree on the pull requests")

    def test_blue_marks_only_identifiers(self):
        chips = re.findall(r'<li class="ee-chip ee-chip-tech">(.*?)</li>', HUB, re.S)
        self.assertTrue(chips)
        for c in chips:
            self.assertRegex(c, r'^<span class="ticket-id">[^<]+</span>$')

    def test_the_sort_control_is_hidden_without_javascript(self):
        self.assertRegex(HUB, r'<div class="ee-sort" data-ee-sort hidden>')
        self.assertIn('<script src="/js/evidence.js', HUB)


class HomeHeroTest(unittest.TestCase):
    def test_tiles_follow_services_json_with_their_bound_figures(self):
        html = H.service_tiles_html(SERVICES)
        self.assertEqual(re.findall(r'class="nb-svc-tile" href="([^"]+)"', html), [s["path"] for s in SERVICES])
        for s in SERVICES:
            low = min((t for t in s["tiers"] if isinstance(t.get("usd"), int)), key=lambda t: t["usd"])
            self.assertIn("<!--svc:%s.%s.usd-->%s" % (s["key"], low["id"], format(low["usd"], ",")), html)

    def test_tiles_fail_fast_on_bad_service_data(self):
        broken = [SERVICES[:3], SERVICES + SERVICES[:1]]
        for field, value in (("key", "unknown"), ("shortName", ""), ("path", "https://evil.example/"), ("tiers", []),
                             ("tiers", [{"id": "x", "usd": 0}]), ("tiers", [{"id": "x", "usd": "4500"}])):
            s = copy.deepcopy(SERVICES)
            s[0][field] = value
            broken.append(s)
        for data in broken:
            with self.subTest(n=len(data), first=data[0].get("key")):
                with self.assertRaises(SystemExit):
                    H.service_tiles_html(data)


if __name__ == "__main__":
    unittest.main()
