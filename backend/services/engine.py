"""EngineService interface.

The real scheduling algorithm (genetic algorithm) will be plugged in later.
This module exposes:

- EngineService.generate(project_id) -> EngineResult
- A stub implementation `StubEngine` that produces a naive assignment so the
  entire application (validation -> generation -> editor -> exports) is
  end-to-end usable during development.

The rest of the application ONLY depends on the abstract interface, so the
production algorithm can be swapped in without touching the API layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from models import (
    FixedPeriod,
    Project,
    SchoolClass,
    Section,
    Subject,
    Teacher,
    TeacherMapping,
)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass
class EngineEntry:
    day_of_week: int
    period_number: int
    class_id: Optional[str] = None
    section_id: Optional[str] = None
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    room_id: Optional[str] = None
    is_locked: bool = False
    note: Optional[str] = None


@dataclass
class EngineResult:
    entries: List[EngineEntry]
    summary: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class EngineInput:
    """JSON-friendly bundle handed to the engine."""

    project: Dict[str, Any]
    teachers: List[Dict[str, Any]]
    subjects: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    sections: List[Dict[str, Any]]
    rooms: List[Dict[str, Any]]
    teacher_mapping: List[Dict[str, Any]]
    teacher_availability: List[Dict[str, Any]]
    fixed_periods: List[Dict[str, Any]]
    weekly_priority: List[Dict[str, Any]]
    school_timing: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    config: Dict[str, Any]


class EngineService(Protocol):
    """Contract that any real engine must implement."""

    def generate(self, project_id: str, config: Dict[str, Any], db: Session) -> EngineResult:
        ...


# ---------------------------------------------------------------------------
# Helpers to build the JSON bundle expected by the engine
# ---------------------------------------------------------------------------


def build_engine_input(db: Session, project_id: str, config: Dict[str, Any]) -> EngineInput:
    from models import (
        Constraint,
        Room,
        SchoolTiming,
        TeacherAvailability,
        WeeklyPriority,
    )

    project = db.query(Project).filter(Project.id == project_id).first()

    def _q(model):
        return db.query(model).filter(model.project_id == project_id).all()

    def _dump(rows):
        return [
            {c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows
        ]

    return EngineInput(
        project=_dump([project])[0] if project else {},
        teachers=_dump(_q(Teacher)),
        subjects=_dump(_q(Subject)),
        classes=_dump(_q(SchoolClass)),
        sections=_dump(_q(Section)),
        rooms=_dump(_q(Room)),
        teacher_mapping=_dump(_q(TeacherMapping)),
        teacher_availability=_dump(_q(TeacherAvailability)),
        fixed_periods=_dump(_q(FixedPeriod)),
        weekly_priority=_dump(_q(WeeklyPriority)),
        school_timing=_dump(_q(SchoolTiming)),
        constraints=_dump(_q(Constraint)),
        config=config or {},
    )


# ---------------------------------------------------------------------------
# Stub engine (placeholder until GA is wired in)
# ---------------------------------------------------------------------------


class StubEngine:
    """Deterministic naive scheduler used until the real engine is integrated.

    It respects `FixedPeriod` rows and then greedily fills each class/section's
    weekly grid using the teacher mappings. This exists ONLY so downstream
    features (editor, exports, validation) are exercisable end-to-end.
    """

    def generate(self, project_id: str, config: Dict[str, Any], db: Session) -> EngineResult:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return EngineResult(entries=[], summary={}, message="Project not found")

        days = project.working_days
        periods = project.periods_per_day

        classes = db.query(SchoolClass).filter(SchoolClass.project_id == project_id).all()
        sections_by_class: Dict[str, List[Section]] = {}
        for s in db.query(Section).filter(Section.project_id == project_id).all():
            sections_by_class.setdefault(s.class_id, []).append(s)

        subjects_by_id = {s.id: s for s in db.query(Subject).filter(Subject.project_id == project_id).all()}
        teachers_by_id = {t.id: t for t in db.query(Teacher).filter(Teacher.project_id == project_id).all()}

        mappings = db.query(TeacherMapping).filter(TeacherMapping.project_id == project_id).all()
        # class_id -> list of (subject_id, teacher_id, periods_needed)
        plan: Dict[str, List[tuple[str, str, int]]] = {}
        for m in mappings:
            subj = subjects_by_id.get(m.subject_id)
            if not subj:
                continue
            plan.setdefault(m.class_id, []).append(
                (m.subject_id, m.teacher_id, m.periods_per_week or subj.weekly_periods)
            )

        fixed = db.query(FixedPeriod).filter(FixedPeriod.project_id == project_id).all()
        fixed_lookup = {(f.class_id, f.section_id, f.day_of_week, f.period_number): f for f in fixed}

        entries: List[EngineEntry] = []
        teacher_busy: set[tuple[str, int, int]] = set()  # (teacher_id, day, period)
        unassigned = 0

        for cls in classes:
            secs = sections_by_class.get(cls.id) or [None]
            for section in secs:
                # First place fixed periods
                for (cid, sid, d, p), fp in fixed_lookup.items():
                    if cid != cls.id:
                        continue
                    if section and sid and sid != section.id:
                        continue
                    entries.append(
                        EngineEntry(
                            day_of_week=d,
                            period_number=p,
                            class_id=cls.id,
                            section_id=section.id if section else None,
                            subject_id=fp.subject_id,
                            teacher_id=fp.teacher_id,
                            is_locked=True,
                            note=fp.label,
                        )
                    )
                    if fp.teacher_id:
                        teacher_busy.add((fp.teacher_id, d, p))

                occupied = {(e.day_of_week, e.period_number) for e in entries if e.class_id == cls.id and (not section or e.section_id == section.id)}
                queue: List[tuple[str, str]] = []
                for subj_id, teacher_id, count in plan.get(cls.id, []):
                    queue.extend([(subj_id, teacher_id)] * count)

                idx = 0
                for d in range(days):
                    for p in range(1, periods + 1):
                        if (d, p) in occupied:
                            continue
                        placed = False
                        for tries in range(len(queue)):
                            i = (idx + tries) % max(1, len(queue))
                            if not queue:
                                break
                            subj_id, teacher_id = queue[i]
                            if (teacher_id, d, p) in teacher_busy:
                                continue
                            entries.append(
                                EngineEntry(
                                    day_of_week=d,
                                    period_number=p,
                                    class_id=cls.id,
                                    section_id=section.id if section else None,
                                    subject_id=subj_id,
                                    teacher_id=teacher_id,
                                )
                            )
                            teacher_busy.add((teacher_id, d, p))
                            queue.pop(i)
                            idx = i
                            placed = True
                            break
                        if not placed:
                            unassigned += 1

        summary = {
            "total_entries": len(entries),
            "unassigned_slots": unassigned,
            "engine": "stub",
        }
        return EngineResult(entries=entries, summary=summary, message="Generated using stub engine")


def get_engine() -> EngineService:
    """Factory. Replace the stub here when the real engine ships."""
    return StubEngine()
