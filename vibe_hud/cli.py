import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from vibe_hud.core.hooks import HooksManager


def detect_terminal_info():
    env = os.environ
    term_program = env.get("TERM_PROGRAM", "")
    iterm_session = env.get("ITERM_SESSION_ID", "")
    # __CFBundleIdentifier is the only reliable way to tell VS Code-family IDEs
    # apart: their integrated terminals all report app_name as "Electron" at
    # the OS process level (see detect_terminal_info's ps walk below), and
    # TERM_PROGRAM is just "vscode" for all of them (VS Code, Cursor,
    # Windsurf, Antigravity, ...). JetBrains terminals are identified by
    # TERMINAL_EMULATOR instead.
    bundle_id = env.get("__CFBundleIdentifier", "")
    terminal_emulator = env.get("TERMINAL_EMULATOR", "")

    app_pid = None
    app_name = None
    curr = os.getppid()

    while curr > 1:
        try:
            out = subprocess.check_output(["ps", "-p", str(curr), "-o", "ppid=,comm="]).decode().strip()
            if not out:
                break
            parts = out.split(None, 1)
            ppid = int(parts[0])
            comm = parts[1] if len(parts) > 1 else ""
            if ppid == 1:
                app_pid = curr
                app_name = Path(comm).name
                break
            curr = ppid
        except Exception:
            break

    return {
        "term_program": term_program,
        "iterm_session": iterm_session,
        "bundle_id": bundle_id,
        "terminal_emulator": terminal_emulator,
        "app_pid": app_pid,
        "app_name": app_name,
    }


DEFAULT_PORT = 28790


def _resolve_port() -> int:
    """The running app writes its actual bound port here (it may not be
    DEFAULT_PORT if that port was already taken by another instance)."""
    port_file = Path.home() / ".vibe-hud" / "port"
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except Exception:
        return DEFAULT_PORT


def send_event(payload: dict) -> bool:
    port = _resolve_port()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.3):
            return True
    except Exception:
        try:
            state_dir = Path.home() / ".claude-hud"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass
        return False


def hook():
    """Claude Code lifecycle hook entry point."""
    raw_input = ""
    try:
        if not sys.stdin.isatty():
            raw_input = sys.stdin.read()
    except Exception:
        pass

    payload = {}
    if raw_input and raw_input.strip():
        try:
            payload = json.loads(raw_input)
        except Exception:
            payload = {"message": raw_input.strip()}

    if len(sys.argv) > 1:
        arg_status = sys.argv[1].lower()
        if arg_status in ["working", "idle", "attention", "complete"]:
            payload["status"] = arg_status
        if len(sys.argv) > 2:
            payload["message"] = " ".join(sys.argv[2:])

    if "cwd" not in payload:
        payload["cwd"] = os.getcwd()

    payload.update(detect_terminal_info())
    payload["timestamp"] = int(time.time() * 1000)
    send_event(payload)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        prog="vibe-hud",
        description="Universal ambient status light for AI coding agents",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("start", help="Start Vibe HUD floating app")
    subparsers.add_parser("hook", help="Run Claude Code hook dispatcher")
    subparsers.add_parser("install", help="Configure hooks in ~/.claude/settings.json")
    subparsers.add_parser("remove", help="Remove hooks from ~/.claude/settings.json")
    subparsers.add_parser("status", help="Check hooks configuration status")
    sim_p = subparsers.add_parser("simulate", help="Run simulated agent lifecycle")
    sim_p.add_argument("scenario", nargs="?", default="multi", choices=["single", "multi"], help="Scenario to simulate")

    parser.add_argument("state", nargs="?", choices=["working", "attention", "complete", "idle", "start"], help="Trigger state")
    parser.add_argument("message", nargs="*", help="Optional status message")

    args = parser.parse_args()
    mgr = HooksManager()

    if args.command == "install":
        res = mgr.install()
        message = res["message"]
        if res["success"]:
            print(f"✅ {message}")
            backup = res.get("backup")
            if backup:
                print(f"📦 Backup created at: {backup}")
        else:
            print(f"❌ {message}")
    elif args.command == "remove":
        res = mgr.remove()
        icon = "✅" if res["success"] else "❌"
        print(f"{icon} {res['message']}")
    elif args.command == "status":
        configured = mgr.is_configured()
        status_text = "Configured ✅" if configured else "Not configured ❌"
        print(f"[vibe-hud] Hooks status: {status_text}")
        print(f"[vibe-hud] Settings path: {mgr.settings_path}")
    elif args.command == "hook":
        hook()
    elif args.command == "simulate":
        term_info = detect_terminal_info()
        if args.scenario == "multi":
            print("Running Multi-Session Simulation (3 Terminals):")
            print("➔ Terminal 1: data-platform (Prompt submitted)")
            p1 = {
                "session_id": "sess_1_data",
                "cwd": "/Users/sahilbagnial/Desktop/repo/data-platform",
                "hook_event_name": "UserPromptSubmit",
                "prompt": "Run database migrations and seed dev users",
            }
            p1.update(term_info)
            send_event(p1)
            time.sleep(1.5)

            print("➔ Terminal 2: sight3-backend (Tool execution)")
            p2 = {
                "session_id": "sess_2_backend",
                "cwd": "/Users/sahilbagnial/Desktop/repo/sight3-backend",
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
            }
            p2.update(term_info)
            send_event(p2)
            time.sleep(1.5)

            print("➔ Terminal 3: sight3-client (Needs permission)")
            p3 = {
                "session_id": "sess_3_client",
                "cwd": "/Users/sahilbagnial/Desktop/repo/sight3-client",
                "hook_event_name": "Notification",
                "message": "Approve running `npm install`?",
            }
            p3.update(term_info)
            send_event(p3)
            time.sleep(2.0)

            print("➔ Terminal 1: data-platform (Complete)")
            p1_stop = {
                "session_id": "sess_1_data",
                "cwd": "/Users/sahilbagnial/Desktop/repo/data-platform",
                "hook_event_name": "Stop",
            }
            p1_stop.update(term_info)
            send_event(p1_stop)
            print("Multi-session simulation events dispatched! Click any terminal card to jump to it.")
        else:
            print("Running Single Session Simulation:")
            p = {"hook_event_name": "UserPromptSubmit", "prompt": "Refactor auth module"}
            p.update(term_info)
            send_event(p)
            time.sleep(2)
            p_tool = {"hook_event_name": "PreToolUse", "tool_name": "Bash"}
            p_tool.update(term_info)
            send_event(p_tool)
            time.sleep(2)
            p_stop = {"hook_event_name": "Stop"}
            p_stop.update(term_info)
            send_event(p_stop)
            print("Single session simulation finished!")
    elif args.state and args.state != "start":
        msg = " ".join(args.message) if args.message else f"State changed to {args.state}"
        payload = {"status": args.state, "message": msg, "cwd": os.getcwd()}
        payload.update(detect_terminal_info())
        send_event(payload)
        print(f"Sent {args.state} state to Vibe HUD")
    else:
        from vibe_hud.window import VibeHudApp
        app = VibeHudApp()
        app.start()


if __name__ == "__main__":
    main()
