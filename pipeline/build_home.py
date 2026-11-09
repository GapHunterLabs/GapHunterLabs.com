#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_home.py -- pre-renderiza las dos piezas de la home (index.html) que
dependen de datos del catalogo:

  * TOOLS: las herramientas destacadas (lista curada a mano en TOOLS,
    con la brecha y la correccion de cada una). Nombre, precio y enlace
    salen de data/catalog-data.json.
  * CATALOG: la linea del catalogo completo, con los totales y la fecha
    del ultimo snapshot que actualiza el CI dos veces al dia.

Rediseno 2026-10-18 ("engineering notebook"): la home dejo de ser un
escaparate del catalogo. Se retiraron el subtitulo con cifras, las 4
metricas del hero, el slider de destacados, la barra de plataformas, las
categorias, la grilla de plugins de pago, los hubs y los facts del metodo,
y con ellos sus marcadores PRERENDER.

Reusa Sources de build_plugin_pages.py -- mismo parseo de
js/catalog-shared.js y mismos helpers de escape.

Uso:
    python pipeline/build_home.py
    python pipeline/build_home.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_plugin_pages import Sources, esc  # noqa: E402
from badges import badge, badge_row, badge_table, price_badge  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HOME_PAGE = ROOT / "index.html"
VSCODE_DATA = ROOT / "data" / "vscode-catalog-data.json"
SPONSORS_DATA = ROOT / "data" / "sponsors.json"
SPONSORS_PAGE = ROOT / "sponsors" / "index.html"
REACH_DATA = ROOT / "data" / "reach.json"
RESEARCH_DATA = ROOT / "data" / "research.json"
PRICING_LABEL = {"FREE": "Free", "FREEMIUM": "Freemium", "PAID": "Paid"}

# (slug, brecha, correccion). Texto en ingles: build_i18n.py lo traduce
# con pipeline/i18n/es.json. Cada linea tiene que poder respaldarse con el
# pitch o la evidencia publicada del plugin.
TOOLS = (
    ("background-readaction-freeze-companion",
     "The freeze pattern that JetBrains&rsquo; Platform Blog names, a background task that reaches a "
     "blocking, non-cancellable read action, had no static check.",
     "An inspection for your plugin&rsquo;s own code. The same check found IDEA-393501 in IntelliJ itself."),
    ("openapi-companion",
     "Reviews of existing OpenAPI plugins report external <code>$ref</code> values that do not resolve, "
     "or editors that freeze the IDE on large specs.",
     "<code>$ref</code> navigation resolved entirely against local files, and a warning on every "
     "<code>$ref</code> that does not resolve."),
    ("ansible-companion",
     "Working with Ansible Vault files in the IDE depended on the <code>ansible-vault</code> command "
     "being installed.",
     "Encrypt and decrypt Ansible Vault (1.1, AES256) directly in the editor."),
)


def sparkline(values, first_date, last_date, w=140, h=28):
    """Polilinea SVG (en linea, sin librerias) de una serie corta de enteros.

    2026-11-08: the label names the real dates of the first and last snapshot. The series is the last 7
    snapshots, and a day without a snapshot made "the last 7 days" untrue."""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = w / (len(values) - 1)
    pts = " ".join("%.0f,%.0f" % (i * step, h - 2 - (v - lo) * (h - 4) / span) for i, v in enumerate(values))
    label = "Total downloads from %s to %s: %s to %s" % (first_date, last_date, format(values[0], ","), format(values[-1], ","))
    return ('<svg class="tw-mt-2 tw-h-7 tw-w-full" viewBox="0 0 %d %d" preserveAspectRatio="none" role="img" '
            'aria-label="%s"><polyline fill="none" stroke="var(--signal)" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round" points="%s"/></svg>' % (w, h, esc(label), pts))


def tile(label, value, sub_html, extra=""):
    return ('<div class="tw-bg-bg tw-p-5"><p class="tw-font-mono tw-text-xs tw-text-faint">%s</p>'
            '<p class="tw-mt-1 tw-text-3xl tw-font-bold tw-text-ink">%s</p>%s'
            '<p class="tw-mt-2 tw-text-xs tw-text-dim">%s</p></div>' % (label, value, extra, sub_html))


