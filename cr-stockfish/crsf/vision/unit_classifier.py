"""Nearest-neighbour unit classifier over labelled crops, with auto-labelling.

Templates live in ``templates/units/<card_key>/*.png``. The advisor adds new
crops automatically: when you type ``o hog`` and a new enemy health bar just
appeared, that crop is saved under ``hog_rider``; when your own hand changes
(you played a card) and a new friendly bar appeared, it is saved under that
card. Over a handful of games the classifier learns both decks' sprites on
your exact emulator, with no training step.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

FEAT_SIZE = (32, 40)
MIN_CONF = 0.6
MAX_PER_CLASS = 40


def _feat(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    img = cv2.resize(img, FEAT_SIZE, interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g -= g.mean()
    n = float(np.linalg.norm(g)) or 1.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return g.flatten() / n, hist.flatten()


class UnitClassifier:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else None
        self._g: Dict[str, List[np.ndarray]] = {}
        self._h: Dict[str, List[np.ndarray]] = {}
        if self.root and self.root.is_dir():
            for d in sorted(self.root.iterdir()):
                if d.is_dir():
                    for p in sorted(d.glob("*.png"))[:MAX_PER_CLASS]:
                        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
                        if img is not None:
                            self.add(d.name, img, save=False)

    def __len__(self) -> int:
        return sum(len(v) for v in self._g.values())

    def classes(self) -> List[str]:
        return sorted(self._g)

    def add(self, key: str, crop: np.ndarray, save: bool = True) -> Optional[Path]:
        if crop is None or crop.size == 0 or min(crop.shape[:2]) < 6:
            return None
        g, h = _feat(crop)
        self._g.setdefault(key, []).append(g)
        self._h.setdefault(key, []).append(h)
        if len(self._g[key]) > MAX_PER_CLASS:
            self._g[key].pop(0)
            self._h[key].pop(0)
        if save and self.root:
            d = self.root / key
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{int(time.time() * 1000)}.png"
            cv2.imwrite(str(p), crop)
            return p
        return None

    def identify(self, crop: np.ndarray) -> Tuple[Optional[str], float]:
        if not self._g or crop is None or crop.size == 0 or min(crop.shape[:2]) < 6:
            return None, 0.0
        g, h = _feat(crop)
        best, best_s = None, -1.0
        for key, feats in self._g.items():
            s_g = max(float(np.dot(g, f)) for f in feats)
            s_h = max(float(cv2.compareHist(h, f, cv2.HISTCMP_CORREL)) for f in self._h[key])
            s = 0.65 * s_g + 0.35 * s_h
            if s > best_s:
                best, best_s = key, s
        if best_s < MIN_CONF:
            return None, best_s
        return best, best_s
