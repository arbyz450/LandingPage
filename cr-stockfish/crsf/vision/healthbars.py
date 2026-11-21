"""Find troops and buildings by their health bars.

Every unit on the arena carries a small horizontal health bar: blue for the
player's units, red for the opponent's. Detecting those coloured bars gives,
with no machine learning at all, each unit's position, side and remaining HP
fraction. What it does not give is the unit's identity; ``UnitClassifier``
(unit_classifier.py) fills that in from labelled crops, and until a label is
known the engine treats the unit as a generic ``unknown`` threat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..state import MY_TOWER_POS, OPP_TOWER_POS, Unit
from .layout import Layout

# HSV (OpenCV ranges). Enemy bars are red; friendly bars are blue.
RED_LO1, RED_HI1 = np.array([0, 140, 120]), np.array([8, 255, 255])
RED_LO2, RED_HI2 = np.array([168, 140, 120]), np.array([180, 255, 255])
BLUE_LO, BLUE_HI = np.array([95, 140, 120]), np.array([125, 255, 255])


@dataclass
class Bar:
    x: int          # bbox in frame pixels (coloured part)
    y: int
    w: int
    h: int
    side: str       # "me" | "opp"
    hp_frac: float
    full_w: int

    @property
    def cx(self) -> float:
        return self.x + self.full_w / 2.0

    @property
    def unit_xy(self) -> Tuple[float, float]:
        """Approximate unit centre: a bit below the bar."""
        return self.cx, self.y + self.h * 4.0


def _bar_mask(hsv: np.ndarray, side: str) -> np.ndarray:
    if side == "opp":
        m = cv2.inRange(hsv, RED_LO1, RED_HI1) | cv2.inRange(hsv, RED_LO2, RED_HI2)
    else:
        m = cv2.inRange(hsv, BLUE_LO, BLUE_HI)
    # Keep thin horizontal structures only.
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    return m


def detect_bars(arena_bgr: np.ndarray, min_w_frac: float = 0.012, max_w_frac: float = 0.09,
                max_h_frac: float = 0.012) -> List[Bar]:
    h, w = arena_bgr.shape[:2]
    hsv = cv2.cvtColor(arena_bgr, cv2.COLOR_BGR2HSV)
    gray_v = hsv[:, :, 2]
    bars: List[Bar] = []
    for side in ("opp", "me"):
        mask = _bar_mask(hsv, side)
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            if bw < min_w_frac * w or bw > max_w_frac * w or bh > max_h_frac * h or bh < 2:
                continue
            if bw / max(1, bh) < 2.2 or area < 0.55 * bw * bh:
                continue
            # Extend to the right over the dark "empty" part of the bar to get the full width.
            row = y + bh // 2
            full = bw
            xx = x + bw
            limit = min(w, x + int(bw * 4))
            while xx < limit and gray_v[row, xx] < 90:
                xx += 1
                full += 1
            frac = bw / max(bw, full)
            bars.append(Bar(int(x), int(y), int(bw), int(bh), side, float(min(1.0, frac)), int(full)))
    return _merge_overlaps(bars)


def _merge_overlaps(bars: List[Bar]) -> List[Bar]:
    out: List[Bar] = []
    for b in sorted(bars, key=lambda b: (-b.w)):
        if any(abs(o.y - b.y) <= max(2, o.h) and abs(o.cx - b.cx) < max(o.full_w, b.full_w) * 0.6 for o in out):
            continue
        out.append(b)
    return out


def _near_tower(tx: float, ty: float, radius: float = 2.2) -> bool:
    for (x, y) in list(MY_TOWER_POS.values()) + list(OPP_TOWER_POS.values()):
        if abs(tx - x) <= radius and abs(ty - y) <= radius:
            return True
    return False


class HealthbarDetector:
    """UnitDetector that finds units by health bars and classifies them if it can."""

    def __init__(self, classifier=None, crop_scale: float = 1.6, ignore_towers: bool = True):
        self.classifier = classifier
        self.crop_scale = crop_scale
        self.ignore_towers = ignore_towers
        self.last_bars: List[Bar] = []
        self.last_crops: List[np.ndarray] = []

    def unit_crop(self, frame: np.ndarray, bar: Bar, ax0: int, ay0: int) -> np.ndarray:
        size = int(max(16, bar.full_w * self.crop_scale))
        cx = int(ax0 + bar.cx)
        y0 = int(ay0 + bar.y + bar.h)
        x0 = max(0, cx - size // 2)
        return frame[y0:y0 + int(size * 1.3), x0:x0 + size]

    def detect(self, frame: np.ndarray, layout: Layout) -> List[Unit]:
        arena = layout.crop(frame, "arena")
        h, w = frame.shape[:2]
        ax0, ay0, _, _ = layout.pixels("arena", w, h)
        bars = detect_bars(arena)
        units: List[Unit] = []
        crops: List[np.ndarray] = []
        kept: List[Bar] = []
        for b in bars:
            ux, uy = b.unit_xy
            tx, ty = layout.arena_to_tiles(frame.shape, ax0 + ux, ay0 + uy)
            if self.ignore_towers and _near_tower(tx, ty):
                continue
            crop = self.unit_crop(frame, b, ax0, ay0)
            key, conf = ("unknown", 0.0)
            if self.classifier is not None and crop.size:
                k, c = self.classifier.identify(crop)
                if k:
                    key, conf = k, c
            units.append(Unit(card=key, side=b.side, x=tx, y=ty, hp_frac=b.hp_frac, id=f"{b.side}:{int(b.cx)}:{int(b.y)}"))
            crops.append(crop)
            kept.append(b)
        self.last_bars, self.last_crops = kept, crops
        return units
