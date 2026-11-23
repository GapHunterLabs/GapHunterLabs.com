"""Light theme surfaces (2026-11-23): a hierarchy of grays instead of one universal white, ambient shadows only in
light mode, and every text color readable on every light surface.

    python -m unittest discover -s pipeline/tests -v
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "css" / "theme.css").read_text(encoding="utf-8")


def block(selector_re):
    m = re.search(selector_re + r"\s*\{(.*?)\n\s*\}", CSS, flags=re.S)
    assert m, selector_re
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)))


LIGHT = block(r"(?m)^:root")
DARK_MEDIA = block(r':root:not\(\[data-theme="light"\]\)')
DARK_ATTR = block(r':root\[data-theme="dark"\]')


def lum(h):
    h = h.strip().lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


SURFACES = ("--bg", "--section", "--surface", "--surface-2", "--surface-3", "--panel-1", "--panel-2", "--band-a", "--band-b")
TEXTS = ("--text", "--text-dim", "--text-faint", "--signal", "--valid", "--inspect", "--cyan", "--bad", "--pending")


class LightThemeTest(unittest.TestCase):
    def test_the_page_is_not_one_universal_white(self):
        self.assertNotIn(LIGHT["--bg"].upper(), ("#FFFFFF", "#FFF", "#FAFAFA"))
        steps = [LIGHT[k].upper() for k in ("--section", "--bg", "--surface", "--panel-1")]
        self.assertEqual(len(set(steps)), 4, steps)
        # cards are lighter than containers, containers lighter than the page, the page lighter than a section
        self.assertEqual(sorted(steps, key=lum), steps)

    def test_every_text_color_reads_on_every_light_surface(self):
        for t in TEXTS:
            for s in SURFACES:
                with self.subTest(text=t, surface=s):
                    self.assertGreaterEqual(ratio(LIGHT[t], LIGHT[s]), 4.5)

    def test_strong_borders_reach_3_to_1(self):
        for s in SURFACES:
            with self.subTest(surface=s):
                self.assertGreaterEqual(ratio(LIGHT["--border-strong"], LIGHT[s]), 3.0)

    def test_ambient_shadows_exist_in_light_mode_only(self):
        self.assertNotEqual(LIGHT["--shadow"].strip(), "none")
        for name, dark in (("media", DARK_MEDIA), ("data-theme", DARK_ATTR)):
            with self.subTest(block=name):
                self.assertEqual(dark.get("--shadow", "").strip(), "none")
                self.assertEqual(dark.get("--shadow-lg", "").strip(), "none")
                self.assertIn("--section", dark)

    def test_the_figures_accent_is_the_site_accent(self):
        self.assertEqual(LIGHT["--iso-accent"].upper(), LIGHT["--signal"].upper())


if __name__ == "__main__":
    unittest.main()
