@echo off
cd /d "%~dp0"
echo 🚀 Khoi dong AI Biometrics Attendance System...

:: Kiem tra va kich hoat venv
if exist "backend\venv\Scripts\activate.bat" (
    echo 📦 Dang kich hoat virtual environment...
    call backend\venv\Scripts\activate.bat
)

:: Khoi dong Backend
echo 📦 Dang khoi dong Backend (FastAPI)...
start "Backend (Uvicorn)" cmd /c "cd backend && ..\backend\venv\Scripts\python.exe run.py"

:: Khoi dong Frontend (hoặc dùng FastAPI static serve)
echo 🌐 Dang mo giao diện hệ thống...
timeout /t 2 >nul
start http://localhost:8000

echo.
echo ✅ He thong da khoi dong thanh cong!
echo 🔗 Giao dien & API: http://localhost:8000
echo (Cua so nay se tu dong dong sau 3 giay...)
timeout /t 3 >nul
