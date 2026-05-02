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
- Node.js + npm
- Git
- VS Code with `code` CLI installed
- A Telegram account + bot token (from the Claude Code setup)

---

## Setup

### Step 1 — Run Claude Code setup first

The Telegram bot config is shared between Claude Code and Cline. If you haven't set it up yet:

```bash
cd ../claude-code
python3 setup.py
```

### Step 2 — Run the Cline installer

```bash
cd cline
bash install.sh
```

The installer:
1. Clones latest Cline from GitHub
2. Copies `TelegramNotificationService.ts` into the source
3. Applies `index.patch` to wire in the parallel watcher
4. Builds the extension (`npm install` + `npm run package`)
5. Installs the `.vsix` directly into VS Code

### Step 3 — Restart VS Code

Reload VS Code after install. Cline will now send Telegram notifications for every tool approval.

---

## File Structure

```
cline/
├── install.sh                      # Automated build + install script
├── TelegramNotificationService.ts  # New service added to Cline
└── index.patch                     # Patch for src/core/task/index.ts
```

---

## Updating

When Cline releases a new version, just run `install.sh` again — it pulls the latest Cline and re-applies the patch.

If the patch fails (Cline's `index.ts` changed significantly), [open an issue](https://github.com/Shreyansh0508/agentgate/issues).

---

## Uninstall

Reinstall the official Cline extension from the VS Code marketplace:

```
Cmd+Shift+X → search "Cline" → Install
```
