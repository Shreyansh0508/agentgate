import json
import os
import ssl
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
    result = _api(token, "sendMessage", payload)
    return result["result"]["message_id"]


def edit_message_text(token: str, chat_id: str, message_id: int, text: str) -> None:
    _api(token, "editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    })


def answer_callback(token: str, callback_query_id: str) -> None:
    _api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})


def poll_for_callback(
    token: str,
    chat_id: str,
    message_id: int,
    session_id: str,
    timeout: int,
) -> tuple[str, str] | None:
    """Returns ("approve"|"deny", callback_query_id) or None on timeout."""
    offset = 0
    deadline = time.time() + timeout
    # Drain old updates first to get a clean offset
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
            cq = update.get("callback_query")
            if not cq:
                continue
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
