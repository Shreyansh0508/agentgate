import json
import os

CONFIG_PATH = os.path.expanduser("~/.claude/remote_approval.json")


def load() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def should_auto_approve(tool_name: str, config: dict) -> bool:
    return tool_name in config.get("auto_approve_tools", [])


def should_require_approval(tool_name: str, config: dict) -> bool:
    required = config.get("require_approval_tools", ["Bash", "Write", "Edit", "MultiEdit"])
    if required == ["*"]:
        return True
    return tool_name in required
