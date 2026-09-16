import os
import subprocess

import pystray

from vibe_hud.platform.base import jump_via_ide_cli, walk_ancestor_processes, build_tray_menu


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


class _FakeApp:
    def __init__(self):
        self.calls = []

    def bring_to_front(self):
        self.calls.append("bring_to_front")

    def center_window(self):
        self.calls.append("center_window")

    def quit_app(self):
        self.calls.append("quit_app")


def test_build_tray_menu_has_show_center_separator_quit():
    app = _FakeApp()
    menu = build_tray_menu(app)
    items = list(menu)
    non_separator = [item for item in items if item is not pystray.Menu.SEPARATOR]
    assert [item.text for item in non_separator] == [
        "Show / Bring to Front", "Center on Screen", "Quit Vibe HUD",
    ]
    assert any(item is pystray.Menu.SEPARATOR for item in items)


def test_build_tray_menu_actions_call_the_right_app_method():
    app = _FakeApp()
    menu = build_tray_menu(app)
    items = [item for item in menu if item is not pystray.Menu.SEPARATOR]

    # pystray.MenuItem doesn't expose its callback as a public attribute in
    # this version (only checked/default/enabled/radio/submenu/text/visible
    # are public) — _action is the only way to invoke it directly for a
    # unit test, verified empirically against the installed pystray version.
    items[0]._action(None, items[0])
    items[1]._action(None, items[1])
    items[2]._action(None, items[2])

    assert app.calls == ["bring_to_front", "center_window", "quit_app"]
