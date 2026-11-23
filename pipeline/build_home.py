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
from badges import badge, badge_row, badge_table, icon_svg, price_badge  # noqa: E402
from build_blog import CATS, EVENTS, STATUS, link as case_link, nice  # noqa: E402
import iso_figures  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HOME_PAGE = ROOT / "index.html"
VSCODE_DATA = ROOT / "data" / "vscode-catalog-data.json"
SPONSORS_DATA = ROOT / "data" / "sponsors.json"
SPONSORS_PAGE = ROOT / "sponsors" / "index.html"
REACH_DATA = ROOT / "data" / "reach.json"
RESEARCH_DATA = ROOT / "data" / "research.json"
SERVICES_DATA = ROOT / "data" / "services.json"
CASES_DATA = ROOT / "data" / "blog-cases.json"
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


def tile(label, value, sub_html, extra=""):
    return ('<div class="tw-bg-bg tw-p-5"><p class="tw-font-mono tw-text-xs tw-text-faint">%s</p>'
            '<p class="tw-mt-1 tw-text-3xl tw-font-bold tw-text-ink">%s</p>%s'
            '<p class="tw-mt-2 tw-text-xs tw-text-dim">%s</p></div>' % (label, value, extra, sub_html))


# Figures of the home that build() inlines by name; the catalog figure and the stat glyphs have their own steps.
HOME_FIGURES = ("grid", "hero", "step-find", "step-trace", "step-fix", "thumb-tickets", "thumb-security", "thumb-audits")
STAT_FIGURES = ("stat-downloads", "stat-tools", "stat-prs", "stat-advisories")


def stat_card(figure, value, label, sub_html):
    return ('<div class="nb-stat"><span class="nb-stat-glyph" aria-hidden="true">'
            '<!-- PRERENDER:ISO:%s:START --><!-- PRERENDER:ISO:%s:END --></span>'
            '<p class="nb-stat-value">%s</p><p class="nb-stat-label">%s</p><p class="nb-stat-sub">%s</p></div>'
            % (figure, figure, value, label, sub_html))


def metrics_html(data, research, vscode_total):
    """Key figures (2026-11-23, graphite redesign): four cards with an isometric glyph, the figure, its label and one
    line of detail, then one foot line with the date of each source. The figures and their glyphs are placed by
    inline_stat_figures() once the block is in the page."""
    points = [d for d in data.get("trend7d", []) if "totalDownloads" in d and d.get("date")]
    trend = [d["totalDownloads"] for d in points]
    pr = research["upstreamPullRequests"]
    adv = research["advisoriesClosedUpstream"]
    # The figure is the all-time total; the line under it states the gain since the first snapshot of the series.
    if len(trend) >= 2:
        since = points[0]["date"]
        dl_sub = '<b>+%s</b> <span>since</span> <time datetime="%s">%s</time>' % (format(trend[-1] - trend[0], ","), since, since)
    else:
        dl_sub = "<span>All-time total</span>"
    cards = [
        stat_card("stat-downloads", format(data["totalDownloads"], ","), "JetBrains Marketplace downloads", dl_sub),
        stat_card("stat-tools", str(data["totalPlugins"] + vscode_total), "Tools in the catalog",
                  "<span>%d JetBrains plugins</span> &middot; <span>%d VS Code extensions</span>" % (data["totalPlugins"], vscode_total)),
        stat_card("stat-prs", str(pr["total"]), "Pull requests to IntelliJ",
                  "<b>%d</b> <span>integrated</span> &middot; <b>%d</b> <span>open</span>" % (pr["integrated"], pr["open"])),
        stat_card("stat-advisories", str(adv["count"]), "Advisories closed upstream",
                  "<span>Fixed by the maintainers in</span> <code>reactive-commons-go</code>"),
    ]
    # Each source keeps its own date: downloads and tool counts come from the twice-daily sync, the pull requests
    # and advisories from research.json, which is checked by hand. One label and its <time> per element: that is
    # what build_i18n keys on (a date inside a longer text would change the translation key every day).
    asof = research["asOf"]
    snap = (data.get("generatedAt") or "")[:10]
    foot = ('<div class="nb-stat-foot"><p><span class="live-dot" aria-hidden="true"></span><span>Downloads and tools as of</span> '
            '<time datetime="%s">%s</time></p><p><span>Pull requests and advisories as of</span> '
            '<time datetime="%s">%s</time></p></div>' % (snap, snap, asof, asof))
    return '<div class="nb-stats">%s</div>%s' % ("".join(cards), foot)


FEATURED = ("openapi-companion", "ansible-companion", "dependency-vulnerability-companion",
            "mermaid-companion", "cors-policy-companion", "cert-companion")
PRICE_LABEL = {"FREE": ("Free", "is-free"), "FREEMIUM": ("Freemium", "is-freemium"), "PAID": ("Paid", "is-paid")}


def featured_html(data, featured=FEATURED):
    """The featured plugin cards of the home catalog section: name, downloads and price, all read from the data.
    A featured plugin missing from the data, without downloads, or with an unknown price stops the build."""
    by_repo = {p["repo"]: p for p in data["plugins"]}
    cards = []
    for repo in featured:
        p = by_repo.get(repo)
        if p is None:
            sys.exit("[build_home] ERROR: featured plugin %r is not in data/catalog-data.json" % repo)
        if p.get("pricing") not in PRICE_LABEL:
            sys.exit("[build_home] ERROR: featured plugin %r has an unknown price %r" % (repo, p.get("pricing")))
        if not isinstance(p.get("downloads"), int):
            sys.exit("[build_home] ERROR: featured plugin %r has no download count" % repo)
        label, cls = PRICE_LABEL[p["pricing"]]
        cards.append('<a class="nb-feat" href="/catalog/%s/"><span class="nb-feat-name">%s</span>'
                     '<span class="nb-feat-meta">%s downloads</span><span class="badge badge-status %s">%s</span></a>'
                     % (repo, esc(p["name"]), format(p["downloads"], ","), cls, label))
    return "".join(cards)


# Hand-made pages that state how many plugins are in the catalog: each figure is bound by a comment placed right
# before it (<!--count:jetbrains-->147), rewritten here from the data. build_i18n drops comments before it looks a
# text up, so the translation keys do not change.
COUNT_PAGES = ("custom-plugins-inspections/index.html", "plugin-performance-audit/index.html", "plugin-updates/index.html")
COUNT_RE = re.compile(r"<!--count:([a-z]+)-->(\d[\d,]*)")


def bind_counts(text, values, label):
    def rep(m):
        if m.group(1) not in values:
            sys.exit("[build_home] ERROR: %s: unknown count %r (known: %s)" % (label, m.group(1), ", ".join(sorted(values))))
        return "<!--count:%s-->%s" % (m.group(1), values[m.group(1)])
    new, n = COUNT_RE.subn(rep, text)
    if n == 0:
        sys.exit("[build_home] ERROR: %s has no <!--count:...--> binding left" % label)
    return new


def bind_count_pages(data, vscode_total, dry_run=False):
    values = {"jetbrains": str(data["totalPlugins"]), "vscode": str(vscode_total),
              "tools": str(data["totalPlugins"] + vscode_total)}
    for rel in COUNT_PAGES:
        path = ROOT / rel
        raw = path.read_bytes().decode("utf-8")
        new = bind_counts(raw, values, rel)
        if new != raw and not dry_run:
            path.write_bytes(new.encode("utf-8"))


def inline_stat_figures(html, where):
    for figure in STAT_FIGURES:
        html = iso_figures.inject_or_die(html, figure, where, "build_home")
    return html


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
                       dict(label="Atlassian Forge", icon="atlassian", variant="dark"),
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


