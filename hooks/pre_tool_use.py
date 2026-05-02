#!/usr/bin/env python3
"""PreToolUse hook — intercepts tool calls and sends phone approval requests via Telegram."""
import json
import os
import select
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hooks.lib import config as cfg
from hooks.lib import telegram as tg

TERMINAL_TIMEOUT = 10  # seconds before falling back to Telegram


def _allow():
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }))
    sys.exit(0)


def _deny(reason: str = "Denied"):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def _format_tool_input(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        return tool_input.get("command", "")
    if tool_name in ("Write", "Edit", "MultiEdit"):
        return tool_input.get("file_path", tool_input.get("path", "?"))
    return json.dumps(tool_input)[:300]


def _terminal_prompt(tool_name: str, cmd: str, project: str) -> str | None:
    """
    Interactive selector on /dev/tty.
    Arrow keys (← →) switch between Allow / Don't allow.
    Enter confirms. 20s timeout returns None → falls back to Telegram.
    """
    try:
        import tty as _tty
        import termios

        fd = open("/dev/tty", "r+b", buffering=0)
        old = termios.tcgetattr(fd)
        _tty.setraw(fd)

        def w(text: str):
            fd.write(text.encode())
            fd.flush()

        cmd_disp = cmd[:70] + ("…" if len(cmd) > 70 else "")
        box_w = max(len(f" Claude wants to run {tool_name} "), len(cmd_disp) + 4, 42)

        w("\r\n")
        w(f"  ╭{'─' * box_w}╮\r\n")
        w(f"  │ Claude wants to run {tool_name:<{box_w - 22}}│\r\n")
        w(f"  │{'─' * box_w}│\r\n")
        w(f"  │  {cmd_disp:<{box_w - 3}}│\r\n")
        w(f"  │{'─' * box_w}│\r\n")
        w(f"  │  Project: {project:<{box_w - 12}}│\r\n")
        w(f"  ╰{'─' * box_w}╯\r\n")
        w("\r\n")
        # 2 dynamic lines drawn in loop below

        selected = 0  # 0 = Allow, 1 = Don't allow
        deadline = time.time() + TERMINAL_TIMEOUT
        result = None
        first = True

        while True:
            remaining = max(0, int(deadline - time.time()))

            if not first:
                w("\x1b[2A")  # move cursor up 2 lines to redraw
            first = False

            if selected == 0:
                opts = "  \x1b[7m Allow \x1b[0m   Don't allow  "
            else:
                opts = "   Allow    \x1b[7m Don't allow \x1b[0m"
            w(opts + "\x1b[K\r\n")
            w(f"  \x1b[2m← → to switch · Enter to confirm · Telegram in {remaining}s\x1b[0m\x1b[K\r\n")

            if remaining == 0:
                break

            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                continue

            ch = fd.read(1)

            if ch in (b"\r", b"\n"):
                result = "approve" if selected == 0 else "deny"
                break
            elif ch == b"\x03":  # Ctrl+C
                result = "deny"
                break
            elif ch == b"\x1b":
                r2, _, _ = select.select([fd], [], [], 0.05)
                if not r2:
                    result = "deny"  # lone Escape
                    break
                b2 = fd.read(1)
                if b2 == b"[":
                    r3, _, _ = select.select([fd], [], [], 0.05)
                    if r3:
                        b3 = fd.read(1)
                        if b3 in (b"C", b"D", b"A", b"B"):  # any arrow key toggles
                            selected ^= 1

        termios.tcsetattr(fd, termios.TCSADRAIN, old)

        w("\x1b[2A")
        if result == "approve":
            w("  ✅ Approved\x1b[K\r\n")
        elif result == "deny":
            w("  ❌ Denied\x1b[K\r\n")
        else:
            w("  ⏱  No response — sending Telegram notification...\x1b[K\r\n")
        w("\x1b[K\r\n")

        fd.close()
        return result

    except Exception:
        return None


def main():
    raw = sys.stdin.read()
    data = json.loads(raw)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", "")
    project = os.path.basename(cwd) if cwd else "unknown"

    conf = cfg.load()

    if cfg.should_auto_approve(tool_name, conf):
        _allow()

    if not cfg.should_require_approval(tool_name, conf):
        sys.exit(0)

    formatted = _format_tool_input(tool_name, tool_input)
    terminal_result = _terminal_prompt(tool_name, formatted, project)

    if terminal_result == "approve":
        _allow()
    if terminal_result == "deny":
        _deny("Denied from terminal")

    # No response in 20s — fall back to Telegram
    token = conf["bot_token"]
    chat_id = conf["chat_id"]
    timeout = conf.get("poll_timeout_seconds", 300)

    text = (
        f"<b>Claude wants to run <code>{tool_name}</code></b>\n\n"
        f"<code>{formatted[:300]}</code>\n\n"
        f"Project: <code>{project}</code>"
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
            {"text": "❌ Deny",    "callback_data": f"deny:{session_id}"},
        ]]
    }

    message_id = tg.send_message(token, chat_id, text, reply_markup)
    result = tg.poll_for_callback(token, chat_id, message_id, session_id, timeout)

    if result is None:
        tg.edit_message_text(token, chat_id, message_id, text + "\n\n<i>⏱ Timed out — auto-denied</i>")
        _deny("Timed out — denied for safety")

    decision, callback_id = result
    tg.answer_callback(token, callback_id)

    status = "✅ Approved" if decision == "approve" else "❌ Denied"
    tg.edit_message_text(token, chat_id, message_id, text + f"\n\n<i>{status}</i>")

    if decision == "approve":
        _allow()
    else:
        _deny("Denied via Telegram")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        sys.exit(0)
    except Exception as e:
        print(str(e), file=sys.stderr)
        _deny(f"Hook error — denied for safety: {e}")
