#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_page_og.py -- one distinct 1200x630 social-share image per hand-made
site page (19 pages), in English and Spanish (not the plugin cards, which
build_og_images.py renders one-per-plugin into media/<slug>/og.png).

Redesigned 2026-10-29 in the site's v3 look (see og_kit.py): near-black ground
with the hero grid and glow, a large headline, one short line of purpose and
inline-SVG badges for the platform, language, tooling or discipline that the page
itself names. Four compositions: the home (with a gap/fix evidence card),
services (price table), the performance audit (price card) and a generic hero for
every other page. Deliberately timeless: no live catalog numbers, so the twice-daily
catalog refresh never has to regenerate these.

Output lives at the repo root:
  home -> og-image.png / og-image.es.png
  /services/ -> og-services.png / og-services.es.png
  ... and og-<slug>.png / og-<slug>.es.png for the rest (38 images).

The English page HTML references these directly in <head>; build_i18n.py rewrites
the ES pages' og:image from og-X.png to og-X.es.png automatically. After changing
an image, bump OG_VERSION in site_config.py so social networks fetch it again.

Requires: playwright + `python -m playwright install chromium`.

Usage:
  python pipeline/build_page_og.py                 # all 38
  python pipeline/build_page_og.py --only og-methodology og-image.es
  python pipeline/build_page_og.py --out-dir /tmp/preview --only og-image
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import og_kit as K  # noqa: E402

ROOT = HERE.parent
OG_STAMP = ROOT / "data" / "og-prices.json"
NL = "\n"

CSS_HERO = """
  .headline { margin-top:0; }
  .lede { max-width:1020px; }
"""

CSS_HOME = """
  .cols { display:grid; grid-template-columns:minmax(0,1fr) 390px; gap:40px; align-items:center; }
  .headline { font-size:56px; }
  .lede { font-size:26px; margin-top:20px; max-width:640px; }
  .evidence { padding:8px 26px; }
  .evidence .row { padding:20px 0; display:grid; gap:10px; }
  .evidence .row + .row { border-top:1px solid #2E2E2E; }
  .evidence .tag { font:700 17px/1 "JetBrains Mono",monospace; letter-spacing:.14em; display:flex; align-items:center; gap:10px; }
  .evidence .tag::before { content:""; width:12px; height:12px; border-radius:50%; background:var(--c); }
  .evidence .gap { --c:#F59E0B; color:#F59E0B; } .evidence .fix { --c:#10B981; color:#10B981; }
  .evidence .ref { font:600 24px/1.2 "JetBrains Mono",monospace; color:#FFFFFF; }
  .evidence .txt { font-size:23px; line-height:1.35; color:#B4B4B4; }
"""

CSS_SERVICES = """
  .headline { font-size:62px; }
  .table { margin-top:26px; padding:2px 28px; }
  .table .tr { display:flex; align-items:baseline; justify-content:space-between; gap:24px; padding:15px 0; font-size:27px; }
  .table .tr + .tr { border-top:1px solid #2E2E2E; }
  .table .nm { color:#EDEDED; font-weight:500; }
  .table .pr { font:600 25px/1 "JetBrains Mono",monospace; color:#FFFFFF; white-space:nowrap; }
  .table .pr small { font:500 19px/1 "JetBrains Mono",monospace; color:#9A9A9A; margin-left:8px; }
"""

CSS_AUDIT = """
  .cols { display:grid; grid-template-columns:minmax(0,1fr) 400px; gap:48px; align-items:center; }
  .headline { font-size:56px; }
  .list { margin-top:22px; display:grid; gap:10px; }
  .list div { display:flex; gap:14px; align-items:baseline; font-size:26px; line-height:1.3; color:#D4D4D4; }
  .list div::before { content:""; flex:none; width:12px; height:12px; border-radius:3px; background:#FF6A1A; transform:translateY(1px); }
  .price { padding:28px 30px; }
  .price .amt { font:700 78px/1 "JetBrains Mono",monospace; letter-spacing:-0.03em; color:#FFFFFF; }
  .price .amt small { font:500 34px/1 "JetBrains Mono",monospace; color:#9A9A9A; margin-right:10px; letter-spacing:0; }
  .price p { margin-top:16px; font-size:23px; line-height:1.4; color:#B4B4B4; }
  .price p.ext { margin-top:18px; padding-top:16px; border-top:1px solid #2E2E2E; font:500 20px/1.4 "JetBrains Mono",monospace; color:#EDEDED; }
"""