# Audience figures: copied by hand from GoatCounter and the LinkedIn profile analytics (neither has a public API).
REACH_COUNTS = {"site": ("visits",), "linkedin": ("followers", "impressions", "membersReached")}
REACH_SHARES = {"site": ("countries", "languages"), "linkedin": ("followerProfile", "viewerProfile")}
REACH_STALE_DAYS = 120
# The 'Track performance' box of LinkedIn: short windows that end on asOf, never mixed with the long window above.
REACH_RECENT_COUNTS = ("postImpressions7d", "profileViewers90d", "connections", "searchAppearances")


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _positive_int(value):
    return _int(value) and value > 0


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
    recent = raw["linkedin"].get("recent")
    if not isinstance(recent, dict):
        die("reach.json: falta el bloque linkedin.recent")
    for field in REACH_RECENT_COUNTS:
        if not _positive_int(recent.get(field)):
            die("reach.json: linkedin.recent.%s tiene que ser un entero positivo" % field)
    change = recent.get("postImpressions7dChangePct")
    if not _int(change) or change < -100:
        die("reach.json: linkedin.recent.postImpressions7dChangePct tiene que ser un entero de -100 en adelante")
    s_from, s_to = _iso(recent.get("searchFrom"), "linkedin.recent.searchFrom"), _iso(recent.get("searchTo"), "linkedin.recent.searchTo")
    if not s_from <= s_to <= as_of:
        die("reach.json: en linkedin.recent tiene que cumplirse searchFrom <= searchTo <= asOf")
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
    """The audience a sponsor's name reaches: this site and the LinkedIn profile, with the dates each figure covers."""
    site, li = reach["site"], reach["linkedin"]
    days = (date.fromisoformat(site["to"]) - date.fromisoformat(site["from"])).days + 1
    per_week = max(1, round(site["visits"] * 7 / days))
    tiles = [
        tile("LinkedIn followers", format(li["followers"], ","), "<span>On my LinkedIn profile</span>"),
        tile("LinkedIn impressions", format(li["impressions"], ","),
             "<b>%d%%</b> <span>from outside my network</span>" % li["outsideNetworkPct"]),
        tile("Members reached", format(li["membersReached"], ","), "<span>Different people who saw my posts</span>"),
        tile("Site visits", format(site["visits"], ","), "<span>About %d a week</span>" % per_week),
    ]
    recent = li["recent"]
    change = recent["postImpressions7dChangePct"]
    tiles += [
        tile("Post impressions, last 7 days", format(recent["postImpressions7d"], ","),
             "<b>%s%d%%</b> <span>vs. the 7 days before</span>" % ("+" if change > 0 else "", change)),
        tile("Profile viewers", format(recent["profileViewers90d"], ","), "<span>In the last 90 days</span>"),
        tile("LinkedIn connections", format(recent["connections"], ","), "<span>People in my network</span>"),
        tile("Search appearances", format(recent["searchAppearances"], ","),
             '<span>From</span> <time datetime="%s">%s</time> <span>to</span> <time datetime="%s">%s</time>'
             % (recent["searchFrom"], recent["searchFrom"], recent["searchTo"], recent["searchTo"])),
    ]
    grid = ('<div class="tw-grid tw-grid-cols-2 tw-gap-px tw-overflow-hidden tw-rounded-lg tw-border tw-border-line '
            'tw-bg-line md:tw-grid-cols-4">%s</div>' % "".join(tiles))
    facts = '<div class="sp-facts">%s</div>' % "".join([
        _share_chips("Where site visits come from", site["countries"]),
        _share_chips("Browser language of site visits", site["languages"]),
        _share_chips("Who follows my LinkedIn profile", li["followerProfile"]),
        _share_chips("Who sees my posts on LinkedIn", li["viewerProfile"]),
    ])
    notes = [_reach_window("Site visits: " + site["source"], site, True),
             _reach_window("LinkedIn: " + li["source"], li, False)]
    if site.get("includesOwnVisits"):
        notes.append(_reach_note(False, "<span>The site count includes my own visits.</span>"))
    notes.append(_reach_note(False, "<span>LinkedIn shows only the most common value in each category.</span>"))
    notes.append(_reach_note(False, "<span>LinkedIn followers and connections are totals on the date below; the 7- and 90-day windows end on it.</span>"))
    notes.append(_reach_note(False, '<span>Counts as of</span> <time datetime="%s">%s</time>' % (reach["asOf"], reach["asOf"])))
    return grid + facts + "".join(notes)


# ---- Hero: the four services and one real case -------------------------------------------------------------------
# Service tiles: name, starting price and delivery time come from data/services.json (the same figures the service
# pages print). The icon is the only thing chosen here.
SERVICE_ICONS = {"audit": "gauge", "updates": "layers", "depsec": "shield", "custom": "code"}


