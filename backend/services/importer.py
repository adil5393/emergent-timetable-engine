"""Import service. Reads Excel/CSV, provides column preview and commit."""
from __future__ import annotations

import io
import os
import tempfile
import uuid
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from models import (
    Constraint,
    Department,
    FixedPeriod,
    ImportJob,
    ImportStatus,
    Room,
    SchoolClass,
    SchoolTiming,
    Section,
    Subject,
    Teacher,
    TeacherAvailability,
    TeacherMapping,
    WeeklyPriority,
    DatasetType,
)


# Directory to hold uploaded files temporarily while user maps columns.
UPLOAD_DIR = "/tmp/timetable_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Dataset schemas — target field metadata used by the wizard for auto-mapping.
# ---------------------------------------------------------------------------

DATASET_FIELDS: Dict[str, Dict[str, Any]] = {
    "teachers": {
        "label": "Teachers",
        "required": ["code", "name"],
        "fields": {
            "code": ["code", "teacher_code", "id", "teacher_id"],
            "name": ["name", "teacher_name", "full_name"],
            "email": ["email", "mail"],
            "phone": ["phone", "mobile", "contact"],
            "department_code": ["department", "dept", "department_code"],
            "max_periods_per_day": ["max_per_day", "max_daily", "max_periods_per_day"],
            "max_periods_per_week": ["max_per_week", "max_weekly", "max_periods_per_week"],
        },
    },
    "subjects": {
        "label": "Subjects",
        "required": ["code", "name"],
        "fields": {
            "code": ["code", "subject_code", "id"],
            "name": ["name", "subject_name", "subject"],
            "weekly_periods": ["weekly_periods", "periods", "per_week"],
            "is_lab": ["is_lab", "lab"],
            "department_code": ["department", "dept", "department_code"],
        },
    },
    "classes": {
        "label": "Classes",
        "required": ["code", "name"],
        "fields": {
            "code": ["code", "class_code", "id"],
            "name": ["name", "class_name"],
            "grade_level": ["grade", "grade_level", "level"],
        },
    },
    "sections": {
        "label": "Sections",
        "required": ["class_code", "code", "name"],
        "fields": {
            "class_code": ["class_code", "class", "class_id"],
            "code": ["code", "section_code"],
            "name": ["name", "section_name", "section"],
            "strength": ["strength", "students", "count"],
        },
    },
    "rooms": {
        "label": "Rooms",
        "required": ["code", "name"],
        "fields": {
            "code": ["code", "room_code", "id"],
            "name": ["name", "room_name"],
            "capacity": ["capacity", "size"],
            "room_type": ["room_type", "type"],
        },
    },
    "departments": {
        "label": "Departments",
        "required": ["code", "name"],
        "fields": {
            "code": ["code", "department_code", "id"],
            "name": ["name", "department_name", "department"],
        },
    },
    "teacher_mapping": {
        "label": "Teacher Mapping",
        "required": ["teacher_code", "subject_code", "class_code"],
        "fields": {
            "teacher_code": ["teacher", "teacher_code", "teacher_id"],
            "subject_code": ["subject", "subject_code", "subject_id"],
            "class_code": ["class", "class_code", "class_id"],
            "section_code": ["section", "section_code", "section_id"],
            "periods_per_week": ["periods_per_week", "periods", "per_week"],
        },
    },
    "weekly_priority": {
        "label": "Weekly Priority",
        "required": ["subject_code"],
        "fields": {
            "subject_code": ["subject", "subject_code"],
            "class_code": ["class", "class_code"],
            "priority": ["priority"],
            "min_periods": ["min", "min_periods"],
            "max_periods": ["max", "max_periods"],
        },
    },
    "school_timing": {
        "label": "School Timing",
        "required": ["day_of_week", "period_number", "start_time", "end_time"],
        "fields": {
            "day_of_week": ["day", "day_of_week", "weekday"],
            "period_number": ["period", "period_number"],
            "start_time": ["start", "start_time", "from"],
            "end_time": ["end", "end_time", "to"],
            "is_break": ["is_break", "break"],
            "label": ["label", "name"],
        },
    },
    "constraints": {
        "label": "Constraints",
        "required": ["type", "name"],
        "fields": {
            "type": ["type", "constraint_type"],
            "name": ["name", "constraint_name"],
            "entity_type": ["entity_type"],
            "entity_id": ["entity_id"],
        },
    },
    "teacher_availability": {
        "label": "Teacher Availability",
        "required": ["teacher_code", "day_of_week", "period_number"],
        "fields": {
            "teacher_code": ["teacher", "teacher_code"],
            "day_of_week": ["day", "day_of_week"],
            "period_number": ["period", "period_number"],
            "is_available": ["is_available", "available"],
        },
    },
    "fixed_periods": {
        "label": "Fixed Periods",
        "required": ["class_code", "day_of_week", "period_number"],
        "fields": {
            "class_code": ["class", "class_code"],
            "section_code": ["section", "section_code"],
            "day_of_week": ["day", "day_of_week"],
            "period_number": ["period", "period_number"],
            "subject_code": ["subject", "subject_code"],
            "teacher_code": ["teacher", "teacher_code"],
            "label": ["label", "note"],
        },
    },
}


