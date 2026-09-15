import os

from vibe_hud.platform.base import PlatformBackend, jump_via_ide_cli, walk_ancestor_processes

# Unlike macOS, Windows doesn't share one generic Electron host process
# across VS Code forks — each ships a distinctly named .exe — so CLI
# resolution is a direct executable-name lookup, no bundle-id table needed.
KNOWN_APP_EXE_NAMES = {
    "code.exe", "code-insiders.exe", "cursor.exe", "windsurf.exe",
    "antigravity-ide.exe", "idea64.exe", "pycharm64.exe", "webstorm64.exe",
    "goland64.exe", "clion64.exe", "rubymine64.exe", "phpstorm64.exe",
    "rider64.exe", "rustrover64.exe", "windowsterminal.exe", "wt.exe",
}

CLI_BY_EXE_NAME = {
    "code.exe": "code",
    "code-insiders.exe": "code-insiders",
    "cursor.exe": "cursor",
    "windsurf.exe": "windsurf",
    "antigravity-ide.exe": "antigravity-ide",
    "idea64.exe": "idea",
    "pycharm64.exe": "pycharm",
    "webstorm64.exe": "webstorm",
    "goland64.exe": "goland",
    "clion64.exe": "clion",
    "rubymine64.exe": "rubymine",
    "phpstorm64.exe": "phpstorm",
    "rider64.exe": "rider",
    "rustrover64.exe": "rustrover",
}


def _resolve_cli(session: dict):
    exe = (session.get("app_exe_name") or "").lower()
    return CLI_BY_EXE_NAME.get(exe)


def _find_app_process(chain):
    # No fallback to the topmost ancestor: that's near the root of the
    # process tree (e.g. a system/session process), not necessarily the
    # window-owning terminal/IDE — using it would hand xdotool/win32 a PID
    # that doesn't own the window we actually want to focus. Better to
    # report no app_pid than a wrong one.
    for p in chain:
        try:
            if p.name().lower() in KNOWN_APP_EXE_NAMES:
                return p
        except Exception:
            continue
    return None


class WindowsBackend(PlatformBackend):
    def configure_window(self, window) -> None:
        pass  # pywebview's own on_top= flag is the only hook needed here

    def set_always_on_top(self, window, value: bool) -> None:
        window.on_top = value

    def bring_to_front(self, window) -> None:
        try:
            window.show()
            window.restore()
        except Exception as e:
            print(f"[vibe-hud] Warning bringing window to front: {e}")

    def setup_tray(self, app) -> None:
        pass  # no tray on Windows in this pass

    def detect_terminal_info(self) -> dict:
        env = os.environ
        chain = walk_ancestor_processes()
        app_process = _find_app_process(chain)

        app_pid = app_process.pid if app_process else None
        app_name = None
        app_exe_name = None
        if app_process:
            try:
                app_name = app_process.name()
                app_exe_name = app_name.lower()
            except Exception:
                pass

        return {
            "term_program": env.get("TERM_PROGRAM", ""),
            "wt_session": env.get("WT_SESSION", ""),
            # JetBrains bundles its own cross-platform terminal (JediTerm),
            # so this is set the same way on Windows as macOS/Linux — needed
            # by jump_via_ide_cli to pick JetBrains-compatible args (no -r).
            "terminal_emulator": env.get("TERMINAL_EMULATOR", ""),
            "app_pid": app_pid,
            "app_name": app_name,
            "app_exe_name": app_exe_name,
        }

    def focus_session(self, session: dict) -> bool:
        if jump_via_ide_cli(session, _resolve_cli):
            return True

        app_pid = session.get("app_pid")
        if app_pid:
            try:
                import win32con
                import win32gui
                import win32process

                target = []

                def _enum_handler(hwnd, _):
                    if not win32gui.IsWindowVisible(hwnd):
                        return
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == app_pid:
                        target.append(hwnd)

                win32gui.EnumWindows(_enum_handler, None)
                if target:
                    win32gui.ShowWindow(target[0], win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(target[0])
                    return True
            except ImportError:
                print("[vibe-hud] pywin32 not installed; skipping native window focus fallback")
            except Exception as e:
                print(f"[vibe-hud] Windows focus error: {e}")

        return False
