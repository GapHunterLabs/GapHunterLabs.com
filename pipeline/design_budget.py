"""Count how many distinct values the hand-written CSS of the site uses for each design property.

    python pipeline/design_budget.py          # the counts, the caps and the goals
    python pipeline/design_budget.py --json   # every value with its count and the first place it appears

The design system (2026-11-09) closes each scale: 10 font sizes, 13 spacing steps, 6 breakpoints, the radius tokens,
3 shadows, 6 layers and the colors of theme.css. pipeline/tests/test_design_budget.py compares the counts with CAPS:
a count above its cap fails (a new page cannot add an eleventh font size unnoticed), and a count below its cap fails
too, asking to lower the cap, so the caps follow every improvement and never go back up. Each step of the migration
lowers them towards GOALS.

Measured:
- every css/*.css except tw.css (compiled by the Tailwind CLI, checked by _review/verify_tailwind.py); plugin.css is
  generated from catalog.css by build_plugin_pages.py and counted like the rest;
- the <style> blocks and style="" attributes of the English pages tracked in git (the Spanish pages are copies made
  by build_i18n.py; the catalog pages share one template and are measured through the first one).
Not measured: the Tailwind classes, and CSS that JavaScript writes at run time.

Since 2026-11-09 the three logo colors appear only as fill="" of the logo SVG (pages, favicon.svg) and in the social
images; logo_color_uses() lists any other use.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "css"
COMPILED = {"tw.css"}

# Counts on 2026-11-09 after the first step of the migration. Lower them; never raise them.
CAPS = {
    "font_sizes": 49,
    "spacing": 43,
    "breakpoints": 21,
    "fixed_radii": 12,
    "shadows": 15,
    "z_index": 10,
    "fixed_colors": 24,
}
# Where the migration ends.
GOALS = {"font_sizes": 10, "spacing": 13, "breakpoints": 6, "fixed_radii": 0, "shadows": 3, "z_index": 6,
         "fixed_colors": 2}

LOGO_COLORS = ("#0151FC", "#01B3FD", "#02F172")

COMMENT = re.compile(r"/\*.*?\*/", re.S)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*("([^"]*)"|'([^']*)')""", re.I)
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)")
FONT_SIZE = re.compile(r"(?<![\w-])font-size\s*:\s*([^;}{]+)")
FONT_SHORT = re.compile(r"(?<![\w-])font\s*:\s*(?:[a-z-]+\s+)*(?:\d{3}\s+)?(clamp\([^)]*\)|var\([^)]*\)|[\d.]+(?:px|rem|em|%))")
SPACING = re.compile(r"(?<![\w-])(?:padding|margin|gap|row-gap|column-gap)(?:-(?:top|right|bottom|left|inline|block)"
                     r"(?:-(?:start|end))?)?\s*:\s*([^;}{]+)")
LENGTH = re.compile(r"(?<![\w.])-?(\d+(?:\.\d+)?)(px|rem|em)\b")
BREAKPOINT = re.compile(r"\((max|min)-width\s*:\s*(\d+(?:\.\d+)?)(px|em|rem)\s*\)")
RADIUS = re.compile(r"(?<![\w-])border(?:-(?:top|bottom)-(?:left|right))?-radius\s*:\s*([^;}{]+)")
SHADOW = re.compile(r"(?<![\w-])box-shadow\s*:\s*([^;}{]+)")
Z_INDEX = re.compile(r"(?<![\w-])z-index\s*:\s*(-?\d+)")


def english_pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    pages, catalog_done = [], False
    for rel in sorted(out.splitlines()):
        if rel.startswith(("es/", "_", "a11y/", "pipeline/")) or "/_" in rel:
            continue
        if rel.startswith("catalog/") and rel.count("/") >= 2:
            if catalog_done:
                continue
            catalog_done = True
        pages.append(ROOT / rel)
    if not pages:
        raise SystemExit("design_budget: no tracked pages found (is this a git checkout?)")
    return pages


def sources():
    """(name, css text, is_theme) for every place hand-written CSS lives."""
    for f in sorted(CSS.glob("*.css")):
        if f.name not in COMPILED:
            yield f.name, f.read_text(encoding="utf-8"), f.name == "theme.css"
    for page in english_pages():
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(ROOT).as_posix()
        for i, block in enumerate(STYLE_BLOCK.findall(text)):
            yield f"{rel} <style> {i}", block, False
        attrs = [m.group(2) if m.group(2) is not None else m.group(3) for m in STYLE_ATTR.finditer(text)]
        if attrs:
            yield f"{rel} style=", ";".join(attrs), False


