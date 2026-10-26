"""
Video Capture Module
Quản lý kết nối camera và trích xuất frame.
"""
import time
import threading
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from app.config import settings


class VideoCapture:
    """
    Quản lý nguồn video (webcam, RTSP, file video).
    """

    def __init__(self, source=None):
        """
        Args:
            source: Nguồn video (int cho webcam, string cho RTSP/file).
                    None = lấy từ config.
        """
        self._source = source if source is not None else settings.camera_source_parsed
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._fps = 0.0

    def start(self, source=None) -> bool:
        """
        Bắt đầu capture video.
        
        Returns:
            True nếu mở camera thành công
        """
        if self._running:
            return True
        if source is not None:
            try:
                self._source = int(source)
            except (TypeError, ValueError):
                self._source = source
        logger.info(f"Đang mở camera: {self._source}")

        self._cap = cv2.VideoCapture(self._source)
        
        if not self._cap.isOpened():
            logger.error(f"Không thể mở camera: {self._source}")
            return False

        # Thiết lập resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, settings.FPS)

        # Bắt đầu thread đọc frame
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        
        logger.info(
            f"✅ Camera đã mở: "
            f"{int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ "
            f"{self._cap.get(cv2.CAP_PROP_FPS):.0f}fps"
        )
        return True

    def _read_loop(self):
        """Thread loop đọc frame liên tục."""
        prev_time = time.time()
        
        while self._running:
            ret, frame = self._cap.read()
            
            if not ret:
                logger.warning("Không đọc được frame từ camera")
                time.sleep(0.1)
                continue

            with self._lock:
                self._frame = frame
                self._frame_count += 1

            # Tính FPS
            curr_time = time.time()
            self._fps = 1.0 / max(curr_time - prev_time, 1e-6)
            prev_time = curr_time

    def read(self) -> Optional[np.ndarray]:
        """
        Đọc frame mới nhất (non-blocking).
        
        Returns:
            BGR image hoặc None nếu không có frame
        """
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def read_resized(self, width: int = 640) -> Optional[np.ndarray]:
        """
        Đọc frame đã resize.
        
        Args:
            width: Chiều rộng mong muốn
            
        Returns:
            Resized BGR image
        """
        frame = self.read()
        if frame is None:
            return None
        
        h, w = frame.shape[:2]
        ratio = width / w
        new_h = int(h * ratio)
        
        return cv2.resize(frame, (width, new_h))

    def stop(self):
        """Dừng capture và tắt camera."""
        self._running = False
        
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        
        self._frame = None
        logger.info("Camera đã được tắt ")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def source(self):
        return self._source

    def __del__(self):
        self.stop()


class FrameProcessor:
    """Tiền xử lý frame trước khi đưa vào pipeline AI."""

    @staticmethod
    def preprocess(frame: np.ndarray) -> np.ndarray:
        """
        Tiền xử lý frame cơ bản.
        """
        # Histogram equalization trên kênh L (LAB color space)
        # để cải thiện chất lượng ảnh trong điều kiện ánh sáng kém
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return result

    @staticmethod
    def encode_frame_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
        """
        Encode frame thành JPEG bytes (cho streaming).
        
        Args:
            frame: BGR image
            quality: JPEG quality (0-100)
            
        Returns:
            JPEG bytes
        """
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode(".jpg", frame, encode_param)
        return buffer.tobytes()


# Singleton instances
video_capture = VideoCapture()
frame_processor = FrameProcessor()
