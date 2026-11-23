#!/usr/bin/env python3
"""build_iso_figures.py -- draw the isometric figures (pipeline/iso/figures/*.cjs) into pipeline/iso/out/*.svg.

Runs pipeline/iso/build.cjs with Node. It needs the build-time packages in pipeline/package.json
(@elchininet/isometric and jsdom: npm ci in pipeline/). The output is committed; the page generators only read it,
so this script is not part of regenerate.py. Run it by hand after changing a figure or the kit, then
python pipeline/regenerate.py --strict.

Fails when a figure breaks its budget (40 KB, 400 nodes, no filters, no hard-coded colors, prefixed ids).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("[build_iso_figures] ERROR: Node is not installed", file=sys.stderr)
        return 2
    if not (PIPELINE / "node_modules" / "@elchininet" / "isometric").is_dir():
        print("[build_iso_figures] ERROR: run npm ci in pipeline/ first", file=sys.stderr)
        return 2
    return subprocess.run([node, str(PIPELINE / "iso" / "build.cjs")], cwd=PIPELINE).returncode


if __name__ == "__main__":
    sys.exit(main())
