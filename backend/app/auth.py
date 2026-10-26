"""Password hashing, signed login sessions, and role authorization."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import AuthUser, ClassConfig
from app.database.session import get_db

SESSION_COOKIE = "ai_biometrics_session"
SESSION_MAX_AGE = 8 * 60 * 60
PASSWORD_ITERATIONS = 310_000


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.urlsafe_b64decode(salt + "==="), int(iterations)
        )
        return hmac.compare_digest(_encode(digest), expected)
    except (ValueError, TypeError):
        return False


def create_session_token(user: AuthUser) -> str:
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({
        "sub": user.id,
        "exp": int(time.time()) + SESSION_MAX_AGE,
    }, separators=(",", ":")).encode())
    signed = f"{header}.{payload}"
    signature = hmac.new(settings.SECRET_KEY.encode(), signed.encode(), hashlib.sha256).digest()
    return f"{signed}.{_encode(signature)}"


def decode_session_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        signed = f"{header}.{payload}"
        expected = _encode(hmac.new(settings.SECRET_KEY.encode(), signed.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "==="))
        if claims.get("exp", 0) <= time.time():
            return None
        return int(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


async def user_from_session(token: str | None, db: AsyncSession) -> AuthUser | None:
    if not token:
        return None
    user_id = decode_session_token(token)
    if user_id is None:
        return None
    user = await db.get(AuthUser, user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    user = await user_from_session(request.cookies.get(SESSION_COOKIE), db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để tiếp tục",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_teacher(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập")
    return user


async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ quản trị viên được phép thực hiện")
    return user


async def assigned_class_names(db: AsyncSession, user: AuthUser) -> set[str] | None:
    """Return a teacher's assigned classes; None represents unrestricted admin access."""
    if user.role == "admin":
        return None
    result = await db.execute(select(ClassConfig.class_name, ClassConfig.instructor))
    return {
        class_name
        for class_name, instructor in result.all()
        if instructor in {user.user_id, user.full_name}
    }


async def require_class_access(db: AsyncSession, user: AuthUser, class_name: str | None) -> None:
    if not class_name:
        raise HTTPException(status_code=403, detail="Phiên này chưa được gán lớp")
    assigned = await assigned_class_names(db, user)
    if assigned is not None and class_name not in assigned:
        raise HTTPException(status_code=403, detail="Bạn không được phân công lớp này")