def dataset_labels() -> List[Dict[str, str]]:
    return [{"dataset_type": k, "label": v["label"]} for k, v in DATASET_FIELDS.items()]


# ---------------------------------------------------------------------------
# File upload + preview
# ---------------------------------------------------------------------------


def save_upload(content: bytes, filename: str) -> str:
    """Persist upload to tmp and return a file_token."""
    token = uuid.uuid4().hex
    ext = os.path.splitext(filename)[1].lower() or ".xlsx"
    path = os.path.join(UPLOAD_DIR, f"{token}{ext}")
    with open(path, "wb") as f:
        f.write(content)
    return token


def _resolve_path(token: str) -> str:
    for ext in (".xlsx", ".xls", ".csv"):
        path = os.path.join(UPLOAD_DIR, f"{token}{ext}")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"Upload token {token} not found")


def read_dataframe(token: str) -> pd.DataFrame:
    path = _resolve_path(token)
    if path.endswith(".csv"):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def suggest_column_map(columns: List[str], dataset_type: str) -> Dict[str, str]:
    schema = DATASET_FIELDS.get(dataset_type)
    if not schema:
        return {}
    normalized_cols = {c: c.strip().lower().replace(" ", "_") for c in columns}
    mapping: Dict[str, str] = {}
    used = set()
    for target_field, aliases in schema["fields"].items():
        for col, norm in normalized_cols.items():
            if col in used:
                continue
            if norm == target_field or norm in aliases:
                mapping[col] = target_field
                used.add(col)
                break
    return mapping


def preview(token: str, dataset_type: str, rows: int = 25) -> Dict[str, Any]:
    df = read_dataframe(token)
    head = df.head(rows).fillna("").to_dict(orient="records")
    return {
        "columns": list(df.columns),
        "rows": head,
        "total_rows": int(len(df)),
        "suggested_map": suggest_column_map(list(df.columns), dataset_type),
    }


# ---------------------------------------------------------------------------
# Commit — write records into the appropriate table
# ---------------------------------------------------------------------------


