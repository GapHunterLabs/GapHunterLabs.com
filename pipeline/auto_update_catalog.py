#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refresh the public plugin catalog from Marketplace and GitHub data.

The generated browser data is written to ``data/catalog-data.json``.
The catalog page's JSON-LD is then regenerated from that same file,
while static counts on the home and catalog pages are kept in sync for
first paint and non-JavaScript visitors. Since Fase 2 (2026-09-22),
catalog/index.html's own grid/table are pre-rendered separately by
pipeline/build_catalog_grid.py, which the workflow runs right after
this script -- see that script for why there's no more no-script
fallback list here (the real grid already is one).

Usage:
    python pipeline/auto_update_catalog.py
    python pipeline/auto_update_catalog.py --seo-from-data
"""
import json
import os
import re
import sys
import subprocess
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_DIR = os.path.join(ROOT, "pipeline")
STATIC_PATH = os.path.join(PIPELINE_DIR, "catalog_static_metadata.json")
HISTORY_PATH = os.path.join(PIPELINE_DIR, "catalog_daily_history.json")
LATEST_PATH = os.path.join(PIPELINE_DIR, "catalog_latest_data.json")
DATA_PATH = os.path.join(ROOT, "data", "catalog-data.json")
# 2026-09-10 (clean-URL migration): the catalog page now lives at
# catalog/index.html so GitHub Pages serves it at /catalog/ with no
# ".html" in the address bar. catalog.html itself became a tiny
# client-side redirect stub and is no longer touched by this script.
CATALOG_PATH = os.path.join(ROOT, "catalog", "index.html")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

API = "https://plugins.jetbrains.com/api"
UA = {"User-Agent": "gap-hunter-auto-update/1.0", "Accept": "application/json"}


def get(url):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30))


def resolve_numeric_id(xml_id, name):
    url = "%s/searchPlugins?search=%s" % (API, urllib.parse.quote(name))
    try:
        data = get(url)
    except Exception as e:
        print(f"  [warn] searchPlugins fallo para '{name}': {e}", file=sys.stderr)
        return None
    for p in data.get("plugins", []):
        if p.get("xmlId") == xml_id:
            # Defense in depth: `id` becomes the numeric segment of
            # marketplaceUrl below, which the catalog's safeUrl() already
            # gates to http(s)-only before ever using it in an href -- but
            # validating the *shape* here too means a malformed/non-numeric
            # `id` (a JetBrains API bug, or a compromised response) never
            # even reaches catalog_latest_data.json in the first place,
            # rather than relying solely on the browser-side gate.
            plugin_id = p.get("id")
            if not isinstance(plugin_id, int):
                print(f"  [warn] id no-numerico para '{name}' ({plugin_id!r}), tratando como no encontrado", file=sys.stderr)
                return None
            return p
    return None


def fetch_reviews(numeric_id):
    try:
        comments = get("%s/plugins/%s/comments" % (API, numeric_id))
    except Exception:
        return 0, None
    ratings = [c.get("rating") for c in comments if c.get("rating")]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return len(comments), avg


def github_stars(repo):
    try:
        out = subprocess.run(
            ["gh", "repo", "view", "GapHunterLabs/%s" % repo, "--json", "stargazerCount"],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0:
            print(f"  [warn] gh repo view fallo para {repo}: {out.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(out.stdout).get("stargazerCount")
    except Exception as e:
        print(f"  [warn] gh repo view excepcion para {repo}: {e}", file=sys.stderr)
        return None


def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"snapshots": []}


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# Download counts are published exactly as the JetBrains Marketplace API
# reports them (decision of 2026-11-08). Until then this script subtracted 1
# per plugin, the install JetBrains' review team makes during approval, and
# the same -1 had been applied by hand to every snapshot already stored in
# catalog_daily_history.json (its 3698 total on 2026-09-03 is the corrected
# figure). The history carries a basis marker so that correction is undone
# exactly once, whenever this version first runs.
HISTORY_BASIS_KEY = "downloadsBasis"
HISTORY_BASIS = "marketplace"


def marketplace_downloads(raw):
    """The Marketplace `downloads` figure, unchanged.

    None stays None (plugin not indexed yet). Anything that is not a
    non-negative int is treated as missing, with a warning, the same way
    resolve_numeric_id() treats a malformed `id`.
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        print(f"  [warn] downloads no valido en la API (tipo {type(raw).__name__}), tratado como sin dato",
              file=sys.stderr)
        return None
    return raw


