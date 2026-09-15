@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion

title Heritage Platform Startup
cd /d "%~dp0"

set "BACKEND_PORT=8001"
set "FRONTEND_PORT=3000"
set "ROOT_DIR=%cd%"

echo.
echo   ========================================================
echo     Heritage Park Research Platform
echo   ========================================================
echo.

echo   [1/6] Checking Python...
call :FindPython
if errorlevel 1 (
    echo   [ERROR] Python 3.10+ not found
    echo   Install Python or Anaconda and add it to PATH
    pause
    exit /b 1
)
for /f "delims=" %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do echo   %%v
echo   Path: %PYTHON_EXE%
echo   [OK]

echo.
echo   [2/6] Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Node.js not found
    echo   Install Node.js 18+ and add it to PATH
    pause
    exit /b 1
)
for /f "delims=" %%v in ('node --version 2^>^&1') do echo   Node.js %%v
echo   [OK]

echo.
echo   [3/6] Checking backend dependencies...
cd /d "%ROOT_DIR%\backend"
"%PYTHON_EXE%" -c "import uvicorn, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo   Installing backend dependencies...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] Backend dependency install failed
        pause
        exit /b 1
    )
) else (
    echo   Backend dependencies ready
)
"%PYTHON_EXE%" -c "import chromadb" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] ChromaDB not installed, vector search disabled
)
echo   [OK]

echo.
echo   [4/6] Checking frontend dependencies...
cd /d "%ROOT_DIR%\frontend"
if not exist "node_modules" (
    echo   Installing frontend dependencies...
    call npm ci
    if errorlevel 1 (
        echo   npm ci failed, trying npm install...
        call npm install
        if errorlevel 1 (
            echo   [ERROR] Frontend dependency install failed
            pause
            exit /b 1
        )
    )
) else (
    echo   Frontend dependencies ready
)
echo   [OK]

echo.
echo   [5/6] Checking database...
cd /d "%ROOT_DIR%\backend"
if not exist "data\heritage.db" (
    echo   Initializing database...
    "%PYTHON_EXE%" scripts\init_db.py
    if errorlevel 1 (
        echo   [ERROR] Database init failed
        pause
        exit /b 1
    )
) else (
    echo   Database exists, skip init
)
echo   [OK]

echo.
echo   [6/6] Starting services...

call :KillPort %BACKEND_PORT%
call :KillPort %FRONTEND_PORT%
ping 127.0.0.1 -n 2 >nul

cd /d "%ROOT_DIR%\backend"
start "Backend-%BACKEND_PORT%" cmd /k "cd /d %ROOT_DIR%\backend && "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

cd /d "%ROOT_DIR%\frontend"
start "Frontend-%FRONTEND_PORT%" cmd /k "cd /d %ROOT_DIR%\frontend && npm run dev"

echo   Waiting for services...
call :WaitForHttp "http://127.0.0.1:%BACKEND_PORT%/docs" 45
call :WaitForHttp "http://127.0.0.1:%FRONTEND_PORT%/" 45

echo.
echo   ========================================================
echo     Startup complete
echo   ========================================================
echo.
echo     Frontend:  http://localhost:%FRONTEND_PORT%
echo     API Docs:  http://localhost:%BACKEND_PORT%/docs
echo.
echo     Login is currently disabled - open frontend directly
echo.
echo   ========================================================
echo     Press any key to stop all services and exit
echo   ========================================================
echo.

start "" "http://localhost:%FRONTEND_PORT%"

pause

echo.
echo   Stopping services...
call :KillPort %BACKEND_PORT%
call :KillPort %FRONTEND_PORT%
echo   Done.
ping 127.0.0.1 -n 3 >nul
exit /b 0


:FindPython
set "PYTHON_EXE="
python --version >nul 2>&1
if not errorlevel 1 for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
if defined PYTHON_EXE exit /b 0

py -3 --version >nul 2>&1
if not errorlevel 1 for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
if defined PYTHON_EXE exit /b 0

py --version >nul 2>&1
if not errorlevel 1 for /f "delims=" %%i in ('py -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
if defined PYTHON_EXE exit /b 0

if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe" & exit /b 0
if exist "%USERPROFILE%\miniconda3\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\python.exe" & exit /b 0
if exist "E:\software\install\Anaconda\python.exe" set "PYTHON_EXE=E:\software\install\Anaconda\python.exe" & exit /b 0
if exist "C:\ProgramData\anaconda3\python.exe" set "PYTHON_EXE=C:\ProgramData\anaconda3\python.exe" & exit /b 0
exit /b 1


:KillPort
set "PORT=%~1"
set "KILLED=0"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr "LISTENING"') do (
    echo   Freeing port %PORT% PID %%a
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED=1"
)
if "!KILLED!"=="0" echo   Port %PORT% is free
exit /b 0


:WaitForHttp
set "URL=%~1"
set "TIMEOUT=%~2"
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(%TIMEOUT%); while((Get-Date) -lt $deadline) { try { $r=Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { Write-Host '   [OK] %URL%'; exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; Write-Host '   [WARN] Timeout: %URL%'; exit 1"
exit /b 0
