"""Freelancer.com: public active-projects API, filtered to entry-level tasks.

No auth is required for the public active-projects endpoint. Each keyword query
returns up to 50 projects with budget, currency, bid count and age. We keep
English, hard-currency projects whose USD-equivalent maximum budget is at least
$10, whose category is a task the owner selected, and whose title is not a
specialist role.
"""
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone

from .. import audience, util

API = "https://www.freelancer.com/api/projects/0.1/projects/active/"
DEFAULT_QUERIES = [
    "data entry",
    "data annotation",
    "virtual assistant",
    "transcription",
    "proofreading",
    "content writing",
    "copy typing",
    "email handling",
    "excel",
    "captioning",
    "pdf data entry",
    "typing",
    "customer support",
]
PER_QUERY = 50
MIN_USD = 10.0
MAX_BIDS = 80
MAX_AGE_DAYS = 14
MAX_RESULTS = 180

# Freelancer's seo_url starts with the category slug. Only keep slugs that map
# to the task types the owner said they can do.
ALLOWED_SLUGS = {
    "data-entry",
    "data-processing",
    "data-annotation",
    "data-analysis",
    "data-collection",
    "virtual-assistant",
    "admin-support",
    "administrative-support",
    "transcription",
    "proofreading",
    "copywriting",
    "content-writing",
    "article-writing",
    "blog-writing",
    "copy-typing",
    "typing",
    "microsoft-word",
    "google-sheets",
    "excel",
    "adobe-acrobat",
    "pdf",
    "email-handling",
    "customer-support",
    "call-center",
    "market-research",
    "research",
    "surveys",
}

HARD_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "NZD", "SGD", "CHF", "JPY"}

# Titles that are a different job even when the keyword query matched.
TITLE_BLOCK = re.compile(
    r"\b("
    r"translat\w*|developer|programmer|wordpress|website|web\s*app|python|"
    r"api|backend|frontend|designer|design|video|social\s*media|instagram|"
    r"facebook|ads?|seo|marketing|tutor|dissertation|thesis|exam|assignment|"
    r"homework|medical|mental\s*health|clinical|psychology|legal|law|finance|"
    r"accounting|crypto|blockchain|security|network|sharepoint|photoshop|"
    r"illustrator|canva|logo|brochure|banner|commission|on[- ]site|"
    r"visa|malaysia|gas\s+safe|depression|publishable|adult|chinese|amharic|"
    r"spanish|french|german|arabic|hindi|portuguese|japanese|korean|russian|"
    r"mandarin|norwegian|italian|indonesian|malay|vietnamese|turkish|urdu|"
    r"bengali|swahili|yoruba|igbo|hausa|musescore|music|scores|"
    r"us[- ]based|us\s+virtual\s+assistant"
    r")\b",
    re.I,
)

US_ONLY = re.compile(
    r"\b("
    r"us[- ]only|usa[- ]only|only\s+(us|usa|united\s+states)|"
    r"must\s+(be\s+)?(based|located|reside)\s+in\s+the\s+(us|usa|united\s+states)|"
    r"us\s+residents\s+only|must\s+reside\s+in\s+(the\s+)?us"
    r")\b",
    re.I,
)

ENGLISH_STOPWORDS = {
    "the", "and", "to", "of", "in", "for", "with", "you", "we", "need",
    "project", "work", "please", "is", "are", "this", "that", "my", "our",
    "your", "will", "can", "have", "from", "on", "at", "be", "as", "or",
    "a", "an", "i", "it", "me", "looking", "help", "job", "task", "data",
}

FALLBACK_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "CAD": 0.73,
    "AUD": 0.66,
    "NZD": 0.60,
    "SGD": 0.74,
    "CHF": 1.12,
    "JPY": 0.0064,
    "INR": 0.0105,
    "NGN": 0.00065,
    "PKR": 0.0036,
    "BRL": 0.18,
    "ZAR": 0.054,
    "KES": 0.0077,
    "GHS": 0.066,
    "AED": 0.27,
}


