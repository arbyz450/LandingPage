"""Digit OCR for tower hit points and the match clock.

Uses Tesseract through ``pytesseract`` when it is installed; otherwise every
reader returns None and the engine falls back to defaults (full tower HP,
wall-clock match timer).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

import cv2
import numpy as np


@lru_cache(maxsize=1)
def has_tesseract() -> bool:
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _prep_text(crop: np.ndarray, scale: int = 4) -> np.ndarray:
    if crop.size == 0:
        return crop
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # HUD numbers are white on dark; invert so text is dark on white for Tesseract.
    _, th = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    th = cv2.copyMakeBorder(th, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    return th


def _ocr(crop: np.ndarray, whitelist: str) -> str:
    if not has_tesseract():
        return ""
    import pytesseract
    img = _prep_text(crop)
    cfg = f"--psm 7 -c tessedit_char_whitelist={whitelist}"
    try:
        return pytesseract.image_to_string(img, config=cfg).strip()
    except Exception:
        return ""


def read_digits(crop: np.ndarray) -> Optional[int]:
    txt = _ocr(crop, "0123456789")
    m = re.search(r"\d{2,5}", txt.replace(" ", ""))
    return int(m.group(0)) if m else None


def read_clock(crop: np.ndarray) -> Optional[int]:
    """Return seconds remaining shown by the clock ("2:34" -> 154), or None."""
    txt = _ocr(crop, "0123456789:")
    m = re.search(r"(\d):(\d\d)", txt)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))
