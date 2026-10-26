"""Administrator-only operational tools."""
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, settings
from app.database import crud
from app.database.models import AuthUser, SystemSetting
from app.database.session import get_db
from app.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["administration"])


class RuntimeSettingsUpdate(BaseModel):
    face_recognition_threshold: float = Field(ge=0.1, le=0.99)
    face_detection_threshold: float = Field(ge=0.1, le=0.99)
    attendance_late_minutes: int = Field(ge=0, le=120)


async def load_runtime_settings(db: AsyncSession) -> None:
    result = await db.execute(select(SystemSetting))
    values = {item.key: item.value for item in result.scalars()}
    if "face_recognition_threshold" in values:
        settings.FACE_RECOGNITION_THRESHOLD = float(values["face_recognition_threshold"])
    if "face_detection_threshold" in values:
        settings.FACE_DETECTION_THRESHOLD = float(values["face_detection_threshold"])
    if "attendance_late_minutes" in values:
        settings.ATTENDANCE_LATE_MINUTES = int(values["attendance_late_minutes"])


@router.get("/settings")
async def get_runtime_settings(
    _: AuthUser = Depends(require_admin),
):
    return {
        "face_recognition_threshold": settings.FACE_RECOGNITION_THRESHOLD,
        "face_detection_threshold": settings.FACE_DETECTION_THRESHOLD,
        "attendance_late_minutes": settings.ATTENDANCE_LATE_MINUTES,
    }


@router.put("/settings")
async def update_runtime_settings(
    data: RuntimeSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    values = {
        "face_recognition_threshold": str(data.face_recognition_threshold),
        "face_detection_threshold": str(data.face_detection_threshold),
        "attendance_late_minutes": str(data.attendance_late_minutes),
    }
    for key, value in values.items():
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    settings.FACE_RECOGNITION_THRESHOLD = data.face_recognition_threshold
    settings.FACE_DETECTION_THRESHOLD = data.face_detection_threshold
    settings.ATTENDANCE_LATE_MINUTES = data.attendance_late_minutes
    await crud.create_audit_log(db, "update_runtime_settings", "settings", None, user.user_id, str(values))
    return {"message": "Đã cập nhật cấu hình hệ thống", **data.model_dump()}


def _remove_backup(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        from loguru import logger
        logger.exception("Could not remove temporary database backup")


@router.get("/backup")
async def download_database_backup(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise HTTPException(status_code=501, detail="Tải backup hiện chỉ hỗ trợ cơ sở dữ liệu SQLite dạng tệp")
    source_path = Path(url.database)
    if not source_path.is_absolute():
        source_path = BASE_DIR / source_path
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp cơ sở dữ liệu")

    await crud.create_audit_log(db, "download_database_backup", "database", None, user.user_id, "SQLite snapshot")
    await db.commit()

    temporary = tempfile.NamedTemporaryFile(prefix="ai-biometrics-backup-", suffix=".sqlite", delete=False)
    backup_path = temporary.name
    temporary.close()
    try:
        with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
    except Exception:
        _remove_backup(backup_path)
        raise

    background_tasks.add_task(_remove_backup, backup_path)
    return FileResponse(
        backup_path,
        media_type="application/vnd.sqlite3",
        filename="ai-biometrics-backup.sqlite",
        background=background_tasks,
    )
