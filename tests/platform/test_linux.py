from vibe_hud.platform.base import PlatformBackend
from vibe_hud.platform.linux import LinuxBackend, _resolve_cli


def test_resolve_cli_vscode_family_by_process_name():
    assert _resolve_cli({"app_exe_name": "cursor"}) == "cursor"
    assert _resolve_cli({"app_exe_name": "code"}) == "code"


def test_resolve_cli_jetbrains_shell_script_name():
    assert _resolve_cli({"app_exe_name": "pycharm.sh"}) == "pycharm"


def test_resolve_cli_unknown_process_returns_none():
    assert _resolve_cli({"app_exe_name": "bash"}) is None


def test_backend_instantiates_and_implements_interface():
    backend = LinuxBackend()
    assert isinstance(backend, PlatformBackend)


def test_detect_terminal_info_returns_expected_keys():
    info = LinuxBackend().detect_terminal_info()
    for key in ("term_program", "vte_version", "konsole_version", "app_pid", "app_name", "app_exe_name"):
        assert key in info


def test_focus_session_returns_false_with_no_pid_and_no_ide_match():
    backend = LinuxBackend()
    assert backend.focus_session({"cwd": "/does/not/exist"}) is False
