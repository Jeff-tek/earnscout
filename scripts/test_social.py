"""Bluesky social-lead filter smoke tests. Run: python3 scripts/test_social.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sources import bluesky  # noqa: E402

CASES = [
    (
        True,
        "We are hiring a data entry assistant. $50 per task. DM me.",
        "realuser.bsky.social",
        None,
    ),
    (
        True,
        "Hiring now (remote): Consumer Reviewer - $20-30/hr through micro1. Apply here.",
        "mtlremotejobs.bsky.social",
        "https://jobs.micro1.ai/post/123",
    ),
    (
        False,
        "I am available for work as a data entry assistant. DM me.",
        "worker.bsky.social",
        None,
    ),
    (
        False,
        "Hiring for Virtual Assistant REMOTE JOB USA. Salary: $35,000. Estimated.",
        "gulfcareerhunt.bsky.social",
        None,
    ),
    (
        False,
        "We are hiring: Basic data entry and spreadsheet logging. Account verification and setup checks.",
        "freelancer2.bsky.social",
        None,
    ),
    (
        False,
        "Micro1 is hiring Video Data Annotators! Pay: $7/hour. Apply now.",
        "rmc89.bsky.social",
        None,
    ),
    (
        False,
        "We are hiring volunteers for data entry. This is unpaid.",
        "charity.bsky.social",
        None,
    ),
    (
        False,
        "what #job sites look like these days: Data Entry, no pay info provided.",
        "ladychelsea.bsky.social",
        None,
    ),
    (
        False,
        "Remote Data Entry Career Opportunities: What You Should Know. Complete guide.",
        "blogger.bsky.social",
        "https://example.blogspot.com/post",
    ),
    (
        False,
        "Hiring now (remote): Spanish-Language Consumer Reviewer. $20-30/hr.",
        "mtlremotejobs.bsky.social",
        None,
    ),
]

PAY_CASES = [
    ("$50 per task", {"min": 50.0, "max": 50.0, "currency": "USD", "period": "task"}),
    ("$20-30/hr", {"min": 20.0, "max": 30.0, "currency": "USD", "period": "hour"}),
    ("$2,000 AUD", {"min": 2000.0, "max": 2000.0, "currency": "AUD", "period": None}),
    ("$50k", {"min": 50000.0, "max": 50000.0, "currency": "USD", "period": None}),
]


def main():
    failures = 0
    for expected, text, handle, apply_url in CASES:
        actual = bluesky.acceptable(text, handle, apply_url)
        ok = actual is expected
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'} accept={actual!s:<5} <- {text[:80]}")
    for text, expected in PAY_CASES:
        actual = bluesky.parse_pay(text)
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'} pay={actual} <- {text}")

    print(f"\nresult: {'ALL PASS' if not failures else f'{failures} FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
