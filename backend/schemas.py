"""Pydantic schemas (API contracts)."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: str = "viewer"


class UserOut(ORMModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Projects ----------


class ProjectIn(BaseModel):
    name: str
    description: Optional[str] = None
    academic_year: Optional[str] = None
    working_days: int = 5
    periods_per_day: int = 8


class ProjectOut(ORMModel):
    id: str
    name: str
    description: Optional[str]
    academic_year: Optional[str]
    working_days: int
    periods_per_day: int
    owner_id: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------- Master data ----------


class DepartmentIn(BaseModel):
    code: str
    name: str


class DepartmentOut(ORMModel):
    id: str
    project_id: str
    code: str
    name: str


class TeacherIn(BaseModel):
    code: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[str] = None
    max_periods_per_day: int = 6
    max_periods_per_week: int = 30
    is_active: bool = True


class TeacherOut(ORMModel):
    id: str
    project_id: str
    code: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    department_id: Optional[str]
    max_periods_per_day: int
    max_periods_per_week: int
    is_active: bool


class SubjectIn(BaseModel):
    code: str
    name: str
    weekly_periods: int = 5
    is_lab: bool = False
    department_id: Optional[str] = None


class SubjectOut(ORMModel):
    id: str
    project_id: str
    code: str
    name: str
    weekly_periods: int
    is_lab: bool
    department_id: Optional[str]


class ClassIn(BaseModel):
    code: str
    name: str
    grade_level: Optional[int] = None


class ClassOut(ORMModel):
    id: str
    project_id: str
    code: str
    name: str
    grade_level: Optional[int]


class SectionIn(BaseModel):
    class_id: str
    code: str
    name: str
    strength: int = 0


class SectionOut(ORMModel):
    id: str
    project_id: str
    class_id: str
    code: str
    name: str
    strength: int


class RoomIn(BaseModel):
    code: str
    name: str
    capacity: int = 40
    room_type: str = "classroom"


class RoomOut(ORMModel):
    id: str
    project_id: str
    code: str
    name: str
    capacity: int
    room_type: str


class TeacherMappingIn(BaseModel):
    teacher_id: str
    subject_id: str
    class_id: str
    section_id: Optional[str] = None
    periods_per_week: Optional[int] = None


class TeacherMappingOut(ORMModel):
    id: str
    project_id: str
    teacher_id: str
    subject_id: str
    class_id: str
    section_id: Optional[str]
    periods_per_week: Optional[int]


class ConstraintIn(BaseModel):
    type: str
    name: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    config: Dict[str, Any] = {}
    is_active: bool = True


class ConstraintOut(ORMModel):
    id: str
    project_id: str
    type: str
    name: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    config: Dict[str, Any]
    is_active: bool


class SchoolTimingIn(BaseModel):
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    is_break: bool = False
    label: Optional[str] = None


class SchoolTimingOut(ORMModel):
    id: str
    project_id: str
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    is_break: bool
    label: Optional[str]


class WeeklyPriorityIn(BaseModel):
    subject_id: str
    class_id: Optional[str] = None
    priority: int = 1
    min_periods: int = 0
    max_periods: int = 8


class WeeklyPriorityOut(ORMModel):
    id: str
    project_id: str
    subject_id: str
    class_id: Optional[str]
    priority: int
    min_periods: int
    max_periods: int


# ---------- Import ----------


class PreviewOut(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    total_rows: int
    suggested_map: Dict[str, str]


class CommitImportIn(BaseModel):
    dataset_type: str
    file_token: str
    column_map: Dict[str, str]
    save_as_template: Optional[str] = None
    replace_existing: bool = False


class ImportJobOut(ORMModel):
    id: str
    project_id: str
    dataset_type: str
    filename: str
    status: str
    total_rows: int
    imported_rows: int
    error_rows: int
    errors: Optional[List[Dict[str, Any]]]
    created_at: datetime


class DatasetSummary(BaseModel):
    dataset_type: str
    label: str
    record_count: int
    last_imported: Optional[datetime]
    last_status: Optional[str]
    validation_status: str  # ok | warning | error
    issue_count: int


# ---------- Validation ----------


class Issue(BaseModel):
    id: str
    severity: str
    code: str
    message: str
    dataset: str
    entity_id: Optional[str] = None
    entity_label: Optional[str] = None
    field: Optional[str] = None
    fix_hint: Optional[str] = None


class ValidationReport(BaseModel):
    generated_at: datetime
    errors: int
    warnings: int
    infos: int
    can_generate: bool
    issues: List[Issue]


# ---------- Timetable ----------


class TimetableEntryOut(ORMModel):
    id: str
    timetable_id: str
    day_of_week: int
    period_number: int
    class_id: Optional[str]
    section_id: Optional[str]
    subject_id: Optional[str]
    teacher_id: Optional[str]
    room_id: Optional[str]
    is_locked: bool
    note: Optional[str]


class TimetableEntryIn(BaseModel):
    day_of_week: int
    period_number: int
    class_id: Optional[str] = None
    section_id: Optional[str] = None
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    room_id: Optional[str] = None
    is_locked: bool = False
    note: Optional[str] = None


class GeneratedTimetableOut(ORMModel):
    id: str
    project_id: str
    version: int
    name: Optional[str]
    status: str
    engine_config: Optional[Dict[str, Any]]
    summary: Optional[Dict[str, Any]]
    engine_message: Optional[str]
    created_at: datetime


class GenerateRequest(BaseModel):
    name: Optional[str] = None
    config: Dict[str, Any] = {}
