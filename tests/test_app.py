"""Run with: python -m unittest discover -s tests -v"""
import json
import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request
from unittest.mock import patch

from domain import ValidationError, validate_done, validate_task
from server import create_server
from storage import TaskStore


class TestValidation(unittest.TestCase):
    def test_length_boundaries_and_defaults(self):
        for size in (1, 80):
            with self.subTest(size=size):
                item = validate_task({"title": " " + "x" * size + " ", "course": " c" + "x" * 39 + " "})
                self.assertEqual(len(item["title"]), size)
                self.assertEqual(len(item["course"]), 40)
                self.assertEqual(item["priority"], "Medium")
        for payload in ({}, {"title": "x" * 81}, {"title": None},
                        {"title": 123}, {"title": "x", "course": "x" * 41},
                        {"title": "x", "course": None},
                        {"title": "x", "priority": []}, None, [], "task"):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                validate_task(payload)

    def test_date_formats_and_leap_years(self):
        for value in (None, "", "2024-02-29"):
            with self.subTest(value=value):
                self.assertEqual(validate_task({"title": "Read", "due_date": value})["due_date"], value or None)
        for value in ("2025-02-29", "20260101", "2026-W01-1", "2026-1-01", "2026-01-01T00:00:00", 123, []):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_task({"title": "Read", "due_date": value})

    def test_completion_types_and_missing_value(self):
        for value in (True, False):
            self.assertIs(validate_done({"is_done": value}), value)
        for payload in ({}, None, [], {"is_done": 0}, {"is_done": 1}, {"is_done": None}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                validate_done(payload)

    def test_valid_task_normalizes_whitespace(self):
        item = validate_task({"title": "  Read notes  ", "course": " Math ", "priority": "High"})
        self.assertEqual(item["title"], "Read notes")
        self.assertEqual(item["course"], "Math")
        self.assertIsNone(item["due_date"])

    def test_blank_title_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "Title"):
            validate_task({"title": "   "})

    def test_invalid_date_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "Due date"):
            validate_task({"title": "Read", "due_date": "2026-02-30"})

    def test_invalid_priority_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "Priority"):
            validate_task({"title": "Read", "priority": "Urgent"})

    def test_completion_requires_a_boolean(self):
        with self.assertRaises(ValidationError):
            validate_done({"is_done": "true"})


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.db"
        self.store = TaskStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_then_list(self):
        task = self.store.create(validate_task({"title": "Practice SQL"}))
        self.assertEqual(self.store.all()[0]["id"], task["id"])
        self.assertFalse(task["is_done"])

    def test_toggle_and_delete(self):
        task = self.store.create(validate_task({"title": "Read chapter"}))
        updated = self.store.update_done(task["id"], True)
        self.assertTrue(updated["is_done"])
        self.assertTrue(self.store.delete(task["id"]))
        self.assertEqual(self.store.all(), [])

    def test_missing_id_is_not_updated(self):
        self.assertIsNone(self.store.update_done(9999, True))

    def test_reopening_preserves_unicode_and_sql_like_text(self):
        title = "Read '); DROP TABLE tasks; -- π"
        task = self.store.create(validate_task({"title": title, "course": "Математика", "due_date": "2024-02-29"}))
        reopened = TaskStore(self.path)
        self.assertEqual(reopened.all(), [task])
        self.assertEqual(task["title"], title)
        self.assertFalse(reopened.update_done(task["id"], False)["is_done"])
        self.assertTrue(reopened.delete(task["id"]))
        self.assertFalse(reopened.delete(task["id"]))
        self.assertEqual(TaskStore(self.path).all(), [])

    def test_ordering_completion_dates_and_ties(self):
        def add(title, due=None):
            return self.store.create(validate_task({"title": title, "due_date": due}))
        done = add("done", "2020-01-01")
        self.store.update_done(done["id"], True)
        add("undated")
        add("later", "2026-12-01")
        add("earlier", "2026-01-01")
        add("same date newer", "2026-01-01")
        self.assertEqual([t["title"] for t in self.store.all()],
                         ["same date newer", "earlier", "later", "undated", "done"])

    def test_failed_transaction_is_rolled_back(self):
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with self.store._connect() as conn:
                conn.execute("INSERT INTO tasks (title) VALUES (?)", ("Uncommitted",))
                raise RuntimeError("abort")
        self.assertEqual(self.store.all(), [])


class TestHTTPAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.server = create_server(port=0, db_path=Path(cls.temp.name) / "api.db")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def stop_server(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        for task in self.server.store.all():
            self.server.store.delete(task["id"])

    def raw_request(self, method, path, body=b"", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_malformed_json_and_body_limits(self):
        for body, headers in ((b"{", {}), (b"\xff", {}), (b"[]", {}),
                              (b"", {}), (b"x" * 10001, {}),
                              (b"", {"Content-Length": "invalid"}),
                              (b"", {"Content-Length": "-1"})):
            with self.subTest(body=body[:20], headers=headers):
                status, _, data = self.raw_request("POST", "/api/tasks", body, headers)
                self.assertEqual(status, 400)
                self.assertIn("error", json.loads(data))
        self.assertEqual(self.server.store.all(), [])

    def test_exact_body_size_limit(self):
        body = b'{"title":"Read"}'
        status, _, _ = self.raw_request("POST", "/api/tasks", body + b" " * (10000 - len(body)))
        self.assertEqual(status, 201)

    def test_invalid_ids_and_missing_deletes(self):
        for task_id in ("0", "-1", "01", "abc", str(2**63), "9" * 5000):
            for method in ("PATCH", "DELETE"):
                with self.subTest(task_id=task_id[:30], method=method):
                    code, _ = self.call_api(method, f"/api/tasks/{task_id}", {"is_done": True} if method == "PATCH" else None)
                    self.assertEqual(code, 404)
        self.assertEqual(self.call_api("DELETE", "/api/tasks/999999")[0], 404)

    def test_invalid_patch_does_not_change_task(self):
        _, data = self.call_api("POST", "/api/tasks", {"title": "Read"})
        task_id = data["task"]["id"]
        for payload in ({}, {"is_done": 1}, {"is_done": "false"}):
            self.assertEqual(self.call_api("PATCH", f"/api/tasks/{task_id}", payload)[0], 400)
        self.assertFalse(self.server.store.all()[0]["is_done"])

    def test_static_allowlist_and_response_headers(self):
        for path, mime in (("/", "text/html"), ("/static/app.js", "text/javascript"), ("/static/style.css", "text/css")):
            status, headers, body = self.raw_request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(mime, headers["Content-Type"])
            self.assertEqual(int(headers["Content-Length"]), len(body))
        for path in ("/server.py", "/focusboard.db", "/static/../storage.py", "/unknown"):
            self.assertEqual(self.call_api("GET", path)[0], 404)
        status, headers, body = self.raw_request("GET", "/api/tasks?filter=all")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(body), {"tasks": []})

    def call_api(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(self.base + path, data=body, method=method,
                              headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except error.HTTPError as response:
            return response.code, json.load(response)

    def test_create_list_and_complete_through_http(self):
        code, data = self.call_api("POST", "/api/tasks", {"title": "Finish AI exam", "priority": "High"})
        self.assertEqual(code, 201)
        task_id = data["task"]["id"]
        code, data = self.call_api("PATCH", f"/api/tasks/{task_id}", {"is_done": True})
        self.assertEqual(code, 200)
        self.assertTrue(data["task"]["is_done"])
        code, data = self.call_api("GET", "/api/tasks")
        self.assertEqual(code, 200)
        self.assertTrue(any(item["id"] == task_id for item in data["tasks"]))
        code, data = self.call_api("DELETE", f"/api/tasks/{task_id}")
        self.assertEqual(code, 200)
        self.assertTrue(data["deleted"])

    def test_invalid_input_returns_http_400(self):
        code, data = self.call_api("POST", "/api/tasks", {"title": ""})
        self.assertEqual(code, 400)
        self.assertIn("Title", data["error"])

    def test_missing_resource_returns_http_404(self):
        code, _ = self.call_api("PATCH", "/api/tasks/999999", {"is_done": True})
        self.assertEqual(code, 404)

    def test_index_is_served(self):
        with request.urlopen(self.base + "/", timeout=3) as res:
            self.assertIn("FocusBoard", res.read().decode("utf-8"))


class TestServerStartup(unittest.TestCase):
    def test_database_failure_closes_server_socket(self):
        with patch("server.ThreadingHTTPServer") as http_server, patch("server.TaskStore", side_effect=OSError("database unavailable")):
            with self.assertRaisesRegex(OSError, "database unavailable"):
                create_server(port=0)
            http_server.return_value.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
