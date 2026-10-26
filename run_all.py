import sys
import subprocess
import time
from pathlib import Path

def run_all():
    backend_dir = Path(__file__).resolve().parent / "backend"

    print("Starting AI Biometrics Attendance System...")
    backend_process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=backend_dir
    )

    print("Frontend and API: http://localhost:8000")
    print("Press Ctrl+C to stop.\n")
    try:
        while backend_process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping the system...")
    finally:
        if backend_process.poll() is None:
            backend_process.terminate()
            backend_process.wait()

if __name__ == "__main__":
    run_all()
