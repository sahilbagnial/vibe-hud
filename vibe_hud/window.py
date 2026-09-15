import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
import webview

from vibe_hud.hooks import HooksManager
from vibe_hud.server import HudServer

SCALE_FACTORS = {"small": 0.88, "medium": 1.0, "large": 1.15}
DISMISS_SWEEP_INTERVAL_SEC = 5

# Jump-to-window support for IDE-integrated terminals: activating the app
# alone (NSRunningApplication) just restores whatever window that app last
# had focused, which is wrong the moment more than one project window is
# open. These CLIs support reopening a specific path in an *already open*
# window that has it, which is what actually lands you on the right screen.
# TERM_PROGRAM is "vscode" for every VS Code fork (Cursor, Windsurf,
# Antigravity, ...) and app_name is useless for telling them apart (they all
# report as "Electron" at the OS process level) — __CFBundleIdentifier is the
# only reliable signal. Entries are best-effort for anything not personally
# confirmed; shutil.which() gates actual use, so a wrong/missing guess just
# falls back to plain app activation instead of failing.
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

if sys.platform == "darwin":
    from AppKit import NSObject

    class _TrayActions(NSObject):
        """Target for the menu bar status item — the fallback recovery path
        when the floating HUD window itself becomes unreachable."""

        def showWindow_(self, sender):
            self.app.bring_to_front()

        def centerWindow_(self, sender):
            self.app.center_window()

        def quitApp_(self, sender):
            self.app.quit_app()
else:
    _TrayActions = None


class VibeHudApi:
    def __init__(self, window_controller):
        self.controller = window_controller
        self.hooks_mgr = HooksManager()

    def set_expanded(self, expanded: bool, orientation: str = "horizontal"):
        self.controller.resize_window(expanded, orientation)

    def set_orientation(self, orientation: str):
        self.controller.set_orientation(orientation)

    def set_scale(self, scale: str):
        self.controller.set_scale(scale)

    def set_always_on_top(self, value: bool):
        self.controller.set_always_on_top(value)

    def quit_app(self):
        self.controller.quit_app()

    def install_hooks(self):
        return self.hooks_mgr.install()

    def center_window(self):
        self.controller.center_window()

    def simulate(self, scenario: str = "multi"):
        self.controller.simulate_scenario(scenario)

    def dismiss_session(self, session_id: str):
        self.controller.dismiss_session(session_id)

    def focus_session(self, session_id: str):
        self.controller.focus_session(session_id)

    def save_settings(self, settings_json: str):
        self.controller.save_settings(settings_json)

    def get_settings(self):
        return self.controller.load_settings()


