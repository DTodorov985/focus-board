"""FocusBoard HTTP API and static frontend server. Run: python server.py"""
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from domain import ValidationError, validate_done, validate_task
from storage import TaskStore

ROOT = Path(__file__).resolve().parent
TASK_PATTERN = re.compile(r"^/api/tasks/([1-9][0-9]{0,18})$")


def task_id_from_path(path):
    match = TASK_PATTERN.fullmatch(path)
    if match:
        task_id = int(match.group(1))
        if task_id <= 2**63 - 1:
            return task_id
    return None


class FocusBoardHandler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _parse_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("Invalid Content-Length.") from exc
        if size <= 0 or size > 10_000:
            raise ValidationError("JSON body must be 1–10000 bytes.")
        try:
            return json.loads(self.rfile.read(size))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Invalid JSON body.") from exc

    def _static(self, relative_path, mime=None):
        path = (ROOT / relative_path).resolve()
        # Only files in the static directory and the index page are exposed.
        allowed = (path == ROOT / "static" / "index.html" or
                   path in {ROOT / "static" / "app.js", ROOT / "static" / "style.css"})
        if not allowed or not path.is_file():
            self._send(404, {"error": "Not found."})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or mimetypes.guess_type(path.name)[0] or "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/tasks":
            self._send(200, {"tasks": self.server.store.all()})
        elif path in ("/", "/index.html"):
            self._static("static/index.html", "text/html; charset=utf-8")
        elif path == "/static/app.js":
            self._static("static/app.js", "text/javascript; charset=utf-8")
        elif path == "/static/style.css":
            self._static("static/style.css", "text/css; charset=utf-8")
        else:
            self._send(404, {"error": "Not found."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/tasks":
            self._send(404, {"error": "Not found."})
            return
        try:
            task = self.server.store.create(validate_task(self._parse_json()))
            self._send(201, {"task": task})
        except ValidationError as exc:
            self._send(400, {"error": str(exc)})

    def do_PATCH(self):
        task_id = task_id_from_path(urlsplit(self.path).path)
        if task_id is None:
            self._send(404, {"error": "Not found."})
            return
        try:
            is_done = validate_done(self._parse_json())
            result = self.server.store.update_done(task_id, is_done)
            self._send(200, {"task": result}) if result else self._send(404, {"error": "Task not found."})
        except ValidationError as exc:
            self._send(400, {"error": str(exc)})

    def do_DELETE(self):
        task_id = task_id_from_path(urlsplit(self.path).path)
        if task_id is None:
            self._send(404, {"error": "Not found."})
            return
        deleted = self.server.store.delete(task_id)
        self._send(200 if deleted else 404, {"deleted": True} if deleted else {"error": "Task not found."})


def create_server(host="127.0.0.1", port=8000, db_path=None):
    httpd = ThreadingHTTPServer((host, port), FocusBoardHandler)
    try:
        httpd.store = TaskStore(db_path or (ROOT / "focusboard.db"))
    except Exception:
        httpd.server_close()
        raise
    return httpd


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    with create_server(host=host, port=port, db_path=os.getenv("DB_PATH")) as app:
        print(f"FocusBoard running at http://{host}:{app.server_port}", flush=True)
        try:
            app.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
