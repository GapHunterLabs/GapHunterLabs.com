"""Critical CSS of the home: the rules its first screen needs, written into <head> so the page paints before its four
stylesheets arrive. The stylesheets themselves load at the end of <body>, where they no longer hold back the first
paint; they still apply every rule, in the same order, so the final page looks exactly as before.

Measured on 2026-11-23 against a local gzip server (median of 7 cold loads): first paint 2.6 s -> 1.8 s on a phone
profile (slow 4G, CPU x4) and 420 -> 290 ms on a fast connection; layout shift stays 0.

    build_critical_css.py   renders the home with Chromium and writes pipeline/critical/home.css (run it after a
                            change to the CSS or to the home's first screen; verify_site.py fails until then)
    inline_critical_css.py  copies that file into index.html (a regenerate.py step; build_i18n copies it into the
                            Spanish home)

Nothing here needs JavaScript in the page or relaxes the Content-Security-Policy: style-src already allows inline
styles, and moving the stylesheets to the end of <body> needs no onload handler.

Known gap: Chromium starts painting before a stylesheet at the end of <body> arrives. A browser that waits for every
stylesheet anyway paints as it did before this change, never worse.
"""
import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
CRITICAL = PIPELINE / "critical"
EXTRACTOR = PIPELINE / "critical_css.js"

# page key -> the English page that carries the block (build_i18n copies it) and the URLs whose first screen it covers.
PAGES = {
    "home": {"html": "index.html", "spanish": "es/index.html", "urls": ("/", "/es/")},
}
# Every width the site's breakpoints separate, and every theme state theme-init.js can produce.
VIEWPORTS = ((390, 844), (768, 1024), (1280, 800), (1920, 1080))
THEMES = (("dark", "dark"), ("light", "light"), ("system", "light"), ("system", "dark"))
# A rule is "first screen" if it styles something within 1.25 viewports: the fallback font can pull content a little
# higher in the first paint than in the final layout.
FOLD = 1.25

MAX_BYTES = 40_000
MAX_GZIP = 14_000   # what fits in the first round trip of a new connection (10 TCP segments)

BLOCK = re.compile(r'<style id="critical-css">(.*?)</style>', re.S)
HEAD = re.compile(r"<head\b[^>]*>(.*?)</head>", re.S | re.I)
SHEET = re.compile(r'<link rel="stylesheet" href="/css/[^"]+"\s*/?>', re.I)


def die(message):
    raise SystemExit("critical_css: " + message)


def css_path(key):
    return CRITICAL / ("%s.css" % key)


def check_css(name, css):
    """Reject CSS that is empty, too large for the first round trip, or that could end the <style> element."""
    if not isinstance(css, str) or not css.strip():
        die("%s is empty; run python pipeline/build_critical_css.py" % name)
    if "</" in css:
        die("%s contains '</', which would end the <style> element early" % name)
    raw = css.encode("utf-8")
    if len(raw) > MAX_BYTES:
        die("%s is %d bytes, over the %d-byte cap" % (name, len(raw), MAX_BYTES))
    packed = len(gzip.compress(raw, 9, mtime=0))
    if packed > MAX_GZIP:
        die("%s is %d bytes compressed, over the %d-byte cap" % (name, packed, MAX_GZIP))
    return len(raw), packed


def check_layout(html, page):
    """The block sits once in <head>, no stylesheet is left in <head>, and every stylesheet loads after </main>."""
    head = HEAD.search(html)
    if not head:
        die("%s has no <head>" % page)
    found = BLOCK.findall(html)
    if len(found) != 1:
        die('%s needs exactly one <style id="critical-css"> in <head>, found %d' % (page, len(found)))
    if not BLOCK.search(head.group(1)):
        die('%s has <style id="critical-css"> outside <head>' % page)
    if SHEET.search(head.group(1)):
        die("%s loads a stylesheet in <head>, which holds back the first paint the critical CSS exists for; move it "
            "to the end of <body>" % page)
    sheets = list(SHEET.finditer(html))
    if not sheets:
        die("%s loads no stylesheet after <head>: only the first screen would be styled" % page)
    main_end = html.rfind("</main>")
    if main_end < 0:
        die("%s has no </main>" % page)
    early = [m.group(0) for m in sheets if m.start() < main_end]
    if early:
        die("%s loads %s before </main>: the content after it would wait for it" % (page, early[0]))


def inline(html, css, page="page"):
    """html with the critical block filled with css. Idempotent."""
    check_css("the critical CSS of %s" % page, css)
    check_layout(html, page)
    # A function, not a replacement string: CSS escapes such as content: "\2192" must survive untouched.
    return BLOCK.sub(lambda m: '<style id="critical-css">%s</style>' % css, html, count=1)
