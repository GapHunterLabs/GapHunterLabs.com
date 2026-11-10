#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_i18n.py -- version nativa en espanol de las 10 paginas principales.

Genera /es/... a partir de la pagina inglesa YA construida (despues de
build_catalog_grid, build_home, build_plugin_pages y build_chrome), asi
que las cifras y listados pre-renderizados que actualiza el CI llegan
solos a la version en espanol. Correr ANTES de version_assets.py.

Como traduce:
  * Unidad de traduccion = el elemento mas externo que tiene texto propio y
    ningun bloque adentro (un <p>, un boton, un titulo...), no fragmentos.
  * Clave = su contenido normalizado: espacios colapsados, numeros -> {n},
    SVG -> {svg}, ?v=hash -> {v}. Asi una cifra que cambia no invalida la
    traduccion. Diccionario: pipeline/i18n/es.json (clave inglesa -> espanol).
  * Tambien traduce aria-label/title/placeholder/alt, <title> y las meta de
    descripcion/og/twitter.
  * No traduce datos: nombres y descripciones de plugins, IDs de tickets,
    la tabla del catalogo, codigo.
  * Reescribe los enlaces internos a su equivalente en espanol, el idioma,
    el canonical, og:url/og:locale y el selector de idioma.

Uso:
  python pipeline/build_i18n.py            # genera; avisa de lo que falte
  python pipeline/build_i18n.py --strict   # ademas falla si falta algo
  python pipeline/build_i18n.py --extract  # escribe pipeline/i18n/es.todo.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_chrome import ES_PATHS, SITE, LANG_START, LANG_END, lang_switch_html, es_path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DICT_PATH = ROOT / "pipeline" / "i18n" / "es.json"
TODO_PATH = ROOT / "pipeline" / "i18n" / "es.todo.json"

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "param"}
BLOCK = {"address", "article", "aside", "blockquote", "details", "dialog", "dd", "div", "dl", "dt", "fieldset",
         "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
         "nav", "ol", "p", "pre", "section", "table", "ul", "tbody", "thead", "tr", "td", "th", "summary", "video",
         "picture", "select", "textarea", "iframe", "canvas", "noscript", "script", "style", "template", "option", "title"}
OPAQUE = {"script", "style", "svg", "pre", "textarea", "template", "noscript"}
SKIP_CLASSES = {"card-pitch", "card-name", "card-niche", "hs-name", "hs-niche", "paid-niche", "sc-name", "sc-niche",
                "ticket-id", "code-window", "gh-brand-name", "gh-lang",
                # fichas de plugin (2026-10-05): datos del plugin y de los relacionados
                "ph-niche", "ph-lead", "pb-text", "rel-name", "rel-niche", "rel-pitch", "fact-data",
                # patrocinadores (2026-10-29): nombres propios que carga data/sponsors.json
                "sp-name",
                # writing (2026-11-03): el cuerpo del articulo se autora en ES
                # directamente (flujo bilingue), no via diccionario. translate()
                # salta este <main>; main() le inserta el <main> ES de es-main.html.
                "writing-article"}
SKIP_IDS = {"tbody"}
SKIP_IN = {"paid-card": {"h3", "p"}, "fact": {"code"}, "fact-data": {"span"}}   # ancestro con clase -> etiquetas de datos adentro
ATTRS = ("aria-label", "title", "placeholder", "alt")
META = ('name="description"', 'property="og:title"', 'property="og:description"', 'name="twitter:title"',
        'name="twitter:description"', 'property="og:image:alt"', 'name="twitter:image:alt"')


class Node:
    __slots__ = ("tag", "attrs", "start", "open_end", "close_start", "end", "children", "parent")

    def __init__(self, tag, attrs, start, open_end, parent):
        self.tag, self.attrs, self.start, self.open_end, self.parent = tag, dict(attrs), start, open_end, parent
        self.close_start = self.end = open_end
        self.children = []

    def classes(self):
        return set((self.attrs.get("class") or "").split())


