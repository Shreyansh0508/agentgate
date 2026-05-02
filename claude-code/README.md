# AgentGate — Claude Code Integration

Never let a Claude Code task stall because you stepped away from your laptop.

When Claude Code runs autonomously and needs your approval — to execute a shell command, write a file, or ask a clarifying question — AgentGate intercepts it. You get **10 seconds** to respond right in your terminal. If you don't, a **Telegram notification** fires to your phone with full context and ✅/❌ buttons. Tap to decide, and Claude continues — no laptop needed.

---

## How It Works

### The Approval Flow

```
Claude Code wants to run a tool (e.g. Bash)
                │
                ▼
   ┌─────────────────────────────────────┐
   │  Terminal prompt appears (10s)      │
   │                                     │
   │  ╭───────────────────────────────╮  │
   │  │ Claude wants to run Bash      │  │
   │  │───────────────────────────────│  │
   │  │  rm -rf dist && npm run build │  │
   │  │───────────────────────────────│  │
   │  │  Project: myproject           │  │
   │  ╰───────────────────────────────╯  │
   │   ❯ Allow    Don't allow           │
   │  ← → · Enter to confirm · 8s left  │
   └─────────────────────────────────────┘
                │
    ┌───────────┼───────────────────────────┐
    │           │                           │
    ▼           ▼                           ▼
Press Enter  Press Esc          No response after 10s
(Allow)      (Deny)                        │
    │           │                           ▼
    │           │           Telegram notification sent to phone
    │           │            ┌─────────────────────────────┐
    │           │            │ Claude wants to run Bash     │
    │           │            │ rm -rf dist && npm run build │
    │           │            │ Project: myproject           │
    │           │            │                             │
    │           │            │  [✅ Approve]  [❌ Deny]    │
    │           │            └─────────────────────────────┘
    │           │                           │
    │           │               ┌───────────┼────────────┐
    │           │               ▼           ▼            ▼
    │           │           Tap Approve  Tap Deny    No response
    │           │               │           │        after 5 min
    ▼           ▼               ▼           ▼            ▼
  Claude     Claude           Claude     Claude       Claude
 proceeds   blocked          proceeds   blocked      blocked
```

Both the terminal and Telegram run **simultaneously** from the moment the tool request arrives. Whichever you respond to first wins — the other is cancelled.

### Under the Hood — The Hook System

Claude Code has a built-in hook system that lets you inject scripts into its execution lifecycle. AgentGate registers two hooks in `~/.claude/settings.json`:

**`PreToolUse` hook** — fires before every tool call:
```json
{
  "PreToolUse": [{
    "matcher": "",
    "hooks": [{
      "type": "command",
      "command": "python3 /path/to/hooks/pre_tool_use.py",
      "timeout": 310
    }]
  }]
}
```
Claude Code passes the hook script a JSON payload via stdin containing the tool name, tool input, session ID, and working directory. The hook outputs a JSON decision back to Claude Code:
- `{"permissionDecision": "allow"}` → Claude proceeds
- `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` → Claude is blocked
- No output / exit 0 → Claude Code uses its own default behavior

**`Stop` hook** — fires when Claude finishes a turn (is about to stop and wait):
```json
{
  "Stop": [{
    "matcher": "",
    "hooks": [{
      "type": "command",
      "command": "python3 /path/to/hooks/stop_hook.py",
      "timeout": 310
    }]
  }]
}
```
The Stop hook receives the path to the session transcript. If Claude's last message contains `[WAITING_FOR_INPUT]`, the hook sends a Telegram notification and waits for a text reply. When you reply, it outputs:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "decision": "block",
    "additionalContext": "User replied via phone: 'your reply here'"
  }
}
```
The `"decision": "block"` keeps the agentic loop alive, and `additionalContext` injects your reply into Claude's next context window — so Claude reads your answer and continues the task.

### What Happens Inside `pre_tool_use.py`

```
stdin JSON arrives
        │
        ▼
  Load config from ~/.claude/remote_approval.json
        │
        ├─ Tool in auto_approve_tools? → output allow, exit immediately
        ├─ Tool NOT in require_approval_tools? → exit 0 (Claude decides)
        │
        ▼
  Spawn two threads simultaneously:
  ┌─────────────────────┐    ┌──────────────────────────────┐
  │   Terminal thread   │    │       Telegram thread        │
  │                     │    │                              │
  │  Open /dev/tty      │    │  send_message() with         │
  │  Render box UI      │    │  inline ✅/❌ buttons        │
  │  Arrow key nav      │    │                              │
  │  10s countdown      │    │  poll_for_callback() in 5s   │
  │                     │    │  chunks, checking stop_event │
  └─────────────────────┘    └──────────────────────────────┘
           │                              │
           └──────────┬───────────────────┘
                      │
              First thread to get a response:
              sets threading.Event (done)
              acquires threading.Lock
              writes decision + source
                      │
              Other thread sees done.is_set()
              and exits its loop
                      │
        done.wait(timeout + 15s)
        t_telegram.join(timeout=5s)   ← ensures msg_id is written
                      │
        Edit Telegram message to show outcome
        Output allow/deny JSON to stdout
        sys.exit(0)
