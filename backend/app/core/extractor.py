
import numpy as np
from loguru import logger

from app.config import settings


class FeatureExtractor:


    def __init__(self):
        self._model = None
        self._initialized = False

    def initialize(self, recognition_model=None):
        """
        Khởi tạo model trích xuất đặc trưng.
        
        Args:
            recognition_model: Model recognition từ InsightFace (nếu đã có).
                             Nếu None, sẽ tải riêng.
        """
        if self._initialized:
            return

        if recognition_model is not None:
            self._model = recognition_model
            self._initialized = True
            logger.info("✅ Feature extractor đã được khởi tạo (shared model)")
            return

        # Tải model riêng nếu cần
        try:
            from insightface.model_zoo import get_model
            
            model_path = f"{settings.MODELS_DIR}/buffalo_l/w600k_r50.onnx"
            self._model = get_model(model_path)
            self._model.prepare(ctx_id=-1)  # -1 for CPU
            self._initialized = True
            logger.info("✅ Feature extractor đã sẵn sàng (standalone model - CPU)")
        except Exception as e:
            logger.error(f"Không thể tải model recognition: {e}")
            raise

    def extract(self, face) -> np.ndarray:
        """
        Trích xuất embedding từ một InsightFace Face object.
        
        InsightFace đã tự động tính embedding khi gọi app.get().
        Method này chỉ đảm bảo embedding hợp lệ và normalized.
        
        Args:
            face: InsightFace Face object (đã có embedding sau detect)
            
        Returns:
            np.ndarray shape (512,) - L2 normalized embedding vector
        """
        if hasattr(face, "embedding") and face.embedding is not None:
            embedding = face.embedding
        else:
            logger.warning("Face object không có embedding sẵn")
            return None

        # L2 normalize
        embedding = self._normalize(embedding)
        
        return embedding

    def extract_from_aligned(self, aligned_face: np.ndarray) -> np.ndarray:
        """
        Trích xuất embedding từ ảnh khuôn mặt đã căn chỉnh (112x112).
        Dùng khi cần tính embedding thủ công (ví dụ: đăng ký sinh viên).
        
        Args:
            aligned_face: BGR image 112x112 (numpy array)
            
        Returns:
            np.ndarray shape (512,) - L2 normalized embedding
        """
        if not self._initialized:
            self.initialize()

        if self._model is None:
            raise RuntimeError("Feature extractor model chưa được khởi tạo")

        embedding = self._model.get_feat(aligned_face)
        embedding = self._normalize(embedding.flatten())
        
        return embedding

    def extract_batch(self, faces: list) -> list[np.ndarray]:
        """
        Trích xuất embeddings cho nhiều khuôn mặt.
        
        Args:
            faces: List InsightFace Face objects
            
        Returns:
            List[np.ndarray] - danh sách embedding vectors
        """
        embeddings = []
        for face in faces:
            embedding = self.extract(face)
            if embedding is not None:
                embeddings.append(embedding)
            else:
                embeddings.append(None)
        
        return embeddings

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        """
        L2 normalize embedding vector.
        Sau khi normalize, cosine similarity = inner product.
        
        Args:
            embedding: Raw embedding vector
            
        Returns:
            L2 normalized embedding
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    @staticmethod
    def compute_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Tính cosine similarity giữa 2 embedding vectors.
        
        Args:
            emb1, emb2: L2 normalized embedding vectors (512,)
            
        Returns:
            float: Cosine similarity [-1, 1]
        """
        return float(np.dot(emb1, emb2))

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Singleton instance
feature_extractor = FeatureExtractor()