def migrate_history_to_marketplace_counts(history):
    """Add back the 1 download subtracted from every stored snapshot, once.

    Keeps the 7-day trend, the recent-changes deltas and the growth
    baselines on the same basis as the live figure, so the switch does not
    show up as a one-day jump of one download per plugin. Returns True when
    it changed the history. A history with an unknown basis aborts the run
    rather than being guessed at.

    Known gap: a stored 0 could also come from a Marketplace 0 that the old
    rule floored; it becomes 1.
    """
    basis = history.get(HISTORY_BASIS_KEY)
    if basis == HISTORY_BASIS:
        return False
    if basis is not None:
        sys.exit("[auto_update] ERROR: %s=%r in catalog_daily_history.json is not %r; "
                 "refusing to guess how its downloads were counted" % (HISTORY_BASIS_KEY, basis, HISTORY_BASIS))
    for snap in history.get("snapshots", []):
        for entry in (snap.get("plugins") or {}).values():
            value = entry.get("downloads")
            if isinstance(value, int) and not isinstance(value, bool):
                entry["downloads"] = value + 1
    history[HISTORY_BASIS_KEY] = HISTORY_BASIS
    return True


def earliest_datapoint(history, xml_id):
    for snap in history.get("snapshots", []):
        if xml_id in snap.get("plugins", {}):
            return snap["date"], snap["plugins"][xml_id]["downloads"]
    return None, None


# Fase 3 del plan de rediseño (Intelligence layer) -- el sparkline de la
# home necesita una serie corta de {date, totalDownloads} en vez de
# mandar el historico completo (pipeline/catalog_daily_history.json,
# que crece sin poda) al navegador. Se computa aca, sobre el `history`
# que YA incluye el snapshot de hoy (agregado mas arriba en main()
# antes de este punto), sin ninguna llamada de red adicional.
def compute_trend7d(history):
    snaps = sorted(history.get("snapshots", []), key=lambda s: s["date"])[-7:]
    return [
        {
            "date": s["date"],
            "totalDownloads": sum(
                (v.get("downloads") or 0) for v in s.get("plugins", {}).values()
            ),
        }
        for s in snaps
    ]


# "Intelligence changes" -- dos señales reales, ambas con granularidad
# de dia (nunca de hora: el cron corre 2x/dia, cualquier timestamp mas
# fino seria fabricado). 1) plugins nuevos via firstPublished (campo
# curado real); 2) mayores subas de descargas entre los ultimos dos
# snapshots disponibles. Sin umbral "magico" de importancia -- se
# ordena por fecha real y se recorta a un maximo razonable.
def compute_recent_changes(history, rows, days=14, max_events=8):
    events = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    for r in rows:
        fp = r.get("firstPublished")
        if fp and fp >= cutoff:
            events.append({"date": fp, "type": "new", "name": r["name"], "niche": r.get("niche")})

    snaps = sorted(history.get("snapshots", []), key=lambda s: s["date"])
    if len(snaps) >= 2:
        prev_snap, cur_snap = snaps[-2], snaps[-1]
        name_by_id = {r["xmlId"]: r["name"] for r in rows}
        niche_by_id = {r["xmlId"]: r.get("niche") for r in rows}
        deltas = []
        for xml_id, cur_v in cur_snap.get("plugins", {}).items():
            prev_v = prev_snap.get("plugins", {}).get(xml_id)
            if not prev_v:
                continue
            prev_dl, cur_dl = prev_v.get("downloads"), cur_v.get("downloads")
            if prev_dl is None or cur_dl is None:
                continue
            delta = cur_dl - prev_dl
            if delta > 0:
                deltas.append((delta, xml_id))
        deltas.sort(reverse=True)
        for delta, xml_id in deltas[:5]:
            events.append({
                "date": cur_snap["date"], "type": "growth",
                "name": name_by_id.get(xml_id, xml_id), "niche": niche_by_id.get(xml_id),
                "delta": delta,
            })

    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:max_events]


