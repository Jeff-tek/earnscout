"""Bluesky public search: paid social leads.

The AppView search endpoint is public and needs no credentials. Every item
returned here is a lead, not a verified job: the poster, pay and company are
unverified until the owner checks the post. Filters are deliberately strict
because Bluesky search is full of reposted job-board spam and engagement bait.
"""
import json
import re
import time
import urllib.parse
from datetime import timedelta

from .. import audience, util

API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
QUERIES = [
    '"we are hiring" "data entry"',
    '"hiring" "virtual assistant"',
    '"transcription" "hiring"',
    '"data annotation" "hiring"',
    '"customer support" "hiring" "remote"',
    '"paid" "data entry" "remote"',
    '"hiring" "remote" "DM"',
]
LIMIT = 50
MAX_AGE_DAYS = 14
MAX_PER_HANDLE = 3
MIN_TASK_USD = 10
HARD = {"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "SGD"}

TASK_RE = re.compile(r"""
  \b(
    data\s*entry | data\s*annotation | annotat\w* | transcrib\w* | caption\w* |
    proofread\w* | copy\s*typ\w* | typing |
    virtual\s*assistant | va |
    customer\s*(support|service) | chat\s*support | support\s*(agent|rep) |
    moderat\w* | rater | reviewer | tagger | labeler |
    microtask\w* | survey\w* | user\s*testing | product\s*tester | tester |
    research\s*assistant | lead\s*generation | appointment\s*setter |
    content\s*writer | writer | copywriter |
    ai\s*training | data\s*collection | video\s*annotation
  )\b
""", re.I | re.X)

HIRING_RE = re.compile(r"""
  \b(
    hiring | we(?:'re|\s+are)\s+hiring |
    looking\s+for\s+(?:a|an|someone|somebody) |
    need\s+(?:a|an|someone|somebody|help) |
    seeking | recruit\w* | join\s+our\s+team |
    paid\s+(?:task|gig|role|job) | task\s+available | work\s+with\s+us |
    apply | position | vacancy | opening | opportunity | collaboration |
    we\s+need
  )\b
""", re.I | re.X)

WORKER_RE = re.compile(r"""
  \b(
    for\s+hire | available\s+for\s+work | hire\s+me | my\s+services |
    i\s+(?:can|will)\s+(?:do|help) | offering\s+(?:my|services) |
    portfolio | i'?m\s+available | freelancer\s+here |
    looking\s+for\s+(?:work|a\s+job) | seeking\s+(?:work|a\s+job) |
    open\s+to\s+work | i\s+am\s+looking\s+for\s+work | i\s+am\s+a\s+freelancer
  )\b
""", re.I | re.X)

SPAM_RE = re.compile(r"""
  \b(
    link\s+in\s+bio | follow\s+me | subscribe | course | mentor |
    how\s+to\s+(?:make|earn) | passive\s+income | giveaway | airdrop |
    click\s+here | dm\s+for\s+quick\s+response |
    account\s+verification\s+and\s+setup\s+checks |
    remote\s+job\s+usa | estimated |
    volunteer | unpaid | pro\s+bono | for\s+free |
    what\s+you\s+should\s+know | career\s+opportunities |
    complete\s+guide | how\s+to\s+apply | tips |
    work\s+from\s+anywhere | flexible\s+online\s+work |
    join\s+our\s+growing\s+team | available\s+projects |
    what\s+#?job\s+sites\s+look\s+like | no\s+pay\s+info\s+provided
  )\b
""", re.I | re.X)

SPAM_HANDLE_RE = re.compile(
    r"(gulfcareerhunt|workfromhomejobs|spotdhire|gigsniper|careerhunt|jobleads|jobhunt|geeboads)",
    re.I,
)

SUSPICIOUS_HOST_RE = re.compile(
    r"(blogspot\.|netlify\.app|wordpress\.com|wixsite\.com|weebly\.com|"
    r"tinyurl\.com|bit\.ly)",
    re.I,
)

LANGUAGE_RE = re.compile(r"""
  \b(?:fluent|native|speaker|language|bilingual)\b.{0,40}
  \b(?:spanish|vietnamese|french|german|portuguese|japanese|korean|mandarin|
       arabic|dutch|danish|italian|polish|turkish|hindi|urdu|tagalog|indonesian|thai)\b
  |
  \b(?:spanish|vietnamese|french|german|portuguese|japanese|korean|mandarin|
       arabic|dutch|danish|italian|polish|turkish|hindi|urdu|tagalog|indonesian|thai)\b
  .{0,40}\b(?:fluent|native|speaker|language|bilingual)\b
""", re.I | re.X)

CONTACT_RE = re.compile(
    r"\b(dm|dms|email|e-mail|apply|application|contact|send(?:\s+me)?|"
    r"through|via|company\s*:|budget|rate|salary|paid|pay)\b",
    re.I,
)

PAY_RE = re.compile(
    r"(?:(?P<code>USD|EUR|GBP|CAD|AUD|CHF|SGD|NGN)\s*)?"
    r"(?P<sym>[$€£₦])\s*"
    r"(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<lowk>[kK])?"
    r"(?:\s*(?:-|–|to)\s*(?:(?:USD|EUR|GBP|CAD|AUD|CHF|SGD|NGN)\s*)?"
    r"[$€£₦]?\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<highk>[kK])?)?"
    r"(?:\s*(?:/|per)\s*(?P<period>hr|hour|task|project|day|week|month|year))?",
    re.I,
)

PAY_CODE_RE = re.compile(
    r"\b(?P<code>USD|EUR|GBP|CAD|AUD|CHF|SGD|NGN)\s*"
    r"(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<k>[kK])?\b",
    re.I,
)

PAY_SUFFIX_RE = re.compile(
    r"\b(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<k>[kK])?\s*"
    r"(?P<code>USD|EUR|GBP|CAD|AUD|CHF|SGD|NGN)\b",
    re.I,
)

PERIOD_RE = re.compile(r"\b(?:per|/)\s*(hour|hr|task|project|day|week|month|year)\b", re.I)
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "₦": "NGN"}


