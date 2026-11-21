"""Command-line entry point: ``python -m crsf <command>``."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from .advisor import Advisor, render_text
from .cards import default_db
from .engine import Engine
from .state import GameState

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES = ROOT / "templates" / "cards"
UNLABELED = ROOT / "templates" / "unlabeled"


def _parse_bbox(s: Optional[str]):
    if not s:
        return None
    parts = [int(v) for v in s.replace("x", ",").split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be x,y,w,h")
    return tuple(parts)


def _source(args):
    from .vision.capture import ImageSource, ScreenSource, WindowSource
    if getattr(args, "images", None):
        return ImageSource([Path(p) for p in args.images])
    if getattr(args, "window", None):
        return WindowSource(args.window)
    return ScreenSource(monitor=args.monitor, bbox=_parse_bbox(args.bbox))


def _advisor(args) -> Advisor:
    from .vision.hand import CardMatcher
    from .vision.layout import Layout
    layout = Layout.load(Path(args.layout) if args.layout else None)
    matcher = CardMatcher(Path(args.templates))
    detector = None
    if getattr(args, "yolo", None):
        from .vision.units import YoloDetector
        detector = YoloDetector(Path(args.yolo), Path(args.yolo_classes))
    adv = Advisor(layout=layout, matcher=matcher, detector=detector, auto_frame=not args.no_auto_frame,
                  use_ocr=None if not args.no_ocr else False)
    if not len(matcher):
        adv.messages.append(f"no card templates in {args.templates}; hand reading disabled (run learn-cards)")
    return adv


# --------------------------------------------------------------------------

def cmd_analyze(args) -> int:
    db = default_db()
    with open(args.state, "r", encoding="utf-8") as fh:
        st = GameState.from_dict(json.load(fh))
    an = Engine(db).analyse(st, top_n=args.top)
    if args.json:
        out = {
            "eval": an.eval, "eval_breakdown": an.eval_breakdown,
            "recommendations": [
                {"card": r.move.card, "zone": r.move.zone, "x": r.move.x, "y": r.move.y, "score": r.score,
                 "reasons": r.reasons, "components": r.components, "text": r.move.describe(db, st)}
                for r in an.recommendations
            ],
            "notes": an.notes,
        }
        print(json.dumps(out, indent=2))
    else:
        print(render_text(db, st, an))
    return 0


def cmd_cards(args) -> int:
    db = default_db()
    cards = db.search(args.query, limit=200) if args.query else list(db)
    for c in sorted(cards, key=lambda c: (c.cost, c.name)):
        roles = ",".join(c.roles)
        print(f"{c.cost}  {c.key:<20} {c.name:<22} {c.kind:<8} {c.targets:<9} hp={c.hp:<5.0f} dmg={c.damage:<5.0f} {roles}")
    print(f"{len(cards)} cards")
    return 0


def _stdin_commands(adv: Advisor, stop: threading.Event) -> None:
    for line in sys.stdin:
        if stop.is_set():
            break
        msg = adv.command(line)
        if msg:
            print(f"> {msg}", flush=True)


def cmd_advise(args) -> int:
    adv = _advisor(args)
    src = _source(args)
    db = adv.db
    for m in adv.messages:
        print(m, file=sys.stderr)
    if adv.use_ocr:
        print("tesseract found: tower HP and clock will be read", file=sys.stderr)
    else:
        print("tesseract not found: using wall-clock timer, towers assumed full (type `t 2:30` to set the clock)", file=sys.stderr)
    record_dir = Path(args.record) if args.record else None
    if record_dir:
        record_dir.mkdir(parents=True, exist_ok=True)
    frames = src.frames(fps=args.fps)
    counter = {"n": 0}

    def produce() -> Optional[str]:
        try:
            raw = next(frames)
        except StopIteration:
            return None
        st, an = adv.step(raw, top_n=args.top)
        counter["n"] += 1
        if record_dir and counter["n"] % max(1, int(args.fps)) == 0:
            import cv2
            cv2.imwrite(str(record_dir / f"frame_{int(time.time() * 1000)}.png"), raw)
        return render_text(db, st, an, adv.last_report)

    if args.no_overlay:
        stop = threading.Event()
        threading.Thread(target=_stdin_commands, args=(adv, stop), daemon=True).start()
        try:
            while True:
                txt = produce()
                if txt is None:
                    break
                print("\033[2J\033[H" + txt, flush=True)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            src.close()
        return 0
    from .overlay import Overlay
    ov = Overlay(produce, adv.command)
    try:
        ov.run()
    finally:
        src.close()
    return 0


def cmd_replay(args) -> int:
    adv = _advisor(args)
    from .vision.capture import ImageSource
    src = ImageSource([Path(p) for p in args.images])
    db = adv.db
    for cmd in args.command or []:
        print("> " + adv.command(cmd))
    for raw in src.frames():
        st, an = adv.step(raw, top_n=args.top)
        rep = adv.last_report
        print(f"=== {src.current.name}  frame={rep.frame_bbox}  elixir={rep.elixir}  clock={rep.clock}")
        if rep.hand:
            print("    slots: " + " | ".join(f"{k or '?'}({c:.2f}{' grey' if g else ''})" for k, c, g in rep.hand))
        if rep.towers:
            print("    towers: " + ", ".join(f"{k}={v}" for k, v in rep.towers.items() if v is not None))
        print(render_text(db, st, an, rep))
        print()
    return 0


def cmd_calibrate(args) -> int:
    import cv2
    from .vision.capture import ImageSource, crop_game_frame, find_game_frame
    from .vision.layout import Layout
    layout = Layout.load(Path(args.layout) if args.layout else None)
    if args.image:
        raw = cv2.imread(args.image)
        if raw is None:
            print(f"could not read {args.image}", file=sys.stderr)
            return 1
    else:
        src = _source(args)
        raw = src.grab()
        src.close()
    bbox = find_game_frame(raw) if not args.no_auto_frame else (0, 0, raw.shape[1], raw.shape[0])
    frame = crop_game_frame(raw, bbox)
    h, w = frame.shape[:2]
    vis = frame.copy()
    for name in layout.regions:
        x0, y0, x1, y1 = layout.pixels(name, w, h)
        color = (0, 255, 0) if name.startswith("hand") else (255, 200, 0) if "hp" in name else (0, 200, 255)
        cv2.rectangle(vis, (x0, y0), (x1, y1), color, 2)
        cv2.putText(vis, name, (x0 + 2, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    out = Path(args.out)
    cv2.imwrite(str(out), vis)
    raw_out = out.with_name(out.stem + "_raw.png")
    cv2.imwrite(str(raw_out), raw)
    from .vision.elixir import read_elixir
    print(f"capture size {raw.shape[1]}x{raw.shape[0]}, detected game frame x={bbox[0]} y={bbox[1]} w={bbox[2]} h={bbox[3]}")
    print(f"elixir read: {read_elixir(frame, layout)}")
    print(f"preview written to {out} (raw capture: {raw_out})")
    print("If boxes are off, copy crsf/data/layout.json, edit the fractions, and pass --layout <file>.")
    print(f"If the frame is wrong, pass --bbox {bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]} adjusted, plus --no-auto-frame.")
    return 0


def cmd_learn_cards(args) -> int:
    """Save hand-slot crops so you can label them as templates."""
    import cv2
    from .vision.capture import crop_game_frame, find_game_frame
    from .vision.layout import HAND_SLOTS, Layout
    from .vision.hand import CardMatcher
    layout = Layout.load(Path(args.layout) if args.layout else None)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    matcher = CardMatcher(Path(args.templates))
    src = _source(args)
    saved = 0
    last = [None] * 5
    try:
        for raw in src.frames(fps=args.fps):
            bbox = find_game_frame(raw) if not args.no_auto_frame else None
            frame = crop_game_frame(raw, bbox)
            names = list(HAND_SLOTS) + (["next_card"] if layout.has("next_card") else [])
            for i, name in enumerate(names):
                crop = layout.crop(frame, name)
                if crop.size == 0:
                    continue
                key, conf = matcher.identify(crop)
                if key is not None and conf >= args.known_conf:
                    continue                      # already have a template for this
                small = cv2.resize(crop, (24, 30))
                if last[i] is not None and cv2.norm(small, last[i], cv2.NORM_L1) / small.size < 12:
                    continue                      # same unknown card as last time
                last[i] = small
                fname = out / f"slot{i + 1}_{int(time.time() * 1000)}.png"
                cv2.imwrite(str(fname), crop)
                saved += 1
                print(f"saved {fname.name} (best guess {key or '-'} {conf:.2f})", flush=True)
            if args.once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        src.close()
    print(f"{saved} crops saved to {out}. Label them with: python -m crsf label <file> <card_key>")
    return 0


def cmd_label(args) -> int:
    db = default_db()
    card = db.get(args.card)
    dst_dir = Path(args.templates)
    dst_dir.mkdir(parents=True, exist_ok=True)
    src = Path(args.file)
    dst = dst_dir / f"{card.key}.png"
    if dst.exists() and not args.force:
        print(f"{dst} exists (use --force to replace)")
        return 1
    src.replace(dst)
    print(f"{src.name} -> {dst}")
    return 0


# --------------------------------------------------------------------------

def _add_capture_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--monitor", type=int, default=1, help="monitor index for mss (1 = primary)")
    p.add_argument("--bbox", help="x,y,w,h region on that monitor to capture")
    p.add_argument("--window", help="capture the window whose title contains this text (needs pygetwindow)")
    p.add_argument("--no-auto-frame", action="store_true", help="don't auto-detect the 9:16 game frame")
    p.add_argument("--layout", help="layout JSON (default: crsf/data/layout.json)")
    p.add_argument("--templates", default=str(DEFAULT_TEMPLATES), help="card template directory")
    p.add_argument("--fps", type=float, default=4.0)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="crsf", description="Clash Royale Stockfish: analysis engine + live advisor")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("analyze", help="analyse a game state JSON file")
    p.add_argument("state")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("cards", help="list / search the card database")
    p.add_argument("query", nargs="?")
    p.set_defaults(fn=cmd_cards)

    p = sub.add_parser("advise", help="live advisor (screen capture + overlay)")
    _add_capture_args(p)
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--no-overlay", action="store_true", help="print to the terminal instead of a Tk window")
    p.add_argument("--no-ocr", action="store_true", help="skip Tesseract even if installed")
    p.add_argument("--record", help="save a frame per second to this directory (for labelling / replay)")
    p.add_argument("--yolo", help="Ultralytics YOLO weights for unit detection")
    p.add_argument("--yolo-classes", help="class map JSON for --yolo")
    p.set_defaults(fn=cmd_advise)

    p = sub.add_parser("replay", help="run the pipeline over saved screenshots")
    p.add_argument("images", nargs="+")
    _add_capture_args(p)
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--no-ocr", action="store_true")
    p.add_argument("--yolo")
    p.add_argument("--yolo-classes")
    p.add_argument("--command", "-c", action="append", help="advisor command to run first (e.g. -c 'd hog,musk,...')")
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("calibrate", help="draw the HUD layout over a screenshot")
    _add_capture_args(p)
    p.add_argument("--image", help="use this screenshot instead of capturing")
    p.add_argument("--out", default="calibration_preview.png")
    p.set_defaults(fn=cmd_calibrate)

    p = sub.add_parser("learn-cards", help="save unknown hand-slot crops for labelling")
    _add_capture_args(p)
    p.add_argument("--images", nargs="*", help="use screenshots instead of live capture")
    p.add_argument("--out", default=str(UNLABELED))
    p.add_argument("--once", action="store_true", help="process a single frame")
    p.add_argument("--known-conf", type=float, default=0.75)
    p.set_defaults(fn=cmd_learn_cards)

    p = sub.add_parser("label", help="turn a saved crop into a card template")
    p.add_argument("file")
    p.add_argument("card")
    p.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_label)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
