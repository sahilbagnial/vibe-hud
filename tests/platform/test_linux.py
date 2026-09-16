import os
import shutil
import subprocess
from unittest.mock import patch

from vibe_hud.platform.base import PlatformBackend, jump_via_ide_cli
from vibe_hud.platform.linux import LinuxBackend, _find_app_process, _resolve_cli


class _FakeProcess:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


def test_resolve_cli_vscode_family_by_process_name():
    assert _resolve_cli({"app_exe_name": "cursor"}) == "cursor"
    assert _resolve_cli({"app_exe_name": "code"}) == "code"


def test_resolve_cli_jetbrains_shell_script_name():
    assert _resolve_cli({"app_exe_name": "pycharm.sh"}) == "pycharm"


def test_resolve_cli_unknown_process_returns_none():
    assert _resolve_cli({"app_exe_name": "bash"}) is None


def test_find_app_process_returns_none_when_no_known_app_in_chain():
    chain = [_FakeProcess("bash"), _FakeProcess("zsh"), _FakeProcess("systemd")]
    assert _find_app_process(chain) is None


def test_find_app_process_returns_none_for_empty_chain():
    assert _find_app_process([]) is None


def test_find_app_process_finds_known_app_anywhere_in_chain():
    target = _FakeProcess("cursor")
    chain = [_FakeProcess("bash"), target, _FakeProcess("systemd")]
    assert _find_app_process(chain) is target


def test_backend_instantiates_and_implements_interface():
    backend = LinuxBackend()
    assert isinstance(backend, PlatformBackend)


def test_detect_terminal_info_returns_expected_keys():
    info = LinuxBackend().detect_terminal_info()
    for key in ("term_program", "vte_version", "konsole_version", "terminal_emulator", "app_pid", "app_name", "app_exe_name"):
        assert key in info


def test_focus_session_returns_false_with_no_pid_and_no_ide_match():
    backend = LinuxBackend()
    assert backend.focus_session({"cwd": "/does/not/exist"}) is False


def test_jetbrains_terminal_emulator_flows_into_jump_args(monkeypatch, tmp_path):
    # Regression: detect_terminal_info() must populate "terminal_emulator" so
    # jump_via_ide_cli can tell JetBrains sessions apart from VS Code-family
    # ones and skip the VS Code-only -r flag.
    monkeypatch.setenv("TERMINAL_EMULATOR", "JetBrains-JediTerm")
    info = LinuxBackend().detect_terminal_info()
    assert info["terminal_emulator"] == "JetBrains-JediTerm"

    monkeypatch.setattr(shutil, "which", lambda name: "/fake/idea")
    captured = {}
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: captured.__setitem__("args", args))

    session = {**info, "cwd": str(tmp_path), "app_exe_name": "idea.sh"}
    assert jump_via_ide_cli(session, _resolve_cli) is True
    assert captured["args"] == ["idea", os.path.realpath(str(tmp_path))]


def test_setup_tray_calls_shared_pystray_helper_with_package_icon():
    backend = LinuxBackend()
    with patch("vibe_hud.platform.base.setup_pystray_tray") as mock_setup:
        backend.setup_tray("fake-app")
    mock_setup.assert_called_once()
    called_app, called_icon_path = mock_setup.call_args[0]
    assert called_app == "fake-app"
    assert called_icon_path.endswith("tray-icon-32.png")
