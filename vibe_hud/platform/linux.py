import os
import shutil
import subprocess

from vibe_hud.platform.base import PlatformBackend, jump_via_ide_cli, walk_ancestor_processes

KNOWN_APP_PROCESS_NAMES = {
    "code", "code-insiders", "cursor", "windsurf", "antigravity-ide",
    "idea", "idea.sh", "pycharm", "pycharm.sh", "webstorm", "webstorm.sh",
    "goland", "goland.sh", "clion", "clion.sh", "rubymine", "rubymine.sh",
    "phpstorm", "phpstorm.sh", "rider", "rider.sh", "rustrover", "rustrover.sh",
    "gnome-terminal-server", "konsole", "xterm", "alacritty", "wezterm",
}

CLI_BY_PROCESS_NAME = {
    "code": "code",
    "code-insiders": "code-insiders",
    "cursor": "cursor",
    "windsurf": "windsurf",
    "antigravity-ide": "antigravity-ide",
    "idea": "idea", "idea.sh": "idea",
    "pycharm": "pycharm", "pycharm.sh": "pycharm",
    "webstorm": "webstorm", "webstorm.sh": "webstorm",
    "goland": "goland", "goland.sh": "goland",
    "clion": "clion", "clion.sh": "clion",
    "rubymine": "rubymine", "rubymine.sh": "rubymine",
    "phpstorm": "phpstorm", "phpstorm.sh": "phpstorm",
    "rider": "rider", "rider.sh": "rider",
    "rustrover": "rustrover", "rustrover.sh": "rustrover",
}


def _resolve_cli(session: dict):
    exe = (session.get("app_exe_name") or "").lower()
    return CLI_BY_PROCESS_NAME.get(exe)


def _find_app_process(chain):
    for p in chain:
        try:
            if p.name().lower() in KNOWN_APP_PROCESS_NAMES:
                return p
        except Exception:
            continue
    return chain[-1] if chain else None


class LinuxBackend(PlatformBackend):
    def configure_window(self, window) -> None:
        pass  # X11/Wayland window-manager "always on all workspaces" hacks are out of scope for this pass

    def set_always_on_top(self, window, value: bool) -> None:
        window.on_top = value

    def bring_to_front(self, window) -> None:
        try:
            window.show()
            window.restore()
        except Exception as e:
            print(f"[vibe-hud] Warning bringing window to front: {e}")

    def setup_tray(self, app) -> None:
        pass  # no tray on Linux in this pass

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
            "vte_version": env.get("VTE_VERSION", ""),
            "konsole_version": env.get("KONSOLE_VERSION", ""),
            "app_pid": app_pid,
            "app_name": app_name,
            "app_exe_name": app_exe_name,
        }

    def focus_session(self, session: dict) -> bool:
        if jump_via_ide_cli(session, _resolve_cli):
            return True

        # wmctrl has no reliable activate-by-pid mode; xdotool does, and
        # X11-only (no generic Wayland equivalent) — best-effort, matching
        # the existing "missing tool -> skip silently" pattern.
        app_pid = session.get("app_pid")
        if app_pid and shutil.which("xdotool"):
            try:
                out = subprocess.check_output(
                    ["xdotool", "search", "--pid", str(app_pid)]
                ).decode().strip()
                window_ids = out.splitlines()
                if window_ids:
                    subprocess.run(["xdotool", "windowactivate", window_ids[0]], check=False)
                    return True
            except Exception:
                pass

        return False
