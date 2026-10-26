"""
CRUD Operations
Các thao tác Create, Read, Update, Delete cho database.
"""
import datetime
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.models import Student, AttendanceRecord, Session, FaceImage, AlertLog, Schedule, AuditLog


# ==================== STUDENT CRUD ====================

async def create_student(
    db: AsyncSession,
    student_id: str,
    full_name: str,
    class_name: str = None,
    department: str = None,
    email: str = None,
    phone: str = None,
) -> Student:
    """Tạo sinh viên mới."""
    student = Student(
        student_id=student_id,
        full_name=full_name,
        class_name=class_name,
        department=department,
        email=email,
        phone=phone,
    )
    db.add(student)
    await db.flush()
    logger.info(f"Đã tạo sinh viên: {student_id} - {full_name}")
    return student


async def get_student(db: AsyncSession, student_id: str) -> Optional[Student]:
    """Lấy thông tin sinh viên theo mã."""
    result = await db.execute(
        select(Student).where(Student.student_id == student_id)
    )
    return result.scalar_one_or_none()


async def get_all_students(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    class_name: str = None,
    face_registered: bool = None,
) -> list[Student]:
    """Lấy danh sách sinh viên với filter."""
    query = select(Student).where(Student.is_active == True)
    
    if class_name:
        query = query.where(Student.class_name == class_name)
    if face_registered is not None:
        query = query.where(Student.face_registered == face_registered)
    
    query = query.offset(skip).limit(limit).order_by(Student.student_id)
    result = await db.execute(query)
    return result.scalars().all()


async def update_student_face_status(
    db: AsyncSession, 
    student_id: str, 
    registered: bool,
    num_images: int = 0,
):
    """Cập nhật trạng thái đăng ký khuôn mặt."""
    student = await get_student(db, student_id)
    if student:
        student.face_registered = registered
        student.num_face_images = num_images
        student.face_registered_at = datetime.datetime.now(datetime.timezone.utc) if registered else None
        await db.flush()


async def get_student_count(db: AsyncSession) -> int:
    """Đếm tổng số sinh viên."""
    result = await db.execute(
        select(func.count(Student.id)).where(Student.is_active == True)
    )
    return result.scalar()


# ==================== SESSION CRUD ====================

async def create_session(
    db: AsyncSession,
    session_name: str,
    course_name: str = None,
    room: str = None,
    class_name: str = None,
    instructor: str = None,
) -> Session:
    """Tạo phiên điểm danh mới."""
    session = Session(
        session_name=session_name,
        course_name=course_name,
        room=room,
        class_name=class_name,
        instructor=instructor,
        start_time=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(session)
    await db.flush()
    logger.info(f"Đã tạo phiên điểm danh: {session_name}")
    return session


async def get_active_session(db: AsyncSession) -> Optional[Session]:
    """Lấy phiên điểm danh đang hoạt động."""
    result = await db.execute(
        select(Session).where(Session.is_active == True).order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()


async def end_session(db: AsyncSession, session_id: int):
    """Kết thúc phiên điểm danh."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        session.is_active = False
        session.end_time = datetime.datetime.now(datetime.timezone.utc)
        await db.flush()


async def get_all_sessions(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> list[Session]:
    """Lấy danh sách phiên điểm danh."""
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


# ==================== ATTENDANCE CRUD ====================

async def record_attendance(
    db: AsyncSession,
    session_id: int,
    student_id: str,
    similarity_score: float,
    confidence: float = None,
    method: str = "auto",
    status: str = "present",
    snapshot_path: str = None,
) -> Optional[AttendanceRecord]:
    """
    Ghi nhận điểm danh.
    Trả về None nếu sinh viên đã được điểm danh trong phiên này.
    """
    # Kiểm tra đã điểm danh chưa
    existing = await db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == student_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.debug(f"Sinh viên {student_id} đã được điểm danh trong phiên {session_id}")
        return None

    record = AttendanceRecord(
        session_id=session_id,
        student_id=student_id,
        similarity_score=similarity_score,
        confidence=confidence,
        method=method,
        status=status,
        snapshot_path=snapshot_path,
    )
    db.add(record)
    await db.flush()
    
    # Cập nhật số lượng trong session
    session_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if session:
        session.total_recognized = (session.total_recognized or 0) + 1
    
    logger.info(f"✅ Điểm danh: {student_id} (similarity={similarity_score:.3f})")
    return record


async def get_attendance_by_session(
    db: AsyncSession, session_id: int
) -> list[AttendanceRecord]:
    """Lấy danh sách điểm danh theo phiên."""
    result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.check_in_time)
    )
    return result.scalars().all()


async def get_attendance_count(db: AsyncSession, session_id: int) -> int:
    """Đếm số sinh viên đã điểm danh trong phiên."""
    result = await db.execute(
        select(func.count(AttendanceRecord.id))
        .where(AttendanceRecord.session_id == session_id)
    )
    return result.scalar()


# ==================== SCHEDULE & AUDIT CRUD ====================

async def create_schedule(db: AsyncSession, **values) -> Schedule:
    schedule = Schedule(**values)
    db.add(schedule)
    await db.flush()
    return schedule


async def get_schedules(db: AsyncSession, limit: int = 100) -> list[Schedule]:
    result = await db.execute(select(Schedule).where(Schedule.is_active == True).order_by(Schedule.start_time).limit(limit))
    return result.scalars().all()


async def create_audit_log(db: AsyncSession, action: str, entity_type: str = None, entity_id: str = None, actor: str = None, details: str = None) -> AuditLog:
    log = AuditLog(action=action, entity_type=entity_type, entity_id=entity_id, actor=actor, details=details)
    db.add(log)
    await db.flush()
    return log


async def get_audit_logs(db: AsyncSession, limit: int = 100) -> list[AuditLog]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return result.scalars().all()


# ==================== ALERT LOG CRUD ====================

async def create_alert(
    db: AsyncSession,
    alert_type: str,
    message: str = None,
    session_id: int = None,
    snapshot_path: str = None,
    similarity_score: float = None,
) -> AlertLog:
    """Tạo log cảnh báo."""
    alert = AlertLog(
        session_id=session_id,
        alert_type=alert_type,
        message=message,
        snapshot_path=snapshot_path,
        similarity_score=similarity_score,
    )
    db.add(alert)
    await db.flush()
    return alert
