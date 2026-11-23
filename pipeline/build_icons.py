#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_icons.py -- extrae de simple-icons (CC0-1.0, devDependency de pipeline/) los
iconos de marca que usa el sitio y los guarda en pipeline/icons.json junto con unos
iconos genericos dibujados a mano. badges.py los incrusta como <svg> en linea: sin
peticiones, sin CDN, y compatibles con la CSP (img-src 'self' data:).

Se corre solo al cambiar la lista ICONS (el JSON se versiona; build_home y el resto
de generadores no necesitan Node):

    cd pipeline && npm install && python build_icons.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SI = HERE / "node_modules" / "simple-icons"
OUT = HERE / "icons.json"

# slug de simple-icons -> nombre corto en el sitio
ICONS = {
    "jetbrains": "jetbrains", "intellijidea": "intellij-idea", "kotlin": "kotlin",
    "gradle": "gradle", "openjdk": "java", "python": "python", "github": "github",
    "githubactions": "github-actions", "git": "git", "markdown": "markdown",
    "junit5": "junit", "cloudflare": "cloudflare", "gitlab": "gitlab", "go": "go", "linkedin": "linkedin",
    "atlassian": "atlassian",
}

# Genericos (no son marcas): 24x24, trazo relleno.
GENERIC = {
    "vscode": ("M16.5 3 21 5.2v13.6L16.5 21 7 12.9 3.6 15.6 2 14.8V9.2l1.6-.8L7 11.1 16.5 3Zm0 4.2-5 4.8 5 4.8V7.2Z",
               "Visual Studio Code (generic mark)"),
    "windows": ("M3 5.5 11 4.4v7H3v-6Zm9 -1.2L21 3v8.4h-9V4.3ZM3 12.6h8v7l-8-1.1v-5.9Zm9 0h9V21l-9-1.3v-7.1Z",
                "Windows (generic mark)"),
    "search": ("M10 3a7 7 0 1 0 4.2 12.6l4.6 4.6 1.4-1.4-4.6-4.6A7 7 0 0 0 10 3Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z", "search"),
    "shield": ("M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Zm0 2.1 6 2.2V11c0 3.9-2.5 7.4-6 8.9-3.5-1.5-6-5-6-8.9V6.3l6-2.2Z", "security"),
    "gauge": ("M12 4a10 10 0 0 0-8.7 15h2.2A8 8 0 1 1 18.5 19h2.2A10 10 0 0 0 12 4Zm4.5 4.5-4.2 4.2a2 2 0 1 0 1.4 1.4l4.2-4.2-1.4-1.4Z", "performance"),
    "code": ("M8.6 16.6 4 12l4.6-4.6L10 8.8 6.8 12l3.2 3.2-1.4 1.4Zm6.8 0-1.4-1.4 3.2-3.2L14 8.8l1.4-1.4L20 12l-4.6 4.6Z", "code"),
    "mail": ("M3 5h18v14H3V5Zm2 2v.6l7 4.4 7-4.4V7H5Zm14 3L12 14.4 5 10v7h14v-7Z", "email"),
    "heart": ("M12 21 10.55 19.7C5.4 15.1 2 12 2 8.2 2 5.1 4.4 2.7 7.5 2.7c1.75 0 3.4.8 4.5 2.1 1.1-1.3 2.75-2.1 4.5-2.1 3.1 0 5.5 2.4 5.5 5.5 0 3.8-3.4 6.9-8.55 11.5L12 21Z", "sponsors"),
    "layers": ("M12 2 2 7l10 5 10-5-10-5Zm-8.2 9L2 12l10 5 10-5-1.8-1L12 15 3.8 11Zm0 5L2 17l10 5 10-5-1.8-1L12 20l-8.2-4Z", "layers"),
}


def main() -> int:
    if not SI.exists():
        print("falta simple-icons: ejecuta `npm install` en pipeline/")
        return 2
    data = SI / "_data" / "simple-icons.json"
    by_title = {m["title"]: m for m in json.loads(data.read_text(encoding="utf-8"))["icons"]} if data.exists() else {}
    out = {}
    for slug, name in ICONS.items():
        svg_file = SI / "icons" / ("%s.svg" % slug)
        if not svg_file.exists():
            print("AVISO: no existe %s en simple-icons" % slug)
            continue
        svg = svg_file.read_text(encoding="utf-8")
        d = re.search(r'<path d="([^"]+)"', svg).group(1)
        title = re.search(r"<title>([^<]+)</title>", svg).group(1)
        hexc = (by_title.get(title) or {}).get("hex")
        out[name] = {"d": d, "title": title, "hex": hexc, "kind": "brand"}
    for name, (d, title) in GENERIC.items():
        out[name] = {"d": d, "title": title, "hex": None, "kind": "generic"}
    OUT.write_text(json.dumps({"_license": "Brand marks: simple-icons, CC0-1.0. Brand names and logos belong to their owners.",
                               "icons": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("icons.json: %d iconos (%d de marca)" % (len(out), sum(1 for v in out.values() if v["kind"] == "brand")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
