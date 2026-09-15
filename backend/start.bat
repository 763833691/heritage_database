@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "BACKEND_PORT=8001"
set "ROOT_DIR=%~dp0"

set "PYTHON_EXE="
python --version >nul 2>&1 && for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
if not defined PYTHON_EXE py -3 --version >nul 2>&1 && for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
if not defined PYTHON_EXE if exist "E:\software\install\Anaconda\python.exe" set "PYTHON_EXE=E:\software\install\Anaconda\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_EXE (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /C:":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
    echo Freeing port %BACKEND_PORT% PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting backend: http://localhost:%BACKEND_PORT%
echo Press Ctrl+C to stop
echo.
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload
