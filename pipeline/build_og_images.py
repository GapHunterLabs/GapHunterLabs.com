#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_og_images.py -- genera la imagen social (1200x630) de cada plugin de JetBrains
(media/<slug>/og.png) y de cada extension de VS Code (media/vscode/<name>/og.png).

Redisenado 2026-10-29 con el kit compartido (og_kit.py): fondo casi negro con la rejilla y
el resplandor del hero de la home, el nombre en grande, una linea del problema que resuelve,
etiquetas SVG en linea (plataforma, precio, categoria) y el icono de la categoria. Sin cifras
de descargas ni estrellas: se desactualizan y la imagen no se regenera en cada build.

Reusa Sources/PluginRenderer de build_plugin_pages.py -- misma fuente de verdad de
categoria/color/icono/pricing que el resto del sitio. Un unico Chromium (Playwright)
renderiza todo en una sola sesion y falla si un nombre o un texto se corta.

Despues de regenerar, sube OG_VERSION en site_config.py y corre build_plugin_pages.py:
las redes sociales guardan la imagen por URL.

Requiere playwright (`pip install playwright` + `python -m playwright install chromium`).

Uso:
    python pipeline/build_og_images.py --limit 3             # prueba rapida
    python pipeline/build_og_images.py --slug mermaid-companion
    python pipeline/build_og_images.py --only vscode          # solo las 33 extensiones
    python pipeline/build_og_images.py                        # los 146 plugins + las extensiones
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import og_kit as K  # noqa: E402
from build_plugin_pages import Sources, PluginRenderer, truncate  # noqa: E402

ROOT = HERE.parent
MEDIA_DIR = ROOT / "media"

CSS = """
  .cols { display:grid; grid-template-columns:minmax(0,1fr) 250px; gap:48px; align-items:center; }
  .headline { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; padding-bottom:.16em; }
  .lede { font-size:27px; max-width:720px; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  .badges { margin-top:26px; }
  .badge .cat { fill:none !important; stroke-width:1.6; }
  .visual { width:250px; height:250px; border-radius:36px; display:grid; place-items:center; justify-self:end;
    background:color-mix(in srgb, var(--cat) 12%, #111111); border:1px solid color-mix(in srgb, var(--cat) 45%, #2E2E2E);
    box-shadow:0 0 90px color-mix(in srgb, var(--cat) 24%, transparent); }
  .visual svg { width:132px; height:132px; stroke:var(--cat); fill:none; stroke-width:1.35; stroke-linecap:round; stroke-linejoin:round; }
  .visual svg.solid { stroke:none; fill:var(--cat); }
"""

ACCENT = "#FF6A1A"  # the site's signal orange: the category colors in the catalog are neutral grays, too dim for a thumbnail
VSCODE_MARK = '<svg class="solid" viewBox="0 0 24 24" aria-hidden="true"><path d="M16.5 3 21 5.2v13.6L16.5 21 7 12.9 3.6 15.6 2 14.8V9.2l1.6-.8L7 11.1 16.5 3Zm0 4.2-5 4.8 5 4.8V7.2Z"/></svg>'
# Generic workflow-graph mark (3 nodes), not an Atlassian/Jira logo -- see js/catalog-shared.js's "atlassian" entry.
ATLASSIAN_MARK = ('<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="6" cy="6" r="2"/><circle cx="14" cy="6" r="2"/>'
                   '<circle cx="10" cy="15" r="2"/><path d="M7.6 7.2 8.5 13.3M12.4 7.2 11.5 13.3"/></svg>')


def name_size(name: str) -> int:
    n = len(name)
    for limit, px in ((14, 84), (20, 74), (26, 64), (34, 56), (40, 50), (48, 44)):
        if n <= limit:
            return px
    return 38


def category_badge(label: str, color: str, inner: str) -> str:
    return ('<span class="badge badge--dark"><svg class="b-ico cat" viewBox="-8 -8 16 16" style="stroke:%s" aria-hidden="true">%s</svg><span>%s</span></span>'
            % (color, inner, K.esc(label)))


def body(name, tagline, badges, color, visual_inner) -> str:
    return ('<div class="cols" style="--cat:%s"><div>'
            '<h1 class="headline" data-fit style="font-size:%dpx">%s</h1><p class="lede">%s</p>%s</div>'
            '<div class="visual" aria-hidden="true">%s</div></div>'
            % (color, name_size(name), K.esc(name), K.esc(tagline), badges, visual_inner))


def plugin_job(renderer: PluginRenderer, src: Sources, p: dict):
    is_pending = p.get("downloads") is None
    pr_cls, _ = renderer.pricing_label(p.get("pricing"), is_pending)
    cat = src.cat_by_key.get(p["categoryKey"], src.cat_by_key["other"])
    inner = src.cat_icon_inner.get(p["categoryKey"]) or src.cat_icon_inner["other"]
    keys = []
    if p.get("marketplaceUrl"):
        keys.append("jetbrains")
    vsx = src.vsx_by_repo.get(p["repo"])
    if vsx and vsx.get("marketplaceUrl"):
        keys.append("vscode")
    badges = K.badges_html(keys + [pr_cls]).replace("</div>", category_badge(cat["label"], "#EDEDED", inner) + "</div>", 1)
    html = K.page_html("en", body(p["name"], truncate(renderer.description(p), 150), badges, ACCENT,
                                  '<svg viewBox="-8 -8 16 16" aria-hidden="true">%s</svg>' % inner),
                       css=CSS, label=p.get("niche") or cat["label"], host="%s/catalog/%s/" % (K.SITE_HOST, p["repo"]))
    return p["repo"], html


def extension_job(renderer: PluginRenderer, e: dict):
    badges = K.badges_html(["vscode", "free"])
    html = K.page_html("en", body(e["displayName"], truncate(renderer.vsx_description(e), 150), badges, "#007ACC", VSCODE_MARK),
                       css=CSS, label=e.get("niche") or "VS Code extension",
                       host="%s/catalog/vscode/%s/" % (K.SITE_HOST, e["name"]))
    return "vscode/" + e["name"], html


def atlassian_job(renderer: PluginRenderer, e: dict):
    is_pending = e.get("installs") is None
    badges = K.badges_html(["atlassian", "pending" if is_pending else "free"])
    html = K.page_html("en", body(e["displayName"], truncate(renderer.atl_description(e), 150), badges, ACCENT, ATLASSIAN_MARK),
                       css=CSS, label=e.get("niche") or "Atlassian Marketplace app",
                       host="%s/catalog/atlassian/%s/" % (K.SITE_HOST, e["name"]))
    return "atlassian/" + e["name"], html


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="solo los primeros N de cada grupo")
    ap.add_argument("--slug", default=None, help="solo este plugin (repo) o extension (vscode/<name>)")
    ap.add_argument("--only", choices=("jetbrains", "vscode", "atlassian"), default=None)
    ap.add_argument("--out-dir", default=str(MEDIA_DIR), help="donde escribir <key>/og.png (default: media/)")
    ap.add_argument("--html", metavar="DIR", default=None, help="tambien escribe el HTML fuente en DIR (depuracion)")
    args = ap.parse_args()

    src = Sources()
    renderer = PluginRenderer(src)
    jobs = []
    if args.only is None or args.only == "jetbrains":
        rows = src.plugins
        if args.limit:
            rows = rows[: args.limit]
        jobs += [plugin_job(renderer, src, p) for p in rows]
    if args.only is None or args.only == "vscode":
        rows = src.vsx_list
        if args.limit:
            rows = rows[: args.limit]
        jobs += [extension_job(renderer, e) for e in rows]
    if args.only is None or args.only == "atlassian":
        rows = src.atl_list
        if args.limit:
            rows = rows[: args.limit]
        jobs += [atlassian_job(renderer, e) for e in rows]
    if args.slug:
        jobs = [j for j in jobs if j[0] == args.slug]
        if not jobs:
            sys.exit("[build_og_images] ERROR: no existe %r" % args.slug)
    if args.html:
        Path(args.html).mkdir(parents=True, exist_ok=True)
        for key, html in jobs:
            (Path(args.html) / (key.replace("/", "__") + ".html")).write_text(html, encoding="utf-8")

    written = K.render(jobs, lambda key: Path(args.out_dir) / key / "og.png", label="build_og_images")
    for out in written:
        group = out.parent.parent.name
        label = out.parent.name if group not in ("vscode", "atlassian") else group + "/" + out.parent.name
        print("  %-60s %4.0f KB" % (label, out.stat().st_size / 1024))
    print("\nOK -- %d imagen(es) OG generada(s)." % len(written))


if __name__ == "__main__":
    main()
