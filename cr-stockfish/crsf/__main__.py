"""Command-line entry point: ``python -m crsf <command>``."""
from __future__ import annotations

import argparse
import json
import os
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
UNIT_TEMPLATES = ROOT / "templates" / "units"
UNLABELED = ROOT / "templates" / "unlabeled"
EVENTS_DIR = ROOT / "data" / "events"
KNOWLEDGE_DIR = ROOT / "knowledge"


def _parse_bbox(s: Optional[str]):
    if not s:
        return None
    parts = [int(v) for v in s.replace("x", ",").split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be x,y,w,h")
    return tuple(parts)


def _adb_device(args):
    from .act.adb import AdbDevice, EMULATOR_PORTS
    dev = AdbDevice(serial=getattr(args, "serial", None))
    target = getattr(args, "connect", None)
    emu = getattr(args, "emulator", None)
    if not target and emu and emu != "phone":
        target = f"127.0.0.1:{EMULATOR_PORTS[emu]}"
    if target:
        print(dev.connect(target), file=sys.stderr)
    devs = [d for d in AdbDevice.devices() if len(d) > 1 and d[1] == "device"]
    if not devs:
        raise SystemExit("no ADB device online. Enable ADB in the emulator (or USB debugging on the phone) and run `adb devices`.")
    if dev.serial is None and len(devs) == 1:
        dev.serial = devs[0][0]
    print(f"using device {dev.serial or devs[0][0]} ({dev.wm_size()[0]}x{dev.wm_size()[1]})", file=sys.stderr)
    return dev


def _source(args):
    from .vision.capture import ImageSource, ScreenSource, WindowSource
    if getattr(args, "images", None):
        return ImageSource([Path(p) for p in args.images])
    if getattr(args, "adb", False) or getattr(args, "connect", None) or getattr(args, "emulator", None):
        from .act.adb import AdbSource
        args._device = _adb_device(args)
        return AdbSource(args._device)
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
    elif getattr(args, "onnx", None):
        from .vision.onnx_units import OnnxYoloDetector
        detector = OnnxYoloDetector(Path(args.onnx), Path(args.onnx_classes))
    adv = Advisor(layout=layout, matcher=matcher, detector=detector, auto_frame=not args.no_auto_frame,
                  use_ocr=None if not getattr(args, "no_ocr", False) else False,
                  unit_templates=Path(getattr(args, "unit_templates", UNIT_TEMPLATES)),
                  detect_units=not getattr(args, "no_units", False))
    if not len(matcher):
        adv.messages.append(f"no card templates in {args.templates}; hand reading disabled (run learn-cards)")
    from .knowledge import default_knowledge
    k = default_knowledge()
    adv.messages.append("knowledge loaded: " + (", ".join(k.loaded) if k.loaded else "none (duel model only)")
                        + f"; unit classifier knows {len(adv.classifier.classes())} units")
    return adv


def _save_events(adv: Advisor, path: Path) -> int:
    if not adv.events:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for ev in adv.events:
            fh.write(json.dumps(ev) + "\n")
    n = len(adv.events)
    adv.events.clear()
    return n


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


def cmd_play(args) -> int:
    """Autoplay: ADB frames in, engine decides, ADB taps out."""
    from .act.adb import AdbActuator, MouseActuator
    from .autoplay import AutoPlayer, AutoplayConfig
    if args.input == "adb":
        args.adb = True
    adv = _advisor(args)
    src = _source(args)
    if args.input == "adb":
        act = AdbActuator(args._device, adv.layout, dry_run=args.dry_run)
    else:
        act = MouseActuator(adv.layout, origin=getattr(src, "origin", (0, 0)), dry_run=args.dry_run)
        print("mouse input: the game window must stay visible and unobstructed; move the mouse to a screen corner to abort", file=sys.stderr)
    cfg = AutoplayConfig(min_score=args.min_score, urgent_score=args.urgent_score)
    bot = AutoPlayer(cfg)
    db = adv.db
    for m in adv.messages:
        print(m, file=sys.stderr)
    print(("DRY RUN: " if args.dry_run else "") + "autoplay armed. Commands: p pause/resume, o <card>, r reset, q quit", file=sys.stderr)
    if not args.dry_run:
        print("Reminder: automation violates Supercell's Terms of Service. Use a secondary account.", file=sys.stderr)
    events_path = EVENTS_DIR / f"play_{int(time.time())}.jsonl"
    frames = src.frames(fps=args.fps)

    def on_command(line: str) -> str:
        l = line.strip().lower()
        if l in ("p", "pause"):
            bot.paused = not bot.paused
            return "paused" if bot.paused else "resumed"
        if l in ("q", "quit"):
            raise KeyboardInterrupt
        return adv.command(line)

    def produce() -> Optional[str]:
        try:
            raw = next(frames)
        except StopIteration:
            return None
        st, an = adv.step(raw, top_n=args.top)
        rec = bot.decide(st, an)
        action = ""
        if rec is not None:
            slot = st.hand.index(rec.move.card)
            entry = act.play(slot, rec.move.x, rec.move.y, raw.shape, adv.frame_bbox, label=rec.move.describe(db, st))
            bot.record(rec, entry)
            action = f"PLAYED {rec.move.describe(db, st)} [{rec.score:+.1f}] via slot {slot + 1} -> px {entry['tile_px']}"
            print(action, file=sys.stderr, flush=True)
        txt = render_text(db, st, an, adv.last_report)
        status = "PAUSED" if bot.paused else ("DRY RUN" if args.dry_run else "AUTOPLAY ON")
        last = bot.history[-1] if bot.history else None
        tail = f"\nlast: {db.get(last['card']).name} @ {last['zone']} ({time.time() - last['t']:.0f}s ago)" if last else ""
        return f"[{status}] plays: {len(bot.history)}{tail}\n\n{txt}"

    try:
        if args.no_overlay:
            stop = threading.Event()

            def reader():
                for line in sys.stdin:
                    if stop.is_set():
                        break
                    try:
                        print("> " + on_command(line), flush=True)
                    except KeyboardInterrupt:
                        stop.set()
                        break
            threading.Thread(target=reader, daemon=True).start()
            while not stop.is_set():
                txt = produce()
                if txt is None:
                    break
                print("\033[2J\033[H" + txt, flush=True)
        else:
            from .overlay import Overlay
            Overlay(produce, on_command, title="CR Stockfish - autoplay").run()
    except KeyboardInterrupt:
        pass
    finally:
        n = _save_events(adv, events_path)
        src.close()
        print(f"{len(bot.history)} plays; {n} deploy events saved to {events_path}" if n else f"{len(bot.history)} plays", file=sys.stderr)
    return 0


def cmd_learn(args) -> int:
    """Watch gameplay (yours or a pro's video) and log deploy events."""
    adv = _advisor(args)
    src = _source(args)
    db = adv.db
    for m in adv.messages:
        print(m, file=sys.stderr)
    out = Path(args.out) if args.out else EVENTS_DIR / f"learn_{int(time.time())}.jsonl"
    print(f"learning: deploy events -> {out}. Type `o <card>` when the opponent plays so enemy units get labelled too.", file=sys.stderr)
    total = 0
    frames = src.frames(fps=args.fps)

    def produce() -> Optional[str]:
        nonlocal total
        try:
            raw = next(frames)
        except StopIteration:
            return None
        st, an = adv.step(raw, top_n=3)
        if len(adv.events) >= 10:
            total += _save_events(adv, out)
        recent = adv.events[-3:]
        lines = [f"events logged: {total + len(adv.events)}  | classifier classes: {len(adv.classifier.classes())}"]
        lines += [f"  {e['card']} @ ({e['x']}, {e['y']}) {e['lane']} [{e['phase']}, {e['side']}]" for e in recent]
        return "\n".join(lines) + "\n\n" + render_text(db, st, an, adv.last_report)

    try:
        if args.no_overlay:
            stop = threading.Event()
            threading.Thread(target=_stdin_commands, args=(adv, stop), daemon=True).start()
            while True:
                txt = produce()
                if txt is None:
                    break
                print("\033[2J\033[H" + txt, flush=True)
        else:
            from .overlay import Overlay
            Overlay(produce, adv.command, title="CR Stockfish - learning").run()
    except KeyboardInterrupt:
        pass
    finally:
        total += _save_events(adv, out)
        src.close()
    print(f"{total} deploy events in {out}. Build priors with: python -m crsf priors", file=sys.stderr)
    return 0


def cmd_priors(args) -> int:
    from .learn import build_priors, load_events
    paths = [Path(p) for p in (args.events or [EVENTS_DIR])]
    events = load_events(paths)
    data = build_priors(events, min_count=args.min_count)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    print(f"{len(events)} events -> priors for {len(data['cards'])} cards written to {out}")
    db = default_db()
    for card, e in sorted(data["cards"].items(), key=lambda kv: -kv[1]["n"])[:15]:
        sits = "; ".join(f"{s}: " + ", ".join(f"({c['x']:.0f},{c['y']:.0f})x{c['count']}" for c in v["clusters"][:3]) for s, v in e["situations"].items())
        print(f"  {db.get(card).name if db.find(card) else card:<18} n={e['n']:<4} {sits}")
    return 0


def cmd_simulate(args) -> int:
    from .sim_runner import simulate
    simulate(games=args.games, n_random=args.decks, procs=args.procs, seed=args.seed, out_dir=Path(args.out), scripted_share=args.scripted_share)
    return 0


def cmd_tune(args) -> int:
    from .sim_runner import tune, WEIGHTS_PATH
    out = Path(args.out) if args.out else WEIGHTS_PATH
    w = tune(iters=args.iters, candidates=args.candidates, pairs=args.pairs, procs=args.procs, seed=args.seed, out=out,
             log_path=Path(args.log) if args.log else None)
    print("final weights:", json.dumps(w.__dict__, indent=1))
    return 0


def cmd_matchup(args) -> int:
    from .matchup import plan_matchup
    db = default_db()
    def parse(txt):
        from .advisor import Advisor
        adv = Advisor(detect_units=False)
        return [adv._resolve(c) for c in txt.replace(";", ",").split(",") if c.strip()]
    mine, theirs = parse(args.my_deck), parse(args.opp_deck)
    plan = plan_matchup(mine, theirs, db)
    print(plan.render(db))
    return 0


def cmd_fetch_icons(args) -> int:
    from .icons import fetch_icons
    dest = Path(args.templates)
    print(f"downloading card icons into {dest} ...", flush=True)
    ok, failed = fetch_icons(dest)
    print(f"{len(ok)} icons ready, {len(failed)} failed")
    for k, why in list(failed.items())[:20]:
        print(f"  {k}: {why}")
    if failed:
        print("Failed cards can be labelled from your own hand with: python -m crsf learn-cards / label")
    return 0 if ok else 1


def cmd_go(args) -> int:
    """One command: find the game window, get icons, calibrate, open the dashboard."""
    import cv2
    from .gui import GuiApp, serve
    from .icons import fetch_icons
    from .vision.capture import find_game_frame, crop_game_frame
    from .vision.elixir import read_elixir
    from .vision.layout import Layout
    templates = Path(args.templates)
    have = len(list(templates.glob("*.png"))) if templates.exists() else 0
    if have < 20 and not args.no_icons:
        print("card icons: downloading official icons so your hand is recognised without labelling ...", flush=True)
        ok, failed = fetch_icons(templates)
        print(f"card icons: {len(ok)} ready, {len(failed)} failed", flush=True)
    source = "window"
    try:
        from .vision.capture import WindowSource
        src = WindowSource(args.window)
        raw = src.grab()
        src.close()
        bbox = find_game_frame(raw)
        frame = crop_game_frame(raw, bbox)
        el = read_elixir(frame, Layout.load())
        print(f"window '{args.window}': {raw.shape[1]}x{raw.shape[0]}, game frame {bbox}, elixir read {el}", flush=True)
        if el is None:
            print("  (no elixir bar seen: open a battle or Training Camp and the readings will start)", flush=True)
        cv2.imwrite(str(Path(args.out)), frame)
    except Exception as exc:
        print(f"window capture not available ({exc}); falling back to monitor 1", flush=True)
        source = "monitor"
    app = GuiApp(templates, Path(args.unit_templates), Path(args.layout) if args.layout else None)
    serve(app, host=args.host, port=args.port, open_browser=not args.no_browser,
          autostart={"source": source, "window": args.window, "monitor": 1, "input": args.input, "dry_run": not args.live})
    return 0


def cmd_gui(args) -> int:
    from .gui import GuiApp, serve
    app = GuiApp(Path(args.templates), Path(args.unit_templates), Path(args.layout) if args.layout else None)
    auto = None
    if args.demo:
        auto = {"source": "demo", "input": "none", "dry_run": True}
    serve(app, host=args.host, port=args.port, open_browser=not args.no_browser, autostart=auto)
    return 0


def cmd_bench(args) -> int:
    """Score the engine against benchmarks/puzzles.json."""
    db = default_db()
    eng = Engine(db)
    with open(args.file, "r", encoding="utf-8") as fh:
        puzzles = json.load(fh)["puzzles"]
    passed = 0
    for pz in puzzles:
        st = GameState.from_dict(pz["state"])
        an = eng.analyse(st, top_n=5)
        best = an.best
        ok = True
        why = []
        if pz.get("wait"):
            ok = best.move.is_wait
        else:
            if best.move.is_wait or best.move.card not in pz["accept"]:
                ok = False
                why.append(f"card {best.move.card}")
            if pz.get("lane") and best.move.lane != pz["lane"]:
                ok = False
                why.append(f"lane {best.move.lane}")
            if pz.get("lane_any") and best.move.lane not in pz["lane_any"]:
                ok = False
                why.append(f"lane {best.move.lane}")
            if pz.get("cls") and best.move.cls != pz["cls"]:
                ok = False
                why.append(f"cls {best.move.cls}")
            if pz.get("not_cls") and best.move.cls in pz["not_cls"]:
                ok = False
                why.append(f"cls {best.move.cls}")
            if pz.get("zone_prefix") and not (best.move.zone or "").startswith(pz["zone_prefix"]):
                ok = False
                why.append(f"zone {best.move.zone}")
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {pz['name']}")
        if not ok or args.verbose:
            for r in an.recommendations[:3]:
                print(f"        {r.text(db, st)}  {'; '.join(r.reasons[:2])}")
    print(f"\n{passed}/{len(puzzles)} puzzles solved ({100 * passed / len(puzzles):.0f}%)")
    return 0 if passed == len(puzzles) else 1


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
    p.add_argument("--adb", action="store_true", help="capture frames via ADB screencap instead of the screen")
    p.add_argument("--emulator", choices=["bluestacks", "ldplayer", "memu", "nox", "mumu", "phone"], help="connect to this emulator's default ADB port (implies --adb)")
    p.add_argument("--connect", help="adb connect to host:port (e.g. 127.0.0.1:5555 or a phone's Wi-Fi ADB address)")
    p.add_argument("--serial", help="ADB device serial when several are attached")
    p.add_argument("--unit-templates", default=str(UNIT_TEMPLATES), help="labelled unit crops directory")
    p.add_argument("--no-units", action="store_true", help="disable health-bar unit detection")
    p.add_argument("--onnx", help="YOLO ONNX unit detector weights (e.g. ClashRoyaleBuildABot units_M_480x352.onnx)")
    p.add_argument("--onnx-classes", help="class list for --onnx, one per line")


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

    p = sub.add_parser("play", help="AUTOPLAY over ADB: the engine plays the match for you (emulator or phone)")
    _add_capture_args(p)
    p.add_argument("--input", choices=["adb", "mouse"], default="adb", help="adb taps (emulator/phone) or mouse clicks on a window (Google Play Games, mirrored phone)")
    p.add_argument("--dry-run", action="store_true", help="decide and log, but never tap")
    p.add_argument("--min-score", type=float, default=0.6)
    p.add_argument("--urgent-score", type=float, default=2.5)
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--no-ocr", action="store_true")
    p.add_argument("--yolo")
    p.add_argument("--yolo-classes")
    p.set_defaults(fn=cmd_play)

    p = sub.add_parser("learn", help="log deploy events from gameplay on screen (yours or a pro's video)")
    _add_capture_args(p)
    p.add_argument("--out", help="events JSONL (default data/events/learn_<ts>.jsonl)")
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--no-ocr", action="store_true")
    p.set_defaults(fn=cmd_learn)

    p = sub.add_parser("priors", help="aggregate logged events into knowledge/priors.json")
    p.add_argument("events", nargs="*", help="event files or directories (default data/events)")
    p.add_argument("--out", default=str(KNOWLEDGE_DIR / "priors.json"))
    p.add_argument("--min-count", type=int, default=2)
    p.set_defaults(fn=cmd_priors)

    p = sub.add_parser("simulate", help="self-play tournament over a deck pool; writes reports/simulation_report.md")
    p.add_argument("--games", type=int, default=10000)
    p.add_argument("--decks", type=int, default=200, help="generated decks added to the meta decks")
    p.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2)))
    p.add_argument("--seed", type=int, default=3)
    p.add_argument("--out", default=str(ROOT / "reports"))
    p.add_argument("--scripted-share", type=float, default=0.05, help="fraction of games played against the scripted bot (sanity check)")
    p.set_defaults(fn=cmd_simulate)

    p = sub.add_parser("tune", help="evolve engine weights by self-play (gated by the puzzle benchmark)")
    p.add_argument("--iters", type=int, default=6)
    p.add_argument("--candidates", type=int, default=6)
    p.add_argument("--pairs", type=int, default=30)
    p.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2)))
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", help="weights JSON (default knowledge/weights.json)")
    p.add_argument("--log", help="write the tuning log JSON here")
    p.set_defaults(fn=cmd_tune)

    p = sub.add_parser("matchup", help="plan how to counter a deck with your deck")
    p.add_argument("my_deck", help="comma-separated card names")
    p.add_argument("opp_deck", help="comma-separated card names")
    p.set_defaults(fn=cmd_matchup)

    p = sub.add_parser("go", help="ONE command: find the Clash Royale window, fetch card icons, calibrate, open the dashboard")
    p.add_argument("--window", default="Clash Royale")
    p.add_argument("--input", choices=["none", "winmsg", "mouse", "adb"], default="winmsg")
    p.add_argument("--live", action="store_true", help="start with dry run OFF (clicks for real)")
    p.add_argument("--no-icons", action="store_true")
    p.add_argument("--out", default="calibration_frame.png")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--layout")
    p.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    p.add_argument("--unit-templates", default=str(UNIT_TEMPLATES))
    p.set_defaults(fn=cmd_go)

    p = sub.add_parser("fetch-icons", help="download official card icons as hand templates (no manual labelling)")
    p.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    p.set_defaults(fn=cmd_fetch_icons)

    p = sub.add_parser("gui", help="desktop dashboard in a browser app window (advise + autoplay controls)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--demo", action="store_true", help="start immediately on synthetic frames")
    p.add_argument("--layout")
    p.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    p.add_argument("--unit-templates", default=str(UNIT_TEMPLATES))
    p.set_defaults(fn=cmd_gui)

    p = sub.add_parser("bench", help="score the engine on benchmarks/puzzles.json")
    p.add_argument("--file", default=str(ROOT / "benchmarks" / "puzzles.json"))
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_bench)

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
