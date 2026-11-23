#!/usr/bin/env python3
"""build_evidence.py -- pre-render the evidence hub (/engineering-evidence/).

Writes four blocks of engineering-evidence/index.html:
  * EEFEATURED: the latest case of each area (static analysis, JetBrains Platform tickets, open-source security reports,
    third-party plugin audits), with its isometric thumbnail, chips, context and a link to the public source;
  * EESECTIONS: one section per area with every case of that area, newest first, and a link to the area page;
  * EECOUNTS: what the four area pages hold, counted from those pages (never typed by hand);
  * the hero figure and the four thumbnails (PRERENDER:ISO markers, see iso_figures.py).

Cases come from data/blog-cases.json, the same file as the Blog. A case is shown only when it has every field the card
prints (title, context, a dated event and a public source); a case without them is left out, never filled in.
The text is English; build_i18n.py translates it with pipeline/i18n/es.json.

    python pipeline/build_evidence.py
    python pipeline/build_evidence.py --dry-run
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_blog import CATS, EVENTS, nice  # noqa: E402
import iso_figures  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "blog-cases.json"
HUB = ROOT / "engineering-evidence" / "index.html"
EE = ROOT / "engineering-evidence"

# (key, title, one line, page, link label, thumbnail figure). The order is the order on the page.
AREAS = (
    ("analysis", "Static analysis", "Inspections I built or proposed for IntelliJ, and the bugs they found in real code.",
     "/engineering-evidence/case-studies/", "Plugin case studies", "thumb-analysis"),
    ("tickets", "JetBrains Platform tickets", "Bugs in JetBrains&rsquo; own code, traced to the cause and measured, with "
     "the fix I proposed.", "/engineering-evidence/jetbrains-platform-tickets/", "All JetBrains Platform tickets", "thumb-tickets"),
    ("security", "Open-source security reports", "Vulnerable dependencies reported to maintainers, each advisory checked "
     "against OSV for the exact pinned version.", "/engineering-evidence/open-source-security-reports/",
     "All security reports", "thumb-security"),
    ("audits", "Third-party plugin audits", "Findings in other vendors&rsquo; plugins, traced from a public error report "
     "and fixed by their maintainers.", "/engineering-evidence/third-party-plugin-audits/", "All third-party audits",
     "thumb-audits"),
)
STATUS = {"fixed": ("Fixed", "is-fixed"), "review": ("In review", "is-progress"), "open": ("Open", "is-open")}
REQUIRED = ("id", "title", "problem", "status", "cat", "events", "refs")


def die(msg: str) -> "NoReturn":  # noqa: F821
    sys.exit("[build_evidence] ERROR: " + msg)


def area_of(case) -> str:
    """Which area page a case belongs to, from its category and its public sources."""
    if case["cat"] == "security":
        return "security"
    if case["cat"] == "custom":
        return "analysis"
    hosts = {urlparse(href).netloc for _, href in case["refs"] if href.startswith("http")}
    if "youtrack.jetbrains.com" in hosts:
        return "tickets"
    return "audits"


def complete(case) -> bool:
    """True when the card has real data for every field it prints."""
    if any(not case.get(k) for k in REQUIRED):
        return False
    if case["cat"] not in CATS or case["status"] not in STATUS:
        return False
    if not all(isinstance(e, dict) and e.get("t") in EVENTS and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e.get("d", "")))
               for e in case["events"]):
        return False
    return any(len(r) == 2 and str(r[1]).startswith("https://") for r in case["refs"])


def source(case):
    """The first public source: the link behind "View case"."""
    return next(href for _, href in case["refs"] if str(href).startswith("https://"))


def ident(href: str) -> str:
    """A short technical identifier for the source: the YouTrack id, or repo#number on GitHub."""
    u = urlparse(href)
    parts = [p for p in u.path.split("/") if p]
    if u.netloc == "youtrack.jetbrains.com" and len(parts) >= 2 and parts[0] == "issue":
        return parts[1]
    if u.netloc == "github.com" and len(parts) >= 4 and parts[2] in ("issues", "pull"):
        return "%s#%s" % (parts[1], parts[3])
    if u.netloc == "github.com" and len(parts) >= 2:
        return parts[1]
    return u.netloc


