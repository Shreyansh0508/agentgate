#!/usr/bin/env python3
"""One-time setup wizard for AgentGate — Cline integration."""
import json
import os
import ssl
import stat
import subprocess
import sys
import time
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_SAP_CERT = os.path.expanduser("~/.claude/certs/SAPNetCA_G2.pem")


def _ssl_context():
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
        "text": "<b>Test: Cline wants to run a command</b>\n\n<code>npm run build</code>\n\nProject: <code>test_project</code>",
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


def main():
    print("=== AgentGate — Cline Setup ===\n")

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

    # Step 3: Test round-trip
    print("Step 3: Testing round-trip — check Telegram and tap Approve or Deny...")
    msg_id = _send_test(token, chat_id, session_id="cline_setup_test")
    if not msg_id:
        print("ERROR: Failed to send test message.")
        sys.exit(1)
    result = _poll_callback(token, chat_id, msg_id, "cline_setup_test", timeout=60)
    print()
    if result is None:
        print("WARNING: Timed out. The system will still work, but verify Telegram is set up correctly.")
    else:
        print(f"  ✓ Test response received: {result}\n")

    # Step 4: Write config (shared with Claude Code if also installed)
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    # Merge with existing config if present (preserves Claude Code settings)
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    config["bot_token"] = token
    config["chat_id"] = chat_id
    config.setdefault("poll_timeout_seconds", 300)
    config.setdefault("auto_approve_tools", ["Read", "Glob", "Grep", "LS"])
    config.setdefault("require_approval_tools", ["Bash", "Write", "Edit", "MultiEdit"])

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"  ✓ Config saved to {CONFIG_PATH}")

    # Step 5: Build and install Cline
    print("\nStep 4: Building and installing patched Cline extension...")
    install_sh = os.path.join(SCRIPT_DIR, "install.sh")
    result = subprocess.run(["bash", install_sh], cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("\nERROR: install.sh failed. See output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
