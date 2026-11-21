# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for a single-file Windows build of the CR Stockfish dashboard.
# Build with build_windows.bat (or: pyinstaller crsf_gui.spec).
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)

datas = [
    (str(root / "crsf" / "data"), "crsf/data"),
    (str(root / "crsf" / "static"), "crsf/static"),
    (str(root / "knowledge"), "knowledge"),
    (str(root / "benchmarks"), "benchmarks"),
]

hiddenimports = (
    ["cv2", "numpy", "mss", "pygetwindow", "pyautogui", "pyscreeze", "pymsgbox", "pytweening", "mouseinfo"]
    + collect_submodules("crsf")
)

a = Analysis(
    [str(root / "run_gui.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "PyQt5", "PySide2", "IPython", "ultralytics", "torch", "onnxruntime"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CRStockfish",
    debug=False,
    strip=False,
    upx=False,
    console=True,          # keep the console: engine errors and the GUI URL print there
    disable_windowed_traceback=False,
)
