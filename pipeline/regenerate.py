#!/usr/bin/env python3
"""regenerate.py -- the one place that knows the order in which the site's generated files are rebuilt.

Why it exists (2026-11-09): the order lived in three lists (the catalog workflow, a document, and whoever ran the
scripts by hand) and they disagreed. Merging #29 and #30 left the live site out of step with its own generators:
  - #29 changed build_plugin_pages.py but committed no page, so 146 plugin pages (and their Spanish copies) kept a
    row the generator no longer writes;
  - #30 regenerated with a short order that skipped build_writing_feed.py, so the Spanish Blog page linked the
    English feed;
  - the VS Code workflow committed new data without rebuilding any page, so the catalog and the search index lagged
    behind it until the next catalog run.
Both workflows now call this script, and pull requests run it with --check.

Usage:
  python pipeline/regenerate.py              # rebuild everything, in order
  python pipeline/regenerate.py --strict     # same, and fail on any untranslated Spanish text
  python pipeline/regenerate.py --check      # rebuild, then fail if any tracked file changed (for CI: the
                                             # committed files must be exactly what the generators produce)
  python pipeline/regenerate.py --list       # print the order
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
ROOT = PIPELINE.parent

# (script, arguments, why it sits here). The order is checked by pipeline/tests/test_regenerate.py.
STEPS = (
    ("build_services.py", (), "service figures, the OfferCatalog and the contact form list, in the English pages"),
    ("build_chrome.py", (), "header and footer of the hand-made English pages (the footer reads data/services.json)"),
    ("build_catalog_grid.py", (), "the catalog's pre-rendered grid and table"),
    ("build_home.py", (), "the home's pre-rendered blocks (metrics, tools, catalog line, sponsors)"),
    ("build_blog.py", (), "the Blog index from data/blog-cases.json"),
    ("build_plugin_pages.py", ("--sitemap", "--inject"), "one page per plugin, the sitemap and the hash shim"),
    ("build_feed.py", (), "the plugins RSS feed"),
    ("build_i18n.py", (), "every Spanish page, copied from the English ones: after every English generator"),
    ("build_writing_feed.py", (), "the Blog feeds and their <link> in both Blog indexes: after build_i18n, which "
                                  "copies the English <head> into the Spanish page"),
    ("build_search_index.py", (), "the search data from the built pages, and its hash inside site-search.js and "
                                  "site-chrome.js: after every page"),
    ("version_assets.py", (), "the ?v= hash of every CSS and JS reference: last, because the steps above change "
                              "CSS and JS"),
)

# Generators that are deliberately not part of a rebuild, with the reason.
EXCLUDED = {
    "build_icons.py": "needs the simple-icons npm package; writes pipeline/icons.json only when a brand icon is added",
    "build_og_images.py": "renders one PNG per plugin with Chromium; run by hand when a plugin is added",
    "build_page_og.py": "renders the page social images with Chromium; build_services.py --check fails when their "
                        "prices are out of date",
}


def git_status():
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8")
    if out.returncode:
        sys.exit("[regenerate] ERROR: git status failed: %s" % out.stderr.strip())
    return [line for line in out.stdout.splitlines() if line.strip()]


def run(strict):
    for script, args, _ in STEPS:
        extra = ("--strict",) if strict and script == "build_i18n.py" else ()
        cmd = [sys.executable, str(PIPELINE / script), *args, *extra]
        print("[regenerate] %s" % " ".join([script, *args, *extra]), flush=True)
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode:
            sys.exit("[regenerate] ERROR: %s failed with exit code %d; the steps after it did not run"
                     % (script, r.returncode))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="fail on any untranslated Spanish text")
    ap.add_argument("--check", action="store_true", help="fail if the rebuild changes any file (needs a clean tree)")
    ap.add_argument("--list", action="store_true", help="print the order and exit")
    args = ap.parse_args()
    if args.list:
        for i, (script, a, why) in enumerate(STEPS, 1):
            print("%2d. %s  -- %s" % (i, " ".join([script, *a]), why))
        return 0
    if args.check:
        dirty = git_status()
        if dirty:
            print("[regenerate] ERROR: --check needs a clean working tree; %d file(s) already differ, e.g. %s"
                  % (len(dirty), dirty[0]), file=sys.stderr)
            return 2
    run(args.strict)
    if args.check:
        changed = git_status()
        if changed:
            print("[regenerate] ERROR: %d committed file(s) are not what the generators produce. Run "
                  "python pipeline/regenerate.py --strict and commit the result:" % len(changed), file=sys.stderr)
            for line in changed[:40]:
                print("   " + line, file=sys.stderr)
            if len(changed) > 40:
                print("   ... and %d more" % (len(changed) - 40), file=sys.stderr)
            return 1
        print("[regenerate] every generated file is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