def sync_html(data):
    snap = (data.get("generatedAt") or "")[:10]
    return ('<span class="live-dot" aria-hidden="true"></span>'
            '<span>Catalog synced</span> <time datetime="%s">%s</time>' % (snap, snap))


def metrics_html(data, research, vscode_total):
    points = [d for d in data.get("trend7d", []) if "totalDownloads" in d and d.get("date")]
    trend = [d["totalDownloads"] for d in points]
    pr = research["upstreamPullRequests"]
    adv = research["advisoriesClosedUpstream"]
    # 2026-11-08: the figure is the all-time total; the line under it used to read "Last 7 days", as if the total
    # were a weekly count. It now states what the sparkline shows: the gain since the first snapshot of the series.
    if len(trend) >= 2:
        since = points[0]["date"]
        dl_sub = '<b>+%s</b> <span>since</span> <time datetime="%s">%s</time>' % (format(trend[-1] - trend[0], ","), since, since)
        dl_extra = sparkline(trend, since, points[-1]["date"])
    else:
        dl_sub, dl_extra = "<span>All-time total</span>", ""
    tiles = [
        tile("JetBrains Marketplace downloads", format(data["totalDownloads"], ","), dl_sub, dl_extra),
        tile("Tools in the catalog", str(data["totalPlugins"] + vscode_total),
             "<span>%d JetBrains plugins</span> &middot; <span>%d VS Code extensions</span>" % (data["totalPlugins"], vscode_total)),
        tile("Pull requests to IntelliJ", str(pr["total"]),
             "<b>%d</b> <span>integrated</span> &middot; <b>%d</b> <span>open</span>" % (pr["integrated"], pr["open"])),
        tile("Advisories closed upstream", str(adv["count"]),
             "<span>Fixed by the maintainers in</span> <code>reactive-commons-go</code>"),
    ]
    grid = ('<div class="tw-grid tw-grid-cols-2 tw-gap-px tw-overflow-hidden tw-rounded-lg tw-border tw-border-line '
            'tw-bg-line md:tw-grid-cols-4">%s</div>' % "".join(tiles))
    chips = badge_row([
        dict(label="JetBrains Marketplace", icon="jetbrains", variant="dark",
             href="https://plugins.jetbrains.com/vendor/gap-hunter-labs"),
        dict(label="GitHub", icon="github", variant="dark", href="https://github.com/GapHunterLabs"),
        dict(label="VS Code Marketplace", icon="vscode", variant="dark"),
    ])
    # Each source keeps its own date: downloads and tool counts come from the twice-daily sync, the pull requests
    # and advisories from research.json, which is checked by hand.
    asof = research["asOf"]
    snap = (data.get("generatedAt") or "")[:10]
    # Two lines, one label each: a label and its <time> in one element is what build_i18n keys on (a date inside
    # a longer text would change the translation key every day).
    foot = ('<p class="tw-mt-3 tw-font-mono tw-text-xs tw-text-faint"><span>Downloads and tools as of</span> '
            '<time datetime="%s">%s</time></p>'
            '<p class="tw-mt-1 tw-font-mono tw-text-xs tw-text-faint"><span>Pull requests and advisories as of</span> '
            '<time datetime="%s">%s</time></p>' % (snap, snap, asof, asof))
    return grid + '<div class="tw-mt-4">' + chips + "</div>" + foot


# Focus areas: shown in the hero card and as the "Disciplines" row of the stack table.
DISCIPLINES = [dict(label="Static analysis", icon="code", variant="dark"),
               dict(label="Performance", icon="gauge", variant="dark"),
               dict(label="Security research", icon="shield", variant="dark"),
               dict(label="Reliability", icon="layers", variant="dark")]


def focus_html():
    return badge_row(DISCIPLINES)


