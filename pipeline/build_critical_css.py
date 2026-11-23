"""build_critical_css.py -- render the home with Chromium and write the rules its first screen needs to
pipeline/critical/home.css (see critical_css.py for why).

    python pipeline/build_critical_css.py            # then: python pipeline/regenerate.py --strict
    python pipeline/build_critical_css.py --check    # exit 1 if the committed file differs from a fresh extraction

Each URL of the page is rendered at every width in critical_css.VIEWPORTS and in every theme state, with its fonts
loaded. A style rule is kept when one of its selectors matches an element on the first screen of any render; the
result keeps the source order of the stylesheets, so the cascade is the same as with the full files. Run it after a
change to the CSS or to the first screen of the home: _review/verify_site.py compares the first screen painted with
only this CSS against the full page and fails while it is out of date.

Needs Playwright and its Chromium, so regenerate.py does not run it (see regenerate.EXCLUDED).
"""
import argparse
import functools
import http.server
import re
import sys
import threading

import critical_css as C


def serve():
    handler = functools.partial(type("Quiet", (http.server.SimpleHTTPRequestHandler,),
                                     {"log_message": lambda *a: None}), directory=str(C.ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def open_page(browser, base, url, viewport, theme, scheme):
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, color_scheme=scheme,
                              reduced_motion="no-preference", locale="en-US")
    ctx.add_init_script("try{localStorage.setItem('ghl-theme','%s')}catch(e){}" % theme)
    page = ctx.new_page()
    page.goto(base + url, wait_until="load")
    page.evaluate("document.fonts.ready.then(() => true)")
    return ctx, page


def extract(browser, base, key):
    spec = C.PAGES[key]
    js = C.EXTRACTOR.read_text(encoding="utf-8")
    union, sheets = set(), None
    for url in spec["urls"]:
        for viewport in C.VIEWPORTS:
            for theme, scheme in C.THEMES:
                ctx, page = open_page(browser, base, url, viewport, theme, scheme)
                try:
                    got = page.evaluate(js, ["paths", viewport[1] * C.FOLD, []])
                finally:
                    ctx.close()
                if not got["sheets"]:
                    C.die("%s at %s loads no stylesheet under /css/" % (key, url))
                if sheets is not None and got["sheets"] != sheets:
                    C.die("%s loads different stylesheets at %s: %s, not %s" % (key, url, got["sheets"], sheets))
                sheets = got["sheets"]
                union.update(got["paths"])
    ctx, page = open_page(browser, base, spec["urls"][0], C.VIEWPORTS[-1], "dark", "dark")
    try:
        css = page.evaluate(js, ["emit", 0, sorted(union)])
    finally:
        ctx.close()
    # One line: no line endings for git to convert, so the inlined copy is the same on every checkout.
    css = re.sub(r"\s*\n\s*", " ", css).strip()
    C.check_css("the extracted CSS of %s" % key, css)
    return css, sheets, len(union)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if a committed file differs from a fresh extraction")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    srv, base = serve()
    stale = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                for key in C.PAGES:
                    css, sheets, rules = extract(browser, base, key)
                    path = C.css_path(key)
                    old = path.read_text(encoding="utf-8").strip() if path.exists() else None
                    raw, packed = C.check_css(key, css)
                    if args.check:
                        if old != css:
                            stale.append(key)
                    elif old != css:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(css + "\n", encoding="utf-8", newline="\n")
                    print("[build_critical_css] %s: %d rules from %s, %d bytes (%d compressed)%s"
                          % (key, rules, ", ".join(sheets), raw, packed, "" if old != css else ", unchanged"))
            finally:
                browser.close()
    finally:
        srv.shutdown()
    if stale:
        print("[build_critical_css] ERROR: out of date: %s. Run python pipeline/build_critical_css.py, then "
              "python pipeline/regenerate.py --strict" % ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
