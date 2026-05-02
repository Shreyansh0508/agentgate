#!/usr/bin/env python3
"""One-time setup wizard for AgentGate — Cline integration."""
import json
import os
import stat
import subprocess
import sys

CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import shared Telegram utilities from the claude-code hooks lib
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "claude-code"))
from hooks.lib import telegram as tg


def _send_test(token, chat_id, session_id="cline_setup_test"):
    text = "<b>Test: Cline wants to run a command</b>\n\n<code>npm run build</code>\n\nProject: <code>test_project</code>"
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
            {"text": "❌ Deny",    "callback_data": f"deny:{session_id}"},
        ]]
    }
    return tg.send_message(token, chat_id, text, reply_markup)


def main():
    print("=== AgentGate — Cline Setup ===\n")

    # Step 1: Bot token
    print("Step 1: Create a Telegram Bot")
    print("  1. Open Telegram → search @BotFather")
    print("  2. Send /newbot and follow prompts")
    print("  3. Copy the token it gives you\n")
    token = input("Enter your bot token: ").strip()
    bot_name = tg.validate_token(token)
    if not bot_name:
        print("ERROR: Could not connect to Telegram with that token. Check and try again.")
        sys.exit(1)
    print(f"  ✓ Connected to bot: @{bot_name}\n")

    # Step 2: Chat ID
    print("Step 2: Get your Chat ID")
    print("  Waiting for you to send a message to your bot in Telegram...")
    print("  (Open Telegram, find your bot, send it any message like 'hello')")
    chat_id, first_name = tg.get_chat_id(token)
    print()
    if not chat_id:
        print("ERROR: Timed out waiting for a message. Make sure you sent a message to the bot.")
        sys.exit(1)
    print(f"  ✓ Chat ID: {chat_id} (from: {first_name})\n")

    # Step 3: Test round-trip
    print("Step 3: Testing round-trip — check Telegram and tap Approve or Deny...")
    msg_id = _send_test(token, chat_id)
    if not msg_id:
        print("ERROR: Failed to send test message.")
        sys.exit(1)
    result = tg.poll_for_callback(token, chat_id, msg_id, "cline_setup_test", timeout=60)
    print()
    if result is None:
        print("WARNING: Timed out. The system will still work, but verify Telegram is set up correctly.")
    else:
        decision, cb_id = result
        tg.answer_callback(token, cb_id)
        print(f"  ✓ Test response received: {decision}\n")

    # Step 4: Write config (merges with existing if claude-code is also set up)
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
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
