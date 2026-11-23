"""Inline the isometric figures into the pages.

The figures are drawn at build time by pipeline/iso/build.cjs (python pipeline/build_iso_figures.py) and committed as
pipeline/iso/out/<name>.svg. A page marks the place of each one with

    <!-- PRERENDER:ISO:<name>:START --><!-- PRERENDER:ISO:<name>:END -->

and its generator calls inject(). The browser receives static SVG and CSS; nothing runs at load time.

load() applies the figure rules again, so a hand-edited or stale SVG fails the page build instead of shipping:
at most BUDGET_BYTES and BUDGET_NODES, no filter, no hard-coded color (CSS variables only), every id prefixed with
the figure name, aria-hidden on the root, and at most one turquoise detail.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "iso" / "out"
BUDGET_BYTES = 40 * 1024
BUDGET_NODES = 400
NAME = re.compile(r"^[a-z][a-z0-9-]*$")
ALLOWED_PAINT = re.compile(r"^(var\(--iso-[a-z0-9-]+\)|url\(#[A-Za-z0-9_-]+\)|none|transparent|currentColor)$")


class FigureError(ValueError):
    pass


def problems(name: str, svg: str) -> list[str]:
    """Every rule the figure breaks; an empty list means it can ship."""
    out = []
    size = len(svg.encode("utf-8"))
    nodes = len(re.findall(r"<(?!/)[a-zA-Z]", svg))
    if size > BUDGET_BYTES:
        out.append("%d bytes, the budget is %d" % (size, BUDGET_BYTES))
    if nodes > BUDGET_NODES:
        out.append("%d nodes, the budget is %d" % (nodes, BUDGET_NODES))
    if re.search(r"<filter\b|\sfilter=|feGaussianBlur|feTurbulence", svg):
        out.append("uses a live filter")
    bad_ids = [i for i in re.findall(r' id="([^"]+)"', svg) if not i.startswith("iso-%s-" % name)]
    if bad_ids:
        out.append("ids without the iso-%s- prefix: %s" % (name, ", ".join(bad_ids[:3])))
    refs = [r for r in re.findall(r"url\(#([^)]+)\)", svg) if not r.startswith("iso-%s-" % name)]
    if refs:
        out.append("references outside the figure: %s" % ", ".join(refs[:3]))
    hard = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", re.sub(r"url\(#[^)]+\)", "", svg))
    # Every paint value must be a --iso-* variable or a gradient of the figure: a named color ("red") is hard-coded too.
    paints = (re.findall(r'\b(?:fill|stroke|color)="([^"]*)"', svg)
              + re.findall(r'(?:stop-color|fill|stroke|color)\s*:\s*([^;"]+)', svg))
    hard += [v.strip() for v in paints if not ALLOWED_PAINT.match(v.strip())]
    if hard:
        out.append("hard-coded colors: %s" % ", ".join(hard[:3]))
    root = re.match(r"<svg\b[^>]*>", svg)
    if not root:
        out.append("does not start with <svg>")
    elif ' aria-hidden="true"' not in root.group(0):
        out.append('the <svg> is not aria-hidden="true"')
    turquoise = len(re.findall(r"--iso-accent-2\b", svg))
    if turquoise > 1:
        out.append("%d turquoise details, at most 1" % turquoise)
    if re.search(r"<script|\son[a-z]+=|javascript:", svg, re.I):
        out.append("contains script")
    return out


def load(name: str) -> str:
    if not NAME.match(name or ""):
        raise FigureError("invalid figure name %r" % (name,))
    path = OUT / (name + ".svg")
    if not path.is_file():
        raise FigureError("missing pipeline/iso/out/%s.svg: run python pipeline/build_iso_figures.py" % name)
    svg = path.read_text(encoding="utf-8").strip()
    found = problems(name, svg)
    if found:
        raise FigureError("figure %s: %s" % (name, "; ".join(found)))
    return svg


def inject(html: str, name: str, where: str) -> str:
    """Put figure `name` between its markers in `html`; the markers must appear exactly once."""
    start, end = "<!-- PRERENDER:ISO:%s:START -->" % name, "<!-- PRERENDER:ISO:%s:END -->" % name
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    found = len(pattern.findall(html))
    if found != 1:
        raise FigureError("%s: the PRERENDER:ISO:%s markers appear %d times (need exactly 1)" % (where, name, found))
    svg = load(name)
    return pattern.sub(lambda _m: start + svg + end, html, count=1)


def inject_or_die(html: str, name: str, where: str, tag: str) -> str:
    try:
        return inject(html, name, where)
    except FigureError as exc:
        sys.exit("[%s] ERROR: %s" % (tag, exc))
