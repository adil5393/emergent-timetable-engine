"""Export routes."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import GeneratedTimetable, User
from services.exporter import REPORTS, REPORT_LABELS, render

router = APIRouter(prefix="/api/projects/{project_id}/timetables", tags=["exports"])


@router.get("/reports/list")
def list_reports(_u: User = Depends(get_current_user)):
    return [{"key": k, "label": v} for k, v in REPORT_LABELS.items()]


@router.get("/{timetable_id}/export")
def export_report(
    project_id: str,
    timetable_id: str,
    report: str,
    fmt: str = "xlsx",
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    tt = db.query(GeneratedTimetable).filter(
        GeneratedTimetable.id == timetable_id, GeneratedTimetable.project_id == project_id
    ).first()
    if not tt:
        raise HTTPException(404, "Timetable not found")
    if report not in REPORTS:
        raise HTTPException(400, f"Unknown report '{report}'")
    df = REPORTS[report](db, project_id, timetable_id)
    try:
        content, filename, ctype = render(report, fmt, df)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(
        content=content,
        media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
