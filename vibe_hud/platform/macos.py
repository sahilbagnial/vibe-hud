import os
import subprocess

import psutil

from vibe_hud.platform.base import PlatformBackend, jump_via_ide_cli

# TERM_PROGRAM is "vscode" for every VS Code fork (Cursor, Windsurf,
# Antigravity, ...) and app_name is useless for telling them apart (they all
# report as "Electron" at the OS process level) — __CFBundleIdentifier is the
# only reliable signal. Entries are best-effort for anything not personally
# confirmed; shutil.which() (inside jump_via_ide_cli) gates actual use, so a
# wrong/missing guess just falls back to plain app activation.
VSCODE_FAMILY_CLI_BY_BUNDLE_ID = {
    "com.microsoft.VSCode": "code",
    "com.microsoft.VSCodeInsiders": "code-insiders",
    "com.todesktop.230313mzl4w4u92": "cursor",
    "com.exafunction.windsurf": "windsurf",
    "com.google.antigravity-ide": "antigravity-ide",
}

# JetBrains terminals identify themselves via TERMINAL_EMULATOR rather than
# TERM_PROGRAM/bundle id, but the bundle id still says which product it is.
JETBRAINS_CLI_BY_BUNDLE_ID = {
    "com.jetbrains.intellij": "idea",
    "com.jetbrains.intellij.ce": "idea",
    "com.jetbrains.WebStorm": "webstorm",
    "com.jetbrains.pycharm": "pycharm",
    "com.jetbrains.PyCharm.ce": "pycharm",
    "com.jetbrains.goland": "goland",
    "com.jetbrains.CLion": "clion",
    "com.jetbrains.rubymine": "rubymine",
    "com.jetbrains.PhpStorm": "phpstorm",
    "com.jetbrains.rider": "rider",
    "com.jetbrains.RustRover": "rustrover",
}


def _resolve_cli(session: dict):
    bundle_id = session.get("bundle_id") or ""
    terminal_emulator = session.get("terminal_emulator") or ""
    term_program = (session.get("term_program") or "").lower()
    if terminal_emulator == "JetBrains-JediTerm":
        return JETBRAINS_CLI_BY_BUNDLE_ID.get(bundle_id)
    if term_program == "vscode":
        return VSCODE_FAMILY_CLI_BY_BUNDLE_ID.get(bundle_id)
    return None


def _walk_to_app_process():
    """Mirrors the original `ps`-based walk exactly: starting at the
    immediate parent, climb until we find the process whose own parent is
    pid 1 (launchd) — that's the actual app (Terminal.app, iTerm2, a
    VS Code-family Electron host, ...), not launchd itself."""
    try:
        curr = psutil.Process(os.getppid())
    except Exception:
        return None, None
    while curr.pid > 1:
        try:
            parent = curr.parent()
        except Exception:
            return None, None
        if parent is None or parent.pid == 1:
            return curr.pid, curr.name()
        curr = parent
    return None, None


class MacOSBackend(PlatformBackend):
    def configure_window(self, window) -> None:
        try:
            from AppKit import NSApp, NSWindowCollectionBehaviorCanJoinAllSpaces
            NSApp.setActivationPolicy_(1)
            for win in NSApp.windows():
                behavior = win.collectionBehavior()
                # NOT NSWindowCollectionBehaviorFullScreenAuxiliary: that flag
                # marks the window as a system-overlay-class panel, which
                # macOS pairs with background dimming. CanJoinAllSpaces alone
                # is enough to float across normal desktop spaces.
                win.setCollectionBehavior_(behavior | NSWindowCollectionBehaviorCanJoinAllSpaces)
        except Exception as e:
            print(f"[vibe-hud] Warning configuring window level: {e}")

    def set_always_on_top(self, window, value: bool) -> None:
        window.on_top = value

    def bring_to_front(self, window) -> None:
        try:
            from AppKit import NSApp
            for win in NSApp.windows():
                win.orderFrontRegardless()
        except Exception as e:
            print(f"[vibe-hud] Warning bringing window to front: {e}")

    def setup_tray(self, app) -> None:
        # NSStatusBar/NSMenu creation asserts it runs on the main thread, but
        # this is called from on_loaded, which pywebview invokes off the main
        # thread — dispatch it there.
        try:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._setup_status_item, app)
        except Exception as e:
            print(f"[vibe-hud] Warning setting up status item: {e}")

    def _setup_status_item(self, app) -> None:
        try:
            from AppKit import NSObject, NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem

            class _TrayActions(NSObject):
                def showWindow_(self, sender):
                    self.app.bring_to_front()

                def centerWindow_(self, sender):
                    self.app.center_window()

                def quitApp_(self, sender):
                    self.app.quit_app()

            self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                NSVariableStatusItemLength
            )
            self._status_item.button().setTitle_("\U0001F6A6")  # traffic light emoji

            self._tray_actions = _TrayActions.alloc().init()
            self._tray_actions.app = app

            menu = NSMenu.alloc().init()

            show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Show / Bring to Front", "showWindow:", ""
            )
            show_item.setTarget_(self._tray_actions)
            menu.addItem_(show_item)

            center_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Center on Screen", "centerWindow:", ""
            )
            center_item.setTarget_(self._tray_actions)
            menu.addItem_(center_item)

            menu.addItem_(NSMenuItem.separatorItem())

            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Vibe HUD", "quitApp:", ""
            )
            quit_item.setTarget_(self._tray_actions)
            menu.addItem_(quit_item)

            self._status_menu = menu
            self._status_item.setMenu_(menu)
        except Exception as e:
            print(f"[vibe-hud] Warning setting up status item: {e}")

    def detect_terminal_info(self) -> dict:
        env = os.environ
        app_pid, app_name = _walk_to_app_process()
        return {
            "term_program": env.get("TERM_PROGRAM", ""),
            "iterm_session": env.get("ITERM_SESSION_ID", ""),
            "bundle_id": env.get("__CFBundleIdentifier", ""),
            "terminal_emulator": env.get("TERMINAL_EMULATOR", ""),
            "app_pid": app_pid,
            "app_name": app_name,
        }

    def focus_session(self, session: dict) -> bool:
        if jump_via_ide_cli(session, _resolve_cli):
            return True

        app_pid = session.get("app_pid")
        cwd = session.get("cwd")
        app_name = session.get("app_name") or ""

        if app_pid:
            try:
                from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                running_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(app_pid)
                if running_app:
                    running_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                    return True
            except Exception as e:
                print(f"[vibe-hud] AppKit activation error: {e}")

        if "iterm" in app_name.lower():
            try:
                subprocess.run(["osascript", "-e", 'tell application "iTerm2" to activate'], check=False)
                return True
            except Exception:
                pass

        if "terminal" in app_name.lower():
            try:
                subprocess.run(["osascript", "-e", 'tell application "Terminal" to activate'], check=False)
                return True
            except Exception:
                pass

        if cwd and os.path.exists(cwd):
            try:
                subprocess.Popen(["open", "-a", "Terminal", cwd])
                return True
            except Exception:
                pass

        return False
