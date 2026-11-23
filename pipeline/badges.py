# -*- coding: utf-8 -*-
"""
badges.py -- insignias (icono + texto) y tabla de insignias como HTML estatico.

Las insignias son <span> con un <svg> en linea (path de pipeline/icons.json), sin
imagenes ni peticiones externas, asi que pasan la CSP del sitio y pintan en el primer
render. Los estilos viven en css-src/tailwind.css (clase .badge y variantes) y salen
compilados en css/tw.css.

Variantes
  brand  relleno del color de marca; el color del texto (blanco o casi negro) se elige
         por contraste WCAG >= 4.5:1. Si ninguno llega, o la marca es casi negra, pasa a dark.
  dark   fondo grafito con borde; el icono va en el color del texto.
  soft   chip claro fijo (igual en ambos temas) con el icono en color de marca si contrasta.

Uso:
    from badges import badge, badge_table
    badge("Kotlin", icon="kotlin")                     # brand, color tomado del icono
    badge("Static analysis", icon="code", variant="dark")
"""
from __future__ import annotations

import html
import json
from pathlib import Path

_ICONS = json.loads((Path(__file__).resolve().parent / "icons.json").read_text(encoding="utf-8"))["icons"]
INK = "0A0A0A"
SOFT_BG = "F3F4F6"
SOFT_FG = "1F2937"


def _lum(hex6: str) -> float:
    def ch(i):
        v = int(hex6[i:i + 2], 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(0) + 0.7152 * ch(2) + 0.0722 * ch(4)


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def icon_svg(name: str) -> str:
    ic = _ICONS.get(name)
    if not ic:
        raise KeyError("icono desconocido: %s (agregalo en build_icons.py)" % name)
    return ('<svg class="b-ico" viewBox="%s" aria-hidden="true" focusable="false">'
            '<path d="%s"/></svg>' % (ic.get("viewBox", "0 0 24 24"), ic["d"]))


def badge(label: str, icon: str | None = None, variant: str = "brand", hex6: str | None = None,
          href: str | None = None, extra_class: str = "") -> str:
    """HTML de una insignia. `label` ya viene escapado por el llamador solo si contiene entidades;
    aqui se escapa siempre (usa textos planos)."""
    ic = _ICONS.get(icon) if icon else None
    if variant == "brand":
        hex6 = (hex6 or (ic or {}).get("hex") or "").upper()
        if not hex6 or _lum(hex6) < 0.02:
            variant = "dark"
        else:
            white, ink = contrast(hex6, "FFFFFF"), contrast(hex6, INK)
            fg, ratio = ("FFFFFF", white) if white >= ink else (INK, ink)
            if ratio < 4.5:
                variant = "dark"
    style = ""
    if variant == "brand":
        style = ' style="--b-bg:#%s;--b-fg:#%s"' % (hex6, fg)
    elif variant == "soft" and ic and ic.get("hex"):
        h = ic["hex"].upper()
        if contrast(h, SOFT_BG) >= 3.0:
            style = ' style="--b-ico:#%s"' % h
    cls = ("badge badge--%s %s" % (variant, extra_class)).strip()
    inner = (icon_svg(icon) if ic else "") + "<span>%s</span>" % html.escape(label, quote=False)
    if href:
        return '<a class="%s" href="%s"%s>%s</a>' % (cls, html.escape(href, quote=True), style, inner)
    return '<span class="%s"%s>%s</span>' % (cls, style, inner)


def price_badge(key: str, text: str) -> str:
    """Pricing as a status badge: the dot color (is-free / is-freemium / is-paid / is-pending) backs the label, never replaces it."""
    return '<span class="badge badge-status is-%s">%s</span>' % (html.escape(key, quote=True), html.escape(text, quote=False))


def badge_row(items) -> str:
    """items: iterable de dicts/tuplas para badge(); devuelve <div class="badge-row">."""
    out = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            out.append(badge(**it))
        else:
            out.append(badge(*it))
    return '<div class="badge-row">%s</div>' % "".join(out)


def badge_table(caption: str, rows, label_id: str) -> str:
    """Tabla de insignias: encabezado centrado + filas con bandas alternas.
    rows: lista de (nombre_de_fila, [items]) -- nombre accesible de la fila (visible solo para lectores).
    Semantica: <table> real, con un <th scope=row> oculto visualmente por fila."""
    body = []
    for name, items in rows:
        body.append('<tr><th scope="row" class="sr-only">%s</th><td>%s</td></tr>'
                    % (html.escape(name, quote=False), badge_row(items)))
    return ('<table class="badge-table" aria-labelledby="%s"><caption id="%s">%s</caption><tbody>%s</tbody></table>'
            % (label_id, label_id, html.escape(caption, quote=False), "".join(body)))
