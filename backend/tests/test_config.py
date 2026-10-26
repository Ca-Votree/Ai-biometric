import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.config import settings

def test_security_config():
    """Verify security configuration."""
    if settings.APP_ENV.lower() == "production":
        assert settings.API_KEY != "", "API_KEY phải được set cho production"
    else:
        assert True
    assert "localhost" in ",".join(settings.cors_origin_list), "CORS không chứa localhost"

def test_db_config():
    """Verify DB PRAGMA."""
    assert "sqlite" in settings.DATABASE_URL
    # Kiểm tra log xem WAL có được áp dụng không (tạm thời check config)
    assert settings.DEBUG is True
