@echo off
chcp 65001 > nul
echo ========================================================
echo Setup Moi truong Du an AI Biometrics Attendance System
echo ========================================================

python --version
if errorlevel 1 (
    echo Khong tim thay Python! Vui long cai dat Python 3.10+
    pause
    exit /b 1
)

if not exist "backend\venv" (
    echo [1/4] Dang tao Virtual Environment...
    python -m venv backend\venv
)

echo [2/4] Dang kich hoạt va cai dat dependencies...
call backend\venv\Scripts\activate
python -m pip install --upgrade pip
if exist "backend\requirements.txt" (
    pip install -r backend\requirements.txt
)

echo [3/4] Tao cau truc thu muc du lieu...
if not exist "backend\data\faces" mkdir backend\data\faces
if not exist "backend\data\faiss_index" mkdir backend\data\faiss_index
if not exist "backend\models" mkdir backend\models

echo [4/4] Hoan tat setup moi truong!
echo De khoi chay backend:
echo   call backend\venv\Scripts\activate
echo   cd backend
echo   python run.py
echo ========================================================
pause
