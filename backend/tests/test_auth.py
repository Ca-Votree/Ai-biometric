import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes.auth import router as auth_router
from app.api.routes.classes import router as classes_router
from app import main as main_module
from app.auth import decode_session_token, hash_password, verify_password
from app.config import settings
from app.database.models import AuthUser, Base
from app.database.session import get_db


def test_password_hashing_and_signed_sessions(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-characters")
    password_hash = hash_password("Correct horse battery staple")
    assert password_hash != "Correct horse battery staple"
    assert verify_password("Correct horse battery staple", password_hash)
    assert not verify_password("incorrect", password_hash)

    user = AuthUser(id=42, user_id="teacher", full_name="Teacher", role="teacher")
    from app.auth import create_session_token

    token = create_session_token(user)
    assert decode_session_token(token) == 42
    assert decode_session_token(token + "x") is None


def test_login_and_role_based_class_permissions(tmp_path, monkeypatch):
    async def exercise():
        monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-characters")
        monkeypatch.setattr(settings, "APP_ENV", "development")
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth-test.db'}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as db:
            db.add_all([
                AuthUser(
                    user_id="admin",
                    full_name="Admin",
                    password_hash=hash_password("admin-password-123"),
                    role="admin",
                ),
                AuthUser(
                    user_id="GV01",
                    full_name="Teacher",
                    password_hash=hash_password("teacher-password-123"),
                    role="teacher",
                ),
            ])
            await db.commit()

        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(classes_router)

        async def override_get_db():
            async with session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid_role = await client.post("/api/auth/login", json={
                "user_id": "admin",
                "password": "admin-password-123",
                "role": "teacher",
            })
            assert invalid_role.status_code == 401

            teacher_login = await client.post("/api/auth/login", json={
                "user_id": "GV01",
                "password": "teacher-password-123",
                "role": "teacher",
            })
            assert teacher_login.status_code == 200
            assert teacher_login.headers["set-cookie"].lower().find("httponly") >= 0
            assert (await client.get("/api/auth/me")).json()["user"]["role"] == "teacher"
            assert (await client.get("/api/classes/")).status_code == 200
            forbidden = await client.post("/api/classes/", json={
                "class_name": "CNTT1",
                "camera_source": "0",
            })
            assert forbidden.status_code == 403

            await client.post("/api/auth/logout", json={})
            admin_login = await client.post("/api/auth/login", json={
                "user_id": "admin",
                "password": "admin-password-123",
                "role": "admin",
            })
            assert admin_login.status_code == 200
            created = await client.post("/api/classes/", json={
                "class_name": "CNTT1",
                "camera_source": "0",
            })
            assert created.status_code == 200

        await engine.dispose()

    asyncio.run(exercise())


def test_frontend_pages_require_a_valid_session(tmp_path, monkeypatch):
    async def exercise():
        monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-characters")
        monkeypatch.setattr(settings, "APP_ENV", "development")
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'page-auth-test.db'}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as db:
            db.add(AuthUser(
                user_id="admin",
                full_name="Admin",
                password_hash=hash_password("admin-password-123"),
                role="admin",
            ))
            db.add(AuthUser(
                user_id="teacher",
                full_name="Teacher",
                password_hash=hash_password("teacher-password-123"),
                role="teacher",
            ))
            await db.commit()

        async def override_get_db():
            async with session_factory() as db:
                yield db

        app = main_module.app
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_get_db
        monkeypatch.setattr(main_module, "async_session_factory", session_factory)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
                follow_redirects=False,
            ) as client:
                protected = await client.get("/students.html")
                assert protected.status_code == 303
                assert protected.headers["location"] == "/login?next=/students.html"
                assert (await client.get("/admin.html")).headers["location"] == "/login?next=/admin.html"
                assert (await client.get("/teacher.html")).headers["location"] == "/login?next=/teacher.html"
                assert (await client.get("/admin-students.html")).headers["location"] == "/login?next=/admin-students.html"
                assert (await client.get("/admin-teachers.html")).headers["location"] == "/login?next=/admin-teachers.html"
                assert (await client.get("/admin-classes.html")).headers["location"] == "/login?next=/admin-classes.html"
                assert (await client.get("/admin-schedules.html")).headers["location"] == "/login?next=/admin-schedules.html"
                assert (await client.get("/admin-settings.html")).headers["location"] == "/login?next=/admin-settings.html"
                assert (await client.get("/admin-audit.html")).headers["location"] == "/login?next=/admin-audit.html"
                assert (await client.get("/admin-backup.html")).headers["location"] == "/login?next=/admin-backup.html"
                assert (await client.get("/teacher-students.html")).headers["location"] == "/login?next=/teacher-students.html"
                assert (await client.get("/monitor.html")).headers["location"] == "/login?next=/monitor.html"
                assert (await client.get("/attendance.html")).headers["location"] == "/login?next=/attendance.html"
                assert (await client.get("/login")).status_code == 200
                assert (await client.get("/api/classes/")).status_code == 401

                logged_in = await client.post("/api/auth/login", json={
                    "user_id": "admin",
                    "password": "admin-password-123",
                    "role": "admin",
                })
                assert logged_in.status_code == 200
                assert (await client.get("/")).headers["location"] == "/admin.html"
                assert (await client.get("/index.html")).headers["location"] == "/admin.html"
                admin_page = await client.get("/admin.html")
                assert admin_page.status_code == 200
                assert "Chọn một khu vực để quản lý" in admin_page.text
                assert "Cấu hình lớp &amp; camera" not in admin_page.text
                assert "Giám sát Live" not in admin_page.text
                assert "Điểm danh" not in admin_page.text
                assert (await client.get("/teacher.html")).headers["location"] == "/admin.html"
                admin_students_page = await client.get("/admin-students.html")
                assert admin_students_page.status_code == 200
                assert "Thêm Sinh viên" in admin_students_page.text
                admin_teachers_page = await client.get("/admin-teachers.html")
                assert admin_teachers_page.status_code == 200
                assert "Tạo tài khoản giảng viên" in admin_teachers_page.text
                admin_classes_page = await client.get("/admin-classes.html")
                assert admin_classes_page.status_code == 200
                assert "Cấu hình lớp" in admin_classes_page.text
                assert (await client.get("/admin-schedules.html")).status_code == 200
                assert (await client.get("/admin-settings.html")).status_code == 200
                assert (await client.get("/admin-audit.html")).status_code == 200
                assert (await client.get("/admin-backup.html")).status_code == 200
                assert (await client.get("/students.html")).headers["location"] == "/admin.html"
                assert (await client.get("/teacher-students.html")).headers["location"] == "/admin.html"
                assert (await client.get("/monitor.html")).headers["location"] == "/admin.html"
                assert (await client.get("/attendance.html")).headers["location"] == "/admin.html"
                assert (await client.get("/static/css/style.css")).status_code == 200

                await client.post("/api/auth/logout", json={})
                teacher_login = await client.post("/api/auth/login", json={
                    "user_id": "teacher",
                    "password": "teacher-password-123",
                    "role": "teacher",
                })
                assert teacher_login.status_code == 200
                assert (await client.get("/")).headers["location"] == "/teacher.html"
                assert (await client.get("/index.html")).headers["location"] == "/teacher.html"
                teacher_page = await client.get("/teacher.html")
                assert teacher_page.status_code == 200
                assert "Giám sát Live" in teacher_page.text
                assert "Điểm danh" in teacher_page.text
                assert "Quản trị hệ thống" not in teacher_page.text
                assert (await client.get("/admin.html")).headers["location"] == "/teacher.html"
                teacher_students_page = await client.get("/teacher-students.html")
                assert teacher_students_page.status_code == 200
                assert "Thêm Sinh viên" not in teacher_students_page.text
                assert "Đăng ký khuôn mặt" in teacher_students_page.text
                assert (await client.get("/students.html")).status_code == 200
                assert (await client.get("/monitor.html")).status_code == 200
                assert (await client.get("/attendance.html")).status_code == 200
                assert (await client.get("/admin-students.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-teachers.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-classes.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-schedules.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-settings.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-audit.html")).headers["location"] == "/teacher.html"
                assert (await client.get("/admin-backup.html")).headers["location"] == "/teacher.html"
        finally:
            app.dependency_overrides = previous_overrides
            await engine.dispose()

    asyncio.run(exercise())
