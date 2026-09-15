import json
import os
import sys
import time
from pathlib import Path
import webview

from vibe_hud.hooks import HooksManager
from vibe_hud.server import HudServer


class VibeHudApi:
    def __init__(self, window_controller):
        self.controller = window_controller
        self.hooks_mgr = HooksManager()

    def set_expanded(self, expanded: bool):
        self.controller.resize_window(expanded)

    def install_hooks(self):
        return self.hooks_mgr.install()

    def center_window(self):
        self.controller.center_window()

    def simulate(self, scenario: str = "multi"):
        self.controller.simulate_scenario(scenario)

    def dismiss_session(self, session_id: str):
        self.controller.dismiss_session(session_id)

    def save_settings(self, settings_json: str):
        self.controller.save_settings(settings_json)

    def get_settings(self):
        return self.controller.load_settings()


class VibeHudApp:
    def __init__(self):
        self.window = None
        self.api = VibeHudApi(self)
        self.server = None
        self.sessions = {}  # session_id -> dict
        self.ui_dir = Path(__file__).parent / "ui"
        self.config_dir = Path.home() / ".vibe-hud"
        self.settings_file = self.config_dir / "settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        self.server = HudServer(on_event=self.handle_incoming_event)
        self.server.start()

        index_html = self.ui_dir / "index.html"

        self.window = webview.create_window(
            "Vibe HUD",
            url=str(index_html.resolve()),
            js_api=self.api,
            width=280,
            height=62,
            x=600,
            y=40,
            frameless=True,
            on_top=True,
            transparent=True,
            easy_drag=True,
        )

        webview.start(self.on_loaded, debug=False)

    def on_loaded(self):
        try:
            if sys.platform == "darwin":
                from AppKit import (
                    NSApp,
                    NSFloatingWindowLevel,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                )
                NSApp.setActivationPolicy_(1)

                for win in NSApp.windows():
                    win.setLevel_(NSFloatingWindowLevel)
                    behavior = win.collectionBehavior()
                    win.setCollectionBehavior_(
                        behavior | NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
        except Exception as e:
            print(f"[vibe-hud] Warning configuring window level: {e}")

        # Send initial settings
        settings = self.load_settings()
        if self.window:
            self.window.evaluate_js(f"if (window.applySettings) window.applySettings({json.dumps(settings)})")

    def resize_window(self, expanded: bool):
        if self.window:
            if expanded:
                self.window.resize(380, 420)
            else:
                self.window.resize(280, 62)

    def center_window(self):
        if self.window:
            self.window.move(600, 40)

    def load_settings(self) -> dict:
        default_settings = {
            "theme": "dark-glass",
            "soundEnabled": True,
            "soundStyle": "marimba",
            "soundVolume": 0.8,
            "autoDismissSec": 60,
            "alwaysOnTop": True
        }
        if self.settings_file.exists():
            try:
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
                default_settings.update(data)
            except Exception:
                pass
        return default_settings

    def save_settings(self, settings_json: str):
        try:
            data = json.loads(settings_json) if isinstance(settings_json, str) else settings_json
            self.settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[vibe-hud] Error saving settings: {e}")

    def dismiss_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.broadcast_state()

    def handle_incoming_event(self, payload: dict):
        event_name = payload.get("hook_event_name", "").lower()
        explicit_status = payload.get("status")

        # Resolve session identifier
        session_id = payload.get("session_id")
        cwd = payload.get("cwd") or ""
        repo_name = Path(cwd).name if cwd else "Terminal"

        if not session_id:
            session_id = cwd if cwd else "default_session"

        now = int(time.time() * 1000)

        # Initialize session entry if new
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "id": session_id,
                "cwd": cwd,
                "repo_name": repo_name,
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
        s["last_updated"] = now

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
            s["detail"] = f"Finished in {s["duration"]}s" if s.get("duration") else "Finished turn"
        elif event_name == "sessionstart":
            s["status"] = "idle"
            s["title"] = f"{repo_name}: Ready"

        self.broadcast_state()

    def simulate_scenario(self, scenario: str):
        now = int(time.time() * 1000)
        if scenario == "multi":
            self.sessions = {
                "sess_backend": {
                    "id": "sess_backend",
                    "cwd": "/Users/dev/repo/sight3-backend",
                    "repo_name": "sight3-backend",
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
                    "cwd": "/Users/dev/repo/sight3-client",
                    "repo_name": "sight3-client",
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
                    "cwd": "/Users/dev/repo/data-platform",
                    "repo_name": "data-platform",
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
            # Priority order: attention > working > complete > idle
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
