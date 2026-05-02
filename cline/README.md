# AgentGate — Cline Integration

Never let a Cline task stall because you stepped away from your laptop.

When Cline needs your approval to run a command or use a tool, two things happen **at the same moment**:
- The **VS Code approval dialog** appears in Cline's panel as normal
- A **Telegram notification** fires to your phone with ✅/❌ buttons

You can respond from either place. Whichever you tap first wins — the other is cancelled automatically.

---

## How It Works

### The Approval Flow

```
Cline wants to run a tool (e.g. a shell command)
                │
                ▼
   ask() is called inside Cline's task engine
                │
    ┌───────────┴────────────────────────────────┐
    │                                            │
    ▼                                            ▼
VS Code approval dialog                 Telegram notification
appears in Cline's sidebar              sent to your phone
                                         immediately
  ┌──────────────────────────┐      ┌─────────────────────────┐
  │ Cline wants to run:      │      │ Cline wants to run       │
  │ > npm run build          │      │ command                  │
  │                          │      │ npm run build            │
  │  [Approve]  [Reject]     │      │ Project: myapp           │
  └──────────────────────────┘      │                         │
                                    │  [✅ Approve] [❌ Deny]  │
                                    └─────────────────────────┘
    │                                            │
    └──────────────────┬─────────────────────────┘
                       │
         Whichever you respond to first:
         click in VS Code  OR  tap on phone
                       │
                       ▼
              Cline continues the task
```

Both channels resolve the **same internal approval**. The first response wins; the second is a no-op.

### Under the Hood — How the Patch Works

Cline is open source. AgentGate patches its source code directly, builds a custom `.vsix`, and installs it as a VS Code extension. The patch touches exactly two things:

**1. A new `TelegramNotificationService.ts` is added to Cline's source:**

This TypeScript module handles everything Telegram-related:
- Reads the shared config from `~/.claude/remote_approval.json`
- Sends the approval notification via the Telegram Bot API (using Node.js `https` module)
- Polls `getUpdates` in 5-second chunks waiting for a button tap
- On response: answers the callback query, edits the message to show the outcome, calls `onDecision(approved)`
- If the VS Code dialog wins first: the `stop()` function is called, the poll loop exits, the Telegram message is updated to "⏱ Timed out — respond in VS Code"

**2. `src/core/task/index.ts` is patched at the `ask()` method:**

Cline's `ask()` is the central method that pauses execution and waits for user approval. The patch adds a parallel Telegram watcher right before the `pWaitFor` loop that blocks until a response arrives:

```typescript
// Before the patch — waits only for VS Code dialog
await pWaitFor(() => this.askResponse !== undefined)

// After the patch — VS Code + Telegram race simultaneously
const TOOL_APPROVAL_TYPES = ["command", "tool", "browser_action_launch", "use_mcp_server"]
let stopTelegramWatcher: (() => void) | undefined

if (TOOL_APPROVAL_TYPES.includes(type)) {
    stopTelegramWatcher = startTelegramApprovalWatcher(
        type,
        text,
        this.taskId,
        path.basename(this.cwd),
        (approved) => {
            // Called when Telegram responds — feeds the decision into
            // the same handleWebviewAskResponse() that the VS Code dialog uses
            void this.handleWebviewAskResponse(
                approved ? "yesButtonClicked" : "noButtonClicked"
            )
        }
    )
}

await pWaitFor(() => this.askResponse !== undefined)
stopTelegramWatcher?.()   // Cancel Telegram watcher if VS Code dialog won
```

Both paths call the same `handleWebviewAskResponse()` function. `pWaitFor` is watching `this.askResponse` — whichever channel sets it first ends the wait. The second call to `handleWebviewAskResponse()` is a no-op because `askResponse` is already set.

### What Happens Inside `TelegramNotificationService.ts`

```
startTelegramApprovalWatcher() called
        │
        ▼
  Load config from ~/.claude/remote_approval.json
  (returns early if config missing — VS Code dialog handles it alone)
        │
        ▼
  Drain pending Telegram updates to get a clean offset
  (prevents stale button taps from prior sessions replaying)
        │
        ▼
  sendMessage() → Telegram API
  Renders notification with ✅/❌ inline keyboard
        │
        ▼
  Background async loop starts:
  ┌─────────────────────────────────────────┐
  │  while (!stopped && time < deadline):   │
  │    poll getUpdates (5s chunks)          │
  │    filter by: chat_id match             │
  │               message_id match          │
  │               session_id match          │
  │    on match:                            │
  │      answerCallbackQuery()              │
  │      editMessageText() → show outcome  │
  │      onDecision(approved) → feeds      │
  │        handleWebviewAskResponse()      │
  │      return                             │
  └─────────────────────────────────────────┘
        │
  Returns stop() function to caller
        │
  stop() is called when VS Code dialog resolves
  → sets stopped=true → loop exits on next iteration
  → edits Telegram message: "⏱ Timed out — respond in VS Code"
```

