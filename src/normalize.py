"""Turn raw source items into canonical listings."""
import re

from . import audience, util

HARD = {"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "SGD"}
CRYPTO = {"USDT", "USDC", "BTC", "ETH", "SOL", "BNB"}
NAMED_RAILS = ["payoneer", "deel", "wise", "grey", "cleva", "daya", "chipper"]
NIGERIA_RE = re.compile(r"\b(nigeria|nigerian|africa|worldwide|anywhere|global|emea)\b", re.I)
EXCLUDE_RE = re.compile(
    r"\b(?:usa|u\.s\.|united states|canada|uk|united kingdom|europe|eu|india|"
    r"philippines|latam|australia|apac|onsite)\b",
    re.I,
)


def detect_rails(text, salary):
    rails = []
    cur = ((salary or {}).get("currency") or "").upper()
    if cur in CRYPTO:
        rails.append(cur)
    elif cur in HARD:
        rails.append(cur)

    if re.search(r"\b(usdt|usdc|btc|eth|sol|crypto|stablecoin)\b", text, re.I):
        if not any(r in CRYPTO for r in rails):
            rails.append("CRYPTO")
    for rail in NAMED_RAILS:
        if re.search(rf"\b{rail}\b", text, re.I):
            rails.append(rail.title())
            break
    if re.search(r"\bNGN\b|₦", text) or cur == "NGN":
        rails.append("NGN")
    if re.search(r"\bgift\s*cards?\b|\bitunes\b|\bsteam\s*card\b|\bgoogle\s*play\b", text, re.I):
        rails.append("gift_card")
    if not rails and cur:
        rails.append(cur)
    if not rails:
        rails.append("unknown")
    return list(dict.fromkeys(rails))


def nigeria_ok(location, text, source_cfg):
    if source_cfg.get("location_scope") == "nigeria":
        return True
    loc = (location or "").lower()
    body = (text or "").lower()
    if NIGERIA_RE.search(loc) or NIGERIA_RE.search(body):
        return True
    if EXCLUDE_RE.search(loc) and not NIGERIA_RE.search(loc):
        return False
    return None


def normalize(raw, source_cfg):
    text = " ".join([
        raw.get("title") or "",
        util.strip_html(raw.get("description") or ""),
        raw.get("location_raw") or "",
    ])
    return {
        "id": util.make_id(raw["source"], raw.get("url") or "", raw.get("title") or ""),
        "source": raw["source"],
        "category": raw.get("category") or "job",
        "title": (raw.get("title") or "").strip(),
        "company": raw.get("company"),
        "audience": audience.classify(
            raw.get("title") or "", util.strip_html(raw.get("description") or "", 600)
        ),
        "url": raw.get("url") or "",
        "location_raw": raw.get("location_raw") or None,
        "nigeria_ok": nigeria_ok(raw.get("location_raw"), text, source_cfg),
        "remote": True if source_cfg.get("location_scope") == "global" else None,
        "payment_rails": detect_rails(text, raw.get("salary")),
        "payment_protection": (
            "escrow" if raw["source"] in ("superteam", "freelancer", "laborx") else "platform"
        ),
        "salary": raw.get("salary"),
        "posted_at": util.iso(util.parse_dt(raw.get("posted_at"))) if raw.get("posted_at") else None,
        "first_seen_at": util.iso(util.now_utc()),
        "deadline": util.iso(util.parse_dt(raw.get("deadline"))) if raw.get("deadline") else None,
        "snippet": util.strip_html(raw.get("description") or "", 480),
        "signals": [],
        "tier": "unverified",
        "review": {"status": "pending", "by": None, "at": None, "note": None},
        "score": None,
        "sources_seen": [raw["source"]],
        "duplicate_of": None,
        "status": "active",
        "_text": text[:20000],
        "_tags": raw.get("tags") or [],
    }