class TreeBuilder(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.line_starts = [0]
        for m in re.finditer("\n", text):
            self.line_starts.append(m.end())
        self.root = Node("#root", [], 0, 0, None)
        self.root.close_start = self.root.end = len(text)
        self.stack = [self.root]

    def _abs(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self._abs()
        node = Node(tag, attrs, start, start + len(self.get_starttag_text()), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        start = self._abs()
        node = Node(tag, attrs, start, start + len(self.get_starttag_text()), self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        start = self._abs()
        end = self.text.index(">", start) + 1
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                for node in self.stack[i + 1:]:          # cierres implicitos
                    node.close_start = node.end = start
                self.stack[i].close_start, self.stack[i].end = start, end
                del self.stack[i:]
                return


def parse(text):
    tb = TreeBuilder(text)
    tb.feed(text)
    tb.close()
    return tb.root


# ---- normalizacion de claves -------------------------------------------------
NUM_RE = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")  # "24, 2026" -> 24 y 2026 (la coma queda en el texto)


def normalize(fragment):
    """-> (clave, valores): SVG/hash/numeros pasan a marcadores."""
    frag = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    vals = {"svg": [], "v": [], "n": []}

    def keep_svg(m):
        vals["svg"].append(m.group(0))
        return "{svg}"
    frag = re.sub(r"<svg\b.*?</svg>", keep_svg, frag, flags=re.S)

    def keep_v(m):
        vals["v"].append(m.group(1))
        return "?v={v}"
    frag = re.sub(r"\?v=([0-9a-f]+)", keep_v, frag)
    out = []
    for part in re.split(r"(<[^>]+>)", frag):
        if part.startswith("<"):
            out.append(part)
        else:
            def keep_n(m):
                vals["n"].append(m.group(0))
                return "{n}"
            out.append(NUM_RE.sub(keep_n, re.sub(r"\s+", " ", part)))
    key = re.sub(r"\s+", " ", "".join(out)).strip()
    return key, vals


# 2026-10-19: separador de miles en espanol. "10,500" -> "10.500" y "1,234.5" -> "1.234,5".
# Solo cambian las cifras agrupadas por miles: una version como "2026.3" no tiene coma y queda igual.
# Aplica a lo que se traduce; los datos que se dejan en ingles (descripciones, evidencias) no pasan por aca.
GROUPED_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def es_number(value):
    if not GROUPED_RE.fullmatch(value):
        return value
    return value.replace(",", "\0").replace(".", ",").replace("\0", ".")


def restore(template, vals):
    it = {k: iter(v) for k, v in vals.items()}
    out = re.sub(r"\{svg\}", lambda m: next(it["svg"], ""), template)
    out = re.sub(r"\?v=\{v\}", lambda m: "?v=" + next(it["v"], ""), out)
    return re.sub(r"\{n\}", lambda m: es_number(next(it["n"], "")), out)


# Patrones para textos que llevan un nombre propio adentro (evita 146 entradas).
PATTERNS = (
    (re.compile(r"^(.+) details$"), r"Detalles de \1"),
    (re.compile(r"^Show (.+)$"), r"Mostrar \1"),
    (re.compile(r"^Share (.+) on (X|LinkedIn)$"), r"Compartir \1 en \2"),
    # titulos de las fichas (2026-10-05; nombre y nicho son datos)
    (re.compile(r"^(.+) — (.+) for IntelliJ \| Gap Hunter Labs$"), r"\1 — \2 para IntelliJ | Gap Hunter Labs"),
    (re.compile(r"^(.+) for VS Code \| Gap Hunter Labs$"), r"\1 para VS Code | Gap Hunter Labs"),
    (re.compile(r"^(.+) — Gap Hunter Labs$"), r"\1 — Gap Hunter Labs"),
    (re.compile(r"^(.+) — (.+) for IntelliJ$"), r"\1 — \2 para IntelliJ"),
    (re.compile(r"^(.+) for IntelliJ$"), r"\1 para IntelliJ"),
    (re.compile(r"^(.+) in action$"), r"\1 en acción"),
)


def plugin_names():
    names = set()
    for rel, key in (("data/catalog-data.json", "name"), ("data/vscode-catalog-data.json", "displayName")):
        f = ROOT / rel
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data.get("plugins") or data.get("extensions") or []
            names.update(i.get(key) for i in items if i.get(key))
    return names


NAMES = plugin_names()
# los nombres con cifras ("AWS S3", "K8s", "N+1") llegan normalizados ({n})
NAMES_NORM = {NUM_RE.sub("{n}", n) for n in NAMES}


def lookup(key, table):
    """Traduccion de una clave: diccionario, patron o nombre propio (se deja igual)."""
    if table.get(key):
        return table[key]
    for rx, repl in PATTERNS:
        if rx.match(key):
            return rx.sub(repl, key)
    if key in NAMES or key in NAMES_NORM:
        return key
    return None


def has_letters(key):
    stripped = re.sub(r"<[^>]+>|\{svg\}|\{n\}|\{v\}|&[a-z#0-9]+;", "", key)
    return re.search(r"[A-Za-z]", stripped) is not None


# ---- recorrido ---------------------------------------------------------------
def skipped(node):
    cls = node.classes()
    if cls & SKIP_CLASSES or node.attrs.get("id") in SKIP_IDS:
        return True
    anc = node.parent
    while anc is not None:
        for c, tags in SKIP_IN.items():
            if c in anc.classes() and node.tag in tags:
                return True
        anc = anc.parent
    return False


def has_block(node):
    return any(c.tag in BLOCK or has_block(c) for c in node.children)


def direct_segments(node, text):
    """Trozos de texto directo de un nodo: (inicio, fin)."""
    segs, pos = [], node.open_end
    for c in node.children:
        segs.append((pos, c.start))
        pos = c.end
    segs.append((pos, node.close_start))
    return [(a, b) for a, b in segs if b > a]


def has_direct_text(node, text):
    return any(re.sub(r"<!--.*?-->", "", text[a:b], flags=re.S).strip() for a, b in direct_segments(node, text))


def collect(node, text, units):
    """Units are (start, end, element): element is the node that holds the whole text, or None for loose text
    inside a mixed block (that text has no element of its own, so it gets no contextual key)."""
    if node.tag in OPAQUE or skipped(node):
        return
    if node.tag != "#root" and node.tag not in VOID and has_direct_text(node, text) and not has_block(node):
        units.append((node.open_end, node.close_start, node))
        return
    if node.tag != "#root" and node.tag not in VOID and has_direct_text(node, text):
        for a, b in direct_segments(node, text):          # texto suelto en un bloque mixto
            if re.sub(r"<!--.*?-->", "", text[a:b], flags=re.S).strip():
                units.append((a, b, None))
    for c in node.children:
        collect(c, text, units)


# ---- claves con contexto (2026-11-09) ---------------------------------------
# The table is keyed by text alone, so one English string gets one Spanish string everywhere. A key written
# "[ctx:<class>] <text>" applies only to an element that has that class, and wins over the plain key there.
# Case: the header link "Sponsors" must read "Patrocinio" (it has to fit the header at 961 px), while the sponsor
# wall headings keep "Patrocinadores"; the header link "Plugins" reads "Herramientas".
# The prefix is one no page text starts with ("::" was the first choice and is real text: Class::method).
CONTEXT_PREFIX = "[ctx:"
CONTEXT_KEY_RE = re.compile(r"^\[ctx:([a-z0-9][a-z0-9_-]*)\] (\S.*)$", re.S)


def context_key(cls, key):
    return "%s%s] %s" % (CONTEXT_PREFIX, cls, key)


def check_table(table):
    """Fail fast on a malformed contextual key, naming it, before any page is translated."""
    bad = [k for k in table if k.startswith(CONTEXT_PREFIX) and not CONTEXT_KEY_RE.match(k)]
    if bad:
        sys.exit("[build_i18n] ERROR: contextual keys must look like \"[ctx:<class>] <text>\": %s"
                 % ", ".join(repr(k[:60]) for k in bad))
    empty = [k for k in table if CONTEXT_KEY_RE.match(k) and not str(table[k]).strip()]
    if empty:
        sys.exit("[build_i18n] ERROR: contextual keys without a translation: %s" % ", ".join(repr(k[:60]) for k in empty))


def stale_context_keys(table, used):
    """Contextual keys no page used. That means the class was renamed or removed: the element now falls back to
    the plain key without any warning, which is what the contextual key was there to prevent. --strict fails."""
    return sorted(k for k in table if CONTEXT_KEY_RE.match(k) and k not in used)


def lookup_in_context(key, node, table, used):
    """The contextual translation for this element, or None. Classes are tried in sorted order so the result
    does not depend on the order they are written in the HTML."""
    if node is None:
        return None
    for cls in sorted(node.classes()):
        ck = context_key(cls, key)
        if table.get(ck):
            used.add(ck)
            return table[ck]
    return None


# ---- traduccion de una pagina ------------------------------------------------
def translate(text, table, missing, page, used_context=None):
    used_context = set() if used_context is None else used_context
    root = parse(text)
    units = []
    collect(root, text, units)
    edits = []
    for a, b, node in units:
        frag = text[a:b]
        key, vals = normalize(frag)
        if not key or not has_letters(key):
            lone = frag.strip()
            if GROUPED_RE.fullmatch(lone):      # a figure on its own ("12,770") takes the Spanish separator too
                edits.append((a, b, frag.replace(lone, es_number(lone))))
            continue
        tr = lookup_in_context(key, node, table, used_context)
        if tr is None:
            tr = lookup(key, table)
        if tr is not None:
            lead = re.match(r"\s*", frag).group(0)
            trail = re.search(r"\s*$", frag).group(0)
            edits.append((a, b, lead + restore(tr, vals) + trail))
        else:
            missing.setdefault(key, set()).add(page)
    for a, b, new in sorted(edits, reverse=True):
        text = text[:a] + new + text[b:]

    # atributos
    def attr_sub(m):
        key, vals = normalize(m.group(2))
        if not has_letters(key):
            return m.group(0)
        tr = lookup(key, table)
        if tr is not None:
            return '%s="%s"' % (m.group(1), restore(tr, vals))
        missing.setdefault(key, set()).add(page)
        return m.group(0)

    def tag_sub(m):
        tag = m.group(0)
        if tag.startswith("<svg") or tag.startswith("<path") or 'class="sp-logo-img"' in tag:   # el alt del logo es un nombre propio
            return tag
        return re.sub(r'\b(%s)="([^"]*)"' % "|".join(ATTRS), attr_sub, tag)
    text = re.sub(r"<(?!/|!|script|style)[a-zA-Z][^>]*>", tag_sub, text)

    for sel in META:
        def meta_sub(m):
            key, vals = normalize(m.group(2))
            tr = lookup(key, table)
            if tr is not None:
                return m.group(1) + restore(tr, vals) + m.group(3)
            # en las fichas, description/og:description eran la descripcion del plugin en ingles (dato, no
            # interfaz). Desde 2026-11-09 la ficha espanola lleva una descripcion en espanol armada con datos del
            # catalogo (nombre, nicho, plataforma, precio), para que el resultado de busqueda salga en espanol.
            if page in PLUGIN_PAGES and "description" in sel:
                es = pitch_description_es(page)
                if es is not None:
                    return m.group(1) + es + m.group(3)
                missing.setdefault("plugin description of " + page + " (pipeline/i18n/plugin-pitches.es.json)",
                                   set()).add(page)
                es = plugin_description_es(page, table)   # red de seguridad fuera de --strict
                if es is not None:
                    return m.group(1) + es + m.group(3)
            missing.setdefault(key, set()).add(page)
            return m.group(0)
        text = re.sub(r'(<meta %s content=")([^"]*)(")' % re.escape(sel), meta_sub, text, count=1)
    return text


# ---- fichas de plugin (2026-10-05) -------------------------------------------
def plugin_pages():
    """Fichas inglesas que existen en disco -> [(ruta_en, ruta_es)]."""
    out = []
    for f in sorted((ROOT / "catalog").glob("*/index.html")) + sorted((ROOT / "catalog" / "vscode").glob("*/index.html")):
        en_path = "/" + f.parent.relative_to(ROOT).as_posix() + "/"
        es_path = es_path_for(en_path)
        if es_path and en_path not in ES_PATHS:
            out.append((en_path, es_path))
    return out


PLUGIN_PAGES = dict(plugin_pages())

PRICING_ES = {"FREE": "gratis", "FREEMIUM": "gratis, con versión Pro", "PAID": "de pago"}
DESC_MAX = 170


def _catalog_entries():
    """{ruta inglesa de la ficha: (nombre, nicho, plataforma, precio)} desde los datos del catalogo."""
    out = {}
    jb = json.loads((ROOT / "data" / "catalog-data.json").read_text(encoding="utf-8"))
    for p in jb.get("plugins", []):
        out["/catalog/%s/" % p["repo"]] = (p["name"], p.get("niche", ""), "jetbrains", p.get("pricing", ""))
    vs = json.loads((ROOT / "data" / "vscode-catalog-data.json").read_text(encoding="utf-8"))
    for e in vs.get("extensions", []):
        out["/catalog/vscode/%s/" % e["name"]] = (e["displayName"], e.get("niche", ""), "vscode", "FREE")
    return out


_CATALOG = None


def plugin_description_es(en_path, table):
    """Descripcion en espanol de una ficha (70-170 caracteres), o None si la ficha no esta en los datos."""
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _catalog_entries()
    entry = _CATALOG.get(en_path)
    if entry is None:
        return None
    name, niche, platform, pricing = entry
    niche_es = (lookup(normalize(niche)[0], table) or niche) if niche else ""
    if platform == "vscode":
        head = "%s: extensión gratuita para VS Code" % name
        tail = "Qué hace, capturas, instalaciones y enlace al VS Code Marketplace."
    else:
        head = "%s: plugin %s para IntelliJ IDEA y los demás IDE de JetBrains" % (name, PRICING_ES.get(pricing, ""))
        head = head.replace("plugin  para", "plugin para")
        tail = "Qué hace, capturas, precio, descargas y enlace a JetBrains Marketplace."
    if niche_es:
        head += " (%s)" % niche_es
    text = "%s. %s" % (head, tail)
    if len(text) > DESC_MAX:
        text = head + "."
    return html_escape_attr(text)


def html_escape_attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


# ---- descripciones de plugins en espanol (2026-11-09) --------------------------------------------------------------
# pipeline/i18n/plugin-pitches.es.json guarda, por plugin, el texto ingles de origen (pitch_prose del dato) y su
# traduccion. Si el dato ingles cambia, la traduccion queda vieja y cuenta como faltante (--strict falla).
PITCHES_FILE = Path(__file__).resolve().parent / "i18n" / "plugin-pitches.es.json"
_PITCH = None


def _pitch_tables():
    """(por ruta inglesa: (texto es, texto en vigente o None si esta vieja), por html ingles de bloque: html espanol)."""
    global _PITCH
    if _PITCH is not None:
        return _PITCH
    from build_plugin_pages import pitch_prose, pitch_text, plain_text, md_inline, esc  # noqa: WPS433
    stored = json.loads(PITCHES_FILE.read_text(encoding="utf-8"))
    by_path, blocks, stale = {}, {}, []
    jb = json.loads((ROOT / "data" / "catalog-data.json").read_text(encoding="utf-8")).get("plugins", [])
    vs = json.loads((ROOT / "data" / "vscode-catalog-data.json").read_text(encoding="utf-8")).get("extensions", [])
    rows = [("jetbrains:" + p["repo"], "/catalog/%s/" % p["repo"], p.get("pitch")) for p in jb]
    rows += [("vscode:" + e["name"], "/catalog/vscode/%s/" % e["name"], e.get("pitch")) for e in vs]
    for key, path, pitch in rows:
        entry = stored.get(key)
        prose = pitch_prose(pitch)
        if entry is None or entry["en"] != prose.strip():
            stale.append(key)
            continue
        es = entry["es"]
        by_path[path] = es
        blocks[('ph-lead', md_inline(prose or "") or "—")] = md_inline(es)
        blocks[('card-pitch', esc(pitch_text(pitch) or ""))] = esc(plain_text(es))
        blocks[('rel-pitch', esc(pitch_text(pitch) or ""))] = esc(plain_text(es))
        blocks[('jsonld', pitch_text(pitch) or "")] = plain_text(es)   # SoftwareApplication.description, sin recortar
    _PITCH = (by_path, blocks, stale)
    return _PITCH


def pitch_description_es(en_path):
    """meta description de la ficha espanola desde su traduccion, con el mismo recorte que la inglesa."""
    from build_plugin_pages import plain_text, truncate, esc, DESC_MAX as PLUGIN_DESC_MAX  # noqa: WPS433
    es = _pitch_tables()[0].get(en_path)
    if es is None:
        return None
    text = plain_text(es)
    limit = PLUGIN_DESC_MAX
    result = truncate(text, limit)
    while len(esc(result)) > PLUGIN_DESC_MAX and limit > 40:
        limit -= 10
        result = truncate(text, limit)
    return esc(result)


PITCH_BLOCK_RE = re.compile(r'(<p class="(ph-lead|card-pitch|rel-pitch)">)(.*?)(</p>)', re.S)
JSONLD_DESC_RE = re.compile(r'("description":\s*")((?:[^"\\]|\\.)*)(")')
META_DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
_JSONLD = None


def _jsonld_descriptions():
    """{descripcion inglesa de la ficha (la del JSON-LD y la meta): descripcion espanola}."""
    global _JSONLD
    if _JSONLD is None:
        import html as _html
        _JSONLD = {}
        for path in _pitch_tables()[0]:
            page = ROOT / path.strip("/") / "index.html"
            m = META_DESC_RE.search(page.read_text(encoding="utf-8")) if page.exists() else None
            if m:
                _JSONLD[_html.unescape(m.group(1))] = _html.unescape(pitch_description_es(path))
    return _JSONLD


def translate_pitches(text, page, missing):
    """Pasa a espanol la descripcion de cada plugin que aparece en la pagina (entradilla, tarjetas, relacionados)."""
    blocks = _pitch_tables()[1]

    def sub(m):
        es = blocks.get((m.group(2), m.group(3)))
        if es is None:
            if m.group(3).strip() not in ("", "—"):
                missing.setdefault("plugin description block (%s) on %s" % (m.group(2), page), set()).add(page)
            return m.group(0)
        return m.group(1) + es + m.group(4)
    text = PITCH_BLOCK_RE.sub(sub, text)
    table = _jsonld_descriptions()

    def jsonld_sub(m):
        try:
            value = json.loads('"%s"' % m.group(2))
        except ValueError:
            return m.group(0)
        es = table.get(value) or blocks.get(("jsonld", value))
        return m.group(0) if es is None else m.group(1) + json.dumps(es, ensure_ascii=False)[1:-1] + m.group(3)
    return JSONLD_DESC_RE.sub(jsonld_sub, text)


# ---- ajustes estructurales ---------------------------------------------------
def localize_links(text):
    def href_sub(m):
        url = m.group(1)
        path, sep, rest = re.match(r"([^?#]*)([?#]?)(.*)", url).groups()
        if path in ES_PATHS:
            return 'href="%s%s%s"' % (ES_PATHS[path], sep, rest)
        if path in PLUGIN_PAGES:
            return 'href="%s%s%s"' % (PLUGIN_PAGES[path], sep, rest)
        return m.group(0)
    # el selector de idioma se regenera aparte; los <link> del <head> no se tocan
    head, body = text.split("</head>", 1)
    body = re.sub(r'href="(/[^"]*)"', href_sub, body)
    return head + "</head>" + body


JSONLD_TRANSLATABLE = ('"FAQPage"', '"Article"', '"TechArticle"')


def translate_jsonld_text(text, table):
    """Traduce los campos de texto (name/text/headline/description) de los
    bloques JSON-LD de FAQPage/Article/TechArticle via el diccionario. Hace
    falta porque <script> esta en OPAQUE y translate() lo copia tal cual del
    ingles. Solo actua en bloques que contienen uno de esos @type; el resto
    del JSON-LD (Organization, SoftwareApplication, BreadcrumbList) queda
    intacto. Cada campo usa normalize/lookup/restore igual que el resto de la
    pagina, asi que reutiliza las mismas claves (p. ej. el H1 y la meta
    description ya traducidos)."""
    def script_sub(m):
        block = m.group(0)
        if not any(t in block for t in JSONLD_TRANSLATABLE):
            return block

        def field_sub(fm):
            try:
                s = json.loads('"' + fm.group(2) + '"')
            except ValueError:
                return fm.group(0)
            key, vals = normalize(s)
            if not has_letters(key):
                return fm.group(0)
            tr = lookup(key, table)
            if tr is None:
                return fm.group(0)
            return fm.group(1) + json.dumps(restore(tr, vals), ensure_ascii=False)[1:-1] + fm.group(3)

        return re.sub(r'("(?:name|text|headline|description)":\s*")((?:[^"\\]|\\.)*)(")', field_sub, block)

    return re.sub(r'<script type="application/ld\+json">.*?</script>', script_sub, text, flags=re.S)


def structural(text, en_path, es_path, table):
    text = text.replace('<html lang="en"', '<html lang="es"', 1)
    en_url, es_url = SITE + en_path, SITE + es_path
    text = text.replace('<link rel="canonical" href="%s">' % en_url, '<link rel="canonical" href="%s">' % es_url, 1)
    text = text.replace('<meta property="og:url" content="%s">' % en_url, '<meta property="og:url" content="%s">' % es_url, 1)
    text = text.replace('<meta property="og:locale" content="en_US">',
                        '<meta property="og:locale" content="es_ES">\n<meta property="og:locale:alternate" content="en_US">', 1)
    # Imagen social propia en espanol: og-X.png -> og-X.es.png (og:image,
    # og:image:secure_url y twitter:image). Las genera pipeline/build_page_og.py.
    # Las fichas de plugin usan /media/<slug>/og.png (sin el prefijo "og-"),
    # asi que este patron no las toca.
    text = re.sub(r'(/og-[a-z0-9-]+)\.png', r'\1.es.png', text)
    text = localize_links(text)
    text = re.sub(re.escape(LANG_START) + r".*?" + re.escape(LANG_END),
                  lambda _m: lang_switch_html("es", en_path, es_path), text, count=1, flags=re.S)
    text = translate_jsonld_text(text, table)
    return text


def ensure_sitemap(today):
    """Agrega al sitemap las URLs en espanol que falten (despues de las
    estaticas inglesas y antes de las fichas); no toca las existentes."""
    sitemap = ROOT / "sitemap.xml"
    text = sitemap.read_text(encoding="utf-8")
    entries = re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text)
    have = {loc for loc, _ in entries}
    # fichas en espanol: mismo lastmod que su ficha inglesa (se sincroniza en
    # cada corrida, porque build_plugin_pages solo mueve el lastmod ingles)
    en_lastmod = dict(entries)
    plugin_es = {SITE + es: en_lastmod.get(SITE + en, today) for en, es in PLUGIN_PAGES.items()}
    synced = [(loc, plugin_es.get(loc, lm)) for loc, lm in entries]
    missing = [SITE + p for p in ES_PATHS.values() if SITE + p not in have]
    missing_plugins = [loc for loc in plugin_es if loc not in have]
    if not missing and not missing_plugins and synced == entries:
        return 0
    entries = synced
    static = [e for e in entries if "/catalog/" not in e[0] or e[0].endswith("/catalog/")]
    rest = [e for e in entries if e not in static]
    ordered = (static + [(loc, today) for loc in missing] + rest
               + [(loc, plugin_es[loc]) for loc in missing_plugins])
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in ordered:
        lines += ["  <url>", "    <loc>%s</loc>" % loc, "    <lastmod>%s</lastmod>" % lastmod, "  </url>"]
    lines.append("</urlset>")
    sitemap.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(missing) + len(missing_plugins)


def file_for(path):
    return ROOT / ("index.html" if path == "/" else path.strip("/") + "/index.html")


WRITING_MAIN_RE = re.compile(r"<main\b[^>]*\bwriting-article\b[^>]*>.*?</main>", re.S)


def apply_writing_es_body(out, en_path):
    """Articulos de /writing (flujo bilingue): translate() salta el <main>
    marcado writing-article; aqui se reemplaza ese <main> por el <main> en
    espanol autorado a mano en writing/<slug>/es-main.html. El cuerpo del
    articulo asi es bilingue de verdad y no vive en es.json (2026-11-03)."""
    if not (en_path.startswith("/writing/") and en_path != "/writing/"):
        return out
    slug = en_path.strip("/").split("/", 1)[1]
    body_file = ROOT / "writing" / slug / "es-main.html"
    if not body_file.exists():
        sys.exit("[build_i18n] falta el <main> ES autorado: %s" % body_file)
    es_main = body_file.read_text(encoding="utf-8").strip()
    out, n = WRITING_MAIN_RE.subn(lambda _m: es_main, out, count=1)
    if n != 1:
        sys.exit("[build_i18n] no pude insertar el <main> ES de %s (writing-article)" % en_path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--extract", action="store_true")
    args = ap.parse_args()
    table = json.loads(DICT_PATH.read_text(encoding="utf-8")) if DICT_PATH.exists() else {}
    check_table(table)
    missing: dict[str, set] = {}
    for key in _pitch_tables()[2]:   # dato ingles cambiado o plugin nuevo sin traduccion
        missing.setdefault("plugin description %s: stale or missing in pipeline/i18n/plugin-pitches.es.json" % key,
                           set()).add("data")
    used_context: set = set()
    for en_path, es_path in list(ES_PATHS.items()) + list(PLUGIN_PAGES.items()):
        src = file_for(en_path).read_text(encoding="utf-8")
        out = structural(translate_pitches(translate(src, table, missing, en_path, used_context), en_path, missing),
                         en_path, es_path, table)
        out = apply_writing_es_body(out, en_path)
        if not args.extract:
            dest = file_for(es_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(out, encoding="utf-8")
    if args.extract:
        TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
        TODO_PATH.write_text(json.dumps({k: "" for k in sorted(missing)}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[build_i18n] %d textos sin traducir -> %s" % (len(missing), TODO_PATH.relative_to(ROOT)))
        return 0
    from datetime import date
    added = ensure_sitemap(date.today().isoformat())
    print("[build_i18n] %d paginas en espanol generadas; %d textos sin traducir; %d URLs nuevas en el sitemap"
          % (len(ES_PATHS) + len(PLUGIN_PAGES), len(missing), added))
    if missing:
        for k in sorted(missing)[:15]:
            print("   sin traducir:", k[:110])
    stale = stale_context_keys(table, used_context)
    for k in stale:
        print("   clave de contexto sin uso:", k[:110])
    return 1 if (args.strict and (missing or stale)) else 0


if __name__ == "__main__":
    sys.exit(main())