def last_event(case):
    return max(case["events"], key=lambda e: e["d"])


def esc_attr(s: str) -> str:
    return htmlmod.escape(str(s), quote=True)


def tech_id(case) -> str:
    """The identifier chip, escaped: it is taken from a URL in the data file."""
    return htmlmod.escape(ident(source(case)), quote=True)


def status_badge(case) -> str:
    label, cls = STATUS[case["status"]]
    return '<span class="badge badge-status %s">%s</span>' % (cls, label)


CLOCK = ('<svg class="ee-ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M11.99 2C6.47 2 2 6.48 2 '
         '12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2ZM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 '
         '8-8 8Zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7Z"/></svg>')


def when(case) -> str:
    # Same wording as the Blog cards ("Fixed Oct 7, 2026"), so both pages share one translation.
    e = last_event(case)
    return '<li data-ev-date="%s">%s%s %s</li>' % (e["d"], CLOCK, EVENTS[e["t"]], nice(e["d"]))


def featured_html(by_area) -> str:
    cards = []
    for key, title, _line, _page, _label, thumb in AREAS:
        cases = by_area[key]
        if not cases:
            continue
        c = cases[0]
        cid = "ee-f-" + c["id"]
        cards.append(
            '<article class="ee-case" aria-labelledby="%s">'
            '<div class="ee-thumb"><!-- PRERENDER:ISO:%s:START --><!-- PRERENDER:ISO:%s:END --></div>'
            '<div class="ee-case-body">'
            '<ul class="ee-chips"><li class="ee-chip">%s</li><li class="ee-chip ee-chip-tech"><span class="ticket-id">%s</span></li>'
            '<li>%s</li></ul>'
            '<h3 id="%s">%s</h3><p class="ee-context">%s</p>'
            '<ul class="ee-case-meta">%s<li>%s</li></ul>'
            '<a class="ee-view" href="%s" target="_blank" rel="noopener"><span class="ee-view-label">View case</span></a>'
            '</div></article>'
            % (cid, thumb, thumb, title, tech_id(c), status_badge(c), cid, c["title"], c["problem"], when(c),
               CATS[c["cat"]], esc_attr(source(c))))
    return "".join(cards)


def sections_html(by_area) -> str:
    out = []
    for key, title, line, page, label, _thumb in AREAS:
        cases = by_area[key]
        if not cases:
            continue
        rows = "".join(
            '<li class="ee-row" data-date="%s"><p class="ee-row-title">%s</p>'
            '<ul class="ee-row-meta"><li>%s</li><li class="ee-chip ee-chip-tech"><span class="ticket-id">%s</span></li>%s'
            '<li><a href="%s" target="_blank" rel="noopener"><span class="ee-view-label">Source</span></a></li></ul></li>'
            % (last_event(c)["d"], c["title"], status_badge(c), tech_id(c), when(c), esc_attr(source(c)))
            for c in cases)
        out.append(
            '<section class="ee-sec" id="ee-%s" aria-labelledby="ee-%s-t">'
            '<div class="ee-sec-head"><h2 id="ee-%s-t">%s</h2><p>%s</p></div>'
            '<ol class="ee-rows" data-sortable>%s</ol>'
            '<p class="ee-sec-more"><a href="%s">%s</a></p></section>'
            % (key, key, key, title, line, rows, page, label))
    return "".join(out)


def _main_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<main\b.*?</main>", text, re.S)
    if not m:
        die("no <main> in %s" % path.relative_to(ROOT))
    return m.group(0)


