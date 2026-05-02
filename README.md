# AgentGate

Never let an AI coding task stall because you stepped away from your laptop.

AgentGate intercepts approval requests from AI coding tools and routes them to your phone via Telegram. You get a notification with full context — the tool name, the exact command or file, the project — tap ✅ or ❌, and the task continues. No laptop needed.

---

## Supported Tools

| Tool | Integration method | How approvals work |
|---|---|---|
| **Claude Code** (CLI) | Hook scripts in `~/.claude/settings.json` | Terminal prompt for 10s → then Telegram; both run simultaneously |
| **Cline** (VS Code extension) | Patched source built into a custom `.vsix` | VS Code dialog + Telegram fire at the same moment; first response wins |

---

## Quick Start

Each tool has its own independent setup — install only what you use.

### Claude Code CLI

```bash
git clone https://github.com/Shreyansh0508/agentgate
cd agentgate/claude-code
python3 setup.py
```

Registers `PreToolUse` and `Stop` hooks in Claude Code's settings. From then on, every tool call that needs approval triggers a terminal prompt followed by a Telegram notification if you don't respond within 10 seconds.

### Cline (VS Code extension)

```bash
git clone https://github.com/Shreyansh0508/agentgate   # skip if already cloned
cd agentgate/cline
python3 setup.py
```

Patches Cline's source, builds a custom `.vsix`, and installs it. From then on, every Cline approval fires both the VS Code dialog and a Telegram notification simultaneously.

> If you use both tools, they share the same config file (`~/.claude/remote_approval.json`) — same bot, same phone. You only set up Telegram once.

---

## How Each Integration Works

### Claude Code — Hook-based

Claude Code has a built-in hook system. AgentGate registers two hook scripts:

- **`PreToolUse` hook** — called before every tool execution. The script reads the tool name and input, decides whether approval is needed, and outputs an `allow` or `deny` JSON decision. While waiting, it shows an interactive terminal UI and simultaneously fires a Telegram notification. The terminal and Telegram race — whichever you respond to first resolves the decision.

- **`Stop` hook** — called when Claude finishes a turn. If Claude's last message ends with `[WAITING_FOR_INPUT]`, the hook sends the question to Telegram and waits for a text reply. When you reply, the answer is injected back into Claude's context and the task continues — Claude never fully stops.

No changes are made to Claude Code itself. The hooks are plain Python scripts using only the standard library.

### Cline — Source Patch

Cline is open source. AgentGate patches it at the source level:

- A new `TelegramNotificationService.ts` is added to Cline's source. It handles the full Telegram lifecycle: send notification, poll for a button tap, answer the callback, edit the message to show the outcome.

- `src/core/task/index.ts` is patched at the `ask()` method — the central point where Cline pauses and waits for approval. The patch launches the Telegram watcher in parallel with the existing VS Code dialog. Both call the same internal `handleWebviewAskResponse()` function. The first response resolves the approval; the second is a no-op.

The patched source is built into a `.vsix` and installed as a VS Code extension, replacing the official Cline.

---

## Repository Structure

```
agentgate/
│
├── claude-code/               # Claude Code CLI integration
│   ├── setup.py               # One-time wizard: Telegram config + hook registration
│   ├── uninstall.py           # Removes hooks from ~/.claude/settings.json
│   ├── requirements.txt       # Empty — no pip dependencies
│   ├── README.md              # Full guide with architecture details
│   └── hooks/
│       ├── pre_tool_use.py    # PreToolUse hook: terminal + Telegram race
│       ├── stop_hook.py       # Stop hook: question relay via Telegram
│       └── lib/
│           ├── config.py      # Reads ~/.claude/remote_approval.json
│           └── telegram.py    # Telegram Bot API client (urllib only)
│
├── cline/                     # Cline VS Code extension integration
│   ├── setup.py               # One-time wizard: Telegram config + build + install
│   ├── install.sh             # Build-only: clone → patch → build → install .vsix
│   ├── uninstall.sh           # Reinstalls official Cline from marketplace
│   ├── TelegramNotificationService.ts  # New service injected into Cline source
│   ├── index.patch            # Git patch for src/core/task/index.ts
│   └── README.md              # Full guide with architecture details
│
└── README.md
```

---

## Detailed Setup Guides

- [Claude Code — full guide with architecture →](claude-code/README.md)
- [Cline — full guide with architecture →](cline/README.md)
