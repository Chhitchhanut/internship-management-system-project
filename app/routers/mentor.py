from fastapi import APIRouter, Request, Depends, Query, Form, UploadFile, File, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.connection import get_db
from datetime import datetime
from app.database.models import User, Department, Task, InternshipSupervision
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

    return templates.TemplateResponse(
        "mentor_dash.html", 
        {
            "request": request, 
            "user": user_ctx, 
            "departments": departments,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "internship_sv_id": t.supervision_id,
                    "student_id": t.student_id,
                    "assigned_by": t.assigned_by,
                    "due_date": t.due_date,
                    "description": t.description,
                    "status": t.status,
                    "created_at": t.created_at,
                    "feedback": t.feedback,
                    "rating": t.rating,
                }
                for t in db.query(Task).order_by(Task.created_at.desc().nullslast()).all()
            ],
            "supervisions": [
                {
                    "id": s.id  ,
                    "internship_id": s.internship_id,
                    "mentor_id": s.mentor_id,
                    "student_id": s.student_id,
                }
                for s in db.query(InternshipSupervision).filter(InternshipSupervision.mentor_id == mentor_id).all()
            ] if mentor_id else [],
            "mentor_id": mentor_id,     
        },
    )


# Create Task Assignment
# ----------------------------
from fastapi import Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import InternshipSupervision, Task
from datetime import datetime

@router.post("/mentor/task_create")
def mentor_task_create(
    mentor_id: int = Form(...),
    student_id: int = Form(...),
    internship_sv_id: int = Form(...),
    title: str = Form(...),
    desc: str = Form(...),
    deadline: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Ensure the supervision exists and belongs to this mentor
    supervision = db.query(InternshipSupervision).filter(
        InternshipSupervision.id == internship_sv_id,
        InternshipSupervision.mentor_id == mentor_id,
        InternshipSupervision.student_id == student_id
    ).first()

    if not supervision:
        # not allowed — either wrong SV id, mentor mismatch, or student mismatch
        return RedirectResponse(url=f"/mentor_dash?mentor_id={mentor_id}", status_code=303)

    task = Task(
        title=title.strip(),
        description=desc.strip(),
        due_date=datetime.fromisoformat(deadline) if deadline else None,
        assigned_by=mentor_id,
        student_id=student_id,
        supervision_id=internship_sv_id,
        status="assigned",
        created_at=datetime.utcnow()
    )
    db.add(task)
    db.commit()

    target = f"/mentor_dash?mentor_id={mentor_id}#assign-tasks"
    return RedirectResponse(url=target, status_code=303)


# Delete Task Assignment
# ----------------------------
@router.post("/mentor/task_delete")
def mentor_task_delete(
    request: Request,
    task_id: int = Form(...),
    mentor_id: int = Form(...),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )
    if tasks:
        db.delete(tasks)
        db.commit()

    target = f"/mentor_dash?mentor_id={mentor_id}#assign-tasks"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


# Update Mentor Profile
# ----------------------------
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
