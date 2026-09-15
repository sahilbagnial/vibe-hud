from vibe_hud.platform.base import PlatformBackend
from vibe_hud.platform.windows import WindowsBackend, _resolve_cli


def test_resolve_cli_vscode_family_by_exe_name():
    assert _resolve_cli({"app_exe_name": "cursor.exe"}) == "cursor"
    assert _resolve_cli({"app_exe_name": "code.exe"}) == "code"


def test_resolve_cli_jetbrains_by_exe_name():
    assert _resolve_cli({"app_exe_name": "idea64.exe"}) == "idea"


def test_resolve_cli_unknown_exe_returns_none():
    assert _resolve_cli({"app_exe_name": "notepad.exe"}) is None


def test_backend_instantiates_and_implements_interface():
    backend = WindowsBackend()
    assert isinstance(backend, PlatformBackend)


def test_detect_terminal_info_returns_expected_keys():
    info = WindowsBackend().detect_terminal_info()
    for key in ("term_program", "wt_session", "app_pid", "app_name", "app_exe_name"):
        assert key in info


def test_focus_session_returns_false_with_no_pid_and_no_ide_match():
    backend = WindowsBackend()
    assert backend.focus_session({"cwd": "/does/not/exist"}) is False
