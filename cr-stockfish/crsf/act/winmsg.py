"""Clicking a window without moving the user's mouse (Windows only).

``WindowMessageActuator`` posts WM_LBUTTONDOWN/UP straight to the window under
each target point, so the real cursor never moves and you can keep using the
PC. It works for most windows (Chromium/Android containers such as Google
Play Games on PC usually accept posted mouse messages); a few games read raw
input and ignore it. If nothing happens in-game, fall back to
``--input mouse`` (real clicks, cursor restored afterwards) or ADB.
"""
from __future__ import annotations

import ctypes
import sys
import time
from typing import List, Optional, Tuple

from ..vision.layout import Layout
from .adb import AdbActuator

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


def _lparam(x: int, y: int) -> int:
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


class WindowMessageActuator(AdbActuator):
    def __init__(self, layout: Layout, window_title: str, origin: Tuple[int, int] = (0, 0), dry_run: bool = False, tap_gap: float = 0.08):
        super().__init__(device=None, layout=layout, dry_run=dry_run, tap_gap=tap_gap)
        self.origin = origin
        self.title = window_title
        self.hwnd = None
        if not dry_run:
            if sys.platform != "win32":
                raise RuntimeError("window-message input is Windows only; use --input mouse or ADB")
            self.user32 = ctypes.windll.user32
            self.hwnd = self._find_window(window_title)
            if not self.hwnd:
                raise RuntimeError(f"no window whose title contains {window_title!r}")

    # ----- win32 helpers --------------------------------------------------
    def _find_window(self, needle: str):
        found: List[int] = []
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            n = self.user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            self.user32.GetWindowTextW(hwnd, buf, n + 1)
            if needle.lower() in buf.value.lower():
                found.append(hwnd)
            return True

        self.user32.EnumWindows(EnumWindowsProc(cb), 0)
        return found[0] if found else None

    def _target_at(self, sx: int, sy: int):
        """Deepest child window under a screen point, plus client coordinates."""
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT(sx, sy)
        hwnd = self.user32.WindowFromPoint(pt) or self.hwnd
        self.user32.ScreenToClient(hwnd, ctypes.byref(pt))
        return hwnd, pt.x, pt.y

    def _click(self, sx: int, sy: int) -> None:
        hwnd, cx, cy = self._target_at(sx, sy)
        lp = _lparam(cx, cy)
        self.user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
        self.user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
        time.sleep(0.03)
        self.user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)

    def play(self, slot: int, tx: float, ty: float, frame_shape, frame_bbox=None, label: str = "") -> dict:
        sx, sy = self.slot_pixel(slot, frame_shape, frame_bbox)
        px, py = self.tile_pixel(tx, ty, frame_shape, frame_bbox)
        ox, oy = self.origin
        entry = {"t": time.time(), "slot": slot, "tile": (round(tx, 1), round(ty, 1)), "slot_px": (ox + sx, oy + sy),
                 "tile_px": (ox + px, oy + py), "label": label, "dry_run": self.dry_run}
        self.log.append(entry)
        if not self.dry_run:
            self._click(ox + sx, oy + sy)
            time.sleep(self.tap_gap)
            self._click(ox + px, oy + py)
        return entry
