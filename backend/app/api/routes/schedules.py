"""Lịch học, duyệt phiên và nhật ký thao tác."""
import csv
import io
import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database import crud
from app.database.models import AuthUser, ClassConfig, Schedule, Session, Student
from app.auth import assigned_class_names, require_admin, require_class_access, require_teacher

router = APIRouter(prefix="/api", tags=["schedules"], dependencies=[Depends(require_teacher)])


class ScheduleCreate(BaseModel):
    class_name: str
    course_name: str
    instructor: str | None = None
    room: str | None = None
    start_time: datetime.datetime
    end_time: datetime.datetime
    repeat_weekly: bool = False


class SessionCreateFromSchedule(BaseModel):
    schedule_id: int
    session_name: str | None = None


@router.post("/schedules")
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu")
    class_result = await db.execute(select(ClassConfig).where(ClassConfig.class_name == data.class_name))
    class_config = class_result.scalar_one_or_none()
    if not class_config:
        raise HTTPException(status_code=404, detail="Lớp chưa được cấu hình")
    if data.instructor:
        teacher_result = await db.execute(
            select(AuthUser).where(
                AuthUser.user_id == data.instructor,
                AuthUser.role == "teacher",
                AuthUser.is_active.is_(True),
            )
        )
        teacher = teacher_result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=400, detail="Giảng viên được chọn không tồn tại hoặc đã bị khóa")
        if class_config.instructor and class_config.instructor not in {teacher.user_id, teacher.full_name}:
            raise HTTPException(status_code=400, detail="Giảng viên chưa được phân công phụ trách lớp này")
        data.instructor = teacher.user_id
    item = await crud.create_schedule(db, **data.model_dump())
    await crud.create_audit_log(db, "create_schedule", "schedule", str(item.id), user.user_id, data.course_name)
    return {"id": item.id, "message": "Đã tạo lịch học"}


@router.delete("/schedules/{schedule_id}")
async def deactivate_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Lịch học không tồn tại")
    schedule.is_active = False
    await crud.create_audit_log(db, "deactivate_schedule", "schedule", str(schedule_id), user.user_id, schedule.course_name)
    return {"message": "Đã lưu trữ lịch học"}


@router.get("/schedules")
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    items = await crud.get_schedules(db)
    assigned = await assigned_class_names(db, user)
    if assigned is not None:
        items = [item for item in items if item.class_name in assigned]
    return {"schedules": [{
        "id": x.id, "class_name": x.class_name, "course_name": x.course_name,
        "instructor": x.instructor, "room": x.room,
        "start_time": x.start_time.isoformat(), "end_time": x.end_time.isoformat(),
        "repeat_weekly": x.repeat_weekly,
    } for x in items]}


@router.post("/attendance/sessions/from-schedule")
async def create_session_from_schedule(
    data: SessionCreateFromSchedule,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    schedules = await crud.get_schedules(db)
    schedule = next((x for x in schedules if x.id == data.schedule_id), None)
    if not schedule:
        raise HTTPException(status_code=404, detail="Lịch học không tồn tại")
    await require_class_access(db, user, schedule.class_name)
    active = await crud.get_active_session(db)
    if active:
        raise HTTPException(status_code=400, detail="Đang có phiên điểm danh hoạt động")
    session = await crud.create_session(
        db, session_name=data.session_name or schedule.course_name,
        course_name=schedule.course_name, room=schedule.room,
        class_name=schedule.class_name,
        instructor=user.full_name if user.role == "teacher" else schedule.instructor,
    )
    session.status = "open"
    await crud.create_audit_log(db, "create_session", "session", str(session.id), user.user_id, schedule.course_name)
    return {"session_id": session.id, "message": "Đã tạo phiên điểm danh"}


@router.post("/attendance/sessions/{session_id}/review")
async def review_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")
    await require_class_access(db, user, session.class_name)
    if session.status == "locked":
        raise HTTPException(status_code=400, detail="Phiên đã khóa")
    session.status = "review"
    session.is_active = False
    session.end_time = datetime.datetime.now(datetime.timezone.utc)
    await crud.create_audit_log(db, "review_session", "session", str(session_id), user.user_id, "Chuyển sang duyệt kết quả")
    return {"message": "Đã đóng camera, chuyển phiên sang trạng thái duyệt"}


@router.post("/attendance/sessions/{session_id}/lock")
async def lock_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")
    await require_class_access(db, user, session.class_name)
    if session.status == "locked":
        return {"message": "Phiên đã khóa"}
    session.status = "locked"
    session.is_active = False
    await crud.create_audit_log(db, "lock_session", "session", str(session_id), user.user_id, "Khóa kết quả điểm danh")
    return {"message": "Đã khóa phiên điểm danh"}


@router.get("/attendance/sessions/{session_id}/export.csv")
async def export_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")
    await require_class_access(db, user, session.class_name)
    records = await crud.get_attendance_by_session(db, session_id)
    records_by_student = {record.student_id: record for record in records}
    students_result = await db.execute(
        select(Student).where(Student.class_name == session.class_name, Student.is_active.is_(True))
        .order_by(Student.student_id)
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Mã sinh viên", "Họ và tên", "Thời gian", "Độ tương đồng", "Phương thức", "Trạng thái", "Ghi chú"])
    for student in students_result.scalars():
        record = records_by_student.get(student.student_id)
        writer.writerow([
            student.student_id,
            student.full_name,
            record.check_in_time.isoformat() if record else "",
            record.similarity_score if record else "",
            record.method if record else "manual",
            record.status if record else "absent",
            record.note if record and record.note else "",
        ])
    await crud.create_audit_log(db, "export_attendance", "session", str(session_id), user.user_id, "CSV")
    return StreamingResponse(iter(["\ufeff" + output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=session-{session_id}.csv"})


@router.get("/audit-logs")
async def audit_logs(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    logs = await crud.get_audit_logs(db)
    return {"logs": [{"id": x.id, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "actor": x.actor, "details": x.details, "created_at": x.created_at.isoformat()} for x in logs]}
