@echo off
REM CR Stockfish - double-click start for Windows.
REM Creates a virtual environment on first run, installs dependencies, downloads
REM card icons, finds the Clash Royale window and opens the dashboard.
setlocal
cd /d "%~dp0"

set PY=
REM Any Python 3.10+ works (numpy/OpenCV wheels exist up to 3.15). Prefer the newest that actually runs.
for %%V in (3.13 3.12 3.14 3.15 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set PY=py -%%V
    )
)
if not defined PY (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)" >nul 2>&1 && set PY=python
)
if not defined PY (
    echo Python 3.10+ was not found. Installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    set PY=py -3.12
)

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    %PY% -m venv .venv || goto :fail
)
set VPY=.venv\Scripts\python.exe
%VPY% -m pip install --quiet --upgrade pip
%VPY% -m pip install --quiet -r requirements.txt pygetwindow pyautogui || goto :fail

echo.
echo Starting CR Stockfish. Keep Clash Royale (Google Play Games) open and visible.
echo The dashboard opens in your browser; autoplay starts DISARMED in dry run.
echo.
%VPY% -m crsf go --auto-install %*
goto :eof

:fail
echo.
echo Setup failed. Run "python -m crsf doctor" inside this folder for details.
pause