class VibeHudApp:
    def __init__(self):
        self.window = None
        self.api = VibeHudApi(self)
        self.server = None
        self.sessions = {}
        self._sessions_lock = threading.Lock()
        self.ui_dir = Path(__file__).parent / "ui"
        self.config_dir = Path.home() / ".vibe-hud"
        self.settings_file = self.config_dir / "settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = self.load_settings()
        self.is_expanded = False

    def start(self):
        self.server = HudServer(on_event=self.handle_incoming_event)
        self.server.start()

        index_html = self.ui_dir / "index.html"
        orientation = self.settings.get("orientation", "horizontal")
        w, h = self._collapsed_size(orientation)

        self._dismiss_thread = threading.Thread(target=self._dismiss_sweep_loop, daemon=True)
        self._dismiss_thread.start()

        self.window = webview.create_window(
            "Vibe HUD",
            url=str(index_html.resolve()),
            js_api=self.api,
            width=w,
            height=h,
            x=600,
            y=40,
            frameless=True,
            # Reverted to pywebview's own on_top (NSStatusWindowLevel on macOS).
            # A prior attempt to avoid that level (NSFloatingWindowLevel instead,
            # to dodge a background-dimming side effect) broke "stays on top" —
            # the window disappeared entirely on losing focus, and the dimming
            # persisted anyway, so it was a straight regression. Reverting.
            on_top=self.settings.get("alwaysOnTop", True),
            transparent=True,
            # Every layout (collapsed/expanded x horizontal/vertical x scale) is a
            # specific, hand-fit CSS box. Free-form OS-level resizing has no
            # sensible in-between state, so size is only ever changed by us
            # (orientation/expand/scale in Settings), never by dragging an edge.
            resizable=False,
            easy_drag=True,
        )

        webview.start(self.on_loaded, debug=False)

    def on_loaded(self):
        try:
            if sys.platform == "darwin":
                from AppKit import (
                    NSApp,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                )
                NSApp.setActivationPolicy_(1)

                for win in NSApp.windows():
                    behavior = win.collectionBehavior()
                    # NOT NSWindowCollectionBehaviorFullScreenAuxiliary: that flag
                    # marks the window as a system-overlay-class panel (the same
                    # class Control Center/Spotlight use over full-screen apps),
                    # which macOS pairs with a background-dimming treatment even
                    # outside an actual full-screen space. CanJoinAllSpaces alone
                    # is enough to float across your normal desktop spaces.
                    win.setCollectionBehavior_(
                        behavior | NSWindowCollectionBehaviorCanJoinAllSpaces
                    )
        except Exception as e:
            print(f"[vibe-hud] Warning configuring window level: {e}")

        if sys.platform == "darwin":
            # on_loaded runs off the main thread (webview.start's func argument
            # is invoked from a background thread), but NSStatusBar/NSMenu
            # creation asserts it's on the main thread — dispatch it there.
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._setup_status_item)
        else:
            self._setup_status_item()

        settings = self.load_settings()
        if self.window:
            self.window.evaluate_js(f"if (window.applySettings) window.applySettings({json.dumps(settings)})")

    def _setup_status_item(self):
        # Fallback recovery path: whatever the cause of the HUD becoming
        # unreachable (hidden behind another window, dragged off-screen,
        # etc.), this menu bar item can always bring it back or quit the app,
        # independent of the floating window's own state.
        if sys.platform != "darwin":
            return
        try:
            from AppKit import NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem

            self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                NSVariableStatusItemLength
            )
            self._status_item.button().setTitle_("\U0001F6A6")  # 🚦

            self._tray_actions = _TrayActions.alloc().init()
            self._tray_actions.app = self

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

    def bring_to_front(self):
        if not self.window:
            return
        try:
            # Re-assert on_top in case it was somehow lost, then force to front.
            self.window.on_top = self.settings.get("alwaysOnTop", True)
            from AppKit import NSApp
            for win in NSApp.windows():
                win.orderFrontRegardless()
        except Exception as e:
            print(f"[vibe-hud] Warning bringing window to front: {e}")

    def set_orientation(self, orientation: str):
        self.settings["orientation"] = orientation
        self.save_settings(self.settings)
        self.resize_window(self.is_expanded, orientation)

    def set_scale(self, scale: str):
        self.settings["scale"] = scale
        self.save_settings(self.settings)
        self.resize_window(self.is_expanded)

    def set_always_on_top(self, value: bool):
        self.settings["alwaysOnTop"] = value
        self.save_settings(self.settings)
        if self.window:
            self.window.on_top = value

    def quit_app(self):
        if self.server:
            self.server.stop()
        os._exit(0)

    def _collapsed_size(self, orientation: str):
        # Must match the body / body[data-orientation="vertical"] base sizes
        # in ui/style.css.
        base = (68, 260) if orientation == "vertical" else (336, 100)
        return self._scaled(base)

    def _expanded_size(self, orientation: str):
        # Must match the body[data-orientation="vertical"][data-expanded="true"]
        # and body[data-expanded="true"] base sizes in ui/style.css.
        base = (396, 420) if orientation == "vertical" else (420, 440)
        return self._scaled(base)

    def _scaled(self, size):
        factor = SCALE_FACTORS.get(self.settings.get("scale", "medium"), 1.0)
        w, h = size
        return int(w * factor), int(h * factor)

    def resize_window(self, expanded: bool, orientation: str = None):
        self.is_expanded = expanded
        if not self.window:
            return

        orient = orientation or self.settings.get("orientation", "horizontal")
        w, h = self._expanded_size(orient) if expanded else self._collapsed_size(orient)
        self.window.resize(w, h)

    def center_window(self):
        if self.window:
            self.window.move(600, 40)

    def _dismiss_sweep_loop(self):
        while True:
            time.sleep(DISMISS_SWEEP_INTERVAL_SEC)
            auto_dismiss_sec = self.settings.get("autoDismissSec", 60)
            if not auto_dismiss_sec:
                continue
            now = int(time.time() * 1000)
            with self._sessions_lock:
                expired = [
                    sid for sid, s in self.sessions.items()
                    if s["status"] == "complete"
                    and s.get("completed_at")
                    and (now - s["completed_at"]) > auto_dismiss_sec * 1000
                ]
                for sid in expired:
                    del self.sessions[sid]
            if expired:
                self.broadcast_state()

    def load_settings(self) -> dict:
        default_settings = {
            "theme": "dark-glass",
            "orientation": "horizontal",
            "scale": "medium",
            "soundEnabled": True,
            "soundStyle": "marimba",
            "soundVolume": 0.8,
            "autoDismissSec": 60,
            "alwaysOnTop": True,
            "colorblindMode": False
        }
        if self.settings_file.exists():
            try:
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
                default_settings.update(data)
            except Exception:
                pass
        return default_settings

    def save_settings(self, settings_data):
        try:
            data = json.loads(settings_data) if isinstance(settings_data, str) else settings_data
            self.settings.update(data)
            self.settings_file.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[vibe-hud] Error saving settings: {e}")

    def dismiss_session(self, session_id: str):
        with self._sessions_lock:
            if session_id not in self.sessions:
                return
            del self.sessions[session_id]
        self.broadcast_state()

    def _jump_via_ide_cli(self, s: dict) -> bool:
        """Reopen the session's cwd via the IDE's own CLI (code -r, idea, etc.)
        so an already-open window for that project gets focused directly,
        instead of just activating the app and landing on whatever window it
        last had up. Returns True if a jump was attempted."""
        cwd = s.get("cwd")
        if not cwd or not os.path.exists(cwd):
            return False

        bundle_id = s.get("bundle_id") or ""
        term_program = (s.get("term_program") or "").lower()
        terminal_emulator = s.get("terminal_emulator") or ""

        cli = None
        args = None
        if terminal_emulator == "JetBrains-JediTerm":
            cli = JETBRAINS_CLI_BY_BUNDLE_ID.get(bundle_id)
            args = [cwd]
        elif term_program == "vscode":
            cli = VSCODE_FAMILY_CLI_BY_BUNDLE_ID.get(bundle_id)
            args = ["-r", cwd]

        if not cli or not shutil.which(cli):
            return False

        try:
            subprocess.Popen([cli, *args])
            return True
        except Exception as e:
            print(f"[vibe-hud] IDE CLI jump error ({cli}): {e}")
            return False

    def focus_session(self, session_id: str):
        s = self.sessions.get(session_id)
        if not s:
            return

        app_pid = s.get("app_pid")
        cwd = s.get("cwd")
        app_name = s.get("app_name") or ""
        activated = False

        if sys.platform == "darwin":
            if self._jump_via_ide_cli(s):
                return

            if app_pid:
                try:
                    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(app_pid)
                    if app:
                        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                        activated = True
                except Exception as e:
                    print(f"[vibe-hud] AppKit activation error: {e}")

            if not activated and "iterm" in app_name.lower():
                try:
                    subprocess.run(["osascript", "-e", "tell application \"iTerm2\" to activate"], check=False)
                    activated = True
                except Exception:
                    pass

            if not activated and "terminal" in app_name.lower():
                try:
                    subprocess.run(["osascript", "-e", "tell application \"Terminal\" to activate"], check=False)
                    activated = True
                except Exception:
                    pass

            if not activated and cwd and os.path.exists(cwd):
                try:
                    subprocess.Popen(["open", "-a", "Terminal", cwd])
                except Exception:
                    pass

    def handle_incoming_event(self, payload: dict):
        event_name = payload.get("hook_event_name", "").lower()
        explicit_status = payload.get("status")

        session_id = payload.get("session_id")
        cwd = payload.get("cwd") or ""
        repo_name = Path(cwd).name if cwd else "Terminal"

        if not session_id:
            session_id = cwd if cwd else "default_session"

        now = int(time.time() * 1000)

        with self._sessions_lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "id": session_id,
                    "cwd": cwd,
                    "repo_name": repo_name,
                    "app_pid": payload.get("app_pid"),
                    "app_name": payload.get("app_name"),
                    "term_program": payload.get("term_program"),
                    "bundle_id": payload.get("bundle_id"),
                    "terminal_emulator": payload.get("terminal_emulator"),
                    "status": "idle",
                    "title": "Ready",
                    "detail": "",
                    "tool_name": None,
                    "prompt": None,
                    "started_at": None,
                    "completed_at": None,
                    "duration": None,
                    "last_updated": now,
                }

            s = self.sessions[session_id]
            s["cwd"] = cwd or s["cwd"]
            s["repo_name"] = repo_name or s["repo_name"]
            if payload.get("app_pid"):
                s["app_pid"] = payload["app_pid"]
            if payload.get("app_name"):
                s["app_name"] = payload["app_name"]
            if payload.get("bundle_id"):
                s["bundle_id"] = payload["bundle_id"]
            if payload.get("terminal_emulator"):
                s["terminal_emulator"] = payload["terminal_emulator"]
            s["last_updated"] = now

            self._apply_event(s, event_name, explicit_status, payload, now, repo_name)

        self.broadcast_state()

    def _apply_event(self, s, event_name, explicit_status, payload, now, repo_name):
        if explicit_status:
            status = explicit_status
            if status == "working" and s["status"] != "working":
                s["started_at"] = now
            elif status == "complete":
                s["duration"] = int((now - s["started_at"]) / 1000) if s.get("started_at") else None
            s["status"] = status
            s["title"] = payload.get("message") or f"{repo_name}: {status}"
        elif event_name == "userpromptsubmit":
            prompt = payload.get("prompt", "")
            s["status"] = "working"
            s["started_at"] = now
            s["prompt"] = prompt
            s["title"] = f"{repo_name}: Thinking..."
            s["detail"] = prompt
            s["tool_name"] = "PROMPT"
        elif event_name == "pretooluse":
            tool = payload.get("tool_name", "Tool")
            s["status"] = "working"
            if not s.get("started_at"):
                s["started_at"] = now
            s["tool_name"] = tool
            s["title"] = f"{repo_name}: Running {tool}"
            s["detail"] = f"Tool execution: {tool}"
        elif event_name == "posttooluse":
            s["status"] = "working"
            s["tool_name"] = payload.get("tool_name")
            s["title"] = f"{repo_name}: Thinking..."
        elif event_name == "notification":
            s["status"] = "attention"
            s["title"] = f"{repo_name}: Needs Input"
            s["detail"] = payload.get("message", "Confirmation required")
        elif event_name == "stop":
            s["status"] = "complete"
            s["completed_at"] = now
            s["duration"] = int((now - s["started_at"]) / 1000) if s.get("started_at") else None
            s["title"] = f"{repo_name}: Turn Complete"
            duration = s["duration"]
            s["detail"] = f"Finished in {duration}s" if duration else "Finished turn"
        elif event_name == "sessionstart":
            s["status"] = "idle"
            s["title"] = f"{repo_name}: Ready"

    def simulate_scenario(self, scenario: str):
        now = int(time.time() * 1000)
        curr_pid = os.getppid()
        if scenario == "multi":
            self.sessions = {
                "sess_backend": {
                    "id": "sess_backend",
                    "cwd": "/Users/sahilbagnial/Desktop/repo/sight3-backend",
                    "repo_name": "sight3-backend",
                    "app_pid": curr_pid,
                    "status": "working",
                    "title": "sight3-backend: Running pytest",
                    "detail": "Executing unit tests for auth module",
                    "tool_name": "BASH",
                    "prompt": "Fix database connection leaks and add tests",
                    "started_at": now - 35000,
                    "last_updated": now,
                },
                "sess_client": {
                    "id": "sess_client",
                    "cwd": "/Users/sahilbagnial/Desktop/repo/sight3-client",
                    "repo_name": "sight3-client",
                    "app_pid": curr_pid,
                    "status": "attention",
                    "title": "sight3-client: Needs Input",
                    "detail": "Approve execution of `npm audit fix`?",
                    "tool_name": "CONFIRM",
                    "prompt": "Update frontend dependencies",
                    "started_at": now - 18000,
                    "last_updated": now,
                },
                "sess_platform": {
                    "id": "sess_platform",
                    "cwd": "/Users/sahilbagnial/Desktop/repo/data-platform",
                    "repo_name": "data-platform",
                    "app_pid": curr_pid,
                    "status": "complete",
                    "title": "data-platform: Complete",
                    "detail": "Backfill migration completed",
                    "tool_name": None,
                    "prompt": "Run event log backfill",
                    "started_at": now - 90000,
                    "completed_at": now,
                    "duration": 48,
                    "last_updated": now,
                }
            }
            self.broadcast_state()

    def broadcast_state(self):
        if not self.sessions:
            state_data = {
                "aggregate_status": "idle",
                "headline_title": "Vibe HUD Ready",
                "headline_subtitle": "Standing by for Claude...",
                "active_tool": None,
                "active_timer": None,
                "sessions": [],
            }
        else:
            priority_order = {"attention": 4, "working": 3, "complete": 2, "idle": 1}
            sorted_sessions = sorted(
                self.sessions.values(),
                key=lambda s: (priority_order.get(s["status"], 0), s.get("last_updated", 0)),
                reverse=True
            )

            top_session = sorted_sessions[0]
            aggregate_status = top_session["status"]

            now = int(time.time() * 1000)
            active_timer = None
            if top_session["status"] == "working" and top_session.get("started_at"):
                active_timer = int((now - top_session["started_at"]) / 1000)
            elif top_session["status"] == "complete" and top_session.get("duration"):
                active_timer = top_session["duration"]

            state_data = {
                "aggregate_status": aggregate_status,
                "headline_title": top_session["title"],
                "headline_subtitle": top_session.get("detail", ""),
                "active_tool": top_session.get("tool_name"),
                "active_timer": active_timer,
                "active_session_id": top_session["id"],
                "sessions": sorted_sessions,
            }

        if self.window:
            js = f"if (window.updateState) window.updateState({json.dumps(state_data)})"
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass
