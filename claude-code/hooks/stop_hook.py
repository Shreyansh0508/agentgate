#!/usr/bin/env python3
"""Stop hook — detects when Claude is waiting for input and routes a phone reply back as context."""
import html
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hooks.lib import config as cfg
from hooks.lib import telegram as tg

WAITING_MARKER = "[WAITING_FOR_INPUT]"
_LOG = os.path.expanduser("~/.agentgate/agentgate.log")


def _log(msg: str):
    try:
        os.makedirs(os.path.dirname(_LOG), exist_ok=True)
        with open(_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [stop_hook] {msg}\n")
    except Exception:
        pass


def _read_last_assistant_message(transcript_path: str) -> str | None:
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))  # read only the last 64 KB
            tail = f.read().decode("utf-8", errors="replace")
    except (OSError, IOError):
        return None

    for line in reversed(tail.splitlines()):
        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if entry.get("role") == "assistant":
            content = entry.get("content", "")
            if isinstance(content, list):
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
    if not last_msg or not last_msg.rstrip().endswith(WAITING_MARKER):
        sys.exit(0)

    display_msg = last_msg.replace(WAITING_MARKER, "").strip()
    _log(f"waiting for input: {display_msg[:80]!r}")

    conf = cfg.load()
    token = conf["bot_token"]
    chat_id = conf["chat_id"]
    timeout = conf.get("poll_timeout_seconds", 300)

    text = (
        f"<b>Claude is waiting for your input:</b>\n\n"
        f"{html.escape(display_msg)}\n\n"
        f"<i>↩️ Reply to this message with your answer</i>"
    )
    message_id = tg.send_message(token, chat_id, text)

    reply = tg.poll_for_text_reply(token, chat_id, message_id, timeout)

    if reply is None:
        _log("timed out waiting for reply")
        tg.edit_message_text(token, chat_id, message_id, text + "\n\n<i>⏱ Timed out — Claude will stop and wait</i>")
        sys.exit(0)

    _log(f"reply received: {reply[:80]!r}")
    tg.edit_message_text(token, chat_id, message_id, text + f"\n\n<i>✅ Reply sent: {html.escape(reply[:100])}</i>")

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
        _log(f"error: {e}")
        print(str(e), file=sys.stderr)
        sys.exit(0)
