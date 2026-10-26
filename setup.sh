#!/usr/bin/env bash
# ==============================================================================
# Script Setup Môi trường & Khởi động Dự án AI Biometrics Attendance System
# Chạy trên Git-Bash (Windows) hoặc Linux/macOS
# ==============================================================================

set -e

echo "=== [1/5] Kiểm tra Python và môi trường ===
python --version

echo "=== [2/5] Tạo và kích hoạt Virtual Environment ==="
if [ ! -d "backend/venv" ]; then
    python -m venv backend/venv
    echo "Đã tạo virtual environment tại backend/venv"
fi

# Kích hoạt venv (Git-Bash / POSIX)
source backend/venv/Scripts/activate || source backend/venv/bin/activate

echo "=== [3/5] Nâng cấp pip và cài đặt dependencies ==="
python -m pip install --upgrade pip
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt
else
    echo "Cảnh báo: Không tìm thấy backend/requirements.txt"
fi

echo "=== [4/5] Tạo các thư mục dữ liệu và models cần thiết ==="
mkdir -p backend/data/faces
mkdir -p backend/data/faiss_index
mkdir -p backend/data/logs
mkdir -p backend/models

echo "=== [5/5] Hoàn tất setup! ==="
echo "Để chạy hệ thống:"
echo "  1. Chạy Backend: python backend/run.py (hoặc uvicorn app.main:app --reload)"
echo "  2. Mở trình duyệt truy cập: http://localhost:8000"