```

### Tool Filtering

You control exactly which tools trigger the approval flow:

| List | Default tools | Behaviour |
|---|---|---|
| `require_approval_tools` | `Bash`, `Write`, `Edit`, `MultiEdit` | Always triggers terminal + Telegram |
| `auto_approve_tools` | `Read`, `Glob`, `Grep`, `LS` | Always allowed instantly, no prompt |
| Everything else | — | Claude Code uses its own dialog |

Set `"require_approval_tools": ["*"]` to require approval for every tool.

### The Telegram Bot

The bot token and chat ID are stored in `~/.claude/remote_approval.json` (chmod 600). All Telegram API calls go through `urllib` — no third-party packages installed. The library:

- Retries `sendMessage` up to 3 times with exponential backoff
- Falls back to `rejectUnauthorized: false` TLS only on certificate errors (for corporate proxies)
- Filters all incoming callbacks by `chat_id` so only your account can approve
- Drains pending updates before each poll so stale callbacks from prior sessions never replay

### Logging

Every approval request, decision, and error is appended to `~/.agentgate/agentgate.log`:
```
2026-05-03 14:22:01 [pre_tool_use] request: tool=Bash session=abc123 project=myapp
2026-05-03 14:22:14 [pre_tool_use] approved via telegram
```

---

## Requirements

- macOS
- Python 3.10+ (no pip installs — pure stdlib)
- A Telegram account
- Claude Code CLI installed and configured

---

## Setup

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:AAHxxx...`)

You only need to do this once. The same bot works for both Claude Code and Cline.

### Step 2 — Run the Setup Wizard

```bash
cd claude-code
python3 setup.py
```

The wizard walks you through:
1. **Token validation** — connects to the bot to verify the token is valid
2. **Chat ID detection** — asks you to send any message to your bot; auto-reads your chat ID from that message
3. **Tool configuration** — set which tools require approval (or keep the defaults)
4. **Timeout configuration** — how long to wait before auto-denying (default: 300s)
5. **Round-trip test** — sends a real approval notification to your phone; tap Approve or Deny to confirm everything works end-to-end
6. **Config write** — saves `~/.claude/remote_approval.json` with `chmod 600`
7. **Hook registration** — patches `~/.claude/settings.json` with the `PreToolUse` and `Stop` hook entries

### Step 3 — Optional: Enable Question Notifications

To get notified when Claude pauses mid-task to ask you something, add this to your project's `CLAUDE.md`:

```
When you need to pause and ask the user a question during a task,
end your message with [WAITING_FOR_INPUT] so the remote notification
system activates and delivers your question to the user's phone.
```

Claude will append `[WAITING_FOR_INPUT]` to any message where it's genuinely blocked waiting for your input. The Stop hook detects this, sends the question to your Telegram, waits for your reply, and injects it back into Claude's context so the task continues automatically.

---

## File Structure

```
claude-code/
├── setup.py              # One-time setup wizard
├── uninstall.py          # Removes hooks and optionally config
├── requirements.txt      # Empty — no pip dependencies
└── hooks/
    ├── pre_tool_use.py   # Intercepts every tool call before execution
    ├── stop_hook.py      # Intercepts when Claude finishes a turn
    └── lib/
        ├── config.py     # Loads and queries ~/.claude/remote_approval.json
        └── telegram.py   # Full Telegram Bot API client (urllib only)
```

**Config file** (`~/.claude/remote_approval.json`, created by setup.py):
```json
{
  "bot_token": "123456789:AAH...",
  "chat_id": "987654321",
  "poll_timeout_seconds": 300,
  "auto_approve_tools": ["Read", "Glob", "Grep", "LS"],
  "require_approval_tools": ["Bash", "Write", "Edit", "MultiEdit"]
}
```

---

## Uninstall

```bash
cd claude-code
python3 uninstall.py
```

Removes the `PreToolUse` and `Stop` hooks from `~/.claude/settings.json`. Detects AgentGate hooks by script name so it works regardless of where the repo was cloned. Optionally deletes the config file.

---

## Enable / Disable

**Disable temporarily** — delete the config file (hooks will deny all tool calls with an error message, which makes the issue obvious):
```bash
rm ~/.claude/remote_approval.json
```

**Disable cleanly** — run `python3 uninstall.py` to remove the hooks entirely. Claude Code falls back to its own built-in approval dialogs.

**Re-enable** — run `python3 setup.py` again.
