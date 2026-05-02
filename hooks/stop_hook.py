#!/usr/bin/env python3
"""Stop hook — detects when Claude is waiting for input and routes a phone reply back as context."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hooks.lib import config as cfg
from hooks.lib import telegram as tg

WAITING_MARKER = "[WAITING_FOR_INPUT]"


def _read_last_assistant_message(transcript_path: str) -> str | None:
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except (OSError, IOError):
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if entry.get("role") == "assistant":
            content = entry.get("content", "")
            if isinstance(content, list):
                # Extract text blocks
                parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                return " ".join(parts)
            if isinstance(content, str):
                return content
    return None


def main():
    raw = sys.stdin.read()
    data = json.loads(raw)

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    last_msg = _read_last_assistant_message(transcript_path)
    if not last_msg or WAITING_MARKER not in last_msg:
        sys.exit(0)

    # Strip the marker from what we show on the phone
    display_msg = last_msg.replace(WAITING_MARKER, "").strip()

    conf = cfg.load()
    token = conf["bot_token"]
    chat_id = conf["chat_id"]
    timeout = conf.get("poll_timeout_seconds", 300)

    text = (
        f"<b>Claude is waiting for your input:</b>\n\n"
        f"{display_msg}\n\n"
        f"<i>↩️ Reply to this message with your answer</i>"
    )
    message_id = tg.send_message(token, chat_id, text)

    reply = tg.poll_for_text_reply(token, chat_id, message_id, timeout)

    if reply is None:
        tg.edit_message_text(token, chat_id, message_id, text + "\n\n<i>⏱ Timed out — Claude will stop and wait</i>")
        sys.exit(0)  # Let Claude stop normally; user can resume at laptop

    tg.edit_message_text(token, chat_id, message_id, text + f"\n\n<i>✅ Reply sent: {reply[:100]}</i>")

    print(json.dumps({
        "decision": "block",
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": f"User replied via phone: '{reply}'",
        },
    }))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        sys.exit(0)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(0)  # On error, let Claude stop normally rather than blocking forever