def stack_html():
    rows = [
        ("Platforms", [dict(label="JetBrains IDEs", icon="jetbrains", variant="dark"),
                       dict(label="IntelliJ IDEA", icon="intellij-idea", variant="dark"),
                       dict(label="VS Code", icon="vscode", variant="brand", hex6="007ACC"),
                       dict(label="Windows", icon="windows", variant="dark"),
                       dict(label="Linux", variant="dark")]),
        ("Languages", [dict(label="Kotlin", icon="kotlin"), dict(label="Java", icon="java", variant="soft"),
                       dict(label="Python", icon="python"),
                       dict(label="TypeScript", variant="brand", hex6="3178C6"),
                       dict(label="Go", icon="go"),
                       dict(label="YAML", variant="dark")]),
        ("Disciplines", DISCIPLINES + [dict(label="Dependency auditing", icon="shield", variant="dark"),
                                       dict(label="Open-source contributions", icon="github", variant="dark")]),
        ("Tooling", [dict(label="Gradle", icon="gradle", variant="soft"), dict(label="JUnit", icon="junit"),
                     dict(label="Git", icon="git"), dict(label="GitHub", icon="github", variant="dark"),
                     dict(label="GitHub Actions", icon="github-actions"),
                     dict(label="Plugin Verifier", variant="dark"),
                     dict(label="Node.js", variant="dark")]),
    ]
    return badge_table("Platforms, languages and tooling", rows, "stackCaption")


# Sponsors: (clave del nivel, titulo del grupo). Platinum/gold/silver llevan logo y enlace; el resto, solo nombre.
SPONSOR_TIERS = (("platinum", "Platinum"), ("gold", "Gold"), ("silver", "Silver"),
                 ("backer", "Backers"), ("supporter", "Supporters"))
HOME_TIERS = ("platinum", "gold")   # el nivel Gold incluye el logo en la home
SPONSOR_OPEN = "The first sponsor spots are open."
SPONSOR_CHIPS = [dict(label="Upstream fixes", icon="git", variant="dark"),
                 dict(label="Free tools kept current", icon="code", variant="dark"),
                 dict(label="Independent research", icon="shield", variant="dark")]


def load_sponsors():
    """Lee data/sponsors.json y valida cada entrada: un error aqui es un logo roto o un nivel mal escrito en produccion."""
    if not SPONSORS_DATA.exists():
        return []
    valid = {k for k, _ in SPONSOR_TIERS}
    rows = json.loads(SPONSORS_DATA.read_text(encoding="utf-8")).get("sponsors", [])
    for r in rows:
        if r.get("tier") not in valid:
            die("sponsors.json: nivel desconocido %r en %r" % (r.get("tier"), r.get("name")))
        if not r.get("name"):
            die("sponsors.json: hay un patrocinador sin nombre")
        if r.get("url") and not str(r["url"]).startswith("https://"):
            die("sponsors.json: la URL de %r tiene que ser https://" % r["name"])
        if r.get("logo") and not (ROOT / str(r["logo"]).lstrip("/")).is_file():
            die("sponsors.json: no existe el logo %s" % r["logo"])
    return rows


def sponsor_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "sponsor"


def sponsor_link(r, inner, cls, where):
    """A linked sponsor. GoatCounter counts the clicks per sponsor and place (aggregate, no personal data) for the
    quarterly note that Gold and Platinum sponsors get."""
    if not r.get("url"):
        return '<span class="%s">%s</span>' % (cls, inner)
    return ('<a class="%s" href="%s" target="_blank" rel="sponsored noopener" data-goatcounter-click="sponsor-%s-%s" '
            'data-goatcounter-title="%s">%s</a>' % (cls, esc(r["url"]), sponsor_slug(r["name"]), where, esc(r["name"]), inner))


def sponsors_html(rows, home):
    """Muro de patrocinadores. Sin patrocinadores muestra la convocatoria (nada inventado)."""
    tiers = [(k, t) for k, t in SPONSOR_TIERS if not home or k in HOME_TIERS]
    where = "home" if home else "page"
    groups = []
    for key, title in tiers:
        mine = [r for r in rows if r["tier"] == key]
        if not mine:
            continue
        if key in ("platinum", "gold", "silver"):
            items = "".join(
                "<li>%s</li>" % sponsor_link(
                    r, ('<img class="sp-logo-img" src="%s" alt="%s" height="%d" loading="lazy" decoding="async">'
                        % (esc(r["logo"]), esc(r["name"]), {"platinum": 56, "gold": 44, "silver": 34}[key]))
                    if r.get("logo") else '<span class="sp-name">%s</span>' % esc(r["name"]), "sp-logo", where)
                for r in mine)
            groups.append('<div class="sp-tier sp-tier-%s"><p class="sp-tier-title">%s</p><ul class="sp-logos">%s</ul></div>'
                          % (key, title, items))
        else:
            items = "".join("<li>%s</li>" % sponsor_link(r, '<span class="sp-name">%s</span>' % esc(r["name"]), "sp-person", where)
                            for r in mine)
            groups.append('<div class="sp-tier sp-tier-%s"><p class="sp-tier-title">%s</p><ul class="sp-names">%s</ul></div>'
                          % (key, title, items))
    if groups:
        return '<div class="sp-wall">%s</div>' % "".join(groups)
    if home:
        slots_pt = "".join(
            '<div class="sp-slot sp-slot--pt" role="img" aria-label="Open Platinum sponsor slot"></div>'
            for _ in range(3))
        slots_gold = "".join(
            '<div class="sp-slot sp-slot--gold" role="img" aria-label="Open Gold sponsor slot"></div>'
            for _ in range(5))
        return ('<div class="sp-slots">'
                '<div class="sp-slots-row"><span class="sp-slots-tier">Platinum</span>%s</div>'
                '<div class="sp-slots-row"><span class="sp-slots-tier">Gold</span>%s</div>'
                '</div><p class="sp-slots-note">%s &mdash; <a href="/sponsors/">see levels</a></p>'
                % (slots_pt, slots_gold, SPONSOR_OPEN))
    return '<p class="sp-empty">%s</p>' % (SPONSOR_OPEN + " Your name or logo could be the first one here.")


# Audience figures: copied by hand from GoatCounter and the LinkedIn page analytics (neither has a public API).
REACH_COUNTS = {"site": ("visits",), "linkedin": ("followers", "impressions", "membersReached")}
REACH_SHARES = {"site": ("countries", "languages"), "linkedin": ("followerProfile", "viewerProfile")}
REACH_STALE_DAYS = 120


def _iso(value, name):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        die("reach.json: %s tiene que ser una fecha AAAA-MM-DD" % name)


def load_reach():
    """Reads data/reach.json. The figures are printed on the sponsors page, so a wrong one is a public error."""
    if not REACH_DATA.exists():
        die("falta data/reach.json (la pagina de patrocinadores imprime esas cifras)")
    raw = json.loads(REACH_DATA.read_text(encoding="utf-8"))
    as_of = _iso(raw.get("asOf"), "asOf")
    for key in ("site", "linkedin"):
        block = raw.get(key)
        if not isinstance(block, dict):
            die("reach.json: falta el bloque %r" % key)
        start, end = _iso(block.get("from"), key + ".from"), _iso(block.get("to"), key + ".to")
        if not start <= end <= as_of:
            die("reach.json: en %r tiene que cumplirse from <= to <= asOf" % key)
        if not block.get("source"):
            die("reach.json: %s.source esta vacio" % key)
        for field in REACH_COUNTS[key]:
            if not isinstance(block.get(field), int) or block[field] <= 0:
                die("reach.json: %s.%s tiene que ser un entero positivo" % (key, field))
        for field in REACH_SHARES[key]:
            items = block.get(field)
            if not items:
                die("reach.json: %s.%s esta vacio" % (key, field))
            for item in items:
                pct = item.get("pct")
                if not item.get("label") or not isinstance(pct, int) or not 0 <= pct <= 100:
                    die("reach.json: %s.%s: cada elemento lleva label y un pct entero de 0 a 100" % (key, field))
    outside = raw["linkedin"].get("outsideNetworkPct")
    if not isinstance(outside, int) or not 0 <= outside <= 100:
        die("reach.json: linkedin.outsideNetworkPct tiene que ser un entero de 0 a 100")
    if (date.today() - as_of).days > REACH_STALE_DAYS:
        print("[build_home] AVISO: data/reach.json es del %s; actualiza las cifras" % as_of)
    return raw


