"""
Student Management API Routes
Quản lý thông tin sinh viên và đăng ký khuôn mặt.
"""
import os
import re
import shutil
import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database.session import get_db
from app.database import crud
from app.core.pipeline import recognition_pipeline
from app.auth import assigned_class_names, require_admin, require_teacher
from app.database.models import AuthUser, FaceImage

router = APIRouter(prefix="/api/students", tags=["students"], dependencies=[Depends(require_teacher)])


def remove_face_files_and_vectors(student_id: str, force: bool = False) -> None:
    from app.core.matcher import face_matcher

    face_root = Path(settings.FACES_DIR).resolve()
    face_dir = (face_root / student_id).resolve()
    if face_dir.parent != face_root:
        raise HTTPException(status_code=400, detail="Đường dẫn dữ liệu khuôn mặt không hợp lệ")
    if force or face_dir.exists():
        face_matcher.initialize()
    if face_matcher.is_initialized:
        face_matcher.remove_student(student_id)
    if face_dir.exists():
        shutil.rmtree(face_dir)


@router.get("/")
async def list_students(
    skip: int = 0,
    limit: int = 100,
    class_name: str = None,
    face_registered: bool = None,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy danh sách sinh viên."""
    assigned = await assigned_class_names(db, user)
    if assigned is not None:
        if not assigned:
            return {"students": [], "total": 0}
        if class_name and class_name not in assigned:
            return {"students": [], "total": 0}
        if class_name is None and len(assigned) == 1:
            class_name = next(iter(assigned))
            students = await crud.get_all_students(
                db, skip=skip, limit=min(limit, 500), class_name=class_name,
                face_registered=face_registered,
            )
        elif class_name is None:
            result = []
            for assigned_class in sorted(assigned):
                result.extend(await crud.get_all_students(
                    db, limit=100000, class_name=assigned_class,
                    face_registered=face_registered,
                ))
            students = sorted(result, key=lambda student: student.student_id)[skip:skip + min(limit, 500)]
        else:
            students = await crud.get_all_students(
                db, skip=skip, limit=limit, class_name=class_name,
                face_registered=face_registered,
            )
    else:
        students = await crud.get_all_students(
            db, skip=skip, limit=limit,
            class_name=class_name, face_registered=face_registered
        )
    return {
        "students": [
            {
                "student_id": s.student_id,
                "full_name": s.full_name,
                "class_name": s.class_name,
                "department": s.department,
                "face_registered": s.face_registered,
                "num_face_images": s.num_face_images,
            }
            for s in students
        ],
        "total": len(students),
    }


@router.post("/")
async def create_student(
    student_id: str = Form(...),
    full_name: str = Form(...),
    class_name: str = Form(None),
    department: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """Tạo sinh viên mới."""
    if not re.fullmatch(r"[A-Za-z0-9]{1,20}", student_id):
        raise HTTPException(status_code=400, detail="Mã sinh viên chỉ được gồm 1-20 chữ cái hoặc chữ số")
    full_name = full_name.strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Họ tên sinh viên không được để trống")
    existing = await crud.get_student(db, student_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Sinh viên {student_id} đã tồn tại")

    student = await crud.create_student(
        db, student_id=student_id, full_name=full_name,
        class_name=class_name, department=department,
        email=email, phone=phone,
    )
    if file and file.filename:
        import cv2
        import numpy as np
        face_dir = Path(settings.FACES_DIR) / student_id
        face_dir.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="Ảnh khuôn mặt không hợp lệ")
        file_path = face_dir / f"face_1{Path(file.filename).suffix}"
        file_path.write_bytes(content)
        result = recognition_pipeline.register_face(student_id, [image])
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        await crud.update_student_face_status(
            db, student_id, registered=True,
            num_images=result["num_images_processed"],
        )
    await crud.create_audit_log(db, "create_student", "student", student_id, user.user_id, "Tạo hồ sơ sinh viên")
    return {"message": f"Đã tạo sinh viên {student_id}", "student_id": student_id}


@router.put("/{student_id}")
async def update_student(
    student_id: str,
    full_name: str = Form(...),
    class_name: str = Form(None),
    department: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    student = await crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")
    student.full_name = full_name
    student.class_name = class_name
    student.department = department
    student.email = email
    student.phone = phone
    await db.flush()
    await crud.create_audit_log(db, "update_student", "student", student_id, user.user_id, "Cập nhật thông tin")
    return {"message": f"Đã cập nhật sinh viên {student_id}"}


@router.delete("/{student_id}")
async def delete_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    student = await crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")
    remove_face_files_and_vectors(student_id, force=student.face_registered)
    student.is_active = False
    student.face_registered = False
    student.face_registered_at = None
    student.num_face_images = 0
    await db.execute(delete(FaceImage).where(FaceImage.student_id == student_id))
    await db.flush()
    await crud.create_audit_log(
        db, "deactivate_student", "student", student_id, user.user_id,
        "Lưu trữ hồ sơ và xóa ảnh/vector khuôn mặt",
    )
    return {"message": f"Đã vô hiệu hóa sinh viên {student_id}"}


@router.get("/{student_id}")
async def get_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Lấy thông tin sinh viên."""
    student = await crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")
    assigned = await assigned_class_names(db, user)
    if assigned is not None and student.class_name not in assigned:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")
    
    return {
        "student_id": student.student_id,
        "full_name": student.full_name,
        "class_name": student.class_name,
        "department": student.department,
        "email": student.email,
        "phone": student.phone,
        "face_registered": student.face_registered,
        "num_face_images": student.num_face_images,
        "created_at": student.created_at.isoformat() if student.created_at else None,
    }


@router.post("/{student_id}/register-face")
async def register_face(
    student_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Đăng ký khuôn mặt cho sinh viên.
    Upload nhiều ảnh khuôn mặt để tăng độ chính xác.
    """
    import cv2
    import numpy as np
    
    if not re.fullmatch(r"[A-Za-z0-9]{1,20}", student_id):
        raise HTTPException(status_code=400, detail="Mã sinh viên không hợp lệ")

    # Kiểm tra sinh viên tồn tại
    student = await crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")

    # Lưu ảnh và đọc vào numpy array
    face_dir = Path(settings.FACES_DIR) / student_id
    face_dir.mkdir(parents=True, exist_ok=True)
    
    images = []
    for i, file in enumerate(files):
        # Lưu ảnh gốc
        file_path = face_dir / f"face_{i+1}{Path(file.filename).suffix}"
        content = await file.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Đọc ảnh bằng OpenCV
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is not None:
            images.append(img)

    if not images:
        raise HTTPException(status_code=400, detail="Không có ảnh hợp lệ nào")

    # Đăng ký qua pipeline
    result = recognition_pipeline.register_face(student_id, images)
    
    if result["success"]:
        await crud.update_student_face_status(
            db, student_id, registered=True, num_images=result["num_images_processed"]
        )
        await crud.create_audit_log(
            db, "register_student_face", "student", student_id, user.user_id,
            f"Đăng ký {result['num_images_processed']} ảnh",
        )
        return result
    else:
        raise HTTPException(status_code=400, detail=result["message"])


@router.delete("/{student_id}/face")
async def delete_face_data(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    if not student_id.isalnum():
        raise HTTPException(status_code=400, detail="Mã sinh viên không hợp lệ")
    student = await crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không tồn tại")

    remove_face_files_and_vectors(student_id, force=True)
    await db.execute(delete(FaceImage).where(FaceImage.student_id == student_id))
    student.face_registered = False
    student.face_registered_at = None
    student.num_face_images = 0
    await crud.create_audit_log(db, "delete_student_face_data", "student", student_id, user.user_id, "Xóa ảnh và vector khuôn mặt")
    return {"message": f"Đã xóa dữ liệu khuôn mặt của sinh viên {student_id}"}


@router.get("/export/csv")
async def export_students(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    assigned = await assigned_class_names(db, user)
    students = []
    if assigned is None:
        students = await crud.get_all_students(db, limit=100000)
    else:
        for class_name in sorted(assigned):
            students.extend(await crud.get_all_students(db, class_name=class_name, limit=100000))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Mã sinh viên", "Họ và tên", "Lớp", "Khoa", "Đã đăng ký khuôn mặt"])
    for student in students:
        writer.writerow([
            student.student_id, student.full_name, student.class_name or "",
            student.department or "", "Có" if student.face_registered else "Không",
        ])
    await crud.create_audit_log(db, "export_students", "student", None, user.user_id, "CSV")
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students.csv"'},
    )


@router.get("/stats/overview")
async def student_stats(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Thống kê tổng quan sinh viên."""
    assigned = await assigned_class_names(db, user)
    students = []
    if assigned is None:
        students = await crud.get_all_students(db, limit=100000)
    else:
        for assigned_class in sorted(assigned):
            students.extend(await crud.get_all_students(db, class_name=assigned_class, limit=100000))
    total = len(students)
    registered = [student for student in students if student.face_registered]
    
    return {
        "total_students": total,
        "face_registered": len(registered),
        "face_not_registered": total - len(registered),
    }
