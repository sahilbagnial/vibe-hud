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

    def simulate(self, state: str):
        self.controller.update_state(state, message=f"Simulated {state}")


class VibeHudApp:
    def __init__(self):
        self.window = None
        self.api = VibeHudApi(self)
        self.server = None
        self.current_status = "idle"
        self.started_at = None
        self.ui_dir = Path(__file__).parent / "ui"

    def start(self):
        # Start embedded local HTTP server for Claude Code hooks
        self.server = HudServer(on_event=self.handle_incoming_event)
        self.server.start()

        index_html = self.ui_dir / "index.html"

        # Create frameless, transparent, always-on-top window
        self.window = webview.create_window(
            "Vibe HUD",
            url=str(index_html.resolve()),
            js_api=self.api,
            width=260,
            height=60,
            x=600,
            y=40,
            frameless=True,
            on_top=True,
            transparent=True,
            easy_drag=True,
        )

        webview.start(self.on_loaded, debug=False)

    def on_loaded(self):
        # Make it stay on top across all macOS workspaces / full-screen spaces
        try:
            if sys.platform == "darwin":
                from AppKit import (
                    NSApp,
                    NSFloatingWindowLevel,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                )
                # Hide dock icon for sleek ambient widget
                NSApp.setActivationPolicy_(1) # NSApplicationActivationPolicyAccessory

                for win in NSApp.windows():
                    win.setLevel_(NSFloatingWindowLevel)
                    behavior = win.collectionBehavior()
                    win.setCollectionBehavior_(
                        behavior | NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
        except Exception as e:
            print(f"[vibe-hud] Warning: Could not configure macOS window level: {e}")

    def resize_window(self, expanded: bool):
        if self.window:
            if expanded:
                self.window.resize(340, 360)
            else:
                self.window.resize(260, 60)

    def center_window(self):
        if self.window:
            self.window.move(600, 40)

    def handle_incoming_event(self, payload: dict):
        event_name = payload.get("hook_event_name", "").lower()
        explicit_status = payload.get("status")

        if explicit_status:
            self.update_state(explicit_status, payload)
            return

        if event_name == "userpromptsubmit":
            prompt = payload.get("prompt", "")
            title = f"Thinking: {prompt[:45]}..." if prompt else "Claude is thinking..."
            self.update_state("working", title=title, detail=prompt, tool_name="PROMPT")
        elif event_name == "pretooluse":
            tool = payload.get("tool_name", "Tool")
            self.update_state("working", title=f"Running {tool}...", detail=f"Executing {tool}", tool_name=tool)
        elif event_name == "posttooluse":
            tool = payload.get("tool_name", "Tool")
            self.update_state("working", title="Thinking...", detail=f"Finished {tool}", tool_name=tool)
        elif event_name == "notification":
            self.update_state("attention", title="Needs Input", detail=payload.get("message", "Confirmation needed"))
        elif event_name == "stop":
            self.update_state("complete", title="Turn Complete", detail="Waiting for next prompt")
        elif event_name == "sessionstart":
            self.update_state("idle", title="Vibe HUD Ready", detail="Session active")

    def update_state(self, status: str, payload: dict = None, title: str = None, detail: str = None, tool_name: str = None):
        now = int(time.time() * 1000)

        if status == "working":
            if self.current_status != "working":
                self.started_at = now
            duration = None
        elif status == "complete":
            duration = int((now - self.started_at) / 1000) if self.started_at else None
        else:
            duration = None
            self.started_at = None

        self.current_status = status

        state_data = {
            "status": status,
            "title": title or (payload.get("title") if payload else None) or f"Claude {status.capitalize()}",
            "detail": detail or (payload.get("detail") or payload.get("message") if payload else None) or "",
            "tool_name": tool_name or (payload.get("tool_name") if payload else None),
            "prompt": payload.get("prompt") if payload else None,
            "started_at": self.started_at,
            "duration": duration,
            "timestamp": now,
        }

        if self.window:
            js = f"window.updateState({json.dumps(state_data)})"
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass
