#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_plugin_pages.py -- una URL real por plugin.

Convierte cada entrada de data/catalog-data.json en

    /catalog/<repo>/index.html

donde <repo> es EXACTAMENTE el mismo slug que hoy viaja en el hash del
catalogo (/catalog/#mermaid-companion), asi que cada enlace ya compartido
sigue apuntando al mismo plugin despues de la migracion.

Principio de diseno: este script NO reimplementa el dossier ni el shell.
Los lee del propio catalogo:

  * el shell (topbar, sidebar, wrappers, footer, <head>) sale de
    catalog/index.html por marcadores estables;
  * el CSS sale de los <style> inline de esa misma pagina y se escribe UNA
    vez a css/plugin.css, cacheable por las 146 fichas;
  * los mapas de datos (NICHE_TO_CATEGORY, GAP_OVERRIDES, DEMO_MEDIA,
    CATEGORIES, ICONS) se parsean de js/catalog-shared.js.

Si alguno de esos marcadores desaparece, el script aborta con un mensaje
concreto en vez de generar paginas silenciosamente rotas. Una sola fuente
de verdad; nada duplicado a mano.

Sin dependencias externas: solo biblioteca estandar.

Uso:
    python pipeline/build_plugin_pages.py --inspect
    python pipeline/build_plugin_pages.py --dry-run --limit 3
    python pipeline/build_plugin_pages.py            # genera todo
    python pipeline/build_plugin_pages.py --sitemap --inject
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from site_config import SITE_URL, OG_VERSION  # noqa: E402
from badges import badge, price_badge  # noqa: E402
SITE = SITE_URL
ORG_ID = SITE + "/#org"
CATALOG_URL = SITE + "/catalog/"

DATA_FILE = ROOT / "data" / "catalog-data.json"
VSX_DATA_FILE = ROOT / "data" / "vscode-catalog-data.json"
SHARED_JS = ROOT / "js" / "catalog-shared.js"
# Optional (2026-11-08): the yearly price of a paid plugin, as listed on JetBrains Marketplace. The public API does
# not expose prices, so the owner fills this file by hand; a plugin without an entry shows no amount (never a guess).
PRICES_FILE = ROOT / "data" / "plugin-prices.json"
CATALOG_PAGE = ROOT / "catalog" / "index.html"
INDEX_PAGE = ROOT / "index.html"
CATALOG_STUB = ROOT / "catalog.html"
CSS_OUT = ROOT / "css" / "plugin.css"
SITEMAP = ROOT / "sitemap.xml"
LASTMOD_STORE = ROOT / "_review" / "plugin_lastmod.json"

OG_IMAGE = "%s/og-image.png?v=%s" % (SITE, OG_VERSION)
OG_IMAGE_ALT = "Gap Hunter Labs — performance, security and reliability engineering"
MEDIA_DIR = ROOT / "media"
SHARE_ICON_X = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 '
                '8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833'
                'L7.084 4.126H5.117z"/></svg>')
SHARE_ICON_LINKEDIN = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328'
                       '-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 '
                       '3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 '
                       '2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452z'
                       'M22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729'
                       'C24 .774 23.2 0 22.222 0h.003z"/></svg>')
SHARE_ICON_LINK = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
                   'stroke-linejoin="round" aria-hidden="true"><path d="M6.5 9.5a3 3 0 0 0 4.2 0l2-2a3 3 0 0 0-4.2-4.2l-.7.7"/>'
                   '<path d="M9.5 6.5a3 3 0 0 0-4.2 0l-2 2a3 3 0 0 0 4.2 4.2l.7-.7"/></svg>')
TITLE_SOFT_MAX = 70
DESC_MAX = 155
SIMILAR_MAX = 4
GROWTH_PERCENT_MIN_BASELINE = 10

# Paginas que llevan el shim hash -> ruta.
# 2026-09-24: el shim de home y catalogo salio del HTML a js/slug-shim.js (para
# poder quitar 'unsafe-inline' de la CSP); catalog.html (stub, sin CSP) conserva el suyo.
SLUG_INJECTION_TARGETS = ("js/slug-shim.js", "catalog.html")
SLUG_MARK_OPEN = "/*SLUGS*/"
SLUG_MARK_CLOSE = "/*ENDSLUGS*/"

# Campos que cuentan como contenido sustancial para el <lastmod>. Las
# metricas en vivo (downloads/growth/stars/reviews/rating) quedan fuera a
# proposito: cambian dos veces al dia y convertirian el lastmod en ruido.
MATERIAL_FIELDS = (
    "name", "pitch", "why", "niche", "pricing",
    "marketplaceUrl", "githubUrl", "firstPublished",
)


def die(msg: str) -> "NoReturn":  # noqa: F821
    sys.exit("[build_plugin_pages] ERROR: " + msg)


# =============================================================================
# 1. Parser tolerante de literales JS (objetos/arrays de catalog-shared.js)
# =============================================================================

class JsLiteralParser:
    """Lee un literal JS de objeto/array. Solo soporta lo que realmente hay
    en catalog-shared.js: strings, numeros, booleanos, null, objetos y
    arrays, con comentarios // y /* */ y claves sin comillas."""

    def __init__(self, src: str, pos: int):
        self.s = src
        self.i = pos

    def parse(self):
        self._ws()
        return self._value()

    def _ws(self):
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                if j < 0:
                    die("comentario /* sin cerrar en el literal JS")
                self.i = j + 2
            else:
                return

    def _value(self):
        c = self.s[self.i]
        if c == "{":
            return self._object()
        if c == "[":
            return self._array()
        if c in "\"'":
            return self._string()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        if self.s.startswith("null", self.i):
            self.i += 4
            return None
        m = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?").match(self.s, self.i)
        if not m:
            die("valor JS no reconocido en la posicion %d: %r" % (self.i, self.s[self.i:self.i + 40]))
        self.i = m.end()
        text = m.group(0)
        return float(text) if ("." in text or "e" in text or "E" in text) else int(text)

    def _object(self):
        out = {}
        self.i += 1  # '{'
        self._ws()
        if self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self._ws()
            key = self._string() if self.s[self.i] in "\"'" else self._ident()
            self._ws()
            if self.s[self.i] != ":":
                die("se esperaba ':' tras la clave %r" % key)
            self.i += 1
            self._ws()
            out[key] = self._value()
            self._ws()
            c = self.s[self.i]
            if c == ",":
                self.i += 1
                self._ws()
                if self.s[self.i] == "}":  # coma final
                    self.i += 1
                    return out
                continue
            if c == "}":
                self.i += 1
                return out
            die("se esperaba ',' o '}' tras el valor de %r" % key)

    def _array(self):
        out = []
        self.i += 1  # '['
        self._ws()
        if self.s[self.i] == "]":
            self.i += 1
            return out
        while True:
            self._ws()
            out.append(self._value())
            self._ws()
            c = self.s[self.i]
            if c == ",":
                self.i += 1
                self._ws()
                if self.s[self.i] == "]":
                    self.i += 1
                    return out
                continue
            if c == "]":
                self.i += 1
                return out
            die("se esperaba ',' o ']' dentro del array JS")

    def _ident(self):
        m = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*").match(self.s, self.i)
        if not m:
            die("clave JS invalida en la posicion %d" % self.i)
        self.i = m.end()
        return m.group(0)

    _ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "0": "\0"}

    def _string(self):
        quote = self.s[self.i]
        self.i += 1
        buf = []
        while True:
            c = self.s[self.i]
            if c == "\\":
                nxt = self.s[self.i + 1]
                if nxt == "u":
                    buf.append(chr(int(self.s[self.i + 2:self.i + 6], 16)))
                    self.i += 6
                elif nxt == "x":
                    buf.append(chr(int(self.s[self.i + 2:self.i + 4], 16)))
                    self.i += 4
                else:
                    buf.append(self._ESCAPES.get(nxt, nxt))
                    self.i += 2
                continue
            if c == quote:
                self.i += 1
                return "".join(buf)
            if c == "\n":
                die("salto de linea dentro de un string JS")
            buf.append(c)
            self.i += 1


def js_literal(src: str, name: str, label: str):
    m = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*", src)
    if not m:
        die("no se encontro `var %s =` en %s -- el renderer cambio, revisar antes de generar" % (name, label))
    return JsLiteralParser(src, m.end()).parse()


# =============================================================================
# 2. Helpers de render (puerto 1:1 de los de js/catalog-shared.js)
# =============================================================================

def esc(value) -> str:
    """Mismo escape que esc() en catalog-shared.js: & < > "."""
    if value is None:
        return ""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def safe_url(value) -> str:
    """Mismo gate que safeUrl(): solo http(s) sobrevive."""
    if value is None:
        return "#"
    text = str(value).strip()
    return text if re.match(r"^https?://", text, re.I) else "#"


def md_inline(text) -> str:
    """Puerto de mdInline(): **negrita** y pares de backticks."""
    out = esc(text).replace("\n", " ")
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    parts = out.split("`")
    if len(parts) < 3:
        return out
    rebuilt = parts[0]
    i = 1
    while i + 1 < len(parts):
        rebuilt += "<code>" + parts[i] + "</code>" + parts[i + 1]
        i += 2
    if i < len(parts):
        rebuilt += "`" + parts[i]
    return rebuilt


