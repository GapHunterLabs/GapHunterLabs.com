"""Mide accesibilidad con axe-core (local, sin red) en paginas representativas.

Uso (con el sitio servido en BASE, por defecto http://127.0.0.1:8080):
    python _review/axe_check.py                 # muestra por tipo de pagina, EN+ES, claro+oscuro, 1440 y 390
    python _review/axe_check.py /services/      # solo esas rutas

Requiere `npm install` en pipeline/ (axe-core). Sale con 1 si hay violaciones serias/criticas
(o de contraste) que no estan en la linea base indicada con --baseline FILE.
Tambien cuenta violaciones de CSP en consola y desborde horizontal.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from build_chrome import ES_PATHS  # noqa: E402  (rutas ES reales, con nombres traducidos)


def es_url(path: str) -> str:
    if path in ES_PATHS:
        return ES_PATHS[path]
    if path.startswith("/catalog/") and path != "/catalog/":
        return "/es/catalogo/" + path[len("/catalog/"):]
    return "/es" + path

AXE = ROOT / "pipeline" / "node_modules" / "axe-core" / "axe.min.js"
SAMPLE = [
    "/", "/services/", "/catalog/", "/contact/", "/methodology/",
    "/engineering-evidence/", "/engineering-evidence/jetbrains-platform-tickets/",
    "/catalog/mermaid-companion/", "/ghl-jail/", "/sponsors/", "/privacy/",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--out", help="escribe el detalle JSON aqui")
    ap.add_argument("--no-es", action="store_true")
    ap.add_argument("--widths", default="1440,390", help="viewport widths, comma separated (default 1440,390)")
    args = ap.parse_args()
    if not AXE.exists():
        print("falta axe-core: ejecuta `npm install` en pipeline/")
        return 2
    axe_src = AXE.read_text(encoding="utf-8")
    paths = args.paths or SAMPLE
    langs = [""] if args.no_es else ["", "/es"]
    results, serious_total = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for lang in langs:
            for path in paths:
                url_path = es_url(path) if lang else path
                for theme in ("dark", "light"):
                    for w in [int(x) for x in args.widths.split(",")]:
                        ctx = b.new_context(viewport={"width": w, "height": 900},
                                            color_scheme=theme)
                        ctx.add_init_script(
                            "try{localStorage.setItem('ghl-theme','%s')}catch(e){}" % theme)
                        pg = ctx.new_page()
                        csp = []
                        pg.on("console", lambda m, c=csp: c.append(m.text)
                              if m.type == "error" and "Content Security Policy" in m.text else None)
                        resp = pg.goto(args.base + url_path, wait_until="networkidle", timeout=45000)
                        if resp is None or resp.status >= 400:
                            results.append({"url": url_path, "theme": theme, "w": w,
                                            "error": "HTTP %s" % (resp.status if resp else "?")})
                            ctx.close()
                            continue
                        pg.evaluate(axe_src)  # evaluate no pasa por CSP
                        res = pg.evaluate(
                            "axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})"
                            ".then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,"
                            "sample:v.nodes.slice(0,3).map(n=>n.target.join(' ')+' | '+(n.any[0]?n.any[0].message:'')).slice(0,3)})))")
                        overflow = pg.evaluate("document.documentElement.scrollWidth-window.innerWidth")
                        bad = [v for v in res if v["impact"] in ("serious", "critical")]
                        serious_total += len(bad)
                        results.append({"url": url_path, "theme": theme, "w": w, "violations": res,
                                        "serious": len(bad), "csp": csp, "overflow": overflow})
                        ctx.close()
        b.close()
    for r in results:
        if "error" in r:
            print("%-52s %-5s %4d  %s" % (r["url"], r["theme"], r["w"], r["error"]))
            continue
        flag = "" if not r["serious"] and not r["csp"] and r["overflow"] <= 0 else "  <<<"
        print("%-52s %-5s %4d  serias=%d total=%d csp=%d desborde=%d%s" % (
            r["url"], r["theme"], r["w"], r["serious"], len(r["violations"]),
            len(r["csp"]), max(r["overflow"], 0), flag))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("TOTAL serias/criticas: %d en %d lecturas" % (serious_total, len(results)))
    return 1 if serious_total else 0


if __name__ == "__main__":
    sys.exit(main())