import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from site_config import SITE_URL  # noqa: E402
SITE = SITE_URL + "/"
CATALOG_URL = SITE + "catalog/"

JSONLD_RE = re.compile(
    r'(<script type="application/ld\+json" id="catalog-jsonld">)(.*?)(</script>)',
    re.S,
)
def plain_text(s):
    s = "" if s is None else str(s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"`+", "", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_catalog_jsonld(rows, generated_at):
    # Fase 1 (2026-09-22) le dio a cada plugin su propia URL real y su
    # propio JSON-LD completo (SoftwareApplication + BreadcrumbList, ver
    # pipeline/build_plugin_pages.py) -- este bloque a nivel catalogo ya
    # no necesita repetir esa entidad. Cada ListItem apunta ahora a esa
    # pagina propia (antes apuntaba al Marketplace/GitHub, dejando a
    # Google sin una URL nuestra que indexar por plugin) y no lleva
    # aggregateRating: esas valoraciones son de otro sitio (el
    # Marketplace) y Google no admite ratings agregados de terceros.
    elements = []
    for i, p in enumerate(rows, 1):
        slug = p.get("repo")
        url = ("%s%s/" % (CATALOG_URL, slug)) if slug else CATALOG_URL
        elements.append({
            "@type": "ListItem",
            "position": i,
            "url": url,
            "name": p.get("name") or slug,
        })
    payload = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Gap Hunter Labs Plugin Catalog",
        "url": CATALOG_URL,
        "description": "A catalog of IntelliJ/JetBrains-family IDE plugins, each built from a documented, evidence-based gap in an existing tool.",
        "inLanguage": "en",
        "isPartOf": {"@id": SITE + "#org"},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(rows),
            "itemListOrder": "https://schema.org/ItemListUnordered",
            "itemListElement": elements,
        },
    }
    if generated_at:
        payload["dateModified"] = generated_at[:10]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</script>", "<\\/script>")


def _replace_inner(page_html, pattern, inner, label):
    if not pattern.search(page_html):
        sys.exit("[auto_update] ERROR: missing %s block in catalog/index.html" % label)

    def repl(mm):
        return mm.group(1) + inner + mm.group(3)

    return pattern.sub(repl, page_html, count=1)


def apply_seo_blocks(page_html, rows, generated_at):
    page_html = _replace_inner(
        page_html, JSONLD_RE, build_catalog_jsonld(rows, generated_at), "catalog-jsonld"
    )
    mld = JSONLD_RE.search(page_html)
    ld = json.loads(mld.group(2))
    if ld.get("mainEntity", {}).get("numberOfItems") != len(rows):
        sys.exit("[auto_update] ERROR: catalog-jsonld numberOfItems does not match plugin count")
    return page_html


def refresh_seo_from_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    rows = data["plugins"]
    generated_at = data.get("generatedAt") or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    with open(CATALOG_PATH, encoding="utf-8") as f:
        page = f.read()
    page = apply_seo_blocks(page, rows, generated_at)
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        f.write(page)
    print("[auto_update] catalog SEO refreshed from external data (%d plugins)" % len(rows))