def md_block(text) -> str:
    """Parrafos + listas "- " + *cursiva* sobre md_inline (2026-09-27): el
    "why" completo de cada plugin trae citas en lista, no solo una linea."""
    blocks, items = [], []

    def inline(s):
        out = md_inline(s)
        return re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", out)

    def flush_items():
        if items:
            blocks.append('<ul class="pb-quotes">%s</ul>' % "".join("<li>%s</li>" % inline(i) for i in items))
            items.clear()

    for chunk in re.split(r"\n\s*\n", (text or "").strip()):
        for line in chunk.split("\n"):
            if line.startswith("- "):
                items.append(line[2:])
            elif line.strip():
                flush_items()
                blocks.append("<p>%s</p>" % inline(line))
        flush_items()
    return "".join(blocks) or "<p>—</p>"


def plain_text(value) -> str:
    """Igual que plain_text() de auto_update_catalog.py: markdown fuera."""
    text = "" if value is None else str(value)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


PITCH_PREFIX_RE = re.compile(r"^\s*(?:IntelliJ|JetBrains|VS Code|Visual Studio Code)[^.]{0,60}\b(?:plugin|extension)\.\s+")
PAIRED_DASH_RE = re.compile(r"\s+[—–]\s+([^—–.]{1,140}?)\s+[—–]\s+")
SINGLE_DASH_RE = re.compile(r"\s+(?:[—–]|--)\s+")


def pitch_prose(value) -> str:
    """Descripcion de un plugin tal como la muestra el sitio (2026-10-08). Sale del README y repite en todas el mismo
    molde: un prefijo de plataforma ("IntelliJ-family plugin.") que ya dice la ficha, y rayas largas para incisos y
    explicaciones. Aqui el prefijo se quita, un par de rayas pasa a parentesis y una raya suelta a dos puntos (o a coma
    si la frase ya tiene dos puntos). Solo para descripciones: la evidencia ("why") trae citas textuales y no pasa por
    aqui. Conserva el markdown en linea para md_inline()."""
    text = "" if value is None else str(value)
    text = PITCH_PREFIX_RE.sub("", text)
    text = PAIRED_DASH_RE.sub(lambda m: " (%s) " % m.group(1), text)

    def single(m):
        before = text[:m.start()]
        sentence = before[before.rfind(". ") + 1:]
        return ", " if ":" in sentence else ": "
    return SINGLE_DASH_RE.sub(single, text)


def pitch_text(value) -> str:
    """pitch_prose() sin markdown, para tarjetas, metadatos y el buscador."""
    return plain_text(pitch_prose(value))


def thousands(n) -> str:
    return "{:,}".format(int(n))


def truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rstrip()
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "…"


# =============================================================================
# 3. Fuentes: datos + mapas + shell
# =============================================================================

def load_prices(path, plugins):
    """{repo: yearly USD price} from data/plugin-prices.json, or {} when the file does not exist.

    The file is checked when it is read, so a typo fails the build instead of printing a wrong price: every key
    must be a PAID or FREEMIUM plugin of the catalog and every value a positive whole number of US dollars.
    """
    if not path.exists():
        return {}
    try:
        # utf-8-sig: PowerShell 5.1's Set-Content -Encoding utf8 and Notepad write a BOM, which plain utf-8 rejects
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError; neither message repeats the file's text
        die("%s: not valid UTF-8 JSON (%s)" % (path.name, exc))
    prices = raw.get("prices") if isinstance(raw, dict) else None
    if not isinstance(prices, dict):
        die("%s: expected an object with a \"prices\" object" % path.name)
    paid = {p.get("repo") for p in plugins if p.get("pricing") in ("PAID", "FREEMIUM")}
    out = {}
    for repo, entry in prices.items():
        if repo not in paid:
            die("%s: \"%s\" is not a paid or freemium plugin of the catalog" % (path.name, repo))
        usd = entry.get("yearUSD") if isinstance(entry, dict) else None
        if isinstance(usd, bool) or not isinstance(usd, int) or usd <= 0:
            die("%s: \"%s\".yearUSD must be a positive whole number of dollars" % (path.name, repo))
        out[repo] = usd
    return out


class Sources:
    def __init__(self):
        self.data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.plugins = self.data["plugins"]
        self.shared_js = SHARED_JS.read_text(encoding="utf-8")
        self.catalog_html = CATALOG_PAGE.read_text(encoding="utf-8")

        label = "js/catalog-shared.js"
        self.niche_to_category = js_literal(self.shared_js, "NICHE_TO_CATEGORY", label)
        self.gap_overrides = js_literal(self.shared_js, "GAP_OVERRIDES", label)
        self.demo_media = js_literal(self.shared_js, "DEMO_MEDIA", label)
        self.categories = js_literal(self.shared_js, "CATEGORIES", label)
        self.icons = js_literal(self.shared_js, "ICONS", label)
        self.cat_icon_inner = js_literal(self.shared_js, "CAT_ICON_INNER", label)
        if "calendar" not in self.icons:
            die("falta ICONS.calendar en js/catalog-shared.js (usado por el stat 'Published')")
        # Una entrada de demo pegada en el bloque equivocado (GAP_OVERRIDES en vez de DEMO_MEDIA, 2026-10-01) rompia
        # el render con un AttributeError en md_block y tres corridas del cron fallaron: se valida la forma al cargar.
        wrong_gap = sorted(k for k, v in self.gap_overrides.items() if not isinstance(v, str))
        if wrong_gap:
            die("GAP_OVERRIDES debe tener solo texto; no lo es en: %s (una entrada de DEMO_MEDIA en el bloque "
                "equivocado?)" % ", ".join(wrong_gap))
        wrong_demo = sorted(k for k, v in self.demo_media.items() if not isinstance(v, dict))
        if wrong_demo:
            die("DEMO_MEDIA debe tener solo objetos {poster, mp4, webm}; no lo es en: %s" % ", ".join(wrong_demo))

        self.prices = load_prices(PRICES_FILE, self.plugins)

        # Cross-reference real a VS Code, por el mismo slug de repo.
        self.vsx_by_repo = {}
        self.vsx_list = []
        if VSX_DATA_FILE.exists():
            vsx = json.loads(VSX_DATA_FILE.read_text(encoding="utf-8"))
            for e in vsx.get("extensions", []):
                if e.get("name"):
                    self.vsx_by_repo[e["name"]] = e
                    self.vsx_list.append(e)

        self.css = self._build_css()
        self.cat_color = self._resolve_category_colors()
        # Para el HTML: la variable CSS (se adapta a tema claro/oscuro). El hex
        # resuelto queda solo para build_og_images.py (render fuera del sitio).
        self.cat_var = {c["key"]: "var(%s)" % c["colorToken"] for c in self.categories}
        for p in self.plugins:
            p["categoryKey"] = self.niche_to_category.get(p.get("niche"), "other")
        self.cat_by_key = {c["key"]: c for c in self.categories}

    # ---- CSS -------------------------------------------------------------
    def _build_css(self) -> str:
        # Los <style> que viven dentro de un <noscript> son condicionales
        # por definicion (el del catalogo oculta el loader cuando no hay
        # JS): sacarlos de ahi los volveria incondicionales, asi que se
        # excluyen antes de extraer nada.
        without_noscript = re.sub(r"<noscript>.*?</noscript>", "", self.catalog_html, flags=re.S)
        blocks = re.findall(r"<style>(.*?)</style>", without_noscript, re.S)
        # 2026-09-27: el CSS principal del catalogo vive en /css/catalog.css
        # (antes era un <style> inline); los <style> inline que quedan se suman.
        catalog_css = ROOT / "css" / "catalog.css"
        if not catalog_css.exists():
            die("falta css/catalog.css -- shell cambiado")
        css = "\n".join([catalog_css.read_text(encoding="utf-8")] + blocks)
        # El dossier estatico usa <h1> donde el overlay usaba <h2>: una
        # pagina, un H1. Se amplia el selector en vez de duplicar la regla.
        css, n = re.subn(r"\.dossier-title-row h2\b", ".dossier-title-row :is(h1, h2)", css)
        if n != 1:
            die("se esperaba 1 regla `.dossier-title-row h2`, se encontraron %d" % n)
        return css + PLUGIN_PAGE_CSS

    def _resolve_category_colors(self) -> dict:
        """CATEGORIES guarda el nombre del token (--accent); en el navegador
        lo resuelve getComputedStyle. Aca se resuelve leyendo el :root."""
        # Los tokens de color viven en /css/theme.css desde 2026-09-27.
        theme = (ROOT / "css" / "theme.css").read_text(encoding="utf-8")
        root = re.search(r":root\s*\{(.*?)\}", theme, re.S)
        if not root:
            die("no se encontro un bloque :root en css/theme.css")
        tokens = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root.group(1)))
        colors = {}
        for cat in self.categories:
            token = cat["colorToken"]
            if token not in tokens:
                die("el token de color %s (categoria %s) no existe en :root" % (token, cat["key"]))
            colors[cat["key"]] = tokens[token].strip()
        return colors


PLUGIN_PAGE_CSS = """
/* 2026-09-27 (v2 de la parte baja): brecha a todo el ancho con citas,
   datos en grilla y relacionados con la tarjeta del catalogo. */
.pb-gap { margin-top: 24px; }
.pb-text p { margin: 0 0 12px; }
.pb-text p:last-child { margin-bottom: 0; }
.pb-text em { color: var(--text); }
.pb-quotes { display: grid; gap: 10px; margin: 4px 0 0; padding: 0; list-style: none; }
.pb-quotes li { padding: 12px 16px; border-left: 3px solid var(--accent); border-radius: 0 var(--radius) var(--radius) 0;
  background: var(--surface-2); color: var(--text-dim); font-size: 15px; line-height: 1.6; }
.pb-facts { margin-top: 16px; }
.pb-facts-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.pb-facts-head .pb-title { margin: 0; }
.pb-facts .pb-facts-head .share-row { margin: 0; padding: 0; border: 0; }
/* Facts: one row per datum with alternating bands (same table style as the home "Data" block).
   Platform and pricing are inline-SVG badges (pipeline/badges.py, styles in css/tw.css). */
.facts-table { margin: 0; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.facts-table .fact { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 4px 16px; align-items: center; min-height: 52px;
  padding: 10px 18px; border-top: 1px solid var(--border); }
.facts-table .fact:first-child { border-top: 0; }
.facts-table .fact:nth-child(odd) { background: var(--band-a); }
.facts-table .fact:nth-child(even) { background: var(--band-b); }
.facts-table dt { color: var(--text-dim); font: 600 12px var(--mono); letter-spacing: 0.06em; text-transform: uppercase; }
.facts-table dd { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0; color: var(--text); font: 600 15px var(--sans); overflow-wrap: anywhere; }
.facts-table dd code { padding: 1px 6px; border-radius: var(--radius); background: var(--surface-3); font: 500 13px var(--mono); }
@media (max-width: 640px) { .facts-table .fact { grid-template-columns: minmax(0, 1fr); } }
.similar-section { margin-top: 32px; }
.similar-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.similar-head h2.similar-title { margin: 0; }
.similar-all { color: var(--accent); font: 600 14px var(--sans); text-decoration: none; }
.similar-all:hover { text-decoration: underline; }
.similar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.rel-card { display: flex; flex-direction: column; gap: 8px; min-width: 0; padding: 20px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); color: var(--text); text-decoration: none;
  transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }
.rel-card:hover { border-color: var(--accent); box-shadow: var(--shadow-lg); }
.rel-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.rel-card .card-cat { position: static; display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 38px; height: 38px; border-radius: var(--radius); color: var(--cat); background: color-mix(in srgb, var(--cat) 12%, var(--surface)); }
.rel-card .card-cat svg { width: 20px; height: 20px; }
.rel-name { font: 600 16px / 1.3 var(--sans); }
.rel-niche { color: var(--text-faint); font: 500 13px var(--sans); }
.rel-pitch { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  margin: 0; color: var(--text-dim); font-size: 14px; line-height: 1.55; }
.rel-foot { display: flex; justify-content: space-between; gap: 10px; margin-top: auto; padding-top: 12px;
  border-top: 1px solid var(--border); color: var(--text-faint); font: 500 13px var(--sans); }
.rel-go { color: var(--accent); font-weight: 600; }
@media (prefers-reduced-motion: reduce) { .rel-card { transition: none; } .rel-card:hover { transform: none; } }
/* 2026-09-27: ficha con el sistema nuevo (encabezado de marca + tarjetas). */
.crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 16px 0 12px; color: var(--text-faint); font: 500 14px var(--sans); }
.crumbs a { color: var(--accent); text-decoration: none; }
.crumbs a:hover { text-decoration: underline; }
.plugin-hero.gh-page-header { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); align-items: center; gap: 32px 40px; margin: 0; }
.plugin-hero.no-media { grid-template-columns: 1fr; }
.plugin-hero.gh-page-header .ph-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 14px; }
.plugin-hero.gh-page-header .ph-title-row h1 { margin: 0; max-width: none; }
.plugin-hero .ph-niche { margin: 8px 0 0; color: var(--text-faint); font: 500 15px var(--sans); }
.plugin-hero .ph-lead { max-width: 60ch; margin: 14px 0 0; color: var(--text-dim); font-size: 17px; line-height: 1.65; }
.plugin-hero .ph-lead code, .pb-text code { padding: 1px 6px; border-radius: var(--radius); background: var(--surface-2); color: var(--text); font: 500 .9em var(--mono); }
.plugin-hero .ph-lead strong { color: var(--text); }
.ph-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.ph-actions .btn, .hire-band .btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border: 1px solid var(--border-strong);
  border-radius: var(--radius); background: var(--surface); color: var(--text); font: 600 14px var(--sans); text-decoration: none; text-transform: none; letter-spacing: 0; }
.ph-actions .btn:hover { border-color: var(--accent); }
.ph-actions .btn.primary, .hire-band .btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.ph-actions .btn.primary:hover, .hire-band .btn.primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
.ph-actions .btn-icon { display: inline-flex; }
.ph-actions .btn-icon svg { width: 16px; height: 16px; }
.ph-buy-note { margin: 12px 0 0; color: var(--text-dim); font-size: 13.5px; line-height: 1.5; }
.ph-stats { margin-top: 24px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
/* 2026-10-05: cuadro de cifras ~55% mas chico en area (ancho y alto a ~2/3).
   Los selectores llevan .ph-stats para ganarle a .hdr-stat de shell.css, que
   carga despues, sin tocar las cifras de la home. */
.ph-stats { max-width: 390px; }
.ph-stats .hdr-stat { gap: 2px; padding: 10px 13px; }
.ph-stats .hdr-stat-num { font-size: 17px; }
.ph-stats .hdr-stat-label { font-size: 11.5px; }
.ph-media { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow-lg); }
.ph-media img, .ph-media video { display: block; width: 100%; height: auto; }
.plugin-body { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); align-items: start; gap: 16px; margin-top: 24px; }
.pb-card { padding: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); }
.pb-title { display: flex; align-items: center; gap: 10px; margin: 0 0 12px; color: var(--text); font: 700 18px var(--sans); letter-spacing: 0; text-transform: none; }
.pb-text { color: var(--text-dim); font-size: 15.5px; line-height: 1.7; }
.pb-facts .facts-list { display: flex; flex-direction: column; margin: 0; padding: 0; list-style: none; }
.pb-facts .facts-list li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); font: 400 14px var(--sans); }
.pb-facts .facts-list li:last-child { border-bottom: 0; }
.pb-facts .fk { color: var(--text-faint); text-transform: none; letter-spacing: 0; font: 400 14px var(--sans); }
.pb-facts .fv { display: inline-flex; align-items: center; gap: 6px; min-width: 0; color: var(--text); font: 600 14px var(--sans); text-align: right; overflow-wrap: anywhere; }
.pb-facts .share-row { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.share-label { font: 600 12px var(--sans); letter-spacing: .06em; }
.share-btn { font-family: var(--sans); }
.similar-section { margin-top: 32px; }
h2.similar-title { margin: 0 0 16px; color: var(--text); font: 700 22px var(--sans); letter-spacing: 0; text-transform: none; }
.similar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.similar-card { display: flex; flex-direction: column; gap: 6px; padding: 18px; background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow); color: var(--text); text-decoration: none; transition: border-color .15s ease; }
.similar-card:hover { border-color: var(--accent); }
.similar-card .card-cat { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: var(--radius);
  color: var(--cat); background: color-mix(in srgb, var(--cat) 12%, var(--surface)); }
.similar-card .card-cat svg { width: 18px; height: 18px; }
.sc-name { font: 600 15px var(--sans); }
.sc-niche { color: var(--text-faint); font: 500 13px var(--sans); text-transform: none; letter-spacing: 0; }
.sc-dl { margin-top: auto; color: var(--text-dim); font: 500 13px var(--sans); }
.plugin-asof { margin: 20px 0 0; color: var(--text-faint); font-size: 13px; }
/* 2026-10-05: menos aire entre los relacionados y el footer (shell.css le da
   72px de margen al footer en todo el sitio; aca solo en las fichas). */
body .site-footer.gh-footer { margin-top: 24px; }
@media (max-width: 900px) {
  .plugin-hero.gh-page-header, .plugin-body { grid-template-columns: 1fr; }
  .ph-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
/* 2026-09-27: h2 semanticos (antes span/div) + banda de contratacion. */
h2.ib-title, h2.similar-title { margin: 0; font: inherit; font-weight: 700; color: inherit; }
.hire-band { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;
  margin-top: 24px; padding: 20px 22px; border: 1px solid var(--accent); border-radius: var(--radius);
  background: var(--surface); }
.hire-band > div { display: flex; flex-direction: column; gap: 4px; }
.hire-band strong { color: var(--text); font-size: 16px; }
.hire-band span { color: var(--text-dim); }

/* ------------------------------------------------------------------
   Generado por pipeline/build_plugin_pages.py -- NO editar a mano.
   Ajustes minimos para la ficha estatica: en el catalogo el dossier es
   un panel dentro de una pagina, aca es la pagina entera, y las tarjetas
   "similar" pasan de <div> con JS a <a> reales.
   ------------------------------------------------------------------ */
.plugin-page .dossier-sheet { margin: 0; }
.plugin-page .dossier-card { animation: none; }
.crumbs {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-family: var(--mono); font-size: 12px; color: var(--text-faint);
  margin: 0 0 var(--space-4);
}
.crumbs a { color: var(--text-dim); text-decoration: none; }
.crumbs a:hover { color: var(--accent); }
.crumbs [aria-current="page"] { color: var(--text); }
.crumb-sep { opacity: .55; }
a.similar-card, a.tbl-similar-card { text-decoration: none; color: inherit; }
.dossier-back { text-decoration: none; }
.plugin-asof {
  font-family: var(--mono); font-size: 11.5px; color: var(--text-faint);
  margin: var(--space-4) 0 0;
}
"""


# =============================================================================
# 4. Render de una ficha
# =============================================================================

class PluginRenderer:
    def __init__(self, src: Sources):
        self.src = src

    # ---- piezas portadas del dossier ------------------------------------
    def pricing_label(self, pricing, is_pending):
        if is_pending:
            return ("pending", "Pending")
        return {"FREE": ("free", "Free"),
                "FREEMIUM": ("freemium", "Freemium"),
                "PAID": ("paid", "Paid")}.get(pricing, ("free", pricing or "—"))

    def gap_text(self, p):
        return self.src.gap_overrides.get(p["repo"]) or p.get("why") or "—"

    def platform_of(self, p):
        m = re.match(r"^(IntelliJ[^.]*?plugin)\s*[.(]", p.get("pitch") or "")
        return m.group(1) if m else "IntelliJ-family"

    def marketplace_id(self, p):
        if not p.get("marketplaceUrl"):
            return None
        m = re.search(r"/plugin/(\d+)-", p["marketplaceUrl"])
        return m.group(1) if m else None

    # 2026-11-08: the plugin pages no longer show a "Growth" fact. Download
    # counts are now the raw Marketplace figure, so most plugins' first
    # stored value is the single review install, and a percentage over it
    # reads as thousands of percent. The catalog cards keep growth_markup(),
    # which already shows an absolute delta below GROWTH_PERCENT_MIN_BASELINE.
    def growth_markup(self, p):
        g = p.get("growth")
        title = ("Since %s: %s → %s" % (p.get("growthSince"), p.get("growthFrom"), p.get("downloads"))
                 if p.get("growthSince") else "No earlier snapshot")
        attr = ' title="%s"' % esc(title)
        if g is None:
            return '<span class="growth flat"%s>—</span>' % attr
        if p.get("growthFrom") is not None and p["growthFrom"] < GROWTH_PERCENT_MIN_BASELINE and p.get("downloads") is not None:
            delta = p["downloads"] - p["growthFrom"]
            if delta > 0:
                return '<span class="growth up"%s>▲ +%d</span>' % (attr, delta)
            if delta < 0:
                return '<span class="growth down"%s>▼ %d</span>' % (attr, delta)
            return '<span class="growth flat"%s>±0</span>' % attr
        if g > 0:
            return '<span class="growth up"%s>▲ %.1f%%</span>' % (attr, g)
        if g < 0:
            return '<span class="growth down"%s>▼ %.1f%%</span>' % (attr, abs(g))
        return '<span class="growth flat"%s>0%%</span>' % attr

    def cat_icon_html(self, key):
        inner = self.src.cat_icon_inner.get(key) or self.src.cat_icon_inner["other"]
        return '<svg viewBox="-8 -8 16 16" aria-hidden="true">%s</svg>' % inner

    def demo_media_html(self, repo, css_class, alt, *, eager=False, decorative=False):
        """<video> con poster+mp4+webm si hay una demo real; <img> con
        solo el poster si es un screenshot estatico (react-native-companion);
        '' si el plugin no tiene ninguno de los dos (Fase 3, 2026-09-23:
        las demos ahora viven en /media/<slug>/ de este mismo repo, no en
        raw.githubusercontent.com -- ver el comentario de DEMO_MEDIA en
        js/catalog-shared.js). decorative=True omite el texto alternativo
        (alt="" / sin aria-label) para cuando el nombre/niche ya son texto
        real justo al lado (el slider de la home) en vez de la unica pista
        de que plugin es (la ficha propia)."""
        media = self.src.demo_media.get(repo)
        if not media:
            return ""
        poster = media["poster"]
        alt_text = "" if decorative else ("%s in action" % alt)
        if "mp4" not in media:
            loading = "" if eager else ' loading="lazy"'
            return '<img class="%s" src="%s" alt="%s"%s decoding="async">' % (
                css_class, esc(poster), esc(alt_text), loading)
        preload = "metadata"  # 2026-09-27: el poster es el LCP; el video se carga al reproducirse
        aria = "" if decorative else (' aria-label="%s"' % esc(alt_text))
        return (
            '<video class="%s" poster="%s" muted loop playsinline autoplay preload="%s"%s>'
            '<source src="%s" type="video/webm"><source src="%s" type="video/mp4"></video>'
        ) % (css_class, esc(poster), preload, aria, esc(media["webm"]), esc(media["mp4"]))

    def similar_card_html(self, s):
        cat = self.src.cat_by_key.get(s["categoryKey"], self.src.cat_by_key["other"])
        color = self.src.cat_var[cat["key"]]
        pending = s.get("downloads") is None
        dl = "Pending moderation" if pending else thousands(s["downloads"]) + " downloads"
        price_key = "pending" if pending else (s.get("pricing") or "FREE").lower()
        price = "Pending" if pending else {"FREE": "Free", "FREEMIUM": "Freemium", "PAID": "Paid"}.get(s.get("pricing"), "Free")
        # No aria-label: visible text is the accessible name (WCAG 2.5.3).
        return (
            '<a class="rel-card" href="/catalog/%s/">'
            '<div class="rel-head"><span class="card-cat" style="--cat:%s" title="%s" aria-hidden="true">%s</span>'
            '<span class="price-badge price-%s">%s</span></div>'
            '<div class="rel-name">%s</div><div class="rel-niche">%s</div>'
            '<p class="rel-pitch">%s</p>'
            '<div class="rel-foot"><span>%s</span><span class="rel-go">Details</span></div></a>'
        ) % (esc(s["repo"]), color, esc(cat["label"]), self.cat_icon_html(s["categoryKey"]),
             price_key, price, esc(s["name"]), esc(s.get("niche")), esc(pitch_text(s.get("pitch")) or ""), dl)

    # ---- compartir --------------------------------------------------------
    # Enlaces planos (X, LinkedIn): no cargan ningun script de terceros ni
    # necesitan JS, asi que la CSP no cambia. "Copy link" si necesita JS
    # (plugin-page.js) y sale con [hidden]: sin JS/clipboard no se muestra un
    # boton muerto.
    def share_html(self, p, platform="IntelliJ IDEs"):
        url = "%s/catalog/%s/" % (SITE, p["repo"])
        kind = "plugin" if platform == "IntelliJ IDEs" else "extension"
        text = "%s — %s %s for %s" % (p["name"], plain_text(p.get("niche")) or "developer tooling", kind, platform)
        q = lambda s: urllib.parse.quote(s, safe="")
        x_url = "https://x.com/intent/post?text=%s&url=%s&via=GapHunterLabs" % (q(text), q(url))
        li_url = "https://www.linkedin.com/sharing/share-offsite/?url=%s" % q(url)
        return (
            '<div class="share-row" role="group" aria-label="Share this plugin">'
            '<span class="share-label">Share</span>'
            '<a class="share-btn share-icon" href="%s" target="_blank" rel="noopener" aria-label="Share %s on X" title="Share on X">%s</a>'
            '<a class="share-btn" href="%s" target="_blank" rel="noopener" aria-label="Share %s on LinkedIn">%s<span>LinkedIn</span></a>'
            '<button type="button" class="share-btn share-copy" data-copy="%s" hidden>%s<span>Copy link</span></button>'
            '</div>'
        ) % (esc(x_url), esc(p["name"]), SHARE_ICON_X, esc(li_url), esc(p["name"]), SHARE_ICON_LINKEDIN,
             esc(url), SHARE_ICON_LINK)

    # ---- cuerpo de la ficha ---------------------------------------------
    def body_html(self, p):
        # 2026-09-27: ficha reconstruida con el sistema nuevo -- encabezado de
        # marca (.gh-page-header) con acciones, cifras (.hdr-stats) y demo;
        # debajo "The gap it fixes" + datos y precio, relacionados y la banda
        # de contratacion. Se quito "What it does": repetia la bajada tal cual.
        src, icons = self.src, self.src.icons
        is_pending = p.get("downloads") is None
        pr_cls, pr_text = self.pricing_label(p.get("pricing"), is_pending)
        cat = src.cat_by_key.get(p["categoryKey"], src.cat_by_key["other"])
        mp_id = self.marketplace_id(p)
        is_paid = p.get("pricing") in ("FREEMIUM", "PAID")
        price_key = "pending" if is_pending else (p.get("pricing") or "FREE").lower()
        price_text = "Pending" if is_pending else {"FREE": "Free", "FREEMIUM": "Freemium", "PAID": "Paid"}.get(
            p.get("pricing"), pr_text)

        similar = sorted(
            (o for o in src.plugins
             if o["repo"] != p["repo"] and o["categoryKey"] == p["categoryKey"]),
            key=lambda o: o.get("downloads") or 0, reverse=True)[:SIMILAR_MAX]

        media = self.demo_media_html(p["repo"], "dossier-gif", p["name"], eager=True)
        h = []
        h.append('<nav class="crumbs" aria-label="Breadcrumb">'
                 '<a href="/">Home</a><span class="crumb-sep">›</span>'
                 '<a href="/catalog/">Catalog</a><span class="crumb-sep">›</span>'
                 '<span aria-current="page">%s</span></nav>' % esc(p["name"]))
        h.append('<header class="plugin-hero page-hero band-dark gh-page-header%s">' % ("" if media else " no-media"))
        h.append('<div class="ph-copy">')
        h.append('<p class="contact-kicker">%s &middot; JetBrains plugin</p>' % esc(cat["label"]))
        h.append('<div class="ph-title-row"><h1>%s</h1><span class="price-badge price-%s">%s</span></div>'
                 % (esc(p["name"]), price_key, esc(price_text)))
        h.append('<p class="ph-niche">%s</p>' % esc(p.get("niche")))
        h.append('<p class="ph-lead">%s</p>' % md_inline(pitch_prose(p.get("pitch")) or "—"))

        h.append('<div class="ph-actions">')
        if p.get("marketplaceUrl"):
            h.append('<a class="btn primary" href="%s" target="_blank" rel="noopener" data-goatcounter-click="out-%s-%s">'
                     '<span class="btn-icon">%s</span>%s ↗</a>'
                     % (esc(safe_url(p["marketplaceUrl"])), "trial" if is_paid else "install", esc(p["repo"]),
                        icons["jetbrains"], "Start free trial on JetBrains" if is_paid else "Install on JetBrains"))
        if is_paid:
            h.append('<a class="btn" href="/contact/?intent=license&amp;plugin=%s" data-goatcounter-click="cta-team-%s">'
                     'Ask about team licenses</a>' % (esc(p["repo"]), esc(p["repo"])))
        h.append('<a class="btn" href="%s" target="_blank" rel="noopener" data-goatcounter-click="out-github-%s">'
                 '<span class="btn-icon">%s</span>GitHub ↗</a>'
                 % (esc(safe_url(p.get("githubUrl"))), esc(p["repo"]), icons["github"]))
        vsx = src.vsx_by_repo.get(p["repo"])
        if vsx:
            h.append('<a class="btn" href="%s" target="_blank" rel="noopener">'
                     '<span class="btn-icon">%s</span>Also for VS Code ↗</a>'
                     % (esc(safe_url(vsx.get("marketplaceUrl"))), icons["vscode"]))
        h.append('</div>')
        if is_paid:
            # 2026-11-08: the price used to be missing from the page entirely ("Pricing: Paid"). Without a confirmed
            # figure the note still tells the visitor where the price and the trial are, and where the terms live.
            usd = self.src.prices.get(p["repo"])
            lead = ("From USD %s a year on JetBrains Marketplace, with a free trial." % thousands(usd) if usd
                    else "Price and free trial on JetBrains Marketplace.")
            h.append('<p class="ph-buy-note">%s <a href="/eula/">License terms (EULA)</a></p>' % lead)

        stat = lambda num, label: ('<div class="hdr-stat"><span class="hdr-stat-num">%s</span>'
                                   '<span class="hdr-stat-label">%s</span></div>' % (num, label))
        h.append('<div class="hdr-stats ph-stats">%s%s%s%s</div>' % (
            stat("—" if is_pending else thousands(p["downloads"]), "Downloads"),
            stat(p.get("stars") if p.get("stars") is not None else "—", "GitHub stars"),
            stat(esc(p.get("firstPublished") or "—"), "Published"),
            stat(esc(price_text), "Pricing")))
        h.append('</div>')
        if media:
            h.append('<div class="ph-media">%s</div>' % media)
        h.append('</header>')

        # 2026-09-27: la brecha va a todo el ancho y con su evidencia completa
        # (citas en lista); los datos pasan a una grilla y los relacionados
        # usan la misma tarjeta que el catalogo.
        h.append('<section class="pb-card pb-gap"><h2 class="pb-title">The gap it fixes</h2>'
                 '<div class="pb-text">%s</div></section>' % md_block(self.gap_text(p)))
        fact = lambda k, v: '<div class="fact"><dt>%s</dt><dd>%s</dd></div>' % (k, v)
        h.append('<section class="pb-card pb-facts"><div class="pb-facts-head"><h2 class="pb-title">Facts and pricing</h2>%s</div>'
                 '<dl class="facts-table">%s</dl></section>' % (self.share_html(p), "".join((
                     fact("Category", esc(cat["label"])),
                     fact("Pricing", price_badge(pr_cls, pr_text)),
                     fact("Platform", badge(self.platform_of(p), icon="jetbrains", variant="dark", extra_class="fact-data")),
                     fact("First published", esc(p.get("firstPublished") or "—")),
                     fact("Marketplace ID", ("#" + esc(mp_id)) if mp_id else ("Pending" if is_pending else "—")),
                     fact("Repository", '<code>%s</code><button type="button" class="copy-btn" data-copy="%s" '
                                        'aria-label="Copy repository name">%s</button>' % (esc(p["repo"]), esc(p["repo"]), icons["copy"])),
                 ))))

        if similar:
            h.append('<section class="similar-section"><div class="similar-head"><h2 class="similar-title">Related plugins</h2>'
                     '<a class="similar-all" href="/catalog/?category=%s">All %s plugins</a></div><div class="similar-grid">'
                     % (esc(cat["key"]), esc(cat["label"])))
            h.extend(self.similar_card_html(s) for s in similar)
            h.append('</div></section>')

        h.append('<div class="hire-band"><div><strong>Need a tool like this built for your codebase?</strong>'
                 '<span>Custom plugins and inspections, plugin updates and performance audits for IntelliJ plugins, at a fixed price.</span></div>'
                 '<a class="btn primary" href="/contact/?intent=hire&amp;service=custom&amp;plugin=%s" data-goatcounter-click="cta-plugin-hire-%s">'
                 'Ask for a quote</a></div>' % (esc(p["repo"]), esc(p["repo"])))
        h.append('<p class="plugin-asof">Download and star counts as of %s, refreshed twice daily '
                 'from the JetBrains Marketplace and GitHub APIs.</p>'
                 % esc((self.src.data.get("generatedAt") or "")[:10]))
        return "".join(h)

    # ---- fichas de extensiones VS Code (2026-09-27) ------------------------
    # Misma plantilla y estructura que las fichas JetBrains, en
    # /catalog/vscode/<name>/. VS Code Marketplace no cobra: todas son Free.
    def vsx_path(self, e):
        return "vscode/%s" % e["name"]

    def vsx_title(self, e):
        base = "%s for VS Code" % e["displayName"]
        branded = base + " | Gap Hunter Labs"
        return branded if len(branded) <= TITLE_SOFT_MAX else truncate(base, TITLE_SOFT_MAX)

    def vsx_description(self, e):
        text = pitch_text(e.get("pitch")) or ("%s for Visual Studio Code." % e["displayName"])
        limit = DESC_MAX
        result = truncate(text, limit)
        while len(esc(result)) > DESC_MAX and limit > 40:
            limit -= 10
            result = truncate(text, limit)
        return result

    def vsx_jsonld(self, e, url):
        app = {
            "@type": "SoftwareApplication", "@id": url + "#app", "name": e["displayName"], "url": url,
            "description": pitch_text(e.get("pitch")), "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Visual Studio Code", "publisher": {"@id": ORG_ID},
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "sameAs": [u for u in (e.get("marketplaceUrl"), e.get("githubUrl")) if u],
        }
        if e.get("marketplaceUrl"):
            app["downloadUrl"] = e["marketplaceUrl"]
        if e.get("version"):
            app["softwareVersion"] = e["version"]
        if e.get("publishedDate"):
            app["datePublished"] = e["publishedDate"][:10]
        crumbs = {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Catalog", "item": CATALOG_URL},
            {"@type": "ListItem", "position": 3, "name": "VS Code extensions", "item": CATALOG_URL + "?platform=vscode"},
            {"@type": "ListItem", "position": 4, "name": e["displayName"]}]}
        return json.dumps({"@context": "https://schema.org", "@graph": [app, crumbs]}, ensure_ascii=False)

    def vsx_card_html(self, o):
        n = o.get("installs") or 0
        # No aria-label: visible text is the accessible name (WCAG 2.5.3).
        return (
            '<a class="rel-card" href="/catalog/vscode/%s/">'
            '<div class="rel-head"><span class="card-cat" style="--cat:var(--accent)" aria-hidden="true">%s</span>'
            '<span class="price-badge price-free">Free</span></div>'
            '<div class="rel-name">%s</div><div class="rel-niche">%s</div><p class="rel-pitch">%s</p>'
            '<div class="rel-foot"><span>%s %s</span><span class="rel-go">Details</span></div></a>'
        ) % (esc(o["name"]), self.src.icons["vscode"], esc(o["displayName"]),
             esc(o.get("niche")), esc(pitch_text(o.get("pitch")) or ""), thousands(n), "install" if n == 1 else "installs")

    def vsx_body_html(self, e):
        src, icons = self.src, self.src.icons
        n = e.get("installs") or 0
        jb = next((p for p in src.plugins if p["repo"] == e["name"]), None)
        others = sorted((o for o in src.vsx_list if o["name"] != e["name"]),
                        key=lambda o: (o.get("niche") != e.get("niche"), -(o.get("installs") or 0)))[:SIMILAR_MAX]
        h = ['<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a><span class="crumb-sep">›</span>'
             '<a href="/catalog/">Catalog</a><span class="crumb-sep">›</span>'
             '<a href="/catalog/?platform=vscode">VS Code</a><span class="crumb-sep">›</span>'
             '<span aria-current="page">%s</span></nav>' % esc(e["displayName"])]
        h.append('<header class="plugin-hero page-hero band-dark gh-page-header no-media"><div class="ph-copy">')
        h.append('<p class="contact-kicker">VS Code extension</p>')
        h.append('<div class="ph-title-row"><h1>%s</h1><span class="price-badge price-free">Free</span></div>' % esc(e["displayName"]))
        h.append('<p class="ph-niche">%s</p>' % esc(e.get("niche")))
        h.append('<p class="ph-lead">%s</p>' % md_inline(pitch_prose(e.get("pitch")) or "—"))
        h.append('<div class="ph-actions">')
        if e.get("marketplaceUrl"):
            h.append('<a class="btn primary" href="%s" target="_blank" rel="noopener" data-goatcounter-click="out-vsx-install-%s">'
                     '<span class="btn-icon">%s</span>Install from VS Code Marketplace ↗</a>'
                     % (esc(safe_url(e["marketplaceUrl"])), esc(e["name"]), icons["vscode"]))
        if e.get("githubUrl"):
            h.append('<a class="btn" href="%s" target="_blank" rel="noopener" data-goatcounter-click="out-github-vsx-%s">'
                     '<span class="btn-icon">%s</span>GitHub ↗</a>' % (esc(safe_url(e["githubUrl"])), esc(e["name"]), icons["github"]))
        if jb:
            h.append('<a class="btn" href="/catalog/%s/"><span class="btn-icon">%s</span>Also for JetBrains IDEs</a>'
                     % (esc(jb["repo"]), icons["jetbrains"]))
        h.append('</div>')
        stat = lambda num, label: ('<div class="hdr-stat"><span class="hdr-stat-num">%s</span>'
                                   '<span class="hdr-stat-label">%s</span></div>' % (num, label))
        h.append('<div class="hdr-stats ph-stats">%s%s%s%s</div>' % (
            stat(thousands(n), "Installs"), stat(esc(e.get("version") or "—"), "Version"),
            stat(esc((e.get("publishedDate") or "—")[:10]), "Published"),
            stat(esc((e.get("lastUpdated") or "—")[:10]), "Last updated")))
        h.append('</div></header>')

        fact = lambda k, v: '<div class="fact"><dt>%s</dt><dd>%s</dd></div>' % (k, v)
        item = (e.get("marketplaceUrl") or "").split("itemName=")[-1]
        share_item = {"repo": self.vsx_path(e), "name": e["displayName"], "niche": e.get("niche")}
        h.append('<section class="pb-card pb-facts pb-gap"><div class="pb-facts-head"><h2 class="pb-title">Facts and pricing</h2>%s</div>'
                 '<dl class="facts-table">%s</dl></section>' % (self.share_html(share_item, platform="VS Code"), "".join((
                     fact("Platform", badge("Visual Studio Code", icon="vscode", variant="dark")),
                     fact("Pricing", price_badge("free", "Free")),
                     fact("Version", esc(e.get("version") or "—")),
                     fact("First published", esc((e.get("publishedDate") or "—")[:10])),
                     fact("Last updated", esc((e.get("lastUpdated") or "—")[:10])),
                     fact("Marketplace ID", "<code>%s</code>" % esc(item) if item else "—"),
                     fact("Repository", '<code>%s</code><button type="button" class="copy-btn" data-copy="%s" '
                                        'aria-label="Copy repository name">%s</button>' % (esc(e.get("repo") or ""), esc(e.get("repo") or ""), icons["copy"])),
                 ))))
        if others:
            h.append('<section class="similar-section"><div class="similar-head"><h2 class="similar-title">Related extensions</h2>'
                     '<a class="similar-all" href="/catalog/?platform=vscode">All VS Code extensions</a></div><div class="similar-grid">')
            h.extend(self.vsx_card_html(o) for o in others)
            h.append('</div></section>')
        h.append('<div class="hire-band"><div><strong>Need a tool like this built for your codebase?</strong>'
                 '<span>Custom plugins and inspections for your codebase, at a fixed price.</span></div>'
                 '<a class="btn primary" href="/contact/?intent=hire&amp;service=custom&amp;plugin=%s" data-goatcounter-click="cta-vsx-hire-%s">'
                 'Ask for a quote</a></div>' % (esc(e["name"]), esc(e["name"])))
        h.append('<p class="plugin-asof">Install counts as of %s, refreshed daily from the VS Code Marketplace API.</p>'
                 % esc((self.src.data.get("generatedAt") or "")[:10]))
        return "".join(h)

    # ---- metadatos -------------------------------------------------------
    def title(self, p):
        # Presupuesto de caracteres, no una plantilla fija: el nombre del
        # plugin ya varia entre 12 y 39 caracteres (p.ej. "Background
        # ReadAction Freeze Companion"), asi que "nombre + niche + cola"
        # puede pasarse de TITLE_SOFT_MAX antes de sumar la marca. Se
        # recorta el niche primero (lo menos importante para SEO), nunca
        # el nombre del plugin.
        name = p["name"]
        niche = plain_text(p.get("niche")) or "JetBrains"
        tail = " for IntelliJ"
        sep = " — "
        fixed_len = len(name) + len(sep) + len(tail)
        if fixed_len > TITLE_SOFT_MAX:
            # Ni siquiera nombre+cola entra: se cae la cola tambien.
            return truncate(name, TITLE_SOFT_MAX)
        budget = TITLE_SOFT_MAX - fixed_len
        niche_fit = niche if len(niche) <= budget else (truncate(niche, budget) if budget >= 4 else None)
        base = (name + sep + niche_fit + tail) if niche_fit else (name + tail)
        with_brand = base + " | Gap Hunter Labs"
        return with_brand if len(esc(with_brand)) <= TITLE_SOFT_MAX else base

    def description(self, p):
        text = pitch_text(p.get("pitch")) or plain_text(self.gap_text(p))
        # 35 pitches empiezan con "IntelliJ-family plugin." -- desperdicia el
        # inicio del snippet; el titulo ya dice "for IntelliJ".
        text = re.sub(r"^IntelliJ-family plugin\.\s*", "", text)
        # truncate() acota la longitud del texto plano, pero esc() (que
        # va a envolver este valor en un atributo HTML) puede inflarlo --
        # cada `"` o `&` que sobreviva al corte suma varios caracteres al
        # escapar. Encoger hasta que la version ESCAPADA (la que
        # verify_seo.py y un crawler realmente miden) entre en el limite.
        limit = DESC_MAX
        result = truncate(text, limit)
        while len(esc(result)) > DESC_MAX and limit > 40:
            limit -= 10
            result = truncate(text, limit)
        return result

    def jsonld(self, p, url):
        app = {
            "@type": "SoftwareApplication",
            "@id": url + "#app",
            "name": p["name"],
            "url": url,
            "description": pitch_text(p.get("pitch")),
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "IntelliJ Platform",
            "publisher": {"@id": ORG_ID},
        }
        same_as = [u for u in (p.get("marketplaceUrl"), p.get("githubUrl")) if u]
        vsx = self.src.vsx_by_repo.get(p["repo"])
        if vsx and vsx.get("marketplaceUrl"):
            same_as.append(vsx["marketplaceUrl"])
        if same_as:
            app["sameAs"] = same_as
        if p.get("marketplaceUrl"):
            app["downloadUrl"] = p["marketplaceUrl"]
        if p.get("firstPublished"):
            app["datePublished"] = p["firstPublished"]
        if p.get("pricing") == "FREE":
            app["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
        elif p.get("pricing") == "PAID" and self.src.prices.get(p["repo"]):
            app["offers"] = {"@type": "Offer", "price": str(self.src.prices[p["repo"]]), "priceCurrency": "USD"}
        # Sin aggregateRating a proposito: las valoraciones son de otro
        # sitio (Marketplace) y Google no admite ratings agregados de
        # terceros -- marcarlos es una violacion de sus guidelines, no un
        # rich result gratis.
        crumbs = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Catalog", "item": CATALOG_URL},
                {"@type": "ListItem", "position": 3, "name": p["name"]},
            ],
        }
        payload = {"@context": "https://schema.org", "@graph": [app, crumbs]}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return raw.replace("</script>", "<\\/script>")


# =============================================================================
# 5. Shell: se recorta del propio catalog/index.html
# =============================================================================

CATALOG_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json" id="catalog-jsonld">.*?</script>\s*', re.S)
# Tolera atributos previos a class="wrap" -- desde la Fase 0 de accesibilidad
# (2026-11-02) el <main> del shell lleva id="main-content" tabindex="-1" para el
# skip-link, y al conservar \1 cada ficha hereda ese landmark enfocable.
MAIN_RE = re.compile(r'(<main\b[^>]*\bclass="wrap">).*?(</main>)', re.S)
# Fase 2 (2026-09-22): catalog/index.html ya no tiene loader ni carga
# catalog-shared.js (su grid/tabla vienen pre-renderizados, ver
# pipeline/build_catalog_grid.py) -- el ancla pasa a ser vscode-catalog.js,
# el unico <script src> que le sigue quedando antes de sus scripts inline.
TAIL_SCRIPTS_RE = re.compile(
    r'<script src="/js/vscode-catalog\.js(?:\?v=[0-9a-f]+)?"></script>.*?(?=<script data-goatcounter)', re.S)
STYLE_RE = re.compile(r"<style>.*?</style>\s*", re.S)


class Shell:
    """Plantilla derivada de catalog/index.html. Cada recorte tiene su
    assert: si el shell cambia de forma, el build falla y lo dice."""

    def __init__(self, src: Sources):
        html = src.catalog_html

        def cut(pattern, replacement, label, expected=1):
            new, n = pattern.subn(replacement, html, count=expected)
            if n != expected:
                die("marcador del shell no encontrado: %s "
                    "(catalog/index.html cambio; revisar build_plugin_pages.py)" % label)
            return new

        # El shim hash -> ruta solo tiene sentido en el catalogo y en la
        # home: una ficha ya ES el destino, y su lista de 146 slugs pesa
        # mas que todo el resto del <head>.
        html = cut(re.compile(r'<script src="/js/slug-shim\.js(?:\?v=[0-9a-f]+)?" defer></script>\s*'),
                   "", "shim de slugs")
        html = cut(CATALOG_JSONLD_RE, "@@JSONLD@@\n", "catalog-jsonld")
        html = cut(TAIL_SCRIPTS_RE, '<script src="/js/plugin-page.js" defer></script>\n', "scripts del catalogo")
        html = cut(MAIN_RE, r"\1@@BODY@@\2", "<main class=\"wrap\">")

        # Todo el CSS inline pasa a /css/plugin.css: una descarga cacheada
        # por las 146 fichas en vez de ~107 KB repetidos en cada una.
        html = STYLE_RE.sub("", html)
        html = re.sub(r'<link rel="stylesheet" href="/css/catalog\.css(?:\?v=[0-9a-f]+)?">',
                      '<link rel="stylesheet" href="/css/plugin.css">', html, count=1)
        if "/css/plugin.css" not in html or "/css/theme.css" not in html:
            die("no se encontro el <link> a /css/catalog.css (o theme.css) para anclar plugin.css")

        html = html.replace('<html lang="en" class="boot">', '<html lang="en">', 1)
        if 'class="boot"' in html:
            die("la clase boot sigue presente tras quitar el loader")

        # Los comentarios del <head> de catalog/index.html son documentacion
        # de esa pagina (por que la CSP dice lo que dice, etc.): valiosos en
        # el fuente, 8 KB repetidos 146 veces aca. Se quitan solo de las
        # copias generadas; el original no se toca.
        # Se preservan los marcadores LANG:* : pipeline/build_i18n.py regenera
        # el selector de idioma entre ellos para /es/, de modo que las fichas
        # en espanol muestren el codigo "ES" y un nombre accesible coherente
        # (WCAG 2.5.3). Sin los marcadores, la copia ES heredaba el boton EN.
        html = re.sub(r"<!--(?!\[if)(?! LANG:).*?-->\s*", "", html, flags=re.S)
        for marker in ('<meta charset="UTF-8">', '@@BODY@@', '@@JSONLD@@',
                       'id="topbarBurger"', 'class="site-footer'):
            if marker not in html:
                die("se perdio %r al quitar los comentarios del shell" % marker)

        # El sidebar marca Catalog como pagina actual; en una ficha sigue
        # siendo la seccion activa, asi que se deja tal cual.
        html = self._swap_head(html)
        self.template = html

    @staticmethod
    def _swap_head(html: str) -> str:
        subs = [
            (r'<meta name="description" content="[^"]*">', '<meta name="description" content="@@DESC@@">', "description"),
            (r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="@@URL@@">', "canonical"),
            (r"<title>.*?</title>", "<title>@@TITLE@@</title>", "title"),
            (r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="@@URL@@">', "og:url"),
            (r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="@@OGTITLE@@">', "og:title"),
            (r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="@@DESC@@">', "og:description"),
            (r'<meta property="og:type" content="[^"]*">', '<meta property="og:type" content="article">', "og:type"),
            (r'<meta name="twitter:title" content="[^"]*">', '<meta name="twitter:title" content="@@OGTITLE@@">', "twitter:title"),
            (r'<meta name="twitter:description" content="[^"]*">', '<meta name="twitter:description" content="@@DESC@@">', "twitter:description"),
            (r'<meta property="og:image" content="[^"]*">', '<meta property="og:image" content="@@OGIMAGE@@">', "og:image"),
            (r'<meta property="og:image:secure_url" content="[^"]*">', '<meta property="og:image:secure_url" content="@@OGIMAGE@@">', "og:image:secure_url"),
            (r'<meta property="og:image:alt" content="[^"]*">', '<meta property="og:image:alt" content="@@OGIMAGEALT@@">', "og:image:alt"),
            (r'<meta name="twitter:image" content="[^"]*">', '<meta name="twitter:image" content="@@OGIMAGE@@">', "twitter:image"),
            (r'<meta name="twitter:image:alt" content="[^"]*">', '<meta name="twitter:image:alt" content="@@OGIMAGEALT@@">', "twitter:image:alt"),
        ]
        for pattern, replacement, label in subs:
            html, n = re.subn(pattern, replacement, html, count=1, flags=re.S)
            if n != 1:
                die("no se pudo reemplazar %s en el <head> del shell" % label)
        # 2026-10-05: las fichas tienen version en espanol (/es/catalogo/<slug>/,
        # la genera build_i18n.py). Los hreflang heredados del catalogo se
        # cambian por los de la propia ficha, y el selector de idioma apunta a
        # la ficha en cada idioma (antes "Espanol" llevaba al catalogo y el
        # sitio volvia al ingles al seguir navegando).
        html = re.sub(r'<link rel="alternate" hreflang="[^"]*" href="[^"]*">\s*', "", html)
        alt = ('<link rel="alternate" hreflang="en" href="%s@@PATH@@">\n'
               '<link rel="alternate" hreflang="es" href="%s@@ESPATH@@">\n'
               '<link rel="alternate" hreflang="x-default" href="%s@@PATH@@">\n') % (SITE, SITE, SITE)
        html, n = re.subn(r"(<link rel=\"canonical\" [^>]*>\n?)", lambda m: m.group(1) + alt, html, count=1)
        if n != 1:
            die("no se encontro el canonical del shell para colgar los hreflang")
        html, n = re.subn(r'href="/catalog/" hreflang="en"', 'href="@@PATH@@" hreflang="en"', html, count=1)
        if n != 1:
            die("no se encontro el enlace English del selector de idioma en el shell")
        html, n = re.subn(r'href="/es/catalogo/" hreflang="es"', 'href="@@ESPATH@@" hreflang="es"', html, count=1)
        if n != 1:
            die("no se encontro el enlace Espanol del selector de idioma en el shell")
        return html

    def render(self, *, title, og_title, desc, url, jsonld, body, og_image, og_image_alt):
        out = self.template
        out = out.replace("@@TITLE@@", esc(title))
        out = out.replace("@@OGTITLE@@", esc(og_title))
        out = out.replace("@@DESC@@", esc(desc))
        out = out.replace("@@URL@@", esc(url))
        path = url[len(SITE):] if url.startswith(SITE) else url
        out = out.replace("@@PATH@@", esc(path))
        # misma regla que build_chrome.es_path_for: /catalog/X/ -> /es/catalogo/X/
        out = out.replace("@@ESPATH@@", esc("/es/catalogo/" + path[len("/catalog/"):]
                                            if path.startswith("/catalog/") else "/es/catalogo/"))
        out = out.replace("@@OGIMAGE@@", esc(og_image))
        out = out.replace("@@OGIMAGEALT@@", esc(og_image_alt))
        out = out.replace("@@JSONLD@@",
                          '<script type="application/ld+json">%s</script>' % jsonld)
        out = out.replace("@@BODY@@", body)
        left = [m for m in re.findall(r"@@[A-Z]+@@", out)]
        if left:
            die("quedaron marcadores sin resolver en la plantilla: %s" % sorted(set(left)))
        return out


# =============================================================================
# 6. Sitemap
# =============================================================================

def rebuild_sitemap(slugs_with_lastmod, static_entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in static_entries:
        lines += ["  <url>", "    <loc>%s</loc>" % loc,
                  "    <lastmod>%s</lastmod>" % lastmod, "  </url>"]
    for slug, lastmod in slugs_with_lastmod:
        lines += ["  <url>", "    <loc>%s/catalog/%s/</loc>" % (SITE, slug),
                  "    <lastmod>%s</lastmod>" % lastmod, "  </url>"]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def read_static_entries():
    """Conserva las 6 URLs estaticas actuales con su lastmod real.
    changefreq/priority se descartan: Google no los usa desde hace anos."""
    text = SITEMAP.read_text(encoding="utf-8")
    entries = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text)
    static = [(loc, lastmod) for loc, lastmod in entries if "/catalog/" not in loc or loc.endswith("/catalog/")]
    if not any(loc == CATALOG_URL for loc, _ in static):
        die("sitemap.xml no tiene la entrada de /catalog/ -- auto_update_catalog.py depende de ella")
    # 2026-11-09: every English page that has a Spanish pair is in the sitemap. The static entries were added by
    # hand, and the English Blog never was (its Spanish pages were). A page added here keeps its lastmod afterwards.
    from build_chrome import ES_PATHS, SITE as CHROME_SITE  # noqa: WPS433
    have = {loc for loc, _ in static}
    today = date.today().isoformat()
    for path in ES_PATHS:
        if CHROME_SITE + path not in have and "/catalog/" not in path:
            static.append((CHROME_SITE + path, today))
    return static


# =============================================================================
# 7. Shim hash -> ruta
# =============================================================================

def inject_slugs(slugs, apply=True):
    payload = json.dumps(sorted(slugs), ensure_ascii=False, separators=(",", ","))
    touched, missing = [], []
    for rel in SLUG_INJECTION_TARGETS:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if SLUG_MARK_OPEN not in text:
            missing.append(rel)
            continue
        new = re.sub(
            re.escape(SLUG_MARK_OPEN) + r"\[.*?\]" + re.escape(SLUG_MARK_CLOSE),
            lambda _m: SLUG_MARK_OPEN + payload + SLUG_MARK_CLOSE,
            text, count=1, flags=re.S)
        if new == text:
            continue
        if apply:
            path.write_text(new, encoding="utf-8")
        touched.append(rel)
    return touched, missing


# =============================================================================
# 8. Main
# =============================================================================

def cmd_inspect(src: Sources):
    from collections import Counter
    keys = Counter()
    for p in src.plugins:
        keys.update(p.keys())
    print("plugins: %d  (generatedAt %s)" % (len(src.plugins), src.data.get("generatedAt")))
    print("\ncampos del JSON:")
    for k, c in keys.most_common():
        sample = next((p[k] for p in src.plugins if p.get(k) not in (None, "")), None)
        print("  %-16s %3d/%d  ej: %s" % (k, c, len(src.plugins), repr(sample)[:70]))
    print("\nmapas parseados de js/catalog-shared.js:")
    print("  NICHE_TO_CATEGORY %d  GAP_OVERRIDES %d  DEMO_MEDIA %d  CATEGORIES %d  ICONS %d"
          % (len(src.niche_to_category), len(src.gap_overrides), len(src.demo_media),
             len(src.categories), len(src.icons)))
    print("  colores resueltos: %s" % src.cat_color)
    print("  VS Code cross-refs: %d" % len(src.vsx_by_repo))
    unmapped = sorted({p["niche"] for p in src.plugins if p["categoryKey"] == "other"})
    if unmapped:
        print("\n  niches que caen en 'other' (%d): %s" % (len(unmapped), unmapped))
    bad = [p["repo"] for p in src.plugins
           if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", p.get("repo") or "")]
    if bad:
        print("\n  !! repos que no sirven como ruta: %s" % bad)
    dup = [r for r, c in Counter(p["repo"] for p in src.plugins).items() if c > 1]
    if dup:
        print("  !! repos duplicados: %s" % dup)


def main():
    ap = argparse.ArgumentParser(description="Genera /catalog/<slug>/index.html por plugin")
    ap.add_argument("--inspect", action="store_true", help="imprime el esquema real y sale")
    ap.add_argument("--dry-run", action="store_true", help="no escribe nada")
    ap.add_argument("--limit", type=int, default=0, help="genera solo las primeras N fichas")
    ap.add_argument("--sitemap", action="store_true", help="reescribe sitemap.xml")
    ap.add_argument("--inject", action="store_true", help="inyecta los slugs en el shim")
    args = ap.parse_args()

    src = Sources()
    if args.inspect:
        cmd_inspect(src)
        return

    seen = {}
    for p in src.plugins:
        slug = p.get("repo")
        if not slug or not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
            die("repo invalido como ruta: %r (plugin %r)" % (slug, p.get("name")))
        if slug in seen:
            die("repo duplicado: %r" % slug)
        seen[slug] = p

    renderer = PluginRenderer(src)
    shell = Shell(src)

    store = json.loads(LASTMOD_STORE.read_text(encoding="utf-8")) if LASTMOD_STORE.exists() else {}
    today = date.today().isoformat()
    rows = src.plugins if not args.limit else src.plugins[:args.limit]

    written, unchanged, lastmods = 0, 0, []
    for p in rows:
        slug = p["repo"]
        url = "%s/catalog/%s/" % (SITE, slug)
        # media/<slug>/og.png lo genera pipeline/build_og_images.py aparte
        # (necesita Chromium headless, no corre en cada build). Si todavia
        # no existe para este plugin, cae a la og-image.png generica en
        # vez de romper el <head>.
        has_own_og = (MEDIA_DIR / slug / "og.png").exists()
        og_image = "%s/media/%s/og.png?v=%s" % (SITE, slug, OG_VERSION) if has_own_og else OG_IMAGE
        og_image_alt = ("%s — Gap Hunter Labs" % p["name"]) if has_own_og else OG_IMAGE_ALT
        page = shell.render(
            title=renderer.title(p),
            # En una tarjeta social el nombre del plugin ya es el gancho;
            # el sufijo de categoria que ayuda en SERP solo estorba ahi.
            og_title="%s — Gap Hunter Labs" % p["name"],
            desc=renderer.description(p),
            url=url,
            jsonld=renderer.jsonld(p, url),
            body=renderer.body_html(p),
            og_image=og_image,
            og_image_alt=og_image_alt,
        )
        # Marca la pagina para que el CSS de la ficha pueda diferenciarse
        # del panel del catalogo sin duplicar reglas.
        page = page.replace('<div class="app-main">', '<div class="app-main plugin-page">', 1)

        fingerprint = json.dumps({k: p.get(k) for k in MATERIAL_FIELDS},
                                 ensure_ascii=False, sort_keys=True)
        prev = store.get(slug, {})
        lastmod = prev.get("lastmod", today) if prev.get("fingerprint") == fingerprint else today
        lastmods.append((slug, lastmod))
        store[slug] = {"fingerprint": fingerprint, "lastmod": lastmod}

        out = ROOT / "catalog" / slug / "index.html"
        if args.dry_run:
            written += 1
            continue
        if out.exists() and out.read_text(encoding="utf-8") == page:
            unchanged += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        written += 1

    # ---- fichas de extensiones VS Code (2026-09-27) --------------------------
    jb_slugs = [s for s, _ in lastmods]
    vsx_written = 0
    for e in ([] if args.limit else src.vsx_list):
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", e["name"]):
            die("nombre de extension invalido como ruta: %r" % e["name"])
        slug = renderer.vsx_path(e)
        url = "%s/catalog/%s/" % (SITE, slug)
        # media/vscode/<name>/og.png lo genera pipeline/build_og_images.py; sin el, cae a la generica.
        has_own_og = (MEDIA_DIR / slug / "og.png").exists()
        page = shell.render(
            title=renderer.vsx_title(e), og_title="%s — Gap Hunter Labs" % e["displayName"],
            desc=renderer.vsx_description(e), url=url, jsonld=renderer.vsx_jsonld(e, url),
            body=renderer.vsx_body_html(e),
            og_image="%s/media/%s/og.png?v=%s" % (SITE, slug, OG_VERSION) if has_own_og else OG_IMAGE,
            og_image_alt=("%s — VS Code extension — Gap Hunter Labs" % e["displayName"]) if has_own_og else OG_IMAGE_ALT)
        page = page.replace('<div class="app-main">', '<div class="app-main plugin-page">', 1)
        fingerprint = json.dumps({k: e.get(k) for k in ("displayName", "pitch", "niche", "version", "marketplaceUrl")},
                                 ensure_ascii=False, sort_keys=True)
        prev = store.get(slug, {})
        lastmod = prev.get("lastmod", today) if prev.get("fingerprint") == fingerprint else today
        lastmods.append((slug, lastmod))
        store[slug] = {"fingerprint": fingerprint, "lastmod": lastmod}
        out = ROOT / "catalog" / slug / "index.html"
        if args.dry_run or (out.exists() and out.read_text(encoding="utf-8") == page):
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        vsx_written += 1
    print("[build] %d fichas VS Code escritas -> catalog/vscode/<name>/index.html" % vsx_written)

    if args.dry_run:
        print("[dry-run] %d fichas renderizadas, nada escrito" % written)
        return

    CSS_OUT.write_text(src.css, encoding="utf-8")
    LASTMOD_STORE.parent.mkdir(parents=True, exist_ok=True)
    LASTMOD_STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print("[build] %d fichas escritas, %d sin cambios -> catalog/<slug>/index.html" % (written, unchanged))
    print("[build] css/plugin.css %d KB" % (len(src.css) // 1024))

    if args.sitemap:
        if args.limit:
            die("--sitemap con --limit generaria un sitemap incompleto")
        SITEMAP.write_text(rebuild_sitemap(lastmods, read_static_entries()), encoding="utf-8")
        print("[build] sitemap.xml: %d estaticas + %d fichas" % (len(read_static_entries()), len(lastmods)))

    if args.inject:
        touched, missing = inject_slugs(jb_slugs)   # el shim de rutas es solo de fichas JetBrains
        print("[build] shim actualizado en: %s" % (touched or "nada que actualizar"))
        if missing:
            print("[build] AVISO: falta el bloque %s en %s" % (SLUG_MARK_OPEN, missing))


if __name__ == "__main__":
    main()
