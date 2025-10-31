from fastapi import APIRouter, Request, Depends, Query, Form, UploadFile, File, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import User, Department
from typing import Optional
import hashlib
import os
from uuid import uuid4

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/mentor_dash")
def mentor_dash(request: Request, mentor_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    user_ctx = {"name": "Mentor"}
    departments = []

    if mentor_id is not None:
        mentor = db.query(User).filter(User.id == mentor_id).first()
        if mentor:
            user_ctx = {
                "id": mentor.id,
                "name": mentor.name,
                "email": mentor.email,
                "phone": mentor.phone,
                "department_id": mentor.department_id,
                "profile_photo_url": mentor.profile_photo_url,
            }
            departments = db.query(Department).order_by(Department.name.asc()).all()

    return templates.TemplateResponse("mentor_dash.html", {"request": request, "user": user_ctx, "departments": departments})


@router.post("/mentor/profile/update")
def update_profile(
    request: Request,
    mentor_id: int = Form(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    password: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == mentor_id).first()
    if not user:
        return RedirectResponse(url="/mentor_dash", status_code=status.HTTP_303_SEE_OTHER)

    if name is not None and name.strip():
        user.name = name.strip()
    if email is not None and email.strip():
        user.email = email.strip()
    if phone is not None:
        user.phone = phone.strip() if phone else None
    if password is not None and password.strip():
        user.password_hash = hashlib.sha256(password.strip().encode("utf-8")).hexdigest()
    if department_id:
        user.department_id = department_id

    # Save photo if provided
    if photo and photo.filename:
        base_dir = os.path.join("static", "uploads", "mentors", str(user.id))
        os.makedirs(base_dir, exist_ok=True)
        ext = os.path.splitext(photo.filename)[1]
        filename = f"photo_{uuid4().hex}{ext}"
        path = os.path.join(base_dir, filename)
        with open(path, "wb") as f:
            f.write(photo.file.read())
        user.profile_photo_url = f"/static/uploads/mentors/{user.id}/{filename}"

    db.add(user)
    db.commit()

    target = f"/mentor_dash?mentor_id={mentor_id}#profile"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
