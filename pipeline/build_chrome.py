#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_chrome.py -- encabezado (top nav) y pie compartidos del sitio.

Una sola fuente para la navegacion de las 8 paginas hechas a mano (home,
catalogo, contacto, metodologia, Laboratorio, seguridad, privacidad,
terminos). Las 146 fichas heredan el encabezado y el pie del catalogo via
build_plugin_pages.py, asi que despues de correr esto hay que regenerarlas.

Reemplaza el contenido entre marcadores <!-- CHROME:HEADER:START/END -->
y <!-- CHROME:FOOTER:START/END -->. La primera vez (sin marcadores)
reemplaza la barra superior + barra lateral y el <footer> anteriores.
Tambien asegura /js/theme-init.js (sin defer) y /js/site-chrome.js (defer)
en el <head>.

Anclas que build_plugin_pages.py exige y que este script conserva:
id="topbar", id="topbarBurger" y class="site-footer".

Uso: python pipeline/build_chrome.py [--check]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (archivo, enlace activo del encabezado, enlace activo del pie)
PAGES = (
    ("index.html", None, None),
    ("catalog/index.html", "/catalog/", None),
    ("methodology/index.html", "/methodology/", None),
    ("engineering-evidence/index.html", "/engineering-evidence/", None),
    ("engineering-evidence/case-studies/index.html", "/engineering-evidence/case-studies/", None),
    ("engineering-evidence/jetbrains-platform-tickets/index.html", "/engineering-evidence/jetbrains-platform-tickets/", None),
    ("engineering-evidence/open-source-security-reports/index.html", "/engineering-evidence/open-source-security-reports/", None),
    ("engineering-evidence/third-party-plugin-audits/index.html", "/engineering-evidence/third-party-plugin-audits/", None),
    ("contact/index.html", "/contact/", None),
    ("security/index.html", None, "/security/"),
    ("privacy/index.html", None, "/privacy/"),
    ("terms/index.html", None, "/terms/"),
    ("eula/index.html", None, "/eula/"),
    ("plugin-performance-audit/index.html", None, "/plugin-performance-audit/"),
    ("dependency-security-review/index.html", "/services/", None),
    ("custom-plugins-inspections/index.html", "/services/", None),
    ("plugin-updates/index.html", "/services/", None),
    ("services/index.html", "/services/", None),
    ("ghl-jail/index.html", None, None),
    ("sponsors/index.html", None, "/sponsors/"),
    ("writing/index.html", "/writing/", None),
    ("writing/background-readaction-freeze/index.html", "/writing/", None),
)

# Un item con submenu es (etiqueta, [(href, texto), ...]); el resto (href, texto).
# 2026-10-19 (rediseno): Work / Engineering / Tools / Services / Contact. Las
# rutas no cambian; Methodology y las paginas de evidencia van bajo Engineering.
# 2026-11-09: Services / Evidence / Plugins / Sponsors / Blog / Contact.
# - "Work" (an anchor on the home) and the "Engineering" menu led to the same evidence pages under two labels;
#   they are one menu now, "Evidence", named like the page it opens.
# - Services goes first: it is the line of business that pays the year. Sponsors joins the header.
# - "Plugins" is the word of the catalog's own title and of the searches that bring visitors. In Spanish the
#   header link reads "Herramientas" and "Sponsors" reads "Patrocinio": both come from contextual keys in
#   es.json ("[ctx:gh-nav-link] ..."), because the plain keys are used elsewhere with other translations.
# - No URL changes. Measured before the change: at 961 px (the narrowest width before the burger menu) this
#   leaves 40 px free in English and 8 px in Spanish; _review/site-behavior.test.js fails if it ever overlaps.
EE = "/engineering-evidence/"
EVIDENCE_ITEMS = ((EE, "Evidence overview", "Everything that backs the work"),
                  (EE + "jetbrains-platform-tickets/", "JetBrains Platform tickets", "Root-cause reports and fixes in the IntelliJ Platform"),
                  (EE + "open-source-security-reports/", "Open-source security reports", "Vulnerable dependencies fixed by maintainers"),
                  (EE + "third-party-plugin-audits/", "Third-party plugin audits", "Findings in other vendors&rsquo; plugins, fixed by them"),
                  (EE + "case-studies/", "Plugin case studies", "Plugins with the strongest evidence"),
                  ("/methodology/", "Methodology", "How problems are investigated and fixed"))
