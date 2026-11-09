import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parents[1]

# 2026-09-10 (clean-URL migration): real content now lives at
# <page>/index.html so GitHub Pages serves it at /<page>/ with no
# ".html" in the address bar. The old top-level *.html files (still
# named PAGES' display names below for readability) are now tiny
# client-side redirect stubs, checked separately further down --
# they're no longer the same file as the content page.
PAGES = (
    ("index.html", "index.html"),
    ("catalog.html", "catalog/index.html"),
    ("methodology.html", "methodology/index.html"),
    ("contact.html", "contact/index.html"),
    ("security.html", "security/index.html"),
    ("engineering-evidence", "engineering-evidence/index.html"),
    ("case-studies", "engineering-evidence/case-studies/index.html"),
    ("jetbrains-platform-tickets", "engineering-evidence/jetbrains-platform-tickets/index.html"),
    ("privacy.html", "privacy/index.html"),
    ("terms.html", "terms/index.html"),
)
# Patrones de texto que nunca deben aparecer en una pagina publica. La
# lista vive FUERA de este repo publico (un archivo local del operador,
# una expresion regular por linea) para que el propio chequeo no publique
# lo que protege. Ruta configurable con GHL_PROHIBITED_PATTERNS_FILE; si
# el archivo no existe (p. ej. en CI) este chequeo se omite con aviso.
import os
_patterns_file = Path(os.environ.get(
    "GHL_PROHIBITED_PATTERNS_FILE",
    ROOT.parent / "pipeline" / "site_prohibited_patterns.txt",
))
if _patterns_file.is_file():
    _lines = [l.strip() for l in _patterns_file.read_text(encoding="utf-8").splitlines()]
    PROHIBITED = re.compile("|".join(l for l in _lines if l and not l.startswith("#")))
else:
    print(f"AVISO: {_patterns_file} no existe; se omite el chequeo de texto prohibido")
    PROHIBITED = re.compile(r"(?!x)x")  # no coincide con nada
# Regression guard for the clean-URL migration itself: these are the
# exact relative asset references that were real bugs the first time
# (they broke the moment the page moved into a subdirectory) -- a
# future edit re-introducing a relative form of any of these would
# silently 404 for every visitor on a migrated page.
RELATIVE_ASSET_REGRESSION = re.compile(
    r'(?:href|src)="(?:css/shell\.css|js/catalog-shared\.js|js/vscode-catalog\.js)"'
    r'|url\("fonts/'
)

for display_name, rel_path in PAGES:
    text = (ROOT / rel_path).read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", text, re.S | re.I)
    # application/ld+json and speculationrules are data, not code (a bare
    # object literal isn't valid top-level JS), so they're allowed inline.
    # Everything else must be an external /js/*.js file: since 2026-09-24
    # the CSP's script-src has NO 'unsafe-inline', so an inline executable
    # script would simply not run in the browser (silently -- the page still
    # renders, the feature just dies). This is the regression guard for that.
    NON_EXECUTABLE_TYPES = ("application/ld+json", "speculationrules")
    inline_exec = [body for attrs, body in scripts if not any(t in attrs for t in NON_EXECUTABLE_TYPES)]
    assert not inline_exec, (display_name, "script inline ejecutable: la CSP ya no tiene 'unsafe-inline'; moverlo a /js/")
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', text).group(1)
    script_src = re.search(r"script-src ([^;]*)", csp).group(1)
    assert "'unsafe-inline'" not in script_src, (display_name, "script-src volvio a permitir 'unsafe-inline'")
    for src in re.findall(r'<script[^>]*\bsrc="(/[^"]*)"', text):
        assert (ROOT / src.lstrip("/").split("?", 1)[0]).is_file(), (display_name, "script inexistente", src)
    print(f"{display_name}: no inline scripts, CSP script-src = {script_src}")
    assert not PROHIBITED.search(text), display_name
    assert not RELATIVE_ASSET_REGRESSION.search(text), (display_name, "relative asset path regression")
    for tag in ("html", "head", "body"):
        opens = len(re.findall(rf"<{tag}[ >]", text, re.I))
        closes = len(re.findall(rf"</{tag}>", text, re.I))
        assert opens == closes == 1, (display_name, tag, opens, closes)

# Los scripts que antes vivian inline ahora son archivos: se sigue verificando
# que TODOS parseen (new Function no ejecuta nada, solo compila).
for js_file in sorted((ROOT / "js").glob("*.js")):
    subprocess.run(
        ["node", "-e",
         f"new Function(require('fs').readFileSync({json.dumps(str(js_file))},'utf8'));"
         f"console.log('js/{js_file.name}: syntax OK')"],
        check=True,
    )

