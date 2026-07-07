"""Generic master-data CRUD for all datasets scoped to a project.

Endpoints follow: /api/projects/{project_id}/{dataset}/...
Supported datasets:
    teachers, subjects, classes, sections, rooms, departments,
    teacher_mapping, weekly_priority, school_timing, constraints
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user, require_editor
from database import get_db
from models import (
    Constraint,
    Department,
    FixedPeriod,
    Project,
    Room,
    SchoolClass,
    SchoolTiming,
    Section,
    Subject,
    Teacher,
    TeacherAvailability,
    TeacherMapping,
    User,
    WeeklyPriority,
)


router = APIRouter(prefix="/api/projects/{project_id}", tags=["master-data"])


MODEL_MAP = {
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


def _to_dict(obj) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        d[c.name] = v
    return d


def _get_model(dataset: str):
    model = MODEL_MAP.get(dataset)
    if not model:
        raise HTTPException(400, f"Unknown dataset '{dataset}'")
    return model


def _ensure_project(db: Session, project_id: str):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Project not found")


@router.get("/data/{dataset}")
def list_records(
    project_id: str,
    dataset: str,
    q: str | None = Query(None),
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    _ensure_project(db, project_id)
    model = _get_model(dataset)
    query = db.query(model).filter(model.project_id == project_id)
    if q and hasattr(model, "name"):
        query = query.filter(model.name.ilike(f"%{q}%"))
    total = query.count()
    rows = query.limit(limit).offset(offset).all()
    return {"total": total, "rows": [_to_dict(r) for r in rows]}


@router.post("/data/{dataset}")
def create_record(
    project_id: str,
    dataset: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_editor),
):
    _ensure_project(db, project_id)
    model = _get_model(dataset)
    payload.pop("id", None)
    payload["project_id"] = project_id
    try:
        obj = model(**payload)
        db.add(obj)
        db.commit()
        db.refresh(obj)
    except TypeError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return _to_dict(obj)


@router.put("/data/{dataset}/{record_id}")
def update_record(
    project_id: str,
    dataset: str,
    record_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_editor),
):
    _ensure_project(db, project_id)
    model = _get_model(dataset)
    obj = db.query(model).filter(model.id == record_id, model.project_id == project_id).first()
    if not obj:
        raise HTTPException(404, "Record not found")
    payload.pop("id", None)
    payload.pop("project_id", None)
    columns = {c.name for c in obj.__table__.columns}
    for k, v in payload.items():
        if k in columns:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _to_dict(obj)


@router.delete("/data/{dataset}/{record_id}")
def delete_record(
    project_id: str,
    dataset: str,
    record_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_editor),
):
    _ensure_project(db, project_id)
    model = _get_model(dataset)
    obj = db.query(model).filter(model.id == record_id, model.project_id == project_id).first()
    if not obj:
        raise HTTPException(404, "Record not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/data/{dataset}/bulk-delete")
def bulk_delete(
    project_id: str,
    dataset: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_editor),
):
    _ensure_project(db, project_id)
    model = _get_model(dataset)
    ids: List[str] = payload.get("ids", [])
    if not ids:
        return {"deleted": 0}
    n = db.query(model).filter(model.project_id == project_id, model.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": n}
