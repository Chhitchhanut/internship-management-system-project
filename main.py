from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers import  auth, student, mentor, admin
from app.database.connection import engine
from app.database import models
import os
from sqlalchemy import text

app = FastAPI(title="Internship Management System")

# Create DB tables on startup (server process only)
@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)
    try:
        print(f"[Startup] Using SQLite DB at: {engine.url.database}")
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            # Check columns in users table
            cols = conn.execute(text("PRAGMA table_info('users')")).fetchall()
            col_names = {c[1] for c in cols}
            if 'profile_photo_url' not in col_names:
                conn.execute(text("ALTER TABLE users ADD COLUMN profile_photo_url VARCHAR"))
            if 'cv_url' not in col_names:
                conn.execute(text("ALTER TABLE users ADD COLUMN cv_url VARCHAR"))
            # Check columns in internships table
            cols_int = conn.execute(text("PRAGMA table_info('internships')")).fetchall()
            int_col_names = {c[1] for c in cols_int}
            if 'requirements' not in int_col_names:
                conn.execute(text("ALTER TABLE internships ADD COLUMN requirements TEXT"))
            conn.commit()
    except Exception:
        pass

# Jinja2 templates for HTML rendering
templates = Jinja2Templates(directory="app/templates")

# Ensure static directory exists before mounting
os.makedirs("static", exist_ok=True)

# Serve static files (for uploads, assets)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(mentor.router)
app.include_router(admin.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup")
def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})