def counts() -> dict:
    """What each area page holds, counted from its HTML."""
    studies = len(re.findall(r'<article class="identity-card identity-case"', _main_of(EE / "case-studies" / "index.html")))
    tickets_main = _main_of(EE / "jetbrains-platform-tickets" / "index.html")
    parts = re.split(r"<h2\b[^>]*>(.*?)</h2>", tickets_main, flags=re.S)
    per_heading = {re.sub(r"<[^>]+>", "", parts[i]).strip(): len(re.findall(r'<article class="ticket-card"', parts[i + 1]))
                   for i in range(1, len(parts) - 1, 2)}
    need = ("Filed directly", "Fixes contributed", "Analysis on existing tickets")
    missing = [h for h in need if h not in per_heading]
    if missing:
        die("the JetBrains tickets page has no heading %s" % ", ".join(missing))
    reports = len(re.findall(r'<article class="ticket-card"', _main_of(EE / "open-source-security-reports" / "index.html")))
    audits = len(re.findall(r'<article class="ticket-card"', _main_of(EE / "third-party-plugin-audits" / "index.html")))
    return {"studies": studies, "filed": per_heading[need[0]], "prs": per_heading[need[1]],
            "analyses": per_heading[need[2]], "reports": reports, "audits": audits}


def counts_html(n: dict) -> str:
    def row(num, one, many, href):
        return '<li><a href="%s"><b>%d</b> <span>%s</span></a></li>' % (href, num, one if num == 1 else many)
    rows = [
        row(n["studies"], "plugin case study", "plugin case studies", "/engineering-evidence/case-studies/"),
        row(n["filed"], "ticket filed with JetBrains", "tickets filed with JetBrains", "/engineering-evidence/jetbrains-platform-tickets/"),
        row(n["prs"], "fix contributed to IntelliJ", "fixes contributed to IntelliJ", "/engineering-evidence/jetbrains-platform-tickets/"),
        row(n["analyses"], "analysis on an existing ticket", "analyses on existing tickets", "/engineering-evidence/jetbrains-platform-tickets/"),
        row(n["reports"], "open-source security report", "open-source security reports", "/engineering-evidence/open-source-security-reports/"),
        row(n["audits"], "third-party plugin audit", "third-party plugin audits", "/engineering-evidence/third-party-plugin-audits/"),
    ]
    return "".join(r for r, k in zip(rows, ("studies", "filed", "prs", "analyses", "reports", "audits")) if n[k] > 0)


def inject(html: str, name: str, content: str) -> str:
    start, end = "<!-- PRERENDER:%s:START -->" % name, "<!-- PRERENDER:%s:END -->" % name
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if len(pattern.findall(html)) != 1:
        die("the PRERENDER:%s markers must appear exactly once in engineering-evidence/index.html" % name)
    return pattern.sub(lambda _m: start + content + end, html, count=1)


def group(cases):
    by_area = {key: [] for key, *_ in AREAS}
    for c in cases:
        if complete(c):
            by_area[area_of(c)].append(c)
    for key in by_area:
        by_area[key].sort(key=lambda c: (last_event(c)["d"], c["id"]), reverse=True)
    return by_area


def build(dry_run: bool = False) -> None:
    cases = json.loads(DATA.read_text(encoding="utf-8"))["cases"]
    by_area = group(cases)
    shown = sum(len(v) for v in by_area.values())
    html = HUB.read_text(encoding="utf-8")
    html = inject(html, "EEFEATURED", featured_html(by_area))
    html = inject(html, "EESECTIONS", sections_html(by_area))
    html = inject(html, "EECOUNTS", counts_html(counts()))
    html = iso_figures.inject_or_die(html, "evidence", "engineering-evidence/index.html", "build_evidence")
    for key, *_rest, thumb in AREAS:
        if by_area[key]:
            html = iso_figures.inject_or_die(html, thumb, "engineering-evidence/index.html", "build_evidence")
    if dry_run:
        print("[build_evidence] dry-run: %d of %d cases shown" % (shown, len(cases)))
        return
    # Keep the line endings the checkout already has (CRLF on Windows with autocrlf, LF elsewhere): a rebuild that
    # changes nothing but the line endings would make regenerate.py --check report the page as changed.
    newline = "\r\n" if b"\r\n" in HUB.read_bytes() else "\n"
    HUB.write_text(html, encoding="utf-8", newline=newline)
    print("[build_evidence] engineering-evidence/index.html: %d of %d cases, %s"
          % (shown, len(cases), ", ".join("%s %d" % (k, len(v)) for k, v in by_area.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    build(ap.parse_args().dry_run)


if __name__ == "__main__":
    main()
