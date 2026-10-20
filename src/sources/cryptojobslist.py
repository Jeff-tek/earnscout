"""CryptoJobsList: RSS 2.0 with dc:creator and media:location."""
import xml.etree.ElementTree as ET

from .. import util

URL = "https://cryptojobslist.com/rss"
NS = {"dc": "http://purl.org/dc/elements/1.1/", "media": "http://search.yahoo.com/mrss/"}


def _text(item, tag, ns=None):
    el = item.find(tag, ns or {})
    return (el.text or "").strip() if el is not None and el.text else ""


def fetch():
    root = ET.fromstring(util.fetch(URL, timeout=60))
    out = []
    for item in root.findall(".//item"):
        out.append({
            "source": "cryptojobslist",
            "category": "job",
            "title": _text(item, "title"),
            "company": _text(item, "dc:creator", NS) or None,
            "url": _text(item, "link"),
            "location_raw": _text(item, "media:location", NS),
            "description": _text(item, "description"),
            "posted_at": _text(item, "pubDate") or None,
            "deadline": None,
            "salary": None,
            "tags": [],
            "extra": {},
        })
    return out