def _title(text):
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    candidate = ""
    for line in lines:
        if TASK_RE.search(line):
            candidate = line
            break
    if not candidate:
        candidate = lines[0] if lines else ""
    sentence = re.split(r"(?<=[.!?])\s+", candidate)[0].strip()
    if len(sentence) >= 25:
        candidate = sentence
    if len(candidate) > 120:
        candidate = candidate[:117].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return candidate


def _number(value, k=False):
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return None
    if k:
        number *= 1000
    return number


def parse_pay(text):
    """Extract a simple pay range from a social post, or return None."""
    text = text or ""
    match = PAY_RE.search(text)
    if match:
        code = (match.group("code") or "").upper()
        currency = code or SYMBOL_CURRENCY.get(match.group("sym"), "USD")
        low = _number(match.group("low"), bool(match.group("lowk")))
        high = _number(match.group("high"), bool(match.group("highk"))) if match.group("high") else low
        period = match.group("period")
        # "$2,000 AUD" and "$50 CAD" need the suffix, not the default USD.
        if currency == "USD":
            suffix = re.search(r"\b(AUD|CAD|SGD|NZD)\b", text[match.end():match.end() + 24], re.I)
            if suffix:
                currency = suffix.group(1).upper()
    else:
        match = PAY_CODE_RE.search(text)
        if not match:
            match = PAY_SUFFIX_RE.search(text)
        if not match:
            return None
        currency = match.group("code").upper()
        low = _number(match.group("low"), bool(match.group("k")))
        high = low
        period = None

    if low is None or high is None or low <= 0:
        return None
    if low > high:
        low, high = high, low
    period_match = PERIOD_RE.search(text)
    if period_match:
        period = period_match.group(1)
    if period:
        period = {"hr": "hour", "day": "day", "week": "week", "month": "month", "year": "year"}.get(
            period.lower(), period.lower()
        )
    return {"min": low, "max": high, "currency": currency, "period": period}


