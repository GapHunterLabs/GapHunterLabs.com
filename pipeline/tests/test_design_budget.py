"""Tests for pipeline/design_budget.py: the closed scales of the design system and the logo colors.

    python -m unittest discover -s pipeline/tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import design_budget as D  # noqa: E402


def css(text, name="x.css", theme=False):
    return [(name, text, theme)]


class SiteBudgetTest(unittest.TestCase):
    def test_the_site_is_exactly_at_its_caps(self):
        # Above a cap: a new value slipped in. Below: lower the cap, so it never goes back up.
        self.assertEqual(D.problems(D.counts()), [])

    def test_caps_are_not_below_the_goals(self):
        for kind, goal in D.GOALS.items():
            self.assertGreaterEqual(D.CAPS[kind], goal, kind)
        self.assertEqual(set(D.CAPS), set(D.GOALS))

    def test_logo_colors_only_in_the_logo(self):
        self.assertEqual(D.logo_color_uses(), [])

    def test_the_pages_are_measured_too(self):
        names = [name for name, _, _ in D.sources()]
        self.assertIn("theme.css", names)
        self.assertNotIn("tw.css", names)
        self.assertTrue(any(n.startswith("index.html") for n in names), "inline CSS of the home page")
        self.assertFalse(any(n.startswith("es/") for n in names), "the Spanish pages are copies")
        self.assertEqual(sum(n.startswith("catalog/") and n.count("/") >= 2 for n in names) <= 2, True,
                         "one catalog page stands for the 146 that share its template")


class ProblemsTest(unittest.TestCase):
    def test_above_below_and_equal(self):
        caps = {"a": 3, "b": 3, "c": 3}
        out = D.problems({"a": 4, "b": 2, "c": 3}, caps)
        self.assertEqual(len(out), 2)
        self.assertIn("a: 4 distinct values, the cap is 3", out[0])
        self.assertIn("lower CAPS['b'] from 3 to 2", out[1])

    def test_a_missing_or_extra_kind_is_reported(self):
        self.assertTrue(D.problems({"a": 1}, {"a": 1, "b": 1}))
        self.assertTrue(D.problems({"a": 1, "z": 0}, {"a": 1}))

    def test_one_new_font_size_breaks_the_site_budget(self):
        # mutation of the real sources: one page adds a 7px label
        items = list(D.sources()) + css("label { font-size: 7px; }", "new-page.html <style> 0")
        self.assertEqual(D.problems(D.counts(items)), [
            f"font_sizes: {D.CAPS['font_sizes'] + 1} distinct values, the cap is {D.CAPS['font_sizes']}; use an existing "
            "value (python pipeline/design_budget.py --json lists them)"])


class MeasureTest(unittest.TestCase):
    def values(self, text, kind, theme=False):
        found, _ = D.measure(css(text, theme=theme))
        return sorted(found[kind])

    def test_font_sizes_in_every_spelling(self):
        self.assertEqual(self.values("a{font-size:14px}b{font:600 11px/1.4 var(--mono)}c{font:italic 700 13px x}",
                                     "font_sizes"), ["11px", "13px", "14px"])
        self.assertEqual(self.values("a{font: 700 clamp(22px, 2.4vw, 28px) / 1.2 var(--sans)}", "font_sizes"),
                         ["clamp(22px, 2.4vw, 28px)"])
        self.assertEqual(self.values("a{font-size:.9em}b{font-size:0.9em}c{font-size:14px !important}", "font_sizes"),
                         ["0.9em", "14px"])
        self.assertEqual(self.values("a{font-size:var(--fs-ui)}b{font:inherit}", "font_sizes"), ["var(--fs-ui)"])

    def test_comments_do_not_count(self):
        self.assertEqual(self.values("/* font-size: 99px */ a{font-size:1px}", "font_sizes"), ["1px"])

    def test_spacing_counts_each_length_and_skips_zero(self):
        self.assertEqual(self.values("a{padding:0 10px 2em}b{margin:-4px auto}c{gap:4px}d{padding-inline-start:6px}",
                                     "spacing"), ["10px", "2em", "4px", "6px"])
        self.assertEqual(self.values("a{margin:0}b{inset:12px}c{top:8px}", "spacing"), [])

    def test_breakpoints_in_px_and_em(self):
        self.assertEqual(self.values("@media (max-width: 640px){}@media(min-width:641px){}@media (max-width: 40em){}",
                                     "breakpoints"), ["max 40em", "max 640px", "min 641px"])

    def test_radii_skip_tokens_and_zero(self):
        self.assertEqual(self.values("a{border-radius:var(--radius)}b{border-radius:0}c{border-radius:50%}"
                                     "d{border-top-left-radius:3px}", "fixed_radii"), ["3px", "50%"])

    def test_shadows_and_layers(self):
        self.assertEqual(self.values("a{box-shadow:none}b{box-shadow:0  1px  2px #000}", "shadows"),
                         ["0 1px 2px #000", "none"])
        self.assertEqual(self.values("a{z-index:-1}b{z-index:50}c{z-index:50}", "z_index"), ["-1", "50"])

    def test_colors_outside_the_theme_only(self):
        self.assertEqual(self.values("a{color:#fff}b{color:#FFFFFF}c{color:rgba(0, 0, 0, .5)}d{color:rgba(0,0,0,0.5)}",
                                     "fixed_colors"), ["#FFFFFF", "rgba(0,0,0,0.5)"])
        self.assertEqual(self.values("a{color:#123456}", "fixed_colors", theme=True), [])

    def test_html_style_blocks_and_attributes(self):
        html = '<style>a{font-size:15px}</style><p style="margin: 3px; color:#abc">x</p>'
        page = D.STYLE_BLOCK.findall(html)[0] + ";" + ";".join(m.group(2) for m in D.STYLE_ATTR.finditer(html))
        found, _ = D.measure(css(page, "p.html"))
        self.assertEqual((sorted(found["font_sizes"]), sorted(found["spacing"]), sorted(found["fixed_colors"])),
                         (["15px"], ["3px"], ["#AABBCC"]))


class LogoColorTest(unittest.TestCase):
    def test_fill_of_an_svg_is_allowed(self):
        self.assertEqual(D.logo_color_uses([("a.html", '<path fill="#0151FC"/><path fill="#01b3fd"/>'),
                                            ("favicon.svg", '<polygon fill="#02F172"/>')]), [])

    def test_any_other_use_is_reported(self):
        self.assertEqual(D.logo_color_uses([
            ("a.css", "x{background:#0151FC}"),
            ("b.html", '<p style="color:#0151FC">'),
            ("c.js", "bar.style.background = '#02f172';"),
            ("d.css", "x{fill:#01B3FD}"),
            ("e.html", '<rect fill="#0151FC80"/>'),
        ]), ["a.css:1", "b.html:1", "c.js:1", "d.css:1", "e.html:1"])

    def test_a_comment_is_not_a_use_and_lines_are_kept(self):
        self.assertEqual(D.logo_color_uses([("a.css", "/* the logo is #0151FC\n */\nx{color:#0151FC}")]), ["a.css:3"])


if __name__ == "__main__":
    unittest.main()
