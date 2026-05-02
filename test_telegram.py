#!/usr/bin/env python3
"""Test script for Telegram integration."""
import json
import os
import ssl
import sys
import time
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
_SAP_CERT = os.path.expanduser("~/.claude/certs/SAPNetCA_G2.pem")


def _ssl_context():
    """Create SSL context with optional SAP cert."""
    ctx = ssl.create_default_context()
    if os.path.exists(_SAP_CERT):
        ctx.load_verify_locations(_SAP_CERT)
    return ctx


def _api(token, method, payload=None):
    """Call Telegram Bot API."""
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


def test_bot_connection(token):
    """Test if bot token is valid."""
    print("Testing bot connection...")
    r = _api(token, "getMe")
    if r.get("ok"):
        bot_info = r["result"]
        print(f"  ✓ Connected to bot: @{bot_info['username']}")
        print(f"    Bot ID: {bot_info['id']}")
        print(f"    Bot Name: {bot_info.get('first_name', 'N/A')}")
        return True
    else:
        print(f"  ✗ Failed to connect: {r.get('error', 'Unknown error')}")
        return False


def send_test_message(token, chat_id):
    """Send a test message with approval buttons."""
    print("\nSending test message...")
    session_id = f"test_{int(time.time())}"
    payload = {
        "chat_id": chat_id,
        "text": (
            "<b>🧪 Test Message from AgentGate</b>\n\n"
            "<code>This is a test of the Telegram integration.</code>\n\n"
            "If you see this message with buttons below, the integration is working! ✅\n\n"
            "Project: <code>agentgate_test</code>"
        ),
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
                {"text": "❌ Deny", "callback_data": f"deny:{session_id}"},
            ]]
        }
    }
    r = _api(token, "sendMessage", payload)
    if r.get("ok"):
        msg_id = r["result"]["message_id"]
        print(f"  ✓ Test message sent (message_id: {msg_id})")
        return msg_id, session_id
    else:
        print(f"  ✗ Failed to send message: {r.get('error', 'Unknown error')}")
        return None, None


def wait_for_response(token, chat_id, message_id, session_id, timeout=30):
    """Wait for user to click approve/deny button."""
    print(f"\nWaiting for your response (timeout: {timeout}s)...")
    print("  (Check Telegram and click Approve or Deny)")
    
    # Get current offset
    offset = 0
    r = _api(token, "getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    for u in r.get("result", []):
        offset = u["update_id"] + 1

    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        r = _api(token, "getUpdates", {"offset": offset, "timeout": min(10, max(1, remaining))})
        
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
                action = "APPROVED" if cb_data.startswith("approve") else "DENIED"
                print(f"\n  ✓ Response received: {action}")
                return action
        
        sys.stdout.write(".")
        sys.stdout.flush()
    
    print("\n  ⚠ Timeout - no response received")
    return None


def main():
    print("=" * 50)
    print("AgentGate Telegram Integration Test")
    print("=" * 50)
    
    # Load config
    if not os.path.exists(CONFIG_PATH):
        print(f"\n✗ Config file not found: {CONFIG_PATH}")
        print("  Run setup.py first to configure the integration.")
        sys.exit(1)
    
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    
    token = config.get("bot_token")
    chat_id = config.get("chat_id")
    
    if not token or not chat_id:
        print("\n✗ Invalid config: missing bot_token or chat_id")
        sys.exit(1)
    
    print(f"\nConfig loaded from: {CONFIG_PATH}")
    print(f"  Chat ID: {chat_id}")
    print(f"  Auto-approve tools: {', '.join(config.get('auto_approve_tools', []))}")
    print(f"  Require approval tools: {', '.join(config.get('require_approval_tools', []))}")
    print(f"  Poll timeout: {config.get('poll_timeout_seconds', 300)}s")
    
    # Test 1: Bot connection
    print("\n" + "-" * 50)
    print("Test 1: Bot Connection")
    print("-" * 50)
    if not test_bot_connection(token):
        sys.exit(1)
    
    # Test 2: Send message
    print("\n" + "-" * 50)
    print("Test 2: Send Test Message")
    print("-" * 50)
    msg_id, session_id = send_test_message(token, chat_id)
    if not msg_id:
        sys.exit(1)
    
    # Test 3: Wait for response (optional)
    print("\n" + "-" * 50)
    print("Test 3: Wait for Response")
    print("-" * 50)
    response = wait_for_response(token, chat_id, msg_id, session_id, timeout=30)
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    print("  ✓ Bot connection: PASSED")
    print("  ✓ Message sending: PASSED")
    if response:
        print(f"  ✓ Response handling: PASSED ({response})")
    else:
        print("  ⚠ Response handling: TIMEOUT (but message was sent successfully)")
    
    print("\n✅ Telegram integration is working!")
    print("\nYou can now use AgentGate with Claude Code or Cline.")


if __name__ == "__main__":
    main()