NAV = (("/services/", "Services"), ("Evidence", EVIDENCE_ITEMS), ("/catalog/", "Plugins"),
       ("/sponsors/", "Sponsors"), ("/writing/", "Blog"), ("/contact/", "Contact"))

LOGO = ('<svg class="gh-logo" viewBox="0 0 1024 1024" aria-hidden="true">'
        '<path d="M 511,81 L 847,283 L 725,351 L 508,223 L 296,348 L 296,588 L 463,691 L 342,765 L 173,665 L 172,281 Z" fill="#0151FC"/>'
        '<path d="M 846,412 L 844,668 L 518,863 L 393,795 L 724,589 L 721,540 L 567,538 L 568,412 Z" fill="#01B3FD"/>'
        '<polygon points="569,413 695,413 695,539 569,539" fill="#02F172"/></svg>')

ICON = {
    "system": '<svg viewBox="0 0 20 20" aria-hidden="true"><rect x="2.5" y="3.5" width="15" height="10" rx="1.5"/><path d="M7 17h6M10 13.5V17"/></svg>',
    "light": '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.5"/><path d="M10 1.8v2M10 16.2v2M1.8 10h2M16.2 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4"/></svg>',
    "dark": '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M16.5 12.3A7 7 0 0 1 7.7 3.5a7 7 0 1 0 8.8 8.8z"/></svg>',
    "github": '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" stroke="none" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    "x": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>',
    "devto": '<svg viewBox="0 0 448 512" aria-hidden="true"><path fill="currentColor" stroke="none" d="M120.12 208.29c-3.88-2.9-7.77-4.35-11.65-4.35H91.03v104.47h17.45c3.88 0 7.77-1.45 11.65-4.35 3.88-2.9 5.82-7.25 5.82-13.06v-69.65c-.01-5.8-1.96-10.16-5.83-13.06zM404.1 32H43.9C19.7 32 .06 51.59 0 75.8v360.4C.06 460.41 19.7 480.01 43.9 480h360.2c24.21.01 43.84-19.59 43.9-43.8V75.8c-.06-24.21-19.7-43.81-43.9-43.8zM154.2 291.19c0 18.81-11.61 47.31-48.36 47.25h-46.4V172.98h47.38c35.44 0 47.36 28.46 47.37 47.28l.01 70.93zm100.68-88.66H201.6v38.42h32.57v29.57H201.6v38.41h53.29v29.57h-62.18c-11.16.29-20.44-8.53-20.72-19.69V193.7c-.27-11.15 8.56-20.41 19.71-20.69h63.19l-.02 29.52zm103.64 115.29c-13.2 30.75-36.85 24.63-47.44 0l-38.53-144.8h32.57l29.71 113.72 29.57-113.72h32.58l-38.53 144.8z"/></svg>',
    "patreon": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M14.82 2.41c3.96 0 7.18 3.24 7.18 7.21 0 3.96-3.22 7.18-7.18 7.18-3.97 0-7.21-3.22-7.21-7.18 0-3.97 3.24-7.21 7.21-7.21M2 21.6h3.5V2.41H2V21.6z"/></svg>',
}
THEMES = (("system", "System"), ("light", "Light"), ("dark", "Dark"))

# ---- idiomas (2026-09-27): version nativa en espanol de las 10 paginas
# principales, generada por pipeline/build_i18n.py. Desde 2026-10-05 las
# fichas de plugin tambien tienen version en espanol (/es/catalogo/<slug>/):
# antes llevaban al catalogo en espanol y, al navegar desde ahi, el sitio
# volvia al ingles. Ver es_path_for().
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from site_config import SITE_URL  # noqa: E402
SITE = SITE_URL
ES_PATHS = {
    "/": "/es/",
    "/catalog/": "/es/catalogo/",
    "/methodology/": "/es/metodologia/",
    "/engineering-evidence/": "/es/ingenieria-y-evidencia/",
    "/engineering-evidence/case-studies/": "/es/ingenieria-y-evidencia/casos-de-estudio/",
    "/engineering-evidence/jetbrains-platform-tickets/": "/es/ingenieria-y-evidencia/tickets-jetbrains-platform/",
    "/engineering-evidence/open-source-security-reports/": "/es/ingenieria-y-evidencia/reportes-de-seguridad/",
    "/engineering-evidence/third-party-plugin-audits/": "/es/ingenieria-y-evidencia/auditorias-de-plugins-de-terceros/",
    "/contact/": "/es/contacto/",
    "/security/": "/es/seguridad/",
    "/privacy/": "/es/privacidad/",
    "/terms/": "/es/terminos/",
    "/eula/": "/es/eula/",
    "/plugin-performance-audit/": "/es/auditoria-de-rendimiento/",
    "/dependency-security-review/": "/es/revision-de-seguridad-de-dependencias/",
    "/custom-plugins-inspections/": "/es/plugins-e-inspecciones-a-medida/",
    "/plugin-updates/": "/es/actualizacion-de-plugins/",
    "/services/": "/es/servicios/",
    "/ghl-jail/": "/es/ghl-jail/",
    "/sponsors/": "/es/patrocinadores/",
    "/writing/": "/es/escritos/",
    "/writing/background-readaction-freeze/": "/es/escritos/background-readaction-freeze/",
}
PLUGIN_PATH_RE = re.compile(r"^/catalog/((?:vscode/)?[a-z0-9][a-z0-9-]*)/$")


def es_path_for(en_path):
    """Ruta en espanol de una ruta inglesa, o None si no tiene version en
    espanol: las 10 principales (ES_PATHS) y las fichas de plugin."""
    if en_path in ES_PATHS:
        return ES_PATHS[en_path]
    m = PLUGIN_PATH_RE.match(en_path)
    return "/es/catalogo/%s/" % m.group(1) if m else None


LANG_START, LANG_END = "<!-- LANG:START -->", "<!-- LANG:END -->"
ALT_START, ALT_END = "<!-- HREFLANG:START -->", "<!-- HREFLANG:END -->"
GLOBE = ('<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/>'
         '<path d="M2.5 10h15M10 2.5c2.2 2.3 3.2 4.8 3.2 7.5s-1 5.2-3.2 7.5c-2.2-2.3-3.2-4.8-3.2-7.5s1-5.2 3.2-7.5z"/></svg>')


def page_path(rel):
    return "/" if rel == "index.html" else "/" + rel[: -len("index.html")]


def lang_switch_html(lang, en_path, es_path):
    """Menu EN/ES. lang = idioma de la pagina actual."""
    label = "Language" if lang == "en" else "Idioma"
    # WCAG 2.5.3 (Label in Name): the button's visible text is the language
    # code (EN/ES), so its accessible name must contain that code. axe strips
    # parenthesised text from the accessible name, so a colon (not parentheses)
    # keeps the code as a matchable part of the name: "Language: EN".
    btn_label = "%s: %s" % (label, lang.upper())
    items = "".join(
        '<a class="gh-pop-item" href="%s" hreflang="%s" lang="%s"%s>%s</a>'
        % (href, code, code, ' aria-current="true"' if code == lang else "", text)
        for code, href, text in (("en", en_path, "English"), ("es", es_path, "Espa&ntilde;ol")))
    return (LANG_START + '<div class="gh-menu gh-lang">'
            '<button type="button" class="gh-icon-btn gh-lang-btn" data-menu-toggle aria-expanded="false" aria-label="%s">'
            '%s<span class="gh-lang-code">%s</span></button>'
            '<div class="gh-pop" data-menu hidden role="group" aria-label="%s">%s</div></div>' + LANG_END) % (
        btn_label, GLOBE, lang.upper(), label, items)


