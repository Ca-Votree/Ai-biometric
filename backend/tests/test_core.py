import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np
from app.core.matcher import FaceMatcher
from app.config import settings

def test_settings():
    assert settings.APP_NAME is not None
    assert settings.FACE_RECOGNITION_THRESHOLD > 0

def test_face_matcher_basic():
    matcher = FaceMatcher()
    matcher._create_new_index()
    assert matcher.total_vectors == 0

    # Add dummy embedding (512,) L2 normalized
    dummy_emb = np.random.randn(512).astype(np.float32)
    dummy_emb /= np.linalg.norm(dummy_emb)

    matcher.add_embedding("SV001", dummy_emb)
    assert matcher.total_vectors == 1

    # Search
    results = matcher.search(dummy_emb, top_k=1)
    assert len(results) == 1
    assert results[0]["student_id"] == "SV001"
    assert results[0]["matched"] == True

    # Remove
    matcher.remove_student("SV001")
    assert matcher.total_vectors == 0