### TLS and Corporate Proxies

The `httpsPost` function tries standard TLS verification first. Only if it gets a certificate-specific error (expired cert, untrusted issuer, self-signed chain — common with corporate HTTPS proxies) does it retry with `rejectUnauthorized: false`. All other errors (network down, DNS failure, timeout) are thrown normally. This keeps TLS properly enforced in standard environments while still working behind proxies that intercept HTTPS.

### Security

- All incoming callbacks are filtered by `chat_id` — only your Telegram account can approve
- The session ID (`taskId + timestamp`) is embedded in the callback data so a button from one task can't resolve a different task
- Config is stored at `~/.claude/remote_approval.json` with `chmod 600`

---

## Requirements

- macOS
- Python 3.10+ (no pip installs — for setup.py only)
- Node.js 18+ and npm
- Git
- VS Code with the `code` CLI installed
  - If missing: `Cmd+Shift+P` → **Shell Command: Install 'code' command in PATH**
- A Telegram account

---

## Setup

### Step 1 — Run the setup wizard

```bash
cd cline
python3 setup.py
```

The wizard:
1. **Token validation** — connects to your Telegram bot to verify the token
2. **Chat ID detection** — asks you to send a message to your bot; reads your chat ID automatically
3. **Round-trip test** — sends a real approval notification to your phone; tap to confirm it works
4. **Config write** — saves `~/.claude/remote_approval.json` with `chmod 600`
5. **Build** — clones Cline at the pinned version, copies `TelegramNotificationService.ts`, applies `index.patch`, runs `npm install` + `npm run package` + `vsce package`
6. **Install** — runs `code --install-extension claude-dev-*.vsix --force`

### Step 2 — Restart VS Code

Reload VS Code after install. From this point, every Cline tool approval fires both the VS Code dialog and a Telegram notification.

---

## File Structure

```
cline/
├── setup.py                        # One-time setup wizard (run this)
├── install.sh                      # Build + install script (called by setup.py, re-run to update)
├── uninstall.sh                    # Reinstalls official Cline, optionally removes config
├── TelegramNotificationService.ts  # New TypeScript service added into Cline's source
└── index.patch                     # Git patch for src/core/task/index.ts
```

**What `install.sh` does step by step:**
1. Checks `node`, `npm`, `git`, `code` CLI are available
2. Checks `~/.claude/remote_approval.json` exists
3. Clones or updates Cline at `CLINE_VERSION` (default: `v3.82.0`) into `~/.agentgate/cline-build/cline`
4. Resets `src/core/task/index.ts` to clean state, removes any old `TelegramNotificationService.ts`
5. Copies `TelegramNotificationService.ts` → `src/services/telegram/`
6. Applies `index.patch` with `git apply`; falls back to fuzzy apply with `--reject` if the clean apply fails
7. Runs `npm install` (root + `webview-ui/`), `npm run protos`, `npm run package`, `npx vsce package`
8. Installs the `.vsix` with `code --install-extension --force`

---

## Updating

Change the `CLINE_VERSION` variable in `install.sh` to the new release tag, then rebuild:

```bash
CLINE_VERSION=v3.83.0 bash install.sh
```

This re-clones at the new tag, re-applies the patch, and installs the updated extension. You don't need to re-run `setup.py` — the Telegram config is already saved.

If the patch fails (Cline changed `index.ts` significantly near the `ask()` method), [open an issue](https://github.com/Shreyansh0508/agentgate/issues).

---

## Differences from Claude Code Integration

| | Claude Code | Cline |
|---|---|---|
| **Integration method** | Hook scripts registered in `~/.claude/settings.json` | Source patch compiled into a custom `.vsix` extension |
| **Terminal prompt** | 10s interactive prompt in terminal → then Telegram | No terminal prompt — Telegram fires immediately |
| **Response channels** | Terminal keyboard OR Telegram | VS Code dialog OR Telegram |
| **Tool filtering** | Configurable per-tool via `require_approval_tools` | All approval types: `command`, `tool`, `browser_action_launch`, `use_mcp_server` |
| **Question handling** | Stop hook + `[WAITING_FOR_INPUT]` marker | Not implemented — VS Code chat handles questions |
| **Dependencies** | Python stdlib only | Node.js + npm required to build |

---

## Uninstall

```bash
cd cline
bash uninstall.sh
```

Reinstalls the official Cline from the VS Code marketplace (`saoudrizwan.claude-dev`). Optionally removes the build directory (`~/.agentgate/cline-build`) and the shared Telegram config.