def alternates_html(en_path, es_path):
    return (ALT_START + '\n<link rel="alternate" hreflang="en" href="%s%s">\n'
            '<link rel="alternate" hreflang="es" href="%s%s">\n'
            '<link rel="alternate" hreflang="x-default" href="%s%s">\n'
            '<link rel="alternate" type="application/rss+xml" title="Gap Hunter Labs — new plugins" href="/feed.xml">\n'
            + ALT_END) % (
        SITE, en_path, SITE, es_path, SITE, en_path)
LINKEDIN = "https://www.linkedin.com/in/joel-diaz-82687b428/?locale=en"


def header_html(active, en_path="/"):
    parts = []
    for first, second in NAV:
        if isinstance(second, tuple):
            in_group = any(href == active for href, _, _ in second)
            items = "".join(
                '<a class="gh-pop-link" href="%s"%s><strong>%s</strong><span>%s</span></a>'
                % (href, ' aria-current="page"' if href == active else "", label, hint)
                for href, label, hint in second)
            parts.append(
                '<div class="gh-menu gh-nav-group">'
                '<button type="button" class="gh-nav-link gh-nav-toggle%s" data-menu-toggle aria-expanded="false">%s'
                '<svg class="gh-chevron" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 8l4 4 4-4"/></svg></button>'
                '<div class="gh-pop gh-pop-wide" data-menu hidden>%s</div></div>'
                % (" is-active" if in_group else "", first, items))
        else:
            parts.append('<a class="gh-nav-link" href="%s"%s>%s</a>'
                         % (first, ' aria-current="page"' if first == active else "", second))
    # 2026-11-09: on phones (below 480px) the header has no room for the search button next to the brand name, so the
    # same search opens from here, the first item of the open menu. CSS hides it everywhere else. The visible text is
    # in a <span> so build_i18n reuses the translation of the header button's screen-reader text.
    nav_search = ('<button type="button" class="gh-nav-search" data-search-open aria-haspopup="dialog" '
                  'aria-expanded="false"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/>'
                  '<path d="M12.6 12.6 17 17"/></svg><span>Search plugins and pages</span></button>')
    links = nav_search + "".join(parts)
    theme_items = "".join(
        '<button type="button" class="gh-pop-item" data-theme-choice="%s" aria-pressed="false">'
        '<span class="gh-ico">%s</span>%s</button>' % (key, ICON[key], label)
        for key, label in THEMES)
    return (
        '<a class="gh-skip-link" href="#main-content">Skip to content</a>\n'
        '<header class="gh-header" id="topbar">\n'
        '  <div class="gh-header-inner">\n'
        '    <a class="gh-brand" href="/" aria-label="Gap Hunter Labs home">%s<span class="gh-brand-name">Gap Hunter Labs</span></a>\n'
        '    <nav class="gh-nav" id="siteNav" aria-label="Primary">%s'
        '<a class="btn primary gh-nav-cta" href="/services/" data-goatcounter-click="cta-nav-hire-mobile">Work with me</a></nav>\n'
        '    <div class="gh-tools">\n'
        # 2026-10-05: buscador del sitio (js/site-search.js, se carga al abrirlo)
        # 2026-11-08 (WCAG 2.5.3, Label in Name): with an aria-label, axe compared it with the visible text
        # "Search Ctrl K" and failed at desktop widths, even with the hint hidden. The button is now named by its
        # content: a screen-reader-only phrase that starts with the visible word "Search". The visible word and the
        # shortcut hint are hidden from the accessibility tree so the name is not read twice, and the phrase stays
        # when the visible label is collapsed below 1180px.
        '      <button type="button" class="gh-search-btn" data-search-open aria-haspopup="dialog" aria-expanded="false">'
        '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/>'
        '<path d="M12.6 12.6 17 17"/></svg><span class="gh-search-label" aria-hidden="true">Search</span>'
        '<span class="sr-only">Search plugins and pages</span>'
        '<kbd class="gh-search-kbd" aria-hidden="true">Ctrl K</kbd></button>\n'
        '      %s\n'
        '      <div class="gh-menu">\n'
        '        <button type="button" class="gh-icon-btn" data-menu-toggle aria-expanded="false" aria-label="Color theme">'
        '<span class="gh-ico gh-ico-system">%s</span><span class="gh-ico gh-ico-light">%s</span><span class="gh-ico gh-ico-dark">%s</span></button>\n'
        '        <div class="gh-pop" data-menu hidden role="group" aria-label="Color theme">%s</div>\n'
        '      </div>\n'
        '      <a class="btn primary gh-cta" href="/services/" data-goatcounter-click="cta-nav-hire">Work with me</a>\n'
        '      <button type="button" class="gh-burger" id="topbarBurger" aria-label="Toggle navigation" aria-expanded="false" aria-controls="siteNav"><span></span></button>\n'
        '    </div>\n'
        '  </div>\n'
        '</header>'
    ) % (LOGO, links, lang_switch_html("en", en_path, ES_PATHS.get(en_path, "/es/")),
         ICON["system"], ICON["light"], ICON["dark"], theme_items)


