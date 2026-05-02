#!/usr/bin/env python3
"""Uninstall AgentGate hooks from Claude Code."""
import json
import os
import sys

SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")
HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks")


def _is_agentgate_command(command: str) -> bool:
    """Match hooks by script name regardless of clone path."""
    markers = ["pre_tool_use.py", "stop_hook.py", "agentgate"]
    return any(m in command for m in markers)


def _remove_hooks():
    if not os.path.exists(SETTINGS_PATH):
        print("  ~/.claude/settings.json not found — nothing to remove.")
        return False

    with open(SETTINGS_PATH) as f:
        settings = json.load(f)

    hooks = settings.get("hooks", {})
    changed = False

    for event in ("PreToolUse", "Stop"):
        entries = hooks.get(event, [])
        filtered = [
            e for e in entries
            if not any(_is_agentgate_command(h.get("command", "")) for h in e.get("hooks", []))
        ]
        if len(filtered) != len(entries):
            changed = True
        if filtered:
            hooks[event] = filtered
        elif event in hooks:
            del hooks[event]

    if not changed:
        print("  No AgentGate hooks found in settings.json.")
        return False

    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    print("  ✓ Hooks removed from ~/.claude/settings.json")
    return True


def main():
    print("=== AgentGate — Claude Code Uninstall ===\n")

    _remove_hooks()

    if os.path.exists(CONFIG_PATH):
        ans = input("\nRemove Telegram config (~/.claude/remote_approval.json)? [y/N]: ").strip().lower()
        if ans == "y":
            os.remove(CONFIG_PATH)
            print("  ✓ Config removed")
        else:
            print("  Config kept (rerun claude-code/setup.py to re-enable)")

    print("\n=== Done. AgentGate hooks are removed from Claude Code. ===")


if __name__ == "__main__":
    main()
