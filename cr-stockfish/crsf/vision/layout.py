"""HUD layout: where each element lives, as fractions of the game frame."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

DEFAULT_LAYOUT_PATH = Path(__file__).parent.parent / "data" / "layout.json"
Region = Tuple[float, float, float, float]

HAND_SLOTS = ("hand_1", "hand_2", "hand_3", "hand_4")
TOWER_REGIONS = {
    "opp_left": "opp_left_hp", "opp_right": "opp_right_hp", "opp_king": "opp_king_hp",
    "my_left": "my_left_hp", "my_right": "my_right_hp", "my_king": "my_king_hp",
}


@dataclass
class Layout:
    regions: Dict[str, Region] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Layout":
        path = Path(path) if path else DEFAULT_LAYOUT_PATH
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        regions = {k: tuple(float(v) for v in val) for k, val in raw.items() if not k.startswith("_")}
        return cls(regions)

    def save(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({k: list(v) for k, v in self.regions.items()}, fh, indent=2)

    def has(self, name: str) -> bool:
        return name in self.regions

    def pixels(self, name: str, width: int, height: int) -> Tuple[int, int, int, int]:
        x0, y0, x1, y1 = self.regions[name]
        return (int(round(x0 * width)), int(round(y0 * height)), int(round(x1 * width)), int(round(y1 * height)))

    def crop(self, frame: np.ndarray, name: str) -> np.ndarray:
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = self.pixels(name, w, h)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, max(x0 + 1, x1)), min(h, max(y0 + 1, y1))
        return frame[y0:y1, x0:x1]

    def arena_to_tiles(self, frame_shape, px: float, py: float) -> Tuple[float, float]:
        """Map a pixel in the game frame to arena tile coordinates (my king = y 0)."""
        h, w = frame_shape[:2]
        ax0, ay0, ax1, ay1 = self.pixels("arena", w, h)
        fx = (px - ax0) / max(1, ax1 - ax0)
        fy = (py - ay0) / max(1, ay1 - ay0)
        return 18.0 * min(1.0, max(0.0, fx)), 32.0 * (1.0 - min(1.0, max(0.0, fy)))
