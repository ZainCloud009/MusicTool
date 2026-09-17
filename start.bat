@echo off
title Social Video Downloader
cd /d "%~dp0"

echo ===================================================
echo           SOCIAL VIDEO DOWNLOADER
echo ===================================================
echo.
echo Starting backend server on port 8000...
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in venv folder!
    echo Please ensure Python and dependencies are installed.
    pause
    exit /b 1
)

start "" http://localhost:8000

echo Backend is running at http://localhost:8000
echo You can close this window to stop the server.
echo.

.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
