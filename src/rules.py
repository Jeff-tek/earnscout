"""Rule engine: hard blocks, weak signals, positive signals."""
import re

from . import util


class Rules:
    def __init__(self, path=None):
        self.cfg = util.load_json(path or f"{util.CONFIG}/rules.json")
        self.compiled = {}
        self.condition_patterns = {}
        for group in ("hard_blocks", "weak_signals", "positive_signals"):
            for r in self.cfg.get(group, []):
                det = r.get("detector", {})
                pats = list(det.get("patterns", []))
                for c in det.get("conditions", []):
                    pats += c.get("patterns", [])
                self.compiled[r["id"]] = [re.compile(p, re.I) for p in pats]
                self.condition_patterns[r["id"]] = [
                    [re.compile(p, re.I) for p in c.get("patterns", [])]
                    for c in det.get("conditions", [])
                ]

    def _first_match(self, rule_id, text):
        for p in self.compiled.get(rule_id, []):
            m = p.search(text)
            if m:
                return m.group(0)
        return None

    def _eval_detector(self, rule, text, listing):
        det = rule.get("detector", {})
        typ = det.get("type")

        if typ == "regex_any":
            return self._first_match(rule["id"], text)

        if typ == "composite_all":
            evidence = []
            passed = True
            conditions = det.get("conditions", [])
            for idx, cond in enumerate(conditions):
                ctyp = cond.get("type")
                if ctyp == "regex_any":
                    found = None
                    for p in self.condition_patterns.get(rule["id"], [[]])[idx]:
                        m = p.search(text)
                        if m:
                            found = m.group(0)
                            break
                    if not found:
                        return None
                    evidence.append(found)
                elif ctyp == "not_present":
                    if any(re.search(p, text, re.I) for p in cond.get("patterns", [])):
                        return None
                else:
                    passed = False
            if not passed:
                return None
            return " | ".join(evidence) if evidence else rule.get("label", "all conditions met")

        if typ == "tld_in":
            tld = util.domain_of(listing.get("url", "")).rsplit(".", 1)[-1]
            return tld if tld in det.get("tlds", []) else None

        # domain_age, page_missing, manual, brand_domain_mismatch, official_domain_match,
        # email_domain_match are evidence-based and land in Phase 3/4.
        return None

    def apply(self, listing):
        text = listing.get("_text") or ""
        signals = []

        for rule in self.cfg.get("hard_blocks", []):
            ev = self._eval_detector(rule, text, listing)
            if ev:
                signals.append({"id": rule["id"], "severity": "block", "evidence": ev[:160]})

        for rule in self.cfg.get("weak_signals", []):
            ev = self._eval_detector(rule, text, listing)
            if ev:
                signals.append({"id": rule["id"], "severity": "weak", "evidence": ev[:160]})

        for rule in self.cfg.get("positive_signals", []):
            det = rule.get("detector", {})
            matched = None
            if det.get("type") == "source_in" and listing["source"] in det.get("sources", []):
                matched = listing["source"]
            elif det.get("type") == "field_present" and listing.get(det.get("field")):
                matched = det.get("field")
            if matched:
                signals.append({
                    "id": rule["id"],
                    "severity": "positive",
                    "support": rule.get("support", 1),
                    "evidence": matched,
                })

        listing["signals"] = signals
        self.retier(listing)
        return listing

    def retier(self, listing):
        signals = listing.get("signals") or []
        if any(s.get("severity") == "block" for s in signals):
            listing["tier"] = "blocked"
            listing["status"] = "blocked"
            return
        support = sum(s.get("support", 0) for s in signals if s.get("severity") == "positive")
        if listing.get("tier") != "verified":
            listing["tier"] = "screened" if support >= 2 else "unverified"
