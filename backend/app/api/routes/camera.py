"""
Camera Control & WebSocket Streaming
API cho điều khiển camera và streaming video real-time.
"""
import asyncio
import datetime

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.camera.capture import video_capture, frame_processor
from app.core.pipeline import recognition_pipeline
from app.database.session import get_db, async_session_factory
from app.database import crud
from app.auth import SESSION_COOKIE, require_class_access, require_teacher, user_from_session
from app.config import settings
from app.database.models import AuthUser, ClassConfig

router = APIRouter(prefix="/api/camera", tags=["camera"])

async def camera_source_for_class(class_name: str, db: AsyncSession, user: AuthUser) -> str:
    await require_class_access(db, user, class_name)
    result = await db.execute(select(ClassConfig).where(ClassConfig.class_name == class_name))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình camera của lớp")
    return config.camera_source or "0"

@router.post("/start")
async def start_camera(
    class_name: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Bắt đầu capture camera."""
    source = await camera_source_for_class(class_name, db, user)
    if video_capture.is_running:
        if str(video_capture.source) != str(source):
            raise HTTPException(status_code=409, detail="Một nguồn camera khác đang chạy. Hãy tắt trước khi chuyển lớp.")
        return {"status": "already_running", "message": "Camera đang chạy"}
    
    success = video_capture.start(source)
    if success:
        await crud.create_audit_log(db, "start_camera", "class", class_name, user.user_id, "Camera started")
        return {"status": "started", "message": "Camera đã bắt đầu"}
    else:
        return {"status": "error", "message": "Không thể mở camera"}


@router.post("/stop")
async def stop_camera(
    class_name: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_teacher),
):
    """Dừng camera."""
    source = await camera_source_for_class(class_name, db, user)
    if video_capture.is_running and str(video_capture.source) != str(source):
        raise HTTPException(status_code=403, detail="Bạn không thể dừng camera của lớp khác")
    video_capture.stop()
    await crud.create_audit_log(db, "stop_camera", "class", class_name, user.user_id, "Camera stopped")
    return {"status": "stopped", "message": "Camera đã dừng"}


@router.get("/status")
async def camera_status(_: AuthUser = Depends(require_teacher)):
    """Kiểm tra trạng thái camera."""
    return {
        "running": video_capture.is_running,
        "fps": round(video_capture.fps, 1),
        "frame_count": video_capture.frame_count,
    }


@router.websocket("/ws/stream")
async def video_stream(websocket: WebSocket):
    """
    WebSocket endpoint cho live video streaming + recognition + liveness.
    """
    origin = websocket.headers.get("origin")
    same_origin = f"{websocket.url.scheme.replace('ws', 'http')}://{websocket.url.netloc}"
    if origin and origin not in {*settings.cors_origin_list, same_origin}:
        await websocket.close(code=4403, reason="Origin not allowed")
        return
    class_name = websocket.query_params.get("class_name")
    async with async_session_factory() as db:
        user = await user_from_session(websocket.cookies.get(SESSION_COOKIE), db)
    if not user or user.role not in {"teacher", "admin"}:
        await websocket.close(code=4401, reason="Authentication required")
        return
    source = None
    if class_name:
        try:
            async with async_session_factory() as db:
                source = await camera_source_for_class(class_name, db, user)
        except HTTPException as error:
            await websocket.close(code=4403, reason=error.detail)
            return
        if str(video_capture.source) != str(source):
            await websocket.close(code=4409, reason="Camera source is not running for this class")
            return
    elif user.role != "admin":
        await websocket.close(code=4403, reason="Chọn một lớp được phân công")
        return
    await websocket.accept()
    logger.info("WebSocket client đã kết nối")



    # Luồng xử lý AI background
    try:
        from fastapi.concurrency import run_in_threadpool
        
        # Cache đơn giản cho thông tin sinh viên để tránh query DB quá nhiều
        student_cache = {}

        async def get_student_info(db, student_id):
            if student_id in student_cache:
                return student_cache[student_id]
            student = await crud.get_student(db, student_id)
            if student:
                student_cache[student_id] = (student.full_name, student.class_name)
                return student_cache[student_id]
            return ("Unknown", None)

        async def process_and_send_result(process_frame):
            try:
                # Xử lý recognition (không vẽ đè để gửi kết quả sạch bên dưới, nhưng có thể lấy data)
                result = await run_in_threadpool(recognition_pipeline.process_frame, process_frame, annotate=False)
                
                if result:
                    # Logic ghi nhận điểm danh & lấy thông tin thêm
                    faces_data = []
                    async with async_session_factory() as db:
                        active_session = await crud.get_active_session(db)
                        if class_name and active_session and active_session.class_name != class_name:
                            active_session = None
                        
                        for face in result.faces:
                            full_name = "Unknown"
                            visible_student_id = face.student_id
                            visible_identified = face.identified
                            if face.identified:
                                full_name, student_class = await get_student_info(db, face.student_id)
                                if class_name and student_class != class_name:
                                    full_name = "Unknown"
                                    visible_student_id = None
                                    visible_identified = False
                                
                                # Ghi nhận điểm danh nếu session đang mở
                                if active_session and visible_identified:
                                    now = datetime.datetime.now(datetime.timezone.utc)
                                    session_start = active_session.start_time
                                    if session_start.tzinfo is None:
                                        session_start = session_start.replace(tzinfo=datetime.timezone.utc)
                                    status = (
                                        "late"
                                        if now > session_start + datetime.timedelta(minutes=settings.ATTENDANCE_LATE_MINUTES)
                                        else "pending"
                                    )
                                    await crud.record_attendance(
                                        db,
                                        session_id=active_session.id,
                                        student_id=face.student_id,
                                        similarity_score=face.similarity,
                                        confidence=face.det_score,
                                        status=status,
                                    )
                            
                            faces_data.append({
                                "student_id": visible_student_id,
                                "full_name": full_name,
                                "identified": visible_identified,
                                "similarity": round(face.similarity, 3),
                                "bbox": face.bbox,
                                "landmarks": face.landmarks,
                            })
                        
                        if active_session:
                            await db.commit()

                    # Gửi kết quả nhận diện đầy đủ
                    await websocket.send_json({
                        "type": "recognition",
                        "frame_id": result.frame_id,
                        "processing_time_ms": round(result.processing_time_ms, 1),
                        "total_faces": result.total_faces,
                        "identified": result.identified_count,
                        "faces": faces_data,
                    })
            except asyncio.CancelledError:
                pass
            except RuntimeError as e:
                # Bỏ qua lỗi ngắt kết nối đột ngột của WebSocket
                if "close" not in str(e).lower() and "completed" not in str(e).lower():
                    logger.error(f"RuntimeError in background AI task: {e}")
            except Exception as e:
                logger.error(f"Error in background AI task: {e}")

        ai_task = None

        # Luồng lắng nghe lệnh từ Client (UI)
        async def listen_for_client():
            try:
                while True:
                    data = await websocket.receive_json()
                    # Không còn liveness commands
            except Exception:
                pass

        listen_task = asyncio.create_task(listen_for_client())

        while True:
            frame = video_capture.read()
            if frame is None:
                await asyncio.sleep(0.05)
                continue

            # 1. Gửi video frame
            jpeg_bytes = frame_processor.encode_frame_jpeg(frame, quality=75)
            await websocket.send_bytes(jpeg_bytes)

            # 2. Xử lý AI song song
            if ai_task is None or ai_task.done():
                ai_task = asyncio.create_task(process_and_send_result(frame))

            await asyncio.sleep(1.0 / 30)

    except WebSocketDisconnect:
        logger.info("WebSocket client đã ngắt kết nối")
    except Exception as e:
        # Bỏ qua dòng log WebSocket disconnect quá dài
        if "close" not in str(e).lower() and "completed" not in str(e).lower():
            logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass
    finally:
        if 'listen_task' in locals() and not listen_task.done():
            listen_task.cancel()
        if 'ai_task' in locals() and ai_task is not None and not ai_task.done():
            ai_task.cancel()
