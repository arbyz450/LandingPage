"""ADB device access: screenshots in, taps out.

Works with any Android target that exposes ADB:

* BlueStacks 5 / LDPlayer 9 / MEmu / Nox / MuMu (enable ADB in the emulator
  settings; see ``EMULATOR_PORTS``),
* a real phone over USB (enable Developer options -> USB debugging) or Wi-Fi
  ADB (``adb tcpip 5555`` then ``--connect <phone-ip>:5555``).

``adb exec-out screencap -p`` gives an exact device-resolution PNG in roughly
60-150 ms on an emulator, which is plenty for a 4-6 Hz decision loop and
removes any need to calibrate a window position: taps and pixels share the
same coordinate system.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..vision.capture import FrameSource
from ..vision.layout import HAND_SLOTS, Layout

EMULATOR_PORTS = {
    "bluestacks": 5555,
    "ldplayer": 5555,
    "memu": 21503,
    "nox": 62001,
    "mumu": 7555,
}


class AdbError(RuntimeError):
    pass


class AdbDevice:
    def __init__(self, serial: Optional[str] = None, adb_path: Optional[str] = None, timeout: float = 5.0):
        self.adb = adb_path or shutil.which("adb") or "adb"
        self.serial = serial
        self.timeout = timeout
        self._size: Optional[Tuple[int, int]] = None

    # ----- plumbing -------------------------------------------------------
    def _cmd(self, *args: str) -> List[str]:
        base = [self.adb]
        if self.serial:
            base += ["-s", self.serial]
        return base + list(args)

    def run(self, *args: str, binary: bool = False, timeout: Optional[float] = None):
        try:
            out = subprocess.run(self._cmd(*args), capture_output=True, timeout=timeout or self.timeout, check=False)
        except FileNotFoundError as exc:
            raise AdbError(f"adb not found ({self.adb}); install Android platform-tools and put adb on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb {' '.join(args)} timed out") from exc
        if out.returncode != 0:
            raise AdbError(f"adb {' '.join(args)} failed: {out.stderr.decode(errors='replace').strip()}")
        return out.stdout if binary else out.stdout.decode(errors="replace")

    @classmethod
    def devices(cls, adb_path: Optional[str] = None) -> List[Tuple[str, str]]:
        dev = cls(adb_path=adb_path)
        lines = dev.run("devices").strip().splitlines()[1:]
        return [tuple(l.split()[:2]) for l in lines if l.strip() and "\t" in l or len(l.split()) >= 2]

    def connect(self, host_port: str) -> str:
        out = self.run("connect", host_port, timeout=10)
        if "connected" not in out and "already" not in out:
            raise AdbError(out.strip())
        self.serial = host_port
        return out.strip()

    def wm_size(self) -> Tuple[int, int]:
        if self._size is None:
            out = self.run("shell", "wm", "size")
            # "Physical size: 1080x1920" (an "Override size" line wins if present)
            line = [l for l in out.splitlines() if "size" in l][-1]
            w, h = line.split(":")[1].strip().split("x")
            self._size = (int(w), int(h))
        return self._size

    # ----- I/O ----------------------------------------------------------
    def screencap(self) -> np.ndarray:
        png = self.run("exec-out", "screencap", "-p", binary=True)
        img = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("screencap returned no image (is the device unlocked and the app in front?)")
        return img

    def tap(self, x: int, y: int) -> None:
        self.run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x0: int, y0: int, x1: int, y1: int, ms: int = 120) -> None:
        self.run("shell", "input", "swipe", str(int(x0)), str(int(y0)), str(int(x1)), str(int(y1)), str(ms))


class AdbSource(FrameSource):
    def __init__(self, device: AdbDevice):
        self.device = device

    def grab(self) -> np.ndarray:
        return self.device.screencap()


class AdbActuator:
    """Turns (card slot, tile) into two taps on the device.

    ``frame_bbox`` is the game frame inside the device screenshot (from the
    advisor's auto-frame detection) so layout fractions map to device pixels.
    """

    def __init__(self, device: AdbDevice, layout: Layout, dry_run: bool = False, tap_gap: float = 0.08):
        self.device = device
        self.layout = layout
        self.dry_run = dry_run
        self.tap_gap = tap_gap
        self.log: List[dict] = []

    def _frame_geom(self, frame_shape, frame_bbox):
        if frame_bbox is None:
            h, w = frame_shape[:2]
            return 0, 0, w, h
        return frame_bbox

    def slot_pixel(self, slot: int, frame_shape, frame_bbox) -> Tuple[int, int]:
        fx, fy, fw, fh = self._frame_geom(frame_shape, frame_bbox)
        x0, y0, x1, y1 = self.layout.pixels(HAND_SLOTS[slot], fw, fh)
        return fx + (x0 + x1) // 2, fy + (y0 + y1) // 2

    def tile_pixel(self, tx: float, ty: float, frame_shape, frame_bbox) -> Tuple[int, int]:
        fx, fy, fw, fh = self._frame_geom(frame_shape, frame_bbox)
        ax0, ay0, ax1, ay1 = self.layout.pixels("arena", fw, fh)
        px = ax0 + (tx / 18.0) * (ax1 - ax0)
        py = ay0 + (1.0 - ty / 32.0) * (ay1 - ay0)
        return fx + int(round(px)), fy + int(round(py))

    def play(self, slot: int, tx: float, ty: float, frame_shape, frame_bbox=None, label: str = "") -> dict:
        sx, sy = self.slot_pixel(slot, frame_shape, frame_bbox)
        px, py = self.tile_pixel(tx, ty, frame_shape, frame_bbox)
        entry = {"t": time.time(), "slot": slot, "tile": (round(tx, 1), round(ty, 1)), "slot_px": (sx, sy), "tile_px": (px, py), "label": label, "dry_run": self.dry_run}
        self.log.append(entry)
        if not self.dry_run:
            self.device.tap(sx, sy)
            time.sleep(self.tap_gap)
            self.device.tap(px, py)
        return entry
