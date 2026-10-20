"""Automated evidence checks: DNS, RDAP domain age, redirects, page status.

Evidence is cached per registrable domain for 7 days (1 day for incomplete
checks) to stay polite and keep runs fast. Domain-age signals are only applied
when the listing host is not a job board or ATS: the age of `remoteok.com` says
nothing about the employer behind a listing.
"""
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from . import util

CACHE_PATH = f"{util.DATA}/evidence.json"
TTL_DAYS = 7
INCOMPLETE_TTL_DAYS = 1
MAX_NEW_PER_RUN = 25
SLEEP_SECONDS = 0.5

ATS_DOMAINS = {
    "greenhouse.io",
    "lever.co",
    "workable.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "workday.com",
    "bamboohr.com",
    "recruitee.com",
    "teamtailor.com",
    "jobvite.com",
    "icims.com",
    "taleo.net",
    "successfactors.com",
    "wellfound.com",
    "angellist.com",
    "applytojob.com",
    "recruiterbox.com",
    "breezy.hr",
    "personio.com",
    "join.com",
    "rippling.com",
    "workatastartup.com",
}

TWO_LEVEL_SUFFIXES = {
    "com.ng", "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au",
    "co.za", "com.br", "co.in", "com.pk", "com.gh", "co.ke", "com.eg",
    "com.tr", "com.sg", "com.my", "co.id", "com.ph",
}

DOMAIN_SIGNAL_IDS = {
    "PS_DOMAIN_AGE_2Y",
    "WK_NEW_DOMAIN",
    "WK_VERY_NEW_DOMAIN",
    "WK_MISSING_PAGE",
}


def registrable(host):
    host = (host or "").lower().strip(".")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    last_two = ".".join(parts[-2:])
    if last_two in TWO_LEVEL_SUFFIXES:
        return ".".join(parts[-3:])
    return last_two


def _platforms():
    cfg = util.load_json(f"{util.CONFIG}/brands.json", {}) or {}
    return set(cfg.get("known_platform_domains", [])) | ATS_DOMAINS


def is_platform(host, platforms):
    host = (host or "").lower()
    return any(host == d or host.endswith("." + d) for d in platforms)


def _dns(host):
    previous = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True, None
    except Exception as exc:
        return False, type(exc).__name__
    finally:
        socket.setdefaulttimeout(previous)


class _Recorder(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain = []
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http(url):
    recorder = _Recorder()
    opener = urllib.request.build_opener(recorder)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": util.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Range": "bytes=0-2047",
        },
    )
    try:
        with opener.open(req, timeout=15) as resp:
            status = resp.status
            final = resp.geturl()
            try:
                resp.read(2048)
            except Exception:
                pass
            return {
                "status": status,
                "final_url": final,
                "redirects": recorder.chain[:5],
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "final_url": exc.geturl(),
            "redirects": recorder.chain[:5],
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "status": None,
            "final_url": url,
            "redirects": recorder.chain[:5],
            "error": type(exc).__name__,
        }


def _vcard_fn(entity):
    vcard = entity.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) > 1:
        for item in vcard[1]:
            if isinstance(item, list) and len(item) > 3 and item[0] == "fn":
                return item[3]
    return None


def _rdap(domain):
    url = "https://rdap.org/domain/" + urllib.parse.quote(domain)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/rdap+json", "User-Agent": util.USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}

    registered = None
    for event in data.get("events") or []:
        if event.get("eventAction") == "registration":
            registered = event.get("eventDate")
            break

    registrar = None
    for entity in data.get("entities") or []:
        if "registrar" in (entity.get("roles") or []):
            registrar = _vcard_fn(entity) or entity.get("handle")
            break

    return {"ok": True, "registered_at": registered, "registrar": registrar}


