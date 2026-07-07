"""Timetable generation, listing, editing routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user, require_editor
from database import get_db
from models import (
    GeneratedTimetable,
    Project,
    TimetableEntry,
    TimetableStatus,
    User,
)
from schemas import GenerateRequest, GeneratedTimetableOut, TimetableEntryIn, TimetableEntryOut
from services.engine import get_engine
from services.validator import validate_project

router = APIRouter(prefix="/api/projects/{project_id}/timetables", tags=["timetables"])


@router.get("", response_model=List[GeneratedTimetableOut])
def list_timetables(project_id: str, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    return (
        db.query(GeneratedTimetable)
        .filter(GeneratedTimetable.project_id == project_id)
        .order_by(GeneratedTimetable.version.desc())
        .all()
    )


@router.post("/generate", response_model=GeneratedTimetableOut)
def generate(
    project_id: str,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    report = validate_project(db, project_id)
    if not report["can_generate"]:
        raise HTTPException(
            400,
            f"Cannot generate: {report['errors']} critical validation error(s) remain.",
        )

    latest = db.query(func.coalesce(func.max(GeneratedTimetable.version), 0)).filter(
        GeneratedTimetable.project_id == project_id
    ).scalar()
    next_version = int(latest or 0) + 1

    tt = GeneratedTimetable(
        project_id=project_id,
        version=next_version,
        name=payload.name or f"Version {next_version}",
        status=TimetableStatus.running,
        engine_config=payload.config or {},
        created_by=user.id,
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)

    engine = get_engine()
    try:
        result = engine.generate(project_id, payload.config or {}, db)
    except Exception as e:  # noqa: BLE001
        tt.status = TimetableStatus.failed
        tt.engine_message = str(e)
        db.commit()
        raise HTTPException(500, f"Engine failed: {e}")

    for e in result.entries:
        db.add(TimetableEntry(
            timetable_id=tt.id,
            day_of_week=e.day_of_week,
            period_number=e.period_number,
            class_id=e.class_id,
            section_id=e.section_id,
            subject_id=e.subject_id,
            teacher_id=e.teacher_id,
            room_id=e.room_id,
            is_locked=e.is_locked,
            note=e.note,
        ))

    tt.status = TimetableStatus.completed
    tt.summary = result.summary
    tt.engine_message = result.message
    db.commit()
    db.refresh(tt)
    return tt


@router.get("/{timetable_id}", response_model=GeneratedTimetableOut)
def get_timetable(project_id: str, timetable_id: str, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    tt = db.query(GeneratedTimetable).filter(
        GeneratedTimetable.id == timetable_id, GeneratedTimetable.project_id == project_id
    ).first()
    if not tt:
        raise HTTPException(404, "Timetable not found")
    return tt


@router.get("/{timetable_id}/entries", response_model=List[TimetableEntryOut])
def list_entries(project_id: str, timetable_id: str, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    return (
        db.query(TimetableEntry)
        .filter(TimetableEntry.timetable_id == timetable_id)
        .order_by(TimetableEntry.day_of_week, TimetableEntry.period_number)
        .all()
    )


@router.patch("/{timetable_id}/entries/{entry_id}", response_model=TimetableEntryOut)
def update_entry(
    project_id: str,
    timetable_id: str,
    entry_id: str,
    payload: TimetableEntryIn,
    db: Session = Depends(get_db),
    _u: User = Depends(require_editor),
):
    entry = db.query(TimetableEntry).filter(
        TimetableEntry.id == entry_id, TimetableEntry.timetable_id == timetable_id
    ).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    for k, v in payload.model_dump().items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{timetable_id}/entries/swap")
def swap_entries(
    project_id: str,
    timetable_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    _u: User = Depends(require_editor),
):
    a_id = payload.get("a_id")
    b_id = payload.get("b_id")
    a = db.query(TimetableEntry).filter(TimetableEntry.id == a_id, TimetableEntry.timetable_id == timetable_id).first()
    b = db.query(TimetableEntry).filter(TimetableEntry.id == b_id, TimetableEntry.timetable_id == timetable_id).first()
    if not (a and b):
        raise HTTPException(404, "Entry not found")
    # Swap the (subject, teacher, room) assignment; keep grid coords.
    a.subject_id, b.subject_id = b.subject_id, a.subject_id
    a.teacher_id, b.teacher_id = b.teacher_id, a.teacher_id
    a.room_id, b.room_id = b.room_id, a.room_id
    a.note, b.note = b.note, a.note
    db.commit()
    return {"ok": True}


@router.post("/{timetable_id}/entries/{entry_id}/toggle-lock")
def toggle_lock(project_id: str, timetable_id: str, entry_id: str, db: Session = Depends(get_db), _u: User = Depends(require_editor)):
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id, TimetableEntry.timetable_id == timetable_id).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    entry.is_locked = not entry.is_locked
    db.commit()
    return {"is_locked": entry.is_locked}


@router.get("/{timetable_id}/conflicts")
def conflicts(project_id: str, timetable_id: str, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    """Detect current constraint violations on this timetable."""
    entries = db.query(TimetableEntry).filter(TimetableEntry.timetable_id == timetable_id).all()

    seen_teacher = {}
    seen_class = {}
    seen_room = {}
    problems = []
    for e in entries:
        if e.teacher_id:
            key = (e.teacher_id, e.day_of_week, e.period_number)
            if key in seen_teacher:
                problems.append({
                    "type": "teacher_overlap",
                    "day": e.day_of_week, "period": e.period_number,
                    "teacher_id": e.teacher_id,
                    "entry_ids": [seen_teacher[key], e.id],
                })
            else:
                seen_teacher[key] = e.id
        if e.class_id:
            key = (e.class_id, e.section_id, e.day_of_week, e.period_number)
            if key in seen_class:
                problems.append({
                    "type": "class_overlap",
                    "day": e.day_of_week, "period": e.period_number,
                    "class_id": e.class_id,
                    "entry_ids": [seen_class[key], e.id],
                })
            else:
                seen_class[key] = e.id
        if e.room_id:
            key = (e.room_id, e.day_of_week, e.period_number)
            if key in seen_room:
                problems.append({
                    "type": "room_overlap",
                    "day": e.day_of_week, "period": e.period_number,
                    "room_id": e.room_id,
                    "entry_ids": [seen_room[key], e.id],
                })
            else:
                seen_room[key] = e.id
    return {"count": len(problems), "conflicts": problems}


@router.delete("/{timetable_id}")
def delete_timetable(project_id: str, timetable_id: str, db: Session = Depends(get_db), _u: User = Depends(require_editor)):
    tt = db.query(GeneratedTimetable).filter(
        GeneratedTimetable.id == timetable_id, GeneratedTimetable.project_id == project_id
    ).first()
    if not tt:
        raise HTTPException(404, "Timetable not found")
    db.delete(tt)
    db.commit()
    return {"ok": True}
