"""Superteam Earn: official agent API (free key from POST /api/agents).

Schema is handled defensively because the API returns an empty list for
agent-eligible listings most of the time. When items appear, the common keys
are mapped; unknown shapes degrade to an empty list rather than crashing.
"""
import json
import os

from .. import util

URL = "https://superteam.fun/api/agents/listings/live?take=50"


def _sponsor_name(value):
    if isinstance(value, dict):
        return value.get("name") or value.get("title")
    return value or None


def fetch():
    key = os.environ.get("SUPERTEAM_API_KEY")
    if not key:
        return []
    raw = util.fetch(URL, timeout=45, headers={"Authorization": f"Bearer {key}"})
    data = json.loads(raw)
    items = data if isinstance(data, list) else (data.get("listings") or data.get("data") or [])
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        slug = it.get("slug") or it.get("id") or ""
        out.append({
            "source": "superteam",
            "category": it.get("type") or "freelance",
            "title": it.get("title") or it.get("name") or "",
            "company": _sponsor_name(it.get("sponsor") or it.get("org")),
            "url": it.get("link") or (f"https://superteam.fun/earn/listing/{slug}" if slug else ""),
            "location_raw": it.get("region") if isinstance(it.get("region"), str) else "Nigeria",
            "description": it.get("description") or it.get("content") or "",
            "posted_at": it.get("publishedAt") or it.get("createdAt"),
            "deadline": it.get("deadline"),
            "salary": None,
            "tags": it.get("skills") or [],
            "extra": {
                "reward": it.get("reward") or it.get("compensation"),
                "type": it.get("type"),
                "slug": slug,
            },
        })
    return out
