"""Game state model.

Coordinates use the arena tile grid: 18 tiles wide (x: 0..18, left to right
from *my* point of view) and 32 tiles tall (y: 0 at my king tower, 32 at the
opponent's king tower). The river is at y = 16. Princess towers sit at roughly
(3.5, 6.5) / (14.5, 6.5) for me and (3.5, 25.5) / (14.5, 25.5) for the opponent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ARENA_W = 18.0
ARENA_H = 32.0
RIVER_Y = 16.0

PRINCESS_TOWER_HP = 3052   # level 11
KING_TOWER_HP = 4824       # level 11

MY_TOWER_POS = {"left": (3.5, 6.5), "right": (14.5, 6.5), "king": (9.0, 2.5)}
OPP_TOWER_POS = {"left": (3.5, 25.5), "right": (14.5, 25.5), "king": (9.0, 29.5)}


def lane_of_x(x: float) -> str:
    if x < 7.5:
        return "left"
    if x > 10.5:
        return "right"
    return "center"


@dataclass
class Unit:
    """A troop or building on the field."""

    card: str                 # card key
    side: str                 # "me" | "opp"
    x: float                  # tiles, 0..18
    y: float                  # tiles, 0..32 (0 = my king)
    hp_frac: float = 1.0      # remaining health fraction, 0..1
    count: int = 0            # 0 => use card default
    id: Optional[str] = None  # tracker id from the detector, if any

    @property
    def lane(self) -> str:
        return lane_of_x(self.x)

    @property
    def on_my_side(self) -> bool:
        return self.y < RIVER_Y


@dataclass
class Tower:
    hp: Optional[float] = None    # None => unknown (vision could not read it)
    max_hp: float = PRINCESS_TOWER_HP
    alive: bool = True

    @property
    def frac(self) -> float:
        if not self.alive:
            return 0.0
        if self.hp is None:
            return 1.0
        return max(0.0, min(1.0, self.hp / self.max_hp))

    @property
    def hp_or_max(self) -> float:
        if not self.alive:
            return 0.0
        return self.max_hp if self.hp is None else self.hp


def default_towers() -> Dict[str, Tower]:
    return {
        "my_left": Tower(), "my_right": Tower(), "my_king": Tower(max_hp=KING_TOWER_HP),
        "opp_left": Tower(), "opp_right": Tower(), "opp_king": Tower(max_hp=KING_TOWER_HP),
    }


@dataclass
class OpponentInfo:
    """What we know / estimate about the opponent (filled by OpponentTracker)."""

    elixir: float = 5.0
    known_deck: List[str] = field(default_factory=list)
    predicted_hand: List[str] = field(default_factory=list)   # cards believed to be in hand now
    out_of_hand: List[str] = field(default_factory=list)      # last 4 distinct cards played
    unknown_slots: int = 8                                    # deck slots not yet identified


@dataclass
class GameState:
    time_left: float = 180.0          # seconds left in the current period
    overtime: bool = False
    my_elixir: float = 5.0
    hand: List[str] = field(default_factory=list)       # up to 4 card keys ("" / None = unknown)
    next_card: Optional[str] = None
    my_deck: List[str] = field(default_factory=list)    # all 8 if known
    opp: OpponentInfo = field(default_factory=OpponentInfo)
    towers: Dict[str, Tower] = field(default_factory=default_towers)
    units: List[Unit] = field(default_factory=list)

    # ----- elixir timing ---------------------------------------------------
    @property
    def elixir_multiplier(self) -> int:
        if self.overtime:
            return 3 if self.time_left <= 60 else 2
        return 2 if self.time_left <= 60 else 1

    @property
    def seconds_per_elixir(self) -> float:
        return 2.8 / self.elixir_multiplier

    @property
    def phase(self) -> str:
        m = self.elixir_multiplier
        return {1: "single", 2: "double", 3: "triple"}[m]

    # ----- convenience -----------------------------------------------------
    def my_units(self) -> List[Unit]:
        return [u for u in self.units if u.side == "me"]

    def opp_units(self) -> List[Unit]:
        return [u for u in self.units if u.side == "opp"]

    def playable_hand(self) -> List[str]:
        return [c for c in self.hand if c]

    def tower(self, name: str) -> Tower:
        return self.towers[name]

    # ----- (de)serialisation ----------------------------------------------
    def to_dict(self) -> dict:
        return {
            "time_left": self.time_left,
            "overtime": self.overtime,
            "my_elixir": self.my_elixir,
            "hand": list(self.hand),
            "next_card": self.next_card,
            "my_deck": list(self.my_deck),
            "opp": {
                "elixir": self.opp.elixir,
                "known_deck": list(self.opp.known_deck),
                "predicted_hand": list(self.opp.predicted_hand),
                "out_of_hand": list(self.opp.out_of_hand),
                "unknown_slots": self.opp.unknown_slots,
            },
            "towers": {k: {"hp": t.hp, "max_hp": t.max_hp, "alive": t.alive} for k, t in self.towers.items()},
            "units": [
                {"card": u.card, "side": u.side, "x": u.x, "y": u.y, "hp_frac": u.hp_frac, "count": u.count}
                for u in self.units
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        st = cls()
        st.time_left = float(d.get("time_left", 180))
        st.overtime = bool(d.get("overtime", False))
        st.my_elixir = float(d.get("my_elixir", 5))
        st.hand = list(d.get("hand", []))
        st.next_card = d.get("next_card")
        st.my_deck = list(d.get("my_deck", []))
        o = d.get("opp", {})
        st.opp = OpponentInfo(
            elixir=float(o.get("elixir", 5)),
            known_deck=list(o.get("known_deck", [])),
            predicted_hand=list(o.get("predicted_hand", [])),
            out_of_hand=list(o.get("out_of_hand", [])),
            unknown_slots=int(o.get("unknown_slots", 8 - len(o.get("known_deck", [])))),
        )
        towers = default_towers()
        for k, tv in d.get("towers", {}).items():
            if k not in towers:
                continue
            if isinstance(tv, (int, float)):
                towers[k].hp = float(tv)
                towers[k].alive = tv > 0
            else:
                towers[k].hp = tv.get("hp")
                towers[k].max_hp = float(tv.get("max_hp", towers[k].max_hp))
                towers[k].alive = bool(tv.get("alive", True)) and (towers[k].hp is None or towers[k].hp > 0)
        st.towers = towers
        st.units = [
            Unit(card=u["card"], side=u.get("side", "opp"), x=float(u.get("x", 9)), y=float(u.get("y", 16)),
                 hp_frac=float(u.get("hp_frac", 1.0)), count=int(u.get("count", 0)))
            for u in d.get("units", [])
        ]
        return st
