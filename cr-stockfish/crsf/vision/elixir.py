"""Read the elixir bar by measuring how much of it is filled with purple."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .layout import Layout

# OpenCV HSV hue is 0..180. Elixir purple/magenta sits around 135..165.
PURPLE_LO = np.array([125, 70, 80], dtype=np.uint8)
PURPLE_HI = np.array([170, 255, 255], dtype=np.uint8)


def purple_mask(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, PURPLE_LO, PURPLE_HI)


def read_elixir(frame: np.ndarray, layout: Layout, max_elixir: float = 10.0) -> Optional[float]:
    """Return elixir in [0, 10] with 0.1 resolution, or None if the bar is not visible."""
    bar = layout.crop(frame, "elixir_bar")
    if bar.size == 0:
        return None
    h, w = bar.shape[:2]
    # Use the middle 60% of rows to avoid the bar's rounded border.
    band = bar[int(h * 0.2): max(int(h * 0.2) + 1, int(h * 0.8)), :]
    mask = purple_mask(band) > 0
    col_fill = mask.mean(axis=0)                     # fraction of purple per column
    filled = col_fill > 0.45
    if filled.mean() < 0.02 and col_fill.max() < 0.3:
        # Nothing purple at all: either 0 elixir or the HUD is not on screen.
        # Distinguish by checking the bar looks like a dark trough.
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        return 0.0 if gray.mean() < 90 else None
    # Elixir fills left to right; find the right-most run of filled columns
    # starting from the left edge (tolerating the segment dividers).
    run_end = 0
    gap = 0
    for i, f in enumerate(filled):
        if f:
            run_end = i + 1
            gap = 0
        else:
            gap += 1
            if gap > max(3, w // 25):
                break
    frac = run_end / w
    return round(min(max_elixir, frac * max_elixir), 1)
