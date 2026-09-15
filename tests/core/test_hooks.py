import json
from vibe_hud.core.hooks import HooksManager


def test_install_writes_all_events(tmp_path):
    mgr = HooksManager()
    mgr.claude_dir = tmp_path
    mgr.settings_path = tmp_path / "settings.json"

    result = mgr.install(hook_cmd="vibe-hud-hook")
    assert result["success"] is True

    data = json.loads(mgr.settings_path.read_text())
    for event in ["UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "SessionStart"]:
        commands = [h["command"] for item in data["hooks"][event] for h in item["hooks"]]
        assert "vibe-hud-hook" in commands


def test_is_configured_true_after_install(tmp_path):
    mgr = HooksManager()
    mgr.claude_dir = tmp_path
    mgr.settings_path = tmp_path / "settings.json"
    mgr.install()
    assert mgr.is_configured() is True


def test_remove_cleans_up_hooks(tmp_path):
    mgr = HooksManager()
    mgr.claude_dir = tmp_path
    mgr.settings_path = tmp_path / "settings.json"
    mgr.install()
    result = mgr.remove()
    assert result["success"] is True
    assert mgr.is_configured() is False


def test_install_preserves_non_vibe_hooks(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "other-tool"}]}]}
    }))
    mgr = HooksManager()
    mgr.claude_dir = tmp_path
    mgr.settings_path = settings_path
    mgr.install()

    data = json.loads(settings_path.read_text())
    commands = [h["command"] for item in data["hooks"]["Stop"] for h in item["hooks"]]
    assert "other-tool" in commands
    assert "vibe-hud-hook" in commands
