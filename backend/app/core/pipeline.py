
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from app.config import settings
from app.core.detector import face_detector
from app.core.aligner import face_aligner
from app.core.extractor import feature_extractor
from app.core.matcher import face_matcher


@dataclass
class RecognitionResult:
    """Kết quả nhận diện cho một khuôn mặt."""
    bbox: list[int]                   # [x1, y1, x2, y2]
    landmarks: Optional[list] = None  # 5 landmarks
    det_score: float = 0.0            # Detection confidence
    student_id: Optional[str] = None  # Mã sinh viên (nếu match)
    similarity: float = 0.0           # Cosine similarity
    identified: bool = False          # Đã nhận diện được hay không
    status: str = "unknown"           # "matched" | "unknown"
    embedding: Optional[np.ndarray] = None  # Embedding vector


@dataclass 
class FrameResult:
    """Kết quả xử lý cho một frame."""
    frame_id: int = 0
    timestamp: float = 0.0
    faces: list[RecognitionResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    annotated_frame: Optional[np.ndarray] = None  # Frame đã vẽ annotations

    @property
    def total_faces(self) -> int:
        return len(self.faces)

    @property
    def identified_count(self) -> int:
        return sum(1 for f in self.faces if f.identified)

    @property
    def unknown_count(self) -> int:
        return sum(1 for f in self.faces if not f.identified)


class RecognitionPipeline:


    def __init__(self):
        self._frame_counter = 0
        self._initialized = False
        self._last_faces = []

    def initialize(self):
        if self._initialized:
            return

        logger.info("🚀 Đang khởi tạo Recognition Pipeline...")
        
        # Detector (YOLO ONNX Runtime)
        face_detector.initialize()
        
        # Extractor (ArcFace)
        feature_extractor.initialize()
        
        # Matcher (FAISS)
        face_matcher.initialize()
        
        self._initialized = True
        logger.info("✅ Recognition Pipeline đã sẵn sàng!")

    def process_frame(self, frame: np.ndarray, annotate: bool = True) -> FrameResult:

        if not self._initialized:
            self.initialize()

        start_time = time.time()
        self._frame_counter += 1

        result = FrameResult(
            frame_id=self._frame_counter,
            timestamp=time.time(),
        )

        # Skip frame logic to reduce inference overhead
        if self._frame_counter % settings.FRAME_SKIP != 0 and self._last_faces:
            result.faces = self._last_faces
            result.processing_time_ms = (time.time() - start_time) * 1000
            if annotate:
                result.annotated_frame = self._annotate_frame(frame.copy(), result.faces)
            return result

        # === Detection ===
        faces = face_detector.detect(frame)

        if not faces:
            self._last_faces = []
            result.processing_time_ms = (time.time() - start_time) * 1000
            if annotate:
                result.annotated_frame = frame.copy()
            return result

        # === Crop, Extract & Match ===
        for face in faces:
            rec_result = RecognitionResult(
                bbox=face.bbox.astype(int).tolist(),
                landmarks=face.kps.tolist() if face.kps is not None else None,
                det_score=float(face.det_score),
            )

            # Cắt và căn chỉnh khuôn mặt
            aligned_face = face_aligner.align_from_face(frame, face)
            
            # Trích xuất embedding
            embedding = None
            if aligned_face is not None:
                embedding = feature_extractor.extract_from_aligned(aligned_face)
            
            if embedding is not None:
                rec_result.embedding = embedding
                
                # === Matching với FAISS ===
                match_result = face_matcher.identify(embedding)
                rec_result.identified = match_result["identified"]
                rec_result.student_id = match_result["student_id"]
                rec_result.similarity = match_result["similarity"]
                rec_result.status = match_result["status"]

            result.faces.append(rec_result)

        self._last_faces = result.faces

        # Annotate frame
        if annotate:
            result.annotated_frame = self._annotate_frame(frame.copy(), result.faces)

        result.processing_time_ms = (time.time() - start_time) * 1000
        
        logger.debug(
            f"Frame #{self._frame_counter}: "
            f"{result.total_faces} faces, "
            f"{result.identified_count} identified, "
            f"{result.processing_time_ms:.1f}ms"
        )

        return result

    def _annotate_frame(
        self, frame: np.ndarray, faces: list[RecognitionResult]
    ) -> np.ndarray:
        """
        Vẽ bounding box, tên, và thông tin lên frame.
        """
        for face in faces:
            x1, y1, x2, y2 = face.bbox
            
            if face.identified:
                # Đã nhận diện → xanh lá
                color = (0, 255, 0)
                label = f"{face.student_id} ({face.similarity:.2f})"
            else:
                # Không nhận diện → đỏ
                color = (0, 0, 255)
                label = f"Unknown ({face.similarity:.2f})"

            # Vẽ bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Vẽ label background
            label_size, baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            y_label = max(y1 - 10, label_size[1] + 10)
            cv2.rectangle(
                frame, 
                (x1, y_label - label_size[1] - 5),
                (x1 + label_size[0] + 5, y_label + 5),
                color, -1
            )
            
            # Vẽ text
            cv2.putText(
                frame, label,
                (x1 + 2, y_label),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 2,
            )

            # Vẽ landmarks
            if face.landmarks:
                for lm in face.landmarks:
                    cv2.circle(frame, (int(lm[0]), int(lm[1])), 2, (0, 255, 255), -1)

        # Thông tin tổng quan
        info_text = (
            f"Faces: {len(faces)} | "
            f"Identified: {sum(1 for f in faces if f.identified)}"
        )
        cv2.putText(
            frame, info_text,
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
            (0, 255, 255), 2,
        )

        return frame

    def register_face(
        self, student_id: str, face_images: list[np.ndarray]
    ) -> dict:
        """
        Đăng ký khuôn mặt sinh viên mới vào database.
        """
        if not self._initialized:
            self.initialize()

        embeddings = []
        
        for img in face_images:
            faces = face_detector.detect(img)
            
            if not faces:
                logger.warning(f"Không phát hiện khuôn mặt trong ảnh cho {student_id}")
                continue
            
            # Lấy khuôn mặt lớn nhất (giả định là khuôn mặt chính)
            main_face = max(faces, key=lambda f: 
                (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
            )
            
            aligned_face = face_aligner.align_from_face(img, main_face)
            embedding = None
            if aligned_face is not None:
                embedding = feature_extractor.extract_from_aligned(aligned_face)
                
            if embedding is not None:
                embeddings.append(embedding)

        if not embeddings:
            return {
                "success": False,
                "student_id": student_id,
                "message": "Không thể trích xuất embedding từ ảnh nào",
            }

        # Lấy embedding trung bình (centroid) - robust hơn dùng 1 ảnh
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)  # Re-normalize
        
        # Thêm vào FAISS
        face_matcher.add_embedding(student_id, avg_embedding)
        face_matcher.save_index()

        return {
            "success": True,
            "student_id": student_id,
            "num_images_processed": len(embeddings),
            "message": f"Đã đăng ký {student_id} với {len(embeddings)} ảnh",
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def release(self):
        """Giải phóng tài nguyên."""
        face_detector.release()
        self._initialized = False
        logger.info("Pipeline đã được giải phóng")


# Singleton instance
recognition_pipeline = RecognitionPipeline()
