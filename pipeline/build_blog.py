#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_blog.py -- pre-renderiza el Blog (/writing/): los articulos, una tarjeta
por caso real y el calendario de debajo, desde data/blog-cases.json.

Texto en ingles: build_i18n.py lo traduce con pipeline/i18n/es.json, como el
resto del sitio. Cada fecha tiene que poder comprobarse en su fuente publica
(YouTrack, GitHub o el commit) y cada texto tiene que decir lo mismo que la
entrada de /engineering-evidence/ del mismo caso.

El calendario lo arma js/blog.js en el navegador a partir de las fechas de las
tarjetas (<li data-ev-date>), asi que sin JS la pagina sigue mostrando todas
las tarjetas con sus fechas.

Uso:
    python pipeline/build_blog.py
    python pipeline/build_blog.py --dry-run
Despues: build_i18n.py y version_assets.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "blog-cases.json"
PAGE = ROOT / "writing" / "index.html"
START, END = "<!-- PRERENDER:BLOG:START -->", "<!-- PRERENDER:BLOG:END -->"

CATS = {"performance": "Performance", "security": "Security", "custom": "Custom tools", "platform": "Platform engineering"}
STATUS = {"fixed": ("Fixed", "is-fixed", "ico-check"), "review": ("In review", "is-open", "ico-clock"),
          "open": ("Open", "is-open", "ico-alert")}
