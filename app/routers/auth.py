from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.connection import get_db
from app.database.models import User, Internship, Application
import hashlib

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------
# Signup
# ---------------------
@router.post("/signup")
def signup_post(
    request: Request,
    role: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form("") ,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email_norm = (email or "").strip().lower()
    if role.strip().lower() != "student":
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Only students can sign up.", "email": email, "role": role, "name": name, "phone": phone},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    existing = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if existing:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already registered.", "email": email, "role": role, "name": name, "phone": phone},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    u = User(
        name=name.strip(),
        email=email_norm,
        role="student",
        phone=(phone or "").strip() or None,
        password_hash=hash_password((password or "").strip()),
        status="active",
    )
    db.add(u)
    db.commit()
    # Redirect to student dashboard so it can load full profile and context
    return RedirectResponse(url=f"/student_dash?student_id={u.id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------
# Login
# ---------------------
@router.post("/login")
def login_post(
    request: Request,
    role: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email_norm = (email or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "email": email, "role": role},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    password_norm = (password or "").strip()
    pw_ok = (user.password_hash == hash_password(password_norm)) or (user.password_hash == password_norm)
    if not pw_ok:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "email": email, "role": role},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # If student or mentor, redirect with ID so dashboards can prefill forms
    role_l = (user.role or "").lower()
    if role_l == "student":
        return RedirectResponse(url=f"/student_dash?student_id={user.id}", status_code=status.HTTP_303_SEE_OTHER)
    if role_l == "mentor":
        return RedirectResponse(url=f"/mentor_dash?mentor_id={user.id}", status_code=status.HTTP_303_SEE_OTHER)

    redirect_map = {
        "admin": "/admin_dash",
    }
    target = redirect_map.get(role_l, "/")
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
