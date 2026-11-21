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
from .tracker import CycleTracker, OpponentTracker, TradeLedger
from .vision.capture import crop_game_frame, find_game_frame
from .vision.elixir import read_elixir
from .vision.hand import CardMatcher, read_hand
from .vision.layout import TOWER_REGIONS, Layout
from .vision.ocr import has_tesseract, read_clock, read_digits
from .vision.units import NullDetector, UnitDetector
from .vision.healthbars import HealthbarDetector
from .vision.unit_classifier import UnitClassifier

REGULATION = 180
OVERTIME = 120


@dataclass
class MatchClock:
    """Keeps the match clock, from OCR when available, else wall time."""

    started_at: Optional[float] = None
    ocr_time_left: Optional[int] = None
    ocr_at: float = 0.0
    overtime: bool = False
    external_elapsed: Optional[float] = None   # set by video replay: seconds since match start from the file

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
        if self.external_elapsed is not None:
            e = self.external_elapsed
            if e <= REGULATION:
                self.overtime = False
                return REGULATION - e
            self.overtime = True
            return max(0.0, OVERTIME - (e - REGULATION))
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
        if self.external_elapsed is not None:
            return self.external_elapsed
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
        unit_templates: Optional[Path] = None,
        detect_units: bool = True,
    ):
        self.db = db or default_db()
        self.layout = layout or Layout.load()
        self.matcher = matcher if matcher is not None else CardMatcher()
        self.classifier = UnitClassifier(unit_templates) if unit_templates else UnitClassifier()
        if detector is not None:
            self.detector = detector
        elif detect_units:
            self.detector = HealthbarDetector(self.classifier)
        else:
            self.detector = NullDetector()
        self.engine = engine or Engine(self.db)
        self.tracked: List[dict] = []          # units seen last frame: {unit, crop, first_seen, labelled}
        self.pending_my_deploy: List[Tuple[str, float]] = []   # (card, deadline) awaiting a new friendly bar
        self.events: List[dict] = []           # deploy events (for `learn`)
        self.last_play_t: float = 0.0
        self.auto_frame = auto_frame
        self.use_ocr = has_tesseract() if use_ocr is None else use_ocr
        self.opp = OpponentTracker(self.db)
        self.me = CycleTracker()
        self.ledger = TradeLedger()
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
                if self.db.find(old):
                    self.ledger.add("me", old, self.db.get(old).cost, self.clock.elapsed())
                self.pending_my_deploy.append((old, time.time() + 2.0))
                self.last_play_t = time.time()
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
        self._track_units(units, st)
        units += self.manual_units
        st.units = units
        self.last_state = st
        self.last_report = rep
        return st

    # ----- unit tracking + auto-labelling --------------------------------
    def _track_units(self, units: List[Unit], st: GameState) -> None:
        """Match detected units to last frame's, flag new ones, auto-label deploys."""
        now = time.time()
        crops = getattr(self.detector, "last_crops", [None] * len(units))
        prev = self.tracked
        new_tracked: List[dict] = []
        for u, crop in zip(units, crops):
            match = None
            for t in prev:
                pu = t["unit"]
                if pu.side == u.side and abs(pu.x - u.x) < 2.0 and abs(pu.y - u.y) < 3.0 and not t.get("taken"):
                    match = t
                    break
            if match is not None:
                match["taken"] = True
                entry = {"unit": u, "crop": crop, "first_seen": match["first_seen"], "label": match.get("label")}
                if entry["label"] and u.card == "unknown":
                    u.card = entry["label"]             # keep an identity once assigned
            else:
                entry = {"unit": u, "crop": crop, "first_seen": now, "label": None if u.card == "unknown" else u.card}
                self._on_new_unit(entry, st)
            new_tracked.append(entry)
        self.tracked = new_tracked
        self.pending_my_deploy = [(c, d) for c, d in self.pending_my_deploy if d > now]

    def _on_new_unit(self, entry: dict, st: GameState) -> None:
        u: Unit = entry["unit"]
        if u.side == "me" and self.pending_my_deploy:
            card, _ = self.pending_my_deploy[0]
            ok = u.y <= 17.0 or any(not st.towers[k].alive for k in ("opp_left", "opp_right"))
            if ok:
                self.pending_my_deploy.pop(0)
                self._label(entry, card)
                self.events.append(self._event(card, u, st))

    def _label(self, entry: dict, card: str) -> None:
        entry["label"] = card
        entry["unit"].card = card
        if entry.get("crop") is not None and getattr(entry["crop"], "size", 0):
            self.classifier.add(card, entry["crop"], save=bool(self.classifier.root))

    def label_recent_enemy(self, card: str, window: float = 3.0) -> int:
        """Called when the user reports an opponent play: label enemy units that just appeared."""
        now = time.time()
        n = 0
        for t in self.tracked:
            u = t["unit"]
            if u.side == "opp" and t.get("label") is None and now - t["first_seen"] <= window:
                self._label(t, card)
                if self.last_state is not None:
                    self.events.append(self._event(card, u, self.last_state))
                n += 1
        return n

    def _event(self, card: str, u: Unit, st: GameState) -> dict:
        enemies = [e for e in st.units if e.side != u.side]
        same_lane = [e for e in enemies if e.lane == u.lane]
        return {
            "t": round(self.clock.elapsed(), 1), "card": card, "side": u.side, "x": round(u.x, 1), "y": round(u.y, 1),
            "lane": u.lane, "my_elixir": st.my_elixir if u.side == "me" else st.opp.elixir, "phase": st.phase,
            "enemy_units": len(enemies), "enemy_same_lane": len(same_lane),
            "enemy_on_my_side": sum(1 for e in enemies if (e.y < 16) == (u.side == "me")),
            "nearest_enemy_y": round(min((abs(e.y - u.y) for e in same_lane), default=99.0), 1),
            "enemy_cards": sorted({e.card for e in same_lane if e.card != "unknown"}),
        }

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
                card, flag = self._resolve_flagged(rest)
                self._flag(card, flag)
                self.opp.record_play(card, self.clock.elapsed())
                self.ledger.add("opp", card, self.db.get(card).cost, self.clock.elapsed())
                n = self.label_recent_enemy(card)
                tag = f", labelled {n} unit crop(s)" if n else ""
                return f"opponent played {self.db.get(card).name} (elixir ~{self.opp.elixir.elixir:.1f}){tag}"
            if op in ("u", "undo"):
                c = self.opp.undo_last()
                if c and self.ledger.opp_plays:
                    self.ledger.opp_plays.pop()
                return f"undid {self.db.get(c).name}" if c else "nothing to undo"
            if op in ("d", "deck"):
                deck = []
                for part in rest.replace(";", ",").split(","):
                    if part.strip():
                        card, flag = self._resolve_flagged(part)
                        self._flag(card, flag)
                        deck.append(card)
                self.opp.cycle.set_deck(deck)
                tagged = ", ".join(f"{f} {self.db.get(c).name}" for c, f in self.opp.flags.items() if c in deck)
                return f"opponent deck set ({len(deck)} cards{'; ' + tagged if tagged else ''})"
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
                self.ledger.reset()
                self.clock.start()
                self.manual_units.clear()
                self.last_state = None
                self.last_hand = [None] * 4
                self.frame_bbox = None
                self.tracked.clear()
                self.pending_my_deploy.clear()
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

    def counter_panel(self) -> dict:
        """Everything a card-counter / elixir-tracker panel needs."""
        db = self.db
        name = lambda k: (db.get(k).name if k and db.find(k) else None)
        el = self.opp.elixir
        rows = []
        for r in self.opp.cycle.status():
            rows.append({**r, "name": name(r["card"]) or "?", "cost": (db.get(r["card"]).cost if r["card"] and db.find(r["card"]) else None),
                         "flag": self.opp.flags.get(r["card"]) if r["card"] else None})
        nxt = self.opp.cycle.next_card()
        elapsed = self.clock.elapsed()
        my_rows = []
        for r in self.me.status():
            my_rows.append({**r, "name": name(r["card"]) or "?"})
        return {
            "opp_cards": rows, "opp_next_back": name(nxt), "opp_unknown": self.opp.cycle.unknown_slots,
            "opp_elixir": round(el.elixir, 1), "opp_elixir_low": round(max(0.0, el.elixir - el.uncertainty), 1),
            "opp_leaking_s": round(el.leaking_for(), 1), "opp_leaked_total": round(el.leaked, 1),
            "opp_history": el.history[-60:],
            "spent_me": self.ledger.spent("me"), "spent_opp": self.ledger.spent("opp"),
            "lead_total": round(self.ledger.lead(), 1), "lead_30s": round(self.ledger.lead(since=elapsed - 30), 1),
            "trades": self.ledger.trades(), "my_cards": my_rows, "my_next_back": name(self.me.next_card()),
        }

    def _resolve_flagged(self, text: str) -> Tuple[str, Optional[str]]:
        """'evo knight' -> ('knight', 'evo'); 'hero musketeer' -> ('musketeer', 'hero')."""
        t = text.strip()
        low = t.lower()
        for prefix, flag in (("evo ", "evo"), ("evolved ", "evo"), ("evolution ", "evo"), ("hero ", "hero")):
            if low.startswith(prefix):
                return self._resolve(t[len(prefix):]), flag
        return self._resolve(t), None

    def _flag(self, card: str, flag: Optional[str]) -> None:
        if flag:
            self.opp.flags[card] = flag

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
        lines.append("threats: " + ", ".join(f"{db.get(u.card).name} ({u.lane}, y{u.y:.0f}, {w:.1f})" for u, w in an.threats[:4]))
    mine = st.my_units()
    if mine:
        lines.append("yours: " + ", ".join(f"{db.get(u.card).name} ({u.lane}, y{u.y:.0f})" for u in mine[:4]))
    lines.append("")
    for i, r in enumerate(an.recommendations, 1):
        lines.append(f"{i}. {r.text(db, st)}")
        if r.reasons:
            lines.append("      " + "; ".join(r.reasons[:3]))
    lines.append("")
    lines += an.notes
    return "\n".join(lines)
