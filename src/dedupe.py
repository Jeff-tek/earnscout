"""Cross-source dedupe: exact URL first, then fuzzy title + company."""
import difflib
import re

from . import util


def _key(item):
    title = re.sub(r"\W+", " ", (item.get("title") or "").lower()).strip()
    company = re.sub(r"\W+", " ", (item.get("company") or "").lower()).strip()
    return title, company


def merge(items, threshold=0.86):
    kept = []
    for item in items:
        dup = None
        for candidate in kept:
            if util.normalize_url(item.get("url")) == util.normalize_url(candidate.get("url")):
                dup = candidate
                break
            t1, c1 = _key(item)
            t2, c2 = _key(candidate)
            if c1 and c1 == c2 and difflib.SequenceMatcher(None, t1, t2).ratio() >= threshold:
                dup = candidate
                break

        if dup is None:
            kept.append(item)
            continue

        sources = list(dict.fromkeys(
            (dup.get("sources_seen") or []) + (item.get("sources_seen") or [])
        ))
        dup["sources_seen"] = sources

        if not dup.get("salary") and item.get("salary"):
            dup["salary"] = item["salary"]
        if len(item.get("snippet") or "") > len(dup.get("snippet") or ""):
            dup["snippet"] = item["snippet"]

        d1 = util.parse_dt(dup.get("posted_at"))
        d2 = util.parse_dt(item.get("posted_at"))
        if d2 and (not d1 or d2 < d1):
            dup["posted_at"] = item.get("posted_at")

        seen = {s.get("id") for s in dup.get("signals", [])}
        for sig in item.get("signals", []):
            if sig.get("id") not in seen:
                dup.setdefault("signals", []).append(sig)

        if len(sources) > 1:
            dup["duplicate_of"] = None

    return kept
