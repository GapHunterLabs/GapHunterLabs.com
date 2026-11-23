"""Tests for the isometric figures: the budget rules, the theme tokens they read, and the pages that inline them.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))
import iso_figures as F  # noqa: E402
import regenerate as R  # noqa: E402

FIGURES = sorted(p.stem for p in (PIPELINE / "iso" / "figures").glob("*.cjs"))
PAGES = {  # English page -> figures it inlines
    "index.html": ("grid", "hero", "catalog"),
    "catalog/index.html": ("catalog",),
    "sponsors/index.html": ("sponsors",),
    "engineering-evidence/index.html": ("evidence", "thumb-analysis", "thumb-tickets", "thumb-security", "thumb-audits"),
    "services/index.html": ("services",),
    "security/index.html": ("security",),
    "writing/index.html": ("writing",),
}
SPANISH = {"index.html": "es/index.html", "catalog/index.html": "es/catalogo/index.html",
           "sponsors/index.html": "es/patrocinadores/index.html",
           "engineering-evidence/index.html": "es/ingenieria-y-evidencia/index.html",
           "services/index.html": "es/servicios/index.html", "security/index.html": "es/seguridad/index.html",
           "writing/index.html": "es/escritos/index.html"}


def theme_blocks():
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "css" / "theme.css").read_text(encoding="utf-8"), flags=re.S)
    light = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    media = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}', css, re.S).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)^\}', css, re.S | re.M).group(1)
    decl = lambda block: dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", block))  # noqa: E731
    return {"light": decl(light), "media": decl(media), "dark": decl(dark)}


class FigureRulesTest(unittest.TestCase):
    def setUp(self):
        self.svg = F.load("thumb-audits")

    def test_every_figure_source_has_a_committed_svg_that_passes(self):
        out = sorted(p.stem for p in F.OUT.glob("*.svg"))
        self.assertEqual(out, FIGURES, "pipeline/iso/out must hold exactly one SVG per figure")
        for name in FIGURES:
            with self.subTest(figure=name):
                svg = (F.OUT / (name + ".svg")).read_text(encoding="utf-8").strip()
                self.assertEqual(F.problems(name, svg), [])
                self.assertLessEqual(len(svg.encode()), 40 * 1024)
                self.assertLessEqual(len(re.findall(r"<(?!/)[a-zA-Z]", svg)), 400)

    def test_budget_json_matches_the_svg_files(self):
        report = json.loads((F.OUT / "budget.json").read_text(encoding="utf-8"))["figures"]
        for name in FIGURES:
            svg = (F.OUT / (name + ".svg")).read_text(encoding="utf-8").strip()
            self.assertEqual(report[name]["bytes"], len(svg.encode()), name)
            self.assertEqual(report[name]["problems"], [], name)

    def broken(self, mutated, needle):
        found = F.problems("thumb-audits", mutated)
        self.assertTrue(any(needle in p for p in found), "%r not in %r" % (needle, found))

    def test_rejects_a_hard_coded_color_in_every_form(self):
        for color in ('fill="#fff"', 'stroke="#A1B2C3"', 'style="stop-color:rgb(1,2,3)"', 'fill="rgba(0,0,0,.5)"',
                      'fill="hsl(10, 50%, 50%)"', 'fill="red"', 'stroke="white"', 'style="stop-color:black"',
                      'fill="var(--signal)"', 'fill="url(javascript:x)"'):
            with self.subTest(color=color):
                self.broken(self.svg.replace('fill="var(--iso-ink)"', color, 1) if 'fill="var(--iso-ink)"' in self.svg
                            else self.svg.replace("<defs>", "<defs><rect %s/>" % color, 1), "hard-coded colors")

    def test_rejects_live_filters(self):
        for f in ('<filter id="iso-thumb-audits-x"><feGaussianBlur stdDeviation="3"/></filter>',
                  '<filter id="iso-thumb-audits-y"/>', '<g filter="url(#iso-thumb-audits-x)"/>'):
            with self.subTest(filter=f):
                self.broken(self.svg.replace("<defs>", "<defs>" + f, 1), "live filter")

    def test_rejects_ids_and_references_outside_the_figure(self):
        self.broken(self.svg.replace("<defs>", '<defs><linearGradient id="top"/>', 1), "prefix")
        self.broken(self.svg.replace("<defs>", '<defs><linearGradient id="iso-hero-top"/>', 1), "prefix")
        self.broken(self.svg.replace("</svg>", '<rect fill="url(#iso-hero-top)"/></svg>'), "references outside")

    def test_rejects_a_figure_screen_readers_would_announce(self):
        self.broken(self.svg.replace(' aria-hidden="true"', "", 1), "aria-hidden")
        self.broken(self.svg.replace(' aria-hidden="true"', ' aria-hidden="false"', 1), "aria-hidden")
        self.broken("<g>" + self.svg + "</g>", "does not start with <svg>")

    def test_rejects_more_than_one_turquoise_detail(self):
        one = self.svg.replace("</svg>", '<path stroke="var(--iso-accent-2)" d="M0 0L1 1"/></svg>')
        self.assertEqual(F.problems("thumb-audits", one), [])
        self.broken(one.replace("</svg>", '<path stroke="var(--iso-accent-2)" d="M0 0L1 1"/></svg>'), "turquoise")

    def test_rejects_script(self):
        self.broken(self.svg.replace("</svg>", "<script>alert(1)</script></svg>"), "script")
        self.broken(self.svg.replace("<defs>", '<defs><rect onload="x()"/>', 1), "script")

    def test_budget_limits_just_below_at_and_above(self):
        base = self.svg
        nodes = len(re.findall(r"<(?!/)[a-zA-Z]", base))
        at = base.replace("</svg>", "<g/>" * (400 - nodes) + "</svg>")
        self.assertEqual(F.problems("thumb-audits", at), [])
        self.broken(at.replace("</svg>", "<g/></svg>"), "nodes")
        pad = 40 * 1024 - len(base.encode()) - len("<desc></desc>")
        at_bytes = base.replace("</svg>", "<desc>%s</desc></svg>" % ("x" * pad))
        self.assertEqual(len(at_bytes.encode()), 40 * 1024)
        self.assertEqual([p for p in F.problems("thumb-audits", at_bytes) if "bytes" in p], [])
        self.broken(at_bytes.replace("<desc>", "<desc>x", 1), "bytes")

    def test_load_fails_fast_on_a_bad_name_or_a_missing_file(self):
        for bad in ("", None, "../hero", "Hero", "hero.svg", "hero/../grid", " hero"):
            with self.subTest(name=bad):
                with self.assertRaises(F.FigureError):
                    F.load(bad)
        with self.assertRaises(F.FigureError) as ctx:
            F.load("no-such-figure")
        self.assertIn("build_iso_figures.py", str(ctx.exception))

    def test_inject_needs_exactly_one_pair_of_markers_and_is_idempotent(self):
        mark = "<!-- PRERENDER:ISO:grid:START --><!-- PRERENDER:ISO:grid:END -->"
        for html in ("<p>none</p>", mark + mark, mark.replace("END", "FIN")):
            with self.subTest(html=html[:40]):
                with self.assertRaises(F.FigureError):
                    F.inject(html, "grid", "test")
        once = F.inject("<div>%s</div>" % mark, "grid", "test")
        self.assertIn(F.load("grid"), once)
        self.assertEqual(F.inject(once, "grid", "test"), once)


class ThemeTokensTest(unittest.TestCase):
    def test_every_token_the_figures_read_is_defined_in_all_three_blocks(self):
        used = set()
        for name in FIGURES:
            used |= set(re.findall(r"var\((--iso-[a-z0-9-]+)\)", (F.OUT / (name + ".svg")).read_text(encoding="utf-8")))
        self.assertTrue(used)
        for block, decl in theme_blocks().items():
            with self.subTest(block=block):
                self.assertEqual(sorted(used - set(decl)), [])

    def test_the_two_dark_blocks_are_identical(self):
        b = theme_blocks()
        diff = sorted(k for k in set(b["media"]) | set(b["dark"]) if b["media"].get(k) != b["dark"].get(k))
        self.assertEqual(diff, [], "prefers-color-scheme and data-theme=dark must declare the same values")

    def test_the_figure_accent_is_the_site_accent(self):
        for block, decl in theme_blocks().items():
            with self.subTest(block=block):
                self.assertEqual(decl["--iso-accent"].upper(), decl["--signal"].upper())

    def test_turquoise_stays_inside_the_figures(self):
        bad = []
        for f in list((ROOT / "css").glob("*.css")) + list((ROOT / "js").glob("*.js")):
            if f.name == "theme.css":
                continue
            if "--iso-accent-2" in f.read_text(encoding="utf-8"):
                bad.append(f.name)
        self.assertEqual(bad, [], "turquoise is for one stroke inside a figure, never for the interface")


class PagesTest(unittest.TestCase):
    def test_each_page_inlines_its_current_figures(self):
        for page, names in PAGES.items():
            for rel in (page, SPANISH[page]):
                html = (ROOT / rel).read_text(encoding="utf-8")
                for name in names:
                    with self.subTest(page=rel, figure=name):
                        m = re.search(r"<!-- PRERENDER:ISO:%s:START -->(.*?)<!-- PRERENDER:ISO:%s:END -->"
                                      % (re.escape(name), re.escape(name)), html, re.S)
                        self.assertIsNotNone(m, "markers missing")
                        self.assertEqual(m.group(1), F.load(name), "stale figure: run the page generator")

    def test_figure_ids_are_unique_on_each_page(self):
        for page in list(PAGES) + list(SPANISH.values()):
            ids = re.findall(r' id="(iso-[^"]+)"', (ROOT / page).read_text(encoding="utf-8"))
            with self.subTest(page=page):
                self.assertTrue(ids)
                self.assertEqual(len(ids), len(set(ids)))


class BuildTest(unittest.TestCase):
    def test_the_figure_build_is_excluded_from_regenerate_with_a_reason(self):
        self.assertIn("build_iso_figures.py", R.EXCLUDED)
        self.assertNotIn("build_iso_figures.py", [s for s, _, _ in R.STEPS])
        self.assertIn("Node", R.EXCLUDED["build_iso_figures.py"])

    def test_dependencies_are_pinned_to_exact_versions(self):
        dev = json.loads((PIPELINE / "package.json").read_text(encoding="utf-8"))["devDependencies"]
        self.assertEqual(dev.get("@elchininet/isometric"), "4.0.0")
        self.assertEqual(dev.get("jsdom"), "31.0.0")

    @unittest.skipUnless(shutil.which("node") and (PIPELINE / "node_modules" / "@elchininet" / "isometric").is_dir(),
                         "needs Node and npm ci in pipeline/")
    def test_the_committed_svg_files_are_what_the_figure_sources_draw(self):
        script = ("const p=require('path');const out={};for(const n of %s){out[n]=require(p.join(%s,'figures',n+'.cjs'))('iso-'+n)}"
                  "process.stdout.write(JSON.stringify(out))" % (json.dumps(FIGURES), json.dumps(str(PIPELINE / "iso"))))
        r = subprocess.run(["node", "-e", script], cwd=PIPELINE, capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        drawn = json.loads(r.stdout)
        for name in FIGURES:
            with self.subTest(figure=name):
                self.assertEqual(drawn[name], F.load(name), "run python pipeline/build_iso_figures.py")


if __name__ == "__main__":
    unittest.main()
