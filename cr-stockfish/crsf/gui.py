"""Local web GUI: ``python -m crsf gui`` then open http://127.0.0.1:8765.

A small threaded HTTP server exposes the advisor as JSON and serves a
single-page dashboard (static/index.html): Stockfish-style eval bar, ranked
plays with reasons, arena minimap with units and the recommended tile, elixir
and cycle panels, matchup plan, autoplay controls and the command box.
The capture/decision loop runs in a background thread and can be started,
stopped and reconfigured from the page.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .advisor import Advisor
from .autoplay import AutoPlayer, AutoplayConfig
from .cards import default_db
from .matchup import plan_matchup

STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parent.parent


class DemoSource:
    """Synthetic frames so the GUI can be tried without a game running."""

    origin = (0, 0)

    def __init__(self):
        from .vision.layout import Layout
        from .vision.synth import CARD_STYLES, draw_card, make_frame
        from .vision.hand import CardMatcher
        self.layout = Layout.load()
        self.make_frame = make_frame
        self.keys = list(CARD_STYLES)
        self.matcher = CardMatcher()
        for k in self.keys:
            self.matcher.add(k, draw_card(80, 100, k))
        self.t0 = time.time()
        self.hand = ["hog_rider", "zap", "giant", "log"]
        self.next = "knight"

    def grab(self) -> np.ndarray:
        el = 10 * (0.5 + 0.5 * np.sin((time.time() - self.t0) / 9.0))
        return self.make_frame(self.layout, elixir=round(float(el), 1), hand=self.hand, next_card=self.next, desktop=100)

    def close(self) -> None:
        pass


class GuiApp:
    def __init__(self, templates: Path, unit_templates: Path, layout_path: Optional[Path] = None):
        self.db = default_db()
        self.templates = templates
        self.unit_templates = unit_templates
        self.layout_path = layout_path
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.advisor: Optional[Advisor] = None
        self.source = None
        self.actuator = None
        self.bot = AutoPlayer(AutoplayConfig())
        self.armed = False
        self.dry_run = True
        self.settings: Dict[str, Any] = {"source": "demo", "window": "Clash Royale", "monitor": 1, "emulator": "ldplayer", "input": "none", "fps": 4}
        self.snapshot: Dict[str, Any] = {"running": False, "status": "idle"}
        self.log: deque = deque(maxlen=200)
        self.fps_est = 0.0
        self.plan = None
        self.plan_text = ""

    # ----- lifecycle -----------------------------------------------------
    def logmsg(self, msg: str) -> None:
        self.log.appendleft({"t": time.strftime("%H:%M:%S"), "msg": msg})

    def start(self, settings: Dict[str, Any]) -> str:
        self.stop()
        self.settings.update({k: v for k, v in settings.items() if v is not None})
        s = self.settings
        from .vision.hand import CardMatcher
        from .vision.layout import Layout
        layout = Layout.load(self.layout_path)
        try:
            if s["source"] == "demo":
                self.source = DemoSource()
                matcher = self.source.matcher
                layout = self.source.layout
            else:
                matcher = CardMatcher(self.templates)
                if s["source"] == "window":
                    from .vision.capture import WindowSource
                    self.source = WindowSource(s["window"])
                elif s["source"] == "monitor":
                    from .vision.capture import ScreenSource
                    self.source = ScreenSource(monitor=int(s["monitor"]))
                else:  # emulator / adb
                    from .act.adb import AdbDevice, AdbSource, EMULATOR_PORTS
                    dev = AdbDevice()
                    emu = s.get("emulator", "ldplayer")
                    if emu in EMULATOR_PORTS:
                        dev.connect(f"127.0.0.1:{EMULATOR_PORTS[emu]}")
                    devs = [d for d in AdbDevice.devices() if len(d) > 1 and d[1] == "device"]
                    if not devs:
                        raise RuntimeError("no ADB device online")
                    dev.serial = dev.serial or devs[0][0]
                    self.source = AdbSource(dev)
                    self._adb = dev
            self.advisor = Advisor(layout=layout, matcher=matcher, unit_templates=self.unit_templates, use_ocr=None)
            self.actuator = self._make_actuator(layout)
        except Exception as exc:
            self.snapshot = {"running": False, "status": f"start failed: {exc}"}
            self.logmsg(f"start failed: {exc}")
            return f"start failed: {exc}"
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.logmsg(f"started ({s['source']}, input {s['input']}, {'dry run' if self.dry_run else 'LIVE'})")
        return "started"

    def _make_actuator(self, layout):
        from .act.adb import AdbActuator, MouseActuator
        inp = self.settings.get("input", "none")
        origin = getattr(self.source, "origin", (0, 0))
        if inp == "adb" and hasattr(self, "_adb"):
            return AdbActuator(self._adb, layout, dry_run=self.dry_run)
        if inp == "mouse":
            return MouseActuator(layout, origin=origin, dry_run=self.dry_run)
        if inp == "winmsg":
            from .act.winmsg import WindowMessageActuator
            return WindowMessageActuator(layout, self.settings.get("window", "Clash Royale"), origin=origin, dry_run=self.dry_run)
        return AdbActuator(None, layout, dry_run=True)       # "none": never clicks

    def stop(self) -> str:
        self.stop_flag.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        if self.source is not None:
            try:
                self.source.close()
            except Exception:
                pass
        self.source = None
        with self.lock:
            self.snapshot = {**self.snapshot, "running": False, "status": "stopped"}
        return "stopped"

    # ----- main loop ---------------------------------------------------------
    def _loop(self) -> None:
        period = 1.0 / max(0.5, float(self.settings.get("fps", 4)))
        last = time.time()
        while not self.stop_flag.is_set():
            t0 = time.time()
            try:
                raw = self.source.grab()
                st, an = self.advisor.step(raw, top_n=4)
                action = None
                if self.armed:
                    rec = self.bot.decide(st, an)
                    if rec is not None and rec.move.card in st.hand:
                        slot = st.hand.index(rec.move.card)
                        entry = self.actuator.play(slot, rec.move.x, rec.move.y, raw.shape, self.advisor.frame_bbox, label=rec.move.describe(self.db, st))
                        self.bot.record(rec, entry)
                        action = f"{'[dry] ' if self.dry_run else ''}played {rec.move.describe(self.db, st)} [{rec.score:+.1f}]"
                        self.logmsg(action)
                now = time.time()
                self.fps_est = 0.8 * self.fps_est + 0.2 * (1.0 / max(1e-3, now - last))
                last = now
                with self.lock:
                    self.snapshot = self._snapshot(st, an, raw.shape)
            except Exception as exc:
                self.logmsg(f"error: {exc}")
                traceback.print_exc()
                with self.lock:
                    self.snapshot = {**self.snapshot, "status": f"error: {exc}"}
                time.sleep(0.5)
            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)

    def _snapshot(self, st, an, shape) -> Dict[str, Any]:
        db = self.db
        name = lambda k: (db.get(k).name if k and db.find(k) else "?")
        rep = self.advisor.last_report
        recs = []
        for r in an.recommendations:
            recs.append({"text": r.move.describe(db, st), "card": r.move.card, "card_name": name(r.move.card) if r.move.card else "Wait",
                         "x": r.move.x, "y": r.move.y, "score": r.score, "reasons": r.reasons[:3], "wait": r.move.is_wait, "source": r.move.source})
        last = self.bot.history[-1] if self.bot.history else None
        return {
            "running": True, "status": "live" if self.armed and not self.dry_run else ("armed (dry run)" if self.armed else "advising"),
            "fps": round(self.fps_est, 1), "frame": self.advisor.frame_bbox, "capture": f"{shape[1]}x{shape[0]}",
            "time_left": int(st.time_left), "overtime": st.overtime, "phase": st.phase,
            "my_elixir": st.my_elixir, "opp_elixir": st.opp.elixir,
            "elixir_read": rep.elixir if rep else None,
            "hand": [{"key": k, "name": name(k), "cost": (db.get(k).cost if k and db.find(k) else 0),
                      "affordable": bool(k and db.find(k) and db.get(k).cost <= st.my_elixir)} for k in st.hand],
            "next": {"key": st.next_card, "name": name(st.next_card)} if st.next_card else None,
            "eval": an.eval, "eval_breakdown": an.eval_breakdown, "wait_score": an.wait_score,
            "recs": recs, "notes": an.notes,
            "threats": [{"name": name(u.card), "lane": u.lane, "x": u.x, "y": u.y, "w": round(w, 1), "hp": u.hp_frac} for u, w in an.threats],
            "units": [{"name": name(u.card), "side": u.side, "x": u.x, "y": u.y, "hp": u.hp_frac} for u in st.units],
            "towers": {k: {"hp": t.hp_or_max, "max": t.max_hp, "alive": t.alive} for k, t in st.towers.items()},
            "opp": {"known": [name(k) for k in st.opp.known_deck], "hand": [name(k) for k in st.opp.predicted_hand],
                    "out": [name(k) for k in st.opp.out_of_hand], "unknown": st.opp.unknown_slots},
            "my_deck": [name(k) for k in st.my_deck],
            "autoplay": {"armed": self.armed, "paused": self.bot.paused, "dry_run": self.dry_run, "plays": len(self.bot.history),
                         "last": (f"{name(last['card'])} ({int(time.time() - last['t'])}s ago)" if last else None),
                         "min_score": self.bot.config.min_score, "min_margin": self.bot.config.min_margin, "input": self.settings.get("input")},
            "classifier_classes": len(self.advisor.classifier.classes()),
            "counter": self.advisor.counter_panel(),
            "plan": self.plan_text, "plan_lines": (self.plan.summary_lines(db) if self.plan else []),
            "log": list(self.log)[:12],
        }

    # ----- commands / control -----------------------------------------------
    def command(self, line: str) -> str:
        if self.advisor is None:
            return "not running"
        op = line.strip().split(" ")[0].lower()
        msg = self.advisor.command(line)
        if op in ("d", "deck", "m", "mydeck", "o", "opp"):
            self._refresh_plan()
        return msg

    def _refresh_plan(self) -> None:
        adv = self.advisor
        opp = adv.opp.cycle.known_deck
        mine = adv.me.known_deck
        if len(opp) >= 4 and len(mine) >= 4:
            try:
                self.plan = plan_matchup(mine, opp, self.db, flags=adv.opp.flags)
                self.plan_text = self.plan.plan_text
            except Exception as exc:
                self.logmsg(f"matchup plan failed: {exc}")

    def control(self, req: Dict[str, Any]) -> Dict[str, Any]:
        act = req.get("action")
        if act == "start":
            self.dry_run = bool(req.get("dry_run", True))
            return {"msg": self.start(req.get("settings", {}))}
        if act == "stop":
            return {"msg": self.stop()}
        if act == "arm":
            self.armed = bool(req.get("armed", not self.armed))
            self.logmsg("autoplay ARMED" if self.armed else "autoplay disarmed")
            return {"msg": "armed" if self.armed else "disarmed"}
        if act == "pause":
            self.bot.paused = not self.bot.paused
            return {"msg": "paused" if self.bot.paused else "resumed"}
        if act == "settings":
            if "min_score" in req:
                self.bot.config.min_score = float(req["min_score"])
            if "min_margin" in req:
                self.bot.config.min_margin = float(req["min_margin"])
            if "dry_run" in req:
                self.dry_run = bool(req["dry_run"])
                if self.actuator is not None:
                    self.actuator.dry_run = self.dry_run
                    if not self.dry_run and self.advisor is not None:
                        try:
                            self.actuator = self._make_actuator(self.advisor.layout)
                        except Exception as exc:
                            self.dry_run = True
                            return {"msg": f"cannot go live: {exc}"}
            return {"msg": "ok"}
        if act == "plan":
            self._refresh_plan()
            return {"msg": self.plan.render(self.db) if self.plan else "need both decks (use d ... and m ...)"}
        return {"msg": f"unknown action {act}"}


def make_handler(app: GuiApp):
    cards = [{"key": c.key, "name": c.name, "cost": c.cost} for c in app.db if c.key != "unknown"]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):   # silence
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path.startswith("/api/state"):
                with app.lock:
                    snap = app.snapshot
                self._send(200, json.dumps(snap).encode())
            elif self.path.startswith("/api/cards"):
                self._send(200, json.dumps(cards).encode())
            else:
                self._send(404, b"{}")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path.startswith("/api/command"):
                self._send(200, json.dumps({"msg": app.command(body.get("line", ""))}).encode())
            elif self.path.startswith("/api/control"):
                self._send(200, json.dumps(app.control(body)).encode())
            else:
                self._send(404, b"{}")

    return H


def serve(app: GuiApp, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, autostart: Optional[Dict[str, Any]] = None) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(app))
    url = f"http://{host}:{port}/"
    print(f"CR Stockfish GUI at {url}", flush=True)
    if autostart:
        app.dry_run = bool(autostart.pop("dry_run", True))
        app.start(autostart)
    if open_browser:
        _open_app_window(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        server.server_close()


def _open_app_window(url: str) -> None:
    """Prefer a chromeless app window (Chrome/Edge --app=), else the default browser."""
    import shutil
    import subprocess
    for exe in ("chrome", "google-chrome", "msedge", "chromium", "chromium-browser",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        path = shutil.which(exe) or (exe if Path(exe).exists() else None)
        if path:
            try:
                subprocess.Popen([path, f"--app={url}", "--window-size=1180,820"])
                return
            except OSError:
                continue
    webbrowser.open(url)
