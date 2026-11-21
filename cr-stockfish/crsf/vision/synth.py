"""Synthetic game frames for testing the vision pipeline without a real game."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from crsf.vision.layout import HAND_SLOTS, Layout

PURPLE = (230, 60, 190)      # BGR
BAR_BG = (40, 20, 50)

CARD_STYLES: Dict[str, Tuple[Tuple[int, int, int], int]] = {
    # key: (BGR colour, shape id)
    "knight": ((60, 120, 200), 0),
    "musketeer": ((200, 80, 120), 1),
    "fireball": ((30, 90, 240), 2),
    "skeleton_army": ((220, 220, 220), 3),
    "hog_rider": ((40, 160, 90), 0),
    "zap": ((240, 200, 40), 1),
    "giant": ((20, 60, 150), 2),
    "log": ((40, 70, 110), 3),
}


def draw_card(w: int = 96, h: int = 120, key: str = "knight", greyed: bool = False) -> np.ndarray:
    color, shape = CARD_STYLES[key]
    img = np.full((h, w, 3), (60, 50, 70), dtype=np.uint8)
    cv2.rectangle(img, (3, 3), (w - 4, h - 4), (120, 110, 130), 2)
    c = tuple(int(v) for v in color)
    if shape == 0:
        cv2.circle(img, (w // 2, h // 2), min(w, h) // 3, c, -1)
    elif shape == 1:
        cv2.rectangle(img, (w // 5, h // 5), (w - w // 5, h - h // 5), c, -1)
    elif shape == 2:
        pts = np.array([[w // 2, h // 6], [w - w // 6, h - h // 6], [w // 6, h - h // 6]], np.int32)
        cv2.fillPoly(img, [pts], c)
    else:
        cv2.ellipse(img, (w // 2, h // 2), (w // 3, h // 5), 30, 0, 360, c, -1)
        cv2.ellipse(img, (w // 2, h // 2), (w // 5, h // 3), 30, 0, 360, c, -1)
    cv2.circle(img, (12, 12), 9, (230, 60, 190), -1)   # elixir badge
    if greyed:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    return img


def make_frame(layout: Layout, width: int = 540, height: int = 960, elixir: float = 6.4,
               hand: Optional[List[str]] = None, next_card: Optional[str] = None,
               greyed: Optional[List[bool]] = None, letterbox: int = 0, desktop: int = 0) -> np.ndarray:
    """A fake 9:16 game frame.

    ``letterbox`` adds black bars on both sides (emulator style); ``desktop``
    embeds the frame in a bright desktop with a grey sidebar on the left
    (Google Play Games on PC style).
    """
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (70, 60, 50)                        # HUD: dark blue-brown
    ax0, ay0, ax1, ay1 = layout.pixels("arena", width, height)
    cv2.rectangle(frame, (0, 0), (width, ay1 + int(0.08 * height)), (90, 140, 70), -1)   # arena + grass/trees reach the frame edges
    hand = hand or ["knight", "musketeer", "fireball", "skeleton_army"]
    greyed = greyed or [False] * 4
    # elixir bar
    x0, y0, x1, y1 = layout.pixels("elixir_bar", width, height)
    cv2.rectangle(frame, (x0, y0), (x1, y1), BAR_BG, -1)
    fill = int(round((x1 - x0) * elixir / 10.0))
    if fill > 0:
        cv2.rectangle(frame, (x0, y0), (x0 + fill, y1), PURPLE, -1)
    for i in range(1, 10):                          # segment dividers
        xd = x0 + int((x1 - x0) * i / 10)
        cv2.line(frame, (xd, y0), (xd, y1), (20, 10, 30), 1)
    # hand slots
    for name, key, g in zip(HAND_SLOTS, hand, greyed):
        sx0, sy0, sx1, sy1 = layout.pixels(name, width, height)
        frame[sy0:sy1, sx0:sx1] = cv2.resize(draw_card(key=key, greyed=g), (sx1 - sx0, sy1 - sy0))
    if next_card and layout.has("next_card"):
        sx0, sy0, sx1, sy1 = layout.pixels("next_card", width, height)
        frame[sy0:sy1, sx0:sx1] = cv2.resize(draw_card(key=next_card), (sx1 - sx0, sy1 - sy0))
    if letterbox:
        out = np.zeros((height, width + 2 * letterbox, 3), dtype=np.uint8)
        out[:, letterbox:letterbox + width] = frame
        return out
    if desktop:
        out = np.full((height + 2 * desktop, width + 3 * desktop, 3), (120, 170, 210), dtype=np.uint8)   # sky-blue desktop
        out[:, :desktop] = (40, 40, 40)                                                                  # grey sidebar
        out[desktop:desktop + height, 2 * desktop:2 * desktop + width] = frame
        return out
    return frame
