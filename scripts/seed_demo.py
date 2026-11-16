"""Optional sample tasks for demo/screenshots. Run: python scripts/seed_demo.py"""
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain import validate_task
from storage import TaskStore

root = Path(__file__).resolve().parents[1]
store = TaskStore(root / "focusboard.db")
if store.all():
    print("Database already contains tasks; no demo data added.")
    raise SystemExit(0)

for title, course, offset, priority in (
    ("Finish Python API assignment", "Software Engineering", 1, "High"),
    ("Review database normalization", "Databases", 3, "Medium"),
    ("Prepare slides for AI exam", "AI Development", 5, "High"),
    ("Read chapter 6 and take notes", "Algorithms", 8, "Low"),
):
    store.create(validate_task({
        "title": title, "course": course,
        "due_date": (date.today() + timedelta(days=offset)).isoformat(),
        "priority": priority,
    }))
print("Added 4 sample tasks to focusboard.db")