def _to_int(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


def _to_bool(val, default=False):
    if val is None or val == "":
        return default
    s = str(val).strip().lower()
    if s in {"true", "yes", "1", "y", "t"}:
        return True
    if s in {"false", "no", "0", "n", "f"}:
        return False
    return default


def _lookup_code_map(db: Session, project_id: str, model, field="code") -> Dict[str, str]:
    rows = db.query(model).filter(model.project_id == project_id).all()
    return {getattr(r, field): r.id for r in rows if getattr(r, field)}


def commit_import(
    db: Session,
    project_id: str,
    dataset_type: str,
    token: str,
    column_map: Dict[str, str],
    filename: str,
    user_id: str | None,
    replace_existing: bool = False,
) -> ImportJob:
    schema = DATASET_FIELDS[dataset_type]
    df = read_dataframe(token)

    # Rename columns according to mapping (source -> target)
    inv = {src: tgt for src, tgt in column_map.items() if tgt}
    df = df.rename(columns=inv)

    # Verify required fields
    missing = [f for f in schema["required"] if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields after mapping: {missing}")

    errors: List[Dict[str, Any]] = []
    imported = 0

    # Optional wipe for the dataset
    if replace_existing:
        _clear_dataset(db, project_id, dataset_type)

    dept_map = _lookup_code_map(db, project_id, Department) if dataset_type in {"teachers", "subjects"} else {}
    teacher_map = _lookup_code_map(db, project_id, Teacher) if dataset_type in {"teacher_mapping", "teacher_availability", "fixed_periods"} else {}
    subject_map = _lookup_code_map(db, project_id, Subject) if dataset_type in {"teacher_mapping", "weekly_priority", "fixed_periods"} else {}
    class_map = _lookup_code_map(db, project_id, SchoolClass) if dataset_type in {"sections", "teacher_mapping", "weekly_priority", "fixed_periods"} else {}
    section_map: Dict[str, str] = {}
    if dataset_type in {"teacher_mapping", "fixed_periods"}:
        sec_rows = db.query(Section).filter(Section.project_id == project_id).all()
        section_map = {s.code: s.id for s in sec_rows}

    for idx, row in df.iterrows():
        try:
            row_num = int(idx) + 2  # +2 accounts for header row + 1-indexing
            _insert_row(
                db, project_id, dataset_type, row,
                dept_map=dept_map,
                teacher_map=teacher_map,
                subject_map=subject_map,
                class_map=class_map,
                section_map=section_map,
            )
            imported += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"row": row_num, "error": str(e)})

    job = ImportJob(
        project_id=project_id,
        dataset_type=DatasetType(dataset_type),
        filename=filename,
        status=ImportStatus.imported if not errors else (ImportStatus.imported if imported else ImportStatus.error),
        total_rows=int(len(df)),
        imported_rows=imported,
        error_rows=len(errors),
        errors=errors[:500] if errors else None,
        column_map=column_map,
        created_by=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        os.remove(_resolve_path(token))
    except Exception:  # noqa: BLE001
        pass

    return job


def _clear_dataset(db: Session, project_id: str, dataset_type: str) -> None:
    model_map = {
        "teachers": Teacher,
        "subjects": Subject,
        "classes": SchoolClass,
        "sections": Section,
        "rooms": Room,
        "departments": Department,
        "teacher_mapping": TeacherMapping,
        "weekly_priority": WeeklyPriority,
        "school_timing": SchoolTiming,
        "constraints": Constraint,
        "teacher_availability": TeacherAvailability,
        "fixed_periods": FixedPeriod,
    }
    model = model_map[dataset_type]
    db.query(model).filter(model.project_id == project_id).delete(synchronize_session=False)
    db.commit()


def _insert_row(
    db: Session,
    project_id: str,
    dataset_type: str,
    row: pd.Series,
    dept_map: Dict[str, str],
    teacher_map: Dict[str, str],
    subject_map: Dict[str, str],
    class_map: Dict[str, str],
    section_map: Dict[str, str],
) -> None:
    g = lambda k, d="": (str(row[k]).strip() if k in row and row[k] not in ("", None) else d)  # noqa: E731

    if dataset_type == "teachers":
        obj = Teacher(
            project_id=project_id,
            code=g("code"),
            name=g("name"),
            email=g("email") or None,
            phone=g("phone") or None,
            department_id=dept_map.get(g("department_code")),
            max_periods_per_day=_to_int(g("max_periods_per_day"), 6),
            max_periods_per_week=_to_int(g("max_periods_per_week"), 30),
        )
    elif dataset_type == "subjects":
        obj = Subject(
            project_id=project_id,
            code=g("code"),
            name=g("name"),
            weekly_periods=_to_int(g("weekly_periods"), 5),
            is_lab=_to_bool(g("is_lab")),
            department_id=dept_map.get(g("department_code")),
        )
    elif dataset_type == "classes":
        obj = SchoolClass(
            project_id=project_id,
            code=g("code"),
            name=g("name"),
            grade_level=_to_int(g("grade_level")),
        )
    elif dataset_type == "sections":
        cls_id = class_map.get(g("class_code"))
        if not cls_id:
            raise ValueError(f"class_code '{g('class_code')}' not found")
        obj = Section(
            project_id=project_id,
            class_id=cls_id,
            code=g("code"),
            name=g("name"),
            strength=_to_int(g("strength"), 0),
        )
    elif dataset_type == "rooms":
        obj = Room(
            project_id=project_id,
            code=g("code"),
            name=g("name"),
            capacity=_to_int(g("capacity"), 40),
            room_type=g("room_type", "classroom"),
        )
    elif dataset_type == "departments":
        obj = Department(project_id=project_id, code=g("code"), name=g("name"))
    elif dataset_type == "teacher_mapping":
        t = teacher_map.get(g("teacher_code"))
        s = subject_map.get(g("subject_code"))
        c = class_map.get(g("class_code"))
        if not (t and s and c):
            raise ValueError("teacher/subject/class code not found")
        obj = TeacherMapping(
            project_id=project_id,
            teacher_id=t,
            subject_id=s,
            class_id=c,
            section_id=section_map.get(g("section_code")) or None,
            periods_per_week=_to_int(g("periods_per_week")),
        )
    elif dataset_type == "weekly_priority":
        s = subject_map.get(g("subject_code"))
        if not s:
            raise ValueError(f"subject_code '{g('subject_code')}' not found")
        obj = WeeklyPriority(
            project_id=project_id,
            subject_id=s,
            class_id=class_map.get(g("class_code")) or None,
            priority=_to_int(g("priority"), 1),
            min_periods=_to_int(g("min_periods"), 0),
            max_periods=_to_int(g("max_periods"), 8),
        )
    elif dataset_type == "school_timing":
        from datetime import datetime as _dt

        def _parse_time(v: str):
            v = str(v).strip()
            for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    return _dt.strptime(v, fmt).time()
                except ValueError:
                    continue
            raise ValueError(f"cannot parse time '{v}'")

        obj = SchoolTiming(
            project_id=project_id,
            day_of_week=_to_int(g("day_of_week"), 0),
            period_number=_to_int(g("period_number"), 1),
            start_time=_parse_time(g("start_time")),
            end_time=_parse_time(g("end_time")),
            is_break=_to_bool(g("is_break")),
            label=g("label") or None,
        )
    elif dataset_type == "constraints":
        obj = Constraint(
            project_id=project_id,
            type=g("type"),
            name=g("name"),
            entity_type=g("entity_type") or None,
            entity_id=g("entity_id") or None,
            config={},
        )
    elif dataset_type == "teacher_availability":
        t = teacher_map.get(g("teacher_code"))
        if not t:
            raise ValueError(f"teacher_code '{g('teacher_code')}' not found")
        obj = TeacherAvailability(
            project_id=project_id,
            teacher_id=t,
            day_of_week=_to_int(g("day_of_week"), 0),
            period_number=_to_int(g("period_number"), 1),
            is_available=_to_bool(g("is_available"), True),
        )
    elif dataset_type == "fixed_periods":
        cid = class_map.get(g("class_code"))
        if not cid:
            raise ValueError(f"class_code '{g('class_code')}' not found")
        obj = FixedPeriod(
            project_id=project_id,
            class_id=cid,
            section_id=section_map.get(g("section_code")) or None,
            day_of_week=_to_int(g("day_of_week"), 0),
            period_number=_to_int(g("period_number"), 1),
            subject_id=subject_map.get(g("subject_code")) or None,
            teacher_id=teacher_map.get(g("teacher_code")) or None,
            label=g("label") or None,
        )
    else:
        raise ValueError(f"Unknown dataset type '{dataset_type}'")

    db.add(obj)
    db.flush()