def service_tiles_html(services):
    if len(services) != 4:
        die("services.json: the hero has room for exactly 4 services, found %d" % len(services))
    tiles = []
    for s in services:
        if s.get("key") not in SERVICE_ICONS:
            die("services.json: no hero icon for the service %r" % s.get("key"))
        priced = [t for t in s.get("tiers", []) if isinstance(t.get("usd"), int) and t["usd"] > 0]
        if not priced or not s.get("shortName") or not str(s.get("path", "")).startswith("/"):
            die("services.json: %r needs a shortName, a path and a priced tier" % s.get("key"))
        first = min(priced, key=lambda t: t["usd"])
        # The <!--svc:...--> comments bind each figure to data/services.json; build_services.py checks them.
        terms = "From USD <!--svc:%s.%s.usd-->%s" % (s["key"], first["id"], format(first["usd"], ","))
        if isinstance(first.get("days"), int) and first["days"] > 0:
            terms += " &middot; <!--svc:%s.%s.days-->%d business days" % (s["key"], first["id"], first["days"])
        tiles.append('<li><a class="nb-svc-tile" href="%s" data-goatcounter-click="cta-hero-svc-%s">%s'
                     '<p class="nb-svc-name">%s</p><p class="nb-svc-sub">%s</p></a></li>'
                     % (esc(s["path"]), s["key"], icon_svg(SERVICE_ICONS[s["key"]]), esc(s["shortName"]), terms))
    return "".join(tiles)


# The case in the hero card: one real case from data/blog-cases.json, shown with its own figures, dates and links.
HERO_CASE = "reactive-commons-go-5"
CASE_SERVICE = {"security": ("/dependency-security-review/", "Dependency and CI/CD security review"),
                "performance": ("/plugin-performance-audit/", "Plugin performance audit"),
                "custom": ("/custom-plugins-inspections/", "Custom plugins and inspections"),
                "platform": ("/services/", "All services")}
CASE_FIELDS = ("title", "problem", "work", "result", "events", "refs", "cat", "status")


def _ico(name, cls="nb-ico"):
    return '<svg class="%s" aria-hidden="true" focusable="false"><use href="#%s"/></svg>' % (cls, name)


