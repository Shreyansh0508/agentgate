#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$HOME/.agentgate/cline-build"

echo ""
echo "=== AgentGate — Cline Setup ==="
echo ""

# ── Check requirements ────────────────────────────────────────────────────────

command -v node >/dev/null 2>&1 || { echo "ERROR: node is required. Install from https://nodejs.org"; exit 1; }
command -v npm  >/dev/null 2>&1 || { echo "ERROR: npm is required."; exit 1; }
command -v git  >/dev/null 2>&1 || { echo "ERROR: git is required."; exit 1; }
command -v code >/dev/null 2>&1 || { echo "ERROR: 'code' CLI not found. In VS Code: Cmd+Shift+P → Shell Command: Install 'code' command"; exit 1; }

# ── Check Telegram config ─────────────────────────────────────────────────────

CONFIG="$HOME/.claude/remote_approval.json"
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: Telegram config not found at $CONFIG"
    echo "Run the AgentGate setup wizard first:"
    echo "  cd ../claude-code && python3 setup.py"
    exit 1
fi
echo "✓ Telegram config found"

# ── Clone Cline ───────────────────────────────────────────────────────────────

mkdir -p "$WORK_DIR"

if [ -d "$WORK_DIR/cline/.git" ]; then
    echo "✓ Cline repo already exists — pulling latest..."
    git -C "$WORK_DIR/cline" pull --ff-only
else
    echo "Cloning Cline..."
    git clone --depth=1 https://github.com/cline/cline.git "$WORK_DIR/cline"
    echo "✓ Cloned"
fi

cd "$WORK_DIR/cline"

# ── Apply patch ───────────────────────────────────────────────────────────────

echo "Applying AgentGate patch to Cline..."

# Reset any previous patch attempts
git checkout src/core/task/index.ts 2>/dev/null || true
rm -f src/services/telegram/TelegramNotificationService.ts 2>/dev/null || true

# Copy new service file
mkdir -p src/services/telegram
cp "$SCRIPT_DIR/TelegramNotificationService.ts" src/services/telegram/

# Apply index.ts patch
if git apply --check "$SCRIPT_DIR/index.patch" 2>/dev/null; then
    git apply "$SCRIPT_DIR/index.patch"
    echo "✓ Patch applied"
else
    echo "WARNING: Patch did not apply cleanly — Cline may have updated."
    echo "Trying fuzzy apply..."
    git apply --reject "$SCRIPT_DIR/index.patch" || true
    if grep -q "startTelegramApprovalWatcher" src/core/task/index.ts; then
        echo "✓ Patch already applied or fuzzily applied"
    else
        echo "ERROR: Could not apply patch. Please open an issue at:"
        echo "  https://github.com/Shreyansh0508/agentgate"
        exit 1
    fi
fi

# ── Build ─────────────────────────────────────────────────────────────────────

echo "Installing dependencies..."
npm install --silent
cd webview-ui && npm install --silent && cd ..
echo "✓ Dependencies installed"

echo "Building extension (this takes ~30 seconds)..."
npm run protos --silent
npm run package --silent 2>&1 | grep -E "DONE|ERROR|warning" || true
echo "✓ Build complete"

# ── Package & Install ─────────────────────────────────────────────────────────

VSIX=$(ls *.vsix 2>/dev/null | head -1)
if [ -z "$VSIX" ]; then
    echo "ERROR: .vsix file not found after build"
    exit 1
fi

echo "Installing $VSIX into VS Code..."
code --install-extension "$VSIX" --force
echo "✓ Installed"

echo ""
echo "=== Done! ==="
echo ""
echo "Restart VS Code, then give Cline any task that runs a command."
echo "You'll get both the VS Code approval dialog AND a Telegram notification"
echo "on your phone — tap either one to approve."
echo ""
