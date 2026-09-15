import threading
import time
from pathlib import Path

SESSION_FIELDS_UPDATED_FROM_PAYLOAD = (
    "app_pid", "app_name", "bundle_id", "terminal_emulator", "app_exe_name",
)


class SessionStore:
    """Owns the in-memory session dict and the event-driven state machine.
    Pure Python — no pywebview/AppKit/platform imports — so it's unit
    testable without any GUI or OS dependency."""

    def __init__(self):
        self.sessions: dict = {}
        self._lock = threading.Lock()

    def apply_event(self, payload: dict) -> None:
        event_name = (payload.get("hook_event_name") or "").lower()
        explicit_status = payload.get("status")
        cwd = payload.get("cwd") or ""
        repo_name = Path(cwd).name if cwd else "Terminal"
        session_id = payload.get("session_id") or (cwd if cwd else "default_session")
        now = int(time.time() * 1000)

        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = self._new_session(session_id, cwd, repo_name, payload, now)

            s = self.sessions[session_id]
            s["cwd"] = cwd or s["cwd"]
            s["repo_name"] = repo_name or s["repo_name"]
            for field in SESSION_FIELDS_UPDATED_FROM_PAYLOAD:
                if payload.get(field):
                    s[field] = payload[field]
            if payload.get("term_program"):
                s["term_program"] = payload["term_program"]
            s["last_updated"] = now

            self._transition(s, event_name, explicit_status, payload, now, repo_name)

    @staticmethod
    def _new_session(session_id, cwd, repo_name, payload, now) -> dict:
        return {
            "id": session_id,
            "cwd": cwd,
            "repo_name": repo_name,
            "app_pid": payload.get("app_pid"),
            "app_name": payload.get("app_name"),
            "term_program": payload.get("term_program"),
            "bundle_id": payload.get("bundle_id"),
            "terminal_emulator": payload.get("terminal_emulator"),
            "app_exe_name": payload.get("app_exe_name"),
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

    @staticmethod
    def _transition(s, event_name, explicit_status, payload, now, repo_name) -> None:
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

    def dismiss(self, session_id: str) -> None:
        with self._lock:
            self.sessions.pop(session_id, None)

    def sweep_expired(self, auto_dismiss_sec) -> list:
        if not auto_dismiss_sec:
            return []
        now = int(time.time() * 1000)
        with self._lock:
            expired = [
                sid for sid, s in self.sessions.items()
                if s["status"] == "complete"
                and s.get("completed_at")
                and (now - s["completed_at"]) > auto_dismiss_sec * 1000
            ]
            for sid in expired:
                del self.sessions[sid]
        return expired

    def get(self, session_id: str):
        return self.sessions.get(session_id)

    def load_simulation(self, sessions: dict) -> None:
        with self._lock:
            self.sessions = sessions

    def to_state_data(self) -> dict:
        with self._lock:
            sessions_snapshot = list(self.sessions.values())

        if not sessions_snapshot:
            return {
                "aggregate_status": "idle",
                "headline_title": "Vibe HUD Ready",
                "headline_subtitle": "Standing by for Claude...",
                "active_tool": None,
                "active_timer": None,
                "sessions": [],
            }

        priority_order = {"attention": 4, "working": 3, "complete": 2, "idle": 1}
        sorted_sessions = sorted(
            sessions_snapshot,
            key=lambda s: (priority_order.get(s["status"], 0), s.get("last_updated", 0)),
            reverse=True,
        )
        top_session = sorted_sessions[0]
        aggregate_status = top_session["status"]

        now = int(time.time() * 1000)
        active_timer = None
        if top_session["status"] == "working" and top_session.get("started_at"):
            active_timer = int((now - top_session["started_at"]) / 1000)
        elif top_session["status"] == "complete" and top_session.get("duration"):
            active_timer = top_session["duration"]

        return {
            "aggregate_status": aggregate_status,
            "headline_title": top_session["title"],
            "headline_subtitle": top_session.get("detail", ""),
            "active_tool": top_session.get("tool_name"),
            "active_timer": active_timer,
            "active_session_id": top_session["id"],
            "sessions": sorted_sessions,
        }
