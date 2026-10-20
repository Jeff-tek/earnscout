"""Persist listings and preserve human review state across runs."""
from . import util

PATH = f"{util.DATA}/listings.json"


def load():
    return util.load_json(PATH, {"version": 1, "updated_at": None, "items": []})


def save(items):
    util.save_json(PATH, {"version": 1, "updated_at": util.iso(util.now_utc()), "items": items})


def merge(old_items, new_items, max_age_days=14, archive_days=90):
    by_id = {i["id"]: i for i in old_items}
    now = util.now_utc()

    for new in new_items:
        old = by_id.get(new["id"])
        if old:
            new["first_seen_at"] = old.get("first_seen_at") or new["first_seen_at"]
            review = old.get("review") or {}
            if review.get("status") == "approved":
                new["review"] = review
                new["tier"] = "verified"
        by_id[new["id"]] = new

    items = []
    for item in by_id.values():
        dt = util.parse_dt(item.get("posted_at"))
        age_days = (now - dt).days if dt else 0
        if item.get("tier") != "blocked":
            if age_days > archive_days:
                item["status"] = "archived"
            elif age_days > max_age_days and item.get("status") == "active":
                item["status"] = "expired"
        items.append(item)

    items.sort(key=lambda x: (x.get("score") or {}).get("total", 0), reverse=True)
    return items