def _share_chips(title, items):
    chips = "".join('<li><span class="sp-person"><span>%s</span> <b>%d%%</b></span></li>' % (esc(i["label"]), i["pct"])
                    for i in items)
    return '<div><p class="sp-tier-title">%s</p><ul class="sp-names">%s</ul></div>' % (title, chips)


def _reach_note(first, inner):
    return '<p class="tw-%s tw-font-mono tw-text-xs tw-text-faint">%s</p>' % ("mt-3" if first else "mt-1", inner)


def _reach_window(label, block, first):
    # Text and data live in separate elements so the Spanish keys never carry a date.
    return _reach_note(first, '<span>%s, from</span> <time datetime="%s">%s</time> <span>to</span> <time datetime="%s">%s</time>'
                       % (label, block["from"], block["from"], block["to"], block["to"]))


def reach_html(reach):
    """The audience a sponsor's name reaches: this site and the LinkedIn page, with the dates each figure covers."""
    site, li = reach["site"], reach["linkedin"]
    days = (date.fromisoformat(site["to"]) - date.fromisoformat(site["from"])).days + 1
    per_week = max(1, round(site["visits"] * 7 / days))
    tiles = [
        tile("LinkedIn followers", format(li["followers"], ","), "<span>On my LinkedIn page</span>"),
        tile("LinkedIn impressions", format(li["impressions"], ","),
             "<b>%d%%</b> <span>from outside my network</span>" % li["outsideNetworkPct"]),
        tile("Members reached", format(li["membersReached"], ","), "<span>Different people who saw my posts</span>"),
        tile("Site visits", format(site["visits"], ","), "<span>About %d a week</span>" % per_week),
    ]
    grid = ('<div class="tw-grid tw-grid-cols-2 tw-gap-px tw-overflow-hidden tw-rounded-lg tw-border tw-border-line '
            'tw-bg-line md:tw-grid-cols-4">%s</div>' % "".join(tiles))
    facts = '<div class="sp-facts">%s</div>' % "".join([
        _share_chips("Where site visits come from", site["countries"]),
        _share_chips("Browser language of site visits", site["languages"]),
        _share_chips("Who follows my LinkedIn page", li["followerProfile"]),
        _share_chips("Who sees my posts on LinkedIn", li["viewerProfile"]),
    ])
    notes = [_reach_window("Site visits: " + site["source"], site, True),
             _reach_window("LinkedIn: " + li["source"], li, False)]
    if site.get("includesOwnVisits"):
        notes.append(_reach_note(False, "<span>The site count includes my own visits.</span>"))
    notes.append(_reach_note(False, "<span>LinkedIn shows only the most common value in each category.</span>"))
    notes.append(_reach_note(False, '<span>Counts as of</span> <time datetime="%s">%s</time>' % (reach["asOf"], reach["asOf"])))
    return grid + facts + "".join(notes)


def die(msg: str) -> "NoReturn":  # noqa: F821
    sys.exit("[build_home] ERROR: " + msg)


def inject(html, start, end, content, label):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if len(pattern.findall(html)) != 1:
        die("marcador %s no encontrado (o duplicado) en index.html" % label)
    return pattern.sub(lambda _m: start + content + end, html, count=1)


