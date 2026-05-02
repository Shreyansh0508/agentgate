# AgentGate

Never let an AI coding task stall because you stepped away from your laptop.

AgentGate intercepts approval requests from AI coding tools and routes them to your phone via Telegram. You get a notification with full context, tap to approve or deny, and the task continues — no laptop needed.

---

## Supported Tools

| Tool | How it works |
|---|---|
| **Claude Code** (CLI) | Hook intercepts tool calls · terminal prompt for 10s · then Telegram |
| **Cline** (VS Code extension) | VS Code dialog shows normally · Telegram fires simultaneously · first response wins |

---

## Quick Start

Each tool has its own independent setup — install only what you use.

### Claude Code CLI

```bash
git clone https://github.com/Shreyansh0508/agentgate
cd agentgate/claude-code
python3 setup.py
```

This sets up the Telegram bot and registers hooks for Claude Code CLI.

### Cline (VS Code extension)

```bash
git clone https://github.com/Shreyansh0508/agentgate  # skip if already cloned
cd agentgate/cline
python3 setup.py
```

This sets up the Telegram bot and builds + installs the patched Cline extension.

> Both setups write to the same config file (`~/.claude/remote_approval.json`), so if you use both tools, the bot token and chat ID are shared automatically.

---

## Structure

```
agentgate/
├── claude-code/        # Claude Code CLI integration
│   ├── setup.py        # One-time wizard
│   ├── hooks/          # PreToolUse + Stop hooks
│   └── README.md       # Full Claude Code setup guide
│
├── cline/              # Cline VS Code extension integration
│   ├── setup.py        # One-time wizard (Telegram config + build + install)
│   ├── install.sh      # Build-only script (re-run to update)
│   ├── TelegramNotificationService.ts
│   ├── index.patch
│   └── README.md       # Full Cline setup guide
│
└── README.md
```

---

## Detailed Setup Guides

- [Claude Code →](claude-code/README.md)
- [Cline →](cline/README.md)
