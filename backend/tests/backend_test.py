"""End-to-end backend tests for the Timetable Management System.

Covers auth, projects CRUD, import wizard, master data CRUD, validation,
timetable generation & editing, and exports.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN = {"email": "admin@timetable.app", "password": "admin123"}
PLANNER = {"email": "planner@timetable.app", "password": "planner123"}
VIEWER = {"email": "viewer@timetable.app", "password": "viewer123"}


# ----------------- helpers -----------------

def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="session")
def planner_token():
    return _login(PLANNER)


@pytest.fixture(scope="session")
def viewer_token():
    return _login(VIEWER)


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture(scope="session")
def project_id(admin_headers):
    """Create a fresh test project for this run."""
    payload = {
        "name": f"TEST_Project_{uuid.uuid4().hex[:6]}",
        "year": "2026",
        "working_days": 5,
        "periods_per_day": 8,
    }
    r = requests.post(f"{BASE}/api/projects", json=payload, headers=admin_headers, timeout=30)
    assert r.status_code == 200, f"project create: {r.status_code} {r.text}"
    return r.json()["id"]


# ----------------- Auth -----------------

class TestAuth:
    def test_admin_login_returns_token_and_user(self):
        r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "admin"

    def test_login_bad_credentials(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@timetable.app", "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me_endpoint(self, admin_headers):
        r = requests.get(f"{BASE}/api/auth/me", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_no_token(self):
        r = requests.get(f"{BASE}/api/auth/me", timeout=30)
        assert r.status_code == 401

    def test_viewer_cannot_write(self, viewer_headers):
        # viewer trying to create a project should be forbidden
        r = requests.post(
            f"{BASE}/api/projects",
            json={"name": "TEST_viewer_denied", "year": "2026", "working_days": 5, "periods_per_day": 8},
            headers=viewer_headers,
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


# ----------------- Projects CRUD -----------------

class TestProjects:
    def test_list_projects(self, admin_headers):
        r = requests.get(f"{BASE}/api/projects", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_project_detail(self, admin_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["id"] == project_id

    def test_update_project(self, admin_headers, project_id):
        r = requests.put(
            f"{BASE}/api/projects/{project_id}",
            json={"name": "TEST_Project_Updated", "year": "2026", "working_days": 5, "periods_per_day": 8},
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Project_Updated"

    def test_delete_project_lifecycle(self, admin_headers):
        # Create a throwaway project and delete it
        payload = {"name": f"TEST_delete_{uuid.uuid4().hex[:6]}", "year": "2026", "working_days": 5, "periods_per_day": 6}
        c = requests.post(f"{BASE}/api/projects", json=payload, headers=admin_headers, timeout=30)
        assert c.status_code == 200
        pid = c.json()["id"]
        d = requests.delete(f"{BASE}/api/projects/{pid}", headers=admin_headers, timeout=30)
        assert d.status_code == 200
        g = requests.get(f"{BASE}/api/projects/{pid}", headers=admin_headers, timeout=30)
        assert g.status_code == 404


# ----------------- Import wizard -----------------

DATASET_FILES = {
    "teachers": "/tmp/teachers.xlsx",
    "subjects": "/tmp/subjects.xlsx",
    "classes": "/tmp/classes.xlsx",
    "teacher_mapping": "/tmp/teacher_mapping.xlsx",
}


class TestImports:
    def test_schema(self, admin_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}/import/schema", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        datasets = r.json()["datasets"]
        keys = {d["dataset_type"] for d in datasets}
        assert "teachers" in keys and "subjects" in keys and "classes" in keys and "teacher_mapping" in keys

    def _upload_and_commit(self, admin_headers, project_id, dataset, file_path):
        with open(file_path, "rb") as fh:
            files = {"file": (os.path.basename(file_path), fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            data = {"dataset_type": dataset}
            up = requests.post(
                f"{BASE}/api/projects/{project_id}/import/upload",
                files=files, data=data, headers=admin_headers, timeout=60,
            )
        assert up.status_code == 200, f"upload {dataset}: {up.status_code} {up.text}"
        body = up.json()
        assert "file_token" in body and body["columns"] and body["rows"]
        assert isinstance(body["suggested_map"], dict)

        commit_payload = {
            "dataset_type": dataset,
            "file_token": body["file_token"],
            "column_map": body["suggested_map"],
            "filename": os.path.basename(file_path),
        }
        cm = requests.post(
            f"{BASE}/api/projects/{project_id}/import/commit",
            json=commit_payload, headers=admin_headers, timeout=60,
        )
        assert cm.status_code == 200, f"commit {dataset}: {cm.status_code} {cm.text}"
        return cm.json()

    def test_upload_and_commit_all_core_datasets(self, admin_headers, project_id):
        # Must be committed in this order so FKs by code resolve
        order = ["teachers", "subjects", "classes", "teacher_mapping"]
        for ds in order:
            res = self._upload_and_commit(admin_headers, project_id, ds, DATASET_FILES[ds])
            assert res["imported_rows"] > 0, f"{ds} imported 0 rows: {res}"
            assert res["error_rows"] == 0, f"{ds} had errors: {res.get('errors')}"

    def test_summary_reflects_counts(self, admin_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}/import/summary", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        summary = {row["dataset_type"]: row["record_count"] for row in r.json()}
        for ds in ["teachers", "subjects", "classes", "teacher_mapping"]:
            assert summary.get(ds, 0) > 0, f"{ds} count is zero: {summary}"


# ----------------- Master data CRUD -----------------

class TestMasterData:
    def test_list_teachers(self, admin_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}/data/teachers", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "rows" in body and body["total"] >= 1

    def test_search_filter(self, admin_headers, project_id):
        # Fetch first teacher name and search for a substring
        r = requests.get(f"{BASE}/api/projects/{project_id}/data/teachers", headers=admin_headers, timeout=30)
        rows = r.json()["rows"]
        if not rows:
            pytest.skip("no teacher rows to search")
        needle = rows[0]["name"][:3]
        r2 = requests.get(
            f"{BASE}/api/projects/{project_id}/data/teachers",
            params={"q": needle}, headers=admin_headers, timeout=30,
        )
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1

    def test_create_update_delete_and_bulk_delete(self, admin_headers, project_id):
        # Create
        c = requests.post(
            f"{BASE}/api/projects/{project_id}/data/subjects",
            json={"code": "TEST_S1", "name": "TEST Subject One", "weekly_periods": 3},
            headers=admin_headers, timeout=30,
        )
        assert c.status_code == 200, c.text
        sid = c.json()["id"]

        # Update
        u = requests.put(
            f"{BASE}/api/projects/{project_id}/data/subjects/{sid}",
            json={"name": "TEST Subject Updated"},
            headers=admin_headers, timeout=30,
        )
        assert u.status_code == 200 and u.json()["name"] == "TEST Subject Updated"

        # Create a second one, then bulk delete both
        c2 = requests.post(
            f"{BASE}/api/projects/{project_id}/data/subjects",
            json={"code": "TEST_S2", "name": "TEST Subject Two", "weekly_periods": 2},
            headers=admin_headers, timeout=30,
        )
        assert c2.status_code == 200
        sid2 = c2.json()["id"]

        bd = requests.post(
            f"{BASE}/api/projects/{project_id}/data/subjects/bulk-delete",
            json={"ids": [sid, sid2]}, headers=admin_headers, timeout=30,
        )
        assert bd.status_code == 200
        assert bd.json()["deleted"] == 2


# ----------------- Validation -----------------

class TestValidation:
    def test_can_generate_after_core_import(self, admin_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}/validation", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        rep = r.json()
        for k in ("errors", "warnings", "infos", "can_generate", "issues"):
            assert k in rep
        assert rep["can_generate"] is True, f"validation says cannot generate: {rep}"

    def test_can_not_generate_with_no_teachers(self, admin_headers):
        """Create fresh project with only subjects to verify can_generate=False."""
        p = requests.post(
            f"{BASE}/api/projects",
            json={"name": f"TEST_no_teachers_{uuid.uuid4().hex[:5]}", "year": "2026", "working_days": 5, "periods_per_day": 6},
            headers=admin_headers, timeout=30,
        ).json()
        pid = p["id"]
        r = requests.get(f"{BASE}/api/projects/{pid}/validation", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["can_generate"] is False


# ----------------- Timetable generate + edit + exports -----------------

class TestTimetables:
    def test_generate_v1_and_v2(self, admin_headers, project_id):
        r1 = requests.post(
            f"{BASE}/api/projects/{project_id}/timetables/generate",
            json={"name": "TEST v1"}, headers=admin_headers, timeout=120,
        )
        assert r1.status_code == 200, r1.text
        tt1 = r1.json()
        assert tt1["version"] == 1
        assert tt1["status"] == "completed"

        r2 = requests.post(
            f"{BASE}/api/projects/{project_id}/timetables/generate",
            json={"name": "TEST v2"}, headers=admin_headers, timeout=120,
        )
        assert r2.status_code == 200, r2.text
        tt2 = r2.json()
        assert tt2["version"] == 2

        # Save ids for downstream tests
        pytest.tt_id = tt2["id"]

    def test_entries_and_toggle_lock(self, admin_headers, project_id):
        tt_id = getattr(pytest, "tt_id", None)
        assert tt_id, "generate test must run first"
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/entries",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) > 0
        entry_id = entries[0]["id"]
        prev_lock = entries[0]["is_locked"]

        tog = requests.post(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/entries/{entry_id}/toggle-lock",
            headers=admin_headers, timeout=30,
        )
        assert tog.status_code == 200
        assert tog.json()["is_locked"] != prev_lock

    def test_conflicts(self, admin_headers, project_id):
        tt_id = getattr(pytest, "tt_id", None)
        assert tt_id
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/conflicts",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200
        assert "count" in r.json() and "conflicts" in r.json()


class TestExports:
    def test_reports_list_has_8_keys(self, admin_headers, project_id):
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/reports/list",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200
        keys = {row["key"] for row in r.json()}
        expected = {"class_wise", "teacher_wise", "subject_wise", "room_wise",
                    "master", "teacher_workload", "free_teachers", "subject_distribution"}
        assert keys == expected, f"reports mismatch: {keys}"

    def test_export_xlsx(self, admin_headers, project_id):
        tt_id = getattr(pytest, "tt_id", None)
        assert tt_id
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/export",
            params={"report": "class_wise", "fmt": "xlsx"},
            headers=admin_headers, timeout=60,
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(r.content) > 100

    def test_export_csv(self, admin_headers, project_id):
        tt_id = getattr(pytest, "tt_id", None)
        assert tt_id
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/export",
            params={"report": "master", "fmt": "csv"},
            headers=admin_headers, timeout=60,
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")

    def test_export_pdf_returns_400(self, admin_headers, project_id):
        tt_id = getattr(pytest, "tt_id", None)
        assert tt_id
        r = requests.get(
            f"{BASE}/api/projects/{project_id}/timetables/{tt_id}/export",
            params={"report": "class_wise", "fmt": "pdf"},
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 400
