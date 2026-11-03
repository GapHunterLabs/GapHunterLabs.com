#!/usr/bin/env python3
"""Feed propio de /writing (separado del feed.xml de plugins).

Genera dos feeds Atom -- /writing/feed.xml (EN) y /es/escritos/feed.xml (ES) --
leyendo las fichas de articulo ya construidas (writing/<slug>/ y
es/escritos/<slug>/), y enlaza cada indice con su feed. Se corre DESPUES de
build_i18n (que ya genero las paginas ES) y antes de version_assets.
"""
import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_config import SITE_URL  # noqa: E402

SITE = SITE_URL.rstrip("/")

TREES = [
    {"lang": "en", "dir": ROOT / "writing", "base": "/writing/",
     "feed": "/writing/feed.xml", "title": "Gap Hunter Labs — Writing"},
    {"lang": "es", "dir": ROOT / "es" / "escritos", "base": "/es/escritos/",
     "feed": "/es/escritos/feed.xml", "title": "Gap Hunter Labs — Escritos"},
]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
DATE_RE = re.compile(r'<time datetime="(\d{4}-\d{2}-\d{2})"')
FEED_LINK_RE = re.compile(r'<link rel="alternate" type="application/atom\+xml"[^>]*href="[^"]*/writing[^"]*"[^>]*>\s*', re.I)


def clean(raw):
    """HTML -> texto plano seguro para XML (decodifica entidades, corta sufijo de marca)."""
    txt = html.unescape(raw).strip()
    txt = re.sub(r"\s*—\s*Gap Hunter Labs$", "", txt)  # quita " — Gap Hunter Labs"
    return txt


def articles(tree):
    out = []
    for idx in sorted(tree["dir"].glob("*/index.html")):
        htmltext = idx.read_text(encoding="utf-8")
        slug = idx.parent.name
        title = clean((TITLE_RE.search(htmltext) or [None, slug])[1])
        canon = (CANON_RE.search(htmltext) or [None, SITE + tree["base"] + slug + "/"])[1]
        desc = clean((DESC_RE.search(htmltext) or [None, ""])[1])
        dm = DATE_RE.search(htmltext)
        date = dm.group(1) if dm else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out.append({"slug": slug, "title": title, "url": canon, "summary": desc, "date": date})
    # mas reciente primero
    out.sort(key=lambda a: a["date"], reverse=True)
    return out


def build_feed(tree, items):
    updated = (max((a["date"] for a in items), default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))) + "T00:00:00Z"
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="%s">' % tree["lang"],
        "  <title>%s</title>" % escape(tree["title"]),
        '  <link href="%s%s" rel="self"/>' % (SITE, tree["feed"]),
        '  <link href="%s%s"/>' % (SITE, tree["base"]),
        "  <id>%s%s</id>" % (SITE, tree["base"]),
        "  <updated>%s</updated>" % updated,
        "  <author><name>Joel Díaz</name></author>",
    ]
    for a in items:
        lines += [
            "  <entry>",
            "    <title>%s</title>" % escape(a["title"]),
            '    <link href="%s"/>' % escape(a["url"]),
            "    <id>%s</id>" % escape(a["url"]),
            "    <updated>%sT00:00:00Z</updated>" % a["date"],
            "    <summary>%s</summary>" % escape(a["summary"]),
            "  </entry>",
        ]
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def link_index(tree):
    """Inyecta <link rel=alternate atom+xml> con el feed correcto en el indice."""
    idx = tree["dir"] / "index.html"
    if not idx.exists():
        return
    text = idx.read_text(encoding="utf-8")
    text = FEED_LINK_RE.sub("", text)  # quita cualquier enlace de feed de writing previo
    tag = '<link rel="alternate" type="application/atom+xml" title="%s" href="%s">\n' % (escape(tree["title"]), tree["feed"])
    # ancla: justo antes de </head>
    new, n = re.subn(r"</head>", tag + "</head>", text, count=1)
    if n == 1 and new != text:
        idx.write_text(new, encoding="utf-8")


def main():
    total = 0
    for tree in TREES:
        items = articles(tree)
        (ROOT / tree["feed"].lstrip("/")).write_text(build_feed(tree, items), encoding="utf-8")
        link_index(tree)
        total += len(items)
        print("[build_writing_feed] %s: %d articulos -> %s" % (tree["lang"], len(items), tree["feed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
