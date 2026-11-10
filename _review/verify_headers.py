"""Check the live HTTP layer of the site: redirects, caching of versioned assets, security headers, certificates.

    python _review/verify_headers.py            # every check; exit 1 if any fails
    python _review/verify_headers.py --today    # only what GitHub Pages alone can give (no proxy in front)

GitHub Pages serves everything with Cache-Control: max-age=600 and sets no security headers on a custom domain.
With the Cloudflare proxy in front (2026-11-09 plan), the versioned assets (?v=) get a long cache, and the HTML
gets HSTS, X-Content-Type-Options, a Referrer-Policy and frame-ancestors. The origin certificate (GitHub's
Let's Encrypt certificate) must stay valid: with "Full (strict)" Cloudflare refuses an expired one, so it is checked
directly against a GitHub Pages IP.
"""
import argparse
import datetime
import socket
import ssl
import sys
import urllib.error
import urllib.request

SITE = "https://gaphunterlabs.com"
GITHUB_PAGES_IP = "185.199.108.153"
UA = {"User-Agent": "Mozilla/5.0 (site header check)"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def head(url, follow=True):
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="GET", headers=UA)
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}


def origin_cert_days():
    ctx = ssl.create_default_context()
    with socket.create_connection((GITHUB_PAGES_IP, 443), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname="gaphunterlabs.com") as tls:
            not_after = tls.getpeercert()["notAfter"]
    end = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
    return (end - datetime.datetime.now(datetime.timezone.utc)).days


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--today", action="store_true", help="only the checks GitHub Pages passes without a proxy")
    args = ap.parse_args(argv)
    results = []

    def check(name, ok, detail="", proxy=False):
        if args.today and proxy:
            return
        results.append((ok, name, detail))

    for url in ("http://gaphunterlabs.com/", "https://www.gaphunterlabs.com/"):
        status, h = head(url, follow=False)
        check("%s redirects to %s/" % (url, SITE), status in (301, 308) and h.get("location", "").rstrip("/") == SITE,
              "%s %s" % (status, h.get("location")))
    status, h = head(SITE + "/")
    check("home answers 200", status == 200, str(status))
    check("HSTS on the HTML", "max-age=" in h.get("strict-transport-security", ""), h.get("strict-transport-security", "none"), proxy=True)
    check("X-Content-Type-Options: nosniff", h.get("x-content-type-options", "").lower() == "nosniff",
          h.get("x-content-type-options", "none"), proxy=True)
    check("Referrer-Policy", bool(h.get("referrer-policy")), h.get("referrer-policy", "none"), proxy=True)
    check("frame-ancestors (CSP header)", "frame-ancestors" in h.get("content-security-policy", ""),
          h.get("content-security-policy", "none")[:60], proxy=True)
    check("HTML is not cached for long", "max-age=31536000" not in h.get("cache-control", ""), h.get("cache-control", ""))
    status, h = head(SITE + "/css/theme.css?v=check")
    check("versioned CSS answers 200", status == 200, str(status))
    check("versioned assets cached for a long time", "max-age=31536000" in h.get("cache-control", "")
          or "max-age=2592000" in h.get("cache-control", ""), h.get("cache-control", ""), proxy=True)
    try:
        days = origin_cert_days()
        check("origin certificate (GitHub Pages) valid for 21+ days", days >= 21, "%d days left" % days)
    except (OSError, ssl.SSLError) as e:
        check("origin certificate (GitHub Pages) readable", False, type(e).__name__)

    for ok, name, detail in results:
        print("%s  %s  (%s)" % ("PASS" if ok else "FAIL", name, detail))
    failed = sum(not ok for ok, _, _ in results)
    print("\n%d checks: %d passed, %d failed" % (len(results), len(results) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
