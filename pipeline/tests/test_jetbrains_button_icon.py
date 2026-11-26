"""Buttons that open JetBrains Marketplace (or a JetBrains plugin page) carry the JetBrains mark, not a generic icon.

    python -m unittest discover -s pipeline/tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_plugin_pages import ROOT, js_literal  # noqa: E402

BRAND_D = json.loads((ROOT / "pipeline" / "icons.json").read_text(encoding="utf-8"))["icons"]["jetbrains"]["d"]
ICONS = js_literal((ROOT / "js" / "catalog-shared.js").read_text(encoding="utf-8"), "ICONS", "js/catalog-shared.js")
ACTIONS = re.compile(r'<div class="ph-actions">(.*?)</div>', re.S)
LINK = re.compile(r"<a\b[^>]*>.*?</a>", re.S)


def jetbrains_buttons(html: str):
    """Every action button that points to JetBrains Marketplace or says it is for JetBrains IDEs."""
    out = []
    for block in ACTIONS.findall(html):
        for a in LINK.findall(block):
            if "plugins.jetbrains.com" in a or "JetBrains IDEs" in a or "IDE de JetBrains" in a:
                out.append(a)
    return out


def pages():
    for pattern in ("catalog/*/index.html", "catalog/vscode/*/index.html",
                    "es/catalogo/*/index.html", "es/catalogo/vscode/*/index.html"):
        yield from sorted(ROOT.glob(pattern))


class JetBrainsButtonIconTest(unittest.TestCase):
    def test_icon_is_the_unmodified_brand_mark(self):
        svg = ICONS["jetbrains"]
        self.assertIn('<path d="%s"/>' % BRAND_D, svg)
        self.assertIn('viewBox="0 0 24 24"', svg)
        self.assertIn('fill="currentColor"', svg, "the mark must follow the button text color in both themes")
        self.assertIn('aria-hidden="true"', svg, "the button text already names JetBrains")
        self.assertNotIn("stroke", svg, "an outline icon means the generic puzzle came back")
        self.assertEqual(svg.count("<path"), 1)

    def test_every_jetbrains_button_on_generated_pages_uses_it(self):
        seen = {"trial": 0, "install": 0, "also": 0}
        for page in pages():
            html = page.read_text(encoding="utf-8")
            for a in jetbrains_buttons(html):
                with self.subTest(page=str(page.relative_to(ROOT))):
                    self.assertIn(BRAND_D, a)
                    self.assertNotIn("M7.5 3.5h3v1.75", a)
                kind = "trial" if "out-trial-" in a else "install" if "out-install-" in a else "also"
                seen[kind] += 1
        # Each variant must exist, so the scan cannot pass by matching nothing.
        for kind, n in seen.items():
            with self.subTest(kind=kind):
                self.assertGreater(n, 0, "no %s button found: the page markup changed, update this test" % kind)

    def test_the_scan_catches_a_button_without_the_mark(self):
        bad = ('<div class="ph-actions"><a class="btn primary" href="https://plugins.jetbrains.com/plugin/1-x" '
               'data-goatcounter-click="out-trial-x"><span class="btn-icon"><svg/></span>Start free trial on JetBrains</a></div>')
        found = jetbrains_buttons(bad)
        self.assertEqual(len(found), 1)
        self.assertNotIn(BRAND_D, found[0])
        self.assertEqual(jetbrains_buttons('<div class="ph-actions"><a class="btn" href="https://github.com/x">GitHub</a></div>'), [])
        self.assertEqual(jetbrains_buttons(""), [])


if __name__ == "__main__":
    unittest.main()
