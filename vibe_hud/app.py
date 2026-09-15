import json
import os
import threading
import time
from pathlib import Path

import webview

from vibe_hud.core.hooks import HooksManager
from vibe_hud.core.server import HudServer
from vibe_hud.core.session_store import SessionStore
from vibe_hud.core.settings import Settings
from vibe_hud.platform import get_backend

DISMISS_SWEEP_INTERVAL_SEC = 5


class VibeHudApi:
    def __init__(self, app):
        self.app = app
        self.hooks_mgr = HooksManager()

    def set_expanded(self, expanded: bool, orientation: str = "horizontal"):
        self.app.resize_window(expanded, orientation)

    def set_orientation(self, orientation: str):
        self.app.set_orientation(orientation)

    def set_scale(self, scale: str):
        self.app.set_scale(scale)

    def set_always_on_top(self, value: bool):
        self.app.set_always_on_top(value)

    def quit_app(self):
        self.app.quit_app()

    def install_hooks(self):
        return self.hooks_mgr.install()

    def center_window(self):
        self.app.center_window()

    def simulate(self, scenario: str = "multi"):
        self.app.simulate_scenario(scenario)

    def dismiss_session(self, session_id: str):
        self.app.dismiss_session(session_id)

    def focus_session(self, session_id: str):
        self.app.focus_session(session_id)

    def save_settings(self, settings_json: str):
        self.app.save_settings(settings_json)

    def get_settings(self):
        return self.app.settings.data


class VibeHudApp:
    def __init__(self):
        self.window = None
        self.api = VibeHudApi(self)
        self.server = None
        self.session_store = SessionStore()
        self.backend = get_backend()
        self.ui_dir = Path(__file__).parent / "ui"
        self.config_dir = Path.home() / ".vibe-hud"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(self.config_dir / "settings.json")
        self.is_expanded = False

    def start(self):
        self.server = HudServer(on_event=self.handle_incoming_event)
        self.server.start()

        index_html = self.ui_dir / "index.html"
        orientation = self.settings.get("orientation", "horizontal")
        w, h = self.settings.collapsed_size(orientation)

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
            on_top=self.settings.get("alwaysOnTop", True),
            transparent=True,
            # Every layout (collapsed/expanded x horizontal/vertical x scale) is
            # a specific, hand-fit CSS box — size only ever changes via our own
            # Settings-driven resize_window(), never free-form OS resizing.
            resizable=False,
            easy_drag=True,
        )

        webview.start(self.on_loaded, debug=False)

    def on_loaded(self):
        try:
            self.backend.configure_window(self.window)
        except Exception as e:
            print(f"[vibe-hud] Warning configuring window: {e}")

        try:
            self.backend.setup_tray(self)
        except Exception as e:
            print(f"[vibe-hud] Warning setting up tray: {e}")

        if self.window:
            self.window.evaluate_js(
                f"if (window.applySettings) window.applySettings({json.dumps(self.settings.data)})"
            )

    def bring_to_front(self):
        if not self.window:
            return
        self.backend.set_always_on_top(self.window, self.settings.get("alwaysOnTop", True))
        self.backend.bring_to_front(self.window)

    def set_orientation(self, orientation: str):
        self.settings.update({"orientation": orientation})
        self.resize_window(self.is_expanded, orientation)

    def set_scale(self, scale: str):
        self.settings.update({"scale": scale})
        self.resize_window(self.is_expanded)

    def set_always_on_top(self, value: bool):
        self.settings.update({"alwaysOnTop": value})
        if self.window:
            self.backend.set_always_on_top(self.window, value)

    def quit_app(self):
        if self.server:
            self.server.stop()
        os._exit(0)

    def resize_window(self, expanded: bool, orientation: str = None):
        self.is_expanded = expanded
        if not self.window:
            return
        orient = orientation or self.settings.get("orientation", "horizontal")
        w, h = self.settings.expanded_size(orient) if expanded else self.settings.collapsed_size(orient)
        self.window.resize(w, h)

    def center_window(self):
        if self.window:
            self.window.move(600, 40)

    def _dismiss_sweep_loop(self):
        while True:
            time.sleep(DISMISS_SWEEP_INTERVAL_SEC)
            auto_dismiss_sec = self.settings.get("autoDismissSec", 60)
            expired = self.session_store.sweep_expired(auto_dismiss_sec)
            if expired:
                self.broadcast_state()

    def save_settings(self, settings_data):
        try:
            data = json.loads(settings_data) if isinstance(settings_data, str) else settings_data
            self.settings.update(data)
        except Exception as e:
            print(f"[vibe-hud] Error saving settings: {e}")

    def dismiss_session(self, session_id: str):
        self.session_store.dismiss(session_id)
        self.broadcast_state()

    def focus_session(self, session_id: str):
        s = self.session_store.get(session_id)
        if not s:
            return
        self.backend.focus_session(s)

    def handle_incoming_event(self, payload: dict):
        self.session_store.apply_event(payload)
        self.broadcast_state()

    def simulate_scenario(self, scenario: str):
        now = int(time.time() * 1000)
        curr_pid = os.getppid()
        if scenario == "multi":
            self.session_store.load_simulation({
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
                },
            })
            self.broadcast_state()

    def broadcast_state(self):
        state_data = self.session_store.to_state_data()
        if self.window:
            js = f"if (window.updateState) window.updateState({json.dumps(state_data)})"
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass
