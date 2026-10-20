"""Audience classification: can an average person actually do this?

`entry`    task-based / support / annotation / assistant work, no specialist
           credentials implied by the title.
`skilled`  engineering, medical, legal, finance, management, design, etc.
`unknown`  title gives no clear signal; hidden by default, visible on request.

The owner explicitly cannot take senior engineering / technical specialist /
admin roles, so `skilled` is never pushed and is hidden in the dashboard.
"""
import re

STRONG_SKILLED = re.compile(r"""
  \b(
    senior | sr\.? | lead | principal | staff | director | vp | vice\s+president |
    head\s+of | chief | cto | ceo | cfo | coo |
    architect | engineer | developer | programmer | scientist | analyst | consultant |
    sysadmin | administrator | devops | sre |
    accountant | nurse | doctor | pharmacist | lawyer | attorney | auditor |
    controller | cpa | cfa | recruiter | economist | quant | trader | underwriter |
    actuary | paralegal | counsel | manager | supervisor | superintendent | officer |
    strategist | designer | editor | technical\s+writer |
    legal | medical | clinical | psychology | finance | accounting | therapist |
    pharmacist | dental | veterinary | sales | business\s+development |
    account\s+development
  )\b
""", re.I | re.X)

ENTRY_TITLE = re.compile(r"""
  \b(
    data\s*entry | annotat\w* | transcrib\w* | caption\w* |
    content\s*(review|moderat)\w* | moderat\w* | rater | reviewer |
    tagger | labeler | microtask\w* | survey\w* |
    customer\s*(support|service) | chat\s*support | support\s*(agent|representative|rep) |
    virtual\s*assistant | assistant | ambassador |
    client\s*engagement\s*representative |
    research\s*assistant | lead\s*generation | appointment\s*setter |
    tester | user\s*testing | product\s*tester |
    proofread\w* | copy\s*typ\w* | typing | writer | copywriter
  )\b
""", re.I | re.X)

ENTRY_HINT = re.compile(
    r"\b(no experience|entry[- ]level|training (is )?provided|fresher)\b",
    re.I,
)


INTERN = re.compile(r"\bintern(ship)?s?\b", re.I)


def classify(title, snippet=""):
    title = (title or "").strip()
    if INTERN.search(title):
        return "unknown"
    if STRONG_SKILLED.search(title):
        return "skilled"
    if ENTRY_TITLE.search(title):
        return "entry"
    if re.search(r"\bspecialist\b", title, re.I):
        return "skilled"
    if ENTRY_HINT.search(title) or ENTRY_HINT.search(snippet or ""):
        return "entry"
    return "unknown"
