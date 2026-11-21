"""YOLOv5-style ONNX unit detector (e.g. ClashRoyaleBuildABot's MIT-licensed
``units_M_480x352.onnx``; download it from that repository's
``clashroyalebuildabot/models`` folder and provide its class list).

Usage: ``--onnx units.onnx --onnx-classes classes.txt`` where classes.txt has
one class name per line in model order (the project's unit list). Names are
mapped to our card keys by fuzzy lookup; unmapped classes become ``unknown``.
Side (me/opp) comes from the health-bar colour above the box, falling back
to the arena half. Needs ``onnxruntime``. This wrapper reads the input shape
from the model, so other YOLOv5/8 exports with (1, N, 5+nc) or (1, 4+nc, N)
outputs work too.

Not validated inside the build environment (the weights could not be
downloaded there); treat the first run as a calibration run with
``advise`` and look at what it labels.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..cards import default_db
from ..state import Unit
from .layout import Layout
from .units import _side_from_healthbar


class OnnxYoloDetector:
    def __init__(self, weights: Path, classes: Path, conf: float = 0.4, iou: float = 0.45):
        import onnxruntime as ort  # optional dependency
        self.sess = ort.InferenceSession(str(weights), providers=["CPUExecutionProvider"])
        inp = self.sess.get_inputs()[0]
        self.input_name = inp.name
        shape = inp.shape
        self.in_h = int(shape[2]) if isinstance(shape[2], int) else 480
        self.in_w = int(shape[3]) if isinstance(shape[3], int) else 352
        self.conf = conf
        self.iou = iou
        self.names = [l.strip() for l in Path(classes).read_text(encoding="utf-8").splitlines() if l.strip()]
        db = default_db()
        self.keys = []
        for n in self.names:
            c = db.find(n) or (db.search(n.replace("_", " "), 1) or [None])[0]
            self.keys.append(c.key if c else "unknown")

    def _letterbox(self, img: np.ndarray) -> Tuple[np.ndarray, float, int, int]:
        h, w = img.shape[:2]
        r = min(self.in_h / h, self.in_w / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh))
        canvas = np.full((self.in_h, self.in_w, 3), 114, dtype=np.uint8)
        top, left = (self.in_h - nh) // 2, (self.in_w - nw) // 2
        canvas[top:top + nh, left:left + nw] = resized
        return canvas, r, left, top

    def detect(self, frame: np.ndarray, layout: Layout) -> List[Unit]:
        arena = layout.crop(frame, "arena")
        h, w = frame.shape[:2]
        ax0, ay0, _, _ = layout.pixels("arena", w, h)
        img, r, left, top = self._letterbox(arena)
        x = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None]
        out = self.sess.run(None, {self.input_name: x})[0]
        out = np.squeeze(out)
        if out.ndim != 2:
            return []
        if out.shape[0] < out.shape[1] and out.shape[0] in (4 + len(self.names), 5 + len(self.names)):
            out = out.T                                   # (4+nc, N) -> (N, 4+nc)
        boxes, scores, cls_ids = [], [], []
        has_obj = out.shape[1] == 5 + len(self.names)
        for row in out:
            cx, cy, bw, bh = row[:4]
            probs = row[5:] if has_obj else row[4:]
            obj = row[4] if has_obj else 1.0
            ci = int(np.argmax(probs))
            sc = float(obj * probs[ci])
            if sc < self.conf:
                continue
            boxes.append([float(cx - bw / 2), float(cy - bh / 2), float(bw), float(bh)])
            scores.append(sc)
            cls_ids.append(ci)
        if not boxes:
            return []
        keep = cv2.dnn.NMSBoxes(boxes, scores, self.conf, self.iou)
        units: List[Unit] = []
        for i in np.array(keep).flatten():
            bx, by, bw, bh = boxes[i]
            # back to arena pixels, then frame pixels
            x0 = (bx - left) / r + ax0
            y0 = (by - top) / r + ay0
            x1 = x0 + bw / r
            y1 = y0 + bh / r
            cxp, cyp = (x0 + x1) / 2, (y0 + y1) / 2
            tx, ty = layout.arena_to_tiles(frame.shape, cxp, cyp)
            side = _side_from_healthbar(frame, x0, y0, x1) or ("opp" if ty > 16 else "me")
            units.append(Unit(self.keys[cls_ids[i]], side, tx, ty, 1.0, id=f"onnx:{int(i)}"))
        return units