def _check_domain(domain, url):
    checked_at = util.iso(util.now_utc())
    resolves, dns_error = _dns(domain)
    http = _http(url)
    rdap = _rdap(domain)

    registered_at = rdap.get("registered_at")
    moment = util.parse_dt(registered_at)
    age_days = (util.now_utc() - moment).days if moment else None
    complete = bool(rdap.get("ok") and resolves)

    checks = [
        {
            "id": "dns",
            "result": "pass" if resolves else "fail",
            "detail": dns_error,
            "checked_at": checked_at,
        },
        {
            "id": "http",
            "result": str(http["status"]) if http["status"] else "error",
            "detail": http.get("error") or http.get("final_url"),
            "checked_at": checked_at,
        },
        {
            "id": "rdap",
            "result": "ok" if rdap.get("ok") else "unknown",
            "detail": registered_at or rdap.get("error"),
            "checked_at": checked_at,
        },
    ]

    return {
        "domain": domain,
        "checked_at": checked_at,
        "complete": complete,
        "registered_at": registered_at,
        "age_days": age_days,
        "registrar": rdap.get("registrar"),
        "resolves": resolves,
        "http_status": http["status"],
        "final_url": http["final_url"],
        "redirects": http["redirects"],
        "checks": checks,
    }


def _fresh(entry, now):
    moment = util.parse_dt((entry or {}).get("checked_at"))
    if not moment:
        return False
    ttl = TTL_DAYS if entry.get("complete") else INCOMPLETE_TTL_DAYS
    return (now - moment).days < ttl


def _attach(item, entry, platform):
    host = util.domain_of(item.get("url"))
    signals = [
        s for s in item.get("signals", []) if s.get("id") not in DOMAIN_SIGNAL_IDS
    ]

    if not entry:
        item["evidence"] = None
        item["signals"] = signals
        return

    item["evidence"] = {
        "domain": entry.get("domain"),
        "registered_at": entry.get("registered_at"),
        "age_days": entry.get("age_days"),
        "registrar": entry.get("registrar"),
        "resolves": entry.get("resolves"),
        "http_status": entry.get("http_status"),
        "final_url": entry.get("final_url"),
        "checked_at": entry.get("checked_at"),
        "self_hosted": not platform,
    }

    if entry.get("http_status") in (404, 410):
        signals.append({
            "id": "WK_MISSING_PAGE",
            "severity": "weak",
            "evidence": f"HTTP {entry['http_status']} at check time",
        })

    if not platform and entry.get("age_days") is not None:
        age = int(entry["age_days"])
        if age >= 730:
            signals.append({
                "id": "PS_DOMAIN_AGE_2Y",
                "severity": "positive",
                "support": 1,
                "evidence": f"registered {age} days ago",
            })
        if age < 30:
            signals.append({
                "id": "WK_VERY_NEW_DOMAIN",
                "severity": "weak",
                "evidence": f"registered {age} days ago",
            })
        elif age < 90:
            signals.append({
                "id": "WK_NEW_DOMAIN",
                "severity": "weak",
                "evidence": f"registered {age} days ago",
            })

    item["signals"] = signals


def enrich(items, max_new=MAX_NEW_PER_RUN):
    """Check up to `max_new` uncached domains, then attach evidence to items."""
    cache = util.load_json(CACHE_PATH, {"version": 1, "domains": {}}) or {
        "version": 1,
        "domains": {},
    }
    domains = cache.setdefault("domains", {})
    platforms = _platforms()
    now = util.now_utc()

    targets = {}
    for item in items:
        if item.get("social"):
            continue
        host = util.domain_of(item.get("url"))
        if not host:
            continue
        reg = registrable(host)
        if not reg:
            continue
        posted = item.get("posted_at") or ""
        if reg not in targets or posted > targets[reg]["posted_at"]:
            targets[reg] = {"url": item.get("url"), "posted_at": posted}

    checked = 0
    for reg, meta in sorted(
        targets.items(), key=lambda kv: kv[1]["posted_at"], reverse=True
    ):
        if checked >= max_new:
            break
        if _fresh(domains.get(reg), now):
            continue
        domains[reg] = _check_domain(reg, meta["url"])
        checked += 1
        time.sleep(SLEEP_SECONDS)

    for item in items:
        if item.get("social"):
            item["evidence"] = None
            continue
        host = util.domain_of(item.get("url"))
        entry = domains.get(registrable(host)) if host else None
        _attach(item, entry, is_platform(host, platforms))

    if checked:
        cache["updated_at"] = util.iso(util.now_utc())
        util.save_json(CACHE_PATH, cache)

    return items, checked
