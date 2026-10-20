"""Pipeline entry point.

Usage:
    python3 -m src.run                    # beat run: cadence gates + Telegram
    python3 -m src.run --force            # ignore cadence gates (local testing)
    python3 -m src.run --sources remoteok,himalayas --force
    python3 -m src.run --dry              # fetch + score, save nothing
"""
import argparse
import copy
import traceback

from . import dedupe, evidence, normalize, rank, rules, store, telegram, util
from .sources import REGISTRY

STATE_PATH = f"{util.DATA}/state.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="", help="comma-separated source ids")
    ap.add_argument("--dry", action="store_true", help="do not write data/listings.json")
    ap.add_argument("--force", action="store_true", help="ignore per-source cadence gates")
    args = ap.parse_args()

    cfg = util.load_json(f"{util.CONFIG}/sources.json")
    by_id = {s["id"]: s for s in cfg["sources"]}
    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not wanted:
        wanted = [s["id"] for s in cfg["sources"] if s["enabled"] and s["wave"] == 1]

    state = util.load_json(STATE_PATH, {}) or {}
    old_state = copy.deepcopy({k: v for k, v in state.items() if k != "updated_at"})
    source_state = copy.deepcopy(state.get("sources", {}) or {})
    now = util.now_utc()

    engine = rules.Rules()
    ranker = rank.Ranker()
    raw_items = []

    for sid in wanted:
        source = by_id.get(sid)
        if not source:
            print(f"[skip] unknown source: {sid}")
            continue

        previous = source_state.get(sid, {}) or {}
        last_fetch = util.parse_dt(previous.get("last_fetch"))
        cadence = int(source.get("cadence_minutes", 40))
        if not args.force and last_fetch:
            age_min = (now - last_fetch).total_seconds() / 60
            if age_min < cadence:
                wait = cadence - age_min
                print(f"[gate] {sid}: next fetch in {wait:.0f}m")
                continue

        try:
            raws = REGISTRY[sid]()
            normalized = [normalize.normalize(r, source) for r in raws]
            normalized = [n for n in normalized if n["title"] and n["url"]]
            for item in normalized:
                engine.apply(item)
                ranker.score(item)

            out_of_region = [n for n in normalized if n.get("nigeria_ok") is False]
            normalized = [n for n in normalized if n.get("nigeria_ok") is not False]
            raw_items.extend(normalized)

            source_state[sid] = {
                **previous,
                "ok": True,
                "fetched": len(raws),
                "kept": len(normalized),
                "dropped_location": len(out_of_region),
                "last_fetch": util.iso(now),
            }
            print(
                f"[ok]   {sid}: fetched={len(raws)} kept={len(normalized)} "
                f"dropped_location={len(out_of_region)}"
            )
        except Exception as exc:  # a broken source must not kill the run
            source_state[sid] = {
                **previous,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[FAIL] {sid}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=1)

    merged = dedupe.merge(raw_items)
    for item in merged:
        item.pop("_text", None)
        item.pop("_tags", None)

    merged, evidence_checked = evidence.enrich(merged)
    if evidence_checked:
        print(f"[ev]   checked {evidence_checked} new domain(s)")

    for item in merged:
        engine.retier(item)
        ranker.score(item)

    current = store.load()
    items = store.merge(current.get("items", []), merged)
    items = normalize.refresh_derived(items, by_id)
    for item in items:
        engine.retier(item)
        ranker.score(item)

    # Review actions first, then push new cards. Dry runs must never touch Telegram.
    tg_offset = int(state.get("telegram_offset", 0) or 0)
    if not args.dry:
        items, tg_offset = telegram.sync(items, tg_offset)
        items = telegram.push(items, state)

    blocked = sum(1 for i in items if i.get("tier") == "blocked")
    screened = sum(1 for i in items if i.get("tier") == "screened")
    verified = sum(1 for i in items if i.get("tier") == "verified")
    active = [i for i in items if i.get("status") == "active"]
    entry = sum(1 for i in active if i.get("audience") == "entry")

    print(
        f"\nmerged={len(merged)} stored={len(items)} active={len(active)} "
        f"entry={entry} blocked={blocked} screened={screened} verified={verified}"
    )
    print("top 5 active:")
    for item in active[:5]:
        total = (item.get("score") or {}).get("total", 0)
        print(f"  {total:>4}  {item['tier']:<10} {item['title'][:62]}  [{item['source']}]")

    if not args.dry:
        changed = store.save(items)
        new_state = {
            "version": 1,
            "updated_at": util.iso(util.now_utc()),
            "sources": source_state,
            "telegram_offset": tg_offset,
            "push_day": state.get("push_day"),
            "push_count": state.get("push_count", 0),
        }
        comparable = {k: v for k, v in new_state.items() if k != "updated_at"}
        if comparable != old_state:
            util.save_json(STATE_PATH, new_state)
        print("saved data/listings.json" if changed else "no listing changes")
    else:
        print("dry run: nothing saved")


if __name__ == "__main__":
    main()
