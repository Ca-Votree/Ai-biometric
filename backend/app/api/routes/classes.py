"""
Class Config & Management API
Quản lý lớp học, gân camera và giảng viên (Admin / Teacher).
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models import AuthUser, ClassConfig
from app.database import crud
from app.auth import assigned_class_names, require_admin, require_teacher

router = APIRouter(prefix="/api/classes", tags=["classes"])


class ClassConfigCreate(BaseModel):
    class_name: str
    camera_source: str = "0"
    instructor: str | None = None
    room: str | None = None


@router.get("/")
async def list_classes(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy danh sách cấu hình lớp học."""
    result = await db.execute(select(ClassConfig).order_by(ClassConfig.class_name))
    configs = result.scalars().all()
    assigned = await assigned_class_names(db, user)
    if assigned is not None:
        configs = [config for config in configs if config.class_name in assigned]
    teacher_ids = {config.instructor for config in configs if config.instructor}
    teachers_result = await db.execute(
        select(AuthUser).where(AuthUser.user_id.in_(teacher_ids), AuthUser.role == "teacher")
    ) if teacher_ids else None
    teachers = {teacher.user_id: teacher.full_name for teacher in teachers_result.scalars()} if teachers_result else {}
    return [
        {
            "id": c.id,
            "class_name": c.class_name,
            "camera_source": c.camera_source if user.role == "admin" else ("Đã cấu hình" if c.camera_source else "Chưa cấu hình"),
            "instructor": teachers.get(c.instructor, c.instructor),
            "instructor_id": c.instructor,
            "room": c.room,
        }
        for c in configs
    ]


@router.post("/")
async def upsert_class_config(
    data: ClassConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """Admin tạo hoặc cập nhật cấu hình lớp học (gán camera, giảng viên)."""
    data.class_name = data.class_name.strip()
    if not data.class_name:
        raise HTTPException(status_code=400, detail="Tên lớp không được để trống")
    if data.instructor:
        teacher_result = await db.execute(
            select(AuthUser).where(
                AuthUser.user_id == data.instructor,
                AuthUser.role == "teacher",
                AuthUser.is_active.is_(True),
            )
        )
        if not teacher_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Giảng viên được chọn không tồn tại hoặc đã bị khóa")
    result = await db.execute(select(ClassConfig).where(ClassConfig.class_name == data.class_name))
    config = result.scalar_one_or_none()

    if config:
        config.camera_source = data.camera_source
        config.instructor = data.instructor
        config.room = data.room
    else:
        config = ClassConfig(
            class_name=data.class_name,
            camera_source=data.camera_source,
            instructor=data.instructor,
            room=data.room,
        )
        db.add(config)

    await crud.create_audit_log(
        db, "upsert_class_config", "class", str(config.id), user.user_id,
        f"class={data.class_name}; instructor={data.instructor or ''}; room={data.room or ''}",
    )
    await db.commit()
    return {"status": "success", "message": f"Đã lưu cấu hình cho lớp {data.class_name}"}
