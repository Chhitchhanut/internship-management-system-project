from fastapi import APIRouter, Request, Depends, Form, status, Query, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import Internship, Application, User, Department, InternshipSupervision
from typing import Optional
import os
from uuid import uuid4
import hashlib

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/student_dash")
def student_dash(request: Request, student_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    internships = db.query(Internship).order_by(Internship.created_at.desc()).all()
    user_ctx = {"name": "Student"}
    applications = []
    applied_ids = []
    total_applied = 0
    total_pending = 0
    total_approved = 0
    total_rejected = 0
    departments = []
    active_internship = None

    if student_id is not None:
        student = db.query(User).filter(User.id == student_id).first()
        if student:
            user_ctx = {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "phone": student.phone,
                "department_id": student.department_id,
                "profile_photo_url": student.profile_photo_url,
                "cv_url": student.cv_url,
            }
            app_rows = (
                db.query(Application, Internship)
                .join(Internship, Application.internship_id == Internship.id)
                .filter(Application.student_id == student.id)
                .order_by(Application.applied_at.desc())
                .all()
            )
            applications = [
                {
                    "internship_id": i.id,
                    "title": i.title,
                    "company": i.company,
                    "location": i.location,
                    "applied_at": a.applied_at,
                    "status": a.status,
                }
                for a, i in app_rows
            ]
            applied_ids = [i.id for a, i in app_rows]

            # Stats
            total_applied = len(applications)
            for a, _ in app_rows:
                st = (a.status or '').lower()
                if st == 'approved':
                    total_approved += 1
                elif st == 'rejected':
                    total_rejected += 1
                else:
                    total_pending += 1
            departments = db.query(Department).order_by(Department.name.asc()).all()

            # Active internship via supervision (only when student's application is approved)
            sup = (
                db.query(InternshipSupervision, Internship)
                .join(Internship, Internship.id == InternshipSupervision.internship_id)
                .join(Application, Application.internship_id == Internship.id)
                .filter(
                    InternshipSupervision.student_id == student.id,
                    Application.student_id == student.id,
                    InternshipSupervision.active == True,
                    func.lower(Application.status) == 'approved',
                )
                .first()
            )
            if sup:
                supervision, intern = sup
                active_internship = {
                    "title": intern.title,
                    "company": intern.company,
                    "supervisor": (supervision.mentor.name if supervision.mentor else None),
                    "location": intern.location,
                    "start_date": intern.start_date,
                    "end_date": intern.end_date,
                }

    return templates.TemplateResponse(
        "student_dash.html",
        {
            "request": request,
            "user": user_ctx,
            "internships": internships,
            "applications": applications,
            "applied_ids": applied_ids,
            "total_applied": total_applied,
            "total_pending": total_pending,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "departments": departments,
            "active_internship": active_internship,
        },
    )


@router.post("/student/apply")
def apply_to_internship(
    request: Request,
    internship_id: int = Form(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    student = db.query(User).filter(User.id == student_id).first()
    if not internship or not student:
        return RedirectResponse(url="/student_dash", status_code=status.HTTP_303_SEE_OTHER)

    existing = (
        db.query(Application)
        .filter(Application.student_id == student_id, Application.internship_id == internship_id)
        .first()
    )
    if not existing:
        app = Application(student_id=student_id, internship_id=internship_id, status="pending", applied_at=func.now())
        db.add(app)
        db.commit()

    # Redirect to Applications section on the dashboard without using JS
    target = f"/student_dash?student_id={student_id}#section-applications"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)



@router.post("/student/profile/update")
def update_profile(
    request: Request,
    student_id: int = Form(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    password: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    cv: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        return RedirectResponse(url="/student_dash", status_code=status.HTTP_303_SEE_OTHER)

    # Update basic fields
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

    # Prepare upload dir
    base_dir = os.path.join("static", "uploads", "students", str(user.id))
    os.makedirs(base_dir, exist_ok=True)

    # Save photo if provided
    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1]
        filename = f"photo_{uuid4().hex}{ext}"
        path = os.path.join(base_dir, filename)
        with open(path, "wb") as f:
            f.write(photo.file.read())
        user.profile_photo_url = f"/static/uploads/students/{user.id}/{filename}"

    # Save CV if provided
    if cv and cv.filename:
        ext = os.path.splitext(cv.filename)[1]
        filename = f"cv_{uuid4().hex}{ext}"
        path = os.path.join(base_dir, filename)
        with open(path, "wb") as f:
            f.write(cv.file.read())
        user.cv_url = f"/static/uploads/students/{user.id}/{filename}"

    db.add(user)
    db.commit()

    target = f"/student_dash?student_id={student_id}#section-profile"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/student/withdraw")
def withdraw_application(
    request: Request,
    internship_id: int = Form(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .filter(Application.student_id == student_id, Application.internship_id == internship_id)
        .first()
    )
    if app and (app.status or '').lower() == 'pending':
        db.delete(app)
        db.commit()

    target = f"/student_dash?student_id={student_id}#section-applications"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)

