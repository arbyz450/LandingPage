@echo off
REM One-file Windows build of the CR Stockfish dashboard (dist\CRStockfish.exe).
REM Run from the cr-stockfish folder on a Windows PC with Python 3.10+ on PATH.
setlocal
cd /d "%~dp0"
if not exist .venv-build (
    python -m venv .venv-build || goto :fail
)
call .venv-build\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip || goto :fail
pip install -r requirements.txt pygetwindow pyautogui pyinstaller || goto :fail
pyinstaller --clean --noconfirm crsf_gui.spec || goto :fail
echo.
echo Built dist\CRStockfish.exe
echo Send that single file. On first run it opens the dashboard in a browser app window.
echo Note: knowledge\*.json and crsf\data are bundled; templates\ (your labelled cards)
echo are created next to the exe on first use, so share them with the exe if you want.
exit /b 0
:fail
echo Build failed.
exit /b 1
