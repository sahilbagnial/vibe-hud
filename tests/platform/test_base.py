import os
import subprocess
from vibe_hud.platform.base import jump_via_ide_cli, walk_ancestor_processes


def test_jump_returns_false_when_cwd_missing():
    assert jump_via_ide_cli({"cwd": "/does/not/exist"}, lambda s: "code") is False


def test_jump_returns_false_when_resolver_finds_nothing(tmp_path):
    assert jump_via_ide_cli({"cwd": str(tmp_path)}, lambda s: None) is False


def test_jump_returns_false_when_cli_not_on_path(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert jump_via_ide_cli({"cwd": str(tmp_path)}, lambda s: "totally-made-up-cli") is False


def test_jump_uses_dash_r_for_vscode_family(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/code")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = jump_via_ide_cli({"cwd": str(tmp_path)}, lambda s: "code")
    assert result is True
    assert captured["args"][0] == "code"
    assert "-r" in captured["args"]


def test_jump_omits_dash_r_for_jetbrains(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/idea")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = jump_via_ide_cli(
        {"cwd": str(tmp_path), "terminal_emulator": "JetBrains-JediTerm"},
        lambda s: "idea",
    )
    assert result is True
    assert captured["args"] == ["idea", os.path.realpath(str(tmp_path))]


def test_walk_ancestor_processes_returns_chain_from_immediate_parent():
    chain = walk_ancestor_processes(max_depth=5)
    assert len(chain) >= 1
    assert chain[0].pid == os.getppid()
