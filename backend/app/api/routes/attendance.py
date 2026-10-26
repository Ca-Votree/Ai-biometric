"""
Attendance API Routes
Quản lý phiên điểm danh và kết quả.
"""
import csv
import datetime
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database.session import get_db
from app.database import crud
from app.database.models import AttendanceRecord, AuthUser, Session, Student
from app.auth import assigned_class_names, require_class_access, require_teacher

router = APIRouter(prefix="/api/attendance", tags=["attendance"], dependencies=[Depends(require_teacher)])


class SessionCreate(BaseModel):
    session_name: str
    course_name: str | None = None
    class_name: str | None = None
    room: str | None = None
    instructor: str | None = None


class RecordDecision(BaseModel):
    status: str
    note: str = Field(min_length=3, max_length=500)


class SessionStatus(BaseModel):
    status: str


async def accessible_session(session_id: int, db: AsyncSession, user: AuthUser) -> Session:
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")
    await require_class_access(db, user, session.class_name)
    return session


@router.post("/sessions")
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Tạo phiên điểm danh mới."""
    await require_class_access(db, user, data.class_name)
    # Kiểm tra có phiên đang active không
    active = await crud.get_active_session(db)
    if active:
        raise HTTPException(
            status_code=400, 
            detail=f"Đang có phiên điểm danh hoạt động: {active.session_name}. "
                   f"Vui lòng kết thúc trước khi tạo phiên mới."
        )
    
    session = await crud.create_session(
        db,
        session_name=data.session_name,
        course_name=data.course_name,
        room=data.room,
        class_name=data.class_name,
        instructor=user.full_name if user.role == "teacher" else (data.instructor or user.full_name),
    )
    await crud.create_audit_log(db, "create_session", "session", str(session.id), user.user_id, data.session_name)
    return {
        "message": f"Đã tạo phiên: {data.session_name}",
        "session_id": session.id,
    }


@router.get("/sessions/active")
async def get_active_session(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy phiên điểm danh đang hoạt động."""
    class_names = await assigned_class_names(db, user)
    sessions = await crud.get_all_sessions(db, limit=5000)
    session = next(
        (item for item in sessions if item.is_active and
         (class_names is None or item.class_name in class_names)),
        None,
    )
    if not session:
        return {"active": False, "session": None}
    
    count = await crud.get_attendance_count(db, session.id)
    
    return {
        "active": True,
        "session": {
            "id": session.id,
            "session_name": session.session_name,
            "course_name": session.course_name,
            "room": session.room,
            "instructor": session.instructor,
            "class_name": session.class_name,
            "status": session.status,
            "start_time": session.start_time.isoformat(),
            "total_recognized": count,
            "total_unknown": session.total_unknown or 0,
        }
    }


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Kết thúc phiên điểm danh."""
    session = await accessible_session(session_id, db, user)
    session.is_active = False
    session.status = "review"
    session.end_time = datetime.datetime.now(datetime.timezone.utc)
    await crud.create_audit_log(db, "review_session", "session", str(session_id), user.user_id, "Chuyển phiên sang duyệt")
    return {"message": f"Đã kết thúc phiên {session_id}"}

@router.patch("/sessions/{session_id}/records/{student_id}")
async def decide_record(
    session_id: int,
    student_id: str,
    data: RecordDecision,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    session = await accessible_session(session_id, db, user)
    if session.status == "locked":
        raise HTTPException(status_code=400, detail="Phiên đã khóa, không thể sửa kết quả")
    if data.status not in {"present", "late", "absent", "rejected"}:
        raise HTTPException(status_code=400, detail="Trạng thái điểm danh không hợp lệ")
    if len(data.note.strip()) < 3:
        raise HTTPException(status_code=400, detail="Lý do cần ít nhất 3 ký tự")
    student = await crud.get_student(db, student_id)
    if not student or student.class_name != session.class_name:
        raise HTTPException(status_code=404, detail="Sinh viên không thuộc lớp của phiên điểm danh")
    records = await crud.get_attendance_by_session(db, session_id)
    record = next((item for item in records if item.student_id == student_id), None)
    old_status = record.status if record else "chưa có bản ghi"
    if not record:
        record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            check_in_time=session.start_time,
            similarity_score=0,
            method="manual",
            status=data.status,
        )
        db.add(record)
    record.status = data.status
    record.note = data.note.strip()
    await crud.create_audit_log(
        db, "correct_attendance", "attendance", str(record.id or student_id), user.user_id,
        f"student={student_id}; status={old_status}->{data.status}; reason={data.note.strip()}",
    )
    return {"message": "Đã cập nhật kết quả duyệt"}

@router.patch("/sessions/{session_id}/status")
async def update_session_status(
    session_id: int,
    data: SessionStatus,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    session = await accessible_session(session_id, db, user)
    if data.status not in {"open", "review", "locked"}:
        raise HTTPException(status_code=400, detail="Trạng thái phiên không hợp lệ")
    session.status = data.status
    session.is_active = data.status == "open"
    await crud.create_audit_log(db, "change_session_status", "session", str(session_id), user.user_id, data.status)
    return {"message": "Đã cập nhật trạng thái phiên", "status": data.status}


@router.get("/sessions")
async def list_sessions(
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy danh sách phiên điểm danh."""
    class_names = await assigned_class_names(db, user)
    sessions = await crud.get_all_sessions(db, skip=0, limit=5000)
    if class_names is not None:
        sessions = [session for session in sessions if session.class_name in class_names]
    sessions = sessions[skip:skip + min(limit, 200)]
    return {
        "sessions": [
            {
                "id": s.id,
                "session_name": s.session_name,
                "course_name": s.course_name,
                "room": s.room,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "class_name": s.class_name,
                "status": s.status or ("open" if s.is_active else "closed"),
                "is_active": s.is_active,
                "total_recognized": s.total_recognized or 0,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}/records")
async def get_records(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy danh sách điểm danh của phiên."""
    session = await accessible_session(session_id, db, user)
    records = await crud.get_attendance_by_session(db, session_id)
    record_by_student = {record.student_id: record for record in records}
    students_result = await db.execute(
        select(Student).where(Student.class_name == session.class_name, Student.is_active.is_(True))
        .order_by(Student.student_id)
    )
    result = []
    for student in students_result.scalars():
        record = record_by_student.get(student.student_id)
        result.append({
            "student_id": student.student_id,
            "full_name": student.full_name,
            "class_name": student.class_name,
            "check_in_time": record.check_in_time.isoformat() if record else None,
            "similarity_score": record.similarity_score if record else None,
            "method": record.method if record else "manual",
            "status": record.status if record else "pending",
            "note": record.note if record else None,
            "confidence": record.confidence if record else None,
        })
    
    return {
        "session_id": session_id,
        "records": result,
        "total": len(result),
    }


@router.get("/dashboard")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Dữ liệu tổng quan cho dashboard."""
    classes = await assigned_class_names(db, user)
    if classes is None:
        students = await crud.get_all_students(db, limit=100000)
    else:
        students = []
        for class_name in classes:
            students.extend(await crud.get_all_students(db, class_name=class_name, limit=100000))
    total_students = len(students)
    registered_students = [student for student in students if student.face_registered]
    sessions = await crud.get_all_sessions(db, limit=5000)
    if classes is not None:
        sessions = [session for session in sessions if session.class_name in classes]
    active_session = next((session for session in sessions if session.is_active), None)
    all_sessions = sessions[:10]
    
    active_count = 0
    if active_session:
        active_count = await crud.get_attendance_count(db, active_session.id)
    
    return {
        "total_students": total_students,
        "registered_faces": len(registered_students),
        "active_session": {
            "id": active_session.id,
            "name": active_session.session_name,
            "attendance_count": active_count,
        } if active_session else None,
        "recent_sessions": [
            {
                "id": s.id,
                "name": s.session_name,
                "date": s.start_time.isoformat() if s.start_time else None,
                "total": s.total_recognized or 0,
            }
            for s in all_sessions
        ],
    }


@router.get("/reports")
async def attendance_report(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    class_names = await assigned_class_names(db, user)
    if class_name:
        await require_class_access(db, user, class_name)
        class_names = {class_name} if class_names is not None else None
    sessions = await crud.get_all_sessions(db, limit=5000)
    sessions = [
        session for session in sessions
        if (class_names is None or session.class_name in class_names)
        and (start_date is None or session.start_time.date() >= start_date)
        and (end_date is None or session.start_time.date() <= end_date)
    ]
    report = []
    for session in sessions:
        records = await crud.get_attendance_by_session(db, session.id)
        roster_result = await db.execute(
            select(func.count(Student.id)).where(
                Student.class_name == session.class_name,
                Student.is_active.is_(True),
            )
        )
        roster_count = roster_result.scalar_one()
        counts = {
            state: sum(record.status == state for record in records)
            for state in ("present", "late", "absent", "rejected", "pending")
        }
        counts["absent"] += max(0, roster_count - len(records))
        total_students = roster_count or len(records)
        report.append({
            "session_id": session.id,
            "session_name": session.session_name,
            "class_name": session.class_name,
            "course_name": session.course_name,
            "start_time": session.start_time.isoformat(),
            "total_students": total_students,
            **counts,
            "attendance_rate": round((counts["present"] + counts["late"]) / total_students * 100, 1) if total_students else 0,
        })
    return {"reports": report}


@router.get("/reports/export.csv")
async def export_attendance_report(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    report_response = await attendance_report(start_date, end_date, class_name, db, user)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Mã phiên", "Tên phiên", "Lớp", "Môn học", "Bắt đầu", "Tổng bản ghi", "Có mặt", "Đi trễ", "Vắng", "Tỷ lệ (%)"])
    for item in report_response["reports"]:
        writer.writerow([
            item["session_id"], item["session_name"], item["class_name"] or "",
            item["course_name"] or "", item["start_time"], item["total_students"],
            item["present"], item["late"], item["absent"], item["attendance_rate"],
        ])
    await crud.create_audit_log(db, "export_attendance_report", "attendance", None, user.user_id, "CSV")
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="attendance-report.csv"'},
    )
