#!/bin/bash
set -e

CONFIG="$HOME/.claude/remote_approval.json"

echo ""
echo "=== AgentGate — Cline Uninstall ==="
echo ""

# Reinstall official Cline from marketplace
echo "Reinstalling official Cline from VS Code marketplace..."
if command -v code >/dev/null 2>&1; then
    code --install-extension saoudrizwan.claude-dev --force
    echo "✓ Official Cline reinstalled"
else
    echo "WARNING: 'code' CLI not found."
    echo "Reinstall Cline manually: Cmd+Shift+X → search 'Cline' → Install"
fi

# Remove build directory
WORK_DIR="$HOME/.agentgate/cline-build"
if [ -d "$WORK_DIR" ]; then
    read -r -p "Remove build directory (~/.agentgate/cline-build)? [y/N]: " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        rm -rf "$WORK_DIR"
        echo "✓ Build directory removed"
    fi
fi

# Optionally remove config
if [ -f "$CONFIG" ]; then
    read -r -p "Remove Telegram config (~/.claude/remote_approval.json)? [y/N]: " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        rm -f "$CONFIG"
        echo "✓ Config removed"
    else
        echo "Config kept (rerun cline/setup.py to re-enable)"
    fi
fi

echo ""
echo "=== Done. Restart VS Code to use the official Cline. ==="
echo ""
