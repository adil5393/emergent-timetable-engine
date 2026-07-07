"""Validation center routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Project, User
from services.validator import validate_project

router = APIRouter(prefix="/api/projects/{project_id}/validation", tags=["validation"])


@router.get("")
def validation_report(project_id: str, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(404, "Project not found")
    report = validate_project(db, project_id)
    return report
