"""Rule-engine smoke tests. Run: python3 scripts/test_rules.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules import Rules  # noqa: E402


def make(text):
    return {
        "source": "remoteok",
        "url": "https://example.com/job",
        "title": "",
        "snippet": text,
        "salary": None,
        "signals": [],
        "tier": "unverified",
        "status": "active",
        "payment_rails": [],
        "payment_protection": "platform",
        "sources_seen": ["remoteok"],
        "_text": text,
    }


CASES = [
    ("Registration fee of N25,000 required to start the job", "HB_PAY_TO_WORK"),
    ("Pay 5000 to activate your account and begin earning", "HB_PAY_TO_WORK"),
    ("Buy an Amazon gift card and send us the code", "HB_GIFT_CARD_DEMAND"),
    ("Send 50 USDT to unlock your withdrawal", "HB_CRYPTO_OUTFLOW"),
    ("Share your seed phrase to verify your wallet", "HB_WALLET_SECURITY"),
    ("Connect your wallet to complete onboarding", "HB_WALLET_SECURITY"),
    ("Receive payments and forward to another account, keep 10%", "HB_MULE"),
    ("Download the APK and enable unknown sources", "HB_SIDELOAD_APK"),
    ("Like videos and earn $10,000 per day from home", "HB_IMPLAUSIBLE_PAY"),
    ("Earn N100,000 daily by rating products", "HB_IMPLAUSIBLE_PAY"),
]

CLEAN = [
    "Senior backend engineer. Remote worldwide. We pay in USDT monthly.",
    "Security engineer: protect customers from seed phrase theft and phishing.",
    "Data annotator reviewing video content. $18/hour.",
]

failures = 0
engine = Rules()

for text, expected in CASES:
    item = make(text)
    engine.apply(item)
    blocks = [s["id"] for s in item["signals"] if s["severity"] == "block"]
    ok = expected in blocks
    print(("PASS" if ok else "FAIL"), expected, "<-", text[:60])
    failures += 0 if ok else 1

for text in CLEAN:
    item = make(text)
    engine.apply(item)
    blocks = [s["id"] for s in item["signals"] if s["severity"] == "block"]
    ok = not blocks
    print(("PASS" if ok else "FAIL"), "clean", "<-", text[:60], blocks)
    failures += 0 if ok else 1

print("\nresult:", "ALL PASS" if failures == 0 else f"{failures} FAILURES")
sys.exit(0 if failures == 0 else 1)