def hero_body(h1, lede, badge_keys, lang):
    return ('<h1 class="headline" style="font-size:%dpx">%s</h1>'
            '<p class="lede">%s</p>%s'
            % (K.headline_size(h1), K.text_html(h1), K.esc(lede), K.badges_html(badge_keys, lang)))


def home_body(c, lang):
    return ('<div class="cols"><div>'
            '<h1 class="headline">%s</h1><p class="lede">%s</p>%s</div>'
            '<div class="card evidence">'
            '<div class="row"><span class="tag gap">%s</span><span class="ref">%s</span><span class="txt">%s</span></div>'
            '<div class="row"><span class="tag fix">%s</span><span class="ref">%s</span><span class="txt">%s</span></div>'
            '</div></div>'
            % (K.text_html(c["h1"]), K.esc(c["lede"]), K.badges_html(c["badges"], lang),
               c["gap_label"], K.esc(c["gap_ref"]), K.esc(c["gap_text"]),
               c["fix_label"], K.esc(c["fix_ref"]), K.esc(c["fix_text"])))


def services_body(c, lang):
    rows = "".join('<div class="tr"><span class="nm">%s</span><span class="pr">%s<small>· %s</small></span></div>'
                   % (K.esc(n), K.esc(p), K.esc(w)) for n, p, w in c["rows"])
    return ('<h1 class="headline">%s</h1><div class="card table">%s</div>%s'
            % (K.text_html(c["h1"]), rows, K.badges_html(c["badges"], lang).replace('class="badges"', 'class="badges" style="margin-top:22px"')))


def audit_body(c, lang):
    lis = "".join("<div>%s</div>" % K.esc(b) for b in c["bullets"])
    return ('<div class="cols"><div><h1 class="headline">%s</h1><div class="list">%s</div>%s</div>'
            '<div class="card price"><div class="amt"><small>%s</small>%s</div><p>%s</p><p class="ext">%s</p></div></div>'
            % (K.text_html(c["h1"]), lis, K.badges_html(c["badges"], lang),
               K.esc(c["cur"]), K.esc(c["amount"]), K.esc(c["price_note"]), K.esc(c["ext_note"])))


LAYOUTS = {"hero": (CSS_HERO, None), "home": (CSS_HOME, home_body), "services": (CSS_SERVICES, services_body),
           "audit": (CSS_AUDIT, audit_body)}


def page(stem, layout, en, es):
    return dict(stem=stem, layout=layout, en=en, es=es)


# 2026-11-09: prices and delivery times come from data/services.json. A changed price changes the
# text of these images, so they must be rendered again (and OG_VERSION bumped); build_services.py --check fails
# until data/og-prices.json, written at the end of a full render, matches the prices below.
import services_data as _S  # noqa: E402
try:
    _SV = _S.load()
except _S.ServicesError as _exc:
    sys.exit("[build_page_og] ERROR: %s" % _exc)


def _usd(ref, lang="en"):
    return _S.usd(_S.value(_SV, ref + ".usd"), lang)


def _days(ref):
    return _S.value(_SV, ref + ".days")


def _from(key, lang="en"):
    return _S.usd(_S.min_usd(_S.by_key(_SV)[key]), lang)


_LOWEST = min(_S.min_usd(s) for s in _SV["services"])


def og_price_texts():
    """Every price or delivery figure these images show, as rendered: the stamp in data/og-prices.json."""
    out = []
    for p in PAGES:
        for lang in ("en", "es"):
            block = p[lang]
            for k in ("note", "amount", "price_note", "ext_note"):
                if k in block:
                    out.append("%s.%s.%s=%s" % (p["stem"], lang, k, block[k]))
            for row in block.get("rows", []):
                out.append("%s.%s.row=%s" % (p["stem"], lang, " | ".join(row)))
    return sorted(t for t in out if re.search(r"\d", t.split("=", 1)[1]))


