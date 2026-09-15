import json
import os
import shutil
import time
from pathlib import Path


class HooksManager:
    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.settings_path = self.claude_dir / "settings.json"

    def is_configured(self) -> bool:
        if not self.settings_path.exists():
            return False
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            hooks = data.get("hooks", {})
            for event in ["UserPromptSubmit", "Stop"]:
                event_hooks = hooks.get(event, [])
                if not isinstance(event_hooks, list):
                    continue
                for item in event_hooks:
                    if isinstance(item, dict) and "hooks" in item:
                        for h in item["hooks"]:
                            cmd = h.get("command", "")
                            if "vibe-hud" in cmd or "claude-hud" in cmd:
                                return True
            return False
        except Exception:
            return False

    def install(self, hook_cmd: str = "vibe-hud-hook") -> dict:
        try:
            self.claude_dir.mkdir(parents=True, exist_ok=True)
            settings = {}
            backup_path = None

            if self.settings_path.exists():
                raw = self.settings_path.read_text(encoding="utf-8")
                try:
                    settings = json.loads(raw)
                except Exception:
                    settings = {}
                backup_path = self.claude_dir / f"settings.backup.{int(time.time() * 1000)}.json"
                backup_path.write_text(raw, encoding="utf-8")

            if "hooks" not in settings or not isinstance(settings["hooks"], dict):
                settings["hooks"] = {}

            matcher_entry = {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_cmd,
                    }
                ]
            }

            events = ["UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "SessionStart"]
            for ev in events:
                if ev not in settings["hooks"] or not isinstance(settings["hooks"][ev], list):
                    settings["hooks"][ev] = []

                # Remove any existing vibe-hud hooks
                cleaned = []
                for item in settings["hooks"][ev]:
                    if not isinstance(item, dict):
                        continue
                    if "hooks" in item and isinstance(item["hooks"], list):
                        has_vibe = any("vibe-hud" in h.get("command", "") or "claude-hud" in h.get("command", "") for h in item["hooks"])
                        if not has_vibe:
                            cleaned.append(item)
                    elif "command" in item:
                        if "vibe-hud" not in item["command"] and "claude-hud" not in item["command"]:
                            cleaned.append(item)
                cleaned.append(matcher_entry)
                settings["hooks"][ev] = cleaned

            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            return {
                "success": True,
                "message": "Vibe HUD hooks configured successfully in ~/.claude/settings.json",
                "backup": str(backup_path) if backup_path else None
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def remove(self) -> dict:
        if not self.settings_path.exists():
            return {"success": True, "message": "Settings file does not exist."}
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            events = ["UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "SessionStart"]
            for ev in events:
                if ev in hooks and isinstance(hooks[ev], list):
                    hooks[ev] = [
                        item for item in hooks[ev]
                        if not (
                            isinstance(item, dict)
                            and "hooks" in item
                            and any("vibe-hud" in h.get("command", "") or "claude-hud" in h.get("command", "") for h in item["hooks"])
                        )
                    ]
                    if not hooks[ev]:
                        del hooks[ev]
            if not hooks:
                settings.pop("hooks", None)

            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            return {"success": True, "message": "Vibe HUD hooks removed cleanly."}
        except Exception as e:
            return {"success": False, "message": str(e)}
