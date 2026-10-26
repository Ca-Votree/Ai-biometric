
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

try:
    import faiss
except ImportError:
    logger.warning("FAISS chưa được cài đặt. Chạy: pip install faiss-cpu")
    faiss = None

from app.config import settings


class FaceMatcher:


    def __init__(self):
        self._index: Optional[object] = None
        self._id_map: dict = {}           # faiss_idx → student_id
        self._reverse_map: dict = {}      # student_id → faiss_idx
        self._embedding_dim: int = 512
        self._initialized: bool = False

    def initialize(self):
        """Khởi tạo hoặc load FAISS index."""
        if self._initialized:
            return

        if faiss is None:
            raise ImportError("FAISS chưa được cài đặt. Chạy: pip install faiss-cpu")

        # Thử load index có sẵn
        if os.path.exists(settings.FAISS_INDEX_PATH):
            self._load_index()
        else:
            self._create_new_index()
        
        self._initialized = True
        logger.info(
            f"✅ Face matcher sẵn sàng | "
            f"Index size: {self._index.ntotal} vectors"
        )

    def _create_new_index(self):
        """Tạo FAISS index mới."""
        # IndexFlatIP: Inner Product (= Cosine Similarity với normalized vectors)
        self._index = faiss.IndexFlatIP(self._embedding_dim)
        self._id_map = {}
        self._reverse_map = {}
        
        logger.info("Đã tạo FAISS index mới")

    def _load_index(self):
        """Load FAISS index và ID map từ disk."""
        try:
            self._index = faiss.read_index(settings.FAISS_INDEX_PATH)
            
            with open(settings.FAISS_ID_MAP_PATH, "r", encoding="utf-8") as f:
                raw_map = json.load(f)
                self._id_map = {int(k): v for k, v in raw_map.items()}
                self._reverse_map = {v: int(k) for k, v in raw_map.items()}
            
            logger.info(f"Đã load FAISS index: {self._index.ntotal} vectors")
        except Exception as e:
            logger.error(f"Lỗi khi load FAISS index: {e}")
            self._create_new_index()

    def save_index(self):
        """Lưu FAISS index và ID map xuống disk (convert từ GPU sang CPU nếu cần)."""
        if self._index is None:
            return

        # Tạo thư mục nếu chưa có
        index_dir = Path(settings.FAISS_INDEX_PATH).parent
        index_dir.mkdir(parents=True, exist_ok=True)

        # Nếu index đang ở GPU, convert sang CPU trước khi lưu
        index_to_save = self._index
        
        # Lưu index
        faiss.write_index(index_to_save, settings.FAISS_INDEX_PATH)
        
        # Lưu ID map
        with open(settings.FAISS_ID_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(self._id_map, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Đã lưu FAISS index: {self._index.ntotal} vectors")

    def add_embedding(self, student_id: str, embedding: np.ndarray):
        """
        Thêm embedding của một sinh viên vào index.
        
        Args:
            student_id: Mã sinh viên
            embedding: L2 normalized embedding vector (512,)
        """
        if not self._initialized:
            self.initialize()

        # Reshape cho FAISS (cần 2D array)
        embedding_2d = embedding.reshape(1, -1).astype(np.float32)
        
        # Lấy index tiếp theo
        faiss_idx = self._index.ntotal
        
        # Thêm vào FAISS
        self._index.add(embedding_2d)
        
        # Cập nhật ID map
        self._id_map[faiss_idx] = student_id
        self._reverse_map[student_id] = faiss_idx
        
        logger.debug(f"Đã thêm embedding cho sinh viên {student_id} (idx={faiss_idx})")

    def add_embeddings_batch(self, student_ids: list[str], embeddings: np.ndarray):
        """
        Thêm nhiều embeddings cùng lúc (batch).
        
        Args:
            student_ids: List mã sinh viên
            embeddings: np.array shape (N, 512)
        """
        if not self._initialized:
            self.initialize()

        start_idx = self._index.ntotal
        embeddings_2d = embeddings.astype(np.float32)
        
        self._index.add(embeddings_2d)
        
        for i, sid in enumerate(student_ids):
            faiss_idx = start_idx + i
            self._id_map[faiss_idx] = sid
            self._reverse_map[sid] = faiss_idx
        
        logger.info(f"Đã thêm batch {len(student_ids)} embeddings")

    def search(
        self, 
        embedding: np.ndarray, 
        top_k: int = 1,
        threshold: float = None
    ) -> list[dict]:
        """
        Tìm kiếm khuôn mặt tương tự nhất trong database.
        
        Args:
            embedding: Query embedding vector (512,)
            top_k: Số kết quả trả về
            threshold: Ngưỡng similarity (None = dùng config)
            
        Returns:
            List[dict] với mỗi dict chứa:
                - student_id: str
                - similarity: float
                - matched: bool (vượt ngưỡng hay không)
        """
        if not self._initialized:
            self.initialize()

        if self._index.ntotal == 0:
            logger.warning("FAISS index rỗng - chưa có sinh viên nào được đăng ký")
            return []

        if threshold is None:
            threshold = settings.FACE_RECOGNITION_THRESHOLD

        # Query FAISS
        embedding_2d = embedding.reshape(1, -1).astype(np.float32)
        similarities, indices = self._index.search(embedding_2d, min(top_k, self._index.ntotal))
        
        results = []
        for sim, idx in zip(similarities[0], indices[0]):
            if idx == -1:
                continue
            
            student_id = self._id_map.get(int(idx), "unknown")
            result = {
                "student_id": student_id,
                "similarity": float(sim),
                "matched": float(sim) >= threshold,
            }
            results.append(result)
        
        return results

    def identify(self, embedding: np.ndarray, threshold: float = None) -> dict:
        """
        Nhận diện danh tính từ embedding (trả về kết quả tốt nhất).
        
        Args:
            embedding: Query embedding vector (512,)
            threshold: Ngưỡng similarity
            
        Returns:
            dict:
                - identified: bool
                - student_id: str | None
                - similarity: float
                - status: "matched" | "unknown"
        """
        results = self.search(embedding, top_k=1, threshold=threshold)
        
        if not results or not results[0]["matched"]:
            return {
                "identified": False,
                "student_id": None,
                "similarity": results[0]["similarity"] if results else 0.0,
                "status": "unknown",
            }
        
        best = results[0]
        return {
            "identified": True,
            "student_id": best["student_id"],
            "similarity": best["similarity"],
            "status": "matched",
        }

    def remove_student(self, student_id: str):
        """
        Xóa sinh viên khỏi FAISS index bằng cách rebuild lại
        (IndexFlatIP không hỗ trợ remove trực tiếp).
        """
        if student_id not in self._reverse_map:
            logger.warning(f"Sinh viên {student_id} không có trong index")
            return

        old_idx = self._reverse_map[student_id]

        # Lấy tất cả embeddings hiện có trừ student cần xóa
        remaining = {}
        for faiss_idx, sid in self._id_map.items():
            if sid == student_id:
                continue
            vec = self._index.reconstruct(int(faiss_idx))
            remaining[sid] = vec

        # Rebuild
        self._create_new_index()
        if remaining:
            sids = list(remaining.keys())
            embs = np.array(list(remaining.values()), dtype=np.float32)
            self.add_embeddings_batch(sids, embs)

        self.save_index()
        logger.info(f"Đã xóa sinh viên {student_id} khỏi FAISS index (rebuild {self._index.ntotal} vectors)")

    def rebuild_index(self, student_embeddings: dict[str, np.ndarray]):
        """
        Rebuild toàn bộ FAISS index từ danh sách embeddings mới.
        
        Args:
            student_embeddings: dict mapping student_id → embedding vector
        """
        if not self._initialized:
            self.initialize()

        self._create_new_index()
        
        if student_embeddings:
            student_ids = list(student_embeddings.keys())
            embeddings = np.array(
                [student_embeddings[sid] for sid in student_ids], 
                dtype=np.float32
            )
            self.add_embeddings_batch(student_ids, embeddings)
        
        self.save_index()
        logger.info(f"Đã rebuild FAISS index: {self._index.ntotal} vectors")

    @property
    def total_vectors(self) -> int:
        """Số lượng vectors hiện có trong index."""
        if self._index is None:
            return 0
        return self._index.ntotal

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Singleton instance
face_matcher = FaceMatcher()
