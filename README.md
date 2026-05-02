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

### 1. Create a Telegram Bot (shared by both tools)

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Copy the bot token it gives you

### 2. Run the setup wizard

```bash
git clone https://github.com/Shreyansh0508/agentgate
cd agentgate/claude-code
python3 setup.py
```

This sets up the Telegram bot and registers hooks for Claude Code CLI.

### 3. Set up Cline (optional)

```bash
cd agentgate/cline
bash install.sh
```

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
│   ├── install.sh      # Clones Cline, patches it, installs .vsix
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
