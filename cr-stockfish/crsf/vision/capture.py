"""Frame sources (screen, images) and detection of the 9:16 game frame."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import cv2
import numpy as np

BBox = Tuple[int, int, int, int]   # x, y, w, h


class FrameSource:
    """Yields BGR frames. Subclasses implement ``grab``."""

    origin: Tuple[int, int] = (0, 0)      # screen position of the frame's top-left pixel (for mouse input)

    def grab(self) -> Optional[np.ndarray]:
        raise NotImplementedError

    def frames(self, fps: float = 4.0) -> Iterator[np.ndarray]:
        period = 1.0 / max(0.1, fps)
        while True:
            t0 = time.time()
            f = self.grab()
            if f is None:
                return
            yield f
            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)

    def close(self) -> None:
        pass


class ScreenSource(FrameSource):
    """Captures a monitor (or a bbox on it) with ``mss``."""

    def __init__(self, monitor: int = 1, bbox: Optional[BBox] = None):
        import mss  # imported lazily: not needed for replay / tests
        self._sct = mss.mss()
        mons = self._sct.monitors
        if monitor >= len(mons):
            raise ValueError(f"monitor {monitor} not found (have {len(mons) - 1})")
        mon = mons[monitor]
        if bbox:
            x, y, w, h = bbox
            self.region = {"left": mon["left"] + x, "top": mon["top"] + y, "width": w, "height": h}
        else:
            self.region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        self.origin = (self.region["left"], self.region["top"])

    def grab(self) -> np.ndarray:
        shot = self._sct.grab(self.region)
        img = np.asarray(shot)[:, :, :3]       # BGRA -> BGR
        return np.ascontiguousarray(img)

    def close(self) -> None:
        self._sct.close()


class WindowSource(ScreenSource):
    """Captures a window by title (requires ``pygetwindow``; Windows/macOS)."""

    def __init__(self, title: str):
        import pygetwindow as gw  # optional dependency
        wins = [w for w in gw.getWindowsWithTitle(title) if w.title]
        if not wins:
            raise ValueError(f"no window with title containing {title!r}")
        w = wins[0]
        import mss
        self._sct = mss.mss()
        self.region = {"left": w.left, "top": w.top, "width": w.width, "height": w.height}
        self.origin = (w.left, w.top)
        self.window = w


class ImageSource(FrameSource):
    """Replays a list of image files (or every image in a directory)."""

    def __init__(self, paths: Sequence[Path], loop: bool = False):
        files: List[Path] = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                files += sorted(q for q in p.iterdir() if q.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"))
            else:
                files.append(p)
        if not files:
            raise ValueError("no images to replay")
        self.files = files
        self.loop = loop
        self._i = 0
        self.current: Optional[Path] = None

    def grab(self) -> Optional[np.ndarray]:
        if self._i >= len(self.files):
            if not self.loop:
                return None
            self._i = 0
        self.current = self.files[self._i]
        self._i += 1
        img = cv2.imread(str(self.current), cv2.IMREAD_COLOR)
        if img is None:
            raise IOError(f"could not read {self.current}")
        return img

    def frames(self, fps: float = 0.0) -> Iterator[np.ndarray]:
        # Replay as fast as possible unless an fps is requested.
        if fps <= 0:
            while True:
                f = self.grab()
                if f is None:
                    return
                yield f
        else:
            yield from super().frames(fps)


# --------------------------------------------------------------------------
# Game-frame detection
# --------------------------------------------------------------------------

# Where the elixir bar sits inside the game frame (fraction of height; see data/layout.json).
ELIXIR_BAR_Y_FRAC = 0.978


def find_game_frame_by_anchors(img: np.ndarray) -> Optional[BBox]:
    """Locate the game frame from two things only Clash Royale has on screen:
    the big green arena (gives the horizontal extent) and the long purple
    elixir bar near the bottom (gives the vertical anchor). Works when the
    game sits in a window with a grey sidebar (Google Play Games) or on a
    desktop background, where black-bar detection fails.
    """
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([30, 60, 60]), np.array([90, 255, 255]))
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(green, connectivity=8)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    gx, gy, gw, gh, garea = stats[i]
    if garea < 0.02 * w * h:
        return None
    purple = cv2.inRange(hsv, np.array([125, 70, 80]), np.array([170, 255, 255]))
    # candidate rows below the arena with a long horizontal purple run
    best_row, best_len = None, 0
    rows_len = {}
    for row in range(gy + gh, h):
        line = purple[row]
        if line.sum() == 0:
            continue
        # longest run of purple (allowing small gaps for segment dividers)
        xs = np.where(line > 0)[0]
        if len(xs) < 0.15 * gw:
            continue
        runs, start, prev = [], xs[0], xs[0]
        for x in xs[1:]:
            if x - prev > 6:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
        length = max(b - a for a, b in runs)
        rows_len[row] = length
        if length > best_len:
            best_row, best_len = row, length
    if best_row is None or best_len < 0.15 * gw:
        return None
    bar_rows = [r for r, l in rows_len.items() if l >= 0.85 * best_len and abs(r - best_row) < 0.03 * h]
    best_row = sum(bar_rows) / len(bar_rows)        # centre of the bar, not its top edge
    # Grass and trees reach the frame's left and right edges, so the green
    # blob's width is the frame width.
    frame_w = float(gw)
    x0 = float(gx)
    frame_h = frame_w * 16 / 9
    y0 = best_row - ELIXIR_BAR_Y_FRAC * frame_h
    bx, by = int(round(x0)), int(round(y0))
    bw, bh = int(round(frame_w)), int(round(frame_h))
    if bw < 50 or bh < 80:
        return None
    # clip to the image but keep the size consistent
    bx, by = max(0, bx), max(0, by)
    bw, bh = min(w - bx, bw), min(h - by, bh)
    return (bx, by, bw, bh)


def find_game_frame(img: np.ndarray, aspect: float = 9 / 16, dark_thresh: int = 28) -> BBox:
    """Locate the portrait game area inside a wider capture.

    Tries the arena/elixir-bar anchors first, then black letterbox bars, then
    falls back to a centred 9:16 crop.
    """
    anchored = find_game_frame_by_anchors(img)
    if anchored is not None:
        return anchored
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    col_bright = (gray > dark_thresh).mean(axis=0)
    row_bright = (gray > dark_thresh).mean(axis=1)
    cols = np.where(col_bright > 0.08)[0]
    rows = np.where(row_bright > 0.08)[0]
    if len(cols) > 10 and len(rows) > 10:
        x0, x1 = int(cols[0]), int(cols[-1]) + 1
        y0, y1 = int(rows[0]), int(rows[-1]) + 1
        bw, bh = x1 - x0, y1 - y0
        if bh > 0 and 0.45 <= bw / bh <= 0.75:
            return (x0, y0, bw, bh)
    # Fallback: centred portrait crop using full height.
    bw = int(round(h * aspect))
    if bw <= w:
        return ((w - bw) // 2, 0, bw, h)
    bh = int(round(w / aspect))
    return (0, (h - bh) // 2, w, bh)


def crop_game_frame(img: np.ndarray, bbox: Optional[BBox] = None) -> np.ndarray:
    if bbox is None:
        bbox = find_game_frame(img)
    x, y, w, h = bbox
    return img[y:y + h, x:x + w]
