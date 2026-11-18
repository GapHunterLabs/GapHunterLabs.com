# -*- coding: utf-8 -*-
"""
og_kit.py -- shared pieces of the social-share (Open Graph) images, 1200x630.

Used by build_page_og.py (the hand-made pages, EN and ES), build_og_images.py
(one image per plugin and per VS Code extension). The look is the site's: near-black
ground with the faint grid and the orange glow of the home hero, a large headline,
one short line of purpose, and inline-SVG badges (pipeline/badges.py) that say
what it is made of. Everything is sized to stay legible at 300px wide (the size
of a small feed preview): headline 56px or more, body 26px or more, badges 22px.

render() screenshots each page with Chromium (Playwright) and fails on text that
is clipped or leaves the canvas, so a long title never ships cut off.
"""
from __future__ import annotations

import html as html_mod
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from badges import badge, price_badge  # noqa: E402

FONTS = (ROOT / "fonts").resolve()
ES = json.loads((HERE / "i18n" / "es.json").read_text(encoding="utf-8"))
SITE_HOST = "gaphunterlabs.com"
W, H = 1200, 630

LOGO = (
    '<svg viewBox="172 81 675 782" aria-hidden="true">'
    '<path d="M 511,81 L 847,283 L 725,351 L 508,223 L 296,348 L 296,588 L 463,691 L 342,765 L 173,665 L 172,281 Z" fill="#0151FC"/>'
    '<path d="M 846,412 L 844,668 L 518,863 L 393,795 L 724,589 L 721,540 L 567,538 L 568,412 Z" fill="#01B3FD"/>'
    '<polygon points="569,413 695,413 695,539 569,539" fill="#02F172"/></svg>'
)

# Badge registry: key -> (label, icon, variant, brand hex). Labels are translated with the site's own dictionary.
REG = {
    "jetbrains": ("JetBrains IDEs", "jetbrains", "dark", None),
    "idea": ("IntelliJ IDEA", "intellij-idea", "dark", None),
    "platform": ("IntelliJ Platform", "jetbrains", "dark", None),
    "marketplace": ("JetBrains Marketplace", "jetbrains", "dark", None),
    "vscode": ("VS Code", "vscode", "brand", "007ACC"),
    "atlassian": ("Atlassian Marketplace", "atlassian", "dark", None),
    "windows": ("Windows", "windows", "dark", None),
    "kotlin": ("Kotlin", "kotlin", "brand", None),
    "java": ("Java", "java", "soft", None),
    "python": ("Python", "python", "brand", None),
    "gradle": ("Gradle", "gradle", "soft", None),
    "git": ("Git", "git", "brand", None),
    "github": ("GitHub", "github", "dark", None),
    "actions": ("GitHub Actions", "github-actions", "brand", None),
    "gitlab": ("GitLab CI", "gitlab", "brand", None),
    "linkedin": ("LinkedIn", "linkedin", "brand", None),
    "static": ("Static analysis", "code", "dark", None),
    "perf": ("Performance", "gauge", "dark", None),
    "security": ("Security research", "shield", "dark", None),
    "reliability": ("Reliability", "layers", "dark", None),
    "audit": ("Third-party audit", "search", "dark", None),
    "email": ("Email", "mail", "dark", None),
}
PRICE = {"free": "Free", "freemium": "Freemium", "paid": "Paid", "pending": "Pending"}


# Labels that only the OG images use (the site's dictionary does not have them).
EXTRA_ES = {"Email": "Correo", "No accounts": "Sin cuentas", "No ad tracking": "Sin rastreo publicitario"}


def tr(text: str, lang: str) -> str:
    """Translate a label with the site's EN->ES dictionary; unknown labels (product names) stay as they are."""
    return EXTRA_ES.get(text, ES.get(text, text)) if lang == "es" else text


def esc(text) -> str:
    return html_mod.escape(str(text), quote=False)


def text_html(text: str) -> str:
    """Escape plain text; a newline becomes <br>."""
    return "<br>".join(esc(line) for line in str(text).split("\n"))


