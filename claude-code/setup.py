#!/usr/bin/env python3
"""One-time setup wizard for Claude Code Remote Approval System."""
import json
import os
import stat
import sys

SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks")

# Import shared Telegram utilities from the hooks lib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hooks.lib import telegram as tg


def _send_test(token, chat_id, session_id="setup_test"):
    text = "<b>Test: Claude wants to run <code>Bash</code></b>\n\n<code>echo hello world</code>\n\nProject: <code>test_project</code>"
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
            {"text": "❌ Deny",    "callback_data": f"deny:{session_id}"},
        ]]
    }
    return tg.send_message(token, chat_id, text, reply_markup)


def _patch_settings(hooks_dir):
    hook_py = sys.executable  # same python that's running setup.py
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
    else:
        settings = {}

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
    try:
        timeout = max(30, int(timeout_input))
    except ValueError:
        timeout = 300

    # Step 5: Test round-trip
    print("\nStep 5: Testing round-trip — check Telegram and tap Approve or Deny...")
    msg_id = _send_test(token, chat_id)
    if not msg_id:
        print("ERROR: Failed to send test message.")
        sys.exit(1)
    result = tg.poll_for_callback(token, chat_id, msg_id, "setup_test", timeout=60)
    print()
    if result is None:
        print("WARNING: Timed out. The system will still work, but verify Telegram is set up correctly.")
    else:
        decision, cb_id = result
        tg.answer_callback(token, cb_id)
        print(f"  ✓ Test response received: {decision}")

    # Step 6: Write config
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
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
