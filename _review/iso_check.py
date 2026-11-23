"""Checks the isometric figures on the site: theme tokens, margins, legibility on a phone and the budget.

    python _review/iso_check.py --out DIR        (after python pipeline/build_iso_figures.py and a rebuild)

Reads the tokens from css/theme.css, the figures from pipeline/iso/out/*.svg and measures them alone and inside the
pages that inline them. Writes DIR/iso_metrics.json and DIR/iso_sheet.png. Exit 1 if a check fails.

1. Themes: the light order of the faces (top > left > right, in CIELAB L*) holds in light and dark; the faces stay at
   least 6 L* apart and the two themes separate them by comparable amounts (ratio at most 1.6); both accents reach
   3:1 against the base (WCAG 1.4.11); the orange accent reaches 4.5:1 as text on the page background; the two dark
   blocks declare the same values.
2. Margins: painted pixels never touch the figure box, in both themes, at 320, 390, 768 and 1280 px.
3. Phone: on each page at 390 px (DPR 3), the finest visible stroke is at least 0.33 CSS px, the fine detail is hidden
   (and shown again at 768 px), and no figure takes more than 40% of the first screen.
4. Budget: pipeline/iso_figures.py finds no problem in any figure.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import re
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import iso_figures  # noqa: E402

PAGES = {"/": ("grid", "hero", "catalog", "stat-downloads", "stat-tools", "stat-prs", "stat-advisories"), "/catalog/": ("catalog",), "/sponsors/": ("sponsors", "stat-downloads", "stat-tools", "stat-prs", "stat-advisories"),
         "/engineering-evidence/": ("evidence", "thumb-analysis", "thumb-tickets", "thumb-security", "thumb-audits"),
         "/services/": ("services",), "/security/": ("security",), "/writing/": ("writing",)}
WIDTHS = (320, 390, 768, 1280)
BACKGROUND = {"grid"}   # drawn behind the hero and faded by CSS: no margin and no phone stroke rule


def blocks():
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "css" / "theme.css").read_text(encoding="utf-8"), flags=re.S)
    light = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    media = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}', css, re.S).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)^\}', css, re.S | re.M).group(1)
    decl = lambda b: {k: v.strip() for k, v in re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", b)}  # noqa: E731
    return decl(light), decl(media), decl(dark)


def lum(hexc):
    h = hexc.strip().lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lstar(hexc):
    y = lum(hexc)
    return 116 * (y ** (1 / 3) if y > 0.008856 else 7.787 * y + 16 / 116) - 16


def theme_checks(fails, M):
    light, media, dark = blocks()
    diff = sorted(k for k in set(media) | set(dark) if media.get(k) != dark.get(k))
    if diff:
        fails.append("dark theme blocks differ: " + ", ".join(diff))
    steps = {}
    for name, t in (("light", light), ("dark", dark)):
        top = lstar(t["--iso-top-2"])
        left = (lstar(t["--iso-left-1"]) + lstar(t["--iso-left-2"])) / 2
        right = (lstar(t["--iso-right-1"]) + lstar(t["--iso-right-2"])) / 2
        s1, s2 = top - left, left - right
        steps[name] = (s1 + s2) / 2
        acc, acc2 = ratio(t["--iso-accent"], t["--iso-top-2"]), ratio(t["--iso-accent-2"], t["--iso-top-2"])
        text = ratio(t["--signal"], t["--bg"])
        M["theme_" + name] = {"L*_top_left_right": [round(top, 1), round(left, 1), round(right, 1)],
                              "step_top_left": round(s1, 1), "step_left_right": round(s2, 1),
                              "orange_vs_base": round(acc, 2), "turquoise_vs_base": round(acc2, 2),
                              "orange_text_vs_page": round(text, 2)}
        if not top > left > right:
            fails.append("%s: face light order broken" % name)
        if min(s1, s2) < 6:
            fails.append("%s: faces closer than 6 L*" % name)
        if acc < 3 or acc2 < 3:
            fails.append("%s: an accent is under 3:1 against the base" % name)
        if text < 4.5:
            fails.append("%s: the orange accent is under 4.5:1 as text on the page" % name)
    k = max(steps.values()) / min(steps.values())
    M["themes_step_ratio"] = round(k, 2)
    if k > 1.6:
        fails.append("themes: face separation differs %.2fx between light and dark" % k)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def margin_checks(b, fails, M, names):
    theme_css = (ROOT / "css" / "theme.css").read_text(encoding="utf-8")
    shell = (ROOT / "css" / "shell.css").read_text(encoding="utf-8")
    # Only rules whose selector STARTS with .iso-figure: a scoped rule such as ".nb-stat-glyph .iso-figure" must not
    # leak into this isolated page and resize every figure.
    rules = "\n".join(re.findall(r"(?m)(^\.iso-figure[^{]*\{[^}]*\}|^@media[^{]*\{\s*\.iso-figure[^}]*\}\s*\})", shell))
    M["margins_px"] = {}
    for name in names:
        if name in BACKGROUND:
            continue
        svg = iso_figures.load(name)
        for theme in ("dark", "light"):
            for vw in WIDTHS:
                p = b.new_page(viewport={"width": vw, "height": 900})
                p.set_content("<!doctype html><html data-theme='%s'><head><style>%s %s body{margin:0;background:transparent}"
                              " .box{padding:16px;max-width:%dpx}</style></head><body><div class=box>%s</div></body></html>"
                              % (theme, theme_css, rules, vw, svg))
                p.wait_for_timeout(50)
                img = Image.open(io.BytesIO(p.query_selector(".iso-figure").screenshot(omit_background=True))).convert("RGBA")
                box = img.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
                p.close()
                if not box:
                    fails.append("%s %s %d: nothing painted" % (name, theme, vw))
                    continue
                m = {"left": box[0], "top": box[1], "right": img.width - box[2], "bottom": img.height - box[3], "width": img.width}
                M["margins_px"]["%s_%s_%d" % (name, theme, vw)] = m
                need = max(4, round(img.width * 0.02))
                if min(m["left"], m["top"], m["right"], m["bottom"]) < need:
                    fails.append("%s %s %dpx: margin under %dpx: %s" % (name, theme, vw, need, m))


def phone_checks(b, base, fails, M):
    M["phone_390"] = {}
    for path, names in PAGES.items():
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, reduced_motion="reduce",
                            locale="en-US")
        p = ctx.new_page()
        p.goto(base + path, wait_until="load")
        for name in names:
            if name in BACKGROUND:
                continue
            svg = iso_figures.load(name)
            vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
            sel = "svg.iso-figure:has(#iso-%s-top)" % name
            r = p.evaluate("(s)=>{const e=document.querySelector(s);if(!e)return null;const b=e.getBoundingClientRect();"
                           "const fine=[...e.querySelectorAll('.iso-fine')];"
                           "return {w:b.width,h:b.height,shown:getComputedStyle(e).display!=='none'&&b.width>0,"
                           "fineHidden:fine.every(x=>getComputedStyle(x).display==='none')}}", sel)
            key = "%s %s" % (path, name)
            if r is None:
                fails.append("%s: figure missing on the page" % key)
                continue
            if not r["shown"]:
                M["phone_390"][key] = {"shown": False}
                continue
            k = r["w"] / vb[2]
            visible = [float(x) for x in re.findall(r'<path(?! class="iso-fine")[^>]*stroke-width="([\d.]+)"', svg)]
            thin = min(visible) * k
            M["phone_390"][key] = {"width": round(r["w"]), "height": round(r["h"]), "scale": round(k, 3),
                                   "finest_visible_stroke_css_px": round(thin, 2), "fine_detail_hidden": r["fineHidden"],
                                   "share_of_first_screen": "%d%%" % round(100 * r["h"] / 844)}
            if thin < 0.33:
                fails.append("%s: a visible stroke renders at %.2f CSS px (under 0.33)" % (key, thin))
            if not r["fineHidden"]:
                fails.append("%s: fine detail still visible at 390 px" % key)
            if r["h"] > 0.4 * 844:
                fails.append("%s: the figure takes %d%% of the first screen" % (key, round(100 * r["h"] / 844)))
        ctx.close()
    ctx = b.new_context(viewport={"width": 768, "height": 900}, reduced_motion="reduce", locale="en-US")
    p = ctx.new_page()
    p.goto(base + "/", wait_until="load")
    if p.evaluate("[...document.querySelectorAll('.nb-hero-figure .iso-fine')].some(e=>getComputedStyle(e).display==='none')"):
        fails.append("768: fine detail hidden on a wide screen")
    ctx.close()


def sheet(b, out, names):
    theme_css = (ROOT / "css" / "theme.css").read_text(encoding="utf-8")
    cells = "".join("<div class=c><p>%s</p>%s</div>" % (n, iso_figures.load(n)) for n in names)
    shots = []
    for theme, bg in (("dark", "#0A0A0A"), ("light", "#FAFAFA")):
        p = b.new_page(viewport={"width": 1400, "height": 400})
        p.set_content("<!doctype html><html data-theme='%s'><head><style>%s body{margin:0;font:13px sans-serif;background:%s;"
                      "color:#888} .g{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;padding:10px} .c p{margin:0}"
                      " .iso-figure{display:block;width:100%%;height:auto}</style></head><body><div class=g>%s</div></body></html>"
                      % (theme, theme_css, bg, cells))
        p.wait_for_timeout(50)
        shots.append(Image.open(io.BytesIO(p.screenshot(full_page=True))))
        p.close()
    im = Image.new("RGB", (1400, sum(s.height for s in shots)))
    y = 0
    for s in shots:
        im.paste(s, (0, y))
        y += s.height
    im.save(out / "iso_sheet.png", optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="folder for the metrics and the sheet (keep it out of the repository)")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    fails, M = [], {}
    names = sorted(p.stem for p in iso_figures.OUT.glob("*.svg"))
    M["budget"] = {}
    for n in names:
        svg = (iso_figures.OUT / (n + ".svg")).read_text(encoding="utf-8").strip()
        probs = iso_figures.problems(n, svg)
        M["budget"][n] = {"bytes": len(svg.encode()), "nodes": len(re.findall(r"<(?!/)[a-zA-Z]", svg)), "problems": probs}
        fails += ["%s: %s" % (n, x) for x in probs]
    theme_checks(fails, M)
    srv, base = serve()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            margin_checks(b, fails, M, names)
            phone_checks(b, base, fails, M)
            sheet(b, out, names)
            b.close()
    finally:
        srv.shutdown()
    M["fails"] = fails
    (out / "iso_metrics.json").write_text(json.dumps(M, indent=1, ensure_ascii=False), encoding="utf-8")
    for f in fails:
        print("FAIL  " + f)
    print("%d checks failed; metrics in %s" % (len(fails), out / "iso_metrics.json"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