def badges_html(keys, lang: str = "en") -> str:
    out = []
    for k in keys:
        if k in PRICE:
            out.append(price_badge(k, tr(PRICE[k], lang)))
            continue
        if isinstance(k, tuple):  # ad-hoc (label, icon, variant)
            label, icon, variant = k
            out.append(badge(tr(label, lang), icon=icon, variant=variant))
            continue
        label, icon, variant, hex6 = REG[k]
        out.append(badge(tr(label, lang), icon=icon, variant=variant, hex6=hex6))
    return '<div class="badges">%s</div>' % "".join(out)


def headline_size(h1: str, *, wide: bool = True) -> int:
    """Headline px from the longest line: short lines get the biggest type, long ones step down but never below 56."""
    longest = max(len(line) for line in h1.split("\n"))
    sizes = ((20, 80), (26, 72), (32, 64), (10 ** 9, 56)) if wide else ((16, 64), (22, 58), (10 ** 9, 54))
    return next(px for limit, px in sizes if longest <= limit)


BASE_CSS = r"""
  @font-face { font-family:"IBM Plex Sans"; src:url("@@FONTS@@/IBMPlexSans-Latin.woff2") format("woff2"); font-weight:100 700; font-display:block; }
  @font-face { font-family:"JetBrains Mono"; src:url("@@FONTS@@/JetBrainsMono-Latin.woff2") format("woff2"); font-weight:100 800; font-display:block; }
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:1200px; height:630px; overflow:hidden; background:#0A0A0A; color:#EDEDED; font-family:"IBM Plex Sans",sans-serif; }
  /* Grid and glow: the home hero, faded toward the bottom right. */
  .bg { position:absolute; inset:0; pointer-events:none;
    background:
      radial-gradient(640px 300px at 14% 0%, rgba(255,106,26,.22), transparent 70%),
      radial-gradient(520px 260px at 100% 100%, rgba(1,81,252,.10), transparent 70%),
      linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
    background-size:auto, auto, 48px 48px, 48px 48px;
    -webkit-mask-image:linear-gradient(180deg,#000 0%,#000 55%,rgba(0,0,0,.35) 100%); }
  .frame { position:absolute; inset:0; padding:46px 64px 40px; display:flex; flex-direction:column; }
  .top { display:flex; align-items:center; justify-content:space-between; gap:24px; flex:none; }
  .brand { display:flex; align-items:center; gap:14px; font:700 26px/1 "IBM Plex Sans",sans-serif; letter-spacing:-0.01em; color:#EDEDED; }
  .brand svg { width:34px; height:39px; display:block; }
  .eyebrow { font:600 20px/1.2 "JetBrains Mono",monospace; letter-spacing:.12em; text-transform:uppercase; color:#FF6A1A; text-align:right;
    max-width:640px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .main { flex:1 1 auto; min-height:0; display:flex; flex-direction:column; justify-content:center; padding:14px 0 10px; overflow:hidden; }
  .headline { font-weight:700; line-height:1.06; letter-spacing:-0.035em; color:#FFFFFF; }
  .lede { margin-top:22px; font:400 28px/1.42 "IBM Plex Sans",sans-serif; color:#B4B4B4; max-width:1000px; }
  .badges { display:flex; flex-wrap:wrap; gap:12px; margin-top:28px; }
  .foot { flex:none; display:flex; align-items:center; justify-content:space-between; gap:24px; padding-top:18px; border-top:1px solid #262626;
    font:500 20px/1.2 "JetBrains Mono",monospace; color:#9A9A9A; }
  .foot .host { color:#EDEDED; font-weight:600; }
  .foot .note { text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:760px; }
  .card { background:#111111; border:1px solid #2E2E2E; border-radius:16px; }
  /* Badges at OG scale (same markup and variants as css-src/tailwind.css). */
  .badge { display:inline-flex; align-items:center; gap:10px; height:46px; padding:0 18px; border-radius:8px; border:1px solid transparent;
    font:600 22px/1 "IBM Plex Sans",sans-serif; white-space:nowrap; background:var(--b-bg,#1C1C1C); color:var(--b-fg,#fff); }
  .badge .b-ico { width:25px; height:25px; flex:none; fill:currentColor; }
  .badge--dark { --b-bg:#171717; --b-fg:#FFFFFF; border-color:#3A3A3A; }
  .badge--soft { --b-bg:#F3F4F6; --b-fg:#1F2937; }
  .badge--soft .b-ico { fill:var(--b-ico,currentColor); }
  .badge-status { --b-bg:#161616; --b-fg:#EDEDED; border-color:#737373; gap:11px; }
  .badge-status::before { content:""; width:11px; height:11px; border-radius:50%; background:var(--dot,#A3A3A3); }
  .badge-status.is-free { --dot:#10B981; } .badge-status.is-freemium { --dot:#4FB3D9; }
  .badge-status.is-paid { --dot:#F59E0B; } .badge-status.is-pending { --dot:#A3A3A3; }
"""

