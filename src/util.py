"""Shared helpers: HTTP, dates, text, ids. Standard library only."""
from __future__ import annotations

import gzip
import hashlib
import html as htmlmod
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CONFIG = os.path.join(ROOT, "config")

USER_AGENT = (
    "EarnScout/0.1 (personal opportunity scanner; "
    "+https://github.com/earnscout/earnscout)"
)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def fetch(url, timeout=45, headers=None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.decompress(raw)
        return raw


def strip_html(value, maxlen=None):
    if not value:
        return ""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(value), flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen] if maxlen else s


def parse_dt(value):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        return None


def iso(dt):
    if not dt:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_utc():
    return datetime.now(timezone.utc)


def normalize_url(url):
    if not url:
        return ""
    url = str(url).strip().split("#")[0]
    url = re.sub(r"([?&])(?:utm_[^&=]+|ref|source)=[^&]*", r"\1", url)
    url = re.sub(r"[?&]+$", "", url)
    return url.rstrip("/").lower()


def domain_of(url):
    m = re.match(r"https?://([^/]+)", url or "", re.I)
    if not m:
        return ""
    d = m.group(1).lower().split(":")[0]
    return d[4:] if d.startswith("www.") else d


def make_id(source, url, title=""):
    basis = normalize_url(url) or title
    return hashlib.sha1(f"{source}:{basis}".encode("utf-8")).hexdigest()[:16]
