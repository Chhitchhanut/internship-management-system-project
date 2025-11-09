from sys import intern
from fastapi import APIRouter, Request, Depends, Form, status, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload
import time
import hashlib
from datetime import datetime
from typing import Optional
from app.database.connection import get_db, engine
from app.database.models import (
    InternshipSupervision,
    User,
    Internship,
    Department,
    Application,
    Task,
    Report,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/admin_dash")
def admin_dash(
    request: Request,
    edit: int | None = Query(None),
    edit_internship: int | None = Query(None),
    updated: int | None = Query(None),
    i_search_field: str | None = Query(None),
    i_q: str | None = Query(None),
    search_email: str | None = Query(None),  # legacy param support
    search_field: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Load and enrich supervisions without complex ORM aliasing
    supervisions = []
    for sv in db.query(InternshipSupervision).all():
        mentor = db.query(User).filter(User.id == sv.mentor_id).first()
        student = db.query(User).filter(User.id == sv.student_id).first() if sv.student_id else None
        internship = db.query(Internship).filter(Internship.id == sv.internship_id).first()
        supervisions.append({
            "id": sv.id,
            "mentor_id": sv.mentor_id,
            "mentor_name": mentor.name if mentor else None,
            "student_id": sv.student_id,
            "student_name": student.name if student else None,
            "internship_id": sv.internship_id,
            "internship_title": internship.title if internship else None,
            "active": sv.active,
            "scope_notes": sv.scope_notes,
        })

        applications = (
            db.query(Application)
            .options(
                joinedload(Application.student),     # load student relationship
                joinedload(Application.internship)   # load internship relationship
            )
            .all()
        )

        application_list = [
            {
                "id": a.id,
                "student_id": a.student_id,
                "student_email": a.student.email if a.student else None,           # <-- added
                "internship_id": a.internship_id,
                "internship_title": a.internship.title if a.internship else None,  # <-- added
                "status": a.status,
                "student_cv_url": a.student.cv_url if a.student else None,
            }
            for a in applications
        ]

        tasks = (
            db.query(Task)
            .options(
                joinedload(Task.student),                          # load student relationship
                joinedload(Task.internship_sv).joinedload(         # load supervision -> internship
                    InternshipSupervision.internship
                )
            )
            .order_by(Task.created_at.desc().nullslast())
            .all()
        )

        task_list = [
            {
                "id": t.id,
                "title": t.title,
                "internship_sv_id": t.supervision_id,
                "internship_title": t.internship_sv.internship.title if t.internship_sv and t.internship_sv.internship else None,  # added
                "student_id": t.student_id,
                "student_email": t.student.email if t.student else None,  # added
                "assigned_by": t.assigned_by,
                "assigned_by_email": db.query(User).filter(User.id == t.assigned_by).first().email if db.query(User).filter(User.id == t.assigned_by).first() else None,  # added
                "due_date": t.due_date,
                "description": t.description,
                "status": t.status,
            }
            for t in tasks
        ]

    edit_supervision = None
    if edit is not None:
        sv = db.query(InternshipSupervision).filter(InternshipSupervision.id == edit).first()
        if sv:
            edit_supervision = {
                "id": sv.id,
                "mentor_id": sv.mentor_id,
                "student_id": sv.student_id,
                "internship_id": sv.internship_id,
                "active": sv.active,
                "scope_notes": sv.scope_notes,
            }

    # Load departments for user creation form
    departments = db.query(Department).order_by(Department.name.asc()).all()
    # Load users for users table
    users = db.query(User).order_by(User.created_at.desc().nullslast()).all()
    # Load internships for postings table with optional search
    internships_query = db.query(Internship)
    i_q_norm = (i_q or "").strip()
    i_field_norm = (i_search_field or "").strip().lower()
    if i_q_norm:
        like = f"%{i_q_norm}%"
        if i_field_norm == "title":
            internships_query = internships_query.filter(Internship.title.like(like))
        elif i_field_norm == "company":
            internships_query = internships_query.filter(Internship.company.like(like))
        elif i_field_norm == "status":
            internships_query = internships_query.filter(Internship.status.like(like))
        else:
            internships_query = internships_query.filter(
                (Internship.title.like(like)) | (Internship.company.like(like)) | (Internship.status.like(like))
            )
    internships = internships_query.order_by(Internship.created_at.desc().nullslast()).all()
    applications = db.query(Application).order_by(Application.applied_at.desc().nullslast()).all()
    tt_students = db.query(User).filter(User.role == "student").count()
    tt_mentors = db.query(User).filter(User.role == "mentor").count()
    tt_active_interns = db.query(InternshipSupervision).count()
    tt_pending_appli = db.query(Application).filter(func.lower(Application.status) == "pending").count()


    # Prefill data for Update Internship form if requested
    edit_intern_ctx = None
    if edit_internship is not None:
        i = db.query(Internship).filter(Internship.id == edit_internship).first()
        if i:
            edit_intern_ctx = {
                "id": i.id,
                "title": i.title,
                "company": i.company,
                "location": i.location,
                "start_date": i.start_date,
                "end_date": i.end_date,
                "slots": i.slots,
                "status": i.status,
                "description": i.description,
                "requirements": getattr(i, "requirements", None),
            }

    # Unified search handling (supports legacy search_email)
    # Normalize incoming
    q_norm = (q or "").strip()
    field_norm = (search_field or "").strip().lower()
    if search_email and str(search_email).strip():
        q_norm = str(search_email).strip()
        field_norm = "email"

    # Constrain page_size to a friendly set
    if page_size not in (10, 20, 50):
        page_size = 10

    search_results = None
    search_total = None
    highlight_user_id: int | None = None
    effective_search = bool(q_norm)
    if effective_search:
        q_lower = q_norm.lower()
        query = db.query(User)
        if field_norm == "name":
            query = query.filter(func.lower(User.name).like(f"%{q_lower}%"))
        elif field_norm == "role":
            # exact role match among known roles
            if q_lower in ("student", "mentor", "admin"):
                query = query.filter(func.lower(User.role) == q_lower)
            else:
                # if role doesn't match allowed values, no results
                query = query.filter(func.lower(User.role) == "__no_match__")
        else:
            # default email partial match (case-insensitive)
            query = query.filter(func.lower(User.email).like(f"%{q_lower}%"))

        search_total = query.count()
        matched = (
            query.order_by(User.created_at.desc().nullslast())
                 .offset((page - 1) * page_size)
                 .limit(page_size)
                 .all()
        )
        search_results = [
            {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "status": u.status}
            for u in matched
        ]

    return templates.TemplateResponse(
        "admin_dash.html",
        {
            "request": request,
            "supervisions": supervisions,
            "edit_supervision": edit_supervision,
            "departments": [{"id": d.id, "name": d.name} for d in departments],
            "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "status": u.status} for u in users],
            "internships": [
                {
                    "id": i.id,
                    "title": i.title,
                    "company": i.company,
                    "start_date": i.start_date,
                    "end_date": i.end_date,
                    "status": i.status,
                }
                for i in internships
            ],
            "applications": application_list,
            "tasks": task_list,
            "edit_internship": edit_intern_ctx,
            "search_email": search_email,
            "search_field": field_norm or None,
            "q": q_norm or None,
            "page": page,
            "page_size": page_size,
            "search_results": search_results,
            "search_total": search_total,
            "highlight_user_id": highlight_user_id,
            "updated": bool(updated),
            "i_search_field": i_field_norm or None,
            "i_q": i_q_norm or None,
            "tt_students": tt_students,
            "tt_mentors": tt_mentors,
            "tt_active_interns": tt_active_interns,
            "tt_pending_appli": tt_pending_appli,
        },
    )


# Approve Application
# ----------------------------
@router.post("/admin/approve")
def approve_application(
    request: Request,
    application_id: int = Form(...),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )
    if app and (app.status or '').lower() == 'pending':
        app.status = 'approved'
        db.commit()

    target = f"/admin_dash#section-approvals"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


# Reject Application
# ----------------------------
@router.post("/admin/reject")
def reject_application(
    request: Request,
    application_id: int = Form(...),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )
    if app and (app.status or '').lower() == 'pending':
        app.status = 'rejected'
        db.commit()

    target = f"/admin_dash#section-approvals"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


# Create Task Assignment
# ----------------------------
@router.post("/admin/task_create")
def create_task(
    request: Request,
    title: str = Form(...),
    mentor_id: int = Form(...),
    student_id: int = Form(...),
    internship_sv_id: int = Form(...),
    deadline: str = Form(...),
    desc: str = Form(...),
    db: Session = Depends(get_db),
):
    deadline = datetime.strptime(deadline, "%Y-%m-%d").date()
    ct = Task(
        title=title,
        description=desc,
        due_date=deadline,
        assigned_by=mentor_id,
        student_id=student_id,
        supervision_id=internship_sv_id,
    )

    db.add(ct)
    db.commit()

    return RedirectResponse(url="/admin_dash#section-assign", status_code=status.HTTP_303_SEE_OTHER)


# Delete Task Assignment
# ----------------------------
@router.post("/admin/Task_delete")
def admin_task_delete(
    request: Request,
    task_id: int = Form(...),
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

    target = f"/admin_dash#section-assign"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


# Delete Internship
# ----------------------------
@router.post("/admin/internships/delete")
def admin_delete_internship(
    request: Request,
    internship_id: int = Form(...),
    db: Session = Depends(get_db),
):
    # Fetch the internship
    intern = db.query(Internship).filter(Internship.id == internship_id).first()
    if not intern:
        return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)

    try:
        # 1️ Delete related supervisions
        supervisions = db.query(InternshipSupervision).filter(
            InternshipSupervision.internship_id == internship_id
        ).all()
        supervision_ids = [s.id for s in supervisions]

        # 2️ Delete tasks linked to these supervisions
        tasks = db.query(Task).filter(Task.supervision_id.in_(supervision_ids)).all()
        task_ids = [t.id for t in tasks]

        if task_ids:
            # Delete feedback for task submissions
            sub_ids = [sid for (sid,) in db.query(TaskSubmission.id).filter(TaskSubmission.task_id.in_(task_ids)).all()]
            if sub_ids:
                db.query(Feedback).filter(Feedback.task_submission_id.in_(sub_ids)).delete(synchronize_session=False)
                db.query(TaskSubmission).filter(TaskSubmission.id.in_(sub_ids)).delete(synchronize_session=False)

            # Delete tasks
            db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)

        # 3️ Delete reports tied to the internship
        db.query(Report).filter(Report.internship_id == internship_id).delete(synchronize_session=False)

        # 4️ Delete applications for this internship
        db.query(Application).filter(Application.internship_id == internship_id).delete(synchronize_session=False)

        # 5️ Delete supervisions
        db.query(InternshipSupervision).filter(InternshipSupervision.internship_id == internship_id).delete(synchronize_session=False)

        # 6️ Finally delete the internship itself
        db.delete(intern)

        # Commit with retry (optional)
        for attempt in range(5):
            try:
                db.commit()
                break
            except OperationalError:
                db.rollback()
                time.sleep(0.2 * (attempt + 1))
        else:
            raise

    except Exception as e:
        db.rollback()
        print("Failed to delete internship:", e)  # log exception

    # Redirect back to admin dashboard
    return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/internships/update")
def admin_update_internship(
    request: Request,
    internship_id: str = Form(""),
    title: str = Form(""),
    company: str = Form(""),
    location: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    slots: str = Form(""),
    status_value: str = Form(""),
    description: str = Form(""),
    requirements: str = Form(""),
    db: Session = Depends(get_db),
):
    # Validate internship_id; if missing, fallback to lookup by title (+ optional company)
    iid = None
    iid_raw = (internship_id or "").strip()
    if iid_raw:
        try:
            iid = int(iid_raw)
        except Exception:
            iid = None
    i = None
    if iid is not None:
        i = db.query(Internship).filter(Internship.id == iid).first()
    if i is None:
        t = (title or "").strip()
        if t:
            q = db.query(Internship).filter(Internship.title == t)
            c = (company or "").strip()
            if c:
                q = q.filter(Internship.company == c)
            i = q.order_by(Internship.created_at.desc().nullslast()).first()
            if i:
                iid = i.id
    if not i:
        return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)
    if not i:
        return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)

    # Safe parse for dates
    def parse_date(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    # Update fields if provided
    if title is not None and title.strip():
        i.title = title.strip()
    if company is not None and company.strip():
        i.company = company.strip()
    if location is not None:
        loc = location.strip()
        if loc != "":
            i.location = loc
    if start_date is not None and start_date.strip():
        parsed = parse_date(start_date)
        if parsed:
            i.start_date = parsed
    if end_date is not None and end_date.strip():
        parsed = parse_date(end_date)
        if parsed:
            i.end_date = parsed
    if slots is not None and str(slots).strip():
        try:
            i.slots = int(str(slots).strip())
        except Exception:
            pass
    if status_value is not None and status_value.strip():
        st = status_value.strip().lower()
        if st in ("open", "closed", "draft"):
            i.status = st

    desc = (description or "").strip()
    req = (requirements or "").strip()
    if desc:
        i.description = desc
    if req:
        # persist requirements into its dedicated column
        if hasattr(i, "requirements"):
            i.requirements = req

    db.add(i)
    for attempt in range(5):
        try:
            db.commit()
            try:
                print(f"[Update] Internship {iid} saved to DB: {engine.url.database}")
            except Exception:
                pass
            break
        except OperationalError:
            db.rollback()
            time.sleep(0.2 * (attempt + 1))
    else:
        raise

    return RedirectResponse(url=f"/admin_dash?edit_internship={iid}&updated=1#section-internships", status_code=status.HTTP_303_SEE_OTHER)

    try:
        # Collect related tasks for cascading deletions
        task_ids = [t.id for t in db.query(Task).filter(Task.internship_id == internship_id).all()]

        if task_ids:
            # Delete feedback linked to task submissions for these tasks
            sub_ids = [sid for (sid,) in db.query(TaskSubmission.id).filter(TaskSubmission.task_id.in_(task_ids)).all()]
            if sub_ids:
                db.query(Feedback).filter(Feedback.task_submission_id.in_(sub_ids)).delete(synchronize_session=False)
                db.query(TaskSubmission).filter(TaskSubmission.id.in_(sub_ids)).delete(synchronize_session=False)
            # Delete task assignments
            db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)
            # Delete tasks
            db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)

        # Delete reports tied to the internship
        db.query(Report).filter(Report.internship_id == internship_id).delete(synchronize_session=False)
        # Delete applications for this internship
        db.query(Application).filter(Application.internship_id == internship_id).delete(synchronize_session=False)
        # Delete supervisions for this internship
        db.query(InternshipSupervision).filter(InternshipSupervision.internship_id == internship_id).delete(synchronize_session=False)
        # Finally delete the internship
        db.delete(intern)

        for attempt in range(5):
            try:
                db.commit()
                break
            except OperationalError:
                db.rollback()
                time.sleep(0.2 * (attempt + 1))
        else:
            raise
    except Exception:
        db.rollback()
    
    # Redirect back to postings table section
    return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/supervisions/create")
def create_supervision(
    request: Request,
    mentor_id: int = Form(...),
    student_id: int = Form(...),
    internship_id: int = Form(...),
    active: str = Form("true"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    sv = InternshipSupervision(
        mentor_id=mentor_id,
        student_id=student_id,
        internship_id=internship_id,
        active=(active.lower() == "true"),
        scope_notes=(notes or None),
    )
    db.add(sv)
    db.commit()

    return RedirectResponse(url="/admin_dash#section-supervisions", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/supervisions/update")
def update_supervision(
    request: Request,
    supervision_id: int = Form(...),
    mentor_id: int = Form(...),
    student_id: int = Form(...),
    internship_id: int = Form(...),
    active: str = Form("true"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    sv = db.query(InternshipSupervision).filter(InternshipSupervision.id == supervision_id).first()
    if sv:
        sv.mentor_id = mentor_id
        sv.student_id = student_id
        sv.internship_id = internship_id
        sv.active = (active.lower() == "true")
        sv.scope_notes = (notes or None)
        db.add(sv)
        db.commit()

    return RedirectResponse(url=f"/admin_dash#section-supervisions", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/users/create")
def admin_create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    department_id: str = Form(""),
    department_name: str = Form(""),
    db: Session = Depends(get_db),
):
    # Normalize
    name_norm = (name or "").strip()
    email_norm = (email or "").strip().lower()
    role_norm = (role or "").strip().lower()
    dep_id = None
    if department_id and str(department_id).strip():
        try:
            dep_id = int(str(department_id).strip())
        except ValueError:
            dep_id = None

    # Validate role
    if role_norm not in ("student", "mentor", "admin"):
        role_norm = "student"

    # Duplicate email check (case-insensitive)
    existing = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if existing:
        # Rebuild context for admin_dash
        supervisions = []
        for sv in db.query(InternshipSupervision).all():
            mentor = db.query(User).filter(User.id == sv.mentor_id).first()
            student = db.query(User).filter(User.id == sv.student_id).first() if sv.student_id else None
            internship = db.query(Internship).filter(Internship.id == sv.internship_id).first()
            supervisions.append({
                "id": sv.id,
                "mentor_id": sv.mentor_id,
                "mentor_name": mentor.name if mentor else None,
                "student_id": sv.student_id,
                "student_name": student.name if student else None,
                "internship_id": sv.internship_id,
                "internship_title": internship.title if internship else None,
                "active": sv.active,
                "scope_notes": sv.scope_notes,
            })
        departments = db.query(Department).order_by(Department.name.asc()).all()
        users = db.query(User).order_by(User.created_at.desc().nullslast()).all()
        return templates.TemplateResponse(
            "admin_dash.html",
            {
                "request": request,
                "supervisions": supervisions,
                "edit_supervision": None,
                "add_user_error": "Email already exists.",
                "add_user_prefill": {"name": name_norm, "email": email, "role": role, "department_id": dep_id, "department_name": (department_name or "")},
                "departments": [{"id": d.id, "name": d.name} for d in departments],
                "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "status": u.status} for u in users],
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # If department_name provided, find-or-create
    dep_name_norm = (department_name or "").strip()
    if dep_name_norm:
        existing_dep = db.query(Department).filter(func.lower(Department.name) == dep_name_norm.lower()).first()
        if existing_dep:
            dep_id = existing_dep.id
        else:
            new_dep = Department(name=dep_name_norm)
            db.add(new_dep)
            # Use flush to get PK without committing the transaction to avoid locks
            db.flush()
            dep_id = new_dep.id

    # Create user
    password_hash = hashlib.sha256((password or "").strip().encode("utf-8")).hexdigest()
    u = User(
        name=name_norm,
        email=email_norm,
        role=role_norm,
        password_hash=password_hash,
        department_id=dep_id,
        status="active",
        created_at=datetime.utcnow(),
    )
    db.add(u)
    # Retry commit to mitigate transient 'database is locked'
    for attempt in range(5):
        try:
            db.commit()
            break
        except OperationalError:
            db.rollback()
            time.sleep(0.2 * (attempt + 1))
    else:
        # If still failing after retries, re-raise
        raise

    return RedirectResponse(url="/admin_dash#section-users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/internships/create")
def admin_create_internship(
    request: Request,
    title: str = Form(...),
    company: str = Form(...),
    location: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    slots: int = Form(0),
    description: str = Form(""),
    requirements: str = Form(""),
    mentor_id: str = Form(""),
    db: Session = Depends(get_db),
):
    title_norm = (title or "").strip()
    company_norm = (company or "").strip()
    if not title_norm or not company_norm:
        return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)

    # Parse dates safely
    def parse_date(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    start_d = parse_date(start_date)
    end_d = parse_date(end_date)

    # Normalize fields
    full_desc = (description or "").strip() or None
    req_norm = (requirements or "").strip() or None

    intern = Internship(
        title=title_norm,
        company=company_norm,
        location=(location or "").strip() or None,
        description=full_desc,
        requirements=req_norm,
        start_date=start_d,
        end_date=end_d,
        slots=slots if isinstance(slots, int) else 0,
        status="open",
        created_at=datetime.utcnow(),
    )
    db.add(intern)

    # Commit with retry to avoid transient DB lock issues
    for attempt in range(5):
        try:
            db.flush()  # get intern.id
            # Optionally create supervision if mentor_id provided and valid
            mentor_val = None
            if mentor_id and str(mentor_id).strip():
                try:
                    mentor_val = int(str(mentor_id).strip())
                except ValueError:
                    mentor_val = None
            if mentor_val:
                db.add(InternshipSupervision(mentor_id=mentor_val, internship_id=intern.id, active=True))

            db.commit()
            break
        except OperationalError:
            db.rollback()
            time.sleep(0.2 * (attempt + 1))
    else:
        raise

    return RedirectResponse(url="/admin_dash#section-internships", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/users/update")
def admin_update_user(
    request: Request,
    user_id: int = Form(...),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    role: str = Form(""),
    status_value: str = Form(""),
    department_id: str = Form(""),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return RedirectResponse(url="/admin_dash#section-users", status_code=status.HTTP_303_SEE_OTHER)

    if name and name.strip():
        u.name = name.strip()
    if email and email.strip():
        u.email = email.strip().lower()
    if password and password.strip():
        u.password_hash = hashlib.sha256(password.strip().encode("utf-8")).hexdigest()
    role_norm = (role or "").strip().lower()
    if role_norm in ("student", "mentor", "admin"):
        u.role = role_norm
    status_norm = (status_value or "").strip().lower()
    if status_norm in ("active", "inactive"):
        u.status = status_norm
    if department_id and str(department_id).strip():
        try:
            u.department_id = int(str(department_id).strip())
        except ValueError:
            pass

    db.add(u)
    for attempt in range(5):
        try:
            db.commit()
            break
        except OperationalError:
            db.rollback()
            time.sleep(0.2 * (attempt + 1))
    else:
        raise

    return RedirectResponse(url="/admin_dash#section-users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/users/delete")
def admin_delete_user(
    request: Request,
    user_id: int = Form(...),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        db.delete(u)
        for attempt in range(5):
            try:
                db.commit()
                break
            except OperationalError:
                db.rollback()
                time.sleep(0.2 * (attempt + 1))
        else:
            raise

    return RedirectResponse(url="/admin_dash#section-users", status_code=status.HTTP_303_SEE_OTHER)
