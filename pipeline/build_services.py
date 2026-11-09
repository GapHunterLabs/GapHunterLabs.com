#!/usr/bin/env python3
"""build_services.py -- applies data/services.json, the single source for the published services (decision D11,
2026-11-09), to every page that shows a service figure.

On the English pages (build_i18n.py makes the Spanish ones afterwards, and the Spanish text keeps its own wording):
  1. Bound figures. Each <!--svc:<key>.<level>.<usd|days>--> is followed by its figure, and the figure is rewritten
     from services.json (10500 -> "10,500"). The comment is invisible and build_i18n drops it before it looks a text
     up, so the translation keys do not change.
  2. The social-image alt text of each service page (og:image:alt and twitter:image:alt): its "USD n" is the
     service's lowest price.
  3. The OfferCatalog of the home's JSON-LD: one Offer per service, with its URL, name and lowest and highest price
     (no highest price when a tier is open-ended).
  4. js/contact.js: the SERVICES list of the engagement form, between its SERVICES:START and SERVICES:END markers.
The footer column comes from the same file through build_chrome.py, and the social images through build_page_og.py.

The build stops, naming the page and line, on:
  - a binding to a service, level or field that does not exist, or to the days of an open-ended tier;
  - a "USD n" in one of these pages that is not bound, which is a price typed by hand again;
  - a price or delivery time in services.json that its own page, /services/ or the home does not show.

Usage:
  python pipeline/build_services.py            # apply (run before build_chrome and build_i18n)
  python pipeline/build_services.py --check    # change nothing; exit 1 if a page is out of date
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import services_data as S  # noqa: E402
from site_config import SITE_URL  # noqa: E402

ROOT = S.ROOT
HOME, HUB, CATALOG = "/", "/services/", "/catalog/"
CONTACT_JS = Path("js") / "contact.js"
OTHER_OPTION = ("other", "Something else", "Otra cosa")

BIND_RE = re.compile(r"<!--svc:([^>]*?)-->(\d{1,3}(?:,\d{3})+|\d+)?")
UNBOUND_RE = re.compile(r"USD\s+(?!<!--svc:)\d")
ALT_META_RE = re.compile(r'(<meta (?:property="og:image:alt"|name="twitter:image:alt") content=")([^"]*)(">)')
ALT_PRICE_RE = re.compile(r"USD \d{1,3}(?:,\d{3})*")
JS_BLOCK_RE = re.compile(r"( *// SERVICES:START[^\n]*\n)(.*?)( *// SERVICES:END)", re.S)


class BuildError(Exception):
    pass


def page_file(root, url_path):
    return root / url_path.strip("/") / "index.html" if url_path != "/" else root / "index.html"


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def skip_ranges(text):
    """<head> and <script> blocks: prices there are handled by rules 2 and 3, not by bindings."""
    ranges = [(m.start(), m.end()) for m in re.finditer(r"<script\b.*?</script>", text, re.S)]
    head = re.search(r"<head\b.*?</head>", text, re.S)
    if head:
        ranges.append((head.start(), head.end()))
    return ranges


def bind(text, data, label):
    """Rewrite every bound figure. Returns (text, set of bindings used)."""
    used = set()

    def sub(m):
        ref, figure = m.group(1), m.group(2)
        if figure is None:
            raise BuildError("%s:%d: <!--svc:%s--> is not followed by a figure" % (label, line_of(text, m.start()), ref))
        try:
            v = S.value(data, ref)
        except S.ServicesError as exc:
            raise BuildError("%s:%d: %s" % (label, line_of(text, m.start()), exc)) from None
        used.add(ref)
        return "<!--svc:%s-->%s" % (ref, S.usd(v) if ref.endswith(".usd") else str(v))
    return BIND_RE.sub(sub, text), used


def unbound(text, label):
    skips = skip_ranges(text)
    bad = [line_of(text, m.start()) for m in UNBOUND_RE.finditer(text)
           if not any(a <= m.start() < b for a, b in skips)]
    return ["%s:%d: \"USD n\" without a <!--svc:...--> binding" % (label, ln) for ln in bad]


def head_prices(text, label, service):
    """Rule 2 on a service page; anywhere else a price in <head> is an error."""
    head = re.search(r"<head\b.*?</head>", text, re.S)
    if not head:
        raise BuildError("%s: no <head>" % label)
    h = head.group(0)
    if service is None:
        if ALT_PRICE_RE.search(h):
            raise BuildError("%s:%d: a price in <head> that no rule keeps up to date"
                             % (label, line_of(text, head.start() + ALT_PRICE_RE.search(h).start())))
        return text
    lowest = "USD " + S.usd(S.min_usd(service))
    found = 0

    def sub(m):
        nonlocal found
        prices = ALT_PRICE_RE.findall(m.group(2))
        if len(prices) != 1:
            raise BuildError("%s: %s must name exactly one price, found %d" % (label, m.group(0)[:40], len(prices)))
        found += 1
        return m.group(1) + ALT_PRICE_RE.sub(lowest, m.group(2)) + m.group(3)
    new_head = ALT_META_RE.sub(sub, h)
    if found != 2:
        raise BuildError("%s: expected og:image:alt and twitter:image:alt with a price, found %d" % (label, found))
    rest = ALT_META_RE.sub("", new_head)
    if ALT_PRICE_RE.search(rest):
        raise BuildError("%s: a price in <head> outside the image alt texts" % label)
    return text[:head.start()] + new_head + text[head.end():]


def offer_catalog(text, data, label):
    key = '"hasOfferCatalog": '
    at = text.find(key)
    if at < 0 or text.find(key, at + 1) >= 0:
        raise BuildError("%s: expected exactly one \"hasOfferCatalog\" in the JSON-LD" % label)
    start = at + len(key)
    old, length = json.JSONDecoder().raw_decode(text[start:])
    line_start = text.rfind("\n", 0, at) + 1
    indent = text[line_start:at]
    if indent.strip():
        raise BuildError("%s: \"hasOfferCatalog\" must start its own line" % label)
    nl = "\r\n" if "\r\n" in text else "\n"
    offers = []
    for s in data["services"]:
        spec = {"@type": "PriceSpecification", "minPrice": str(S.min_usd(s))}
        if S.max_usd(s) is not None:
            spec["maxPrice"] = str(S.max_usd(s))
        spec["priceCurrency"] = "USD"
        offers.append({"@type": "Offer", "priceSpecification": spec, "url": SITE_URL + s["path"],
                       "itemOffered": {"@type": "Service", "name": s["name"]}})
    catalog = {"@type": "OfferCatalog", "name": old.get("name", "Developer tooling services"), "itemListElement": offers}
    dumped = json.dumps(catalog, indent=2, ensure_ascii=False).split("\n")
    block = nl.join([dumped[0]] + [indent + ln for ln in dumped[1:]])
    return text[:start] + block + text[start + length:]


def js_str(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def contact_services(text, data, label):
    m = JS_BLOCK_RE.search(text)
    if not m or len(JS_BLOCK_RE.findall(text)) != 1:
        raise BuildError("%s: expected one SERVICES:START ... SERVICES:END block" % label)
    nl = "\r\n" if "\r\n" in text else "\n"
    rows = [(s["key"], s["contactLabel"]["en"], s["contactLabel"]["es"]) for s in data["services"]] + [OTHER_OPTION]
    body = nl.join(["  var SERVICES = ["]
                   + ["    [%s, t(%s, %s)]%s" % (js_str(k), js_str(en), js_str(es), "," if i < len(rows) - 1 else "")
                      for i, (k, en, es) in enumerate(rows)]
                   + ["  ];"]) + nl
    return text[:m.start(2)] + body + text[m.end(2):]


def coverage(data, used_by_page):
    """Every price and delivery time must be shown on its own page, on /services/ and on the home."""
    errors = []
    for s in data["services"]:
        for lv in s["tiers"] + s.get("addOns", []):
            for field in S.FIELDS:
                if lv.get(field) is None:
                    continue
                ref = "%s.%s.%s" % (s["key"], lv["id"], field)
                for where in (s["path"], HUB, HOME):
                    if ref not in used_by_page.get(where, set()):
                        errors.append("%s: no page binding shows %s (%s)" % (where, ref, lv[field]))
    return errors


def og_stamp_problems(root=ROOT):
    """The social images are PNGs rendered by build_page_og.py, outside this build. Their prices come from
    services.json too, so a price change leaves them stale until they are rendered again: compare the prices they
    would show now with the ones recorded at their last full render."""
    import build_page_og
    stamp = root / "data" / "og-prices.json"
    if not stamp.is_file():
        return ["data/og-prices.json is missing: run python pipeline/build_page_og.py"]
    try:
        recorded = json.loads(stamp.read_text(encoding="utf-8")).get("texts")
    except ValueError as exc:
        return ["data/og-prices.json: not valid JSON (%s)" % exc]
    now = build_page_og.og_price_texts()
    if recorded != now:
        changed = sorted(set(now) ^ set(recorded or []))
        return ["the social images show old prices (%s): run python pipeline/build_page_og.py and bump OG_VERSION "
                "in site_config.py" % "; ".join(changed[:4])]
    return []


def build(root=ROOT, data=None):
    """-> {relative path: new text} for every file that changes. Raises BuildError or ServicesError."""
    data = S.load(root=root) if data is None else S.validate(data, root)
    by_path = {s["path"]: s for s in data["services"]}
    pages = [HOME, HUB, CATALOG] + [s["path"] for s in data["services"]]
    changes, used_by_page, problems = {}, {}, []
    for url in pages:
        path = page_file(root, url)
        label = path.relative_to(root).as_posix()
        old = read(path)
        new, used = bind(old, data, label)
        used_by_page[url] = used
        problems += unbound(new, label)
        new = head_prices(new, label, by_path.get(url))
        if url == HOME:
            new = offer_catalog(new, data, label)
        if new != old:
            changes[label] = new
    js = root / CONTACT_JS
    old = read(js)
    new = contact_services(old, data, CONTACT_JS.as_posix())
    if new != old:
        changes[CONTACT_JS.as_posix()] = new
    problems += coverage(data, used_by_page)
    if problems:
        raise BuildError("\n".join(problems))
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if a page is out of date")
    args = ap.parse_args()
    try:
        changes = build()
    except (BuildError, S.ServicesError) as exc:
        print("[build_services] ERROR: %s" % exc, file=sys.stderr)
        return 1
    og = og_stamp_problems()
    for msg in og:
        print("[build_services] %s: %s" % ("ERROR" if args.check else "WARNING", msg), file=sys.stderr)
    if args.check:
        for rel in sorted(changes):
            print("[build_services] out of date: %s" % rel, file=sys.stderr)
        print("[build_services] %s" % ("up to date" if not (changes or og) else "%d file(s) out of date" % len(changes)))
        return 1 if (changes or og) else 0
    for rel, text in changes.items():
        with open(ROOT / rel, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    print("[build_services] %d file(s) updated from data/services.json" % len(changes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