# Static page counts: this script used to rewrite count markers in the
# static HTML itself (a hero subtitle until 2026-09-10, then the footer's
# `id="footerStatusText">N plugins tracked`). Both are gone: the v2 footer
# (commit fc7d5d9, 2026-09-28, pipeline/build_chrome.py) carries no count,
# and every visible count on the home and the catalog is now written by
# build_home.py and build_catalog_grid.py, which run right after this
# script in the same workflow. The footer swap had become a dead marker
# that aborted every scheduled run (2026-09-28 11:25 UTC); it is removed
# rather than re-adding a count to a footer designed without one. The
# "Sanity-check generated catalog" workflow step still fails the job if
# the data, the JSON-LD, the cards and the table rows ever disagree.


def main():
    with open(STATIC_PATH, encoding="utf-8") as f:
        static = json.load(f)["plugins"]

    history = load_history()
    if migrate_history_to_marketplace_counts(history):
        print("[auto_update] historico pasado a conteos de Marketplace (+1 por plugin en cada snapshot)")
    today = str(date.today())

    results = {}
    snapshot_for_history = {}
    # 2026-08-28 (fix del hallazgo critico #25/#24 de la auditoria):
    # contador real de exito/fallo de github_stars() -- antes nada
    # trackeaba esto, asi que un GH_TOKEN faltante/invalido/sin permisos
    # (exactamente lo que paso hasta este fix) hacia fallar el 100% de
    # las llamadas en silencio, sin que el workflow lo notara. Ver el
    # chequeo real despues del loop.
    stars_attempted = 0
    stars_succeeded = 0

    print(f"[auto_update] {len(static)} plugins en metadata estatica")
    for repo, meta in sorted(static.items()):
        xml_id = meta["xmlId"]
        name = meta["name"]
        p = resolve_numeric_id(xml_id, name)

        if p is None:
            print(f"  -> {repo:28} sin indexar todavia / no encontrado")
            entry = dict(meta)
            entry.update({
                "repo": repo,
                "marketplaceUrl": None,
                "downloads": None,
                "pricing": None,
                "reviews": 0,
                "rating": None,
                "growth": None,
                "growthSince": None,
                "growthFrom": None,
            })
            results[repo] = entry
            continue

        numeric_id = p.get("id")
        # The Marketplace figure as published: see marketplace_downloads().
        downloads = marketplace_downloads(p.get("downloads"))
        pricing = p.get("pricingModel")
        reviews, rating = fetch_reviews(numeric_id)
        stars = github_stars(repo)
        stars_attempted += 1
        if stars is not None:
            stars_succeeded += 1

        base_date, base_downloads = earliest_datapoint(history, xml_id)
        growth = None
        if base_downloads is not None and base_downloads > 0 and downloads is not None:
            growth = round((downloads - base_downloads) / base_downloads * 100, 1)

        entry = dict(meta)
        entry.update({
            "repo": repo,
            "marketplaceUrl": f"https://plugins.jetbrains.com/plugin/{numeric_id}-{repo}",
            "downloads": downloads,
            "pricing": pricing,
            "reviews": reviews,
            "rating": rating,
            "stars": stars,
            "growth": growth,
            "growthSince": base_date,
            "growthFrom": base_downloads,
        })
        results[repo] = entry
        snapshot_for_history[xml_id] = {"downloads": downloads}

        print(f"  -> {repo:28} {downloads if downloads is not None else 'sin indexar'} dl")

    # Guarda el snapshot de HOY en el historico propio de este repo --
    # si ya existe uno de hoy (2 corridas el mismo dia), lo reemplaza en
    # vez de duplicar.
    history["snapshots"] = [s for s in history["snapshots"] if s["date"] != today]
    history["snapshots"].append({"date": today, "plugins": snapshot_for_history})

    rows = list(results.values())
    rows.sort(key=lambda r: (r["downloads"] is None, -(r["downloads"] or 0)))

    total_downloads = sum(r["downloads"] or 0 for r in rows)
    pending = sum(1 for r in rows if r["downloads"] is None)
    total_stars = sum(r["stars"] or 0 for r in rows if r.get("stars"))
    total_reviews = sum(r["reviews"] or 0 for r in rows)
    rated = [r["rating"] for r in rows if r.get("rating")]
    avg_rating_all = round(sum(rated) / len(rated), 2) if rated else None

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    data = {
        "generatedAt": generated_at,
        "totalPlugins": len(rows),
        "totalDownloads": total_downloads,
        "pending": pending,
        "totalStars": total_stars,
        "totalReviews": total_reviews,
        "avgRating": avg_rating_all,
        "trend7d": compute_trend7d(history),
        "recentChanges": compute_recent_changes(history, rows),
        "plugins": rows,
    }

    print(f"[auto_update] plugins: {len(rows)} | descargas totales: {total_downloads} "
          f"| pendientes: {pending} | stars: {total_stars}")
    print(f"[auto_update] github_stars(): {stars_succeeded}/{stars_attempted} llamadas exitosas")

    # 2026-08-28 (fix del hallazgo critico #25/#24 de la auditoria):
    # abortar con exit code distinto de 0 si el 100% de las llamadas a
    # github_stars() fallaron -- asi el workflow se marca en ROJO en vez
    # de verde-silencioso cuando GH_TOKEN falta/expira/pierde permisos,
    # que es exactamente el bug real que dejo GitHub Stars/Reviews/Rating
    # en cero durante semanas sin que nadie lo notara (documentado en
    # DOCUMENTATION.md). El umbral es "0 exitosas de al menos 10
    # intentos" (no "menos del 100%") -- un puñado de fallos puntuales
    # por rate-limit/timeout de gh en un plugin especifico es normal y
    # no amerita abortar toda la corrida, solo un fallo TOTAL sistemico
    # (token invalido/faltante) lo amerita.
    if stars_attempted >= 10 and stars_succeeded == 0:
        sys.exit(
            "[auto_update] ERROR: 0/%d llamadas a github_stars() tuvieron exito -- "
            "esto casi siempre significa que GH_TOKEN no esta seteado o no tiene "
            "permisos (ver el paso 'Run auto-update' en update-catalog.yml). "
            "Abortando antes de publicar datos con stars en "
            "cero silenciosamente." % stars_attempted
        )

    save_history(history)
    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    refresh_seo_from_data()
    print("[auto_update] external catalog JSON and catalog SEO updated")

    # sitemap.xml <lastmod>, 2026-08-23 (audit finding): the page's real
    # content changes twice a day via this same script, but the sitemap
    # never carried a <lastmod> for crawlers to prioritize re-fetching
    # against. Swap-in-place on the one <url> entry, same discipline as
    # the catalog-data block above -- generatedAt is already a real UTC
    # timestamp from this same run, just reused here as the date portion.
    if os.path.exists(SITEMAP_PATH):
        with open(SITEMAP_PATH, encoding="utf-8") as f:
            sitemap = f.read()
        lastmod_date = generated_at[:10]  # YYYY-MM-DD from the ISO timestamp
        catalog_entry = re.compile(
            r"(<loc>%scatalog/</loc>\s*<lastmod>).*?(</lastmod>)" % re.escape(SITE),
            re.S,
        )
        sitemap, count = catalog_entry.subn(r"\g<1>%s\g<2>" % lastmod_date, sitemap, count=1)
        if count != 1:
            sys.exit("[auto_update] ERROR: catalog/ sitemap entry missing")
        with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
            f.write(sitemap)
        print(f"[auto_update] sitemap.xml lastmod actualizado a {lastmod_date}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args in (["--seo-from-data"], ["--seo-from-index"]):
        refresh_seo_from_data()
    elif not args:
        main()
    else:
        sys.exit(
            "Usage: python pipeline/auto_update_catalog.py [--seo-from-data]"
        )
