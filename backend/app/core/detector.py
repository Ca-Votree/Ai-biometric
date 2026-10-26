import os

import cv2
import numpy as np
from loguru import logger

from app.config import settings

try:
    import onnxruntime as ort
except ImportError:
    logger.warning("onnxruntime chưa được cài đặt. Chạy: pip install onnxruntime")
    ort = None


class Face:
    def __init__(self, bbox, det_score, kps=None):
        self.bbox = np.array(bbox, dtype=np.float32)
        self.det_score = float(det_score)
        self.kps = np.array(kps, dtype=np.float32) if kps is not None else None
        self.embedding = None


class FaceDetector:
    """YOLO face detector chạy trực tiếp bằng ONNX Runtime."""

    def __init__(self):
        self._session = None
        self._input_name = None
        self._input_size = (640, 640)
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return
        if ort is None:
            raise ImportError("Chạy: pip install onnxruntime")

        model_path = os.path.join(settings.MODELS_DIR, settings.DETECTION_MODEL)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Không tìm thấy face detector: {model_path}")

        providers = ["CPUExecutionProvider"]
        available = ort.get_available_providers()
        if settings.USE_GPU and "CUDAExecutionProvider" in available:
            providers.insert(0, "CUDAExecutionProvider")

        self._session = ort.InferenceSession(model_path, providers=providers)
        model_input = self._session.get_inputs()[0]
        self._input_name = model_input.name
        shape = model_input.shape
        if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
            self._input_size = (shape[3], shape[2])
        self._initialized = True
        logger.info(
            f"Face detector ONNX đã sẵn sàng: {os.path.basename(model_path)} "
            f"({self._session.get_providers()[0]})"
        )

    def detect(self, frame: np.ndarray) -> list:
        if not self._initialized:
            self.initialize()

        original_h, original_w = frame.shape[:2]
        input_w, input_h = self._input_size
        image = cv2.resize(frame, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = image.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        output = self._session.run(None, {self._input_name: image})[0]
        predictions = np.squeeze(output)
        if predictions.ndim == 1:
            predictions = predictions[:, None]
        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T

        boxes, scores = [], []
        scale_x, scale_y = original_w / input_w, original_h / input_h
        for prediction in predictions:
            if len(prediction) < 5:
                continue
            cx, cy, width, height, score = prediction[:5]
            score = float(score)
            if score < settings.FACE_DETECTION_THRESHOLD:
                continue
            x1 = max(0.0, (cx - width / 2) * scale_x)
            y1 = max(0.0, (cy - height / 2) * scale_y)
            x2 = min(float(original_w), (cx + width / 2) * scale_x)
            y2 = min(float(original_h), (cy + height / 2) * scale_y)
            if x2 > x1 and y2 > y1:
                boxes.append([x1, y1, x2 - x1, y2 - y1])
                scores.append(score)

        keep = cv2.dnn.NMSBoxes(
            boxes, scores, settings.FACE_DETECTION_THRESHOLD, 0.45
        )
        faces = [
            Face(
                bbox=[boxes[int(i)][0], boxes[int(i)][1],
                      boxes[int(i)][0] + boxes[int(i)][2],
                      boxes[int(i)][1] + boxes[int(i)][3]],
                det_score=scores[int(i)],
            )
            for i in np.array(keep).reshape(-1)
        ]
        faces.sort(key=lambda face: face.det_score, reverse=True)
        logger.debug(f"ONNX YOLO phát hiện {len(faces)} khuôn mặt trong frame")
        return faces[:settings.MAX_FACES_PER_FRAME]

    def detect_batch(self, frames: list[np.ndarray]) -> list[list]:
        return [self.detect(frame) for frame in frames]

    @staticmethod
    def extract_face_data(face) -> dict:
        data = {
            "bbox": face.bbox.astype(int).tolist(),
            "landmarks": face.kps.tolist() if face.kps is not None else None,
            "score": float(face.det_score),
        }
        if face.embedding is not None:
            data["embedding"] = face.embedding.tolist()
        return data

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def release(self):
        self._session = None
        self._initialized = False
        logger.info("ONNX face detector đã được giải phóng")


face_detector = FaceDetector()