# Each entry has an English and a Spanish block. `label` is the mono eyebrow (what the page is), `h1` the headline
# (\n = line break), `lede` one short line of purpose, `badges` keys from og_kit.REG, `note` the footer line.
PAGES = [
    page("og-image", "home",
         dict(label="Engineering practice of Joel Díaz", h1="I find the gap.\nI trace the cause.\nI build the fix.",
              lede="I investigate performance, security and reliability failures in developer tools and open-source software, and I fix them at the root cause.",
              badges=["static", "perf", "security", "reliability"], gap_label="GAP", fix_label="FIX",
              gap_ref="lsp4ij#1540", gap_text="A UI-thread violation in Red Hat's LSP4IJ",
              fix_ref="commit f38259550e", fix_text="Fixed by the maintainer after the report",
              note="Fixed-scope engagements from USD %s" % _S.usd(_LOWEST)),
         dict(label="Estudio de ingeniería de Joel Díaz", h1="Encuentro la brecha.\nRastreo la causa.\nConstruyo la corrección.",
              lede="Investigo fallas de rendimiento, seguridad y fiabilidad en herramientas de desarrollo y código abierto, y las corrijo en su causa raíz.",
              badges=["static", "perf", "security", "reliability"], gap_label="BRECHA", fix_label="SOLUCIÓN",
              gap_ref="lsp4ij#1540", gap_text="Una violación del hilo de UI en LSP4IJ de Red Hat",
              fix_ref="commit f38259550e", fix_text="Corregido por el mantenedor tras el reporte",
              note="Proyectos de alcance fijo desde USD %s" % _S.usd(_LOWEST, "es"))),
    page("og-services", "services",
         dict(label="Engineering services", h1="Fixed scope. Published prices.", badges=["jetbrains", "kotlin", "gradle", "actions", "gitlab"],
              rows=[("Plugin performance audit", "USD %s" % _usd("audit.base"), "%d business days" % _days("audit.base")),
                    ("Plugin updates for new IDE versions", "from USD %s" % _from("updates"), "%d business days" % _days("updates.minor")),
                    ("Custom plugins and inspections", "from USD %s" % _from("custom"), "%d business days" % _days("custom.inspections")),
                    ("Dependency and CI/CD security review", "from USD %s" % _from("depsec"), "%d business days" % _days("depsec.one-repo"))],
              note="Written deliverables · 50% on start, 50% on delivery"),
         dict(label="Servicios de ingeniería", h1="Alcance fijo. Precios publicados.", badges=["jetbrains", "kotlin", "gradle", "actions", "gitlab"],
              rows=[("Auditoría de rendimiento de plugins", "USD %s" % _usd("audit.base", "es"), "%d días hábiles" % _days("audit.base")),
                    ("Actualización de plugins para nuevos IDE", "desde USD %s" % _from("updates", "es"), "%d días hábiles" % _days("updates.minor")),
                    ("Plugins e inspecciones a medida", "desde USD %s" % _from("custom", "es"), "%d días hábiles" % _days("custom.inspections")),
                    ("Seguridad de dependencias y CI/CD", "desde USD %s" % _from("depsec", "es"), "%d días hábiles" % _days("depsec.one-repo"))],
              note="Entregables por escrito · 50% al iniciar, 50% al entregar")),
    page("og-audit", "audit",
         dict(label="Plugin performance audit", h1="Your plugin freezes.\nI find the cause and patch it.", badges=["jetbrains", "perf"],
              bullets=["Reproduction on each IDE version you support", "UI-thread measurements, cold and warm", "Patches with before-and-after measurements"],
              cur="USD", amount=_usd("audit.base"),
              price_note="Fixed price. One plugin, up to 3 IDE versions, %d business days." % _days("audit.base"),
              ext_note="Extended: USD %s · %d business days" % (_usd("audit.extended"), _days("audit.extended")),
              note="The same method found freeze bugs in the IntelliJ Platform"),
         dict(label="Auditoría de rendimiento de plugins", h1="Tu plugin se congela.\nEncuentro la causa y lo parcheo.", badges=["jetbrains", "perf"],
              bullets=["Reproducción en cada versión del IDE que soportas", "Mediciones del hilo de UI, en frío y en caliente", "Parches con mediciones antes y después"],
              cur="USD", amount=_usd("audit.base", "es"),
              price_note="Precio fijo. Un plugin, hasta 3 versiones del IDE, %d días hábiles." % _days("audit.base"),
              ext_note="Extendida: USD %s · %d días hábiles" % (_usd("audit.extended", "es"), _days("audit.extended")),
              note="El mismo método halló congelamientos en IntelliJ Platform")),
    page("og-dependency-security", "hero",
         dict(label="Security review", h1="Dependency and CI/CD\nsecurity review",
              lede="I review your dependencies and CI/CD workflows, read-only: known CVEs, dependency confusion and workflow permissions.",
              badges=["security"], note="Fixed price from USD %s" % _from("depsec")),
         dict(label="Revisión de seguridad", h1="Revisión de seguridad de\ndependencias y CI/CD",
              lede="Reviso tus dependencias y flujos de CI/CD, en solo lectura: CVE conocidos, confusión de dependencias y permisos de workflows.",
              badges=["security"], note="Precio fijo desde USD %s" % _from("depsec", "es"))),
    page("og-custom-plugins", "hero",
         dict(label="Custom plugins", h1="Custom plugins and\ninspections",
              lede="I build static-analysis inspections for your codebase as a plugin your team installs and runs in CI.",
              badges=["static", "actions", "gitlab"], note="Fixed price from USD %s" % _from("custom")),
         dict(label="Plugins a medida", h1="Plugins e inspecciones\na medida",
              lede="Construyo inspecciones de análisis estático para tu código como un plugin que tu equipo instala y corre en CI.",
              badges=["static", "actions", "gitlab"], note="Precio fijo desde USD %s" % _from("custom", "es"))),
    page("og-plugin-updates", "hero",
         dict(label="IDE compatibility", h1="Plugin updates for\nnew IDE versions",
              lede="I build and verify your JetBrains plugin against the IDE versions you support: removed APIs, Kotlin K2 and Plugin Verifier failures.",
              badges=["jetbrains", "kotlin", "gradle"], note="Fixed price from USD %s" % _from("updates")),
         dict(label="Compatibilidad del IDE", h1="Actualización de plugins\npara nuevos IDE",
              lede="Compilo y verifico tu plugin de JetBrains contra las versiones del IDE que soportas: API removidas, Kotlin K2 y fallos del Plugin Verifier.",
              badges=["jetbrains", "kotlin", "gradle"], note="Precio fijo desde USD %s" % _from("updates", "es"))),
    page("og-catalog", "hero",
         dict(label="Plugin catalog", h1="JetBrains & VS Code plugins\nfor real developer gaps",
              lede="Every plugin I build for JetBrains IDEs and VS Code: filter by category and price and see the gap each one fixes.",
              badges=["jetbrains", "vscode", "free", "freemium", "paid"], note="Filter by category, platform and price"),
         dict(label="Catálogo de plugins", h1="Plugins para JetBrains y VS Code\nque resuelven brechas reales",
              lede="Todos los plugins que construyo para IDE de JetBrains y VS Code: filtra por categoría y precio y mira la brecha que resuelve cada uno.",
              badges=["jetbrains", "vscode", "free", "freemium", "paid"], note="Filtra por categoría, plataforma y precio")),
    page("og-methodology", "hero",
         dict(label="Methodology", h1="How a gap becomes a fix",
              lede="How I investigate and fix performance, security and reliability problems, and how I report the catalog data.",
              badges=["perf", "security", "reliability"], note="Investigate · Reproduce · Fix · Report"),
         dict(label="Metodología", h1="De la brecha a la solución",
              lede="Cómo investigo y corrijo los problemas de rendimiento, seguridad y fiabilidad, y cómo reporto los datos del catálogo.",
              badges=["perf", "security", "reliability"], note="Investigar · Reproducir · Corregir · Reportar")),
    page("og-evidence", "hero",
         dict(label="Engineering & Evidence", h1="Everything that backs the work",
              lede="My root-cause analysis and fixes in the IntelliJ Platform, security reports that maintainers fixed and my plugin case studies, each with a public source.",
              badges=["platform", "github", "security"], note="Tickets · Security reports · Audits · Case studies"),
         dict(label="Ingeniería y evidencia", h1="Todo lo que respalda el trabajo",
              lede="Mi análisis de causa raíz y mis correcciones en IntelliJ Platform, reportes de seguridad que corrigieron los mantenedores y mis casos de estudio, cada uno con fuente pública.",
              badges=["platform", "github", "security"], note="Tickets · Reportes · Auditorías · Casos")),
    page("og-evidence-case-studies", "hero",
         dict(label="Case studies", h1="Plugins with the strongest evidence",
              lede="A freeze pattern JetBrains named itself, a compliance gap cloud tools cannot clear, and injection sinks behind real CVEs.",
              badges=["static", "perf", "security"], note="Engineering & Evidence"),
         dict(label="Casos de estudio", h1="Plugins con la evidencia\nmás sólida",
              lede="Un congelamiento que nombró JetBrains, una brecha de cumplimiento que la nube no cubre y sinks de inyección con CVE reales.",
              badges=["static", "perf", "security"], note="Ingeniería y evidencia")),
    page("og-evidence-jetbrains-tickets", "hero",
         dict(label="JetBrains Platform tickets", h1="Root-cause reports in the\nIntelliJ Platform",
              lede="Bugs I filed in JetBrains' YouTrack after my catalog check found them in IntelliJ's source, plus my root-cause analysis on existing tickets.",
              badges=["idea", "platform"], note="Engineering & Evidence"),
         dict(label="Tickets de JetBrains Platform", h1="Reportes de causa raíz en\nIntelliJ Platform",
              lede="Errores que reporté en el YouTrack de JetBrains tras hallarlos mi control del catálogo en el código de IntelliJ, y mi análisis de causa raíz en tickets existentes.",
              badges=["idea", "platform"], note="Ingeniería y evidencia")),
    page("og-evidence-security-reports", "hero",
         dict(label="Open-source security reports", h1="Vulnerable dependencies,\nfixed by maintainers",
              lede="Advisories I reported to open-source maintainers, each checked against the exact pinned version in OSV and listed once fixed.",
              badges=["github", "security"], note="Engineering & Evidence"),
         dict(label="Reportes de seguridad", h1="Dependencias vulnerables,\ncorregidas por sus mantenedores",
              lede="Avisos que reporté a mantenedores de código abierto, cada uno verificado contra la versión exacta fijada en OSV y publicado cuando se corrigió.",
              badges=["github", "security"], note="Ingeniería y evidencia")),
    page("og-evidence-third-party-audits", "hero",
         dict(label="Third-party plugin audits", h1="Findings in other vendors'\nplugins, fixed by them",
              lede="Performance findings I reported in third-party IntelliJ plugins, with the root cause and a suggested fix, listed once public.",
              badges=["platform", "perf", "audit"], note="Engineering & Evidence"),
         dict(label="Auditorías de plugins de terceros", h1="Hallazgos en plugins de otros\nproveedores, corregidos por ellos",
              lede="Hallazgos de rendimiento que reporté en plugins de terceros para IntelliJ, con la causa raíz y un arreglo sugerido, publicados cuando son públicos.",
              badges=["platform", "perf", "audit"], note="Ingeniería y evidencia")),
    page("og-contact", "hero",
         dict(label="Contact", h1="Get in touch",
              lede="Write to me about audits and engineering work, plugin support or partnerships, by email, GitHub, JetBrains Marketplace or LinkedIn.",
              badges=["email", "github", "marketplace", "linkedin"], note="Email · GitHub · JetBrains · LinkedIn"),
         dict(label="Contacto", h1="Ponte en contacto",
              lede="Escríbeme sobre auditorías y trabajo de ingeniería, soporte de plugins o alianzas, por correo, GitHub, JetBrains Marketplace o LinkedIn.",
              badges=["email", "github", "marketplace", "linkedin"], note="Correo · GitHub · JetBrains · LinkedIn")),
    page("og-security", "hero",
         dict(label="Security", h1="What my plugins do with your\ncode, and what they don't",
              lede="What my plugins do and don't do with your code, how I handle vulnerability reports, and where certification stands.",
              badges=["security", "github"], note="Responsible disclosure · No telemetry"),
         dict(label="Seguridad", h1="Qué hacen mis plugins con tu\ncódigo, y qué no",
              lede="Qué hacen y qué no hacen mis plugins con tu código, cómo manejo los reportes de vulnerabilidades y en qué punto está la certificación.",
              badges=["security", "github"], note="Divulgación responsable · Sin telemetría")),
    page("og-privacy", "hero",
         dict(label="Privacy", h1="A short privacy policy",
              lede="What this site collects, what it doesn't, and why: a short policy, because the data footprint is short.",
              badges=[("No accounts", "shield", "dark"), ("No ad tracking", "shield", "dark")], note="Gap Hunter Labs"),
         dict(label="Privacidad", h1="Una política de privacidad corta",
              lede="Qué recoge este sitio, qué no y por qué: una política corta, porque la huella de datos real del sitio es corta.",
              badges=[("No accounts", "shield", "dark"), ("No ad tracking", "shield", "dark")], note="Gap Hunter Labs")),
    page("og-terms", "hero",
         dict(label="Terms", h1="Terms of Service",
              lede="What this catalog is, what it isn't, and who is responsible for what.",
              badges=["jetbrains", "vscode"], note="Gap Hunter Labs"),
         dict(label="Términos", h1="Términos de servicio",
              lede="Qué es este catálogo, qué no es y quién responde por qué.",
              badges=["jetbrains", "vscode"], note="Gap Hunter Labs")),
    page("og-eula", "hero",
         dict(label="License (EULA)", h1="End User License Agreement",
              lede="License terms for the paid Gap Hunter Labs plugins on JetBrains Marketplace: license, source code, warranty, liability and support.",
              badges=["marketplace", ("Apache-2.0", "code", "dark")], note="Paid plugins · Apache-2.0 source"),
         dict(label="Licencia (EULA)", h1="Acuerdo de Licencia\nde Usuario Final",
              lede="Términos de licencia de los plugins de pago de Gap Hunter Labs en JetBrains Marketplace: licencia, código fuente, garantía, responsabilidad y soporte.",
              badges=["marketplace", ("Apache-2.0", "code", "dark")], note="Plugins de pago · Código Apache-2.0")),
    page("og-ghl-jail", "hero",
         dict(label="Open-source tool", h1="A one-line Windows sandbox\nfor untrusted CLIs",
              lede="Run a command-line tool so it can only touch one project folder, not your SSH keys, cloud tokens or .env. No admin, no driver.",
              badges=["windows", "python", "security"], note="No admin · No driver · Just Python"),
         dict(label="Herramienta de código abierto", h1="Un sandbox de Windows de una\nlínea para CLIs no confiables",
              lede="Ejecuta una herramienta de línea de comandos para que solo toque una carpeta de proyecto, no tus claves SSH, tokens de la nube ni tu .env. Sin admin, sin controlador.",
              badges=["windows", "python", "security"], note="Sin admin · Sin controlador · Solo Python")),
    page("og-sponsors", "hero",
         dict(label="Sponsors", h1="Sponsor the work",
              lede="Fund the upstream fixes and the free JetBrains and VS Code tools. Five levels from USD 5 a month, and no sponsor can change a finding or a report.",
              badges=[("Sponsorship", "heart", "dark"), "jetbrains", "vscode", "security"], note="Independent by design"),
         dict(label="Patrocinadores", h1="Patrocina el trabajo",
              lede="Financia las correcciones al origen y las herramientas gratuitas para JetBrains y VS Code. Cinco niveles desde USD 5 al mes, y ningún patrocinador puede cambiar un hallazgo o un informe.",
              badges=[("Patrocinio", "heart", "dark"), "jetbrains", "vscode", "security"], note="Independiente por diseño")),
]