def build(dry_run: bool = False) -> None:
    src = Sources()
    html = HOME_PAGE.read_text(encoding="utf-8")
    data = src.data
    by_slug = {p["repo"]: p for p in src.plugins}

    # ---- TOOLS: herramientas curadas -----------------------------------------
    rows = []
    for slug, gap, fix in TOOLS:
        p = by_slug.get(slug)
        if not p:
            die("la herramienta destacada %s ya no esta en el catalogo" % slug)
        pricing = p.get("pricing") or "FREE"
        rows.append(
            '<article class="tool">'
            '<div class="tool-head"><h3 class="tool-name"><a href="/catalog/%s/">%s</a></h3>'
            '<div class="badge-row tool-badges">%s%s</div></div>'
            '<dl class="tool-facts"><div><dt class="is-gap">Gap</dt><dd>%s</dd></div>'
            '<div><dt class="is-fix">Fix</dt><dd>%s</dd></div></dl>'
            '</article>'
            % (esc(slug), esc(p["name"]),
               badge("JetBrains IDEs", icon="jetbrains", variant="dark"),
               price_badge(pricing.lower(), PRICING_LABEL.get(pricing, "Free")), gap, fix)
        )
    tools_html = "".join(rows)

    # ---- CATALOG: totales y fecha del snapshot -------------------------------
    vscode_total = 0
    if VSCODE_DATA.exists():
        vscode_total = json.loads(VSCODE_DATA.read_text(encoding="utf-8")).get("totalExtensions") or 0
    snapshot = (data.get("generatedAt") or "")[:10]
    catalog_line = (
        "%d JetBrains plugins and %d VS Code extensions, each with its own page and a clear price: "
        "free, freemium or paid. Figures are synced twice a day from public JetBrains Marketplace "
        "and GitHub data (last snapshot: %s)." % (data["totalPlugins"], vscode_total, snapshot)
    )

    html = inject(html, "<!-- PRERENDER:TOOLS:START -->", "<!-- PRERENDER:TOOLS:END -->", tools_html, "TOOLS")
    research = json.loads(RESEARCH_DATA.read_text(encoding="utf-8"))
    html = inject(html, "<!-- PRERENDER:SYNC:START -->", "<!-- PRERENDER:SYNC:END -->", sync_html(data), "SYNC")
    html = inject(html, "<!-- PRERENDER:METRICS:START -->", "<!-- PRERENDER:METRICS:END -->",
                  metrics_html(data, research, vscode_total), "METRICS")
    html = inject(html, "<!-- PRERENDER:STACK:START -->", "<!-- PRERENDER:STACK:END -->", stack_html(), "STACK")
    html = inject(html, "<!-- PRERENDER:CATALOG:START -->", "<!-- PRERENDER:CATALOG:END -->", esc(catalog_line), "CATALOG")

    sponsors = load_sponsors()
    html = inject(html, "<!-- PRERENDER:SPONSORS:START -->", "<!-- PRERENDER:SPONSORS:END -->",
                  sponsors_html(sponsors, home=True), "SPONSORS")
    sp_page = None
    if SPONSORS_PAGE.exists():
        sp_page = SPONSORS_PAGE.read_text(encoding="utf-8")
        sp_page = inject(sp_page, "<!-- PRERENDER:SPONSORS:START -->", "<!-- PRERENDER:SPONSORS:END -->",
                         sponsors_html(sponsors, home=False), "SPONSORS (pagina)")
        sp_page = inject(sp_page, "<!-- PRERENDER:METRICS:START -->", "<!-- PRERENDER:METRICS:END -->",
                         metrics_html(data, research, vscode_total), "METRICS (pagina)")
        sp_page = inject(sp_page, "<!-- PRERENDER:REACH:START -->", "<!-- PRERENDER:REACH:END -->",
                         reach_html(load_reach()), "REACH (pagina)")

    if dry_run:
        print("[dry-run] %d herramientas, catalogo: %s -- nada escrito" % (len(rows), catalog_line))
        return

    HOME_PAGE.write_text(html, encoding="utf-8")
    if sp_page is not None:
        SPONSORS_PAGE.write_text(sp_page, encoding="utf-8")
    print("[build_home] index.html: %d herramientas destacadas + linea del catalogo (%s)" % (len(rows), snapshot))


def main():
    ap = argparse.ArgumentParser(description="Pre-renderiza la home (index.html)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    build(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
