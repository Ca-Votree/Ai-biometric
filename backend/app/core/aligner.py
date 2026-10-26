
import cv2
import numpy as np
from loguru import logger


# Template landmarks chuẩn cho khuôn mặt 112x112 (ArcFace standard)
# Thứ tự: mắt trái, mắt phải, mũi, khóe miệng trái, khóe miệng phải
ARCFACE_REFERENCE_LANDMARKS = np.array([
    [38.2946, 51.6963],   # Mắt trái
    [73.5318, 51.5014],   # Mắt phải
    [56.0252, 71.7366],   # Mũi
    [41.5493, 92.3655],   # Khóe miệng trái
    [70.7299, 92.2041],   # Khóe miệng phải
], dtype=np.float32)


class FaceAligner:


    def __init__(self, output_size: tuple = (112, 112)):

        self.output_size = output_size
        self.reference_landmarks = ARCFACE_REFERENCE_LANDMARKS.copy()

    def align(self, frame: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """
        Căn chỉnh khuôn mặt dựa trên 5 landmarks.
        """
        if landmarks is None or len(landmarks) != 5:
            logger.warning("Landmarks không hợp lệ, trả về crop thay vì align")
            return None

        # Tính Similarity Transformation Matrix
        # (rotation, scale, translation - giữ nguyên tỷ lệ)
        M = self._estimate_transform(landmarks.astype(np.float32))
        
        # Apply affine warp
        aligned_face = cv2.warpAffine(
            frame,
            M,
            self.output_size,
            borderValue=(0, 0, 0)
        )
        
        return aligned_face

    def align_from_face(self, frame: np.ndarray, face) -> np.ndarray:
        """
        Căn chỉnh khuôn mặt trực tiếp từ InsightFace Face object.
        """
        if not hasattr(face, "kps") or face.kps is None:
            logger.warning("Face object không có landmarks")
            return self._crop_face(frame, face.bbox)
        
        return self.align(frame, face.kps)

    def _estimate_transform(self, src_landmarks: np.ndarray) -> np.ndarray:
        """
        Ước lượng Similarity Transformation Matrix (2x3).
        Sử dụng phương pháp Umeyama algorithm.
        """
        dst = self.reference_landmarks
        src = src_landmarks

        # Estimate partial affine (similarity transform: rotation + scale + translation)
        tform = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
        
        if tform[0] is not None:
            return tform[0]
        
        # Fallback: dùng full affine nếu partial thất bại
        tform_full = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
        if tform_full[0] is not None:
            return tform_full[0]
        
        # Final fallback: chỉ dùng 3 điểm (2 mắt + mũi)
        M = cv2.getAffineTransform(src[:3], dst[:3])
        return M

    def _crop_face(self, frame: np.ndarray, bbox: np.ndarray) -> np.ndarray:
        """
        Fallback: Crop khuôn mặt theo bounding box nếu không có landmarks.
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Đảm bảo trong giới hạn ảnh
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        face_crop = frame[y1:y2, x1:x2]
        
        if face_crop.size == 0:
            return np.zeros((*self.output_size, 3), dtype=np.uint8)
        
        return cv2.resize(face_crop, self.output_size)

    def batch_align(self, frame: np.ndarray, faces: list) -> list[np.ndarray]:
        """
        Căn chỉnh nhiều khuôn mặt trong cùng một frame.
        """
        aligned_faces = []
        for face in faces:
            aligned = self.align_from_face(frame, face)
            if aligned is not None:
                aligned_faces.append(aligned)
        
        return aligned_faces


# Singleton instance
face_aligner = FaceAligner()
