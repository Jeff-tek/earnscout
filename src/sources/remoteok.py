"""Remote OK: public JSON array, first element is a legal notice."""
import json

from .. import util

URL = "https://remoteok.com/api"


def fetch():
    data = json.loads(util.fetch(URL, timeout=60))
    out = []
    for it in data:
        if not isinstance(it, dict) or not it.get("position"):
            continue
        out.append({
            "source": "remoteok",
            "category": "job",
            "title": it.get("position") or "",
            "company": it.get("company"),
            "url": it.get("url") or it.get("apply_url") or "",
            "location_raw": it.get("location") or "",
            "description": it.get("description") or "",
            "posted_at": it.get("date"),
            "deadline": None,
            "salary": {
                "min": it.get("salary_min") or None,
                "max": it.get("salary_max") or None,
                "currency": "USD" if (it.get("salary_min") or it.get("salary_max")) else None,
                "period": "year",
            },
            "tags": it.get("tags") or [],
            "extra": {"id": it.get("id"), "apply_url": it.get("apply_url")},
        })
    return out