# Todo `shared.X` que un script pide a catalog-shared.js (GapCatalog.ready)
# tiene que ser un export real: el rail de /security/ leia shared.GIF_URL,
# renombrado a DEMO_MEDIA en la Fase 3, y el TypeError resultante lo
# tragaba un .catch -- el rail quedo oculto durante dias sin que nada fallara.
shared_src = (ROOT / "js" / "catalog-shared.js").read_text(encoding="utf-8")
api_start = shared_src.index("var api = {")
api_block = shared_src[api_start:shared_src.index("};", api_start)]
exports = set(re.findall(r"^\s+([A-Za-z_]+):", api_block, re.M))
assert {"DEMO_MEDIA", "plugins", "esc"} <= exports, ("no pude leer el objeto api de catalog-shared.js", sorted(exports))
for js_file in sorted((ROOT / "js").glob("*.js")):
    if js_file.name == "catalog-shared.js":
        continue
    # (?<![-/\w]) y (?!js\b): no confundir "catalog-shared.js" (un nombre de
    # archivo en un comentario) con un acceso a la propiedad shared.<export>.
    used = set(re.findall(r"(?<![-/\w])shared\.(?!js\b)([A-Za-z_]+)", js_file.read_text(encoding="utf-8")))
    missing_exports = sorted(u for u in used if u not in exports)
    assert not missing_exports, (js_file.name, "pide a catalog-shared.js exports que no existen", missing_exports)

# The two shared JS modules must fetch their JSON data with an absolute
# path -- a relative fetch('data/...') resolves against the *page's*
# URL, so it 404s the instant the calling page moves into a
# subdirectory (catalog/, etc.) while working fine from the root. This
# was a real bug caught during the migration; guard against it coming
# back.
for js_name, expected in (
    ("catalog-shared.js", "fetch('/data/catalog-data.json'"),
    ("vscode-catalog.js", "fetch('/data/vscode-catalog-data.json'"),
):
    js_text = (ROOT / "js" / js_name).read_text(encoding="utf-8")
    assert expected in js_text, (js_name, "expected absolute fetch path")

data = json.loads((ROOT / "data/catalog-data.json").read_text(encoding="utf-8"))
catalog = (ROOT / "catalog" / "index.html").read_text(encoding="utf-8")
jsonld = json.loads(
    re.search(
        r'<script type="application/ld\+json" id="catalog-jsonld">(.*?)</script>',
        catalog,
        re.S,
    ).group(1)
)
# Fase 2 (2026-09-22): ya no hay noscript de respaldo -- pipeline/
# build_catalog_grid.py pre-renderiza la grilla y la tabla reales, asi
# que ESE es ahora el contenido que ve un crawler/usuario sin JS. La
# paridad se verifica contra las tarjetas y filas reales, no contra una
# lista aparte.
counts = (
    data["totalPlugins"],
    len(data["plugins"]),
    jsonld["mainEntity"]["numberOfItems"],
    len(re.findall(r'class="plugin-card"', catalog)),
)
assert len(set(counts)) == 1, counts
# 2026-09-27: las filas de la tabla las arma js/catalog.js; no deben volver
# a pre-renderizarse (duplicaban la grilla completa).
assert not re.search(r'<tr class="row"', catalog), "la tabla del catalogo volvio a pre-renderizarse"

sitemap_text = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
ElementTree.parse(ROOT / "sitemap.xml")
for slug in ("catalog", "methodology", "contact", "security", "engineering-evidence",
             "engineering-evidence/case-studies", "engineering-evidence/jetbrains-platform-tickets", "privacy", "terms"):
    assert f"https://gaphunterlabs.com/{slug}/</loc>" in sitemap_text, (
        "sitemap.xml missing clean-URL entry for", slug
    )
    assert f"{slug}.html" not in sitemap_text, ("sitemap.xml still has an old .html URL for", slug)

