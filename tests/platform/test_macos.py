import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only backend")


def test_resolve_cli_vscode_family():
    from vibe_hud.platform.macos import _resolve_cli
    session = {"term_program": "vscode", "bundle_id": "com.todesktop.230313mzl4w4u92"}
    assert _resolve_cli(session) == "cursor"


def test_resolve_cli_jetbrains():
    from vibe_hud.platform.macos import _resolve_cli
    session = {"terminal_emulator": "JetBrains-JediTerm", "bundle_id": "com.jetbrains.pycharm"}
    assert _resolve_cli(session) == "pycharm"


def test_resolve_cli_unknown_bundle_returns_none():
    from vibe_hud.platform.macos import _resolve_cli
    assert _resolve_cli({"term_program": "vscode", "bundle_id": "com.unknown.thing"}) is None


def test_backend_instantiates_and_implements_interface():
    from vibe_hud.platform.base import PlatformBackend
    from vibe_hud.platform.macos import MacOSBackend
    backend = MacOSBackend()
    assert isinstance(backend, PlatformBackend)


def test_detect_terminal_info_returns_expected_keys():
    from vibe_hud.platform.macos import MacOSBackend
    info = MacOSBackend().detect_terminal_info()
    for key in ("term_program", "iterm_session", "bundle_id", "terminal_emulator", "app_pid", "app_name"):
        assert key in info
