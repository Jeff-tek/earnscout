"""Explainable ranking: every component is stored and displayed."""
import re

from . import util

HARD = {"usd", "eur", "gbp", "cad", "aud", "chf", "sgd"}
CRYPTO = {"usdt", "usdc", "btc", "eth", "sol", "bnb"}
NAMED = {"payoneer", "deel", "wise", "grey", "cleva", "daya", "chipper"}
NIGERIA_ONLY_SOURCES = {"jobzilla", "jobgurus", "fuzu_ng", "jobicy", "myjobmag", "hotnigerianjobs"}


class Ranker:
    def __init__(self, path=None):
        self.cfg = util.load_json(path or f"{util.CONFIG}/scoring.json")
        self.w = self.cfg["weights"]

    def score(self, listing):
        c = {}
        rails = [str(r).lower() for r in (listing.get("payment_rails") or [])]
        cur = self.w["currency"]

        if any(r in CRYPTO or r == "crypto" for r in rails):
            c["currency"] = cur["crypto_named"]
        elif "gift_card" in rails:
            c["currency"] = cur["gift_card_named"]
        elif any(r in HARD for r in rails):
            c["currency"] = cur["hard_currency_disclosed"]
        elif any(r in NAMED for r in rails):
            c["currency"] = cur["payoneer_or_deel_named"]
        else:
            c["currency"] = cur["ngn_only"]

        c["protection"] = self.w["protection"].get(
            listing.get("payment_protection") or "unknown", 0
        )

        intl = self.w["international"]
        if listing.get("source") not in NIGERIA_ONLY_SOURCES:
            c["international"] = intl["non_nigerian_employer"]
            loc = (listing.get("location_raw") or "").lower()
            if re.search(r"worldwide|anywhere|global|remote", loc):
                c["international"] += intl["global_remote"]
        else:
            c["international"] = 0

        sal = listing.get("salary") or {}
        disclosed = bool(sal.get("min") or sal.get("max") or sal.get("currency"))
        c["pay_quality"] = self.w["pay_quality"]["disclosed"] if disclosed else 0

        fresh = self.w["freshness"]
        dt = util.parse_dt(listing.get("posted_at"))
        age_h = (util.now_utc() - dt).total_seconds() / 3600 if dt else None
        if age_h is not None and age_h < 24:
            c["freshness"] = fresh["lt_24h"]
        elif age_h is not None and age_h < 72:
            c["freshness"] = fresh["lt_72h"]
        else:
            c["freshness"] = 0

        c["trending"] = (
            self.w["trending"]["cross_source_duplicate"]
            if len(listing.get("sources_seen") or []) > 1
            else 0
        )
        c["tier"] = self.w["tier"].get(listing.get("tier"), 0)

        listing["score"] = {"total": round(sum(c.values()), 2), "components": c}
        return listing["score"]["total"]
