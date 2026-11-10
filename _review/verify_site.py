#!/usr/bin/env python3
"""verify_site.py -- behaviour checks for the static site, run in a real browser (Playwright).

Covers what the other verifiers do not: the catalog filters, pager, table and platform tabs,
the home sections and their figures, the Ctrl+K search, theme and navigation, the contact
form, mobile overflow, internal links, redirect stubs and third-party requests. Each check
runs in its own browser context and reports PASS or FAIL; the exit code is 1 if any fails.

    python _review/verify_site.py                    # starts its own local server
    python _review/verify_site.py --base http://127.0.0.1:8080
    python _review/verify_site.py --only catalog,search
    python _review/verify_site.py --list
    python _review/verify_site.py --shots            # also saves screenshots to _review/screenshots/
    python _review/verify_site.py --browser "C:/path/to/msedge.exe"

Page structure and expectations come from the pages and from data/*.json, so a change in the
catalog does not need a change here. Update the checks when the markup changes.
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import math
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path(__file__).resolve().parent / "screenshots"
PAGE_SIZE = 15  # js/catalog.js
PNG_MAGIC = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
CATEGORIES = ("api", "devops", "security", "data", "quality", "codegen", "testing", "editor")
THIRD_PARTY_OK = ("gc.zgo.at", ".goatcounter.com")  # the only analytics the CSP allows

LANGS = {
    "en": dict(home="/", catalog="/catalog/", ficha="/catalog/openapi-companion/", contact="/contact/",
               services="/services/", pager=r"Page (\d+) of (\d+)", card_prefix="/catalog/"),
    "es": dict(home="/es/", catalog="/es/catalogo/", ficha="/es/catalogo/openapi-companion/", contact="/es/contacto/",
               services="/es/servicios/", pager=r"P[aá]gina (\d+) de (\d+)", card_prefix="/es/catalogo/"),
}

CHECKS: list[tuple[str, str, object]] = []


def check(group: str, name: str):
    def deco(fn):
        CHECKS.append((group, name, fn))
        return fn
    return deco


def expect(cond, message: str = "expectation failed"):
    if not cond:
        raise AssertionError(message)


def eq(actual, wanted, what: str):
    if actual != wanted:
        raise AssertionError("%s: got %r, expected %r" % (what, actual, wanted))


# ------------------------------------------------------------------------------ server
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *a):  # noqa: D401
        pass


def start_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


# ----------------------------------------------------------------------------- harness
class Env:
    def __init__(self, browser, base: str, shots: bool):
        self.browser, self.base, self.shots = browser, base, shots
        cat = json.loads((ROOT / "data" / "catalog-data.json").read_text(encoding="utf-8"))
        vsx_path = ROOT / "data" / "vscode-catalog-data.json"
        vsx = json.loads(vsx_path.read_text(encoding="utf-8")) if vsx_path.exists() else {}
        self.total_plugins = cat["totalPlugins"]
        self.total_downloads = cat["totalDownloads"]
        self.total_vsx = vsx.get("totalExtensions") or 0

    @contextlib.contextmanager
    def page(self, width=1440, height=1000, theme="dark", block_data=False, js=True):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=js,
                                       reduced_motion="reduce", device_scale_factor=1,
                                       locale="en-US")   # the site redirects / by the browser language
        if theme:
            ctx.add_init_script("try{localStorage.setItem('ghl-theme','%s')}catch(e){}" % theme)
        if block_data:
            ctx.route("**/data/*.json", lambda route: route.abort())
        page = ctx.new_page()
        page.set_default_timeout(8000)
        page.rec = SimpleNamespace(errors=[], requests=[])
        page.on("pageerror", lambda e: page.rec.errors.append(str(e)[:200]))
        page.on("request", lambda r: page.rec.requests.append(r.url))
        try:
            yield page
        finally:
            ctx.close()

    def go(self, page, path: str, wait="networkidle"):
        page.goto(self.base + path, wait_until=wait)

    def get(self, path: str) -> int:
        import urllib.request
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:  # noqa: PERF203
            return e.code

    def shot(self, page, name: str, full=False):
        if self.shots:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / (name + ".png")), full_page=full)


def visible_cards(page):
    return page.evaluate("[...document.querySelectorAll('#catalogGrid > *')].filter(e=>!e.hidden).map(e=>({cat:e.dataset.cat,pricing:e.dataset.pricing,"
                         "search:e.dataset.search,name:e.querySelector('.card-name').textContent.trim(),href:e.getAttribute('href')}))")


def all_cards(page):
    return page.evaluate("[...document.querySelectorAll('#catalogGrid > *')].map(e=>({cat:e.dataset.cat,pricing:e.dataset.pricing,search:e.dataset.search}))")


def pager_state(page, lang):
    text = page.locator(".catalog-pager-status").first.inner_text()
    m = re.search(LANGS[lang]["pager"], text)
    expect(m, "pager text not recognised: %r" % text)
    return int(m.group(1)), int(m.group(2))


# ==================================================================================== catalog
def _catalog_checks(lang: str):
    L = LANGS[lang]

    @check("catalog", "prerendered in the HTML without JavaScript [%s]" % lang)
    def _prerender(env: Env):
        with env.page(js=False) as p:
            env.go(p, L["catalog"], wait="load")
            n = p.locator("#catalogGrid > a.plugin-card").count()
            eq(n, env.total_plugins, "plugin cards in the raw HTML")
            bad = p.evaluate("[...document.querySelectorAll('#catalogGrid > a.plugin-card')].filter(a=>!a.getAttribute('href').startsWith('%s')).length" % L["card_prefix"])
            eq(bad, 0, "cards whose link is outside %s" % L["card_prefix"])

    @check("catalog", "pager: 15 per page, previous/next, last page [%s]" % lang)
    def _pager(env: Env):
        pages = math.ceil(env.total_plugins / PAGE_SIZE)
        with env.page() as p:
            env.go(p, L["catalog"])
            eq(len(visible_cards(p)), PAGE_SIZE, "visible cards on page 1")
            eq(pager_state(p, lang), (1, pages), "pager on load")
            expect(p.locator("[data-page-dir='-1']").first.is_disabled(), "previous should be disabled on page 1")
            p.locator("[data-page-dir='1']").first.click()
            eq(pager_state(p, lang), (2, pages), "pager after next")
            eq(len(visible_cards(p)), PAGE_SIZE, "visible cards on page 2")
            for _ in range(pages - 2):
                p.locator("[data-page-dir='1']").first.click()
            eq(pager_state(p, lang), (pages, pages), "pager on the last page")
            eq(len(visible_cards(p)), env.total_plugins - PAGE_SIZE * (pages - 1), "cards on the last page")
            expect(p.locator("[data-page-dir='1']").first.is_disabled(), "next should be disabled on the last page")
            env.shot(p, "catalog-%s-desktop" % lang)

    @check("catalog", "category filter via the URL, 8 categories [%s]" % lang)
    def _categories(env: Env):
        with env.page() as p:
            env.go(p, L["catalog"])
            cards = all_cards(p)
            for cat in CATEGORIES:
                env.go(p, "%s?category=%s" % (L["catalog"], cat))
                eq(p.locator("#categoryFilter").input_value(), cat, "select value for " + cat)
                vis = visible_cards(p)
                wanted = min(PAGE_SIZE, sum(1 for c in cards if c["cat"] == cat))
                eq(len(vis), wanted, "visible cards for " + cat)
                expect(wanted > 0, "category %s has no plugins" % cat)
                expect(all(v["cat"] == cat for v in vis), "a card of another category is visible under " + cat)

    @check("catalog", "text search and clearing it [%s]" % lang)
    def _search(env: Env):
        with env.page() as p:
            env.go(p, L["catalog"])
            cards = all_cards(p)
            p.locator("#searchInput").fill("Mermaid")
            p.wait_for_timeout(300)
            vis = visible_cards(p)
            wanted = min(PAGE_SIZE, sum(1 for c in cards if "mermaid" in (c["search"] or "")))
            eq(len(vis), wanted, "cards matching 'Mermaid'")
            expect(wanted >= 1 and "Mermaid" in vis[0]["name"], "Mermaid Companion should be the first match")
            p.locator("#searchInput").fill("")
            p.wait_for_timeout(300)
            eq(len(visible_cards(p)), PAGE_SIZE, "cards after clearing the search")

    @check("catalog", "pricing filter: free and paid & pro [%s]" % lang)
    def _pricing(env: Env):
        with env.page() as p:
            env.go(p, L["catalog"])
            cards = all_cards(p)
            p.locator("#pricingFilter").select_option("FREE")
            vis = visible_cards(p)
            eq(len(vis), min(PAGE_SIZE, sum(1 for c in cards if c["pricing"] == "FREE")), "free cards")
            expect(all(v["pricing"] == "FREE" for v in vis), "a non-free card is visible under Free")
            env.go(p, L["catalog"] + "?pricing=paid")
            vis = visible_cards(p)
            wanted = min(PAGE_SIZE, sum(1 for c in cards if c["pricing"] in ("FREEMIUM", "PAID")))
            eq(len(vis), wanted, "freemium + paid cards via ?pricing=paid")
            expect(all(v["pricing"] in ("FREEMIUM", "PAID") for v in vis), "a free card is visible under Paid & Pro")

    @check("catalog", "search without results offers the hire link [%s]" % lang)
    def _no_results(env: Env):
        with env.page() as p:
            env.go(p, L["catalog"])
            p.locator("#searchInput").fill("zzzzq")
            p.wait_for_timeout(300)
            eq(len(visible_cards(p)), 0, "visible cards for a nonsense query")
            box = p.locator("#fieldNoResults")
            expect(box.is_visible(), "the no-results box should be visible")
            href = box.locator("a.miss-cta").get_attribute("href")
            expect("intent=hire" in href and "need=zzzzq" in href, "miss link should carry the intent and the query: %r" % href)

    @check("catalog", "table view: rows, order and sorting [%s]" % lang)
    def _table(env: Env):
        with env.page() as p:
            env.go(p, L["catalog"])
            p.locator("#modeToggle [data-mode='table']").click()
            expect(p.locator("#tableView").is_visible(), "table view should be visible")
            rows = p.evaluate("[...document.querySelectorAll('#tbody tr.row')].filter(r=>!r.hidden).map(r=>({d:+r.dataset.downloads,n:r.dataset.name,badge:!!r.querySelector('.price-badge')}))")
            eq(len(rows), PAGE_SIZE, "visible rows")
            expect(all(r["badge"] for r in rows), "every row should show a pricing badge")
            d = [r["d"] for r in rows]
            expect(d == sorted(d, reverse=True), "rows should start sorted by downloads, descending: %r" % d)
            p.locator("thead th[data-key='name']").click()
            first = [r for r in p.evaluate("[...document.querySelectorAll('#tbody tr.row')].filter(r=>!r.hidden).map(r=>r.dataset.name)")]
            expect(first == sorted(first) or first == sorted(first, reverse=True), "rows should be sorted by name after the click")
            p.locator("thead th[data-key='name']").click()
            second = p.evaluate("[...document.querySelectorAll('#tbody tr.row')].filter(r=>!r.hidden).map(r=>r.dataset.name)")
            expect(second == first[::-1] or second != first, "a second click should flip the order")
            env.shot(p, "catalog-%s-table" % lang)

    @check("catalog", "keeps working with the data files unreachable [%s]" % lang)
    def _data_blocked(env: Env):
        with env.page(block_data=True) as p:
            env.go(p, L["catalog"], wait="load")
            p.wait_for_timeout(500)
            p.locator("#searchInput").fill("Mermaid")
            p.wait_for_timeout(300)
            expect(len(visible_cards(p)) >= 1, "search should still work without data/*.json")
            eq(p.rec.errors, [], "uncaught page errors")


for _lang in ("en", "es"):
    _catalog_checks(_lang)


@check("catalog", "platform tabs: VS Code panel and brand colors")
def _tabs(env: Env):
    blue = "rgb(0, 122, 204)"
    for theme in ("dark", "light"):
        with env.page(theme=theme) as p:
            env.go(p, "/catalog/")
            color = lambda plat: p.evaluate("getComputedStyle(document.querySelector('.platform-tab[data-platform=\"%s\"] svg')).color" % plat)
            eq(p.locator(".platform-tab[data-platform=jetbrains]").get_attribute("aria-selected"), "true", "JetBrains tab selected on load")
            expect(color("jetbrains") != blue, "the JetBrains icon must not use the VS Code blue (%s)" % theme)
            p.locator(".platform-tab[data-platform=vscode]").click()
            p.wait_for_timeout(300)
            eq(p.locator(".platform-tab[data-platform=vscode]").get_attribute("aria-selected"), "true", "VS Code tab selected")
            eq(color("vscode"), blue, "VS Code icon color when selected (%s)" % theme)
            expect(p.locator("#vsxSection").is_visible() and not p.locator("#jetbrains").is_visible(), "panels should switch")
            expect("platform=vscode" in p.url, "the URL should record the platform: " + p.url)
            expect(p.locator("#vsxGrid > *:not([hidden])").count() > 0, "no VS Code cards are visible")
            env.shot(p, "catalog-vscode-" + theme)


@check("catalog", "opening ?platform=vscode shows the VS Code panel")
def _tab_url(env: Env):
    with env.page() as p:
        env.go(p, "/catalog/?platform=vscode")
        expect(p.locator("#vsxSection").is_visible(), "VS Code panel should be open from the URL")


# 2026-11-09: the home checks moved to _review/site-behavior.test.js, which runs in CI ('home: hero, profile card, figures, investigations, tools, stack').
# They had gone stale here after the redesigns, and nothing ran this file.


# =============================================================================== chrome
@check("chrome", "theme: first visit dark, choices persist, system clears the attribute")
def _theme(env: Env):
    with env.page(theme=None) as p:
        env.go(p, "/")
        eq(p.evaluate("document.documentElement.getAttribute('data-theme')"), "dark", "first visit")
        p.locator("footer [data-theme-choice=light]").click()
        eq(p.evaluate("document.documentElement.getAttribute('data-theme')"), "light", "after choosing light")
        eq(p.evaluate("localStorage.getItem('ghl-theme')"), "light", "stored choice")
        p.reload(wait_until="networkidle")
        eq(p.evaluate("document.documentElement.getAttribute('data-theme')"), "light", "after reload")
        eq(p.locator("footer [data-theme-choice=light]").get_attribute("aria-pressed"), "true", "pressed state")
        p.locator("footer [data-theme-choice=system]").click()
        eq(p.evaluate("document.documentElement.getAttribute('data-theme')"), None, "system removes the attribute")
        eq(p.evaluate("localStorage.getItem('ghl-theme')"), "system", "system is stored")


# 2026-11-09: the Ctrl+K search checks moved to _review/site-behavior.test.js, which runs in CI ('Ctrl+K search' and 'phone search').
# They had gone stale here after the redesigns, and nothing ran this file.


@check("chrome", "language switch lands on the Spanish home with lang=es")
def _lang_switch(env: Env):
    with env.page() as p:
        env.go(p, "/")
        p.locator(".gh-lang-btn").click()
        with p.expect_navigation():
            p.locator(".gh-lang a[href='/es/']").click()
        eq(urllib.parse.urlparse(p.url).path, "/es/", "path after switching")
        eq(p.evaluate("document.documentElement.lang"), "es", "html lang")


# ============================================================================== contact
# 2026-11-09: the contact form checks moved to _review/site-behavior.test.js, which runs in CI (the two 'contact:' tests).
# They had gone stale here after the redesigns, and nothing ran this file.


@check("contact", "?intent and ?need prefill the form")
def _contact_prefill(env: Env):
    with env.page() as p:
        env.go(p, "/contact/?intent=hire&need=openapi%20drift")
        expect(p.locator(".qa-item[data-target=hire]").get_attribute("class").count("is-active") == 1, "hire should be active")
        expect("openapi drift" in p.locator("#cfFields [name=message]").input_value(), "the message should carry the query")


@check("sponsors", "sponsors page: five levels, ways to join, reach figures and sponsor links marked rel=sponsored")
def _sponsors_page(env: Env):
    listed = json.loads((ROOT / "data" / "sponsors.json").read_text(encoding="utf-8")).get("sponsors", [])
    reach = json.loads((ROOT / "data" / "reach.json").read_text(encoding="utf-8"))
    li, site = reach["linkedin"], reach["site"]
    figures = [li["followers"], li["impressions"], li["membersReached"], site["visits"]]
    recent = li["recent"]
    figures += [recent["postImpressions7d"], recent["profileViewers90d"], recent["connections"], recent["searchAppearances"]]
    for lang, path, contact in (("en", "/sponsors/", "/contact/"), ("es", "/es/patrocinadores/", "/es/contacto/")):
        with env.page() as p:
            env.go(p, path)
            eq(p.locator(".sp-level").count(), 5, "levels [%s]" % lang)
            hrefs = p.evaluate("[...document.querySelectorAll('.get-row a')].map(a => a.getAttribute('href'))")
            expect(any("patreon.com" in h for h in hrefs), "the Patreon link is missing [%s]" % lang)
            expect(any("buymeacoffee.com" in h for h in hrefs), "the Buy Me a Coffee link is missing [%s]" % lang)
            expect(any(h.split("?")[0] == contact for h in hrefs),
                   "the company-sponsorship link should go to %s [%s]" % (contact, lang))
            eq(p.locator(".sp-reach .tw-bg-bg").count(), 4, "reach figures [%s]" % lang)
            sep = "," if lang == "en" else "."
            downloads = p.evaluate("document.querySelector('.sp-reach .tw-text-3xl').textContent.trim()")
            expect(re.fullmatch(r"\d{1,3}(%s\d{3})+" % re.escape(sep), downloads), "downloads separator [%s]: %r" % (lang, downloads))
            # the audience card prints data/reach.json: same numbers, the thousands separator of the language, dated
            eq(p.locator(".sp-audience .tw-bg-bg").count(), 8, "audience figures [%s]" % lang)
            want = [format(n, ",").replace(",", sep) for n in figures]
            eq(p.evaluate("[...document.querySelectorAll('.sp-audience .tw-text-3xl')].map(e => e.textContent.trim())"),
               want, "audience figures match data/reach.json [%s]" % lang)
            stamps = p.evaluate("[...document.querySelectorAll('.sp-audience time')].map(t => t.getAttribute('datetime'))")
            eq(stamps, [recent["searchFrom"], recent["searchTo"], site["from"], site["to"], li["from"], li["to"], reach["asOf"]], "audience dates [%s]" % lang)
            expect(not re.search(r"NaN|undefined|None", p.locator(".sp-audience").inner_text()),
                   "the audience card prints a broken value [%s]" % lang)
            eq(p.locator(".sp-wall").count() > 0, bool(listed), "the wall and data/sponsors.json disagree [%s]" % lang)
            if not listed:
                eq(p.locator(".sp-empty").count(), 1, "the open call [%s]" % lang)
            rels = p.evaluate("[...document.querySelectorAll('a.sp-logo, a.sp-person')].map(a => a.getAttribute('rel') || '')")
            expect(all("sponsored" in r for r in rels), "sponsor links must carry rel=sponsored [%s]" % lang)
            eq(len(rels), len([r for r in listed if r.get("url")]), "linked sponsors [%s]" % lang)


@check("sponsors", "home: the sponsors section links to the sponsors page")
def _sponsors_home(env: Env):
    for lang, home, target in (("en", "/", "/sponsors/"), ("es", "/es/", "/es/patrocinadores/")):
        with env.page() as p:
            env.go(p, home)
            expect(p.locator("#sponsors").count() == 1, "the sponsors section is missing [%s]" % lang)
            expect(p.locator("#sponsors a.btn[href='%s']" % target).count() == 1, "the call to action [%s]" % lang)


@check("sponsors", "sponsor links are counted per sponsor and place, keep rel=sponsored, and unlinked names stay plain")
def _sponsors_counted(env: Env):
    sys.path.insert(0, str(ROOT / "pipeline"))
    from build_home import sponsors_html
    rows = [{"name": "Acme Corp", "tier": "gold", "url": "https://acme.example/"},
            {"name": "Jane Roe", "tier": "backer", "url": "https://jane.example/"},
            {"name": "No Link", "tier": "supporter"}]
    for home, where, want in ((True, "home", ["sponsor-acme-corp-home"]),
                              (False, "page", ["sponsor-acme-corp-page", "sponsor-jane-roe-page"])):
        html = sponsors_html(rows, home=home)
        links = re.findall(r"<a [^>]*>", html)
        expect(links and all('rel="sponsored noopener"' in a for a in links), "sponsor links must carry rel=sponsored [%s]" % where)
        eq(re.findall(r'data-goatcounter-click="([^"]+)"', html), want, "sponsor click events [%s]" % where)
        expect(home or '<span class="sp-person"><span class="sp-name">No Link</span></span>' in html,
               "a sponsor without a URL must stay plain text")


@check("share", "Spanish pages translate their titles and social cards (not just the visible text)")
def _es_meta(env: Env):
    sys.path.insert(0, str(ROOT / "pipeline"))
    from build_chrome import ES_PATHS
    keys = ('property="og:title"', 'name="twitter:title"', 'property="og:description"', 'name="twitter:description"',
            'property="og:image:alt"', 'name="twitter:image:alt"', 'name="description"')

    def metas(path):
        rel = "index.html" if path == "/" else path.strip("/") + "/index.html"
        text = (ROOT / rel).read_text(encoding="utf-8")
        return {k: (re.search(r"<meta %s content=\"([^\"]*)\"" % re.escape(k), text) or [None, None])[1] for k in keys}

    def title_of(path):
        rel = "index.html" if path == "/" else path.strip("/") + "/index.html"
        return re.search(r"<title>(.*?)</title>", (ROOT / rel).read_text(encoding="utf-8"), re.S).group(1)

    same = []
    for en_path, es_path in ES_PATHS.items():
        en, es = metas(en_path), metas(es_path)
        # a card equal in both languages is fine when the page title is too ("Blog — Gap Hunter Labs")
        same_title = title_of(en_path) == title_of(es_path)
        same += ["%s %s" % (es_path, k.split('"')[1]) for k in keys
                 if en[k] and en[k] == es[k] and not (same_title and 'title' in k or same_title and 'image:alt' in k)]
    expect(not same, "still in English: " + "; ".join(same[:8]))


# Voice: everything I publish speaks as "I" (strict first person singular). The EULA keeps the licensor
# wording of its template ("the Developer") and plugin pages carry catalog data, so both are left out.
VOICE_EN = re.compile(
    r"\b[Ww]e\b|\b[Oo]ur(s|selves)?\b|\bus\b"
    r"|\bJoel (is|has|does|builds|writes|maintains|leads|runs|replies|responds)\b|\b(with|Email|Ask|Tell|Contact) Joel\b"
    r"|\bone engineer\b|\bthe (author|studio|team)\b"
    r"|\bGap Hunter Labs (is (the|an|a)|are|does|do|maintains|publishes|builds|ships|has|have|offers|provides|runs|never|will|keeps|tests|uses|reports)\b")
VOICE_ES = re.compile(r"\bnuestr[oa]s?\b|\bnosotr[oa]s\b|\bJoel (es|tiene|responde|hace|construye|escribe|mantiene)\b|\b(con|a) Joel\b|\bun solo ingeniero\b")
VOICE_SKIP = ("eula/", "es/eula/", "catalog/", "es/catalogo/", "laboratorio/")


def _visible_main(text):
    m = re.search(r"(?is)<main\b.*?</main>", re.sub(r"(?s)<!--.*?-->", "", text))
    body = m.group(0) if m else ""
    body = re.sub(r"(?is)<(script|style|svg)\b.*?</\1>", " ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    import html as _html
    return " ".join(_html.unescape(body).split())


@check("voice", "public copy and page descriptions speak in the first person singular (no 'we', 'our', 'Joel does', 'one engineer')")
def _voice(env: Env):
    import html as _html
    bad = []
    for f in sorted(ROOT.rglob("index.html")):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(("node_modules/", "pipeline/", "_review/")) or rel.startswith(VOICE_SKIP):
            continue
        rx = VOICE_ES if rel.startswith("es/") else VOICE_EN
        page = f.read_text(encoding="utf-8")
        text = _visible_main(page)
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if rx.search(sent) and "Gap Hunter Labs is my" not in sent:
                bad.append("%s: %s" % (rel, sent[:110]))
        # what search results and social cards show: the page descriptions
        for m in re.finditer(r'<meta (?:name|property)="(?:description|og:description|twitter:description)" content="([^"]*)"', page):
            share = _html.unescape(m.group(1))
            if rx.search(share):
                bad.append("%s (description): %s" % (rel, share[:110]))
    for js in ("contact.js", "catalog.js", "catalog-vsx.js", "site-search.js"):
        text = (ROOT / "js" / js).read_text(encoding="utf-8")
        for m in re.finditer(r"'([^'\n]{12,})'", text):
            if VOICE_EN.search(m.group(1)) or VOICE_ES.search(m.group(1)):
                bad.append("js/%s: %s" % (js, m.group(1)[:90]))
    expect(not bad, "%d line(s) not in my voice: %s" % (len(bad), " | ".join(bad[:6])))


# ================================================================================ pages
PAGES_AT_390 = ["/", "/es/", "/catalog/", "/es/catalogo/", "/catalog/openapi-companion/", "/services/", "/es/servicios/",
                "/engineering-evidence/", "/engineering-evidence/jetbrains-platform-tickets/",
                "/engineering-evidence/case-studies/", "/engineering-evidence/open-source-security-reports/",
                "/engineering-evidence/third-party-plugin-audits/", "/contact/", "/security/", "/methodology/",
                "/privacy/", "/terms/", "/ghl-jail/", "/sponsors/", "/es/patrocinadores/"]


@check("pages", "no horizontal overflow at 390 px, no page errors")
def _overflow(env: Env):
    bad = []
    with env.page(width=390, height=844) as p:
        for path in PAGES_AT_390:
            before = len(p.rec.errors)
            env.go(p, path)
            over = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 0:
                bad.append("%s overflows by %dpx" % (path, over))
            if len(p.rec.errors) > before:
                bad.append("%s: %s" % (path, p.rec.errors[-1]))
    expect(not bad, "; ".join(bad))


@check("pages", "no horizontal overflow at 320 px (header and long words included)")
def _overflow_320(env: Env):
    bad = []
    with env.page(width=320, height=640) as p:
        for path in PAGES_AT_390:
            env.go(p, path)
            over = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            header = p.evaluate("(() => { const h = document.querySelector('.gh-header-inner'); return h.scrollWidth - h.clientWidth; })()")
            if over > 0 or header > 0:
                bad.append("%s overflows by %dpx (header %dpx)" % (path, over, header))
    expect(not bad, "; ".join(bad))


@check("pages", "methodology: the decision diagram fits a phone")
def _methodology(env: Env):
    with env.page(width=390, height=844) as p:
        env.go(p, "/methodology/")
        w = p.evaluate("document.querySelector('.decision-diagram').getBoundingClientRect().width")
        expect(0 < w <= 390, "diagram width %.0f should fit 390px" % w)
        eq(p.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), False, "page overflow")


@check("pages", "plugin page: facts table, badges and related plugins")
def _ficha(env: Env):
    for lang in ("en", "es"):
        with env.page() as p:
            env.go(p, LANGS[lang]["ficha"])
            # 6 rows since the "Growth" row was removed (2026-11-09)
            eq(p.locator(".facts-table .fact").count(), 6, "facts rows [%s]" % lang)
            expect(p.locator(".facts-table .badge svg").count() >= 1, "the platform badge should carry an inline icon")
            expect(p.locator(".facts-table .badge-status").count() == 1, "the pricing badge is missing")
            expect(p.locator(".similar-grid .rel-card").count() >= 3, "related plugins are missing")


@check("pages", "redirect stubs land on their target")
def _stubs(env: Env):
    stubs = {}
    for f in ROOT.glob("*.html"):
        m = re.search(r'http-equiv="refresh" content="\d+;\s*url=([^"]+)"', f.read_text(encoding="utf-8"))
        if m:
            stubs["/" + f.name] = m.group(1)
    expect(len(stubs) >= 5, "expected the redirect stubs, found %r" % stubs)
    with env.page() as p:
        for src, dst in stubs.items():
            env.go(p, src, wait="load")
            p.wait_for_url("**" + dst, timeout=5000)


def _internal_links(env: Env, page, path):
    hrefs = page.evaluate("[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')))]")
    out = []
    for h in hrefs:
        if h.startswith(("mailto:", "tel:", "javascript:", "#", "http://", "https://", "//")):
            continue
        out.append(h.split("#")[0] or path)
    return sorted(set(out))


@check("pages", "internal links resolve on the main pages")
def _links(env: Env):
    broken = []
    seen = {}
    with env.page() as p:
        for path in ["/", "/es/", "/catalog/", "/es/catalogo/", "/services/", "/es/servicios/", "/engineering-evidence/",
                     "/contact/", "/security/", "/methodology/", "/sponsors/", "/es/patrocinadores/"]:
            env.go(p, path)
            for href in _internal_links(env, p, path):
                if href not in seen:
                    seen[href] = env.get(href.split("?")[0])
                if seen[href] >= 400:
                    broken.append("%s -> %s (%d)" % (path, href, seen[href]))
    expect(not broken, "broken links: " + "; ".join(broken[:8]))


@check("pages", "no third-party requests except analytics")
def _third_party(env: Env):
    offenders = set()
    host = urllib.parse.urlparse(env.base).netloc
    with env.page() as p:
        for path in ["/", "/es/", "/catalog/", "/services/", "/contact/", "/catalog/openapi-companion/", "/engineering-evidence/"]:
            env.go(p, path)
        for u in p.rec.requests:
            h = urllib.parse.urlparse(u).netloc
            if u.startswith(("data:", "blob:")) or h == host or not h:
                continue
            if any(h == ok or h.endswith(ok) for ok in THIRD_PARTY_OK):
                continue
            offenders.add(h)
    expect(not offenders, "third-party hosts contacted: %s" % sorted(offenders))


@check("share", "social images: every page points to an existing 1200x630 PNG with the current version")
def _og(env: Env):
    import struct
    cfg = (ROOT / "pipeline" / "site_config.py").read_text(encoding="utf-8")
    version = re.search(r'OG_VERSION\s*=\s*"([^"]+)"', cfg).group(1)
    problems, users = [], {}
    pages = [p for p in ROOT.rglob("index.html") if not any(part in ("node_modules", "_review", "pipeline", "out") for part in p.relative_to(ROOT).parts)]
    pages += list(ROOT.glob("*.html"))
    for page in pages:
        rel = page.relative_to(ROOT).as_posix()
        text = page.read_text(encoding="utf-8")
        m = re.search(r'<meta property="og:image" content="([^"]+)"', text)
        if not m:
            if page.name == "index.html":  # 404.html and the search-console file are not content pages
                problems.append("%s: no og:image" % rel)
            continue
        url = urllib.parse.urlparse(m.group(1))
        if 'http-equiv="refresh"' not in text:  # redirect stubs mirror their target and may share its image
            users.setdefault(url.path, []).append(rel)
        if "v=" + version not in url.query:
            problems.append("%s: og:image should carry ?v=%s (%s)" % (rel, version, m.group(1)))
        png = ROOT / url.path.lstrip("/")
        if not png.exists():
            problems.append("%s: %s does not exist" % (rel, url.path))
            continue
        head = png.read_bytes()[:24]
        if head[:8] != PNG_MAGIC or struct.unpack(">II", head[16:24]) != (1200, 630):
            problems.append("%s: %s is not a 1200x630 PNG" % (rel, url.path))
        for tag in ("og:image:width", "og:image:height", "twitter:image"):
            if tag not in text:
                problems.append("%s: missing %s" % (rel, tag))
    generic = users.get("/og-image.png", []) + users.get("/og-image.es.png", [])
    extra = [g for g in generic if g not in ("index.html", "es/index.html")]
    expect(not extra, "the generic home image is reused by other pages: %s" % extra[:5])
    for path, rels in users.items():
        if path.startswith("/media/"):
            expect(len(rels) <= 2, "%s is shared by more than an EN/ES pair: %s" % (path, rels[:4]))
    expect(not problems, "; ".join(problems[:8]) + (" (+%d more)" % (len(problems) - 8) if len(problems) > 8 else ""))


@check("pages", "screenshots (only with --shots)")
def _screens(env: Env):
    if not env.shots:
        return
    for label, w, h in (("desktop", 1440, 1000), ("mobile", 390, 844)):
        with env.page(width=w, height=h) as p:
            for name, path in (("home", "/"), ("services", "/services/"), ("engineering", "/engineering-evidence/"),
                               ("security", "/security/"), ("methodology", "/methodology/")):
                env.go(p, path)
                env.shot(p, "%s-%s" % (name, label), full=True)


# ================================================================================ runner
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="URL of a running server (default: start a local one)")
    ap.add_argument("--only", help="comma-separated groups or words to run (e.g. catalog,search)")
    ap.add_argument("--list", action="store_true", help="list the checks and exit")
    ap.add_argument("--shots", action="store_true", help="save screenshots to _review/screenshots/")
    ap.add_argument("--browser", default=os.environ.get("VERIFY_BROWSER"), help="path to a Chromium-based browser (default: Playwright's)")
    ap.add_argument("--json", help="write the results to this file")
    args = ap.parse_args()

    wanted = [w.strip().lower() for w in (args.only or "").split(",") if w.strip()]
    selected = [c for c in CHECKS if not wanted or any(w in (c[0] + " " + c[1]).lower() for w in wanted)]
    if args.list:
        for g, n, _ in selected:
            print("%-8s %s" % (g, n))
        print("%d checks" % len(selected))
        return 0

    server = None
    base = args.base
    if not base:
        server, base = start_server()
    results = []
    with sync_playwright() as pw:
        kw = {"executable_path": args.browser} if args.browser else {}
        browser = pw.chromium.launch(headless=True, **kw)
        env = Env(browser, base.rstrip("/"), args.shots)
        print("site: %s | browser: %s %s | checks: %d" % (env.base, browser.browser_type.name, browser.version, len(selected)))
        for group, name, fn in selected:
            t0 = time.time()
            try:
                fn(env)
                status, detail = "PASS", ""
            except Exception as exc:  # noqa: BLE001
                status = "FAIL"
                detail = str(exc) if isinstance(exc, AssertionError) else "%s: %s" % (type(exc).__name__, str(exc).splitlines()[0] if str(exc) else "")
                if not isinstance(exc, AssertionError):
                    detail += "\n" + "".join(traceback.format_exc().splitlines(True)[-4:])
            dt = time.time() - t0
            results.append(dict(group=group, name=name, status=status, seconds=round(dt, 1), detail=detail))
            print("%s  %-8s %s (%.1fs)" % (status, group, name, dt))
            if detail:
                print("      " + detail.replace("\n", "\n      "))
        browser.close()
    if server:
        server.shutdown()
    failed = [r for r in results if r["status"] == "FAIL"]
    print("\n%d checks: %d passed, %d failed" % (len(results), len(results) - len(failed), len(failed)))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