_SERVICES = None


def _services():
    """data/services.json, read once and checked by services_data.load (the build stops on a bad file)."""
    global _SERVICES
    if _SERVICES is None:
        import services_data
        try:
            _SERVICES = services_data.load()
        except services_data.ServicesError as exc:
            _sys.exit("[build_chrome] ERROR: %s" % exc)
    return _SERVICES


def footer_html(active):
    def link(href, label, external=False):
        cur = ' aria-current="page"' if href == active else ""
        ext = ' target="_blank" rel="noopener"' if external else ""
        return '<a href="%s"%s%s>%s</a>' % (href, cur, ext, label)

    # 2026-11-09: 6 columns. "Work" and "Engineering" were the same evidence pages under two titles, and three
    # of the four service pages and the Blog had no footer link at all.
    # The service links come from data/services.json, in its order, with their footer labels.
    cols = (
        ("Services", [link("/services/", "Work with me")]
                     + [link(s["path"], s["shortName"]) for s in _services()["services"]]
                     + [link("/contact/", "Contact")]),
        ("Evidence", [link(EE, "Evidence overview"),
                      link(EE + "jetbrains-platform-tickets/", "JetBrains Platform tickets"),
                      link(EE + "open-source-security-reports/", "Open-source security reports"),
                      link(EE + "third-party-plugin-audits/", "Third-party plugin audits"),
                      link(EE + "case-studies/", "Plugin case studies"),
                      link("/methodology/", "Methodology"), link("/writing/", "Blog")]),
        ("Tools", [link("/catalog/", "Plugin catalog"), link("/catalog/?pricing=paid", "Paid &amp; Pro plugins"),
                   link("/catalog/?platform=vscode", "VS Code extensions"), link("/ghl-jail/", "ghl-jail (Windows sandbox)")]),
        # 2026-11-08: sponsorship is its own line of support, not a service (a service has a fixed scope and date).
        ("Sponsorship", [link("/sponsors/", "Sponsor the work"), link("/sponsors/#sec-levels", "Sponsorship levels"),
                         link("/contact/?intent=sponsor", "Company sponsorship")]),
        ("Marketplaces", [link("https://plugins.jetbrains.com/vendor/gap-hunter-labs", "JetBrains Marketplace", True),
                          link("https://marketplace.visualstudio.com/publishers/GapHunterLabs", "VS Code Marketplace", True),
                          link("https://github.com/GapHunterLabs", "GitHub", True)]),
        ("Legal", [link("/security/", "Security"), link("/privacy/", "Privacy"), link("/terms/", "Terms"),
                   link("/eula/", "EULA")]),
    )
    cols_html = "".join(
        '<div class="gh-footer-col"><p class="gh-footer-title">%s</p>%s</div>' % (title, "".join(items))
        for title, items in cols)
    social = "".join(
        '<a class="gh-social" href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a>' % (href, label, ICON[key])
        for key, href, label in (("github", "https://github.com/GapHunterLabs", "Gap Hunter Labs on GitHub"),
                                 ("linkedin", LINKEDIN, "Joel Diaz on LinkedIn"),
                                 ("x", "https://x.com/GapHunterLabs", "Gap Hunter Labs on X"),
                                 ("youtube", "https://www.youtube.com/@GapHunterLabs", "Gap Hunter Labs on YouTube"),
                                 ("devto", "https://dev.to/gap_hunterlabs", "Gap Hunter Labs on DEV"),
                                 ("patreon", "https://www.patreon.com/c/GapHunterLabs", "Gap Hunter Labs on Patreon")))
    theme_seg = "".join(
        '<button type="button" class="gh-seg-btn" data-theme-choice="%s" aria-pressed="false" aria-label="%s theme" title="%s">%s</button>'
        % (key, label, label, ICON[key]) for key, label in THEMES)
    return (
        '<footer class="site-footer gh-footer band-dark">\n'
        '  <div class="gh-footer-inner">\n'
        '    <div class="gh-footer-top">\n'
        '      <div class="gh-footer-brand">\n'
        '        <a class="gh-brand" href="/">%s<span class="gh-brand-name">Gap Hunter Labs</span></a>\n'
        '        <p>My engineering practice: I trace performance bottlenecks, security vulnerabilities and structural failures '
        'in developer tools, enterprise platforms and open-source ecosystems to their root cause, and ship the fix.</p>\n'
        '        <a class="btn primary" href="/services/" data-goatcounter-click="cta-footer-hire">Work with me</a>\n'
        '        <div class="gh-footer-about">\n'
        '          <img src="/assets/img/joel-diaz-96.jpg" width="48" height="48" alt="" loading="lazy" decoding="async">\n'
        '          <div><p class="gh-footer-about-title">About</p>\n'
        '          <p><strong>Joel D&iacute;az, Founder.</strong> Trained in systems engineering, with a background in industrial operations and logistics.</p>\n'
        '          <p class="gh-footer-about-links"><a href="/feed.xml">RSS</a><a href="mailto:contact@gaphunterlabs.com">contact@gaphunterlabs.com</a></p></div>\n'
        '        </div>\n'
        '      </div>\n'
        '      <nav class="gh-footer-cols" aria-label="Footer">%s</nav>\n'
        '    </div>\n'
        '    <div class="gh-footer-bottom">\n'
        '      <p class="gh-footer-legal">&copy; 2026 Gap Hunter Labs. Download data is synced twice daily from the public JetBrains Marketplace and GitHub APIs.</p>\n'
        '      <div class="gh-footer-social">%s</div>\n'
        '      <div class="gh-seg" role="group" aria-label="Color theme">%s</div>\n'
        '    </div>\n'
        '  </div>\n'
        '</footer>'
    ) % (LOGO, cols_html, social, theme_seg)


