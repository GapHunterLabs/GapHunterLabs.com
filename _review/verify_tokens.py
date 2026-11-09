"""Syntax-check page scripts and report leftover raw values in style blocks."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from design_budget import english_pages  # noqa: E402

# 2026-11-09: the pages come from git (every English page, the catalog pages through the first one, the Spanish pages
# are copies), the same set the design budget measures. The fixed list of 2026-09-10 still checked laboratorio/, which
# is a redirect now, and missed every page added since. The old top-level *.html files are redirect stubs, checked in
# verify_static.py.
PAGES = [p for p in english_pages() if p.name == "index.html"]

RADIUS_LEFTOVER = re.compile(r"border-radius:\s*(4|5|6|7|8|9|10)px")
DURATION_LEFTOVER = re.compile(r"(?<![\d.])(0\.15s|0\.12s|0\.3s|0\.25s|0\.18s|0\.2s|0\.1s|\.4s|\.9s|\.12s|\.24s)")
EASE_LEFTOVER = re.compile(r"(?<!ease-standard: )(?<!ease-emphasized: )cubic-bezier\(\.(?:65|2),")
BARE_DURATION = re.compile(r"(?<![\d.])\.\d+s")


def style_blocks(html: str) -> str:
    return "\n".join(m.group(0) for m in re.finditer(r"<style\b[^>]*>.*?</style>", html, flags=re.I | re.S))


def scripts(html: str) -> list[str]:
    out = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.I | re.S):
        attrs, body = m.group(1), m.group(2)
        if "src=" in attrs or not body.strip():
            continue
        if "application/ld+json" in attrs or "speculationrules" in attrs:
            continue
        out.append(body)
    return out


def main() -> None:
    errors = 0
    for path in PAGES:
        # Every migrated page is literally named "index.html" now (it's
        # what makes GitHub Pages serve it extensionless), so path.name
        # / path.stem alone collide across pages -- use the ROOT-relative
        # path, slashes swapped for underscores, as the unique label for
        # both printed output and temp-file names.
        label_path = path.relative_to(ROOT).as_posix()
        stem = label_path.replace("/", "_").removesuffix(".html")
        html = path.read_text(encoding="utf-8")
        css = style_blocks(html)
        for label, rx in (
            ("radius px", RADIUS_LEFTOVER),
            ("migrated duration", DURATION_LEFTOVER),
            ("raw easing", EASE_LEFTOVER),
            ("leading-dot duration", BARE_DURATION),
        ):
            hits = rx.findall(css)
            if hits:
                print(f"{label_path} leftover {label}: {hits[:12]}")
                errors += 1
        if "var(--ease-standard);" in css.split(":root", 1)[-1][:800] and "cubic-bezier(.65,0,.35,1)" not in css:
            print(f"{label_path} missing ease token values")
            errors += 1
        for i, body in enumerate(scripts(html), 1):
            tmp = ROOT / "_review" / f"_syntax_{stem}_{i}.js"
            tmp.write_text(body, encoding="utf-8")
            proc = subprocess.run(
                ["node", "-e", f"new Function(require('fs').readFileSync({tmp.as_posix()!r},'utf8'))"],
                capture_output=True,
                text=True,
            )
            tmp.unlink(missing_ok=True)
            if proc.returncode != 0:
                print(f"{label_path} script {i} syntax error:\n{proc.stderr}")
                errors += 1
            else:
                print(f"{label_path} script {i} ok")
    if errors:
        raise SystemExit(f"verify failed ({errors})")
    print("verify ok")


if __name__ == "__main__":
    main()
