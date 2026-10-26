"""
FastAPI Main Application
Entry point cho hệ thống điểm danh AI.
"""
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings, BASE_DIR
from app.database.session import async_session_factory, init_db, close_db
from app.auth import SESSION_COOKIE, decode_session_token
from app.database.models import AuthUser

FRONTEND_DIR = BASE_DIR.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup + shutdown events."""
    # === STARTUP ===
    logger.info(f"🚀 Khởi động {settings.APP_NAME}...")
    settings.validate_production_security()
    
    # Tạo các thư mục cần thiết
    dirs_to_create = [
        Path(settings.FACES_DIR),
        Path(settings.FAISS_INDEX_PATH).parent,
        Path(settings.LOG_FILE).parent,
        BASE_DIR / "models",
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
    
    # Khởi tạo Database
    await init_db()
    from app.api.routes.auth import seed_admin_account
    from app.api.routes.admin import load_runtime_settings
    async with async_session_factory() as db:
        await load_runtime_settings(db)
        await seed_admin_account(db)

    logger.info("AI Pipeline sẽ được khởi tạo khi có request đầu tiên (lazy loading)")
    
    logger.info(f"✅ {settings.APP_NAME} API Backend đã sẵn sàng!")
    logger.info(f"📡 API đang chạy tại: http://{settings.HOST}:{settings.PORT}")
    
    yield
    
    # === SHUTDOWN ===
    logger.info("Đang tắt ứng dụng...")
    await close_db()
    logger.info("👋 Đã tắt ứng dụng")


app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống điểm danh tự động sử dụng nhận diện khuôn mặt AI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Enforce same-origin writes and optional API keys alongside user sessions."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        allowed_origins = {str(request.base_url).rstrip("/"), *settings.cors_origin_list}
        if origin and origin not in allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Nguồn yêu cầu không được phép"})
    if (
        settings.API_KEY
        and request.url.path.startswith("/api/")
        and not request.url.path.startswith("/api/auth/")
        and request.headers.get("X-API-Key") != settings.API_KEY
        and decode_session_token(request.cookies.get(SESSION_COOKIE)) is None
    ):
        return JSONResponse(status_code=401, content={"detail": "API key không hợp lệ"})
    return await call_next(request)


# === Register API Routes ===
from app.api.routes.students import router as students_router
from app.api.routes.attendance import router as attendance_router
from app.api.routes.camera import router as camera_router
from app.api.routes.classes import router as classes_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(students_router)
app.include_router(attendance_router)
app.include_router(camera_router)
app.include_router(classes_router)
app.include_router(schedules_router)

if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


async def serve_page(page_name: str, request: Request, user: AuthUser | None = None):
    page = FRONTEND_DIR / page_name
    if not page.is_file():
        return JSONResponse(status_code=404, content={"detail": "Trang không tồn tại"})
    if page_name != "login.html" and not user:
        next_path = quote(request.url.path, safe="/")
        return RedirectResponse(url=f"/login?next={next_path}", status_code=303)
    return FileResponse(page)


@app.get("/")
async def serve_dashboard(request: Request):
    user = await _page_user(request)
    if not user:
        return RedirectResponse(url="/login?next=%2F", status_code=303)
    destination = "/admin.html" if user.role == "admin" else "/teacher.html"
    return RedirectResponse(url=destination, status_code=303)


async def serve_role_dashboard(request: Request, role: str, page_name: str):
    user = await _page_user(request)
    if not user:
        return await serve_page(page_name, request)
    if user.role != role:
        destination = "/admin.html" if user.role == "admin" else "/teacher.html"
        return RedirectResponse(url=destination, status_code=303)
    return await serve_page(page_name, request, user)


async def _page_user(request: Request) -> AuthUser | None:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = decode_session_token(token) if token else None
    if user_id is None:
        return None
    async with async_session_factory() as db:
        user = await db.get(AuthUser, user_id)
        return user if user and user.is_active else None


@app.get("/login")
@app.get("/login.html")
async def serve_login(request: Request):
    return await serve_page("login.html", request)


@app.get("/index.html")
async def serve_dashboard_page(request: Request):
    return await serve_dashboard(request)


@app.get("/admin.html")
async def serve_admin_dashboard(request: Request):
    return await serve_role_dashboard(request, "admin", "admin.html")


@app.get("/teacher.html")
async def serve_teacher_dashboard(request: Request):
    return await serve_role_dashboard(request, "teacher", "teacher.html")


@app.get("/admin-students.html")
async def serve_admin_students_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-students.html")


@app.get("/admin-teachers.html")
async def serve_admin_teachers_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-teachers.html")


@app.get("/admin-classes.html")
async def serve_admin_classes_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-classes.html")


@app.get("/admin-schedules.html")
async def serve_admin_schedules_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-schedules.html")


@app.get("/admin-settings.html")
async def serve_admin_settings_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-settings.html")


@app.get("/admin-audit.html")
async def serve_admin_audit_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-audit.html")


@app.get("/admin-backup.html")
async def serve_admin_backup_page(request: Request):
    return await serve_role_dashboard(request, "admin", "admin-backup.html")


@app.get("/teacher-students.html")
async def serve_teacher_students_page(request: Request):
    return await serve_role_dashboard(request, "teacher", "teacher-students.html")


@app.get("/monitor.html")
async def serve_monitor_page(request: Request):
    return await serve_role_dashboard(request, "teacher", "monitor.html")


@app.get("/students.html")
async def serve_students_page(request: Request):
    return await serve_teacher_students_page(request)


@app.get("/attendance.html")
async def serve_attendance_page(request: Request):
    return await serve_role_dashboard(request, "teacher", "attendance.html")

# === Health Check ===
@app.get("/api/health")
async def health_check():
    """API health check."""
    from app.core.pipeline import recognition_pipeline
    from app.core.matcher import face_matcher
    from app.camera.capture import video_capture
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "pipeline_ready": recognition_pipeline.is_initialized,
        "faiss_vectors": face_matcher.total_vectors if face_matcher.is_initialized else 0,
        "camera_running": video_capture.is_running,
    }
