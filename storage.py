"""Small SQLite persistence layer: parameterized SQL, no third-party packages."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class TaskStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  course TEXT NOT NULL DEFAULT '',
                  due_date TEXT,
                  priority TEXT NOT NULL DEFAULT 'Medium',
                  is_done INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _as_task(row):
        if row is None:
            return None
        task = dict(row)
        task["is_done"] = bool(task["is_done"])
        return task

    def all(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks
                ORDER BY is_done ASC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                         due_date ASC, id DESC
            """).fetchall()
            return [self._as_task(row) for row in rows]

    def create(self, data):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, course, due_date, priority) VALUES (?, ?, ?, ?)",
                (data["title"], data["course"], data["due_date"], data["priority"]),
            )
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
            return self._as_task(row)

    def update_done(self, task_id, is_done):
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET is_done = ? WHERE id = ?", (int(is_done), task_id)
            )
            if not cur.rowcount:
                return None
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._as_task(row)

    def delete(self, task_id):
        with self._connect() as conn:
            return bool(conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount)
