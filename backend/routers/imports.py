"""Import wizard routes."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from auth import get_current_user, require_editor
from database import get_db
from models import (
    Constraint,
    Department,
    FixedPeriod,
    ImportJob,
    MappingTemplate,
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
    DatasetType,
)
from services.importer import (
    DATASET_FIELDS,
    commit_import,
    dataset_labels,
    preview,
    save_upload,
)

router = APIRouter(prefix="/api/projects/{project_id}/import", tags=["import"])


@router.get("/schema")
def get_schema():
    """Return metadata describing each dataset's target fields."""
    return {
        "datasets": [
            {
                "dataset_type": key,
                "label": val["label"],
                "required": val["required"],
                "fields": list(val["fields"].keys()),
            }
            for key, val in DATASET_FIELDS.items()
        ]
    }


@router.post("/upload")
async def upload_file(
    project_id: str,
    dataset_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(require_editor),
):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Project not found")
    if dataset_type not in DATASET_FIELDS:
        raise HTTPException(400, f"Unknown dataset_type '{dataset_type}'")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    token = save_upload(content, file.filename or "upload.xlsx")
    try:
        pv = preview(token, dataset_type)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Failed to read file: {e}")
    return {
        "file_token": token,
        "filename": file.filename,
        "dataset_type": dataset_type,
        **pv,
    }


@router.post("/commit")
def commit(
    project_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Project not found")
    dataset_type = payload.get("dataset_type")
    token = payload.get("file_token")
    column_map = payload.get("column_map", {})
    filename = payload.get("filename", "upload.xlsx")
    replace_existing = bool(payload.get("replace_existing", False))
    template_name = payload.get("save_as_template")

    if not dataset_type or not token:
        raise HTTPException(400, "dataset_type and file_token are required")

    try:
        job = commit_import(
            db, project_id, dataset_type, token, column_map,
            filename=filename,
            user_id=user.id,
            replace_existing=replace_existing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if template_name:
        db.add(MappingTemplate(
            project_id=project_id,
            name=template_name,
            dataset_type=DatasetType(dataset_type),
            column_map=column_map,
        ))
        db.commit()

    return {
        "id": job.id,
        "status": job.status.value,
        "total_rows": job.total_rows,
        "imported_rows": job.imported_rows,
        "error_rows": job.error_rows,
        "errors": job.errors or [],
    }


@router.get("/jobs")
def list_jobs(
    project_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    jobs = (
        db.query(ImportJob)
        .filter(ImportJob.project_id == project_id)
        .order_by(ImportJob.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": j.id,
            "dataset_type": j.dataset_type.value,
            "filename": j.filename,
            "status": j.status.value,
            "total_rows": j.total_rows,
            "imported_rows": j.imported_rows,
            "error_rows": j.error_rows,
            "errors": j.errors or [],
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/summary")
def dataset_summary(
    project_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Project not found")

    counters = {
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

    summary = []
    for key, model in counters.items():
        count = db.query(model).filter(model.project_id == project_id).count()
        last_job = (
            db.query(ImportJob)
            .filter(ImportJob.project_id == project_id, ImportJob.dataset_type == DatasetType(key))
            .order_by(ImportJob.created_at.desc())
            .first()
        )
        summary.append({
            "dataset_type": key,
            "label": DATASET_FIELDS[key]["label"],
            "record_count": count,
            "last_imported": last_job.created_at.isoformat() if last_job else None,
            "last_status": last_job.status.value if last_job else None,
            "validation_status": "ok" if count > 0 else ("warning" if key in {"teachers", "subjects", "classes"} else "info"),
            "issue_count": last_job.error_rows if last_job else 0,
        })
    return summary


@router.get("/templates")
def list_templates(project_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = (
        db.query(MappingTemplate)
        .filter((MappingTemplate.project_id == project_id) | (MappingTemplate.project_id.is_(None)))
        .order_by(MappingTemplate.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "name": t.name,
            "dataset_type": t.dataset_type.value,
            "column_map": t.column_map,
            "is_global": t.project_id is None,
        }
        for t in rows
    ]
