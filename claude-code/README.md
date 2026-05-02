# AgentGate — Claude Code Setup

Never let a Claude Code task stall because you stepped away from your laptop.

When Claude Code is running autonomously and needs your approval — to run a shell command, write a file, or ask a clarifying question — this tool intercepts it, shows a prompt in your terminal for **10 seconds**, then sends a **Telegram notification** to your phone. Tap to approve or deny, and Claude continues.

---

## How It Works

```
Claude wants to run a tool
         │
         ▼
Terminal prompt appears (10 seconds)
  ╭────────────────────────────────────╮
  │ Claude wants to run Bash           │
  │────────────────────────────────────│
  │  rm -rf dist && npm run build      │
  │────────────────────────────────────│
  │  Project: myproject                │
  ╰────────────────────────────────────╯
   ❯ Allow    Don't allow
  ← → · Enter to confirm · Telegram in 8s
         │
         ├─ Press Enter → Claude proceeds immediately
         ├─ Press Esc / Ctrl+C → Claude blocked
         └─ No response after 10s → Telegram notification sent
                    │
                    ├─ Tap ✅ Approve → Claude proceeds
                    ├─ Tap ❌ Deny → Claude blocked
                    └─ No response after 5 min → auto-denied
```

---

## Requirements

- macOS
- Python 3 (no pip installs — pure stdlib)
- A Telegram account
- Claude Code CLI

---

## Setup

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (e.g. `123456789:AAH...`)

### Step 2 — Run the Setup Wizard

```bash
cd claude-code
python3 setup.py
```

The wizard:
- Validates your bot token
- Auto-detects your Telegram chat ID
- Lets you configure which tools need approval
- Sends a test notification to verify everything works
- Writes config to `~/.claude/remote_approval.json`
- Registers hooks in `~/.claude/settings.json`

### Step 3 — Optional: Add to CLAUDE.md

To get notified when Claude asks a question mid-task, add to your project's `CLAUDE.md`:

```
When you need to pause and ask the user a question, end your message
with [WAITING_FOR_INPUT] so the remote notification system activates.
```

---

## File Structure

```
claude-code/
├── setup.py                  # One-time setup wizard
├── requirements.txt          # Empty — no dependencies
└── hooks/
    ├── pre_tool_use.py       # Intercepts tool calls
    ├── stop_hook.py          # Intercepts when Claude waits for input
    └── lib/
        ├── config.py         # Loads ~/.claude/remote_approval.json
        └── telegram.py       # Telegram API (urllib only)
```

---

## Enable / Disable

**Disable** — remove the hooks from `~/.claude/settings.json`, or:
```bash
rm ~/.claude/remote_approval.json
```

**Re-enable** — run `python3 setup.py` again.
