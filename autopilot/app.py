import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, data, status=200):
        self._send(status, json.dumps(data), "application/json")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._serve_static("app.js", "application/javascript")
        if path == "/styles.css":
            return self._serve_static("styles.css", "text/css")
        if path == "/api/summary":
            try:
                return self._json(engine.get_summary())
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if path == "/api/progress":
            return self._json(engine.get_progress())
        if path == "/api/refresh":
            try:
                return self._json(engine.refresh(force=True))
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        self._send(404, "Not found", "text/plain")

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/api/refresh":
            try:
                return self._json(engine.refresh(force=True))
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        self._send(404, "Not found", "text/plain")

    def _serve_static(self, filename, content_type):
        path = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(path):
            return self._send(404, "Missing static file", "text/plain")
        with open(path, "rb") as f:
            self._send(200, f.read(), content_type)

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Portfolio Autopilot running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
