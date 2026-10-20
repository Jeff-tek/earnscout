# EarnScout

Fresh, hard-currency online earning opportunities for Nigeria — scouted from free public sources, hard-blocked against known scam patterns, scored against your preferences, and pushed to Telegram within the hour.

Personal tool (owner-first). Friends can be added later by whitelisting their Telegram chat IDs; no accounts or login in v1.

## Core loop

```
free sources ──▶ ingest ──▶ normalize + dedupe ──▶ hard blocks ──▶ weak signals
                                                          │
                                                          ▼
                              ranking (currency, protection, international,
                              pay quality, freshness, trending, tier)
                                                          │
                                        ┌─────────────────┴─────────────────┐
                                        ▼                                   ▼
                                 Telegram push                    GitHub Pages dashboard
                                 (Approve / Reject)                (history, evidence, links)
```

## Verification model

| Tier | Meaning |
|---|---|
| 🚫 blocked | A hard-block rule matched. Never shown as an opportunity. |
| 🟡 unverified | Ingested; only weak signals or unknowns. |
| 🟢 screened | No hard blocks; at least two positive signals. |
| ✅ verified | Screened **and** a human approved it, within the review TTL. |
| 🔮 speculative | Airdrops only. Official announcement confirmed; payout not guaranteed. Separate section, never counted as income. |

Labels are **dated claims**, never "safe":

> "No payment demand found (checked 2026-10-20). Domain registered 12 days ago; no CAC match."

## Sources

**Wave 1 (international-first):** Superteam Earn Nigeria, Himalayas, Remote OK, We Work Remotely, CryptoJobsList.

**Wave 2:** HN "Who is Hiring", LaborX, Freelancer, Devpost, Jobzilla, Jobgurus, Fuzu NG, Jobicy, ReliefWeb (pending free appname).

**Excluded** (ToS/robots conflicts, login-gated, or dead): see `config/excluded.json` — Remotive, Reddit, Jobberman, Upwork, LinkedIn, Indeed, Wellfound, Prolific, Remotasks, Toloka, Fiverr, PeoplePerHour/Contra.

**Login-gated platforms** (manual checking only, no polling): see `config/manual-platforms.json`.

## Ranking

```
score = currency      (hard currency disclosed +4, crypto +3, Payoneer/Deel +1, NGN 0)
      + protection    (escrow +2, platform +1, direct 0)
      + international (non-Nigerian employer +2, global-remote +1)
      + pay quality   (above floor +2, disclosed +1)
      + freshness     (<24h +2, <72h +1)
      + trending      (cross-source duplicate +1, engagement +1)
      + tier          (verified +2, screened +1)
```

Floors (hybrid policy): Freelancer projects ≥ **$100** budget, hackathons ≥ **$500** prize pool. Everywhere else, pay is scored and flagged "undisclosed" — never fabricated.

PayPal: hidden when it is the only rail (owner cannot receive it); mixed-rail listings are shown with a flag.

## Architecture

- **Scheduler:** GitHub Actions, 20-minute beat; per-source cadence gates (RSS 40 min, JSON boards ~80 min, Himalayas 6 h).
- **Push budget:** max 5 cards per run and 20/day, newest first, so a backlog never floods the chat.
- **Runtime:** Python 3, stdlib + `feedparser`, `httpx`, `beautifulsoup4`. No LLM calls (not free), heuristics only.
- **Storage:** JSON committed to the repo. Git history is the audit trail. No database.
- **Delivery:** Telegram Bot API push; Approve/Reject inline buttons. Dashboard on GitHub Pages.
- **Cost:** $0. Public repo (unlimited Actions minutes). Bot token lives in Actions secrets.
- **Latency:** alert ≤ ~50 min after a listing appears; button taps settle within one heartbeat.

## Repository layout

```
config/     sources, excluded sources, rules, scoring, brands, manual platforms
schema/     JSON Schema for listings, evidence and sources config
data/       listings.json, manual/speculative.json, evidence/
src/        pipeline code (Phase 1+)
scripts/    maintenance helpers
.github/    Actions workflows
```

## Setup

1. **Secrets** — local `.env` (gitignored) and GitHub Actions secrets use the same names:
   - `TELEGRAM_BOT_TOKEN` — from @BotFather
   - `TELEGRAM_CHAT_ID` — send `/start` to the bot, then run `python3 scripts/tg_whoami.py`
   - `SUPERTEAM_API_KEY` — free agent key from `POST https://superteam.fun/api/agents`
2. **First run:** `python3 -m src.run --force`
3. **Dashboard:** enable GitHub Pages on `main` / root, then open the Pages URL.
4. **Schedule:** `.github/workflows/scan.yml` runs every 20 minutes; per-source gates enforce 40 minutes or longer.

## Audience gate

Every listing is classified `entry`, `skilled` or `unknown`.

- **entry** — task-based work, support, annotation, transcription, assistant, sales rep, writing.
- **skilled** — senior engineering, technical specialist, medical, legal, finance, management, design.
- **unknown** — no clear signal in the title.

The dashboard defaults to **Doable for me** (entry) and the bot only pushes entry items. The audience dropdown reveals the rest.

**Known limitation (2026-10-20):** the current Wave 1 sources are professional/tech boards. Only ~14 of 231 active listings classify as entry, and several are full-time sales/support roles rather than side hustles. The next source pass targets entry-level task work (Freelancer data-entry/VA/transcription categories, support-only feeds, and microtask platform checks).

## Build status

- [x] **Phase 0** — scaffolding, configs, rule schema, README
- [x] **Phase 1** — ingest Wave 1 → normalize → dedupe → `listings.json` + functional dashboard
- [x] **Phase 2** — Telegram bot: push cards, filters, Approve/Reject, update polling
- [x] **Phase 3a** — automated checks (DNS/RDAP/HTTP/redirects), evidence cache, explainable ranking
- [ ] **Phase 3b** — employer-domain discovery + per-listing evidence pages + CAC manual check
- [ ] **Phase 4** — speculative section (manual airdrops) + brand table wired in
- [ ] **Phase 5** — extra sources, beauty pass, friends' chat-ID whitelist

## Non-negotiable safety rules

1. Never pay to get a job — no registration, activation, training, "unlock" or withdrawal fees.
2. A gift-card demand is a scam.
3. Money flows **to** the worker, never **from** the worker.
4. Never share a seed phrase; never connect a wallet that holds funds.
5. Airdrops: fresh wallet only, official domains only, never treated as verified income.

## Compliance

Build only on sources whose `robots.txt` and terms permit automated access. Link out to the rest. Honour attribution requirements (Remote OK, Jobicy).
