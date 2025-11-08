# Internship Management System

A lightweight internship management system built with FastAPI, SQLAlchemy and Jinja2 templates.
It provides student, mentor and admin dashboards, internship postings, application workflows, task assignment, and file uploads (profile photos and CVs). By default it uses an SQLite database stored at the project root.

---

## Features

- Role-based accounts: student, mentor, admin
- Student signup and role-aware login redirects
- Admin user management (create / update / delete users)
- Departments (create / attach to users)
- Internships: create / update / delete postings
- Student applications with duplicate checks
- Application workflow: admin approve / reject, student withdraw
- Internship supervision linking mentors ↔ students ↔ internships
- Task assignments with feedback, rating and status
- Reports and notifications stored in the database models
- File uploads for profile photos and CVs (saved under `static/uploads/...`)
- Server-rendered dashboards using Jinja2 templates for admin, mentor and student
- Search, filtering and pagination support in admin dashboard
- SQLite backend with automatic table creation and light schema adjustments on startup

## Quick start (development)

Prerequisites

- Python 3.10+ (recommended)
- Git

Recommended Python packages (example). Use a virtual environment for development.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy jinja2 python-multipart
```

Run the app (from the repository root):

```powershell
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

Notes:

- The application uses an SQLite file `intern_sys.db` created at the project root by default (see `app/database/connection.py`).
- Static files are served at `/static`. Uploads are saved to `static/uploads/...` and are accessible from that path.

## Project structure (important files)

- `main.py` — FastAPI application entrypoint; mounts routers and static files; creates DB tables on startup.
- `app/routers/` — route handlers for `auth`, `admin`, `mentor`, and `student` flows.
- `app/database/connection.py` — SQLAlchemy engine, session factory, and `Base` declarative class.
- `app/database/models.py` — ORM models: `User`, `Internship`, `Application`, `Task`, `Report`, `Notification`, etc.
- `app/templates/` — Jinja2 HTML templates (dashboards, login, signup pages).
- `static/` — CSS and `uploads/` for user files.

## Configuration & environment

- Database path is configured in `app/database/connection.py` and points to `intern_sys.db` by default. For production, switch to a production-grade RDBMS (Postgres) and follow env-driven configuration.

## Security notes (please review)

- Password hashing currently uses SHA-256 (see `auth` router) and the login logic also accepts a plaintext fallback. This is insecure. Migrate to `passlib` (bcrypt or argon2) and remove any plaintext comparisons.
- There is no token-based or session-based authentication implemented; only simple form-based redirects by role. Add proper authentication (OAuth2 / JWT, or secure session cookies) and route protection for admin-only actions.
- File uploads are saved without strict validation. Add checks for allowed MIME types, maximum file size, and sanitize filenames to avoid directory traversal or other risks.
- SQLite is fine for local development but not ideal for high-concurrency production. Use Postgres or another production-ready database and add migrations (Alembic) for schema management.

## Testing

- There are currently no automated tests. Add unit and integration tests using `pytest` and FastAPI's `TestClient`.

## Roadmap / Improvements

1. Replace SHA-256 hashing with `passlib` (bcrypt/argon2) and remove plaintext fallback.
2. Implement proper authentication and authorization (OAuth2 / JWT or secure session cookies).
3. Add Alembic for database migrations and stop using runtime ALTER PRAGMA checks.
4. Add file upload validation and size limits.
5. Add tests (smoke tests for signup, login, apply, approve, upload) and CI integration.
6. Provide a `requirements.txt` or `pyproject.toml` and optionally a `Dockerfile` / `docker-compose.yml` for reproducible development.

## Contributing

- Fork the repository, create a feature branch, add tests for new behavior, and open a pull request.
- Please include a clear description of changes and update this README or add migration notes as needed.

## License

Add a license file (for example `LICENSE` with the MIT license) or indicate the project's license here.

---

If you'd like, I can also add a `requirements.txt`, a simple `pytest` smoke test, or create a `Dockerfile` and `docker-compose.yml` to make local development reproducible. Tell me which you'd like next.
