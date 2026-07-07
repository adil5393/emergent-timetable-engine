# Timetable Management System — PRD

## Problem Statement
Build a School Timetable Management System that feels like Microsoft Excel + Odoo + modern scheduling software. Users import Excel/CSV once, then do all editing inside the web app. Data is relational (Teachers ↔ Subjects ↔ Classes/Sections; Constraints; Generated Timetables), so PostgreSQL + SQLAlchemy are mandatory. JWT auth with 3 roles: Administrator, Planner, Viewer. The scheduling engine is external (only an EngineService interface must exist). Generated timetables are versioned and never overwritten. Exports must ship Excel + CSV first with a PDF path preserved.

## Architecture
- **Backend**: FastAPI + SQLAlchemy 2.0 (sync) + PostgreSQL 15 + Alembic-ready models. JWT via PyJWT + bcrypt.
- **Routers**: `auth`, `projects`, `master_data` (generic CRUD for every dataset), `imports` (wizard: schema / upload / commit / summary / templates), `validation`, `timetables` (list / generate / entries / swap / lock / conflicts), `exports` (report registry).
- **Services**: `importer.py` (DATASET_FIELDS + auto column-mapping + commit), `validator.py` (errors/warnings/suggestions with can_generate flag), `engine.py` (`EngineService` Protocol + `StubEngine` placeholder + `build_engine_input`), `exporter.py` (report registry rendering to xlsx/csv; PDF pluggable via same DataFrame contract).
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui. Swiss / high-contrast workstation aesthetic (Chivo + IBM Plex Sans + JetBrains Mono). Sidebar navigation, top ribbon, status bar.

## User Personas
1. **Administrator** — full access, seeds users, manages projects.
2. **Planner** — imports data, edits master data, generates timetables, exports.
3. **Viewer** — read-only observability.

## Core Requirements (delivered)
- Project workspace with academic year, working days, periods/day.
- Import Wizard (upload → auto column mapping → preview → commit) with template save.
- Import Dashboard: 12 dataset cards with record counts, last-imported timestamp, status chips.
- Smart Data Grid on every dataset: search, add/edit (double-click)/delete, save (batched), copy/paste TSV, dense Excel-like styling with sticky headers, row selection.
- Validation Center: errors + warnings + suggestions with per-issue "Go to record" navigation.
- Generate & Versions: pre-flight badges, generation gated on `can_generate`, every version preserved.
- Timetable Editor: Excel-like day × period grid, drag-and-drop swap, cell inspector (subject/teacher/room), lock/unlock, live conflict detection panel.
- Exports: 8 reports (class/teacher/subject/room-wise, master, workload, free teachers, subject distribution) × xlsx & csv.

## What's Been Implemented (2026-02-07)
- Full backend (routers + services + models + auth) with 24/24 pytest cases passing.
- Full frontend (Login, Projects, Import Dashboard, Import Wizard, Master Data grid, Validation Center, Generate & Versions, Timetable Editor, Exports).
- StubEngine end-to-end wired so downstream features are exercisable.
- JWT auth with 3 seeded users.
- Design guidelines applied (Chivo + IBM Plex Sans, dense grids, monochrome).

## Prioritized Backlog

### P0 — Blockers for real deployment
- Plug in the real genetic-algorithm engine into `EngineService` (currently `StubEngine`).
- Wrap `master_data.create_record` in `IntegrityError` handling to return 400 (currently 500 on duplicate code).

### P1 — High value next iteration
- Undo/Redo history for the Smart Data Grid (state ring already exists, wire keyboard shortcuts Ctrl-Z / Ctrl-Y).
- PDF export renderer (register alongside xlsx/csv in `exporter.render`).
- Mapping Templates picker in Import Wizard (backend already exposes `/import/templates`).
- Freeze columns / column resize on the Smart Data Grid.
- Fixed Periods editor UI (backend model + import already exist).
- Section-level and multi-section grid views in Timetable Editor.
- Role management screen (currently seeded from `.env`).

### P2 — Nice to have
- Alembic migrations wired (currently `Base.metadata.create_all` at startup).
- WebSocket-based live validation while editing master data.
- Diff view between two versions of a generated timetable.
- Bulk-edit modal on the Smart Data Grid.
- Audit log per record.

## Test Credentials
See `/app/memory/test_credentials.md`.
