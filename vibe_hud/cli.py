import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from vibe_hud.hooks import HooksManager


def send_event(payload: dict) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:28790/event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.3):
            return True
    except Exception:
        # Fallback to state file
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
    subparsers.add_parser("simulate", help="Run simulated agent lifecycle")

    # Direct status trigger
    parser.add_argument("state", nargs="?", choices=["working", "attention", "complete", "idle", "start"], help="Trigger state")
    parser.add_argument("message", nargs="*", help="Optional status message")

    args = parser.parse_args()
    mgr = HooksManager()

    if args.command == "install":
        res = mgr.install()
        if res["success"]:
            print(f"✅ {res["message"]}")
            if res.get("backup"):
                print(f"📦 Backup created at: {res["backup"]}")
        else:
            print(f"❌ {res["message"]}")
    elif args.command == "remove":
        res = mgr.remove()
        print(f"✅ {res["message"]}" if res["success"] else f"❌ {res["message"]}")
    elif args.command == "status":
        configured = mgr.is_configured()
        print(f"[vibe-hud] Hooks status: {"Configured ✅" if configured else "Not configured ❌"}")
        print(f"[vibe-hud] Settings path: {mgr.settings_path}")
    elif args.command == "hook":
        hook()
    elif args.command == "simulate":
        print("Running Vibe HUD simulation:")
        print("1. Prompt submitted ➔ RED")
        send_event({"hook_event_name": "UserPromptSubmit", "prompt": "Refactor auth pipeline and tests"})
        time.sleep(2.5)
        print("2. Tool executing ➔ RED (BASH)")
        send_event({"hook_event_name": "PreToolUse", "tool_name": "Bash"})
        time.sleep(2.5)
        print("3. Human permission required ➔ AMBER")
        send_event({"hook_event_name": "Notification", "message": "Approve database migration?"})
        time.sleep(2.5)
        print("4. Turn complete ➔ EMERALD GREEN")
        send_event({"hook_event_name": "Stop"})
        print("Finished simulation!")
    elif args.state and args.state != "start":
        msg = " ".join(args.message) if args.message else f"State changed to {args.state}"
        send_event({"status": args.state, "message": msg})
        print(f"Sent {args.state} state to Vibe HUD")
    else:
        # Launch floating window
        from vibe_hud.window import VibeHudApp
        app = VibeHudApp()
        app.start()


if __name__ == "__main__":
    main()
