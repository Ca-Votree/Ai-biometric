"""
Database Models
SQLAlchemy models cho hệ thống điểm danh.
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    Text, ForeignKey, LargeBinary, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Base class cho tất cả models."""
    pass


class AuthUser(Base):
    """Tài khoản đăng nhập quản trị viên và giảng viên."""
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Student(Base):
    """Bảng thông tin sinh viên."""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False, index=True)  # Mã SV
    full_name = Column(String(100), nullable=False)
    class_name = Column(String(50), nullable=True)   # Lớp
    department = Column(String(100), nullable=True)   # Khoa
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Trạng thái đăng ký khuôn mặt
    face_registered = Column(Boolean, default=False)
    face_registered_at = Column(DateTime, nullable=True)
    num_face_images = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    face_images = relationship("FaceImage", back_populates="student")

    def __repr__(self):
        return f"<Student(id={self.student_id}, name={self.full_name})>"


class FaceImage(Base):
    """Bảng lưu ảnh khuôn mặt đã đăng ký."""
    __tablename__ = "face_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("students.student_id"), nullable=False)
    image_path = Column(String(500), nullable=False)    # Đường dẫn ảnh gốc
    embedding_blob = Column(LargeBinary, nullable=True) # Embedding vector (serialized)
    quality_score = Column(Float, nullable=True)         # Chất lượng ảnh
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="face_images")


class Session(Base):
    """Bảng phiên điểm danh (buổi học / sự kiện)."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(200), nullable=False)  # Tên buổi
    course_name = Column(String(200), nullable=True)    # Tên môn học
    class_name = Column(String(50), nullable=True)      # Lớp học
    room = Column(String(50), nullable=True)            # Phòng học
    instructor = Column(String(100), nullable=True)     # Giảng viên
    
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="open")  # open / review / locked
    
    # Thống kê
    total_recognized = Column(Integer, default=0)
    total_unknown = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    attendance_records = relationship("AttendanceRecord", back_populates="session")

    def __repr__(self):
        return f"<Session(name={self.session_name}, active={self.is_active})>"


class AttendanceRecord(Base):
    """Bảng ghi nhận điểm danh."""
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    student_id = Column(String(20), ForeignKey("students.student_id"), nullable=False)
    
    # Thông tin điểm danh
    check_in_time = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    similarity_score = Column(Float, nullable=False)    # Độ tương đồng khi nhận diện
    confidence = Column(Float, nullable=True)           # Detection confidence
    
    # Metadata
    method = Column(String(20), default="auto")         # auto / manual
    status = Column(String(20), default="present")      # present / late / absent
    snapshot_path = Column(String(500), nullable=True)   # Ảnh chụp lúc điểm danh
    note = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    session = relationship("Session", back_populates="attendance_records")

    def __repr__(self):
        return f"<Attendance(session={self.session_id}, student={self.student_id}, time={self.check_in_time})>"


class AlertLog(Base):
    """Bảng log cảnh báo (khuôn mặt lạ, lỗi hệ thống, v.v.)."""
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)     # unknown_face / system_error / etc.
    message = Column(Text, nullable=True)
    snapshot_path = Column(String(500), nullable=True)   # Ảnh chụp
    similarity_score = Column(Float, nullable=True)      # Score cao nhất (nếu là unknown)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ClassConfig(Base):
    """Bảng cấu hình lớp học: gán camera và giảng viên do Admin quản lý."""
    __tablename__ = "class_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(50), unique=True, nullable=False, index=True)
    camera_source = Column(String(200), default="0")     # Nguồn camera cho lớp này (0, RTSP URL, file, v.v.)
    instructor = Column(String(100), nullable=True)      # Giảng viên phụ trách mặc định
    room = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<ClassConfig(class={self.class_name}, camera={self.camera_source}, teacher={self.instructor})>"


class Schedule(Base):
    """Lịch học dùng để tạo phiên điểm danh."""
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(50), nullable=False, index=True)
    course_name = Column(String(200), nullable=False)
    instructor = Column(String(100), nullable=True)
    room = Column(String(50), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    repeat_weekly = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    """Nhật ký thao tác quản trị và điểm danh."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(100), nullable=True)
    actor = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SystemSetting(Base):
    """Persistent administrator-managed runtime configuration."""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