def normal(value):
    value = re.sub(r"\s+", " ", value.replace("!important", "")).strip()
    value = re.sub(r"(?<![\d.])\.(\d)", r"0.\1", value)                      # .9em and 0.9em are one value
    return re.sub(r"#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])\b", r"#\1\1\2\2\3\3", value).upper() \
        if value.startswith("#") else value                                  # #fff and #FFFFFF are one color


def measure(items=None):
    """Distinct values per kind: {kind: Counter(value -> uses)}, and the first source of each value."""
    found = {k: Counter() for k in CAPS}
    where = {k: {} for k in CAPS}

    def add(kind, value, name):
        value = normal(value)
        found[kind][value] += 1
        where[kind].setdefault(value, name)

    for name, text, is_theme in (sources() if items is None else items):
        body = COMMENT.sub("", text)
        for m in FONT_SIZE.finditer(body):
            add("font_sizes", m.group(1), name)
        for m in FONT_SHORT.finditer(body):
            add("font_sizes", m.group(1), name)
        for m in SPACING.finditer(body):
            for number, unit in LENGTH.findall(m.group(1)):
                if float(number) != 0:
                    add("spacing", number + unit, name)
        for m in BREAKPOINT.finditer(body):
            add("breakpoints", f"{m.group(1)} {m.group(2)}{m.group(3)}", name)
        for m in RADIUS.finditer(body):
            value = m.group(1).strip()
            if "var(" not in value and value not in ("0", "inherit"):
                add("fixed_radii", value, name)
        for m in SHADOW.finditer(body):
            add("shadows", m.group(1), name)
        for m in Z_INDEX.finditer(body):
            add("z_index", m.group(1), name)
        if not is_theme:
            for c in COLOR.findall(body):
                add("fixed_colors", c.replace(" ", "") if not c.startswith("#") else c, name)
    return found, where


def counts(items=None):
    found, _ = measure(items)
    return {k: len(v) for k, v in found.items()}


LOGO_FILL = re.compile(r'fill="(#[0-9A-Fa-f]{6})"')


def logo_color_uses(files=None):
    """Every use of a logo color that is not the fill="" of an SVG path in a page or in favicon.svg.

    files: iterable of (relative path, text); by default every tracked .html, .css, .js and .svg file."""
    if files is None:
        out = subprocess.run(["git", "ls-files", "*.html", "*.css", "*.js", "*.svg", "*.mjs", "*.cjs"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        files = ((rel, (ROOT / rel).read_text(encoding="utf-8", errors="replace")) for rel in out.splitlines())
    pattern = re.compile("|".join(c[1:] for c in LOGO_COLORS), re.I)
    bad = []
    for rel, text in files:
        if rel.endswith((".css", ".js", ".mjs", ".cjs")):  # a comment is not a use; keep the line numbers
            text = COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
        allowed = rel.endswith((".html", ".svg"))
        fills = {m.start(1) + 1 for m in LOGO_FILL.finditer(text)} if allowed else set()
        for m in pattern.finditer(text):
            if m.start() not in fills:
                line = text.count("\n", 0, m.start()) + 1
                bad.append(f"{rel}:{line}")
    return bad


def problems(current, caps=None):
    """Messages for every count above its cap (a regression) or below it (lower the cap)."""
    caps = CAPS if caps is None else caps
    out = []
    if set(current) != set(caps):
        out.append(f"kinds differ: {sorted(set(current) ^ set(caps))}")
    for kind in sorted(set(current) & set(caps)):
        if current[kind] > caps[kind]:
            out.append(f"{kind}: {current[kind]} distinct values, the cap is {caps[kind]}; use an existing value "
                       f"(python pipeline/design_budget.py --json lists them)")
        elif current[kind] < caps[kind]:
            out.append(f"{kind}: {current[kind]} distinct values now; lower CAPS[{kind!r}] from {caps[kind]} to "
                       f"{current[kind]} in pipeline/design_budget.py")
    return out


def main(argv):
    found, where = measure()
    if "--json" in argv:
        report = {k: {"count": len(v), "cap": CAPS[k], "goal": GOALS[k],
                      "values": {val: [n, where[k][val]] for val, n in sorted(v.items())}} for k, v in found.items()}
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 0
    for k, v in found.items():
        print(f"{k:13} {len(v):3}  cap {CAPS[k]:3}  goal {GOALS[k]:3}")
    bad = logo_color_uses()
    print("logo colors outside the logo:", ", ".join(bad) if bad else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
