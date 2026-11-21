"""The live advisor: frames in, ranked recommendations out.

``Advisor.step(frame)`` reads the HUD, updates the trackers, builds a
GameState and runs the engine. Opponent plays (and anything vision cannot
see yet) are fed through ``Advisor.command`` using short text commands, from
the overlay's input box or the terminal:

    o <card>      opponent played <card>         (e.g. "o hog", "o musk")
    u             undo the last opponent play
    d <c1,c2,..>  set the opponent's known deck
    m <c1,c2,..>  set my deck (enables "cycle toward win condition" advice)
    e <n>         force the opponent's elixir estimate to n
    r             reset for a new match
    t <m:ss>      set the match clock (when OCR is unavailable)
    x <card> [me|opp] [left|right|center] [y]
                  place a unit manually on the board (for engine testing)
    c             clear manual units
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .cards import CardDB, default_db
from .engine import Analysis, Engine
from .state import GameState, Tower, Unit, default_towers, KING_TOWER_HP, PRINCESS_TOWER_HP
from .tracker import CycleTracker, OpponentTracker
from .vision.capture import crop_game_frame, find_game_frame
from .vision.elixir import read_elixir
from .vision.hand import CardMatcher, read_hand
from .vision.layout import TOWER_REGIONS, Layout
from .vision.ocr import has_tesseract, read_clock, read_digits
from .vision.units import NullDetector, UnitDetector

REGULATION = 180
OVERTIME = 120


@dataclass
class MatchClock:
    """Keeps the match clock, from OCR when available, else wall time."""

    started_at: Optional[float] = None
    ocr_time_left: Optional[int] = None
    ocr_at: float = 0.0
    overtime: bool = False

    def start(self) -> None:
        self.started_at = time.time()
        self.ocr_time_left = None
        self.overtime = False

    def set_ocr(self, time_left: int) -> None:
        # The clock jumping *up* means overtime started (or a new match).
        if self.ocr_time_left is not None and time_left > self.ocr_time_left + 20:
            if self.ocr_time_left <= 5:
                self.overtime = True
            else:
                self.started_at = time.time()
                self.overtime = False
        self.ocr_time_left = time_left
        self.ocr_at = time.time()
        if self.started_at is None:
            self.started_at = time.time() - (REGULATION - time_left)

    def set_manual(self, time_left: int, overtime: bool = False) -> None:
        self.overtime = overtime
        total = OVERTIME if overtime else REGULATION
        self.started_at = time.time() - (total - time_left)
        self.ocr_time_left = None

    def time_left(self) -> float:
        if self.ocr_time_left is not None and time.time() - self.ocr_at < 5:
            return float(self.ocr_time_left)
        if self.started_at is None:
            return float(REGULATION)
        elapsed = time.time() - self.started_at
        if not self.overtime:
            if elapsed <= REGULATION:
                return REGULATION - elapsed
            self.overtime = True
            self.started_at = time.time()
            return float(OVERTIME)
        return max(0.0, OVERTIME - elapsed)

    def elapsed(self) -> float:
        """Seconds since match start (overtime continues counting)."""
        if self.started_at is None:
            return 0.0
        base = REGULATION if self.overtime else 0.0
        return base + (time.time() - self.started_at)


@dataclass
class VisionReport:
    elixir: Optional[float] = None
    hand: List[Tuple[Optional[str], float, bool]] = field(default_factory=list)
    next_card: Tuple[Optional[str], float] = (None, 0.0)
    towers: dict = field(default_factory=dict)
    clock: Optional[int] = None
    frame_bbox: Optional[Tuple[int, int, int, int]] = None


class Advisor:
    def __init__(
        self,
        db: Optional[CardDB] = None,
        layout: Optional[Layout] = None,
        matcher: Optional[CardMatcher] = None,
        detector: Optional[UnitDetector] = None,
        engine: Optional[Engine] = None,
        auto_frame: bool = True,
        use_ocr: Optional[bool] = None,
    ):
        self.db = db or default_db()
        self.layout = layout or Layout.load()
        self.matcher = matcher or CardMatcher()
        self.detector = detector or NullDetector()
        self.engine = engine or Engine(self.db)
        self.auto_frame = auto_frame
        self.use_ocr = has_tesseract() if use_ocr is None else use_ocr
        self.opp = OpponentTracker(self.db)
        self.me = CycleTracker()
        self.clock = MatchClock()
        self.manual_units: List[Unit] = []
        self.last_hand: List[Optional[str]] = [None] * 4
        self.last_state: Optional[GameState] = None
        self.last_report: Optional[VisionReport] = None
        self.frame_bbox: Optional[Tuple[int, int, int, int]] = None
        self.messages: List[str] = []

    # ----- vision ---------------------------------------------------------
    def read(self, raw: np.ndarray) -> Tuple[np.ndarray, VisionReport]:
        if self.auto_frame:
            if self.frame_bbox is None:
                self.frame_bbox = find_game_frame(raw)
            frame = crop_game_frame(raw, self.frame_bbox)
        else:
            frame = raw
        rep = VisionReport(frame_bbox=self.frame_bbox)
        rep.elixir = read_elixir(frame, self.layout)
        if len(self.matcher):
            rep.hand, rep.next_card = read_hand(frame, self.layout, self.matcher)
        if self.use_ocr:
            if self.layout.has("clock"):
                rep.clock = read_clock(self.layout.crop(frame, "clock"))
            for tower, region in TOWER_REGIONS.items():
                if self.layout.has(region):
                    rep.towers[tower] = read_digits(self.layout.crop(frame, region))
        return frame, rep

    # ----- state assembly -------------------------------------------------
    def build_state(self, frame: np.ndarray, rep: VisionReport) -> GameState:
        if rep.clock is not None:
            self.clock.set_ocr(rep.clock)
        elif self.clock.started_at is None and rep.elixir is not None:
            self.clock.start()                       # first frame with a HUD = match start
        st = GameState()
        st.time_left = self.clock.time_left()
        st.overtime = self.clock.overtime
        st.my_elixir = rep.elixir if rep.elixir is not None else (self.last_state.my_elixir if self.last_state else 5.0)

        hand: List[str] = []
        for i in range(4):
            key = rep.hand[i][0] if i < len(rep.hand) else None
            if key is None and self.last_state and i < len(self.last_state.hand):
                key = self.last_state.hand[i]       # keep the last confident read
            hand.append(key or "")
        # Detect my own plays: a slot changing to a new card means the old one was played.
        for i in range(4):
            old = self.last_hand[i]
            new = hand[i] or None
            if old and new and old != new and old not in hand:
                self.me.record_play(old, self.clock.elapsed())
            self.last_hand[i] = new
        for k in hand:
            if k and k not in self.me.known_deck:
                self.me.known_deck.append(k)
        if rep.next_card[0] and rep.next_card[0] not in self.me.known_deck:
            self.me.known_deck.append(rep.next_card[0])
        st.hand = hand
        st.next_card = rep.next_card[0]
        st.my_deck = list(self.me.known_deck)

        self.opp.tick(self.clock.elapsed(), st.seconds_per_elixir)
        st.opp = self.opp.info()

        towers = default_towers()
        for name, hp in rep.towers.items():
            if hp is not None and 0 < hp <= towers[name].max_hp:
                towers[name].hp = float(hp)
            elif self.last_state is not None:
                towers[name] = self.last_state.towers[name]
        st.towers = towers

        units = list(self.detector.detect(frame, self.layout))
        units += self.manual_units
        st.units = units
        self.last_state = st
        self.last_report = rep
        return st

    def step(self, raw: np.ndarray, top_n: int = 5) -> Tuple[GameState, Analysis]:
        frame, rep = self.read(raw)
        st = self.build_state(frame, rep)
        return st, self.engine.analyse(st, top_n=top_n)

    # ----- commands -------------------------------------------------------
    def command(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        op, _, rest = line.partition(" ")
        op = op.lower()
        rest = rest.strip()
        try:
            if op in ("o", "opp"):
                card = self._resolve(rest)
                self.opp.record_play(card, self.clock.elapsed())
                return f"opponent played {self.db.get(card).name} (elixir ~{self.opp.elixir.elixir:.1f})"
            if op in ("u", "undo"):
                c = self.opp.undo_last()
                return f"undid {self.db.get(c).name}" if c else "nothing to undo"
            if op in ("d", "deck"):
                deck = [self._resolve(c) for c in rest.replace(";", ",").split(",") if c.strip()]
                self.opp.cycle.set_deck(deck)
                return f"opponent deck set ({len(deck)} cards)"
            if op in ("m", "mydeck"):
                deck = [self._resolve(c) for c in rest.replace(";", ",").split(",") if c.strip()]
                self.me.set_deck(deck)
                return f"my deck set ({len(deck)} cards)"
            if op in ("e", "elixir"):
                self.opp.elixir.elixir = max(0.0, min(10.0, float(rest)))
                return f"opponent elixir set to {self.opp.elixir.elixir:.1f}"
            if op in ("r", "reset"):
                self.opp.reset()
                self.me.reset()
                self.clock.start()
                self.manual_units.clear()
                self.last_state = None
                self.last_hand = [None] * 4
                self.frame_bbox = None
                return "reset for a new match"
            if op in ("t", "time"):
                mm, _, ss = rest.partition(":")
                ot = "ot" in line.lower()
                self.clock.set_manual(int(mm) * 60 + int(ss or 0), overtime=ot)
                return f"clock set to {rest}"
            if op in ("x", "unit"):
                parts = rest.split()
                card = self._resolve(parts[0])
                side = parts[1] if len(parts) > 1 and parts[1] in ("me", "opp") else "opp"
                lane = next((p for p in parts if p in ("left", "right", "center")), "left")
                x = {"left": 3.5, "right": 14.5, "center": 9.0}[lane]
                y = float(parts[-1]) if parts[-1].replace(".", "", 1).isdigit() else (13.0 if side == "opp" else 15.0)
                self.manual_units.append(Unit(card, side, x, y))
                return f"placed {self.db.get(card).name} ({side}, {lane}, y={y:g})"
            if op in ("c", "clear"):
                self.manual_units.clear()
                return "manual units cleared"
            if op in ("h", "help", "?"):
                return __doc__.split("commands:", 1)[-1] if "commands:" in __doc__ else __doc__
        except (KeyError, ValueError, IndexError) as exc:
            return f"error: {exc}"
        return f"unknown command: {op}"

    def _resolve(self, text: str) -> str:
        text = text.strip()
        c = self.db.find(text)
        if c:
            return c.key
        hits = self.db.search(text, limit=1)
        if hits:
            return hits[0].key
        raise KeyError(f"no card matches {text!r}")


# --------------------------------------------------------------------------
# Text rendering (terminal / overlay share this)
# --------------------------------------------------------------------------

def render_text(db: CardDB, st: GameState, an: Analysis, rep: Optional[VisionReport] = None) -> str:
    lines = []
    sign = "+" if an.eval >= 0 else ""
    lines.append(f"eval {sign}{an.eval:.1f}   (towers {an.eval_breakdown['towers']:+.1f}, elixir {an.eval_breakdown['elixir']:+.1f}, field {an.eval_breakdown['field']:+.1f})")
    hand = ", ".join(db.get(k).name if k and db.find(k) else "?" for k in st.hand) or "?"
    lines.append(f"you {st.my_elixir:.1f}  |  opp ~{st.opp.elixir:.1f}  |  {int(st.time_left) // 60}:{int(st.time_left) % 60:02d} {'OT ' if st.overtime else ''}{st.phase}")
    lines.append(f"hand: {hand}" + (f"   next: {db.get(st.next_card).name}" if st.next_card and db.find(st.next_card) else ""))
    if an.threats:
        lines.append("threats: " + ", ".join(f"{db.get(u.card).name} ({u.lane}, {w:.1f})" for u, w in an.threats[:4]))
    lines.append("")
    for i, r in enumerate(an.recommendations, 1):
        lines.append(f"{i}. {r.text(db, st)}")
        if r.reasons:
            lines.append("      " + "; ".join(r.reasons[:3]))
    lines.append("")
    lines += an.notes
    return "\n".join(lines)
