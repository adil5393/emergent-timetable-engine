"""Exporters for timetables and reports.

Design: A registry maps `report_name -> function(db, project_id, timetable_id) -> pandas.DataFrame`.
The dispatcher converts the DataFrame to xlsx or csv. PDF exports can be added
by registering an alternative renderer that consumes the same DataFrame.
"""
from __future__ import annotations

import io
from typing import Callable, Dict

import pandas as pd
from sqlalchemy.orm import Session

from models import (
    GeneratedTimetable,
    SchoolClass,
    Section,
    Subject,
    Teacher,
    TimetableEntry,
    Room,
)


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _entries_df(db: Session, timetable_id: str) -> pd.DataFrame:
    entries = db.query(TimetableEntry).filter(TimetableEntry.timetable_id == timetable_id).all()
    if not entries:
        return pd.DataFrame(columns=["day", "period", "class", "section", "subject", "teacher", "room"])

    teacher_map = {t.id: (t.code, t.name) for t in db.query(Teacher).all()}
    subj_map = {s.id: (s.code, s.name) for s in db.query(Subject).all()}
    class_map = {c.id: (c.code, c.name) for c in db.query(SchoolClass).all()}
    sec_map = {s.id: (s.code, s.name) for s in db.query(Section).all()}
    room_map = {r.id: (r.code, r.name) for r in db.query(Room).all()}

    rows = []
    for e in entries:
        rows.append({
            "day": DAY_NAMES[e.day_of_week] if 0 <= e.day_of_week < 7 else str(e.day_of_week),
            "day_index": e.day_of_week,
            "period": e.period_number,
            "class_code": class_map.get(e.class_id, ("", ""))[0],
            "class_name": class_map.get(e.class_id, ("", ""))[1],
            "section_code": sec_map.get(e.section_id, ("", ""))[0],
            "section_name": sec_map.get(e.section_id, ("", ""))[1],
            "subject_code": subj_map.get(e.subject_id, ("", ""))[0],
            "subject_name": subj_map.get(e.subject_id, ("", ""))[1],
            "teacher_code": teacher_map.get(e.teacher_id, ("", ""))[0],
            "teacher_name": teacher_map.get(e.teacher_id, ("", ""))[1],
            "room_code": room_map.get(e.room_id, ("", ""))[0],
            "room_name": room_map.get(e.room_id, ("", ""))[1],
            "note": e.note or "",
            "is_locked": e.is_locked,
        })
    return pd.DataFrame(rows)


def _pivot(df: pd.DataFrame, index_col: str, cell_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    df["slot"] = df["day"] + " P" + df["period"].astype(str)
    return df.pivot_table(index=index_col, columns="slot", values=cell_col, aggfunc="first").fillna("")


# ---- Registered reports ---------------------------------------------------


def report_class_wise(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    df["cell"] = df["subject_code"].astype(str) + " / " + df["teacher_code"].astype(str)
    df["row"] = df["class_code"].astype(str) + df["section_code"].map(lambda x: f"-{x}" if x else "")
    return _pivot(df, "row", "cell")


def report_teacher_wise(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    df["cell"] = df["class_code"].astype(str) + df["section_code"].map(lambda x: f"-{x}" if x else "") + " / " + df["subject_code"].astype(str)
    return _pivot(df[df["teacher_code"] != ""], "teacher_code", "cell")


def report_subject_wise(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    df["cell"] = df["class_code"].astype(str) + " / " + df["teacher_code"].astype(str)
    return _pivot(df[df["subject_code"] != ""], "subject_code", "cell")


def report_room_wise(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    df["cell"] = df["class_code"].astype(str) + " / " + df["subject_code"].astype(str)
    return _pivot(df[df["room_code"] != ""], "room_code", "cell")


def report_master(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    return _entries_df(db, timetable_id)


def report_teacher_workload(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    grouped = df[df["teacher_code"] != ""].groupby(["teacher_code", "teacher_name"]).size().reset_index(name="periods")
    return grouped.sort_values("periods", ascending=False)


def report_free_teachers(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    teachers = db.query(Teacher).filter(Teacher.project_id == project_id).all()
    if df.empty:
        return pd.DataFrame([{"teacher_code": t.code, "teacher_name": t.name, "busy_periods": 0} for t in teachers])
    busy = df[df["teacher_code"] != ""].groupby("teacher_code").size().to_dict()
    return pd.DataFrame(
        [{"teacher_code": t.code, "teacher_name": t.name, "busy_periods": busy.get(t.code, 0)} for t in teachers]
    ).sort_values("busy_periods")


def report_subject_distribution(db: Session, project_id: str, timetable_id: str) -> pd.DataFrame:
    df = _entries_df(db, timetable_id)
    if df.empty:
        return df
    return df[df["subject_code"] != ""].groupby(["subject_code", "subject_name"]).size().reset_index(name="periods")


REPORTS: Dict[str, Callable[[Session, str, str], pd.DataFrame]] = {
    "class_wise": report_class_wise,
    "teacher_wise": report_teacher_wise,
    "subject_wise": report_subject_wise,
    "room_wise": report_room_wise,
    "master": report_master,
    "teacher_workload": report_teacher_workload,
    "free_teachers": report_free_teachers,
    "subject_distribution": report_subject_distribution,
}


REPORT_LABELS = {
    "class_wise": "Class-wise Timetable",
    "teacher_wise": "Teacher-wise Timetable",
    "subject_wise": "Subject-wise Timetable",
    "room_wise": "Room-wise Timetable",
    "master": "Master Timetable",
    "teacher_workload": "Teacher Workload Report",
    "free_teachers": "Free Teacher List",
    "subject_distribution": "Subject Distribution Report",
}


def render(report: str, fmt: str, df: pd.DataFrame) -> tuple[bytes, str, str]:
    """Return (bytes, filename, content_type)."""
    fmt = fmt.lower()
    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=(df.index.name is not None))
        return buf.getvalue().encode("utf-8"), f"{report}.csv", "text/csv"
    if fmt in {"xlsx", "excel"}:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name=report[:31] or "sheet1", index=(df.index.name is not None))
        return buf.getvalue(), f"{report}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise ValueError(f"Unsupported export format: {fmt} (pdf coming soon)")
