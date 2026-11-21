"""Troop/building detection on the arena.

The engine works without unit detection (it then advises on cycle, elixir
and push timing). For full "what beats what is on the board" advice, plug in
a detector. ``YoloDetector`` wraps an Ultralytics YOLO model trained on
Clash Royale screenshots (several public datasets exist on Roboflow; train
one and point ``--yolo`` at the weights plus a class map JSON).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Protocol

import numpy as np

from ..state import Unit
from .layout import Layout


class UnitDetector(Protocol):
    def detect(self, frame: np.ndarray, layout: Layout) -> List[Unit]: ...


class NullDetector:
    """Detects nothing. Units can still be fed manually through the overlay."""

    def detect(self, frame: np.ndarray, layout: Layout) -> List[Unit]:
        return []


class YoloDetector:
    """Ultralytics YOLO wrapper.

    ``class_map`` maps the model's class names to ``{"card": key, "side": "me"|"opp"|"auto"}``.
    With ``"auto"`` the side is inferred from the unit's colour of health bar
    (blue = me, red = opp) sampled just above the box; if that fails we fall
    back to the arena half.
    """

    def __init__(self, weights: Path, class_map: Path, conf: float = 0.35):
        from ultralytics import YOLO  # optional dependency
        self.model = YOLO(str(weights))
        with open(class_map, "r", encoding="utf-8") as fh:
            self.class_map: Dict[str, dict] = json.load(fh)
        self.conf = conf

    def detect(self, frame: np.ndarray, layout: Layout) -> List[Unit]:
        arena = layout.crop(frame, "arena")
        ah, aw = arena.shape[:2]
        h, w = frame.shape[:2]
        ax0, ay0, _, _ = layout.pixels("arena", w, h)
        results = self.model.predict(arena, conf=self.conf, verbose=False)
        units: List[Unit] = []
        for r in results:
            names = r.names
            for box in r.boxes:
                cls = names[int(box.cls[0])]
                info = self.class_map.get(cls)
                if not info:
                    continue
                x0, y0, x1, y1 = [float(v) for v in box.xyxy[0]]
                cx, cy = (x0 + x1) / 2 + ax0, (y0 + y1) / 2 + ay0
                tx, ty = layout.arena_to_tiles(frame.shape, cx, cy)
                side = info.get("side", "auto")
                if side == "auto":
                    side = _side_from_healthbar(frame, x0 + ax0, y0 + ay0, x1 + ax0) or ("opp" if ty > 16 else "me")
                units.append(Unit(card=info["card"], side=side, x=tx, y=ty, hp_frac=1.0, id=f"{cls}:{len(units)}"))
        return units


def _side_from_healthbar(frame: np.ndarray, x0: float, y0: float, x1: float) -> Optional[str]:
    import cv2
    y_top = int(max(0, y0 - 14))
    strip = frame[y_top:int(max(y_top + 1, y0)), int(max(0, x0)):int(min(frame.shape[1], x1))]
    if strip.size == 0:
        return None
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1] > 90
    hue = hsv[:, :, 0]
    blue = ((hue > 95) & (hue < 130) & sat).sum()
    red = (((hue < 10) | (hue > 165)) & sat).sum()
    if blue + red < 8:
        return None
    return "me" if blue > red else "opp"