def jobs():
    out = []
    for p in PAGES:
        for lang in ("en", "es"):
            c = p[lang]
            css, builder = LAYOUTS[p["layout"]]
            body = builder(c, lang) if builder else hero_body(c["h1"], c["lede"], c["badges"], lang)
            stem = p["stem"] + (".es" if lang == "es" else "")
            out.append((stem, K.page_html(lang, body, css=css, label=c["label"], note=c["note"])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(ROOT), help="where to write the PNGs (default: the repo root)")
    ap.add_argument("--only", nargs="*", help="only these stems (e.g. og-methodology og-image.es)")
    ap.add_argument("--html", action="store_true", help="also write the source HTML next to the PNG (for debugging)")
    args = ap.parse_args()

    all_jobs = jobs()
    stems = {s for s, _ in all_jobs}
    if args.only:
        unknown = set(args.only) - stems
        if unknown:
            sys.exit("[build_page_og] ERROR: unknown stems: %s" % ", ".join(sorted(unknown)))
        all_jobs = [j for j in all_jobs if j[0] in set(args.only)]
    out_dir = Path(args.out_dir)
    if args.html:
        out_dir.mkdir(parents=True, exist_ok=True)
        for stem, html in all_jobs:
            (out_dir / (stem + ".html")).write_text(html, encoding="utf-8")
    written = K.render(all_jobs, lambda stem: out_dir / (stem + ".png"), label="build_page_og")
    for out in written:
        print("  %-42s %6.0f KB" % (out.name, out.stat().st_size / 1024))
    print("\nOK -- %d image(s)." % len(written))
    if not args.only and out_dir.resolve() == ROOT.resolve() and len(written) == len(all_jobs):
        # Only a full render into the site records which prices the images now show (see og_price_texts).
        OG_STAMP.write_text(json.dumps({"about": "Prices and delivery times the social images show, written by "
                                        "build_page_og.py after a full render. build_services.py --check compares it "
                                        "with data/services.json.", "texts": og_price_texts()},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("[build_page_og] %s updated" % OG_STAMP.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