EVENTS = {"filed": "Filed", "reported": "Reported", "analysis": "Analysis posted", "pr": "Pull request",
          "fixed": "Fixed", "merged": "Integrated", "published": "Published"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

SPRITE = (
    '<svg class="blog-sprite" aria-hidden="true" focusable="false">'
    '<symbol id="ico-alert" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2Zm1 15h-2v-2h2v2Zm0-4h-2V7h2v6Z"/></symbol>'
    '<symbol id="ico-gear" viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58ZM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6Z"/></symbol>'
    '<symbol id="ico-check" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2Zm-2 15-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9Z"/></symbol>'
    '<symbol id="ico-check-o" viewBox="0 0 24 24"><path d="M16.59 7.58 10 14.17l-3.59-3.58L5 12l5 5 8-8-1.41-1.42ZM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2Zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8Z"/></symbol>'
    '<symbol id="ico-clock" viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2ZM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8Zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7Z"/></symbol>'
    '<symbol id="ico-link" viewBox="0 0 24 24"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7ZM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7Z"/></symbol>'
    '<symbol id="ico-chev-l" viewBox="0 0 24 24"><path d="m14 6-6 6 6 6 1.4-1.4L10.8 12l4.6-4.6L14 6Z"/></symbol>'
    '<symbol id="ico-chev-r" viewBox="0 0 24 24"><path d="m10 6-1.4 1.4 4.6 4.6-4.6 4.6L10 18l6-6-6-6Z"/></symbol>'
    "</svg>")


def ico(name: str, cls: str = "case-ico") -> str:
    return '<svg class="%s" aria-hidden="true" focusable="false"><use href="#%s"/></svg>' % (cls, name)


def nice(d: str) -> str:
    y, m, dd = (int(x) for x in d.split("-"))
    date(y, m, dd)  # valida la fecha
    return "%s %d, %d" % (MONTHS[m - 1], dd, y)


def link(label: str, href: str) -> str:
    ext = href.startswith("http")
    return '<a href="%s"%s>%s</a>' % (href, ' target="_blank" rel="noopener"' if ext else "", label)


def dates_html(events) -> str:
    items = "".join('<li data-ev-date="%s" data-ev="%s">%s%s %s</li>' % (e["d"], e["t"], ico("ico-clock"), EVENTS[e["t"]], nice(e["d"]))
                    for e in events)
    return '<ul class="case-dates">%s</ul>' % items


def case_html(c) -> str:
    st_label, st_cls, st_ico = STATUS[c["status"]]
    cid = "case-" + c["id"]
    metric = ""
    if c.get("metric"):
        m = c["metric"]
        inner = ('<span class="m-before">%s</span> <span class="case-arrow" aria-hidden="true">&rarr;</span> '
                 '<span class="m-after">%s</span>' % (m[0], m[1])) if len(m) == 2 else '<span class="m-before">%s</span>' % m[0]
        metric = '<p class="case-metric">%s</p>' % inner
        if c.get("caption"):
            metric += '<p class="case-caption">%s</p>' % c["caption"]
    facts = "".join('<div><dt>%s%s</dt><dd>%s</dd></div>' % (ico(i), dt, c[k]) for i, dt, k in
                    (("ico-alert", "The problem", "problem"), ("ico-gear", "The work", "work"), ("ico-check-o", "The result", "result")))
    refs = " &middot; ".join(link(label, href) for label, href in c["refs"])
    return ('<article class="case blog-item" id="%s" data-cat="%s" aria-labelledby="%s-t">'
            '<div class="case-top"><p class="case-label">%s</p><p class="case-status %s">%s%s</p></div>'
            '<h3 class="case-title" id="%s-t">%s</h3>%s<dl class="case-facts">%s</dl>%s'
            '<p class="case-refs">%s<span>%s</span></p></article>'
            % (cid, c["cat"], cid, CATS[c["cat"]], st_cls, ico(st_ico, "case-ico case-ico-sm"), st_label,
               cid, c["title"], metric, facts, dates_html(c["events"]), ico("ico-link"), refs))


def post_html(p) -> str:
    return ('<article class="case case--post blog-item" id="%s" aria-labelledby="%s-t">'
            '<div class="case-top"><p class="case-label">Post</p></div>'
            '<h3 class="case-title" id="%s-t"><a href="%s">%s</a></h3>'
            '<p class="case-summary">%s</p>%s'
            '<p class="case-refs"><a href="%s">Read the write-up &rarr;</a></p></article>'
            % (p["id"], p["id"], p["id"], p["href"], p["title"], p["summary"], dates_html(p["events"]), p["href"]))


def calendar_html() -> str:
    labels = "".join('<p data-cal-t="%s">%s</p>' % (k, v) for k, v in EVENTS.items())
    labels += ('<p data-cal-t="one">1 event</p><p data-cal-t="many">events</p>'
               '<p data-cal-t="none">Nothing happened on this day.</p>')
    return ('<section class="blog-sec" id="calendar" aria-labelledby="blogCalTitle">'
            '<div class="blog-sec-head"><h2 id="blogCalTitle">Calendar</h2>'
            '<p>Every date on the cards, by day. Pick a highlighted day to see what happened on it.</p></div>'
            '<div class="cal" data-cal hidden>'
            '<div class="cal-head"><button type="button" class="cal-nav" data-cal-prev aria-label="Previous month">%s</button>'
            '<h3 class="cal-month" data-cal-month aria-live="polite"></h3>'
            '<button type="button" class="cal-nav" data-cal-next aria-label="Next month">%s</button></div>'
            '<table class="cal-grid" data-cal-grid><caption class="sr-only">Days with events</caption><thead></thead><tbody></tbody></table>'
            '<div class="cal-day" data-cal-day aria-live="polite"></div>'
            '<div class="cal-i18n" hidden>%s</div></div>'
            '<noscript><p class="blog-noscript">The calendar needs JavaScript. Every date is also on its card above.</p></noscript>'
            '</section>' % (ico("ico-chev-l", "cal-ico"), ico("ico-chev-r", "cal-ico"), labels))


def build(dry_run: bool = False) -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cases = sorted(data["cases"], key=lambda c: (max(e["d"] for e in c["events"]), c["id"]), reverse=True)
    for c in cases:
        assert c["cat"] in CATS and c["status"] in STATUS, c["id"]
    posts = "".join(post_html(p) for p in data["posts"])
    grid = "".join(case_html(c) for c in cases)
    block = (SPRITE +
             '<section class="blog-sec" aria-labelledby="blogPostsTitle"><div class="blog-sec-head"><h2 id="blogPostsTitle">Posts</h2></div>'
             '<div class="case-grid case-grid--posts">%s</div></section>'
             '<section class="blog-sec" aria-labelledby="blogCasesTitle"><div class="blog-sec-head"><h2 id="blogCasesTitle">Cases</h2>'
             '<p>%d real cases, newest first: the problem, what I did and what happened, each with its public source.</p></div>'
             '<div class="case-grid">%s</div></section>' % (posts, len(cases), grid)
             + calendar_html())
    html = PAGE.read_text(encoding="utf-8")
    a, b = html.find(START), html.find(END)
    if a < 0 or b < a:
        sys.exit("[build_blog] faltan los marcadores PRERENDER:BLOG en %s" % PAGE)
    html = html[:a + len(START)] + block + html[b:]
    if dry_run:
        print("[build_blog] dry-run: %d casos, %d articulos" % (len(cases), len(data["posts"])))
        return
    PAGE.write_text(html, encoding="utf-8", newline="\n")
    print("[build_blog] writing/index.html: %d casos, %d articulos" % (len(cases), len(data["posts"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    build(ap.parse_args().dry_run)


if __name__ == "__main__":
    main()
