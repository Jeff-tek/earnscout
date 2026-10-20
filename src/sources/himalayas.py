"""Himalayas: public JSON, jobs[] with locationRestrictions and salary fields."""
import json

from .. import util

URL = "https://himalayas.app/jobs/api"


def fetch():
    data = json.loads(util.fetch(URL, timeout=60))
    out = []
    for j in data.get("jobs") or []:
        guid = j.get("guid") or ""
        url = j.get("applicationLink") or ""
        if not url and guid:
            url = guid if guid.startswith("http") else f"https://himalayas.app/jobs/{guid}"
        locs = j.get("locationRestrictions") or []
        out.append({
            "source": "himalayas",
            "category": "job",
            "title": j.get("title") or "",
            "company": j.get("companyName"),
            "url": url,
            "location_raw": ", ".join(locs) if locs else "Worldwide",
            "description": j.get("description") or j.get("excerpt") or "",
            "posted_at": j.get("pubDate"),
            "deadline": j.get("expiryDate"),
            "salary": {
                "min": j.get("minSalary") or None,
                "max": j.get("maxSalary") or None,
                "currency": j.get("currency"),
                "period": j.get("salaryPeriod"),
            },
            "tags": (j.get("categories") or []) + (j.get("parentCategories") or []),
            "extra": {"guid": guid, "timezones": j.get("timezoneRestrictions")},
        })
    return out
