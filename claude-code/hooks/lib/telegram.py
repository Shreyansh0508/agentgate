import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.parse

_SAP_CERT = os.path.expanduser("~/.claude/certs/SAPNetCA_G2.pem")


def _ssl_context():
    ctx = ssl.create_default_context()
    if os.path.exists(_SAP_CERT):
        ctx.load_verify_locations(_SAP_CERT)
    return ctx


def _api(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    last_err = None
    for ctx in (_ssl_context(), ssl._create_unverified_context()):
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(str(last_err))


def send_message(token: str, chat_id: str, text: str, reply_markup: dict | None = None) -> int:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    last_err = None
    for attempt in range(3):
        try:
            result = _api(token, "sendMessage", payload)
            return result["result"]["message_id"]
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s backoff
    raise RuntimeError(f"send_message failed after 3 attempts: {last_err}")


def edit_message_text(token: str, chat_id: str, message_id: int, text: str) -> None:
    _api(token, "editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    })


def answer_callback(token: str, callback_query_id: str) -> None:
    _api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})


def validate_token(token: str) -> str | None:
    """Returns the bot username if the token is valid, else None."""
    try:
        r = _api(token, "getMe", {})
        if r.get("ok"):
            return r["result"]["username"]
    except Exception:
        pass
    return None


def get_chat_id(token: str, timeout: int = 120) -> tuple[str, str] | tuple[None, None]:
    """
    Polls getUpdates until the first message arrives, returning (chat_id, first_name).
    Prints dots to stdout as progress. Returns (None, None) on timeout.
    """
    deadline = time.time() + timeout
    offset = 0
    while time.time() < deadline:
        try:
            r = _api(token, "getUpdates", {"offset": offset, "timeout": 10})
        except Exception:
            time.sleep(2)
            continue
        for update in r.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message")
            if msg:
                return str(msg["chat"]["id"]), msg["chat"].get("first_name", "")
        sys.stdout.write(".")
        sys.stdout.flush()
    return None, None


def poll_for_callback(
    token: str,
    chat_id: str,
    message_id: int,
    session_id: str,
    timeout: int,
    stop_event=None,
) -> tuple[str, str] | None:
    """Returns ("approve"|"deny", callback_query_id) or None on timeout/stop."""
    offset = 0
    deadline = time.time() + timeout
    data = _api(token, "getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    for u in data.get("result", []):
        offset = u["update_id"] + 1

    while time.time() < deadline:
        if stop_event and stop_event.is_set():
            return None
        remaining = int(deadline - time.time())
        poll_secs = min(5, max(1, remaining))  # short chunks so stop_event is checked often
        try:
            data = _api(token, "getUpdates", {"offset": offset, "timeout": poll_secs})
        except Exception:
            time.sleep(2)
            continue
        for update in data.get("result", []):
            offset = update["update_id"] + 1
            cq = update.get("callback_query")
            if not cq:
                continue
            if str(cq.get("from", {}).get("id")) != str(chat_id):
                continue  # reject callbacks from users other than the configured owner
            cb_data = cq.get("data", "")
            cb_msg_id = cq.get("message", {}).get("message_id")
            if cb_msg_id != message_id:
                continue
            if cb_data in (f"approve:{session_id}", f"deny:{session_id}"):
                decision = "approve" if cb_data.startswith("approve") else "deny"
                return decision, cq["id"]
    return None


def poll_for_text_reply(
    token: str,
    chat_id: str,
    reply_to_message_id: int,
    timeout: int,
) -> str | None:
    """Waits for a text message that is a reply to reply_to_message_id. Returns text or None."""
    offset = 0
    deadline = time.time() + timeout
    data = _api(token, "getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    for u in data.get("result", []):
        offset = u["update_id"] + 1

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        poll_secs = min(25, max(1, remaining))
        try:
            data = _api(token, "getUpdates", {"offset": offset, "timeout": poll_secs})
        except Exception:
            time.sleep(2)
            continue
        for update in data.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message")
            if not msg:
                continue
            if str(msg.get("chat", {}).get("id")) != str(chat_id):
                continue
            reply_to = msg.get("reply_to_message", {})
            if reply_to.get("message_id") == reply_to_message_id:
                return msg.get("text", "")
    return None