HEADER_START, HEADER_END = "<!-- CHROME:HEADER:START -->", "<!-- CHROME:HEADER:END -->"
FOOTER_START, FOOTER_END = "<!-- CHROME:FOOTER:START -->", "<!-- CHROME:FOOTER:END -->"
OLD_HEADER_RE = re.compile(r'<nav class="topbar" id="topbar">.*?</nav>\s*<aside class="app-sidebar" id="appSidebar">.*?</aside>', re.S)
OLD_FOOTER_RE = re.compile(r'<footer class="site-footer[^"]*">.*?</footer>', re.S)
HEAD_SCRIPTS = ('<script src="/js/theme-init.js"></script>\n'
                '<script src="/js/site-chrome.js" defer></script>\n')
REVEAL_SCRIPT = '<script src="/js/site-reveal.js" defer></script>\n'
LANG_DETECT_SCRIPT = '<script src="/js/lang-detect.js"></script>\n'


def replace_region(html, start, end, content, old_re, label, path):
    block = start + "\n" + content + "\n" + end
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pat.search(html):
        return pat.sub(lambda _m: block, html, count=1)
    new, n = old_re.subn(lambda _m: block, html, count=1)
    if n != 1:
        sys.exit("[build_chrome] ERROR: %s no encontrado en %s" % (label, path))
    return new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; sale con 1 si alguna pagina esta desactualizada")
    args = ap.parse_args()
    stale = 0
    for rel, active_head, active_foot in PAGES:
        path = ROOT / rel
        html = path.read_text(encoding="utf-8")
        en_path = page_path(rel)
        new = replace_region(html, HEADER_START, HEADER_END, header_html(active_head, en_path), OLD_HEADER_RE, "encabezado", rel)
        alt = alternates_html(en_path, ES_PATHS[en_path])
        if ALT_START in new:
            new = re.sub(re.escape(ALT_START) + r".*?" + re.escape(ALT_END), lambda _m: alt, new, count=1, flags=re.S)
        else:
            new, n = re.subn(r'(<link rel="canonical" href="[^"]*">)', lambda m: m.group(1) + "\n" + alt, new, count=1)
            if n != 1:
                sys.exit("[build_chrome] ERROR: sin canonical en %s" % rel)
        new = replace_region(new, FOOTER_START, FOOTER_END, footer_html(active_foot), OLD_FOOTER_RE, "pie", rel)
        if "/js/theme-init.js" not in new:
            new, n = re.subn(r'(<meta name="viewport"[^>]*>\n)', lambda m: m.group(1) + HEAD_SCRIPTS, new, count=1)
            if n != 1:
                sys.exit("[build_chrome] ERROR: sin <meta name=viewport> en %s" % rel)
        # Aparicion al hacer scroll (2026-10-08): despues de site-chrome.js, con defer.
        if "/js/site-reveal.js" not in new:
            new, n = re.subn(r'(<script src="/js/site-chrome\.js[^"]*" defer></script>\n)',
                             lambda m: m.group(1) + REVEAL_SCRIPT, new, count=1)
            if n != 1:
                sys.exit("[build_chrome] ERROR: sin site-chrome.js en %s" % rel)
        # Redireccion por idioma del navegador (2026-11-02): antes de theme-init,
        # sin defer, para redirigir la home EN a /es/ sin flash. Solo actua en la
        # home; respeta la eleccion manual del selector. Tolera el ?v= de versionado.
        if "/js/lang-detect.js" not in new:
            new, n = re.subn(r'(<script src="/js/theme-init\.js[^"]*"></script>\n)',
                             lambda m: LANG_DETECT_SCRIPT + m.group(1), new, count=1)
            if n != 1:
                sys.exit("[build_chrome] ERROR: sin theme-init.js para anclar lang-detect en %s" % rel)
        # Destino del skip-link (2026-11-02, a11y): el landmark <main> recibe id y
        # foco programatico. Solo el <main> real lleva atributos (los de comentarios
        # son <main> pelados), asi que exigimos un espacio tras "main".
        if 'id="main-content"' not in new:
            new = re.sub(r'<main (?![^>]*\bid=)', '<main id="main-content" tabindex="-1" ', new, count=1)
        if new != html:
            stale += 1
            if not args.check:
                path.write_text(new, encoding="utf-8")
    print("[build_chrome] %d paginas %s" % (stale, "desactualizadas" if args.check else "actualizadas"))
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
