from sqlalchemy import Column, Integer, String, ForeignKey, Date, TIMESTAMP, Boolean, Text
from sqlalchemy.orm import relationship
from .connection import Base

# Departments
# ---------------------
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    users = relationship("User", back_populates="department")


# Users
# ---------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # student / mentor / admin
    phone = Column(String)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
    status = Column(String, default="active")
    profile_photo_url = Column(String)
    cv_url = Column(String)

    department = relationship("Department", back_populates="users")
    applications = relationship("Application", back_populates="student", foreign_keys="Application.student_id")
    supervised_internships = relationship("InternshipSupervision", back_populates="mentor", foreign_keys="InternshipSupervision.mentor_id")
    tasks_assigned = relationship("Task", back_populates="assigned_by_user", foreign_keys="Task.assigned_by")
    notifications = relationship("Notification", back_populates="user")
    reports = relationship("Report", back_populates="student")


# Internships
# ---------------------
class Internship(Base):
    __tablename__ = "internships"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    requirements = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    slots = Column(Integer)
    status = Column(String, default="draft")  # open/closed/draft
    created_at = Column(TIMESTAMP)

    applications = relationship("Application", back_populates="internship")
    supervisions = relationship("InternshipSupervision", back_populates="internship")
    reports = relationship("Report", back_populates="internship")


# Applications
# ---------------------
class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    internship_id = Column(Integer, ForeignKey("internships.id"), nullable=False)
    status = Column(String, default="pending")  # pending/approved/rejected/withdrawn
    applied_at = Column(TIMESTAMP)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(TIMESTAMP)
    notes = Column(Text)
    cv_url = Column(String, nullable=True)

    student = relationship("User", back_populates="applications", foreign_keys=[student_id])
    internship = relationship("Internship", back_populates="applications")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


# Internship Supervisions
# ---------------------
class InternshipSupervision(Base):
    __tablename__ = "internship_supervisions"

    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    internship_id = Column(Integer, ForeignKey("internships.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scope_notes = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP)

    mentor = relationship("User", back_populates="supervised_internships", foreign_keys=[mentor_id])
    internship = relationship("Internship", back_populates="supervisions")
    student = relationship("User", foreign_keys=[student_id])
    tasks = relationship("Task", back_populates="internship_sv")


# Tasks
# ---------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    supervision_id = Column(Integer, ForeignKey("internship_supervisions.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    feedback = Column(Text)
    rating = Column(String, default="not_yet")  # e.g., excellent/good/need_improvement/not_yet
    due_date = Column(Date)
    created_at = Column(TIMESTAMP)
    status = Column(String, default="assigned")  # assigned/in_progress/completed/overdue

    internship_sv = relationship("InternshipSupervision", back_populates="tasks", foreign_keys=[supervision_id])
    assigned_by_user = relationship("User", back_populates="tasks_assigned", foreign_keys=[assigned_by])


# Notifications
# ---------------------
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text)
    type = Column(String)
    read_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP)

    user = relationship("User", back_populates="notifications")


# Reports
# ---------------------
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    internship_id = Column(Integer, ForeignKey("internships.id"), nullable=False)
    title = Column(String, nullable=False)
    file_url = Column(String)
    issued_at = Column(TIMESTAMP)

    student = relationship("User", back_populates="reports")
    internship = relationship("Internship", back_populates="reports")