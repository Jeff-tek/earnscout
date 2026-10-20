"""Pipeline entry point.

Usage:
    python3 -m src.run                 # wave 1 enabled sources
    python3 -m src.run --sources remoteok,himalayas
    python3 -m src.run --dry           # fetch + score, do not save
"""
import argparse
import traceback

from . import dedupe, normalize, rank, rules, store, util
from .sources import REGISTRY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="", help="comma-separated source ids")
    ap.add_argument("--dry", action="store_true", help="do not write data/listings.json")
    args = ap.parse_args()

    cfg = util.load_json(f"{util.CONFIG}/sources.json")
    by_id = {s["id"]: s for s in cfg["sources"]}
    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not wanted:
        wanted = [s["id"] for s in cfg["sources"] if s["enabled"] and s["wave"] == 1]

    engine = rules.Rules()
    ranker = rank.Ranker()
    raw_items = []
    source_status = {}

    for sid in wanted:
        source = by_id.get(sid)
        if not source:
            print(f"[skip] unknown source: {sid}")
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
            source_status[sid] = {
                "ok": True,
                "fetched": len(raws),
                "kept": len(normalized),
                "dropped_location": len(out_of_region),
            }
            print(
                f"[ok]   {sid}: fetched={len(raws)} kept={len(normalized)} "
                f"dropped_location={len(out_of_region)}"
            )
        except Exception as exc:  # a broken source must not kill the run
            source_status[sid] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[FAIL] {sid}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=1)

    merged = dedupe.merge(raw_items)
    for item in merged:
        engine.retier(item)
        ranker.score(item)
        item.pop("_text", None)
        item.pop("_tags", None)

    current = store.load()
    items = store.merge(current.get("items", []), merged)

    blocked = sum(1 for i in items if i.get("tier") == "blocked")
    screened = sum(1 for i in items if i.get("tier") == "screened")
    verified = sum(1 for i in items if i.get("tier") == "verified")
    active = [i for i in items if i.get("status") == "active"]

    print(
        f"\nmerged={len(merged)} stored={len(items)} active={len(active)} "
        f"blocked={blocked} screened={screened} verified={verified}"
    )
    print("top 5 active:")
    for item in active[:5]:
        total = (item.get("score") or {}).get("total", 0)
        print(f"  {total:>4}  {item['tier']:<10} {item['title'][:62]}  [{item['source']}]")

    if not args.dry:
        store.save(items)
        util.save_json(
            f"{util.DATA}/state.json",
            {"updated_at": util.iso(util.now_utc()), "sources": source_status},
        )
        print("saved data/listings.json")
    else:
        print("dry run: nothing saved")


if __name__ == "__main__":
    main()
