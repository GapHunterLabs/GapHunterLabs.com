#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_search_index.py -- indice del buscador del topbar (js/search-data.js).

El buscador es 100% local: la CSP del sitio no permite fetch() a 'self'
(connect-src solo lista GoatCounter), asi que el indice es un script que
define window.GHL_SEARCH y se carga recien cuando alguien abre el buscador.

Que indexa (en ingles y en espanol cuando hay version ES):
  * las fichas JetBrains y VS Code (nombre, descripcion, nicho, categoria,
    precio, descargas, enlaces),
  * las paginas principales (titulo y descripcion de la pagina ya construida),
  * los casos de estudio y los tickets de JetBrains Platform.

Versionado: escribe el hash del indice dentro de js/site-search.js y el hash
de site-search.js dentro de js/site-chrome.js (entre marcadores), para que
version_assets.py, que solo versiona atributos src/href, igual invalide la
cache de los dos scripts que se cargan dinamicamente.

Correr despues de build_plugin_pages.py y build_i18n.py, y antes de
version_assets.py.
Uso: python pipeline/build_search_index.py
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_chrome import ES_PATHS  # noqa: E402
from build_plugin_pages import Sources, pitch_prose  # noqa: E402

DATA_JS = ROOT / "js" / "search-data.js"
SEARCH_JS = ROOT / "js" / "site-search.js"
CHROME_JS = ROOT / "js" / "site-chrome.js"
ES_DICT = ROOT / "pipeline" / "i18n" / "es.json"


def text_of(fragment: str) -> str:
    frag = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", " ", fragment, flags=re.S)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", frag))).strip()


