"""data/services.json: the single source for the published services (2026-11-09, decision D11).

Before this file a service price was typed by hand in 4 or 5 places (the home, /services/, the service page, the
catalog, the social images), so a change in one of them left the site contradicting itself. Every reader goes
through load(), which checks the whole file first and names the field that is wrong.

Shape (all keys required unless marked optional):
  services[]: key          short id, also the ?service= value of the contact form ("audit")
              name         full name ("Plugin performance audit")
              shortName    footer label ("Performance audit")
              path         the service page ("/plugin-performance-audit/"); its index.html must exist
              group        "jetbrains" (for JetBrains plugin teams) or "any" (any codebase)
              contactLabel {"en": ..., "es": ...} option of the contact form (contact.js is not translated by
                           build_i18n, so it carries both languages)
              tiers[]      {"id", "usd", "days", "openEnded" (optional)}: whole US dollars, business days.
                           days is null only for an open-ended tier ("From USD 15,000", the date is set in the scope)
              addOns[]     optional, {"id", "usd", "days"}: added to any tier (the EU CRA readiness check)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES_FILE = ROOT / "data" / "services.json"

KEY_RE = re.compile(r"^[a-z][a-z0-9]{1,19}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,29}$")
PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9-]*/$")
GROUPS = ("jetbrains", "any")
RESERVED_KEYS = ("other",)            # the contact form's own "Something else" option
SERVICE_FIELDS = {"key", "name", "shortName", "path", "group", "contactLabel", "tiers", "addOns"}
TIER_FIELDS = {"id", "usd", "days", "openEnded"}
ADDON_FIELDS = {"id", "usd", "days"}
FIELDS = ("usd", "days")


class ServicesError(ValueError):
    """services.json is missing, unreadable or wrong. The message names the field."""


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ServicesError("%s must be non-empty text without leading or trailing spaces" % where)
    if any(c in value for c in "<>\n\r\\"):
        # Names go into HTML, JSON-LD and a JavaScript string: no markup, line breaks or backslashes.
        raise ServicesError("%s must not contain <, >, a line break or a backslash" % where)
    return value


def _whole(value, where, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ServicesError("%s must be a whole number of at least %d" % (where, minimum))
    return value


def _unknown(entry, allowed, where):
    extra = sorted(set(entry) - allowed)
    if extra:
        raise ServicesError("%s has unknown field(s) %s (a typo would be silently ignored)" % (where, ", ".join(extra)))


def _levels(entries, where, fields, addon):
    if not isinstance(entries, list) or (not addon and not entries):
        raise ServicesError("%s must be a %slist" % (where, "" if addon else "non-empty "))
    out = []
    for j, lv in enumerate(entries):
        w = "%s[%d]" % (where, j)
        if not isinstance(lv, dict):
            raise ServicesError("%s must be an object" % w)
        _unknown(lv, fields, w)
        if not isinstance(lv.get("id"), str) or not ID_RE.match(lv["id"]):
            raise ServicesError("%s.id must match %s" % (w, ID_RE.pattern))
        w = "%s (%s)" % (w, lv["id"])
        _whole(lv.get("usd"), w + ".usd", 1)
        open_ended = lv.get("openEnded", False)
        if not isinstance(open_ended, bool):
            raise ServicesError("%s.openEnded must be true or false" % w)
        if lv.get("days") is None and not addon and open_ended:
            pass
        elif lv.get("days") is None:
            raise ServicesError("%s.days is required (null only for an open-ended tier)" % w)
        else:
            _whole(lv["days"], w + ".days", 1)
        if open_ended and lv.get("days") is not None:
            raise ServicesError("%s is open-ended, so its delivery date is set in the scope: days must be null" % w)
        out.append(lv)
    return out


def validate(data, root=ROOT):
    if not isinstance(data, dict):
        raise ServicesError("services.json must be an object")
    _unknown(data, {"about", "services"}, "services.json")
    services = data.get("services")
    if not isinstance(services, list) or not services:
        raise ServicesError("services.json: \"services\" must be a non-empty list")
    keys, paths = set(), set()
    for i, s in enumerate(services):
        where = "services[%d]" % i
        if not isinstance(s, dict):
            raise ServicesError("%s must be an object" % where)
        _unknown(s, SERVICE_FIELDS, where)
        key = s.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key) or key in RESERVED_KEYS:
            raise ServicesError("%s.key must match %s and not be %s" % (where, KEY_RE.pattern, "/".join(RESERVED_KEYS)))
        if key in keys:
            raise ServicesError("%s.key %r is repeated" % (where, key))
        keys.add(key)
        where = "services[%d] (%s)" % (i, key)
        _text(s.get("name"), where + ".name")
        _text(s.get("shortName"), where + ".shortName")
        path = s.get("path")
        if not isinstance(path, str) or not PATH_RE.match(path):
            raise ServicesError("%s.path must look like /service-page/" % where)
        if path in paths:
            raise ServicesError("%s.path %s is repeated" % (where, path))
        if not (root / path.strip("/") / "index.html").is_file():
            raise ServicesError("%s.path %s has no index.html" % (where, path))
        paths.add(path)
        if s.get("group") not in GROUPS:
            raise ServicesError("%s.group must be one of %s" % (where, ", ".join(GROUPS)))
        label = s.get("contactLabel")
        if not isinstance(label, dict) or set(label) != {"en", "es"}:
            raise ServicesError("%s.contactLabel must have exactly \"en\" and \"es\"" % where)
        _text(label["en"], where + ".contactLabel.en")
        _text(label["es"], where + ".contactLabel.es")
        if "'" in label["en"] + label["es"]:
            raise ServicesError("%s.contactLabel must not contain an apostrophe (it becomes a JavaScript string)" % where)
        tiers = _levels(s.get("tiers"), where + ".tiers", TIER_FIELDS, addon=False)
        addons = _levels(s.get("addOns", []), where + ".addOns", ADDON_FIELDS, addon=True)
        ids = [lv["id"] for lv in tiers + addons]
        if len(ids) != len(set(ids)):
            raise ServicesError("%s: tier and add-on ids must be unique within the service" % where)
    return data


def load(path=SERVICES_FILE, root=ROOT):
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ServicesError("%s does not exist" % path.name) from None
    try:   # decoding is inside: a file that is not UTF-8 is a ServicesError too, not a traceback
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:   # UnicodeDecodeError and JSONDecodeError; neither repeats the file's text
        raise ServicesError("%s: not valid JSON (%s)" % (path.name, exc)) from None
    return validate(data, root)


def by_key(data):
    return {s["key"]: s for s in data["services"]}


def level(data, key, level_id):
    s = by_key(data).get(key)
    if s is None:
        raise ServicesError("no service %r" % key)
    for lv in s["tiers"] + s.get("addOns", []):
        if lv["id"] == level_id:
            return lv
    raise ServicesError("service %r has no level %r" % (key, level_id))


def value(data, ref):
    """"audit.base.usd" -> 10500. A null value (the days of an open-ended tier) is an error: it cannot be shown."""
    parts = ref.split(".")
    if len(parts) != 3 or parts[2] not in FIELDS:
        raise ServicesError("binding %r must be <key>.<level>.<usd|days>" % ref)
    v = level(data, parts[0], parts[1]).get(parts[2])
    if v is None:
        raise ServicesError("binding %r has no value (an open-ended tier has no days)" % ref)
    return v


def usd(n, lang="en"):
    """10500 -> "10,500" (en) or "10.500" (es)."""
    s = "{:,}".format(n)
    return s.replace(",", ".") if lang == "es" else s


def min_usd(service):
    return min(t["usd"] for t in service["tiers"])


def max_usd(service):
    """Highest total a visitor can be charged, or None when a tier is open-ended ("From USD ...")."""
    if any(t.get("openEnded") for t in service["tiers"]):
        return None
    return max(t["usd"] for t in service["tiers"]) + sum(a["usd"] for a in service.get("addOns", []))
