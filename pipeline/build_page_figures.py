#!/usr/bin/env python3
"""build_page_figures.py -- inlines the isometric figure of each hand-made English page that has one.

The pages built by their own generator inline their figure there (home and sponsors in build_home.py, the catalog in
build_catalog_grid.py, the evidence hub in build_evidence.py). This covers the hand-made pages: each one holds
    <!-- PRERENDER:ISO:<name>:START --><!-- PRERENDER:ISO:<name>:END -->
exactly once, and iso_figures.py applies the figure rules again before inlining, so a stale or hand-edited SVG stops
the build. build_i18n.py copies the result to the Spanish pages afterwards.

Usage:
    python pipeline/build_page_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import iso_figures  # noqa: E402

ROOT = HERE.parent
PAGES = (
    ("services/index.html", "services"),
    ("security/index.html", "security"),
    ("writing/index.html", "writing"),
)


def build(root: Path = ROOT) -> list[str]:
    changed = []
    for rel, figure in PAGES:
        path = root / rel
        raw = path.read_bytes().decode("utf-8")
        html = iso_figures.inject_or_die(raw, figure, rel, "build_page_figures")
        if html != raw:
            path.write_bytes(html.encode("utf-8"))   # bytes in, bytes out: the page keeps its line endings
            changed.append(rel)
    return changed


def main() -> int:
    changed = build()
    print("[build_page_figures] %d page(s), %d updated%s"
          % (len(PAGES), len(changed), (": " + ", ".join(changed)) if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
