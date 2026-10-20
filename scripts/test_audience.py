"""Audience classifier tests. Run: python3 scripts/test_audience.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audience import classify  # noqa: E402

CASES = [
    ("Senior Customer Support Specialist", "skilled"),
    ("Customer Support Specialist", "entry"),
    ("Data Entry Clerk", "entry"),
    ("Virtual Assistant", "entry"),
    ("Senior Software Engineer", "skilled"),
    ("Technical Specialist", "skilled"),
    ("Administrative Assistant", "entry"),
    ("Circle Summer Intern 2027", "unknown"),
    ("Security Operation Intern", "unknown"),
    ("Content Moderator", "entry"),
    ("Academic Dean", "unknown"),
    ("Project Manager", "skilled"),
    ("Clinical Specialist, CRM", "skilled"),
    ("Billing and Claims Support Representative", "entry"),
    ("Client Engagement Representative Work From Home", "entry"),
    ("Senior Data Entry Specialist", "skilled"),
    ("Sales Development Representative", "skilled"),
    ("Legal Operations Assistant", "skilled"),
    ("Circle Summer Intern 2027", "unknown"),
    ("Client Engagement Representative Work From Home", "entry"),
]

failures = 0
for title, expected in CASES:
    actual = classify(title)
    ok = actual == expected
    print(("PASS" if ok else "FAIL"), f"{actual:8}", "<-", title)
    failures += 0 if ok else 1

print("\nresult:", "ALL PASS" if failures == 0 else f"{failures} FAILURES")
sys.exit(0 if failures == 0 else 1)
