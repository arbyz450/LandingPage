"""Android bridge for CR Stockfish (called from Kotlin through Chaquopy).

Every function returns a JSON string and never raises: Kotlin only has to
parse ``{"error": ...}`` when something goes wrong. The engine, vision and
autoplay policy are the same modules the PC app uses (``crsf`` is bundled
into the APK by the Gradle ``syncCrsf`` task).
"""
from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

import numpy as np

_S = {"adv": None, "bot": None, "layout": None, "last_bgr": None, "last_shape": None, "screen": (1080, 2400), "log": []}


def _err(exc: BaseException) -> str:
    _S["log"].append(traceback.format_exc()[-800:])
    return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def _to_bgr(buf, w: int, h: int, row_stride: int) -> np.ndarray:
    import cv2
    try:
        arr = np.frombuffer(buf, dtype=np.uint8)
    except (TypeError, ValueError):
        arr = np.frombuffer(bytes(buf), dtype=np.uint8)
    stride = row_stride if row_stride and row_stride >= w * 4 else w * 4
    arr = arr[: stride * h].reshape(h, stride // 4, 4)[:, :w, :]
    return cv2.cvtColor(np.ascontiguousarray(arr), cv2.COLOR_RGBA2BGR)


def init(templates_dir: str, unit_templates_dir: str = "", layout_json_path: str = "", screen_w: int = 1080, screen_h: int = 2400) -> str:
    try:
        from crsf.advisor import Advisor
        from crsf.autoplay import AutoPlayer, AutoplayConfig
        from crsf.vision.hand import CardMatcher
        from crsf.vision.layout import Layout
        layout = Layout.load(Path(layout_json_path)) if layout_json_path and os.path.exists(layout_json_path) else Layout.load()
        Path(templates_dir).mkdir(parents=True, exist_ok=True)
        matcher = CardMatcher(Path(templates_dir))
        adv = Advisor(layout=layout, matcher=matcher, unit_templates=Path(unit_templates_dir) if unit_templates_dir else None,
                      detect_units=True, use_ocr=False, auto_frame=True)
        adv.matcher = matcher          # an empty matcher is falsy; make sure ours (with its save dir) is used
        _S.update(adv=adv, bot=AutoPlayer(AutoplayConfig()), layout=layout, screen=(int(screen_w), int(screen_h)))
        from crsf.knowledge import default_knowledge
        k = default_knowledge()
        return json.dumps({"ok": True, "templates": len(matcher), "knowledge": k.loaded, "cards": len(adv.db)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def set_config(min_score: float = 0.6, min_margin: float = 1.2, screen_w: int = 0, screen_h: int = 0) -> str:
    try:
        bot = _S["bot"]
        if bot is not None:
            bot.config.min_score = float(min_score)
            bot.config.min_margin = float(min_margin)
        if screen_w and screen_h:
            _S["screen"] = (int(screen_w), int(screen_h))
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def step(buf, w: int, h: int, row_stride: int = 0, armed: bool = False) -> str:
    """One captured frame in (RGBA), decision out.

    ``buf`` is the downscaled capture (w x h); device-pixel coordinates in the
    result are scaled back up to the real screen size given at init().
    """
    adv, bot = _S["adv"], _S["bot"]
    if adv is None:
        return json.dumps({"error": "not initialised"})
    try:
        from crsf.advisor import render_text
        bgr = _to_bgr(buf, int(w), int(h), int(row_stride))
        _S["last_bgr"], _S["last_shape"] = bgr, bgr.shape
        st, an = adv.step(bgr, top_n=3)
        sw, sh = _S["screen"]
        sx, sy = sw / float(w), sh / float(h)
        out = {
            "text": render_text(adv.db, st, an, adv.last_report),
            "eval": an.eval, "wait_score": an.wait_score,
            "my_elixir": st.my_elixir, "opp_elixir": st.opp.elixir,
            "hand": [k or "" for k in st.hand],
            "frame": list(adv.frame_bbox) if adv.frame_bbox else None,
            "recs": [{"text": r.move.describe(adv.db, st), "score": r.score, "card": r.move.card, "x": r.move.x, "y": r.move.y}
                     for r in an.recommendations],
            "play": None,
        }
        rec = bot.decide(st, an) if armed else None
        if rec is not None and rec.move.card in st.hand:
            slot = st.hand.index(rec.move.card)
            fb = adv.frame_bbox or (0, 0, bgr.shape[1], bgr.shape[0])
            fx, fy, fw, fh = fb
            from crsf.vision.layout import HAND_SLOTS
            x0, y0, x1, y1 = adv.layout.pixels(HAND_SLOTS[slot], fw, fh)
            px, py = adv.layout.tiles_to_pixel((fh, fw), rec.move.x, rec.move.y)
            play = {
                "card": rec.move.card, "slot": slot, "x": rec.move.x, "y": rec.move.y, "score": rec.score,
                "slot_px": int((fx + (x0 + x1) / 2) * sx), "slot_py": int((fy + (y0 + y1) / 2) * sy),
                "px": int((fx + px) * sx), "py": int((fy + py) * sy),
                "text": rec.move.describe(adv.db, st),
            }
            bot.record(rec, {"tile_px": (play["px"], play["py"])})
            out["play"] = play
        return json.dumps(out)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def command(line: str) -> str:
    adv = _S["adv"]
    if adv is None:
        return "not initialised"
    try:
        return adv.command(str(line))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def label_slot(slot: int, card_key: str) -> str:
    """Teach the card matcher from the last frame: save hand slot ``slot`` (0-3, 4 = next) as ``card_key``."""
    adv, bgr = _S["adv"], _S["last_bgr"]
    if adv is None or bgr is None:
        return json.dumps({"error": "no frame yet"})
    try:
        import cv2
        from crsf.vision.capture import crop_game_frame
        from crsf.vision.layout import HAND_SLOTS
        card = adv.db.get(card_key)
        frame = crop_game_frame(bgr, adv.frame_bbox) if adv.frame_bbox else bgr
        name = HAND_SLOTS[slot] if 0 <= slot < 4 else "next_card"
        crop = adv.layout.crop(frame, name)
        d = adv.matcher.dir or Path(".")
        d.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(d / f"{card.key}.png"), crop)
        adv.matcher.add(card.key, crop)
        return json.dumps({"ok": True, "card": card.key, "templates": len(adv.matcher)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def pause(flag: bool) -> str:
    bot = _S["bot"]
    if bot is not None:
        bot.paused = bool(flag)
    return json.dumps({"ok": True, "paused": bool(flag)})


def debug_log() -> str:
    return "\n---\n".join(_S["log"][-5:])
