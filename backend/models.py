"""SQLAlchemy ORM models for the Timetable Management System.

Design principles:
- Every entity is scoped to a Project (multi-tenant per project).
- Generated timetables are versioned; never overwrite.
- Import jobs and mapping templates enable a flexible column-mapping importer.
- Constraints are stored generically (type + JSON config) to allow evolution
  without schema migrations.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    admin = "admin"
    planner = "planner"
    viewer = "viewer"


class DatasetType(str, enum.Enum):
    teachers = "teachers"
    subjects = "subjects"
    classes = "classes"
    sections = "sections"
    rooms = "rooms"
    departments = "departments"
    teacher_availability = "teacher_availability"
    teacher_mapping = "teacher_mapping"
    subject_mapping = "subject_mapping"
    weekly_priority = "weekly_priority"
    fixed_periods = "fixed_periods"
    school_timing = "school_timing"
    constraints = "constraints"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    validated = "validated"
    imported = "imported"
    error = "error"


class TimetableStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Severity(str, enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.viewer)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


# ---------------------------------------------------------------------------
# Project (top-level tenant)
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    academic_year = Column(String, nullable=True)
    working_days = Column(Integer, default=5, nullable=False)
    periods_per_day = Column(Integer, default=8, nullable=False)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------


class Department(Base):
    __tablename__ = "departments"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_department_code"),)


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    department_id = Column(String, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    max_periods_per_day = Column(Integer, default=6, nullable=False)
    max_periods_per_week = Column(Integer, default=30, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_teacher_code"),
        Index("ix_teachers_project_name", "project_id", "name"),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    weekly_periods = Column(Integer, default=5, nullable=False)
    is_lab = Column(Boolean, default=False, nullable=False)
    department_id = Column(String, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_subject_code"),)


class SchoolClass(Base):
    __tablename__ = "classes"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    grade_level = Column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_class_code"),)


class Section(Base):
    __tablename__ = "sections"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    strength = Column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("class_id", "code", name="uq_section_code"),)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    capacity = Column(Integer, default=40, nullable=False)
    room_type = Column(String, default="classroom", nullable=False)  # classroom, lab, hall

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_room_code"),)


class TeacherAvailability(Base):
    __tablename__ = "teacher_availability"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0 = Monday
    period_number = Column(Integer, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", "day_of_week", "period_number", name="uq_teacher_avail"),
    )


class TeacherMapping(Base):
    """Which teacher teaches which subject in which class/section."""

    __tablename__ = "teacher_mapping"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("sections.id", ondelete="CASCADE"), nullable=True, index=True)
    periods_per_week = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "teacher_id", "subject_id", "class_id", "section_id", name="uq_teacher_mapping"
        ),
    )


class WeeklyPriority(Base):
    __tablename__ = "weekly_priorities"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True)
    priority = Column(Integer, default=1, nullable=False)  # 1 = highest
    min_periods = Column(Integer, default=0, nullable=False)
    max_periods = Column(Integer, default=8, nullable=False)


class FixedPeriod(Base):
    __tablename__ = "fixed_periods"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("sections.id", ondelete="CASCADE"), nullable=True, index=True)
    day_of_week = Column(Integer, nullable=False)
    period_number = Column(Integer, nullable=False)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    label = Column(String, nullable=True)  # e.g., Assembly, Lunch


class SchoolTiming(Base):
    __tablename__ = "school_timings"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    period_number = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_break = Column(Boolean, default=False, nullable=False)
    label = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "day_of_week", "period_number", name="uq_school_timing"),
    )


class Constraint(Base):
    __tablename__ = "constraints"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)  # e.g., "max_daily_periods", "no_overlap"
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)  # teacher, subject, class, room
    entity_id = Column(String, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# Import wizard support
# ---------------------------------------------------------------------------


class MappingTemplate(Base):
    __tablename__ = "mapping_templates"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)  # nullable = global
    name = Column(String, nullable=False)
    dataset_type = Column(Enum(DatasetType, name="dataset_type"), nullable=False)
    column_map = Column(JSON, nullable=False, default=dict)  # {source_column: target_field}
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_type = Column(Enum(DatasetType, name="dataset_type_ij"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(Enum(ImportStatus, name="import_status"), default=ImportStatus.pending, nullable=False)
    total_rows = Column(Integer, default=0, nullable=False)
    imported_rows = Column(Integer, default=0, nullable=False)
    error_rows = Column(Integer, default=0, nullable=False)
    errors = Column(JSON, nullable=True)
    column_map = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ---------------------------------------------------------------------------
# Generated timetables (versioned)
# ---------------------------------------------------------------------------


class GeneratedTimetable(Base):
    __tablename__ = "generated_timetables"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    status = Column(Enum(TimetableStatus, name="timetable_status"), default=TimetableStatus.queued, nullable=False)
    engine_config = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)  # score, unassigned counts, etc.
    engine_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_timetable_version"),)


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id = Column(String, primary_key=True, default=_uuid)
    timetable_id = Column(String, ForeignKey("generated_timetables.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    period_number = Column(Integer, nullable=False)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id = Column(String, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    is_locked = Column(Boolean, default=False, nullable=False)
    note = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_entry_grid", "timetable_id", "day_of_week", "period_number"),
    )