def _queries():
    cfg = util.load_json(f"{util.CONFIG}/sources.json", {}) or {}
    for source in cfg.get("sources", []):
        if source.get("id") == "freelancer":
            return source.get("queries") or DEFAULT_QUERIES
    return DEFAULT_QUERIES


def _iso(epoch):
    try:
        return util.iso(datetime.fromtimestamp(int(epoch), tz=timezone.utc))
    except Exception:
        return None


def _english(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_ratio = sum(1 for c in letters if c.isascii()) / len(letters)
    if ascii_ratio < 0.90:
        return False
    words = re.findall(r"[a-z]{2,}", text.lower())
    if len(words) < 12:
        return True
    hits = sum(1 for word in words if word in ENGLISH_STOPWORDS)
    return hits / len(words) >= 0.05


def _budget(project):
    budget = project.get("budget") or {}
    currency = project.get("currency") or {}
    code = (currency.get("code") or "").upper()
    rate = currency.get("exchange_rate")
    try:
        rate = float(rate) if rate else FALLBACK_RATES.get(code, 1.0)
    except (TypeError, ValueError):
        rate = FALLBACK_RATES.get(code, 1.0)

    minimum = budget.get("minimum")
    maximum = budget.get("maximum")
    if minimum is None and maximum is None:
        return None
    minimum = float(minimum or 0)
    maximum = float(maximum or minimum)
    usd_min = round(minimum * rate, 2)
    usd_max = round(maximum * rate, 2)
    if usd_min < MIN_USD:
        return None

    return {
        "min": minimum or None,
        "max": maximum or None,
        "currency": code or None,
        "period": "hour" if project.get("type") == "hourly" else "project",
        "usd_min": usd_min,
        "usd_max": usd_max,
    }


def _parse(project, query):
    if project.get("language") and not str(project["language"]).lower().startswith("en"):
        return None

    title = (project.get("title") or "").strip()
    preview = util.strip_html(project.get("preview_description") or "")
    if not title or not _english(f"{title} {preview}"):
        return None
    if US_ONLY.search(f"{title} {preview}"):
        return None
    if TITLE_BLOCK.search(title):
        return None
    if audience.classify(title, preview) == "skilled":
        return None

    seo = project.get("seo_url") or ""
    slug = seo.split("/")[0] if seo else ""
    if slug not in ALLOWED_SLUGS:
        return None

    salary = _budget(project)
    if salary is None or salary.get("currency") not in HARD_CURRENCIES:
        return None

    submitted = project.get("time_submitted")
    if submitted:
        age_days = (time.time() - int(submitted)) / 86400
        if age_days > MAX_AGE_DAYS:
            return None

    bid_stats = project.get("bid_stats") or {}
    bid_count = bid_stats.get("bid_count")
    if bid_count is not None and bid_count > MAX_BIDS:
        return None

    url = f"https://www.freelancer.com/projects/{seo}" if seo else ""
    if not url:
        return None

    return {
        "source": "freelancer",
        "category": "freelance",
        "title": title,
        "company": None,
        "url": url,
        "location_raw": "Worldwide",
        "description": preview,
        "posted_at": _iso(submitted),
        "deadline": None,
        "salary": salary,
        "tags": [query],
        "audience": "entry",
        "audience_locked": True,
        "competition": bid_count,
        "payment_protection": "escrow" if project.get("is_escrow_project") else "platform",
        "extra": {
            "type": project.get("type"),
            "slug": slug,
            "bid_count": bid_count,
            "queries": [query],
        },
    }


def fetch():
    results = []
    seen = set()
    for query in _queries():
        url = f"{API}?limit={PER_QUERY}&query={urllib.parse.quote(query)}"
        try:
            data = json.loads(util.fetch(url, timeout=60))
        except Exception as exc:
            print(f"[freelancer] query '{query}' failed: {type(exc).__name__}: {exc}")
            continue
        for project in (data.get("result") or {}).get("projects") or []:
            project_id = project.get("id")
            if not project_id or project_id in seen:
                continue
            seen.add(project_id)
            parsed = _parse(project, query)
            if parsed:
                results.append(parsed)
        time.sleep(1.0)

    results.sort(key=lambda item: item.get("posted_at") or "", reverse=True)
    return results[:MAX_RESULTS]
