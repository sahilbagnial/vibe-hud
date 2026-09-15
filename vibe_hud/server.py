import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Optional


class HudRequestHandler(BaseHTTPRequestHandler):
    on_event_callback: Optional[Callable[[dict], None]] = None

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "app": "vibe-hud"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ["/event", "/status", "/hook"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
                if HudRequestHandler.on_event_callback:
                    HudRequestHandler.on_event_callback(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "received": True}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class HudServer:
    def __init__(self, on_event: Callable[[dict], None], port: int = 28790):
        self.port = port
        self.on_event = on_event
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        HudRequestHandler.on_event_callback = self.on_event
        for p in range(self.port, self.port + 10):
            try:
                self.server = HTTPServer(("127.0.0.1", p), HudRequestHandler)
                self.port = p
                break
            except OSError:
                continue

        if not self.server:
            raise RuntimeError("Could not bind to local port for Vibe HUD server")

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"[vibe-hud] Local server running on http://127.0.0.1:{self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