# Migración en curso a un shell con sidebar persistente (ver
# css/shell.css): las páginas ya migradas reemplazan #topbarNav
# (Catalog/Methodology/Contact) por #appSidebar (Home/Catalog/
# Methodology/Contact). Este chequeo entiende ambas generaciones -- lo
# detecta por qué id existe en la página, no por una lista fija, para
# no crashear a mitad de la migración.
# "Insights" (link + #insights anchor en index.html) sacado del sidebar
# 2026-09-10 a pedido explícito -- esa sección ya se había borrado del
# index antes (ver "borra esto del index" en el historial), el link
# quedaba apuntando a un anchor huérfano.
# "Laboratorie" (laboratorio.html) agregado al sidebar el mismo día --
# página nueva con los case studies curados a mano del catálogo. Nombre
# del nav renombrado de "Lab" a "Laboratorie" horas después, a pedido
# explícito del usuario.
# security.html no tiene entrada propia en el sidebar de 5 ítems (se
# llega vía el footer nav / el botón "Security Report" de contact) --
# por eso su active esperado es None, no falta un ítem.
# 2026-09-27: la barra lateral se reemplazo por un encabezado horizontal
# (pipeline/build_chrome.py). "Laboratorie" paso a "Engineering & Evidence",
# un submenu con Overview + 2 subpaginas (pedido explicito del usuario).
# Security/Privacy/Terms viven en el pie: su enlace activo se marca ahi.
# 2026-10-19 (rediseno): Work / Engineering / Tools / Services / Contact.
# Methodology y las paginas de evidencia pasan al submenu de Engineering
# (6 items); las rutas no cambian. Ver pipeline/build_chrome.py.
# 2026-11-09: Services / Evidence / Plugins / Sponsors / Blog / Contact; Methodology goes last in the
# Evidence menu. This list had been failing since 2026-11-04, when Blog joined the header without it.
import html as _html
TOP_LABELS = ["Services", "Evidence", "Plugins", "Sponsors", "Blog", "Contact"]
SUB_LABELS = ["Evidence overview", "JetBrains Platform tickets", "Open-source security reports", "Third-party plugin audits", "Plugin case studies", "Methodology"]
for display_name, rel_path, active, footer_active in (
    ("index.html", "index.html", None, None),
    ("catalog.html", "catalog/index.html", "Plugins", None),
    ("methodology.html", "methodology/index.html", "Methodology", None),
    ("engineering-evidence", "engineering-evidence/index.html", "Evidence overview", None),
    ("case-studies", "engineering-evidence/case-studies/index.html", "Plugin case studies", None),
    ("jetbrains-platform-tickets", "engineering-evidence/jetbrains-platform-tickets/index.html", "JetBrains Platform tickets", None),
    ("security.html", "security/index.html", None, "Security"),
    ("contact.html", "contact/index.html", "Contact", None),
    ("privacy/index.html", "privacy/index.html", None, "Privacy"),
    ("terms/index.html", "terms/index.html", None, "Terms"),
):
    text = (ROOT / rel_path).read_text(encoding="utf-8")
    assert 'id="appSidebar"' not in text, (display_name, "quedo la barra lateral vieja")
    nav = re.search(r'<nav class="gh-nav" id="siteNav"[^>]*>(.*?)</nav>', text, re.S).group(1)
    clean = lambda frag: _html.unescape(re.sub("<.*?>", "", frag)).strip()
    top = [clean(m) for m in re.findall(r'<(?:a|button) [^>]*class="gh-nav-link[^"]*"[^>]*>(.*?)</(?:a|button)>', nav, re.S)]
    assert top == TOP_LABELS, (display_name, top)
    subs = [clean(m) for m in re.findall(r'<a class="gh-pop-link"[^>]*><strong>(.*?)</strong>', nav, re.S)]
    assert subs == SUB_LABELS, (display_name, subs)
    current = [clean(m) for m in re.findall(r'<a[^>]*aria-current="page"[^>]*>(?:<strong>)?(.*?)(?:</strong>.*?)?</a>', nav, re.S)]
    assert current == ([] if active is None else [active]), (display_name, current)
    footer = re.search(r'<footer class="site-footer[^"]*">(.*?)</footer>', text, re.S).group(1)
    fcur = [clean(m) for m in re.findall(r'<a[^>]*aria-current="page"[^>]*>(.*?)</a>', footer, re.S)]
    assert fcur == ([] if footer_active is None else [footer_active]), (display_name, "pie", fcur)
    assert 'data-theme-choice="system"' in text and "/js/theme-init.js" in text, (display_name, "falta el selector de tema")

# Redirect stubs: the 5 old top-level *.html URLs (already indexed by
# search engines) must keep working as redirects to their new clean
# URL rather than disappearing outright -- explicit user decision
# during the clean-URL migration. Verify each stub actually points at
# its matching new location and preserves query/hash (deep links like
# catalog.html#some-repo-slug or security.html#sec-report must keep
# resolving after the redirect).
REDIRECT_STUBS = (
    ("catalog.html", "/catalog/"),
    ("methodology.html", "/methodology/"),
    ("contact.html", "/contact/"),
    ("security.html", "/security/"),
    ("laboratorio.html", "/engineering-evidence/"),
    ("laboratorio/index.html", "/engineering-evidence/"),
)
for stub_name, target in REDIRECT_STUBS:
    stub_text = (ROOT / stub_name).read_text(encoding="utf-8")
    for tag in ("html", "head", "body"):
        opens = len(re.findall(rf"<{tag}[ >]", stub_text, re.I))
        closes = len(re.findall(rf"</{tag}>", stub_text, re.I))
        assert opens == closes == 1, (stub_name, tag, opens, closes)
    assert f'content="0; url={target}"' in stub_text, (stub_name, "missing meta refresh")
    assert f'href="https://gaphunterlabs.com{target}"' in stub_text, (stub_name, "missing canonical")
    # Fase 0/4 del SuperPlan de SEO (2026-09-23): noindex removido a
    # proposito -- un meta refresh de 0s ya se procesa como redireccion
    # permanente, y noindex junto a canonical en el mismo documento son
    # senales contradictorias.
    assert 'noindex' not in stub_text, (stub_name, "el noindex volvio; el refresh de 0s ya basta como redireccion")
    assert f"location.replace('{target}' + location.search + location.hash)" in stub_text, (
        stub_name, "missing/incorrect JS redirect with query+hash preservation"
    )

print({
    "script_pages": len(PAGES),
    "catalog_counts": counts,
    "navigation": "passed",
    "redirect_stubs": len(REDIRECT_STUBS),
})
