#!/usr/bin/env python3
"""build_feed.py -- /feed.xml (RSS 2.0) con los lanzamientos mas recientes
del catalogo: plugins JetBrains y extensiones VS Code, cada uno enlazado a
su ficha en el sitio.

Estable a proposito: lastBuildDate es la fecha del item mas reciente (no la
hora de la corrida), asi el CI no genera un commit cada vez que corre si no
hubo lanzamientos nuevos.

Uso: python pipeline/build_feed.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_config import SITE_URL  # noqa: E402
from build_plugin_pages import Sources, plain_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "feed.xml"
MAX_ITEMS = 40


def rfc822(day: str) -> str:
    dt = datetime.strptime(day[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y 00:00:00 +0000")


def main() -> int:
    src = Sources()
    items = []
    for p in src.plugins:
        if p.get("firstPublished"):
            cat = src.cat_by_key.get(p["categoryKey"], {}).get("label", "Other")
            items.append((p["firstPublished"][:10], p["name"], "%s/catalog/%s/" % (SITE_URL, p["repo"]),
                          plain_text(p.get("pitch")), "JetBrains plugin · " + cat))
    for e in src.vsx_list:
        if e.get("publishedDate"):
            items.append((e["publishedDate"][:10], e["displayName"], "%s/catalog/vscode/%s/" % (SITE_URL, e["name"]),
                          plain_text(e.get("pitch")), "VS Code extension · " + (e.get("niche") or "")))
    for e in src.atl_list:
        if e.get("publishedDate"):
            items.append((e["publishedDate"][:10], e["displayName"], "%s/catalog/atlassian/%s/" % (SITE_URL, e["name"]),
                          plain_text(e.get("pitch")), "Atlassian Marketplace app · " + (e.get("niche") or "")))
    items.sort(key=lambda i: (i[0], i[1]), reverse=True)
    items = items[:MAX_ITEMS]
    if not items:
        print("[build_feed] sin items con fecha -- feed.xml no se toca")
        return 0
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
           "<channel>",
           "<title>Gap Hunter Labs: new plugins</title>",
           "<link>%s/</link>" % SITE_URL,
           '<atom:link href="%s/feed.xml" rel="self" type="application/rss+xml"/>' % SITE_URL,
           "<description>New JetBrains plugins and VS Code extensions from Gap Hunter Labs, each built for a documented gap in developer tooling.</description>",
           "<language>en</language>",
           "<lastBuildDate>%s</lastBuildDate>" % rfc822(items[0][0])]
    for day, title, link, desc, category in items:
        out += ["<item>",
                "<title>%s</title>" % escape(title),
                "<link>%s</link>" % escape(link),
                '<guid isPermaLink="true">%s</guid>' % escape(link),
                "<pubDate>%s</pubDate>" % rfc822(day),
                "<category>%s</category>" % escape(category),
                "<description>%s</description>" % escape(desc or ""),
                "</item>"]
    out += ["</channel>", "</rss>", ""]
    text = "\n".join(out)
    if FEED.exists() and FEED.read_text(encoding="utf-8") == text:
        print("[build_feed] feed.xml sin cambios (%d items)" % len(items))
        return 0
    FEED.write_text(text, encoding="utf-8")
    print("[build_feed] feed.xml: %d items (mas reciente %s)" % (len(items), items[0][0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