def plain(md: str) -> str:
    """Pitch en markdown liviano -> texto plano."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", md or "")
    s = re.sub(r"`([^`]*)`", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def page_file(path: str) -> Path:
    return ROOT / ("index.html" if path == "/" else path.strip("/") + "/index.html")


def head_meta(path: str):
    s = page_file(path).read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", s, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', s)
    t = htmllib.unescape(title.group(1)).strip() if title else path
    t = re.sub(r"\s*[|—–-]\s*(Engineering &amp; Evidence\s*\|\s*)?Gap Hunter Labs$", "", t)
    t = re.sub(r"\s*\|\s*Engineering & Evidence$", "", t)
    return t, htmllib.unescape(desc.group(1)).strip() if desc else ""


def short(s: str, n: int = 240) -> str:
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def main() -> int:
    src = Sources()
    es = json.loads(ES_DICT.read_text(encoding="utf-8"))
    items = []

    for p in src.plugins:
        cat = src.cat_by_key.get(p.get("categoryKey"), src.cat_by_key["other"])
        items.append({
            "t": "p", "n": p["name"], "s": p["repo"], "d": short(plain(pitch_prose(p.get("pitch"))), 320),
            "k": p.get("niche") or "", "c": {"en": cat["label"], "es": es.get(cat["label"], cat["label"])},
            "pr": p.get("pricing") or "FREE", "dl": p.get("downloads") or 0,
            "u": "/catalog/%s/" % p["repo"], "m": p.get("marketplaceUrl") or "",
        })
    for e in src.vsx_list:
        items.append({
            "t": "v", "n": e.get("displayName") or e["name"], "s": e["name"], "d": short(plain(pitch_prose(e.get("pitch"))), 320),
            "k": e.get("niche") or "", "c": {"en": "VS Code extension", "es": "Extensión para VS Code"},
            "pr": "FREE", "dl": e.get("installs") or 0,
            "u": "/catalog/vscode/%s/" % e["name"], "m": e.get("marketplaceUrl") or "",
        })
    for e in src.atl_list:
        items.append({
            "t": "a", "n": e.get("displayName") or e["name"], "s": e["name"], "d": short(plain(pitch_prose(e.get("pitch"))), 320),
            "k": e.get("niche") or "", "c": {"en": "Atlassian Marketplace app", "es": "App de Atlassian Marketplace"},
            "pr": "FREE", "dl": e.get("installs") or 0,
            "u": "/catalog/atlassian/%s/" % e["name"], "m": e.get("marketplaceUrl") or "",
        })

    for en_path, es_path in ES_PATHS.items():
        t_en, d_en = head_meta(en_path)
        t_es, d_es = head_meta(es_path)
        items.append({"t": "g", "n": {"en": t_en, "es": t_es}, "d": {"en": short(d_en), "es": short(d_es)},
                      "u": {"en": en_path, "es": es_path}})

    def cards(path, art_re, title_re, body_re):
        s = page_file(path).read_text(encoding="utf-8")
        main_html = re.search(r"<main.*?</main>", s, re.S).group(0)
        out = []
        for art in re.findall(art_re, main_html, re.S):
            title = re.search(title_re, art, re.S)
            body = re.search(body_re, art, re.S)
            out.append((text_of(title.group(1)) if title else "", text_of(body.group(1)) if body else "", art))
        return out

    cs_en = "/engineering-evidence/case-studies/"
    cs = list(zip(cards(cs_en, r'<article class="identity-card identity-case">(.*?)</article>', r"<h2>(.*?)</h2>",
                        r'<p class="eyebrow">.*?</p>\s*<h2>.*?</h2>\s*<p>(.*?)</p>'),
                  cards(ES_PATHS[cs_en], r'<article class="identity-card identity-case">(.*?)</article>', r"<h2>(.*?)</h2>",
                        r'<p class="eyebrow">.*?</p>\s*<h2>.*?</h2>\s*<p>(.*?)</p>')))
    for (n_en, d_en, _), (n_es, d_es, _) in cs:
        items.append({"t": "c", "n": {"en": n_en, "es": n_es}, "d": {"en": short(d_en), "es": short(d_es)},
                      "u": {"en": cs_en, "es": ES_PATHS[cs_en]}})

    tk_en = "/engineering-evidence/jetbrains-platform-tickets/"
    tks = list(zip(cards(tk_en, r'<article class="ticket-card">(.*?)</article>', r"<h3>(.*?)</h3>", r"<p>(.*?)</p>"),
                   cards(ES_PATHS[tk_en], r'<article class="ticket-card">(.*?)</article>', r"<h3>(.*?)</h3>", r"<p>(.*?)</p>")))
    for (n_en, d_en, art), (_, d_es, art_es) in tks:
        tid = re.search(r'class="ticket-id"[^>]*>([^<&]+)', art)
        st_en = re.search(r'class="ticket-status[^"]*">([^<]+)', art)
        st_es = re.search(r'class="ticket-status[^"]*">([^<]+)', art_es)
        items.append({"t": "k", "n": {"en": (tid.group(1).strip() + " — " if tid else "") + n_en,
                                      "es": (tid.group(1).strip() + " — " if tid else "") + n_en},
                      "d": {"en": short(d_en), "es": short(d_es)},
                      "st": {"en": st_en.group(1).strip() if st_en else "", "es": st_es.group(1).strip() if st_es else ""},
                      "u": {"en": tk_en, "es": ES_PATHS[tk_en]}})

    payload = {"generated": (src.data.get("generatedAt") or "")[:10], "items": items}
    body = ("/* Indice del buscador del sitio. Lo genera pipeline/build_search_index.py; no editar a mano. */\n"
            "window.GHL_SEARCH = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    DATA_JS.write_text(body, encoding="utf-8")
    data_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]

    def inject(path: Path, marker: str, value: str):
        s = path.read_text(encoding="utf-8")
        new, n = re.subn(r"(/\*%s\*/)'[^']*'(/\*END%s\*/)" % (marker, marker), r"\1'%s'\2" % value, s)
        if n != 1:
            raise SystemExit("[build_search_index] marcador %s no encontrado en %s" % (marker, path.name))
        if new != s:
            path.write_text(new, encoding="utf-8")

    inject(SEARCH_JS, "DATA_URL", "/js/search-data.js?v=" + data_hash)
    # CRLF -> LF antes de hashear (igual que version_assets.py): en Windows, con autocrlf, el disco tiene CRLF pero el
    # repo y el cron (Linux) ven LF, y el hash tiene que ser el mismo en los dos.
    search_hash = hashlib.sha256(SEARCH_JS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:8]
    inject(CHROME_JS, "SEARCH_SRC", "/js/site-search.js?v=" + search_hash)
    counts = {}
    for it in items:
        counts[it["t"]] = counts.get(it["t"], 0) + 1
    print("[build_search_index] %d entradas (%s) -> js/search-data.js (%d KB)"
          % (len(items), ", ".join("%s=%d" % kv for kv in sorted(counts.items())), len(body.encode("utf-8")) // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