CHECK_JS = """() => {
  const out = [];
  const main = document.querySelector('.main');
  if (main && (main.scrollHeight > main.clientHeight + 1)) out.push('content taller than the canvas (' + main.scrollHeight + ' > ' + main.clientHeight + ')');
  document.querySelectorAll('[data-fit]').forEach(el => {
    if (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) out.push('clipped: ' + el.className);
  });
  for (const el of document.querySelectorAll('.frame *')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > 1200.5 || r.bottom > 630.5 || r.left < -0.5 || r.top < -0.5)) { out.push('outside the canvas: ' + el.className + ' ' + Math.round(r.right) + 'x' + Math.round(r.bottom)); break; }
  }
  const h = document.querySelector('.headline');
  if (h) { const lh = parseFloat(getComputedStyle(h).lineHeight); const lines = Math.round(h.getBoundingClientRect().height / lh); if (lines > 3) out.push('headline wraps to ' + lines + ' lines'); }
  const blocks = [...document.querySelectorAll('.main > *')].map(e => e.getBoundingClientRect());
  for (let i = 1; i < blocks.length; i += 1) if (blocks[i].top < blocks[i - 1].bottom - 1) out.push('blocks overlap in .main');
  return out;
}"""


def page_html(lang: str, body: str, *, css: str = "", label: str = "", note: str = "", host: str = SITE_HOST) -> str:
    css_all = (BASE_CSS + css).replace("@@FONTS@@", FONTS.as_uri())
    eyebrow = '<div class="eyebrow">%s</div>' % esc(label) if label else ""
    note_html = '<div class="note">%s</div>' % esc(note) if note else ""
    return (
        '<!doctype html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n<meta name="robots" content="noindex">\n'
        '<title>Gap Hunter Labs social share preview</title>\n<style>%s</style>\n</head>\n<body>\n'
        '<div class="bg"></div>\n<div class="frame">\n'
        '  <div class="top"><div class="brand">%s Gap Hunter Labs</div>%s</div>\n'
        '  <div class="main">%s</div>\n'
        '  <div class="foot"><span class="host">%s</span>%s</div>\n'
        '</div>\n</body>\n</html>\n' % (lang, css_all, LOGO, eyebrow, body, esc(host), note_html)
    )


def render(jobs, out_path, *, check: bool = True, label: str = "og"):
    """jobs: iterable of (key, html). out_path(key) -> Path. Raises SystemExit listing every image that fails the checks."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("[%s] ERROR: falta playwright -- pip install playwright && python -m playwright install chromium" % label)
    written, problems = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            for key, html in jobs:
                out = out_path(key)
                out.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                    f.write(html)
                    tmp = Path(f.name)
                try:
                    page.goto(tmp.resolve().as_uri(), wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    page.wait_for_timeout(200)
                    if check:
                        issues = page.evaluate(CHECK_JS)
                        if issues:
                            problems.append("%s: %s" % (key, "; ".join(issues)))
                    page.screenshot(path=str(out), type="png")
                finally:
                    tmp.unlink(missing_ok=True)
                if not out.exists() or out.stat().st_size < 5000:
                    problems.append("%s: PNG missing or suspiciously small" % key)
                written.append(out)
        finally:
            browser.close()
    if problems:
        sys.exit("[%s] %d image(s) failed the layout checks:\n  - %s" % (label, len(problems), "\n  - ".join(problems)))
    return written
