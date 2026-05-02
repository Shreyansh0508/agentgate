#!/usr/bin/env python3
"""PreToolUse hook — terminal prompt + Telegram notification fired simultaneously."""
import json
import os
import select
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hooks.lib import config as cfg
from hooks.lib import telegram as tg

TERMINAL_TIMEOUT = 10  # seconds before terminal prompt closes


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


def _terminal_prompt(tool_name: str, cmd: str, project: str, done_event: threading.Event) -> str | None:
    """
    Interactive selector on /dev/tty. Closes after TERMINAL_TIMEOUT seconds
    or when done_event is set (Telegram responded first).
    Returns 'approve', 'deny', or None.
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

        selected = 0
        deadline = time.time() + TERMINAL_TIMEOUT
        result = None
        first = True

        while True:
            remaining = max(0, int(deadline - time.time()))

            if not first:
                w("\x1b[2A")
            first = False

            if done_event.is_set():
                w("  \x1b[2m(Responded via Telegram)\x1b[0m\x1b[K\r\n")
                w("\x1b[K\r\n")
                break

            opts = ("  \x1b[7m Allow \x1b[0m   Don't allow  " if selected == 0
                    else "   Allow    \x1b[7m Don't allow \x1b[0m")
            w(opts + "\x1b[K\r\n")
            w(f"  \x1b[2m← → · Enter to confirm · also sent to Telegram · {remaining}s\x1b[0m\x1b[K\r\n")

            if remaining == 0:
                w("\x1b[2A")
                w("  \x1b[2m(No terminal response — waiting for Telegram...)\x1b[0m\x1b[K\r\n")
                w("\x1b[K\r\n")
                break

            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                continue

            ch = fd.read(1)
            if ch in (b"\r", b"\n"):
                result = "approve" if selected == 0 else "deny"
                break
            elif ch == b"\x03":
                result = "deny"
                break
            elif ch == b"\x1b":
                r2, _, _ = select.select([fd], [], [], 0.05)
                if not r2:
                    result = "deny"
                    break
                b2 = fd.read(1)
                if b2 == b"[":
                    r3, _, _ = select.select([fd], [], [], 0.05)
                    if r3:
                        b3 = fd.read(1)
                        if b3 in (b"C", b"D", b"A", b"B"):
                            selected ^= 1

        termios.tcsetattr(fd, termios.TCSADRAIN, old)

        if result == "approve":
            w("\x1b[2A")
            w("  ✅ Approved from terminal\x1b[K\r\n")
            w("\x1b[K\r\n")
        elif result == "deny":
            w("\x1b[2A")
            w("  ❌ Denied from terminal\x1b[K\r\n")
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

    token = conf["bot_token"]
    chat_id = conf["chat_id"]
    timeout = conf.get("poll_timeout_seconds", 300)
    formatted = _format_tool_input(tool_name, tool_input)

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

    # Shared state between threads
    decision = [None]
    source = [None]
    done = threading.Event()
    telegram_msg_id = [None]
    telegram_callback_id = [None]

    def run_telegram():
        try:
            msg_id = tg.send_message(token, chat_id, text, reply_markup)
            telegram_msg_id[0] = msg_id
            result = tg.poll_for_callback(token, chat_id, msg_id, session_id, timeout, stop_event=done)
            if result and not done.is_set():
                decision[0], telegram_callback_id[0] = result
                source[0] = "telegram"
                done.set()
        except Exception:
            pass

    def run_terminal():
        result = _terminal_prompt(tool_name, formatted, project, done)
        if result and not done.is_set():
            decision[0] = result
            source[0] = "terminal"
            done.set()

    t_telegram = threading.Thread(target=run_telegram, daemon=True)
    t_terminal = threading.Thread(target=run_terminal, daemon=True)

    t_telegram.start()
    t_terminal.start()

    done.wait(timeout=timeout + 15)

    # Update Telegram message to reflect final outcome
    if telegram_msg_id[0]:
        try:
            if source[0] == "telegram" and telegram_callback_id[0]:
                tg.answer_callback(token, telegram_callback_id[0])
            if decision[0] == "approve":
                suffix = "\n\n<i>✅ Approved" + (" from terminal" if source[0] == "terminal" else "") + "</i>"
            elif decision[0] == "deny":
                suffix = "\n\n<i>❌ Denied" + (" from terminal" if source[0] == "terminal" else "") + "</i>"
            else:
                suffix = "\n\n<i>⏱ Timed out — auto-denied</i>"
            tg.edit_message_text(token, chat_id, telegram_msg_id[0], text + suffix)
        except Exception:
            pass

    if decision[0] == "approve":
        _allow()
    elif decision[0] == "deny":
        _deny(f"Denied via {source[0] or 'timeout'}")
    else:
        _deny("Timed out — denied for safety")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        sys.exit(0)
    except Exception as e:
        print(str(e), file=sys.stderr)
        _deny(f"Hook error — denied for safety: {e}")
