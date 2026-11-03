#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_catalog_grid.py -- Fase 2 del SuperPlan de SEO: pre-renderiza
/catalog/'s propia grilla (Field) y tabla, en vez de dejar que el
navegador las pinte tras un fetch de data/catalog-data.json.

Escribe HTML real -- 146 <a class="plugin-card" href="/catalog/<repo>/">
y 146 <tr> de tabla, cada uno con sus data-* -- entre los marcadores
PRERENDER:* que pipeline/build_plugin_pages.py's Shell NO toca (viven
dentro de <main class="wrap">, que ese script reemplaza entero al
generar cada ficha; los dos scripts son independientes entre si).

Con esto, catalog/index.html deja de necesitar JS para pintar su
contenido principal: el script inline que queda en esa pagina solo
oculta (hidden)/reordena (appendChild) nodos que YA existen -- nunca
construye HTML ni hace fetch. Ver el propio <script> de la pagina para
el detalle de esa hidratacion.

Reusa Sources/PluginRenderer de build_plugin_pages.py (mismo parseo de
js/catalog-shared.js, mismos helpers de escape/color/icono) -- ningun
dato ni mapa se mantiene por duplicado.

Uso:
    python pipeline/build_catalog_grid.py
    python pipeline/build_catalog_grid.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_plugin_pages import Sources, PluginRenderer, esc, thousands, die, plain_text, pitch_text  # noqa: E402
import json  # noqa: E402

PRICE_LABEL = {"FREE": "Free", "FREEMIUM": "Freemium", "PAID": "Paid"}
VS_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/></svg>')


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PAGE = ROOT / "catalog" / "index.html"


def marker_span(html, start, end, label):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if len(pattern.findall(html)) != 1:
        die("marcador %s no encontrado (o duplicado) en catalog/index.html" % label)
    return pattern


def inject(html, start, end, content, label):
    pattern = marker_span(html, start, end, label)
    return pattern.sub(lambda _m: start + content + end, html, count=1)


def plugin_count_text(n: int) -> str:
    return "1 plugin" if n == 1 else "%d plugins" % n


def card_html(p, renderer: PluginRenderer, src: Sources) -> str:
    is_pending = p.get("downloads") is None
    cat = src.cat_by_key.get(p["categoryKey"], src.cat_by_key["other"])
    color = src.cat_var[cat["key"]]
    pr_cls, pr_text = renderer.pricing_label(p.get("pricing"), is_pending)
    search = (p["name"] + " " + (p.get("niche") or "") + " " + p["repo"]).lower()

    attrs = [
        'data-repo="%s"' % esc(p["repo"]),
        'data-cat="%s"' % esc(p["categoryKey"]),
        'data-pricing="%s"' % esc(p.get("pricing") or ""),
        'data-name="%s"' % esc(p["name"].lower()),
        'data-search="%s"' % esc(search),
    ]
    if is_pending:
        attrs.append('data-pending="1"')
    else:
        attrs.append('data-downloads="%d"' % p["downloads"])
    if p.get("reviews") is not None:
        attrs.append('data-reviews="%d"' % p["reviews"])
    if p.get("rating") is not None:
        attrs.append('data-rating="%s"' % p["rating"])
    if p.get("stars") is not None:
        attrs.append('data-stars="%d"' % p["stars"])
    if p.get("firstPublished"):
        attrs.append('data-firstpublished="%s"' % esc(p["firstPublished"]))

    price_badge = ('<span class="price-badge price-pending">Pending</span>' if is_pending else
                   '<span class="price-badge price-%s">%s</span>'
                   % ((p.get("pricing") or "FREE").lower(), PRICE_LABEL.get(p.get("pricing"), esc(pr_text))))
    downloads = ("Pending moderation" if is_pending else
                 '<span class="dl-icon">%s</span><span class="card-dl">%s</span> downloads'
                 % (src.icons["downloads"], thousands(p["downloads"])))
    # No aria-label: the card's visible text (name, niche, pitch, downloads,
    # "Details") is the accessible name, so it satisfies WCAG 2.5.3 (Label in
    # Name). A short aria-label here would drop most of that visible text and
    # axe flags the mismatch (label-content-name-mismatch).
    return (
        '<a class="plugin-card" href="/catalog/%s/" %s>'
        '<div class="card-header">'
        '<span class="card-cat" style="--cat:%s" title="%s" aria-hidden="true">%s</span>%s</div>'
        '<div class="card-top"><div class="card-name">%s</div><div class="card-niche">%s</div></div>'
        '<p class="card-pitch">%s</p>'
        '<div class="card-metrics"><span class="card-dl-wrap">%s</span><span class="card-go">Details</span></div></a>'
    ) % (esc(p["repo"]), " ".join(attrs), color, esc(cat["label"]),
         renderer.cat_icon_html(p["categoryKey"]), price_badge, esc(p["name"]), esc(p.get("niche")),
         esc(pitch_text(p.get("pitch")) or ""), downloads)


def table_row_html(p, renderer: PluginRenderer, src: Sources) -> str:
    is_pending = p.get("downloads") is None
    pr_cls, pr_text = renderer.pricing_label(p.get("pricing"), is_pending)
    search = (p["name"] + " " + (p.get("niche") or "") + " " + p["repo"]).lower()

    attrs = [
        'data-repo="%s"' % esc(p["repo"]),
        'data-cat="%s"' % esc(p["categoryKey"]),
        'data-pricing="%s"' % esc(p.get("pricing") or ""),
        'data-name="%s"' % esc(p["name"].lower()),
        'data-search="%s"' % esc(search),
    ]
    if is_pending:
        attrs.append('data-pending="1"')
    else:
        attrs.append('data-downloads="%d"' % p["downloads"])
    if p.get("reviews") is not None:
        attrs.append('data-reviews="%d"' % p["reviews"])
    if p.get("rating") is not None:
        attrs.append('data-rating="%s"' % p["rating"])
    if p.get("stars") is not None:
        attrs.append('data-stars="%d"' % p["stars"])
    if p.get("firstPublished"):
        attrs.append('data-firstpublished="%s"' % esc(p["firstPublished"]))

    dl_cell = "—" if is_pending else (thousands(p["downloads"]) + renderer.growth_markup(p))
    return (
        '<tr class="row" %s>'
        '<td class="name-cell"><a href="/catalog/%s/"><div class="plugin-name">%s</div>'
        '<div class="niche">%s</div></a></td>'
        '<td class="num-cell" data-label="Downloads">%s</td>'
        '<td class="num-cell tbl-optional" data-label="Reviews">%s</td>'
        '<td class="num-cell tbl-optional" data-label="Rating">%s</td>'
        '<td class="num-cell" data-label="GitHub ★">%s</td>'
        '<td data-label="Pricing"><span class="chip %s">%s</span></td>'
        '<td class="num-cell" data-label="Published" style="text-align:left">%s</td>'
        '</tr>'
    ) % (" ".join(attrs), esc(p["repo"]), esc(p["name"]), esc(p.get("niche")), dl_cell,
         "—" if p.get("reviews") is None else p["reviews"],
         "—" if p.get("rating") is None else ("%.2f" % p["rating"]),
         "—" if p.get("stars") is None else p["stars"],
         pr_cls, esc(pr_text), esc(p.get("firstPublished") or "—"))


def sort_default(plugins):
    """Mismo default que el JS: sortKey='downloads', sortDir=-1 (desc),
    ausentes siempre al final sin importar la direccion."""
    def key(p):
        d = p.get("downloads")
        return (d is None, -(d or 0))
    return sorted(plugins, key=key)


def update_category_board(html: str, src: Sources) -> str:
    counts = {c["key"]: 0 for c in src.categories}
    for p in src.plugins:
        counts[p["categoryKey"]] = counts.get(p["categoryKey"], 0) + 1
    total = len(src.plugins)

    # Celda "All categories" (data-cat="").
    pattern = re.compile(r'(data-cat=""[^>]*>.*?<span class="cat-cell-count">)([^<]*)(</span>)', re.S)
    html, n = pattern.subn(lambda m: m.group(1) + plugin_count_text(total) + m.group(3), html, count=1)
    if n != 1:
        die("celda 'All categories' del cat-board no encontrada")

    for cat in src.categories:
        key = cat["key"]
        n_count = counts.get(key, 0)
        pattern = re.compile(
            r'(data-cat="%s"[^>]*>.*?<span class="cat-cell-count">)([^<]*)(</span>)' % re.escape(key), re.S)
        html, n = pattern.subn(lambda m: m.group(1) + plugin_count_text(n_count) + m.group(3), html, count=1)
        if n != 1:
            die("celda de categoria '%s' no encontrada en el cat-board" % key)

    # La celda 'other' se oculta si nunca hay ningun plugin sin categoria
    # mapeada -- mismo criterio que updateCategoryBoard() tenia en JS.
    other_button = re.compile(r'(<button type="button" class="cat-cell" data-cat="other"[^>]*?)(\s*hidden)?(>)')
    m = other_button.search(html)
    if not m:
        die("celda 'other' del cat-board no encontrada")
    replacement = m.group(1) + ("" if counts.get("other", 0) > 0 else " hidden") + m.group(3)
    html = html[:m.start()] + replacement + html[m.end():]
    return html


def build(dry_run: bool = False) -> None:
    src = Sources()
    renderer = PluginRenderer(src)
    html = CATALOG_PAGE.read_text(encoding="utf-8")

    rows = sort_default(src.plugins)

    total_downloads = src.data.get("totalDownloads", sum(p.get("downloads") or 0 for p in src.plugins))
    cat_count = len([c for c in src.categories if c["key"] != "other"])
    vsx_path = ROOT / "data" / "vscode-catalog-data.json"
    vsx = json.loads(vsx_path.read_text(encoding="utf-8")).get("extensions", []) if vsx_path.exists() else []
    # 2026-10-19: spec sheet instead of four big numbers (no download totals in the header).
    by_price = {k: sum(1 for p in src.plugins if p.get("pricing") == k) for k in ("FREE", "FREEMIUM", "PAID")}
    snapshot = (src.data.get("generatedAt") or "")[:10]
    spec_rows = (
        ("JetBrains IDEs", "%d plugins" % len(src.plugins)),
        ("VS Code", "%d extensions" % len(vsx)),
        ("Pricing", "%d free &middot; %d freemium &middot; %d paid" % (by_price["FREE"], by_price["FREEMIUM"], by_price["PAID"])),
        ("Categories", "%d, each with its own filter below" % cat_count),
        ("Source code", "A public GitHub repository for every plugin and extension"),
        ("Data", "Synced twice a day from public JetBrains Marketplace and GitHub data; last snapshot %s" % snapshot),
    )
    stats_html = "".join('<div class="spec-row"><dt>%s</dt><dd>%s</dd></div>' % row for row in spec_rows)
    _ = total_downloads

    counts = {c["key"]: 0 for c in src.categories}
    for p in src.plugins:
        counts[p["categoryKey"]] = counts.get(p["categoryKey"], 0) + 1
    active_cats = [c for c in src.categories if c["key"] != "other" or counts.get("other", 0) > 0]
    options_html = "".join(
        '<option value="%s">%s (%d)</option>' % (c["key"], esc(c["label"]), counts.get(c["key"], 0))
        for c in active_cats
    )

    grid_html = "".join(card_html(p, renderer, src) for p in rows)
    table_html = "".join(table_row_html(p, renderer, src) for p in rows)

    html = inject(html, "<!-- PRERENDER:STATS:START -->", "<!-- PRERENDER:STATS:END -->", stats_html, "STATS")
    html = inject(html, "<!-- PRERENDER:CATOPTIONS:START -->", "<!-- PRERENDER:CATOPTIONS:END -->",
                  options_html, "CATOPTIONS")
    html = inject(html, "<!-- PRERENDER:GRID:START -->", "<!-- PRERENDER:GRID:END -->", grid_html, "GRID")
    # 2026-09-27: la tabla ya no se pre-renderiza (duplicaba la grilla); la
    # arma js/catalog.js desde las tarjetas. El marcador queda vacio.
    _ = table_html
    html = inject(html, "<!-- PRERENDER:TABLE:START -->", "<!-- PRERENDER:TABLE:END -->", "", "TABLE")
    html = update_category_board(html, src)

    # ---- VS Code: tarjetas pre-renderizadas (mismo markup que js/catalog-vsx.js) --
    def vsx_card(e):
        # 2026-09-27: enlaza a la ficha propia (/catalog/vscode/<name>/); mismo
        # markup que cardHtml() de js/catalog-vsx.js.
        n = e.get("installs") or 0
        # No aria-label: visible text is the accessible name (WCAG 2.5.3).
        return (
            '<a class="vsx-card" href="/catalog/vscode/%s/">'
            '<div class="card-header"><span class="card-cat vsx-mark" aria-hidden="true">%s</span>'
            '<span class="price-badge price-free">Free</span></div>'
            '<div class="card-top"><div class="card-name">%s</div><div class="card-niche">%s</div></div>'
            '<p class="card-pitch">%s</p>'
            '<div class="card-metrics"><span class="card-dl-wrap">%s %s</span>'
            '<span class="card-go">Details</span></div></a>'
            % (esc(e.get("name")), VS_ICON, esc(e.get("displayName")), esc(e.get("niche")),
               esc(pitch_text(e.get("pitch"))), thousands(n), "install" if n == 1 else "installs"))

    html = inject(html, "<!-- PRERENDER:VSXSUB:START -->", "<!-- PRERENDER:VSXSUB:END -->",
                  "%d extensions, built with the same evidence-driven approach and free on the VS Code Marketplace." % len(vsx),
                  "VSXSUB")
    html = inject(html, "<!-- PRERENDER:VSXGRID:START -->", "<!-- PRERENDER:VSXGRID:END -->",
                  "".join(vsx_card(e) for e in vsx), "VSXGRID")
    html = inject(html, "<!-- PRERENDER:TABJB:START -->", "<!-- PRERENDER:TABJB:END -->", str(len(src.plugins)), "TABJB")
    html = inject(html, "<!-- PRERENDER:TABVSX:START -->", "<!-- PRERENDER:TABVSX:END -->", str(len(vsx)), "TABVSX")

    # ---- hubs: data/hubs.json (la seccion no existe hasta el primer hub) ----
    hubs_path = ROOT / "data" / "hubs.json"
    hubs = json.loads(hubs_path.read_text(encoding="utf-8")) if hubs_path.exists() else []
    hubs_html = ""
    if hubs:
        hubs_html = (
            '<section class="catalog-hubs" id="hubs" aria-labelledby="hubsTitle"><div class="cv-head"><div>'
            '<p class="cv-eyebrow">Plugin hubs</p><h2 id="hubsTitle">One install for a whole tool family</h2></div></div>'
            '<div class="svc-grid">%s</div></section>' % "".join(
                '<article class="svc-card"><p class="svc-kicker">%d plugins &middot; %s</p><h3>%s</h3><p>%s</p>'
                '<div class="svc-actions"><a class="btn primary" href="%s" target="_blank" rel="noopener" '
                'data-goatcounter-click="out-hub-%s">Get the hub &#8599;</a></div></article>'
                % (len(h.get("plugins", [])), PRICE_LABEL.get(h.get("pricing", "PAID"), "Paid"), esc(h["name"]),
                   esc(h.get("pitch")), esc(h["marketplaceUrl"]), esc(h["slug"]))
                for h in hubs))
    html = inject(html, "<!-- PRERENDER:CATHUBS:START -->", "<!-- PRERENDER:CATHUBS:END -->", hubs_html, "CATHUBS")

    if dry_run:
        print("[dry-run] %d tarjetas, %d filas, %d opciones de categoria -- nada escrito"
              % (len(rows), len(rows), len(active_cats)))
        return

    CATALOG_PAGE.write_text(html, encoding="utf-8")
    print("[build_catalog_grid] catalog/index.html: %d tarjetas pre-renderizadas (la tabla la arma catalog.js)" % len(rows))


def main():
    ap = argparse.ArgumentParser(description="Pre-renderiza la grilla/tabla de /catalog/")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    build(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
