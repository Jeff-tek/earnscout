"""Telegram delivery: push cards, handle /start and Approve/Reject callbacks."""
import json
import os
import urllib.request

from . import util

TIER_EMOJI = {
    "verified": "✅",
    "screened": "🟢",
    "unverified": "🟡",
    "speculative": "🔮",
}


def _token():
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def api(method, payload=None, timeout=30):
    token = _token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": util.USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {body.get('description')}")
    return body


def get_updates(offset):
    body = api("getUpdates", {
        "offset": offset,
        "timeout": 0,
        "allowed_updates": ["message", "callback_query"],
    })
    return body.get("result", [])


def send(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return api("sendMessage", payload)


def card_text(item):
    score = (item.get("score") or {}).get("total", "—")
    lines = [
        f"{TIER_EMOJI.get(item.get('tier'), '•')} {str(item.get('tier', '')).upper()} · score {score}",
        item.get("title") or "(untitled)",
    ]
    if item.get("company"):
        lines.append(str(item["company"]))
    lines.append(f"{item.get('source')} · {item.get('location_raw') or 'location n/a'}")
    lines.append(
        "Pay: " + ", ".join(item.get("payment_rails") or ["unknown"])
        + f" · {item.get('payment_protection') or 'unknown'} protection"
    )
    if item.get("deadline"):
        lines.append(f"Closes: {item['deadline'][:10]}")
    if item.get("posted_at"):
        lines.append(f"Posted: {item['posted_at'][:10]}")
    components = (item.get("score") or {}).get("components") or {}
    if components:
        lines.append("Why: " + ", ".join(f"{k} {v}" for k, v in components.items()))
    lines.append(item.get("url") or "")
    return "\n".join(lines)


def sync(items, offset=0):
    """Process pending updates: /start handshake and review callbacks.

    Returns (items, new_offset). The offset must be persisted by the caller,
    otherwise every run replays the same updates.
    """
    try:
        updates = get_updates(offset)
    except Exception as exc:
        print(f"[tg] getUpdates failed: {exc}")
        return items, offset

    by_id = {i["id"]: i for i in items}
    for update in updates:
        offset = max(offset, int(update.get("update_id", 0)) + 1)
        if "message" in update:
            msg = update["message"]
            text = (msg.get("text") or "").strip()
            chat_id = msg.get("chat", {}).get("id")
            if text.startswith("/start") and chat_id:
                send(
                    chat_id,
                    "EarnScout connected.\n\n"
                    "You will receive fresh, hard-currency opportunities with dated evidence.\n"
                    "Every card is screened; press ✅ only after you have checked it.\n\n"
                    f"Your chat id: {chat_id}\n"
                    "Add it as TELEGRAM_CHAT_ID (secret / .env) so scheduled runs can push.",
                )
                print(f"[tg] /start from chat {chat_id}")
        callback = update.get("callback_query")
        if not callback:
            continue
        action, _, item_id = (callback.get("data") or "").partition(":")
        item = by_id.get(item_id)
        if not item or action not in ("approve", "reject"):
            api("answerCallbackQuery", {"callback_query_id": callback["id"], "text": "Unknown item"})
            continue
        approved = action == "approve"
        item["review"] = {
            "status": "approved" if approved else "rejected",
            "by": str(callback.get("from", {}).get("username") or callback.get("from", {}).get("id")),
            "at": util.iso(util.now_utc()),
            "note": None,
        }
        if approved and item.get("tier") != "blocked":
            item["tier"] = "verified"
        else:
            item["tier"] = "unverified" if not approved else item.get("tier")
            if not approved:
                item["status"] = "archived"
        api("answerCallbackQuery", {
            "callback_query_id": callback["id"],
            "text": "Marked verified" if approved else "Rejected",
        })
        print(f"[tg] {action} {item_id} -> {item.get('tier')}")

    return items, offset


def push(items, state, limit=5, daily_cap=20):
    """Send new screened/verified items to the owner's chat.

    A daily cap prevents a backlog from flooding the chat on first run.
    """
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        print("[tg] TELEGRAM_CHAT_ID not set; skipping push (send /start to the bot)")
        return items

    today = util.iso(util.now_utc())[:10]
    if state.get("push_day") != today:
        state["push_day"] = today
        state["push_count"] = 0
    if int(state.get("push_count", 0)) >= daily_cap:
        print("[tg] daily push cap reached; backlog stays queued")
        return items

    sent = 0
    ordered = sorted(
        items,
        key=lambda i: ((i.get("first_seen_at") or ""), (i.get("score") or {}).get("total", 0)),
        reverse=True,
    )
    for item in ordered:
        if sent >= limit or int(state.get("push_count", 0)) >= daily_cap:
            break
        if item.get("status") != "active" or item.get("pushed_at"):
            continue
        if item.get("audience") != "entry":
            continue
        if item.get("tier") not in ("screened", "verified"):
            continue

        keyboard = None
        if item.get("tier") == "screened":
            keyboard = [[
                {"text": "✅ I checked it", "callback_data": f"approve:{item['id']}"},
                {"text": "🚫 Reject", "callback_data": f"reject:{item['id']}"},
            ]]
        try:
            send(chat_id, card_text(item), keyboard)
        except Exception as exc:
            print(f"[tg] send failed: {exc}")
            break
        item["pushed_at"] = util.iso(util.now_utc())
        state["push_count"] = int(state.get("push_count", 0)) + 1
        sent += 1

    if sent:
        print(f"[tg] pushed {sent} item(s)")
    return items
