# FocusBoard — Study Task Tracker

A dependency-free study task tracker built with Python, SQLite, HTML, CSS, and JavaScript.

## Run locally

Requires Python 3.9 or newer. No additional packages are needed.

```bash
python server.py
```

On Windows, you can use the Python launcher:

```powershell
py -3.13 server.py
```

Open http://127.0.0.1:8000. Stop the server with Ctrl+C. The SQLite database is created automatically and keeps tasks between restarts.

Optional sample data, while the database is empty:

```bash
python scripts/seed_demo.py
```

Configuration uses the `HOST`, `PORT`, and `DB_PATH` environment variables. For example, in PowerShell:

```powershell
$env:PORT = '8080'
py -3.13 server.py
```

The default host is `127.0.0.1`. The application is intended for local, single-user use and does not provide authentication.

## Features

- Create tasks with a title, course, optional due date, and priority.
- Search titles and courses as you type, ignoring case.
- Combine search with All, To do, and Completed filters.
- Mark tasks complete or incomplete and delete tasks with confirmation.
- View totals and completion progress across all tasks, regardless of filters.
- Save tasks in SQLite and validate input on the server.
- Use the dashboard on desktop and mobile screens.

## Architecture

- `server.py`: serves the frontend and JSON API using Python's threaded HTTP server.
- `domain.py`: validates and normalizes task fields and completion updates.
- `storage.py`: manages SQLite connections and parameterized SQL operations.
- `static/index.html`: dashboard structure and forms.
- `static/app.js`: browser state, rendering, search, filters, and API requests.
- `static/style.css`: dashboard styling and responsive layout.
- `scripts/seed_demo.py`: optional sample task generator.
- `tests/test_app.py`: validation, storage, HTTP, and startup regression tests.

Creation flows from the browser through the HTTP handler, domain validation, and SQLite repository. The server returns JSON; the browser reloads task data and updates the dashboard. Search and status filtering happen in the browser.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/tasks` | List tasks |
| POST | `/api/tasks` | Create a task |
| PATCH | `/api/tasks/{id}` | Update `is_done` |
| DELETE | `/api/tasks/{id}` | Delete a task |

## Tests

```bash
python -m unittest discover -s tests -v
```

On Windows:

```powershell
py -3.13 -m unittest discover -s tests -v
```

The 24 tests cover validation boundaries, dates, persistence, ordering, rollback, malformed requests, body limits, task IDs, static-file restrictions, and startup cleanup. Database tests use temporary databases and do not change your saved tasks. HTTP tests start a local server on an automatically selected port. The suite does not automate browser interactions.

GitHub Actions runs the suite on pushes and pull requests using Python 3.9 and 3.13 on Linux and Windows.

## Repository contents

The `.gitignore` excludes local databases, SQLite journal files, Python caches, virtual environments, and temporary directories. The database is regenerated when the app starts.

The `screenshots/` directory contains earlier dashboard examples; those images predate the search field. `PROMPT_LOG.md` records AI-assisted work from this development session.
