"""Authentication and account administration endpoints."""
import re
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    hash_password,
    require_admin,
    verify_password,
    get_current_user,
)
from app.config import settings
from app.database.models import AuthUser
from app.database import crud
from app.database.session import get_db

router = APIRouter(prefix="/api/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-password")


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    role: str


class TeacherCreate(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256)


class TeacherStatusUpdate(BaseModel):
    is_active: bool


class TeacherPasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=256)


def user_payload(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "user_id": user.user_id,
        "full_name": user.full_name,
        "role": user.role,
    }


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    if data.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=400, detail="Vai trò đăng nhập không hợp lệ")
    result = await db.execute(select(AuthUser).where(AuthUser.user_id == data.user_id.strip()))
    user = result.scalar_one_or_none()
    valid = bool(user and user.is_active and user.role == data.role)
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    if not verify_password(data.password, password_hash) or not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ID, mật khẩu hoặc vai trò không chính xác")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        samesite="strict",
        path="/",
    )
    await crud.create_audit_log(db, "login", "user", user.user_id, user.user_id, user.role)
    return {"user": user_payload(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        samesite="strict",
        path="/",
    )
    return {"message": "Đã đăng xuất"}


@router.get("/me")
async def current_user(user: AuthUser = Depends(get_current_user)):
    return {"user": user_payload(user)}


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
async def create_teacher(
    data: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    admin: AuthUser = Depends(require_admin),
):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", data.user_id):
        raise HTTPException(status_code=400, detail="ID chỉ được chứa chữ cái, số, dấu chấm, gạch dưới hoặc gạch ngang")
    full_name = data.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Họ tên không được để trống")
    result = await db.execute(select(AuthUser).where(AuthUser.user_id == data.user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ID đăng nhập đã tồn tại")
    teacher = AuthUser(
        user_id=data.user_id,
        full_name=full_name,
        password_hash=hash_password(data.password),
        role="teacher",
    )
    db.add(teacher)
    await db.flush()
    await crud.create_audit_log(db, "create_teacher", "user", teacher.user_id, admin.user_id, "Tạo tài khoản giảng viên")
    return {"user": user_payload(teacher), "message": "Đã tạo tài khoản giảng viên"}


@router.get("/teachers")
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    result = await db.execute(
        select(AuthUser).where(AuthUser.role == "teacher").order_by(AuthUser.full_name)
    )
    return {"teachers": [
        {**user_payload(user), "is_active": user.is_active}
        for user in result.scalars()
    ]}


@router.patch("/teachers/{user_id}")
async def update_teacher_status(
    user_id: str,
    data: TeacherStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AuthUser = Depends(require_admin),
):
    result = await db.execute(
        select(AuthUser).where(AuthUser.user_id == user_id, AuthUser.role == "teacher")
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Tài khoản giảng viên không tồn tại")
    teacher.is_active = data.is_active
    await crud.create_audit_log(
        db, "update_teacher_status", "user", teacher.user_id, admin.user_id,
        "Kích hoạt" if data.is_active else "Khóa tài khoản",
    )
    return {"user": {**user_payload(teacher), "is_active": teacher.is_active}}


@router.post("/teachers/{user_id}/password")
async def reset_teacher_password(
    user_id: str,
    data: TeacherPasswordReset,
    db: AsyncSession = Depends(get_db),
    admin: AuthUser = Depends(require_admin),
):
    result = await db.execute(
        select(AuthUser).where(AuthUser.user_id == user_id, AuthUser.role == "teacher")
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Tài khoản giảng viên không tồn tại")
    teacher.password_hash = hash_password(data.password)
    await crud.create_audit_log(db, "reset_teacher_password", "user", teacher.user_id, admin.user_id, "Đặt lại mật khẩu")
    return {"message": f"Đã đặt lại mật khẩu cho {teacher.user_id}"}


async def seed_admin_account(db: AsyncSession) -> None:
    result = await db.execute(select(AuthUser).where(AuthUser.role == "admin").limit(1))
    if result.scalar_one_or_none():
        return
    if not settings.ADMIN_ID or not settings.ADMIN_PASSWORD:
        raise RuntimeError("Chưa có tài khoản quản trị. Hãy cấu hình ADMIN_ID và ADMIN_PASSWORD trong backend/.env")
    if len(settings.ADMIN_PASSWORD) < 12:
        raise RuntimeError("ADMIN_PASSWORD phải có ít nhất 12 ký tự")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", settings.ADMIN_ID):
        raise RuntimeError("ADMIN_ID chỉ được chứa chữ cái, số, dấu chấm, gạch dưới hoặc gạch ngang")
    exists = await db.execute(select(AuthUser).where(AuthUser.user_id == settings.ADMIN_ID))
    if exists.scalar_one_or_none():
        raise RuntimeError("ADMIN_ID đã được dùng cho tài khoản không phải quản trị viên")
    db.add(AuthUser(
        user_id=settings.ADMIN_ID,
        full_name="Quản trị viên",
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        role="admin",
    ))
    await db.commit()
