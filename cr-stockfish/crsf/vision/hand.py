"""Identify the four cards in hand (and the next card) by template matching.

Templates are small PNG crops of each card slot, named ``<card_key>.png``,
stored in a templates directory (``python -m crsf learn-cards`` produces them).
Matching is scale-normalised: both the template and the live crop are resized
to the same size, then compared with normalised cross-correlation plus a colour
histogram, so it survives moderate resolution and emulator differences.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .layout import HAND_SLOTS, Layout

MATCH_SIZE = (48, 60)     # (w, h) to which slot crops are normalised
MIN_CONFIDENCE = 0.55


def _prep(img: np.ndarray) -> np.ndarray:
    img = cv2.resize(img, MATCH_SIZE, interpolation=cv2.INTER_AREA)
    # Drop the bottom ~22% (elixir-cost badge sits at the top-left, the lower
    # part is the card frame) - keep the artwork region.
    return img


def _hist(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [18, 6], [0, 180, 0, 256])
    cv2.normalize(h, h)
    return h.flatten()


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ga -= ga.mean()
    gb -= gb.mean()
    denom = float(np.sqrt((ga * ga).sum() * (gb * gb).sum()))
    if denom < 1e-6:
        return 0.0
    return float((ga * gb).sum() / denom)


class CardMatcher:
    def __init__(self, template_dir: Optional[Path] = None):
        self.templates: Dict[str, np.ndarray] = {}
        self._hists: Dict[str, np.ndarray] = {}
        self.dir = Path(template_dir) if template_dir else None
        if self.dir and self.dir.is_dir():
            for p in sorted(self.dir.glob("*.png")):
                img = cv2.imread(str(p), cv2.IMREAD_COLOR)
                if img is not None:
                    self.add(p.stem, img)

    def add(self, key: str, img: np.ndarray) -> None:
        t = _prep(img)
        self.templates[key] = t
        self._hists[key] = _hist(t)

    def __len__(self) -> int:
        return len(self.templates)

    def identify(self, crop: np.ndarray) -> Tuple[Optional[str], float]:
        if crop.size == 0 or not self.templates:
            return None, 0.0
        q = _prep(crop)
        qh = _hist(q)
        grey = is_greyed(q)      # unaffordable cards are desaturated: colour is useless
        best, best_score = None, -1.0
        for key, t in self.templates.items():
            ncc = _ncc(q, t)
            if grey:
                score = ncc
            else:
                hist = float(cv2.compareHist(qh, self._hists[key], cv2.HISTCMP_CORREL))
                score = 0.6 * ncc + 0.4 * hist
            if score > best_score:
                best, best_score = key, score
        if best_score < MIN_CONFIDENCE:
            return None, best_score
        return best, best_score


def is_greyed(crop: np.ndarray) -> bool:
    """True when the card slot is desaturated (not enough elixir to play it)."""
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 1].mean()) < 45


def read_hand(frame: np.ndarray, layout: Layout, matcher: CardMatcher):
    """Return ([(key|None, confidence, greyed) x4], (next_key|None, conf))."""
    slots = []
    for name in HAND_SLOTS:
        crop = layout.crop(frame, name)
        key, conf = matcher.identify(crop)
        slots.append((key, conf, is_greyed(crop)))
    nxt = (None, 0.0)
    if layout.has("next_card"):
        nxt = matcher.identify(layout.crop(frame, "next_card"))
    return slots, nxt
