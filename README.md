# Claude Code Remote Approval

Never let a Claude task stall because you stepped away from your laptop.

When Claude is running autonomously and needs your approval — to run a shell command, write a file, or ask a clarifying question — this tool intercepts it, shows a prompt in your terminal, and if you don't respond within 10 seconds, sends a Telegram notification to your phone. You approve or deny with a tap, and Claude continues.

---

## How It Works

```
Claude wants to run a tool
         │
         ▼
Terminal prompt appears (10 seconds)
  ╭─────────────────────────────────╮
  │ Claude wants to run Bash        │
  │─────────────────────────────────│
  │  rm -rf dist && npm run build   │
  │─────────────────────────────────│
  │  Project: myproject             │
  ╰─────────────────────────────────╯
   ❯ Allow    Don't allow
  ← → to switch · Enter to confirm · Telegram in 8s
         │
         ├─ Press Enter → Claude proceeds immediately
         ├─ Press Esc / Ctrl+C → Claude blocked
         │
         └─ No response after 10s → Telegram notification sent
                    │
                    ├─ Tap ✅ Approve → Claude proceeds
                    ├─ Tap ❌ Deny → Claude blocked
                    └─ No response after 5 min → auto-denied
```

### Two hook types

**`PreToolUse`** — fires before every tool call (Bash, Write, Edit, etc.)
- Auto-approves safe tools: `Read`, `Glob`, `Grep`, `LS`
- Asks for approval on risky tools: `Bash`, `Write`, `Edit`, `MultiEdit`

**`Stop`** — fires when Claude asks a question and waits for your reply
- Activates only when Claude ends its message with `[WAITING_FOR_INPUT]`
- Sends the question to your phone as a Telegram message
- You reply in Telegram, and Claude continues with your answer injected

---

## Requirements

- macOS
- Python 3 (no pip installs needed — pure stdlib)
- A Telegram account
- Claude Code CLI

---

## Setup

### Step 1 — Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token it gives you (looks like `123456789:AAH...`)

### Step 2 — Run the Setup Wizard

```bash
cd /path/to/prompt_tool
python3 setup.py
```

The wizard will:
- Validate your bot token
- Auto-detect your Telegram chat ID (just send any message to your bot when prompted)
- Let you configure which tools require approval
- Send a test notification to verify the full round-trip works
- Write the config to `~/.claude/remote_approval.json`
- Automatically add the hooks to `~/.claude/settings.json`

### Step 3 — Add to your project's CLAUDE.md (optional)

To get notified when Claude asks a question mid-task, add this line to your project's `CLAUDE.md`:

```
When you need to pause and ask the user a question during a task,
end your message with [WAITING_FOR_INPUT] so the remote notification system activates.
```

---

## File Structure

```
prompt_tool/
├── setup.py                  # One-time setup wizard
├── requirements.txt          # Empty — no dependencies
└── hooks/
    ├── pre_tool_use.py       # Intercepts tool calls (Bash, Write, Edit)
    ├── stop_hook.py          # Intercepts when Claude waits for input
    └── lib/
        ├── config.py         # Loads ~/.claude/remote_approval.json
        └── telegram.py       # Telegram API calls (urllib only)
```

### Config file — `~/.claude/remote_approval.json`

Created automatically by `setup.py`. Stored with `chmod 600` (owner-read only).

```json
{
  "bot_token": "your_bot_token",
  "chat_id": "your_chat_id",
  "poll_timeout_seconds": 300,
  "auto_approve_tools": ["Read", "Glob", "Grep", "LS"],
  "require_approval_tools": ["Bash", "Write", "Edit", "MultiEdit"]
}
```

| Field | Description |
|---|---|
| `bot_token` | Your Telegram bot token from BotFather |
| `chat_id` | Your Telegram user ID (auto-detected during setup) |
| `poll_timeout_seconds` | How long to wait for phone response before auto-denying (default 300s) |
| `auto_approve_tools` | Tools that never require approval |
| `require_approval_tools` | Tools that always require approval |

---

## Enabling / Disabling

The hooks are registered in `~/.claude/settings.json` under `"PreToolUse"` and `"Stop"`.

**Disable** — remove those two entries from `settings.json`, or delete the config:
```bash
rm ~/.claude/remote_approval.json
```
With no config file, the hooks exit silently and Claude runs without any approval prompts.

**Re-enable** — run `python3 setup.py` again to restore the config and re-register the hooks.

---

## Corporate / Proxy Networks

If you're behind a corporate HTTPS proxy with a custom CA certificate, the tool handles it automatically. It tries a verified SSL connection first, then falls back to an unverified connection if the corporate CA blocks it. Your bot token (the secret) is protected by Telegram's own infrastructure regardless of local SSL inspection.

---

## Security Notes

- The bot token is stored in `~/.claude/remote_approval.json` with `chmod 600`
- Never commit that file — it is not inside the project directory
- If your bot token is ever exposed, revoke it immediately via `@BotFather → /mybots → Revoke token`
- On timeout (no response from phone), the tool **denies** the action by default — fail safe
- On any hook error, the tool **denies** the action by default — fail safe
