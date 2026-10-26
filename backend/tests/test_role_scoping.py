import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.admin import router as admin_router
from app.api.routes.attendance import router as attendance_router
from app.api.routes.auth import router as auth_router
from app.api.routes.classes import router as classes_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.students import router as students_router
from app.auth import hash_password
from app.config import settings
from app.database.models import (
    AttendanceRecord,
    AuditLog,
    AuthUser,
    Base,
    ClassConfig,
    Session,
    Student,
)
from app.database.session import get_db


def test_teacher_scope_review_and_admin_tools(tmp_path, monkeypatch):
    async def exercise():
        monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-characters")
        monkeypatch.setattr(settings, "APP_ENV", "development")
        database_path = tmp_path / "role-scope.db"
        monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as db:
            admin = AuthUser(
                user_id="admin",
                full_name="Admin",
                password_hash=hash_password("admin-password-123"),
                role="admin",
            )
            teacher = AuthUser(
                user_id="teacher-a",
                full_name="Teacher A",
                password_hash=hash_password("teacher-password-123"),
                role="teacher",
            )
            db.add_all([
                admin,
                teacher,
                ClassConfig(class_name="Class A", instructor="teacher-a", camera_source="0"),
                ClassConfig(class_name="Class B", instructor="teacher-b", camera_source="1"),
                Student(student_id="SVA", full_name="Student A", class_name="Class A"),
                Student(student_id="SVB", full_name="Student B", class_name="Class B"),
            ])
            await db.flush()
            own_session = Session(
                session_name="Own class",
                class_name="Class A",
                instructor="Teacher A",
                start_time=datetime.now(timezone.utc),
                is_active=False,
                status="review",
            )
            other_session = Session(
                session_name="Other class",
                class_name="Class B",
                instructor="Teacher B",
                start_time=datetime.now(timezone.utc),
                is_active=False,
                status="review",
            )
            db.add_all([own_session, other_session])
            await db.commit()
            own_session_id = own_session.id
            other_session_id = other_session.id

        app = FastAPI()
        for router in (auth_router, admin_router, classes_router, students_router, attendance_router, schedules_router):
            app.include_router(router)

        async def override_get_db():
            async with session_factory() as db:
                yield db
                await db.commit()

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={
                "user_id": "teacher-a",
                "password": "teacher-password-123",
                "role": "teacher",
            })
            assert login.status_code == 200
            teacher_classes = (await client.get("/api/classes/")).json()
            assert [item["class_name"] for item in teacher_classes] == ["Class A"]
            assert teacher_classes[0]["camera_source"] == "Đã cấu hình"
            assert (await client.get("/api/students/?limit=200")).status_code == 200
            assert (await client.get("/api/students/?class_name=Class B")).json()["students"] == []
            assert (await client.get("/api/students/SVB")).status_code == 404
            student_export = await client.get("/api/students/export/csv")
            assert student_export.status_code == 200
            assert "SVA" in student_export.text
            assert "SVB" not in student_export.text
            assert [item["class_name"] for item in (await client.get("/api/attendance/sessions")).json()["sessions"]] == ["Class A"]
            assert (await client.get(f"/api/attendance/sessions/{other_session_id}/records")).status_code == 403
            assert (await client.get("/api/attendance/reports?class_name=Class%20B")).status_code == 403
            assert (await client.get("/api/audit-logs")).status_code == 403
            assert (await client.get("/api/admin/backup")).status_code == 403
            assert (await client.post("/api/classes/", json={"class_name": "Class C"})).status_code == 403
            assert (await client.post("/api/schedules", json={
                "class_name": "Class A",
                "course_name": "Course",
                "start_time": "2026-10-26T10:00:00",
                "end_time": "2026-10-26T11:00:00",
            })).status_code == 403

            correction = await client.patch(
                f"/api/attendance/sessions/{own_session_id}/records/SVA",
                json={"status": "absent", "note": "Confirmed by class instructor"},
            )
            assert correction.status_code == 200
            records = (await client.get(f"/api/attendance/sessions/{own_session_id}/records")).json()["records"]
            assert len(records) == 1
            assert records[0]["status"] == "absent"
            assert records[0]["note"] == "Confirmed by class instructor"
            assert (await client.patch(
                f"/api/attendance/sessions/{own_session_id}/records/SVA",
                json={"status": "present", "note": "x"},
            )).status_code == 422
            created_session = await client.post("/api/attendance/sessions", json={
                "session_name": "New class session",
                "course_name": "Attendance",
                "class_name": "Class A",
                "room": None,
                "instructor": None,
            })
            assert created_session.status_code == 200

            await client.post("/api/auth/logout", json={})
            admin_login = await client.post("/api/auth/login", json={
                "user_id": "admin",
                "password": "admin-password-123",
                "role": "admin",
            })
            assert admin_login.status_code == 200
            assert (await client.get("/api/auth/teachers")).status_code == 200
            updated = await client.put("/api/admin/settings", json={
                "face_recognition_threshold": 0.6,
                "face_detection_threshold": 0.55,
                "attendance_late_minutes": 10,
            })
            assert updated.status_code == 200
            assert (await client.get("/api/admin/settings")).json()["attendance_late_minutes"] == 10
            now = datetime.now(timezone.utc)
            schedule = await client.post("/api/schedules", json={
                "class_name": "Class A",
                "course_name": "Security of Data",
                "instructor": "teacher-a",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
            })
            assert schedule.status_code == 200
            backup = await client.get("/api/admin/backup")
            assert backup.status_code == 200
            assert backup.content.startswith(b"SQLite format 3")

        async with session_factory() as db:
            log = await db.scalar(select(AuditLog).where(AuditLog.action == "correct_attendance"))
            assert log is not None
            assert log.actor == "teacher-a"
            assert "Confirmed by class instructor" in log.details
        await engine.dispose()

    asyncio.run(exercise())
