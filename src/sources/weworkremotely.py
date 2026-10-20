"""We Work Remotely: RSS 2.0 with region/country fields."""
import xml.etree.ElementTree as ET

from .. import util

URL = "https://weworkremotely.com/remote-jobs.rss"


def _text(item, tag):
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def fetch():
    root = ET.fromstring(util.fetch(URL, timeout=60))
    out = []
    for item in root.findall(".//item"):
        raw_title = _text(item, "title")
        company, title = None, raw_title
        if ": " in raw_title:
            company, title = raw_title.split(": ", 1)
        out.append({
            "source": "weworkremotely",
            "category": "job",
            "title": title.strip(),
            "company": company.strip() if company else None,
            "url": _text(item, "link"),
            "location_raw": _text(item, "region") or _text(item, "country"),
            "description": _text(item, "description"),
            "posted_at": _text(item, "pubDate"),
            "deadline": _text(item, "expires_at") or None,
            "salary": None,
            "tags": [t.strip() for t in _text(item, "skills").split(",") if t.strip()],
            "extra": {
                "category": _text(item, "category"),
                "type": _text(item, "type"),
                "country": _text(item, "country"),
            },
        })
    return out