def hero_case_html(cases, case_id=HERO_CASE):
    found = [c for c in cases if c.get("id") == case_id]
    if len(found) != 1:
        die("blog-cases.json: the hero case %r appears %d times" % (case_id, len(found)))
    c = found[0]
    missing = [k for k in CASE_FIELDS if not c.get(k)]
    if missing:
        die("blog-cases.json: the hero case %r has no %s" % (case_id, ", ".join(missing)))
    if c["cat"] not in CATS or c["status"] not in STATUS:
        die("blog-cases.json: the hero case %r has an unknown category or status" % case_id)
    for ref in c["refs"]:
        if len(ref) != 2 or not re.match(r'^(https://|/)[^\s"<>]*$', str(ref[1])) or "<" in str(ref[0]):
            die("blog-cases.json: the hero case %r has a source that is not an https:// or site link" % case_id)
    st_label, st_cls, _ = STATUS[c["status"]]
    metric = ""
    m = c.get("metric") or []
    if len(m) == 2:
        metric = ('<p class="nb-panel-metric"><span class="m-before">%s</span> <span class="nb-arrow" aria-hidden="true">'
                  '&rarr;</span> <span class="m-after">%s</span></p>' % (m[0], m[1]))
    elif len(m) == 1:
        metric = '<p class="nb-panel-metric"><span class="m-before">%s</span></p>' % m[0]
    if metric and c.get("caption"):
        metric += '<p class="nb-panel-caption">%s</p>' % c["caption"]
    facts = "".join('<div>%s<dt>%s</dt><dd>%s</dd></div>' % (_ico(i), dt, c[k]) for i, dt, k in
                    (("ico-alert", "The problem", "problem"), ("ico-gear", "The work", "work"),
                     ("ico-check", "The result", "result")))
    # Same wording as the Blog cards ("Fixed Oct 7, 2026"), so both pages share one translation.
    dates = "".join('<li data-ev-date="%s">%s%s %s</li>' % (e["d"], _ico("ico-clock"), EVENTS[e["t"]], nice(e["d"]))
                    for e in c["events"])
    refs = " &middot; ".join(case_link(label, href) for label, href in c["refs"])
    svc_href, svc_label = CASE_SERVICE[c["cat"]]
    return ('<div class="nb-case"><div class="nb-panel-top"><p class="nb-panel-label">Real case &middot; %s</p>'
            '<p class="nb-panel-status %s">%s</p></div>'
            '<div class="nb-case-head"><div class="nb-panel-hero">%s</div>'
            '<figure class="nb-hero-face"><img class="nb-avatar" src="/assets/img/joel-diaz.jpg" alt="Joel Díaz, '
            'founder of Gap Hunter Labs" width="104" height="104" loading="eager" decoding="async" fetchpriority="high">'
            '<figcaption>Joel Díaz</figcaption></figure></div>'
            '<h2 class="nb-case-title" id="heroCaseTitle">%s</h2>'
            '<dl class="nb-panel-facts">%s</dl><ul class="nb-panel-meta">%s</ul>'
            '<p class="nb-panel-ref">%s<span>%s</span></p>'
            '<a class="nb-panel-svc" href="%s" data-goatcounter-click="cta-hero-card-%s">%s &rarr;</a></div>'
            % (CATS[c["cat"]], st_cls, st_label, metric, c["title"], facts, dates, _ico("ico-link"), refs,
               svc_href, c["cat"], svc_label))


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
        "free, freemium or paid." % (data["totalPlugins"], vscode_total)
    )

    html = inject(html, "<!-- PRERENDER:TOOLS:START -->", "<!-- PRERENDER:TOOLS:END -->", tools_html, "TOOLS")
    services = json.loads(SERVICES_DATA.read_text(encoding="utf-8"))["services"]
    html = inject(html, "<!-- PRERENDER:SVCTILES:START -->", "<!-- PRERENDER:SVCTILES:END -->",
                  service_tiles_html(services), "SVCTILES")
    cases = json.loads(CASES_DATA.read_text(encoding="utf-8"))["cases"]
    html = inject(html, "<!-- PRERENDER:HEROCASE:START -->", "<!-- PRERENDER:HEROCASE:END -->",
                  hero_case_html(cases), "HEROCASE")
    for figure in HOME_FIGURES:
        html = iso_figures.inject_or_die(html, figure, "index.html", "build_home")
    research = json.loads(RESEARCH_DATA.read_text(encoding="utf-8"))
    html = inject(html, "<!-- PRERENDER:METRICS:START -->", "<!-- PRERENDER:METRICS:END -->",
                  metrics_html(data, research, vscode_total), "METRICS")
    html = inline_stat_figures(html, "index.html")
    html = inject(html, "<!-- PRERENDER:STACK:START -->", "<!-- PRERENDER:STACK:END -->", stack_html(), "STACK")
    html = inject(html, "<!-- PRERENDER:CATALOG:START -->", "<!-- PRERENDER:CATALOG:END -->", esc(catalog_line), "CATALOG")
    # Every number of the catalog section comes from the data, so the twice-daily cron (regenerate.py) keeps it
    # current: the title, the "All n tools" link and the featured cards (name, downloads, price).
    total_tools = data["totalPlugins"] + vscode_total
    html = inject(html, "<!-- PRERENDER:CATTITLE:START -->", "<!-- PRERENDER:CATTITLE:END -->",
                  "%d engineering tools,<br>one place" % total_tools, "CATTITLE")
    html = inject(html, "<!-- PRERENDER:CATALL:START -->", "<!-- PRERENDER:CATALL:END -->",
                  "All %d tools &rarr;" % total_tools, "CATALL")
    html = inject(html, "<!-- PRERENDER:CATFEATURED:START -->", "<!-- PRERENDER:CATFEATURED:END -->",
                  featured_html(data), "CATFEATURED")
    html = iso_figures.inject_or_die(html, "catalog", "index.html", "build_home")
    bind_count_pages(data, vscode_total, dry_run)

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
        sp_page = inline_stat_figures(sp_page, "sponsors/index.html")
        sp_page = inject(sp_page, "<!-- PRERENDER:REACH:START -->", "<!-- PRERENDER:REACH:END -->",
                         reach_html(load_reach()), "REACH (pagina)")
        sp_page = iso_figures.inject_or_die(sp_page, "sponsors", "sponsors/index.html", "build_home")

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