def _apply_url(post):
    record = post.get("record") or {}
    embed = record.get("embed") or {}
    external = embed.get("external") if isinstance(embed, dict) else None
    if isinstance(external, dict) and external.get("uri"):
        return external["uri"]
    for facet in record.get("facets") or []:
        for feature in facet.get("features") or []:
            if str(feature.get("$type", "")).endswith("#link") and feature.get("uri"):
                return feature["uri"]
    return None


def acceptable(text, handle="", apply_url=None):
    """Whether a post is a plausible entry-level paid lead, not a worker ad."""
    text = text or ""
    if len(text) < 30:
        return False
    if SPAM_HANDLE_RE.search(handle or ""):
        return False
    if apply_url and SUSPICIOUS_HOST_RE.search(apply_url):
        return False
    if WORKER_RE.search(text) or SPAM_RE.search(text) or LANGUAGE_RE.search(text):
        return False
    if not (TASK_RE.search(text) and HIRING_RE.search(text)):
        return False
    if audience.classify(text[:200], text) != "entry":
        return False

    salary = parse_pay(text)
    if salary and salary["currency"] in HARD and salary["max"] < MIN_TASK_USD:
        return False
    if not salary and not apply_url and not CONTACT_RE.search(text):
        return False
    return True


def _search(query):
    params = urllib.parse.urlencode({
        "q": query,
        "limit": LIMIT,
        "sort": "latest",
        "lang": "en",
    })
    body = json.loads(util.fetch(f"{API}?{params}", timeout=30))
    return body.get("posts") or []


def fetch():
    now = util.now_utc()
    out = []
    seen_uris = set()
    seen_text = set()
    per_handle = {}
    errors = []

    for index, query in enumerate(QUERIES):
        if index:
            time.sleep(0.6)
        try:
            posts = _search(query)
        except Exception as exc:  # one query must not kill the whole source
            errors.append(f"{type(exc).__name__}: {exc}")
            continue

        for post in posts:
            uri = post.get("uri")
            if not uri or uri in seen_uris:
                continue
            record = post.get("record") or {}
            if record.get("reply"):
                continue

            text = (record.get("text") or "").strip()
            handle = (post.get("author") or {}).get("handle") or ""
            apply_url = _apply_url(post)
            if not acceptable(text, handle, apply_url):
                continue

            created = util.parse_dt(record.get("createdAt") or post.get("indexedAt"))
            if not created or (now - created) > timedelta(days=MAX_AGE_DAYS):
                continue

            duplicate_key = (handle.lower(), re.sub(r"\W+", " ", text.lower())[:500])
            if duplicate_key in seen_text:
                continue
            handle_key = handle.lower()
            if per_handle.get(handle_key, 0) >= MAX_PER_HANDLE:
                continue
            seen_uris.add(uri)
            seen_text.add(duplicate_key)
            per_handle[handle_key] = per_handle.get(handle_key, 0) + 1

            salary = parse_pay(text)
            category = "job" if re.search(
                r"\b(part[- ]time|full[- ]time|position|salary|per\s+hour|/hr)\b", text, re.I
            ) else "microtask"
            location = "Remote" if re.search(
                r"\b(remote|worldwide|anywhere|work\s+from\s+home|wfh)\b", text, re.I
            ) else None

            out.append({
                "source": "bluesky",
                "category": category,
                "title": _title(text),
                "company": None,
                "audience": "entry",
                "audience_locked": True,
                "url": f"https://bsky.app/profile/{handle}/post/{uri.rsplit('/', 1)[-1]}",
                "apply_url": apply_url,
                "location_raw": location,
                "description": text,
                "posted_at": created,
                "deadline": None,
                "salary": salary,
                "payment_protection": "direct",
                "social": True,
                "tags": ["social", "bluesky"],
                "extra": {
                    "handle": handle,
                    "uri": uri,
                    "query": query,
                    "likes": post.get("likeCount"),
                    "replies": post.get("replyCount"),
                },
            })

    if errors and len(errors) == len(QUERIES):
        raise RuntimeError("; ".join(errors[:2]))
    return out
