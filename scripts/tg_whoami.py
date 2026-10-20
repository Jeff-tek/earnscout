"""Print Telegram chat IDs from pending updates. Run after sending /start to the bot.

    python3 scripts/tg_whoami.py

Keep the result in .env as TELEGRAM_CHAT_ID (never commit it).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import telegram  # noqa: E402


def main():
    updates = telegram.get_updates(0)
    if not updates:
        print("No updates. Open Telegram, send /start to your bot, then run this again.")
        return
    seen = set()
    for update in updates:
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") and chat["id"] not in seen:
            seen.add(chat["id"])
            who = chat.get("username") or chat.get("first_name") or chat.get("type")
            print(f"chat_id={chat['id']}  ({who})")
    if not seen:
        print("Updates found, but no chat IDs. Send /start to the bot.")


if __name__ == "__main__":
    main()
