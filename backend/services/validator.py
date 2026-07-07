"""Validation service. Produces a list of Issues (errors/warnings/info)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from models import (
    SchoolClass,
    SchoolTiming,
    Section,
    Subject,
    Teacher,
    TeacherMapping,
)


def _iss(severity: str, code: str, message: str, dataset: str, **kw):
    return {
        "id": uuid.uuid4().hex,
        "severity": severity,
        "code": code,
        "message": message,
        "dataset": dataset,
        "entity_id": kw.get("entity_id"),
        "entity_label": kw.get("entity_label"),
        "field": kw.get("field"),
        "fix_hint": kw.get("fix_hint"),
    }


def validate_project(db: Session, project_id: str) -> dict:
    issues: List[dict] = []

    teachers = db.query(Teacher).filter(Teacher.project_id == project_id).all()
    subjects = db.query(Subject).filter(Subject.project_id == project_id).all()
    classes = db.query(SchoolClass).filter(SchoolClass.project_id == project_id).all()
    sections = db.query(Section).filter(Section.project_id == project_id).all()
    mappings = db.query(TeacherMapping).filter(TeacherMapping.project_id == project_id).all()
    timings = db.query(SchoolTiming).filter(SchoolTiming.project_id == project_id).all()

    # --- Coverage checks
    if not teachers:
        issues.append(_iss("error", "no_teachers", "No teachers have been imported yet.", "teachers",
                           fix_hint="Import Teachers to continue."))
    if not subjects:
        issues.append(_iss("error", "no_subjects", "No subjects have been imported yet.", "subjects",
                           fix_hint="Import Subjects to continue."))
    if not classes:
        issues.append(_iss("error", "no_classes", "No classes have been imported yet.", "classes",
                           fix_hint="Import Classes to continue."))

    # --- Duplicates (defense in depth beyond DB uniqueness)
    seen = {}
    for t in teachers:
        if t.code in seen:
            issues.append(_iss("error", "dup_teacher_code",
                               f"Duplicate teacher code '{t.code}'.", "teachers",
                               entity_id=t.id, entity_label=t.name))
        seen[t.code] = t.id

    seen.clear()
    for s in subjects:
        if s.code in seen:
            issues.append(_iss("error", "dup_subject_code",
                               f"Duplicate subject code '{s.code}'.", "subjects",
                               entity_id=s.id, entity_label=s.name))
        seen[s.code] = s.id

    # --- Missing mapping
    mapped_subject_ids = {m.subject_id for m in mappings}
    for s in subjects:
        if s.id not in mapped_subject_ids:
            issues.append(_iss("warning", "subject_no_teacher",
                               f"Subject '{s.name}' has no mapped teacher.",
                               "teacher_mapping", entity_id=s.id, entity_label=s.name,
                               fix_hint="Add a Teacher Mapping row for this subject."))

    mapped_teacher_ids = {m.teacher_id for m in mappings}
    for t in teachers:
        if t.id not in mapped_teacher_ids:
            issues.append(_iss("warning", "teacher_no_subject",
                               f"Teacher '{t.name}' ({t.code}) has no mapped subjects.",
                               "teacher_mapping", entity_id=t.id, entity_label=t.name,
                               fix_hint="Add subjects for this teacher in Teacher Mapping."))

    # --- Weekly period sanity per class
    subj_periods = {s.id: s.weekly_periods for s in subjects}
    project = None
    if classes:
        from models import Project

        project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        max_weekly = project.working_days * project.periods_per_day
        # Aggregate by class
        totals: dict[str, int] = {}
        for m in mappings:
            totals[m.class_id] = totals.get(m.class_id, 0) + subj_periods.get(m.subject_id, 0)
        for c in classes:
            planned = totals.get(c.id, 0)
            if planned > max_weekly:
                issues.append(_iss("error", "class_overloaded",
                                   f"Class {c.name} has {planned} weekly periods planned but only {max_weekly} are available.",
                                   "classes", entity_id=c.id, entity_label=c.name,
                                   fix_hint="Reduce weekly periods for subjects or teacher mapping."))

    # --- Teacher workload
    load_per_teacher: dict[str, int] = {}
    for m in mappings:
        load_per_teacher[m.teacher_id] = load_per_teacher.get(m.teacher_id, 0) + subj_periods.get(m.subject_id, 0)
    for t in teachers:
        planned = load_per_teacher.get(t.id, 0)
        if planned > t.max_periods_per_week:
            issues.append(_iss("warning", "teacher_overloaded",
                               f"Teacher {t.name} planned {planned} periods/week (max {t.max_periods_per_week}).",
                               "teachers", entity_id=t.id, entity_label=t.name,
                               fix_hint="Increase max periods or reduce mapped subjects."))

    # --- Sections without a class
    class_ids = {c.id for c in classes}
    for s in sections:
        if s.class_id not in class_ids:
            issues.append(_iss("error", "section_orphan",
                               f"Section '{s.name}' points to a missing class.",
                               "sections", entity_id=s.id, entity_label=s.name))

    # --- Timings
    if not timings and project and project.periods_per_day:
        issues.append(_iss("info", "no_school_timing",
                           "School timings are not defined. The generator will use default period lengths.",
                           "school_timing",
                           fix_hint="Import School Timing to define exact start/end times."))

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    infos = sum(1 for i in issues if i["severity"] == "info")

    return {
        "generated_at": datetime.now(timezone.utc),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "can_generate": bool(errors == 0 and teachers and subjects and classes),
        "issues": issues,
    }
