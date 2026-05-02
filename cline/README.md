# AgentGate — Cline Setup

Adds phone approval to the [Cline](https://github.com/cline/cline) VS Code extension.

When Cline needs your approval to run a command or use a tool, two things happen simultaneously:
- The **VS Code approval dialog** shows in Cline's panel (unchanged)
- A **Telegram notification** fires to your phone with ✅/❌ buttons

Whichever you respond to first wins.

---

## How It Works

```
Cline wants to run a tool
         │
         ├──────────────────────────────────────────────────┐
         ▼                                                  ▼
VS Code approval dialog                    Telegram notification sent
shows in Cline panel                       to your phone immediately
         │                                                  │
         └────────────────────┬───────────────────────────┘
                              │
               Whichever you respond to first:
               Click in VS Code  OR  tap on phone
                              │
                      Cline continues
```

This works because the install script patches Cline's `ask()` method to fire a Telegram watcher in parallel with the VS Code dialog. Both call the same internal `handleWebviewAskResponse()` function — whichever fires first resolves the approval.

---

## Requirements

- macOS
- Python 3 (no pip installs — pure stdlib)
- Node.js + npm
- Git
- VS Code with `code` CLI installed
- A Telegram account

---

## Setup

### Step 1 — Run the setup wizard

```bash
cd cline
python3 setup.py
```

The wizard:
1. Validates your Telegram bot token
2. Auto-detects your chat ID
3. Sends a test notification to verify everything works
4. Saves config to `~/.claude/remote_approval.json`
5. Automatically runs `install.sh` to build and install the extension

### Step 2 — Restart VS Code

Reload VS Code after install. Cline will now send Telegram notifications for every tool approval.

---

## File Structure

```
cline/
├── setup.py                        # One-time setup wizard (run this)
├── install.sh                      # Build + install script (called by setup.py)
├── TelegramNotificationService.ts  # New service added to Cline
└── index.patch                     # Patch for src/core/task/index.ts
```

---

## Updating

When Cline releases a new version, update the `CLINE_VERSION` pin in `install.sh` to the new tag, then rebuild:

```bash
CLINE_VERSION=v3.83.0 bash install.sh
```

If the patch fails (Cline's `index.ts` changed significantly), [open an issue](https://github.com/Shreyansh0508/agentgate/issues).

---

## Differences from Claude Code integration

| | Claude Code | Cline |
|---|---|---|
| **Per-tool filtering** | Configurable — only fires for tools in `require_approval_tools` | Fires for all tool approvals (`command`, `tool`, `browser_action_launch`, `use_mcp_server`) |
| **Terminal prompt** | 10s terminal prompt → then Telegram | No terminal prompt — Telegram fires immediately alongside VS Code dialog |
| **Response channels** | Terminal or Telegram | VS Code dialog or Telegram |

---

## Uninstall

```bash
cd cline
bash uninstall.sh
```

Reinstalls the official Cline from the VS Code marketplace and optionally removes the Telegram config and build directory.
