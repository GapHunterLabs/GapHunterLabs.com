"""inline_critical_css.py -- copy pipeline/critical/<page>.css into the <style id="critical-css"> of its English page
(see critical_css.py). A regenerate.py step before build_i18n, which copies the block into the Spanish page.

    python pipeline/inline_critical_css.py

Stops the build when the file is missing, empty or over its size cap, when the page has no block or more than one,
or when a stylesheet still loads in <head> or before </main>.
"""
import sys

import critical_css as C


def main():
    for key, spec in C.PAGES.items():
        path = C.css_path(key)
        if not path.is_file():
            C.die("%s is missing; run python pipeline/build_critical_css.py" % path.relative_to(C.ROOT).as_posix())
        css = path.read_text(encoding="utf-8").strip()
        page = C.ROOT / spec["html"]
        with open(page, encoding="utf-8", newline="") as f:
            html = f.read()
        new = C.inline(html, css, spec["html"])
        if new != html:
            tmp = page.with_suffix(page.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            tmp.replace(page)
        print("[inline_critical_css] %s: %d bytes of critical CSS%s" % (spec["html"], len(css.encode("utf-8")),
                                                                       "" if new != html else ", unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
