#!/usr/bin/env python3
"""One-time setup wizard for Claude Code Remote Approval System."""
import json
import os
import ssl
import stat
import sys
import time
import urllib.request

SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks")

_SAP_CERT = os.path.expanduser("~/.claude/certs/SAPNetCA_G2.pem")


def _ssl_context():
    # Try with SAP corporate CA cert first; fall back to unverified if still blocked
    ctx = ssl.create_default_context()
    if os.path.exists(_SAP_CERT):
        ctx.load_verify_locations(_SAP_CERT)
    return ctx


def _api(token, method, payload=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    last_err = None
    for ctx in (_ssl_context(), ssl._create_unverified_context()):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
            continue
    return {"ok": False, "error": str(last_err)}


def _validate_token(token):
    r = _api(token, "getMe")
    if r.get("ok"):
        return r["result"]["username"]
    print(f"  [debug] error: {r.get('error')}")
    return None


def _get_chat_id(token):
    print("  Waiting for you to send a message to your bot in Telegram...")
    print("  (Open Telegram, find your bot, send it any message like 'hello')")
    deadline = time.time() + 120
    offset = 0
    while time.time() < deadline:
        r = _api(token, "getUpdates", {"offset": offset, "timeout": 10})
        for update in r.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message")
            if msg:
                return str(msg["chat"]["id"]), msg["chat"].get("first_name", "")
        sys.stdout.write(".")
        sys.stdout.flush()
    return None, None


def _send_test(token, chat_id, session_id="test"):
    payload = {
        "chat_id": chat_id,
        "text": "<b>Test: Claude wants to run <code>Bash</code></b>\n\n<code>echo hello world</code>\n\nProject: <code>test_project</code>",
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
                {"text": "❌ Deny",    "callback_data": f"deny:{session_id}"},
            ]]
        }
    }
    r = _api(token, "sendMessage", payload)
    return r.get("result", {}).get("message_id")


def _poll_callback(token, chat_id, message_id, session_id, timeout=60):
    offset = 0
    r = _api(token, "getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    for u in r.get("result", []):
        offset = u["update_id"] + 1

    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        r = _api(token, "getUpdates", {"offset": offset, "timeout": min(15, max(1, remaining))})
        for update in r.get("result", []):
            offset = update["update_id"] + 1
            cq = update.get("callback_query")
            if not cq:
                continue
            if cq.get("message", {}).get("message_id") != message_id:
                continue
            cb_data = cq.get("data", "")
            if cb_data in (f"approve:{session_id}", f"deny:{session_id}"):
                _api(token, "answerCallbackQuery", {"callback_query_id": cq["id"]})
                return "approve" if cb_data.startswith("approve") else "deny"
        sys.stdout.write(".")
        sys.stdout.flush()
    return None


def _patch_settings(hooks_dir):
    hook_py = sys.executable  # same python that's running setup.py
    with open(SETTINGS_PATH) as f:
        settings = json.load(f)

    hooks = settings.setdefault("hooks", {})

    pre_cmd = f"{hook_py} {os.path.join(hooks_dir, 'pre_tool_use.py')}"
    stop_cmd = f"{hook_py} {os.path.join(hooks_dir, 'stop_hook.py')}"

    hooks["PreToolUse"] = [{"matcher": "", "hooks": [{"type": "command", "command": pre_cmd, "timeout": 310}]}]
    hooks["Stop"] = [{"matcher": "", "hooks": [{"type": "command", "command": stop_cmd, "timeout": 310}]}]

    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def main():
    print("=== Claude Code Remote Approval Setup ===\n")

    # Step 1: Bot token
    print("Step 1: Create a Telegram Bot")
    print("  1. Open Telegram → search @BotFather")
    print("  2. Send /newbot and follow prompts")
    print("  3. Copy the token it gives you\n")
    token = input("Enter your bot token: ").strip()
    bot_name = _validate_token(token)
    if not bot_name:
        print("ERROR: Could not connect to Telegram with that token. Check and try again.")
        sys.exit(1)
    print(f"  ✓ Connected to bot: @{bot_name}\n")

    # Step 2: Chat ID
    print("Step 2: Get your Chat ID")
    chat_id, first_name = _get_chat_id(token)
    print()
    if not chat_id:
        print("ERROR: Timed out waiting for a message. Make sure you sent a message to the bot.")
        sys.exit(1)
    print(f"  ✓ Chat ID: {chat_id} (from: {first_name})\n")

    # Step 3: Tool lists
    print("Step 3: Configure which tools require remote approval")
    print("  Defaults — require approval: Bash, Write, Edit, MultiEdit")
    print("             auto-approve: Read, Glob, Grep, LS")
    require_input = input("  Require approval (comma-separated) [Bash,Write,Edit,MultiEdit]: ").strip()
    auto_input = input("  Auto-approve (comma-separated) [Read,Glob,Grep,LS]: ").strip()

    require_tools = [t.strip() for t in require_input.split(",")] if require_input else ["Bash", "Write", "Edit", "MultiEdit"]
    auto_tools = [t.strip() for t in auto_input.split(",")] if auto_input else ["Read", "Glob", "Grep", "LS"]

    # Step 4: Timeout
    timeout_input = input("\nStep 4: Seconds to wait before auto-denying [300]: ").strip()
    timeout = int(timeout_input) if timeout_input.isdigit() else 300

    # Step 5: Test round-trip
    print("\nStep 5: Testing round-trip — check Telegram and tap Approve or Deny...")
    msg_id = _send_test(token, chat_id, session_id="setup_test")
    if not msg_id:
        print("ERROR: Failed to send test message.")
        sys.exit(1)
    result = _poll_callback(token, chat_id, msg_id, "setup_test", timeout=60)
    print()
    if result is None:
        print("WARNING: Timed out. The system will still work, but verify Telegram is set up correctly.")
    else:
        print(f"  ✓ Test response received: {result}")

    # Step 6: Write config
    config = {
        "bot_token": token,
        "chat_id": chat_id,
        "poll_timeout_seconds": timeout,
        "auto_approve_tools": auto_tools,
        "require_approval_tools": require_tools,
    }
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"\n  ✓ Config saved to {CONFIG_PATH}")

    # Step 7: Patch settings.json
    print("\nStep 6: Installing hooks into ~/.claude/settings.json...")
    try:
        _patch_settings(HOOKS_DIR)
        print("  ✓ PreToolUse hook added")
        print("  ✓ Stop hook added")
    except Exception as e:
        print(f"  ERROR patching settings.json: {e}")
        print("  Add hooks manually — see README for JSON snippets.")
        sys.exit(1)

    print("\n=== Setup complete! ===")
    print("From now on, when Claude wants to run Bash/Write/Edit, you'll get a Telegram notification.")
    print("\nTip: To get notified when Claude is asking a question during a task,")
    print("     add this line to your project's CLAUDE.md:")
    print('     "When you need to pause and ask the user a question, end your message with [WAITING_FOR_INPUT]"')


if __name__ == "__main__":
    main()
